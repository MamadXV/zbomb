# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""The one place that orchestrates real archive work.

Every front end — the classic CLI, the new headless commands and the Textual
TUI — goes through :class:`ArchiveService`. It owns planning, policy gating,
the write itself, audit recording and error classification, and it publishes
structured events rather than printing anything.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from ..domain.models import (
    ArchiveError,
    ArchiveJob,
    ArchivePlan,
    OperationOutcome,
    RiskWarning,
    ScanOutcome,
)
from ..infrastructure.audit import AuditLog, default_audit_log
from ..infrastructure.logging import get_logger
from . import risk as risk_tool
from .events import (
    ArchiveCompletedEvent,
    ArchiveFailedEvent,
    ArchivePlannedEvent,
    ArchiveWarningEvent,
    EventBus,
    ScanCompletedEvent,
)
from .progress import BridgeProgress

__all__ = ["ArchiveService", "PreparedArchive"]


@dataclass
class PreparedArchive:
    """A modelled archive plus the raw estimator/plan behind it.

    ``summary`` is the stable, presentation-friendly view; ``raw`` is the
    original ``Estimate`` or ``BombPlan`` object, kept so the classic printers
    keep rendering exactly what they always did.
    """

    summary: ArchivePlan
    raw: object
    job: ArchiveJob

    @property
    def is_recipe(self) -> bool:
        return self.job.options.recipe not in ("", "flat")


