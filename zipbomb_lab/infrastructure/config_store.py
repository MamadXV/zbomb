# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Persistent settings storage.

A thin, typed facade over the existing settings file (``core.config``), so the
on-disk JSON format, the ``ZIPBOMB_LAB_CONFIG`` override and the
"missing-or-damaged never stops the tool" behaviour are all preserved while
new code talks to a named object instead of loose functions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

__all__ = ["ConfigStore", "default_config_store"]


class ConfigStore:
    """Read and write the remembered defaults."""

    def __init__(self, path: Path | None = None) -> None:
        self._explicit = Path(path) if path else None

    @property
    def path(self) -> Path:
        """Where settings are read from / written to."""
        from ..core import config_path

        return self._explicit or config_path()

    def load(self) -> tuple[Any, list[str]]:
        """Return ``(config, warnings)``; never raises on a damaged file."""
        from ..core import load

        return load(self._explicit)

    def save(self, config: Any) -> Path:
        """Persist *config* atomically (creating the parent directory)."""
        from ..core import save

        return save(config, self._explicit)

    def exists(self) -> bool:
        return self.path.exists()


def default_config_store() -> ConfigStore:
    """The store the CLI uses when no ``--config`` was supplied."""
    return ConfigStore()


__credit__ = "ZipBomb Lab - zipbomb_lab.infrastructure.config_store - made by Xv @XvRendering https://github.com/MamadXV"
