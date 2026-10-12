# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Settings screen: edit and persist the remembered defaults."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Checkbox, Input, Select, Static

from ..dialogs import ErrorDialog
from .base import LabScreen

__all__ = ["SettingsScreen"]

VERIFY_CHOICES = ["none", "sample", "full"]
PROGRESS_CHOICES = ["auto", "ansi", "plain", "log", "none"]


def level_options() -> list[tuple[str, int]]:
    """Descriptive level options with tooltips."""
    return [
        ("Level 0 - Fastest, no compression", 0),
        ("Level 1 - Very fast, minimal compression", 1),
        ("Level 2 - Fast, light compression", 2),
        ("Level 3 - Good speed/balance", 3),
        ("Level 4 - Balanced", 4),
        ("Level 5 - Good compression", 5),
        ("Level 6 - Better compression", 6),
        ("Level 7 - High compression (slow)", 7),
        ("Level 8 - Very high compression", 8),
        ("Level 9 - Maximum compression (slowest)", 9),
    ]


class SettingsScreen(LabScreen):
    """A real settings form backed by the on-disk configuration file."""

    key_context = "form"
    scroll_body = True

    def compose_body(self) -> ComposeResult:
        yield Static("Settings", classes="title")
        yield Static("", classes="tagline", id="settings-path")
        with Horizontal(classes="field-row"):
            yield Static("output directory", classes="field-label")
            yield Input(id="output_dir")
        with Horizontal(classes="field-row"):
            yield Static("default method", classes="field-label")
            yield Select(
                [(k, k) for k in ("stored", "deflate", "bzip2", "lzma")],
                value="deflate",
                allow_blank=False,
                id="method",
            )
        with Horizontal(classes="field-row"):
            yield Static("default level", classes="field-label")
            yield Select(level_options(), value=9, allow_blank=False, id="level")
        with Horizontal(classes="field-row"):
            yield Static("default size", classes="field-label")
            yield Input(id="size")
        with Horizontal(classes="field-row"):
            yield Static("write buffer", classes="field-label")
            yield Input(id="chunk")
        with Horizontal(classes="field-row"):
            yield Static("split size", classes="field-label")
            yield Input(id="split")
        with Horizontal(classes="field-row"):
            yield Static("verify after write", classes="field-label")
            yield Select(
                [(v, v) for v in VERIFY_CHOICES], value="sample", allow_blank=False, id="verify"
            )
        with Horizontal(classes="field-row"):
            yield Static("output mode", classes="field-label")
            yield Select(
                [(v, v) for v in PROGRESS_CHOICES], value="auto", allow_blank=False, id="progress"
            )
        yield Checkbox("ask before writing an archive", value=True, id="confirm_before_write")
        yield Checkbox("compact layout", value=False, id="compact")
        with Horizontal(classes="buttons"):
            yield Button("Save", variant="primary", id="save-btn")

    def on_mount(self) -> None:
        super().on_mount()
        self.call_after_refresh(self._initialise)

    def _initialise(self) -> None:
        config = self.app.config
        self.query_one("#settings-path", Static).update(f"[dim]{self.app.settings.path}[/dim]")
        if config is not None:
            self.query_one("#output_dir", Input).value = str(config.output_dir)
            self.query_one("#method", Select).value = config.method
            self.query_one("#level", Select).value = int(config.level)
            self.query_one("#size", Input).value = str(config.size)
            self.query_one("#chunk", Input).value = str(config.chunk)
            self.query_one("#split", Input).value = str(config.split)
            self.query_one("#verify", Select).value = config.verify
            self.query_one("#progress", Select).value = config.progress
            self.query_one("#confirm_before_write", Checkbox).value = bool(
                config.confirm_before_write
            )
            self.query_one("#compact", Checkbox).value = bool(config.compact)
        self.query_one("#output_dir", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self.save()

    def save(self) -> None:
        config = self.app.config
        if config is None:
            return
        config.output_dir = self.query_one("#output_dir", Input).value.strip() or "."
        config.method = str(self.query_one("#method", Select).value or "deflate")
        config.level = int(self.query_one("#level", Select).value)
        config.size = self.query_one("#size", Input).value.strip() or config.size
        config.chunk = self.query_one("#chunk", Input).value.strip() or config.chunk
        config.split = self.query_one("#split", Input).value.strip()
        config.verify = str(self.query_one("#verify", Select).value or config.verify)
        config.progress = str(self.query_one("#progress", Select).value or config.progress)
        config.confirm_before_write = bool(
            self.query_one("#confirm_before_write", Checkbox).value
        )
        config.compact = bool(self.query_one("#compact", Checkbox).value)
        try:
            saved = self.app.settings.save(config)
        except OSError as exc:
            self.app.push_screen(ErrorDialog("Could not save settings", str(exc)))
            return
        self.query_one("#settings-path", Static).update(f"[green]saved[/green] [dim]{saved}[/dim]")
        self.app.refresh_chrome()


__credit__ = "ZipBomb Lab - zipbomb_lab.tui.screens.settings - made by Xv @XvRendering https://github.com/MamadXV"
