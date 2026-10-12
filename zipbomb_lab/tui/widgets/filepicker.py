# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""A real terminal file browser.

Supports directory navigation, parent directory, hidden-file toggling,
multi-selection and incremental filtering — and it never returns a raw
"enter a path" prompt. Paths (including spaces, Unicode and symlinks) are
handled by :mod:`pathlib` throughout.
"""

from __future__ import annotations

from pathlib import Path

from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

__all__ = ["FilePicker"]


class FilePicker(Widget):
    """An inline, keyboard-driven file/directory chooser."""

    class Selected(Message):
        """A file (or directory, in ``dir`` mode) was confirmed."""

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    class Highlighted(Message):
        """The highlighted entry changed (for live previews)."""

        def __init__(self, path: Path | None) -> None:
            super().__init__()
            self.path = path

    cwd: reactive[Path] = reactive(Path.cwd)

    def __init__(
        self,
        *,
        start: Path | None = None,
        mode: str = "file",
        suffixes: tuple[str, ...] | None = None,
        multi: bool = False,
        include_hidden: bool = False,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.cwd = Path(start or Path.cwd()).expanduser()
        self.mode = mode if mode in ("file", "dir") else "file"
        self.suffixes = tuple(s.lower() for s in suffixes) if suffixes else None
        self.multi = multi
        self.include_hidden = include_hidden
        self._entries: list[Path] = []
        self._marked: set[Path] = set()
        self._filter = ""

    def compose(self):
        yield Input(placeholder="filter (type to narrow the list)", id="filter")
        yield OptionList(id="entries")
        yield Static("", id="preview")

    def on_mount(self) -> None:
        self.reload()

    # -- listing -----------------------------------------------------------
    def reload(self) -> None:
        """Re-read the current directory and rebuild the option list."""
        options = self.query_one("#entries", OptionList)
        options.clear_options()
        self._entries = []
        try:
            children = sorted(
                self.cwd.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except (OSError, PermissionError):
            options.add_option(Option("[unreadable directory]", disabled=True))
            return

        if not self.include_hidden:
            children = [c for c in children if not c.name.startswith(".")]
        if self._filter:
            needle = self._filter.lower()
            children = [c for c in children if needle in c.name.lower()]

        accepted: list[Path] = []
        for child in children:
            if child.is_dir():
                accepted.append(child)
            elif self.mode == "file":
                if self.suffixes is None or child.suffix.lower() in self.suffixes:
                    accepted.append(child)

        if not accepted:
            options.add_option(Option("[nothing here]", disabled=True))
        else:
            for index, path in enumerate(accepted):
                self._entries.append(path)
                marker = "✓ " if path in self._marked else ("▸ " if path.is_dir() else "  ")
                suffix = "/" if path.is_dir() else ""
                options.add_option(Option(f"{marker}{path.name}{suffix}", id=str(index)))

        self._preview(self._entries[0] if self._entries else None)

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        index = self._index_of(event.option)
        path = self._entries[index] if index is not None else None
        self._preview(path)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        index = self._index_of(event.option)
        if index is None:
            return
        path = self._entries[index]
        if path.is_dir():
            self.cwd = path
            self._filter = ""
            self.query_one("#filter", Input).value = ""
            self.reload()
            self.query_one("#entries", OptionList).focus()
            return
        self.post_message(self.Selected(path))

    def _index_of(self, option) -> int | None:
        try:
            return int(option.id) if option.id is not None else None
        except (TypeError, ValueError):  # pragma: no cover - defensive
            return None
# -- interaction -------------------------------------------------------
    def on_input_changed(self, event: Input.Changed) -> None:
        self._filter = event.value
        self.reload()

    def action_parent(self) -> None:
        """Move to the parent directory (bound to Backspace by the screen)."""
        parent = self.cwd.parent
        if parent != self.cwd:
            self.cwd = parent
            self.reload()

    def action_toggle_hidden(self) -> None:
        self.include_hidden = not self.include_hidden
        self.reload()

    def action_toggle_mark(self) -> None:
        """Mark/unmark the highlighted entry (multi-select mode)."""
        if not self.multi:
            return
        options = self.query_one("#entries", OptionList)
        index = options.highlighted
        if index is None or index >= len(self._entries):
            return
        path = self._entries[index]
        if path in self._marked:
            self._marked.discard(path)
        else:
            self._marked.add(path)
        self.reload()
        options.highlighted = index

    def action_clear_marks(self) -> None:
        self._marked.clear()
        self.reload()

    # -- accessors ---------------------------------------------------------
    def current_directory(self) -> Path:
        return self.cwd

    def marked_paths(self) -> list[Path]:
        return sorted(self._marked)

    def highlighted_path(self) -> Path | None:
        options = self.query_one("#entries", OptionList)
        index = options.highlighted
        if index is None or index >= len(self._entries):
            return None
        return self._entries[index]

    def selected(self) -> list[Path]:
        """The paths a caller should act on: marks first, else the highlight."""
        if self._marked:
            return sorted(self._marked)
        path = self.highlighted_path()
        return [path] if path else []

    def _preview(self, path: Path | None) -> None:
        preview = self.query_one("#preview", Static)
        if path is None:
            preview.update(f"[dim]{self.cwd}[/dim]")
            return
        try:
            if path.is_dir():
                kind, size = "directory", ""
            else:
                kind, size = "file", f"  {path.stat().st_size:,} bytes"
        except OSError:
            kind, size = "unreadable", ""
        preview.update(f"[dim]{path}[/dim]\n{kind}{size}")
        self.post_message(self.Highlighted(path))


__credit__ = "ZipBomb Lab - zipbomb_lab.tui.widgets.filepicker - made by Xv @XvRendering https://github.com/MamadXV"
