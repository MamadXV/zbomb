# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Info screen: a simple scrollable text panel (policy, audit, version)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Static

from .base import LabScreen

__all__ = ["InfoScreen"]


class InfoScreen(LabScreen):
    """Show a title and a block of pre-rendered text."""

    key_context = "home"
    scroll_body = True

    def __init__(self, title: str, body: str = "") -> None:
        super().__init__()
        self.title_text = title
        self.body_text = body

    def compose_body(self) -> ComposeResult:
        yield Static(self.title_text, classes="title")
        yield Static(self.body_text or "(nothing to show)", id="info-body")


__credit__ = "ZipBomb Lab - zipbomb_lab.tui.screens.info - made by Xv @XvRendering https://github.com/MamadXV"
