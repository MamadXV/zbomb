# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Inspect screen: choose a real archive and scan it (never extracts)."""

from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, Checkbox, Input, Static

from ..widgets.filepicker import FilePicker
from .base import LabScreen

__all__ = ["InspectScreen"]


class InspectScreen(LabScreen):
    """Pick an archive with the built-in browser, then scan it."""

    key_context = "form"
    scroll_body = True
    BINDINGS = [
        Binding("backspace", "parent_dir", "parent", show=False),
        Binding("space", "toggle_mark", "mark", show=False),
        Binding("slash", "focus_filter", "filter", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._path: Path | None = None
        self.verdict_text: str = ""

    def compose_body(self) -> ComposeResult:
        yield Static("Inspect an archive", classes="title")
        yield Static(
            "metadata-first scan: nothing is ever extracted", classes="tagline"
        )
        yield FilePicker(
            start=self.app.state.navigation.directory,
            mode="file",
            suffixes=(".zip",),
            id="picker",
        )
        with Horizontal(classes="field-row"):
            yield Static("ratio / total", classes="field-label")
            yield Input(value="", placeholder="ratio threshold (blank = default)", id="max-ratio")
        with Horizontal(classes="field-row"):
            yield Static("", classes="field-label")
            yield Input(value="", placeholder="total size threshold (e.g. 100GB)", id="max-total")
        yield Checkbox("probe entries for nested archives (bounded)", value=True, id="deep")
        with Horizontal(classes="buttons"):
            yield Button("Scan archive", variant="primary", id="scan-btn")
        yield Static("", id="verdict")

    def on_mount(self) -> None:
        super().on_mount()
        self.call_after_refresh(self._initialise)

    def _initialise(self) -> None:
        self.query_one("#picker", FilePicker).focus()

    def reload_view(self) -> None:
        self.query_one("#picker", FilePicker).reload()

    # -- picker actions ----------------------------------------------------
    def action_parent_dir(self) -> None:
        self.query_one("#picker", FilePicker).action_parent()

    def action_toggle_mark(self) -> None:
        self.query_one("#picker", FilePicker).action_toggle_mark()

    def action_focus_filter(self) -> None:
        self.query_one("#picker Input", Input).focus()

    def on_file_picker_selected(self, event: FilePicker.Selected) -> None:
        self._path = event.path
        self.query_one("#verdict", Static).update(f"[b]selected[/b] {event.path}")

    # -- scan --------------------------------------------------------------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "scan-btn":
            self.start_scan()

    def start_scan(self) -> None:
        picker = self.query_one("#picker", FilePicker)
        paths = picker.selected()
        if not paths and self._path is not None:
            paths = [self._path]
        if not paths:
            self.app._notify_error(
                "Nothing to scan",
                "Select an archive first.",
                hint="Use Enter to open a folder and Space to mark a file.",
            )
            return
        target = paths[0]
        if not target.is_file():
            self.app._notify_error("Not a file", f"{target} is not a file.")
            return
        self.query_one("#verdict", Static).update(f"[dim]scanning {target}...[/dim]")
        self._scan_job(
            str(target),
            bool(self.query_one("#deep", Checkbox).value),
            self.query_one("#max-ratio", Input).value.strip(),
            self.query_one("#max-total", Input).value.strip(),
        )

    @work(thread=True, exclusive=True)
    def _scan_job(self, path: str, deep: bool, max_ratio: str, max_total: str) -> None:
        from ...core import parse_size

        kwargs = {"deep": deep}
        try:
            if max_ratio:
                kwargs["max_ratio"] = float(max_ratio)
            if max_total:
                kwargs["max_total"] = parse_size(max_total)
        except Exception:
            pass
        outcome = self.app.service.scan(path, **kwargs)
        self.app.call_from_thread(self._show_verdict, outcome)

    def _show_verdict(self, outcome) -> None:
        target = self.query_one("#verdict", Static)
        if outcome.error:
            self.verdict_text = outcome.error
        else:
            report = outcome.report
            verdict = "SUSPICIOUS" if outcome.suspicious else "clean"
            colour = "red" if outcome.suspicious else "green"
            lines = [
                f"[b {colour}]{verdict}[/]  {report.get('path')}",
                f"entries {report.get('entry_count', 0):,}   "
                f"ratio {report.get('max_ratio_human', 'n/a')}   "
                f"zip64 {'yes' if report.get('zip64') else 'no'}",
            ]
            for reason in report.get("reasons", []):
                lines.append(f"[yellow]! {reason}[/yellow]")
            for note in report.get("notes", [])[:5]:
                lines.append(f"[dim]{note}[/dim]")
            self.verdict_text = "\n".join(lines)
        target.update(self.verdict_text)


__credit__ = "ZipBomb Lab - zipbomb_lab.tui.screens.inspect - made by Xv @XvRendering https://github.com/MamadXV"
