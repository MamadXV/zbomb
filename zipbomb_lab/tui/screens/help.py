# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Help screen: commands, keybindings and examples (searchable)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Input, Static

from ..keys import KEYMAP
from .base import LabScreen

__all__ = ["HelpScreen"]


class HelpScreen(LabScreen):
    """A scrollable, filterable reference for commands and keys."""

    key_context = "home"
    scroll_body = True

    def __init__(self) -> None:
        super().__init__()
        self.commands_text: str = ""

    def compose_body(self) -> ComposeResult:
        yield Static("Help", classes="title")
        yield Static(
            "type to filter commands   ·   Ctrl+K opens the command palette",
            classes="tagline",
        )
        yield Input(placeholder="filter commands", id="help-search")
        with Container(classes="card"):
            yield Static("Commands", classes="heading", id="help-commands-title")
            yield Static("", id="help-commands")
        with Container(classes="card"):
            yield Static("Keyboard", classes="heading")
            yield Static("", id="help-keys")

    def on_mount(self) -> None:
        super().on_mount()
        self.call_after_refresh(self._initialise)

    def _initialise(self) -> None:
        self._redraw("")
        self.query_one("#help-search", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        self._redraw(event.value)

    def _redraw(self, query: str) -> None:
        registry = self.app.registry
        commands = registry.match_names(query) if query else registry.all()
        if not commands:
            body = "[dim]no matching commands[/dim]"
        else:
            lines = []
            for command in commands:
                alias = f"  [dim]({', '.join(command.aliases)})[/dim]" if command.aliases else ""
                lines.append(
                    f"  [b][#FF6B00]{command.name}[/][/b]{alias}  {command.summary}"
                )
                if command.examples:
                    lines.append(f"      [dim]e.g. {command.examples[0]}[/dim]")
            body = "\n".join(lines)
        self.commands_text = body
        self.query_one("#help-commands", Static).update(body)
        shown = f"Commands  [dim]{len(commands)} shown[/dim]" if query else "Commands"
        self.query_one("#help-commands-title", Static).update(shown)

        keys = [f"  [b][#FF6B00]{key:<16}[/][/b] {label}" for key, label in KEYMAP]
        self.query_one("#help-keys", Static).update("\n".join(keys))


__credit__ = "ZipBomb Lab - zipbomb_lab.tui.screens.help - made by Xv @XvRendering https://github.com/MamadXV"
