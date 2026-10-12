# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""About screen: project credits and a short description."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static

from .base import LabScreen

__all__ = ["AboutScreen"]

#: Capability bullets, one line each.
FEATURES = (
    "Flat zero-fill bombs - any size the safety policy allows",
    "Structural recipes: layered, cascade, wide, traversal, onopen, stack, overlap",
    "Live calibration of every codec on the current interpreter",
    "Deep scanning for nested and ambiguous archives",
)


class AboutScreen(LabScreen):
    """Project credits and a short description."""

    key_context = "home"
    scroll_body = True

    def compose_body(self) -> ComposeResult:
        from ... import __version__
        from ...ui import AUTHOR, GITHUB, TAGLINE, TELEGRAM, TOOL

        yield Static("About", classes="title")
        yield Static(f"{TAGLINE} - for isolated lab use", classes="tagline")

        with Container(classes="card -hero"):
            yield Static(f"{TOOL}  [dim]v{__version__}[/dim]", classes="heading")

        with Container(classes="card"):
            yield Static("Credits", classes="heading")
            yield Static(f"[b]Author[/b]    {AUTHOR}")
            yield Static(f"[b]Telegram[/b]  {TELEGRAM}")
            yield Static(f"[b]GitHub[/b]    {GITHUB}")

        with Container(classes="card"):
            yield Static("What it does", classes="heading")
            for feature in FEATURES:
                yield Static(f"•  {feature}")

        with Container(classes="card -warn"):
            yield Static("Safety", classes="heading")
            yield Static(
                "All artifacts are created in an isolated directory you control.\n"
                "[b]Never extract a bomb on a system you care about.[/b]"
            )


__credit__ = "ZipBomb Lab - zipbomb_lab.tui.screens.about - made by Xv @XvRendering https://github.com/MamadXV"