class ArchiveService:
    """Plan, gate and build archives; scan them back; record the audit trail."""

    def __init__(self, bus: EventBus | None = None, audit: AuditLog | None = None) -> None:
        self.bus = bus or EventBus()
        self.audit = audit or default_audit_log()
        self.log = get_logger("services.archive")

    # -- planning ----------------------------------------------------------
    def plan(self, job: ArchiveJob) -> PreparedArchive:
        """Model *job* without writing anything (raises :class:`ArchiveError`)."""
        from ..core import METHODS

        opts = job.options
        method = (opts.method or "deflate").lower()
        if method not in METHODS:
            raise ArchiveError(
                f"unknown method {opts.method!r} - choose one of: {', '.join(sorted(METHODS))}",
                "usage",
            )
        if int(job.target_bytes) <= 0:
            raise ArchiveError("target size must be greater than zero", "usage")

        try:
            if opts.recipe and opts.recipe != "flat":
                from ..engine import plan as plan_recipe

                raw = plan_recipe(
                    opts.recipe,
                    job.target_bytes,
                    method,
                    opts.level,
                    opts.layers,
                    opts.fanout,
                    opts.entries,
                    opts.name_style,
                    opts.preamble,
                )
                summary = ArchivePlan(
                    recipe=raw.recipe,
                    method=raw.method,
                    level=raw.level,
                    target_bytes=raw.expanded_bytes,
                    output_bytes=raw.archive_bytes,
                    ratio=raw.ratio,
                    seconds=raw.seconds,
                    entries=raw.outer_entries,
                    zip64=raw.zip64,
                    encoder_memory=self._encoder_memory(raw.method, raw.level),
                    expanded_bytes=raw.expanded_bytes,
                    measured=raw.measured,
                    detail=raw.as_dict(),
                )
            else:
                from ..core import estimate as estimate_method

                raw = estimate_method(job.target_bytes, method, opts.level, opts.split)
                summary = ArchivePlan(
                    recipe="flat",
                    method=raw.method,
                    level=raw.level,
                    target_bytes=raw.target_bytes,
                    output_bytes=raw.output_bytes,
                    ratio=raw.ratio,
                    seconds=raw.seconds,
                    entries=raw.entries,
                    zip64=raw.zip64_required,
                    encoder_memory=raw.encoder_memory,
                    expanded_bytes=raw.target_bytes,
                    measured=True,
                    detail=raw.as_dict(),
                )
        except ArchiveError:
            raise
        except (ValueError, KeyError) as exc:
            raise ArchiveError(str(exc), "usage", path=job.output) from exc

        prepared = PreparedArchive(summary=summary, raw=raw, job=job)
        self.bus.publish(
            ArchivePlannedEvent(
                job_label=job.label,
                recipe=summary.recipe,
                method=summary.method,
                output_bytes=summary.output_bytes,
                ratio=summary.ratio,
                seconds=summary.seconds,
                detail=summary.as_dict(),
            )
        )
        return prepared

    @staticmethod
    def _encoder_memory(method: str, level: int | None) -> int:
        from ..core import approx_encoder_memory

        try:
            return approx_encoder_memory(method, level)
        except Exception:  # pragma: no cover - defensive
            return 0

    # -- gating ------------------------------------------------------------
    def risks(
        self,
        prepared: PreparedArchive,
        *,
        force: bool = False,
        ack: str | None = None,
    ) -> list[RiskWarning]:
        """Run the safety policy; return typed warnings (raises on refusal)."""
        from ..core import PolicyError, check_create, check_recipe

        job = prepared.job
        overwrite = job.options.overwrite
        try:
            if prepared.is_recipe:
                messages = check_recipe(
                    job.output, prepared.raw, force=force, ack=ack, overwrite=overwrite
                )
            else:
                messages = check_create(
                    job.output, prepared.raw, force=force, ack=ack, overwrite=overwrite
                )
        except PolicyError as exc:
            raise ArchiveError(str(exc), "policy", path=job.output, hint=exc.kind) from exc

        return risk_tool.from_messages(messages, source="policy")

    def _publish_warnings(self, warnings) -> None:
        for warning in warnings:
            self.bus.publish(
                ArchiveWarningEvent(
                    job_label="",
                    message=warning.message,
                    level=warning.level.value,
                )
            )

    # -- writing -----------------------------------------------------------
    def create(
        self,
        prepared: PreparedArchive,
        *,
        warnings: list[RiskWarning] | None = None,
        ux=None,
        show_progress: bool = True,
    ) -> OperationOutcome:
        """Write *prepared* to disk, publishing real progress as it goes.

        When *ux* is supplied the classic printer keeps its own progress bar
        (this is what the existing CLI does). When it is ``None`` the service
        drives a :class:`BridgeProgress` so a TUI sees live byte counts.
        """
        from ..engine import build_bomb, create_archive
        from ..ui import UX

        job = prepared.job
        opts = job.options
        active = list(warnings or [])
        self._publish_warnings(active)
        notes = [w.message for w in active]

        started = time.perf_counter()
        bar = None
        if ux is None:
            label = f"building {opts.recipe}" if prepared.is_recipe else f"writing {opts.method}"
            if prepared.is_recipe:
                total = getattr(prepared.raw, "processed_bytes", 0) or prepared.summary.expanded_bytes
            else:
                total = prepared.summary.target_bytes
            bar = BridgeProgress(
                self.bus,
                label=label,
                total=int(total or 0),
                output=str(job.output),
                recipe=prepared.summary.recipe,
            )
        engine_ux = ux if ux is not None else UX("none")

        try:
            if prepared.is_recipe:
                result = build_bomb(
                    job.output,
                    prepared.raw,
                    ux=engine_ux,
                    verify=opts.verify,
                    overwrite=opts.overwrite,
                    show_progress=show_progress,
                    progress=bar,
                )
            else:
                result = create_archive(
                    job.output,
                    job.target_bytes,
                    method=opts.method,
                    level=opts.level,
                    chunk_bytes=opts.chunk_bytes,
                    split=opts.split,
                    ux=engine_ux,
                    show_progress=show_progress,
                    verify=opts.verify,
                    resume=opts.resume,
                    overwrite=opts.overwrite,
                    warnings=notes,
                    progress=bar,
                )
        except KeyboardInterrupt as exc:
            return self._failed(prepared, ArchiveError.from_exception(exc, path=job.output))
        except (FileExistsError, ValueError, OSError) as exc:
            return self._failed(prepared, ArchiveError.from_exception(exc, path=job.output))
        finally:
            if bar is not None:
                bar.close()

        extra = risk_tool.from_messages(
            [m for m in result.warnings if m not in notes], source="engine"
        )
        active.extend(extra)
        self._publish_warnings(extra)

        payload = result.as_dict()
        payload["path"] = str(result.path)
        self.bus.publish(ArchiveCompletedEvent(job_label=job.label, result=payload))
        return OperationOutcome(
            kind="create",
            ok=True,
            result=payload,
            warnings=tuple(active),
            exit_code=0,
            seconds=time.perf_counter() - started,
            detail=str(result.path),
        )

    def _failed(self, prepared: PreparedArchive, error: ArchiveError) -> OperationOutcome:
        self.log.warning("archive failed: %s (%s)", error.message, error.kind)
        self.bus.publish(ArchiveFailedEvent(job_label=prepared.job.label, error=error.as_dict()))
        return OperationOutcome(
            kind="create",
            ok=False,
            error=error,
            exit_code=self.exit_code_for(error),
            detail=error.message,
        )

    @staticmethod
    def exit_code_for(error: ArchiveError) -> int:
        """Map a classified failure onto the CLI's documented exit codes."""
        mapping = {
            "permission": 1,
            "disk": 1,
            "exists": 1,
            "corrupt": 3,
            "usage": 1,
            "policy": 1,
            "interrupted": 130,
            "unknown": 1,
        }
        return mapping.get(error.kind, 1)

    # -- scanning ----------------------------------------------------------
    def scan_reports(
        self,
        paths,
        *,
        max_ratio: float | None = None,
        max_total: int | None = None,
        deep: bool = False,
        max_depth: int | None = None,
        probe_bytes: int | None = None,
    ) -> tuple[list, int]:
        """Scan *paths*; return ``(reports, worst_exit_code)``.

        Mirrors ``cmd_inspect``'s semantics exactly: unreadable archives are
        reported (and counted) but never abort the batch, and exit codes are
        ``0`` / ``2`` / ``3`` per the documented CLI contract.
        """
        from ..engine import DEFAULT_MAX_DEPTH, DEFAULT_MAX_RATIO, DEFAULT_MAX_TOTAL
        from ..engine import DEFAULT_PROBE_BYTES, ZipBombError, scan_archive

        reports: list = []
        worst = 0
        for raw in paths:
            path = Path(raw)
            try:
                report = scan_archive(
                    path,
                    max_ratio=max_ratio if max_ratio is not None else DEFAULT_MAX_RATIO,
                    max_total=max_total if max_total is not None else DEFAULT_MAX_TOTAL,
                    deep=deep,
                    max_depth=max_depth or DEFAULT_MAX_DEPTH,
                    probe_bytes=probe_bytes if probe_bytes is not None else DEFAULT_PROBE_BYTES,
                )
            except ZipBombError as exc:
                self.log.warning("unreadable archive %s: %s", path, exc)
                self.bus.publish(
                    ScanCompletedEvent(
                        outcome=ScanOutcome(
                            path=str(path), suspicious=False, exit_code=3, error=str(exc)
                        ).as_dict()
                    )
                )
                worst = max(worst, 3)
                continue
            reports.append(report)
            worst = max(worst, report.exit_code)
            self.bus.publish(ScanCompletedEvent(outcome=report.as_dict()))
        return reports, worst

    def scan(self, path, **kwargs) -> ScanOutcome:
        """Scan a single archive, returning a structured outcome."""
        reports, _ = self.scan_reports([path], **kwargs)
        if not reports:
            return ScanOutcome(path=str(path), suspicious=False, exit_code=3, error="unreadable")
        report = reports[0]
        return ScanOutcome(
            path=report.path,
            suspicious=report.suspicious,
            exit_code=report.exit_code,
            report=report.as_dict(),
            reasons=tuple(report.reasons),
            max_ratio=report.max_ratio,
        )

    # -- audit -------------------------------------------------------------
    def record(self, result: dict, *, source: str = "service") -> None:
        """Append a created artifact to the audit log."""
        event = {
            "event": "created",
            "source": source,
            "path": result.get("path"),
            "method": result.get("method"),
            "level": result.get("level"),
            "ratio": round(float(result.get("ratio") or 0.0), 2),
            "seconds": round(float(result.get("seconds") or 0.0), 2),
            "entries": result.get("entries"),
        }
        for key in ("recipe", "declared_bytes", "archive_bytes", "expanded_bytes", "target_bytes"):
            if result.get(key) is not None:
                event[key] = result[key]
        self.audit.append(event)

    def record_refusal(self, reason: str, *, path=None, **extra) -> None:
        """Append a refused artifact to the audit log."""
        event = {"event": "refused", "reason": reason, "path": str(path) if path else None}
        event.update(extra)
        self.audit.append(event)


__credit__ = "ZipBomb Lab - zipbomb_lab.services.archive_service - made by Xv @XvRendering https://github.com/MamadXV"
