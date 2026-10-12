# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""The keyboard model for the TUI, in one place.

Global bindings live on the app; each screen may add contextual ones. Keeping
the map here means the help screen documents the *actual* keys, never a stale
copy.
"""

from __future__ import annotations

from textual.binding import Binding

__all__ = ["GLOBAL_BINDINGS", "HOME_BINDINGS", "KEYMAP", "keybar_hints"]

#: App-wide bindings. ``priority`` keeps the palette and quit working even
#: while an input widget has focus.
GLOBAL_BINDINGS = [
    Binding("ctrl+k", "command_palette", "palette", priority=True, show=True),
    Binding("f1,question_mark", "help", "help", show=True),
    Binding("escape", "back", "back", priority=True, show=True),
    Binding("q,ctrl+c", "quit_app", "quit", priority=True, show=True),
    Binding("ctrl+r", "refresh", "refresh", show=False),
]

#: Home-screen number shortcuts. Each maps to an explicit action method so the
#: binding string stays unambiguous.
HOME_BINDINGS = [
    Binding("1", "open_create", "create", show=False, priority=True),
    Binding("2", "open_estimate", "estimate", show=False, priority=True),
    Binding("3", "open_inspect", "inspect", show=False, priority=True),
    Binding("4", "open_methods", "methods", show=False, priority=True),
    Binding("5", "open_recipes", "recipes", show=False, priority=True),
    Binding("6", "open_settings", "settings", show=False, priority=True),
    Binding("8", "open_about", "about", show=False, priority=True),
    Binding("7", "open_help", "help", show=False, priority=True),
    Binding("d", "open_demo", "demo", show=False, priority=True),
]

#: Documented keymap for the help screen (key -> description).
KEYMAP: tuple[tuple[str, str], ...] = (
    ("↑ / ↓", "move the selection"),
    ("← / →", "switch tabs and panes"),
    ("Enter", "open the selected item / submit a form"),
    ("Esc", "go back / close a dialog"),
    ("Tab / Shift+Tab", "next / previous control"),
    ("Space", "toggle a checkbox or mark a file"),
    ("Backspace", "parent directory in the file browser"),
    ("/", "search (file browser, help)"),
    ("Ctrl+K", "open the command palette"),
    ("1…8", "jump straight to a home action"),
    ("F1 / ?", "this help"),
    ("Ctrl+R", "refresh the current view"),
    ("q / Ctrl+C", "quit the application"),
)


def keybar_hints(context: str = "home") -> list[tuple[str, str]]:
    """Short hint pairs for the bottom bar, per context."""
    common = [("↑↓", "navigate"), ("Enter", "select"), ("Ctrl+K", "palette")]
    if context == "home":
        return [*common, ("1-8", "jump"), ("Esc", "back"), ("?", "help"), ("q", "quit")]
    if context == "form":
        return [("Tab", "next"), ("Enter", "apply"), ("Esc", "back"), ("Ctrl+K", "palette")]
    if context == "progress":
        return [("Ctrl+C", "quit"), ("Esc", "back")]
    return [*common, ("Esc", "back"), ("q", "quit")]


__credit__ = "ZipBomb Lab - zipbomb_lab.tui.keys - made by Xv @XvRendering https://github.com/MamadXV"
