# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Allow ``python -m zipbomb_lab ...``."""

from __future__ import annotations

import sys

from .cli import main


__credit__ = "ZipBomb Lab - zipbomb_lab.__main__ - made by Xv @XvRendering https://github.com/MamadXV"
if __name__ == "__main__":
    sys.exit(main())
