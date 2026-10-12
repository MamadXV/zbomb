# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Explicit, typed domain models shared by every layer.

These dataclasses describe the *what* of an operation. They never import a
rendering library and never look at ``sys.stdout``, so they can be built,
compared and tested in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

__all__ = [
    "ArchiveError",
    "ArchiveJob",
    "ArchiveOptions",
    "ArchivePlan",
    "ArchiveProgress",
    "FileSelection",
    "OperationOutcome",
    "RiskLevel",
    "RiskWarning",
    "ScanOutcome",
    "AppSettings",
]


class RiskLevel(str, Enum):
    """How much attention a warning deserves."""

    INFO = "info"
    WARNING = "warning"
    DANGER = "danger"

    @classmethod
    def from_any(cls, value) -> "RiskLevel":
        """Coerce a string/int/bool into a level (defaults to ``WARNING``)."""
        if isinstance(value, RiskLevel):
            return value
        if isinstance(value, str):
            try:
                return cls(value.strip().lower())
            except ValueError:
                return cls.WARNING
        return cls.WARNING


@dataclass(frozen=True)
class RiskWarning:
    """One pre-flight warning, with enough context to act on it."""

    message: str
    level: RiskLevel = RiskLevel.WARNING
    source: str = ""

    def as_dict(self) -> dict:
        return {"message": self.message, "level": self.level.value, "source": self.source}


