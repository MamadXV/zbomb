# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Demo screen: build a tiny archive and scan it back in one guided step."""

from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Input, ProgressBar, Select, Static

from ...core import parse_size
from ...domain.data import default_output_name, method_rows
from ...domain.models import ArchiveError, ArchiveJob, ArchiveOptions
from .base import LabScreen

__all__ = ["DemoScreen"]


class DemoScreen(LabScreen):
    """The safe, seconds-long end-to-end loop."""

    key_context = "form"
    scroll_body = True

    def compose_body(self) -> ComposeResult:
        methods = [(f"{m['key']} - {m['label']}", m["key"]) for m in method_rows()]
        yield Static("Guided demo", classes="title")
        yield Static(
            "build a small bomb, scan it back, see what a scanner sees", classes="tagline"
        )
        with Horizontal(classes="field-row"):
            yield Static("size", classes="field-label")
            yield Input(value="16MiB", id="size")
        with Horizontal(classes="field-row"):
            yield Static("method", classes="field-label")
            yield Select(methods, value="bzip2", allow_blank=False, id="method")
        with Horizontal(classes="buttons"):
            yield Button("Run demo", variant="primary", id="run-btn")
        yield ProgressBar(total=100, show_eta=False, id="progress")
        yield Static("", id="progress-text")
        yield Static("", id="result")

    def on_mount(self) -> None:
        super().on_mount()
        self.call_after_refresh(self._initialise)

    def _initialise(self) -> None:
        self.set_interval(0.15, self.progress_tick)

    def progress_tick(self) -> None:
        op = self.app.state.operation
        bar = self.query_one("#progress", ProgressBar)
        text = self.query_one("#progress-text", Static)
        bar.update(progress=op.percent)
        if op.running:
            text.update(f"{op.percent:5.1f}%  {op.written:,} / {op.total:,} bytes")
        elif op.outcome is not None and op.outcome.ok:
            text.update("[green]archive written[/green]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run-btn":
            self.start_demo()

    def start_demo(self) -> None:
        size_text = self.query_one("#size", Input).value.strip() or "16MiB"
        try:
            target = parse_size(size_text)
        except Exception as exc:
            self.app._notify_error("Bad size", str(exc))
            return
        method = str(self.query_one("#method", Select).value or "bzip2")
        directory = self.app.state.navigation.directory
        output = directory / default_output_name(size_text, method)
        job = ArchiveJob(
            output=output,
            target_bytes=target,
            options=ArchiveOptions(method=method, verify="sample", overwrite=True),
        )
        service = self.app.service
        try:
            prepared = service.plan(job)
            warnings = service.risks(prepared)
        except ArchiveError as exc:
            self.app._notify_error("Cannot model the demo", exc.message, hint=exc.hint)
            return
        self.app.state.begin("demo", f"building {output.name}", prepared.summary.target_bytes)
        self._run_demo(prepared, warnings)

    @work(thread=True, exclusive=True)
    def _run_demo(self, prepared, warnings) -> None:
        service = self.app.service
        outcome = service.create(prepared, warnings=warnings, ux=None, show_progress=True)
        scan = None
        if outcome.ok:
            service.record(outcome.result, source="tui-demo")
            scan = service.scan(prepared.job.output, deep=True)
        self.app.call_from_thread(self._demo_done, outcome, scan)

    def _demo_done(self, outcome, scan) -> None:
        self.app.state.finish(outcome)
        self.progress_tick()
        result = self.query_one("#result", Static)
        if not outcome.ok:
            error = outcome.error
            result.update(f"[red]{error.message if error else 'failed'}[/red]")
            return
        lines = [f"[green]created[/green] {outcome.detail}"]
        if scan is not None:
            verdict = "SUSPICIOUS" if scan.suspicious else "clean"
            colour = "red" if scan.suspicious else "green"
            lines.append(f"scan verdict: [b {colour}]{verdict}[/b]")
            for reason in scan.reasons:
                lines.append(f"[yellow]! {reason}[/yellow]")
        result.update("\n".join(lines))


__credit__ = "ZipBomb Lab - zipbomb_lab.tui.screens.demo - made by Xv @XvRendering https://github.com/MamadXV"
