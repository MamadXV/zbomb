# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Platform-specific facts the lab needs (bitness, disk space, OS quirks).

Thin, explicit wrappers over ``core.policy`` so the numbers stay identical to
the ones the safety layer already reports, while the TUI and services depend
on named helpers rather than re-deriving them.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

__all__ = ["is_windows", "python_version", "bitness", "is_32bit", "disk_free"]


def is_windows() -> bool:
    return os.name == "nt"


def python_version() -> str:
    return sys.version.split()[0]


def is_32bit() -> bool:
    from ..core import is_32bit as _is_32bit

    return _is_32bit()


def bitness() -> int:
    return 32 if is_32bit() else 64


def disk_free(path: Path | str) -> int | None:
    """Free bytes on the volume holding *path*, or ``None`` when unknown."""
    from ..core import disk_free as _disk_free

    return _disk_free(Path(path))


__credit__ = "ZipBomb Lab - zipbomb_lab.infrastructure.platform - made by Xv @XvRendering https://github.com/MamadXV"
