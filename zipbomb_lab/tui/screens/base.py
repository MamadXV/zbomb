# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Shared screen scaffold: persistent chrome around a swappable body.

Every screen inherits this, so the header, status bar and key bar are always
present and always fed from the same :class:`~zipbomb_lab.tui.state.AppState`.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.screen import Screen

from ..widgets.chrome import AppHeader, KeyBar, StatusBar

__all__ = ["LabScreen", "ScrollScreen"]


class LabScreen(Screen):
    """A screen with the lab chrome and a body the subclass fills in."""

    #: Which hint set the key bar shows.
    key_context: str = "home"
    #: Set True to wrap the body in a vertical scroll container.
    scroll_body: bool = False

    def compose(self) -> ComposeResult:
        yield AppHeader(id="header")
        if self.scroll_body:
            with VerticalScroll(id="body"):
                yield from self.compose_body()
        else:
            with Container(id="body"):
                yield from self.compose_body()
        yield StatusBar(id="status")
        yield KeyBar(id="keybar")

    def compose_body(self):
        """Subclasses yield their widgets here."""
        return iter(())

    def on_mount(self) -> None:
        self._sync_narrow()
        self.refresh_chrome()

    def _sync_narrow(self) -> None:
        """Track the terminal width so responsive CSS can kick in."""
        from ..app import NARROW_WIDTH

        try:
            self.set_class(self.app.size.width < NARROW_WIDTH, "-narrow")
        except Exception:  # pragma: no cover - size not settled yet
            pass

    def refresh_chrome(self) -> None:
        """Push current state into the header, status bar and key bar."""
        try:
            app = self.app
            self.query_one("#header", AppHeader).set_directory(app.state.navigation.directory)
            self.query_one("#status", StatusBar).set_segments(app.status_segments())
            self.query_one("#keybar", KeyBar).set_context(self.key_context)
        except Exception:  # pragma: no cover - chrome not yet mounted
            pass

    @property
    def lab_app(self):
        return self.app


class ScrollScreen(LabScreen):
    """Convenience base for long, text-heavy screens."""

    scroll_body = True


__credit__ = "ZipBomb Lab - zipbomb_lab.tui.screens.base - made by Xv @XvRendering https://github.com/MamadXV"
