# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Zip bomb lab: build, measure and detect compression bombs.

Real code lives in 3 consolidated modules (+ the CLI):

* ``zipbomb_lab.core``   - sizes, methods, policy, config (foundations)
* ``zipbomb_lab.engine`` - craft, make, detect, recipes (bomb engine)
* ``zipbomb_lab.ui``     - theme, branding, ux (presentation)
* ``zipbomb_lab.cli``    - commands + interactive panel (panel folded in)
"""

from __future__ import annotations

__version__ = "2.3.1"

# Import consolidated homes first so old-path aliases register in sys.modules.
from . import core as _core  # noqa: E402,F401
from . import engine as _engine  # noqa: E402,F401
from . import ui as _ui  # noqa: E402,F401

from .ui import AUTHOR, GITHUB, TELEGRAM, WATERMARK as BRAND_WATERMARK  # noqa: E402

__all__ = [
    "__version__",
    "AUTHOR",
    "GITHUB",
    "TELEGRAM",
    "BRAND_WATERMARK",
    "METHODS",
    "RECIPES",
    "NAME_STYLES",
    "MAX_CREATE_BYTES",
    "ACK_PHRASE",
    "create_archive",
    "verify_archive",
    "scan_archive",
    "estimate",
    "plan_recipe",
    "build_recipe",
]

from .core import ACK_PHRASE, MAX_CREATE_BYTES, METHODS, estimate
from .engine import NAME_STYLES, RECIPES, build_bomb as build_recipe
from .engine import create_archive, plan as plan_recipe, scan_archive, verify_archive


__credit__ = "ZipBomb Lab - zipbomb_lab - made by Xv @XvRendering https://github.com/MamadXV"
