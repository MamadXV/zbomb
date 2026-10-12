# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Settings access for the front ends.

Wraps :class:`~zipbomb_lab.infrastructure.config_store.ConfigStore` in a tiny
service that also applies a remembered theme globally, mirroring what the
classic CLI does when it loads its configuration.
"""

from __future__ import annotations

from pathlib import Path

from ..domain.data import theme_keys
from ..infrastructure.config_store import ConfigStore

__all__ = ["SettingsService"]


class SettingsService:
    """Load, save and apply the remembered defaults."""

    def __init__(self, path: Path | None = None) -> None:
        self.store = ConfigStore(path)

    @property
    def path(self) -> Path:
        return self.store.path

    def load(self):
        """Return ``(config, warnings)``."""
        return self.store.load()

    def save(self, config) -> Path:
        return self.store.save(config)

    def apply_theme(self, config) -> str:
        """Activate the remembered theme (best effort) and return its name."""
        from ..ui import DEFAULT_THEME, active_theme_name, set_theme

        name = getattr(config, "theme", None) or DEFAULT_THEME
        try:
            set_theme(name)
        except ValueError:
            set_theme(DEFAULT_THEME)
            return DEFAULT_THEME
        return active_theme_name()

    def set_values(self, config, pairs) -> list[str]:
        """Apply ``KEY=VALUE`` pairs to *config*; return human error strings.

        The validation rules match ``cmd_config --set`` exactly (booleans,
        integers, the theme registry), so behaviour does not drift.
        """
        from ..ui import THEMES, THEME_NAMES, did_you_mean

        problems: list[str] = []
        for item in pairs or ():
            if "=" not in item:
                problems.append(f"expected KEY=VALUE, got {item!r}")
                continue
            key, _, raw = item.partition("=")
            key = key.strip()
            if not hasattr(config, key):
                problems.append(f"unknown setting {key!r}")
                continue
            current = getattr(config, key)
            value = raw.strip()
            if key == "theme":
                choice = value.lower()
                if choice not in THEMES:
                    suggestions = did_you_mean(choice, list(THEME_NAMES))
                    hint = f" - did you mean '{suggestions[0]}'?" if suggestions else ""
                    problems.append(
                        f"unknown theme {value!r}{hint} - choose one of: {', '.join(THEME_NAMES)}"
                    )
                    continue
                setattr(config, key, choice)
            elif isinstance(current, bool):
                setattr(config, key, value.lower() in ("1", "true", "yes", "on"))
            elif isinstance(current, int):
                try:
                    setattr(config, key, int(value))
                except ValueError:
                    problems.append(f"{key} needs a whole number, got {value!r}")
            else:
                setattr(config, key, value)
        return problems

    def theme_names(self) -> tuple[str, ...]:
        return tuple(theme_keys())


__credit__ = "ZipBomb Lab - zipbomb_lab.services.settings_service - made by Xv @XvRendering https://github.com/MamadXV"
