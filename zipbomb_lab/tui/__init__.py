# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Interactive terminal UI (Textual).

Importing this package is cheap: the Textual application and its screens are
imported lazily, so ``import zipbomb_lab`` never pays for the TUI unless it is
actually launched.
"""

from __future__ import annotations

__all__ = ["run_tui", "LabApp", "can_use_tui"]


def __getattr__(name: str):
    if name in ("run_tui", "LabApp", "can_use_tui"):
        from . import app as _app

        return getattr(_app, name)
    raise AttributeError(name)


__credit__ = "ZipBomb Lab - zipbomb_lab.tui - made by Xv @XvRendering https://github.com/MamadXV"
