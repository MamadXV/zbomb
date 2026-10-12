# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""The command layer: registry plus the built-in command set."""

from __future__ import annotations

from .registry import (
    COMMAND_GROUPS,
    Command,
    CommandContext,
    CommandRegistry,
    CommandResult,
)
from .builtins import SESSION_COMMANDS, build_registry

__all__ = [
    "COMMAND_GROUPS",
    "Command",
    "CommandContext",
    "CommandRegistry",
    "CommandResult",
    "SESSION_COMMANDS",
    "build_registry",
]


__credit__ = "ZipBomb Lab - zipbomb_lab.commands - made by Xv @XvRendering https://github.com/MamadXV"
