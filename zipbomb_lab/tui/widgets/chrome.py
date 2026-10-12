# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Always-on shell chrome: the header, the status bar and the key bar."""

from __future__ import annotations

from pathlib import Path

from textual.reactive import reactive
from textual.widgets import Static

from ..keys import keybar_hints
from ... import __version__

__all__ = ["AppHeader", "StatusBar", "KeyBar"]


class AppHeader(Static):
    """Top bar: product identity on the left, the working directory right."""

    directory: reactive[str] = reactive("")

    def __init__(self, directory: Path | str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.directory = str(directory or Path.cwd())

    def render(self) -> str:
        left = f" ZIP BOMB LAB v{__version__}"
        right = f"{self.directory} "
        width = max(self.size.width, 20)
        gap = max(width - len(left) - len(right) - 2, 1)
        return f"{left}{' ' * gap}{right}"

    def set_directory(self, directory: Path | str) -> None:
        self.directory = str(directory)


class StatusBar(Static):
    """Bottom status: mode, directory, file count and the latest message."""

    segments: reactive[tuple[tuple[str, str], ...]] = reactive(())

    def set_segments(self, segments) -> None:
        self.segments = tuple((str(key), str(value)) for key, value in segments)

    def render(self) -> str:
        if not self.segments:
            return "ready"
        return "   ".join(f"{key} {value}" for key, value in self.segments)


class KeyBar(Static):
    """A dim, context-aware row of keyboard hints."""

    context: reactive[str] = reactive("home")

    def set_context(self, context: str) -> None:
        self.context = context

    def render(self) -> str:
        hints = keybar_hints(self.context)
        return "  ".join(f"{key} {label}" for key, label in hints)


__credit__ = "ZipBomb Lab - zipbomb_lab.tui.widgets.chrome - made by Xv @XvRendering https://github.com/MamadXV"
