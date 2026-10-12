# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Create screen: configure, preview, confirm and build a real archive."""

from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    ProgressBar,
    Select,
    Static,
)

from ...core import format_duration, parse_size
from ...domain.data import default_output_name, method_rows, recipe_entries
from ...domain.models import ArchiveError, ArchiveJob, ArchiveOptions, RiskLevel
from ..widgets.preview import PlanPreview
from .base import LabScreen
from .settings import level_options

__all__ = ["CreateScreen"]

SIZE_PRESETS = ("100MB", "1GiB", "10GiB", "100GiB", "500GiB", "1TiB")


class CreateScreen(LabScreen):
    """The end-to-end build workflow, with a live plan and real progress."""

    key_context = "form"
    BINDINGS = [("escape", "app.back", "back")]

    def compose_body(self) -> ComposeResult:
        methods = [(f"{m['key']} - {m['label']}", m["key"]) for m in method_rows()]
        recipes = [(f"{r['key']} - {r['label']}", r["key"]) for r in recipe_entries()]
        yield Static("Create an archive", classes="title")
        yield Static(
            "payloads are generated zeros - nothing is read from disk", classes="tagline"
        )
        with Horizontal(classes="field-row"):
            yield Static("method", classes="field-label")
            yield Select(methods, value="deflate", allow_blank=False, id="method")
        with Horizontal(classes="field-row"):
            yield Static("level", classes="field-label")
            yield Select(level_options(), value=9, allow_blank=False, id="level")
        with Horizontal(classes="field-row"):
            yield Static("target size", classes="field-label")
            yield Input(value="100MB", id="size")
        with Horizontal(classes="field-row"):
            yield Static("preset", classes="field-label")
            yield Select(
                [(p, p) for p in SIZE_PRESETS], value="100MB", allow_blank=True, id="size-preset"
            )
        with Horizontal(classes="field-row"):
            yield Static("recipe", classes="field-label")
            yield Select(recipes, value="flat", allow_blank=False, id="recipe")
        with Horizontal(classes="field-row"):
            yield Static("entry names", classes="field-label")
            yield Select(
                [("plain", "plain"), ("mimic (disguise)", "mimic")],
                value="plain",
                allow_blank=False,
                id="names",
            )
        with Horizontal(classes="field-row"):
            yield Static("preamble", classes="field-label")
            yield Select(
                [("none", "none"), ("pdf", "pdf"), ("html", "html"), ("gif", "gif")],
                value="none",
                allow_blank=False,
                id="preamble",
            )
        with Horizontal(classes="field-row"):
            yield Static("verify", classes="field-label")
            yield Select(
                [("none", "none"), ("sample", "sample"), ("full", "full")],
                value="sample",
                allow_blank=False,
                id="verify",
            )
        with Horizontal(classes="field-row"):
            yield Static("output", classes="field-label")
            yield Input(value="", placeholder="path to write (.zip)", id="output")
        yield Checkbox("overwrite an existing file", value=True, id="overwrite")
        with Horizontal(classes="buttons"):
            yield Button("Preview", id="preview-btn")
            yield Button("Create archive", variant="primary", id="create-btn")
        yield PlanPreview(id="plan")
        yield ProgressBar(total=100, show_eta=False, id="progress")
        yield Static("", id="progress-text")

    def on_mount(self) -> None:
        super().on_mount()
        self.call_after_refresh(self._initialise)

    def _initialise(self) -> None:
        self._prepare_defaults()
        self.set_interval(0.15, self.progress_tick)
        self.recompute()

    def __init__(self) -> None:
        super().__init__()
        self._prepared = None
        self._warnings: list = []
        self._default_output_dir: Path = Path.cwd()
        self._ready = False

    # -- defaults ----------------------------------------------------------
    def _prepare_defaults(self) -> None:
        config = self.app.config
        state = self.app.state
        if config is not None:
            self.query_one("#method", Select).value = getattr(config, "method", "deflate")
            try:
                self.query_one("#level", Select).value = int(getattr(config, "level", 9))
            except Exception:
                pass
            self.query_one("#size", Input).value = str(getattr(config, "size", "100MB"))
            self.query_one("#verify", Select).value = getattr(config, "verify", "sample")
            base = Path(getattr(config, "output_dir", ".") or ".")
        else:
            base = state.navigation.directory
        if not base.is_absolute():
            base = (Path.cwd() / base).resolve()
        state.navigation.directory = base
        self._default_output_dir = base
        self._refresh_output_name()

    def _refresh_output_name(self) -> None:
        output = self.query_one("#output", Input)
        if output.value:
            return
        method = self.query_one("#method", Select).value or "deflate"
        recipe = self.query_one("#recipe", Select).value or "flat"
        size = self.query_one("#size", Input).value or "100MB"
        name = default_output_name(size, str(method), self._level(), str(recipe))
        try:
            output.value = str(self._default_output_dir / name)
        except Exception:
            pass

    # -- model building ----------------------------------------------------
    def _level(self) -> int | None:
        try:
            return int(self.query_one("#level", Select).value)
        except Exception:
            return None

    def _options(self) -> ArchiveOptions:
        method = str(self.query_one("#method", Select).value or "deflate")
        return ArchiveOptions(
            method=method,
            level=self._level(),
            recipe=str(self.query_one("#recipe", Select).value or "flat"),
            name_style=str(self.query_one("#names", Select).value or "plain"),
            preamble=str(self.query_one("#preamble", Select).value or "none"),
            verify=str(self.query_one("#verify", Select).value or "sample"),
            overwrite=bool(self.query_one("#overwrite", Checkbox).value),
        )

    def _job(self) -> ArchiveJob | None:
        raw = self.query_one("#size", Input).value.strip()
        try:
            target = parse_size(raw)
        except Exception as exc:
            self._preview_error(f"cannot parse size {raw!r}: {exc}")
            return None
        output_raw = self.query_one("#output", Input).value.strip()
        output = Path(output_raw).expanduser() if output_raw else (
            self._default_output_dir / "zeros.zip"
        )
        return ArchiveJob(output=output, target_bytes=target, options=self._options())

    # -- preview -----------------------------------------------------------
    def _preview_error(self, message: str) -> None:
        self.query_one("#plan", PlanPreview).update(f"[red]{message}[/red]")
        self._prepared = None
        self._warnings = []

    def recompute(self) -> None:
        """Re-model the current form and refresh the preview (never writes)."""
        self._refresh_output_name()
        job = self._job()
        if job is None:
            return
        service = self.app.service
        try:
            prepared = service.plan(job)
        except ArchiveError as exc:
            self._preview_error(exc.message)
            return
        warnings = []
        try:
            warnings = service.risks(prepared)
        except ArchiveError as exc:
            warnings = [
                type("W", (), {"message": exc.message, "level": RiskLevel.DANGER})()
            ]
        self._prepared = prepared
        self._warnings = warnings
        self.query_one("#plan", PlanPreview).show(
            prepared.summary,
            output=job.output,
            source="generated zeros",
            warnings=warnings,
            headline="plan",
        )

    def progress_tick(self) -> None:
        """Render live progress from the app's operation state."""
        op = self.app.state.operation
        bar = self.query_one("#progress", ProgressBar)
        text = self.query_one("#progress-text", Static)
        if not op.running and op.outcome is None:
            bar.update(progress=0)
            text.update("")
            return
        bar.update(progress=op.percent)
        seconds = op.outcome.seconds if op.outcome else 0.0
        if op.running:
            text.update(
                f"{op.percent:5.1f}%  {op.written:,} / {op.total:,} bytes  {op.label}"
            )
        elif op.outcome is not None and op.outcome.ok:
            text.update(f"[green]created[/green] {op.outcome.detail}")
