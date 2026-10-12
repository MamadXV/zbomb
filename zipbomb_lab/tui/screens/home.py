# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Home screen: the application's front door.

Three grouped sections with divider rules, digit shortcuts surfaced as orange
chips, gray dimmed tips under white labels, and a detail card on the right
that explains whatever is currently highlighted.
"""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from ..keys import HOME_BINDINGS
from .base import LabScreen

__all__ = ["HomeScreen", "HOME_ORDER", "HOME_SECTIONS", "SHORTCUTS"]

#: Menu sections in display order: ``(header label, action ids)``.
HOME_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("build", ("create", "estimate")),
    ("scan & measure", ("inspect", "methods", "recipes")),
    ("app", ("settings", "help", "about")),
)

#: Flat action order, derived from the sections (kept for tests and callers
#: that only care about the ids).
HOME_ORDER: tuple[str, ...] = tuple(
    name for _, names in HOME_SECTIONS for name in names
)

#: Keyboard shortcut per action, derived from the real bindings so a chip can
#: never drift from what the keyboard actually does.
SHORTCUTS: dict[str, str] = {
    binding.action.removeprefix("open_"): binding.key
    for binding in HOME_BINDINGS
}


def shorten(text: str, width: int) -> str:
    """Trim *text* to *width* characters, on a word boundary, with an ellipsis."""
    if width <= 0 or len(text) <= width:
        return text
    cut = text[: max(width - 1, 1)].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "\u2026"


class HomeScreen(LabScreen):
    """The default screen."""

    key_context = "home"
    BINDINGS = HOME_BINDINGS

    def compose_body(self) -> ComposeResult:
        yield Static("Zip Bomb Lab", classes="title")
        yield Static(
            "build, measure and detect compression bombs - for isolated lab use",
            classes="tagline",
        )
        yield Static("", classes="path", id="home-dir")
        yield Static("", classes="tagline", id="home-recent")
        with Horizontal(classes="split"):
            yield OptionList(id="actions")
            with Container(classes="card", id="home-detail"):
                yield Static("Zip Bomb Lab", classes="heading", id="detail-title")
                yield Static("", id="detail-body")

    def on_mount(self) -> None:
        super().on_mount()
        self.call_after_refresh(self._initialise)

    def _initialise(self) -> None:
        self.populate()
        self.query_one("#actions", OptionList).focus()

    def populate(self) -> None:
        """(Re)build the sectioned action list from the registry."""
        listing = self.query_one("#actions", OptionList)
        listing.clear_options()
        tip_width = self._tip_width()
        first_index: int | None = None
        for position, (header, names) in enumerate(HOME_SECTIONS):
            if position:
                listing.add_option(None)  # divider rule between sections
            listing.add_option(Option(header.upper(), disabled=True))
            for name in names:
                command = self.app.registry.get(name)
                if command is None:
                    continue
                if first_index is None:
                    first_index = listing.option_count
                listing.add_option(Option(self._row(name, command, tip_width), id=name))
        directory = self.app.state.navigation.directory
        self.query_one("#home-dir", Static).update(
            f"[dim]working directory[/dim]  {directory}"
        )
        recent = self.app.state.navigation.recent_actions
        self.query_one("#home-recent", Static).update(
            "[dim]recent[/dim]  " + ("  ".join(recent) if recent else "nothing yet")
        )
        if first_index is not None:
            listing.highlighted = first_index
            self._show_detail(listing.options[first_index].id)

    # -- row painting ------------------------------------------------------
    def _row(self, name: str, command, tip_width: int) -> Text:
        """One menu line: orange key chip, white label, gray dimmed tip."""
        label = name[:1].upper() + name[1:]
        chip = SHORTCUTS.get(name, "")
        parts: list[tuple[str, str] | str] = [
            (f" {chip} " if chip else "   ", "bold black on #FF6B00"),
            " ",
            (f"{label:<10}", "bold"),
            (shorten(command.summary, tip_width), "dim"),
        ]
        if command.dangerous:
            parts.append(("  !", "bold"))
        return Text.assemble(*parts)

    def _tip_width(self) -> int:
        """Characters left for the gray tip inside the menu column."""
        narrow = self.has_class("-narrow")
        body = max(self.size.width - (2 if narrow else 4), 40)  # #body padding
        menu = body if narrow else body - 39  # detail card 38 + gap 1
        # round border, option padding, chip + gap + label column, danger mark
        return max(18, menu - 2 - 2 - 15 - 3)

    # -- detail card -------------------------------------------------------
    def _show_detail(self, name: str | None) -> None:
        title = self.query_one("#detail-title", Static)
        body = self.query_one("#detail-body", Static)
        command = self.app.registry.get(name) if name else None
        if command is None:
            title.update("Zip Bomb Lab")
            body.update(
                "[dim]arrow keys move, Enter opens, digits jump straight to an "
                "action, Ctrl+K opens the palette[/dim]"
            )
            return
        label = name[:1].upper() + name[1:] if name else command.label.title()
        badge = "   [#CC5500 b]writes data[/]" if command.dangerous else ""
        title.update(f"{label}{badge}")
        lines = [command.summary, ""]
        shortcut = SHORTCUTS.get(name or "", "")
        if shortcut:
            lines.append(f"[#FF6B00 b]shortcut[/]  [{shortcut}] on the keyboard")
        if command.usage:
            lines.append(f"[#FF6B00 b]usage[/]    [dim]{command.usage}[/]")
        if command.examples:
            lines.append(f"[#FF6B00 b]example[/]  [dim]{command.examples[0]}[/]")
        if command.keys:
            lines.append(f"[#FF6B00 b]also keys[/]  [dim]{', '.join(command.keys)}[/]")
        body.update("\n".join(lines))

    # -- chrome ------------------------------------------------------------
    def refresh_chrome(self) -> None:
        super().refresh_chrome()
        try:
            self.query_one("#home-dir", Static).update(
                f"[dim]working directory[/dim]  {self.app.state.navigation.directory}"
            )
        except Exception:  # pragma: no cover - mid-mount
            pass

    def reload_view(self) -> None:
        self.populate()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        self._show_detail(event.option.id)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            self.app.open_command(str(event.option.id))

    # -- number shortcuts (actions resolve on the owning screen) -----------
    def action_open_create(self) -> None:
        self.app.open_command("create")

    def action_open_estimate(self) -> None:
        self.app.open_command("estimate")

    def action_open_inspect(self) -> None:
        self.app.open_command("inspect")

    def action_open_methods(self) -> None:
        self.app.open_command("methods")

    def action_open_recipes(self) -> None:
        self.app.open_command("recipes")

    def action_open_settings(self) -> None:
        self.app.open_command("settings")

    def action_open_help(self) -> None:
        self.app.open_command("help")

    def action_open_demo(self) -> None:
        self.app.open_command("demo")

    def action_open_about(self) -> None:
        self.app.open_command("about")

    def set_directory(self, directory: Path) -> None:
        self.app.state.navigation.directory = Path(directory)
        self.refresh_chrome()


__credit__ = "ZipBomb Lab - zipbomb_lab.tui.screens.home - made by Xv @XvRendering https://github.com/MamadXV"
