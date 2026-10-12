# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""TUI screens."""

from __future__ import annotations

from .base import LabScreen, ScrollScreen
from .demo import DemoScreen
from .estimate import EstimateScreen
from .help import HelpScreen
from .home import HomeScreen
from .info import InfoScreen
from .inspect import InspectScreen
from .methods import MethodsScreen
from .recipes import RecipesScreen
from .settings import SettingsScreen

__all__ = [
    "LabScreen",
    "ScrollScreen",
    "HomeScreen",
    "CreateScreen",
    "EstimateScreen",
    "InspectScreen",
    "RecipesScreen",
    "MethodsScreen",
    "SettingsScreen",
    "HelpScreen",
    "InfoScreen",
    "DemoScreen",
]


def __getattr__(name: str):
    """Lazily expose the heavy CreateScreen without importing it eagerly."""
    if name == "CreateScreen":
        from .create import CreateScreen

        return CreateScreen
    if name == "AboutScreen":
        from .about import AboutScreen

        return AboutScreen
    raise AttributeError(name)


__credit__ = "ZipBomb Lab - zipbomb_lab.tui.screens - made by Xv @XvRendering https://github.com/MamadXV"