# -- events ------------------------------------------------------------
    def on_select_changed(self, event: Select.Changed) -> None:
        if not self._ready:
            return
        if event.select.id == "size-preset" and event.value:
            self.query_one("#size", Input).value = str(event.value)
        self.recompute()

    def on_input_changed(self, event: Input.Changed) -> None:
        if not self._ready:
            return
        if event.input.id == "size-preset":
            return
        if event.input.id in ("size", "output"):
            self.recompute()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if not self._ready:
            return
        self.recompute()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "preview-btn":
            self.recompute()
        elif event.button.id == "create-btn":
            self.start_create()

    # -- run ---------------------------------------------------------------
    def start_create(self) -> None:
        """Validate, (optionally) confirm, then build in a worker thread."""
        from ..dialogs import ConfirmDialog

        self.recompute()
        prepared = getattr(self, "_prepared", None)
        if prepared is None:
            self.app._notify_error(
                "Cannot build the archive",
                "The current configuration is not valid.",
                hint="Fix the highlighted problem in the preview, then try again.",
            )
            return
        job = prepared.job
        confirm_needed = bool(getattr(self.app.config, "confirm_before_write", True))
        if job.output.exists() or confirm_needed:
            title = "Overwrite existing archive?" if job.output.exists() else "Write the archive?"
            detail = (
                f"{job.output} already exists and will be replaced."
                if job.output.exists()
                else f"This writes a real compression bomb to {job.output}."
            )
            self.app.push_screen(
                ConfirmDialog(
                    title,
                    str(job.output),
                    detail=detail,
                    confirm_label="Overwrite" if job.output.exists() else "Create",
                    danger=job.output.exists(),
                ),
                lambda choice: self._confirmed(prepared, choice),
            )
        else:
            self._run(prepared)

    def _confirmed(self, prepared, choice) -> None:
        if choice == "confirm":
            self._run(prepared)

    def _run(self, prepared) -> None:
        self.app.state.begin(
            "create", f"writing {prepared.job.output.name}", prepared.summary.target_bytes
        )
        self._run_job(prepared)

    @work(thread=True, exclusive=True)
    def _run_job(self, prepared) -> None:
        outcome = self.app.service.create(
            prepared, warnings=getattr(self, "_warnings", []), ux=None, show_progress=True
        )
        if outcome.ok:
            self.app.service.record(outcome.result, source="tui")
        self.app.call_from_thread(self._job_done, outcome)

    def _job_done(self, outcome) -> None:
        from ..dialogs import ErrorDialog

        self.app.state.finish(outcome)
        self.progress_tick()
        if outcome.ok:
            self.app.notify(f"created {outcome.detail}", title="archive ready")
        else:
            error = outcome.error
            self.app.push_screen(
                ErrorDialog(
                    "Unable to create the archive",
                    error.message if error else "unknown error",
                    hint=(error.hint if error else ""),
                    details=(f"kind: {error.kind}\npath: {error.path}" if error else ""),
                )
            )


__credit__ = "ZipBomb Lab - zipbomb_lab.tui.screens.create - made by Xv @XvRendering https://github.com/MamadXV"
