# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Structured file logging that can never corrupt the interactive terminal.

The TUI owns the screen, so the lab never writes log records to stdout. Every
module asks :func:`get_logger` for a logger whose only handler appends to a
file (``ZIPBOMB_LAB_DEBUG_LOG`` overrides the location).

The file is opened *per record* and closed again immediately: a permanently
open handle would keep the file locked on Windows, which makes temporary
directories (and the audit log) undeletable while the process lives.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

__all__ = ["DEBUG_ENV", "LOG_ENV", "log_path", "get_logger", "debug_enabled"]

DEBUG_ENV = "ZIPBOMB_LAB_DEBUG"
LOG_ENV = "ZIPBOMB_LAB_DEBUG_LOG"

_CONFIGURED = False


def log_path() -> Path:
    """Where debug records are appended."""
    override = os.environ.get(LOG_ENV)
    if override:
        return Path(override)
    from ..core import log_path as audit_path

    return audit_path().with_suffix(".debug.log")


def debug_enabled() -> bool:
    """True when verbose logging was requested in the environment."""
    value = (os.environ.get(DEBUG_ENV) or "").strip().lower()
    return value not in ("", "0", "false", "no", "off")


class _AppendingFileHandler(logging.Handler):
    """Append one formatted line per record, closing the file each time."""

    def __init__(self, target: Path) -> None:
        super().__init__()
        self._target = Path(target)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
            self._target.parent.mkdir(parents=True, exist_ok=True)
            with self._target.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except Exception:  # pragma: no cover - logging must never raise
            pass


def _configure() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    root = logging.getLogger("zipbomb_lab")
    root.propagate = False
    root.setLevel(logging.DEBUG if debug_enabled() else logging.WARNING)
    if not root.handlers:
        # Always present: keeps Python's lastResort stderr handler out of the way.
        root.addHandler(logging.NullHandler())
        if debug_enabled():
            handler = _AppendingFileHandler(log_path())
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
            )
            root.addHandler(handler)
    _CONFIGURED = True


def get_logger(name: str = "zipbomb_lab") -> logging.Logger:
    """Return a configured child logger (never writes to stdout)."""
    _configure()
    if name == "zipbomb_lab" or name.startswith("zipbomb_lab."):
        return logging.getLogger(name)
    return logging.getLogger(f"zipbomb_lab.{name}")


__credit__ = "ZipBomb Lab - zipbomb_lab.infrastructure.logging - made by Xv @XvRendering https://github.com/MamadXV"