class ArchiveError(Exception):
    """A user-facing archive failure, with a class and an actionable hint.

    The ``kind`` classifies the problem (``permission``, ``disk``,
    ``exists``, ``corrupt``, ``usage``, ``interrupted``, ``unknown``) so the
    CLI can map it onto an exit code and the TUI can render friendly copy
    instead of a traceback.
    """

    KINDS = (
        "usage",
        "exists",
        "permission",
        "disk",
        "corrupt",
        "interrupted",
        "policy",
        "unknown",
    )

    def __init__(
        self,
        message: str,
        kind: str = "unknown",
        *,
        path: Path | None = None,
        hint: str = "",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.kind = "unknown" if kind not in self.KINDS else kind
        self.path = Path(path) if path else None
        self.hint = hint

    @classmethod
    def from_exception(
        cls, exc: BaseException, *, path: Path | None = None
    ) -> "ArchiveError":
        """Classify a low-level exception into a friendly :class:`ArchiveError`."""
        import errno as _errno

        message = str(exc) or exc.__class__.__name__
        kind = "unknown"
        hint = ""
        if isinstance(exc, KeyboardInterrupt):
            kind = "interrupted"
            hint = "the partial archive was finalised; use --resume to continue"
        elif isinstance(exc, FileExistsError):
            kind = "exists"
            hint = "choose another name or allow overwriting"
        elif isinstance(exc, FileNotFoundError):
            kind = "usage"
            hint = "check that the path exists and is spelled correctly"
        elif isinstance(exc, PermissionError):
            kind = "permission"
            hint = "choose a writable destination or check directory permissions"
        elif isinstance(exc, IsADirectoryError):
            kind = "usage"
            hint = "that path is a directory; give a file name instead"
        elif isinstance(exc, OSError):
            code = getattr(exc, "errno", None)
            if code in (_errno.ENOSPC, 122):  # disk full (POSIX / Windows)
                kind = "disk"
                hint = "free some space or pick another destination"
            else:
                kind = "unknown"
        elif isinstance(exc, ValueError):
            kind = "usage"
        return cls(message, kind, path=path, hint=hint)

    def as_dict(self) -> dict:
        return {
            "message": self.message,
            "kind": self.kind,
            "path": str(self.path) if self.path else None,
            "hint": self.hint,
        }


@dataclass
class ArchiveOptions:
    """Every knob the lab accepts for one build."""

    method: str = "deflate"
    level: int | None = None
    split: int | None = None
    chunk_bytes: int = 4 * 1024 * 1024
    recipe: str = "flat"
    name_style: str = "plain"
    preamble: str = "none"
    layers: int | None = None
    fanout: int | None = None
    entries: int | None = None
    verify: str = "sample"
    overwrite: bool = True
    resume: bool = False
    generate: bool = True

    def as_dict(self) -> dict:
        return {
            "method": self.method,
            "level": self.level,
            "split": self.split,
            "chunk_bytes": self.chunk_bytes,
            "recipe": self.recipe,
            "name_style": self.name_style,
            "preamble": self.preamble,
            "layers": self.layers,
            "fanout": self.fanout,
            "entries": self.entries,
            "verify": self.verify,
            "overwrite": self.overwrite,
            "resume": self.resume,
            "generate": self.generate,
        }


@dataclass
class FileSelection:
    """The files and directories one build draws from.

    The classic lab genuinely *generates* zeros (``generate=True``); when a
    real path is supplied the same job can archive that tree instead. Either
    way the model is explicit rather than implied by flags in a dozen places.
    """

    roots: tuple[Path, ...] = ()
    include_hidden: bool = False
    generate: bool = True

    @property
    def has_sources(self) -> bool:
        return bool(self.roots)

    def display(self) -> str:
        if self.generate and not self.roots:
            return "generated zeros (no source tree)"
        return ", ".join(str(root) for root in self.roots) or "(none)"

    def as_dict(self) -> dict:
        return {
            "roots": [str(root) for root in self.roots],
            "include_hidden": self.include_hidden,
            "generate": self.generate,
        }


@dataclass
class ArchiveJob:
    """One unit of work: write *target_bytes* (or *selection*) to *output*."""

    output: Path
    target_bytes: int
    options: ArchiveOptions = field(default_factory=ArchiveOptions)
    selection: FileSelection = field(default_factory=FileSelection)
    label: str = ""

    def as_dict(self) -> dict:
        return {
            "output": str(self.output),
            "target_bytes": self.target_bytes,
            "options": self.options.as_dict(),
            "selection": self.selection.as_dict(),
            "label": self.label,
        }


@dataclass(frozen=True)
class ArchivePlan:
    """A modelled (not yet built) archive, ready for confirmation.

    ``detail`` carries the method-specific dictionary (an ``Estimate`` or a
    ``BombPlan``) so the risk layer and the renderers keep every number
    without re-deriving it.
    """

    recipe: str
    method: str
    level: int
    target_bytes: int
    output_bytes: int
    ratio: float
    seconds: float
    entries: int
    zip64: bool
    encoder_memory: int
    expanded_bytes: int = 0
    measured: bool = True
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        data = dict(self.detail)
        data.update(
            {
                "recipe": self.recipe,
                "method": self.method,
                "level": self.level,
                "target_bytes": self.target_bytes,
                "output_bytes": self.output_bytes,
                "ratio": round(self.ratio, 3),
                "seconds": round(self.seconds, 2),
                "entries": self.entries,
                "zip64_required": self.zip64,
                "encoder_memory_bytes": self.encoder_memory,
                "expanded_bytes": self.expanded_bytes,
                "measured": self.measured,
            }
        )
        return data


@dataclass(frozen=True)
class ArchiveProgress:
    """One real progress sample emitted while bytes are being written."""

    written: int
    total: int
    label: str = ""

    @property
    def fraction(self) -> float:
        return 0.0 if self.total <= 0 else min(self.written / self.total, 1.0)

    @property
    def percent(self) -> float:
        return self.fraction * 100.0

    def as_dict(self) -> dict:
        return {
            "written": self.written,
            "total": self.total,
            "fraction": round(self.fraction, 6),
            "label": self.label,
        }


@dataclass
class ScanOutcome:
    """Result of scanning one archive, plus the code the CLI should return."""

    path: str
    suspicious: bool
    exit_code: int
    report: dict = field(default_factory=dict)
    reasons: tuple[str, ...] = ()
    max_ratio: float = 0.0
    error: str = ""

    def as_dict(self) -> dict:
        return dict(self.report)


@dataclass
class OperationOutcome:
    """A finished operation: what happened, and everything needed to show it."""

    kind: str
    ok: bool
    result: dict = field(default_factory=dict)
    warnings: tuple[RiskWarning, ...] = ()
    error: ArchiveError | None = None
    exit_code: int = 0
    seconds: float = 0.0
    detail: str = ""

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "ok": self.ok,
            "result": dict(self.result),
            "warnings": [w.as_dict() for w in self.warnings],
            "error": self.error.as_dict() if self.error else None,
            "exit_code": self.exit_code,
        }


@dataclass
class AppSettings:
    """Typed view over the persisted settings file.

    Kept as a thin, explicit view so callers depend on names rather than on
    the storage format (which stays backwards compatible elsewhere).
    """

    output_dir: str = "."
    method: str = "deflate"
    level: int = 9
    size: str = "100MB"
    chunk: str = "4MiB"
    split: str = ""
    progress: str = "auto"
    verify: str = "sample"
    confirm_before_write: bool = True
    theme: str = "ember"
    compact: bool = False

    @classmethod
    def from_config(cls, config) -> "AppSettings":
        """Build a view from a ``core.Config`` (or any object with the attrs)."""
        names = cls.__dataclass_fields__.keys()
        return cls(**{name: getattr(config, name) for name in names if hasattr(config, name)})

    def as_dict(self) -> dict:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


__credit__ = "ZipBomb Lab - zipbomb_lab.domain.models - made by Xv @XvRendering https://github.com/MamadXV"
