# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""An extensible command registry.

Every user-facing action — the argparse subcommands, the interactive shell's
slash commands and the TUI command palette — is described once, here. Adding a
feature means registering a :class:`Command`; nothing else needs an ``if``
branch, a new help string and a new palette entry.

The registry holds only metadata and small in-app callbacks. Operations that
need real arguments are dispatched through the *existing* argparse parser (via
:attr:`CommandContext.run_argv`), so command semantics are never duplicated.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Callable

__all__ = [
    "Command",
    "CommandContext",
    "CommandResult",
    "CommandRegistry",
    "COMMAND_GROUPS",
]

#: Display order for the registry groups (used by help and the palette).
COMMAND_GROUPS = (
    "core",
    "inspect",
    "configure",
    "session",
)


@dataclass
class CommandResult:
    """What a command produced: an exit code and, optionally, a message."""

    exit_code: int = 0
    message: str = ""
    handled: bool = True

    def __bool__(self) -> bool:
        return self.exit_code == 0


@dataclass
class CommandContext:
    """Everything a command may need to do its job.

    *services* are injected, not imported, so a command never reaches into a
    global. *run_argv* dispatches an argv through the real argparse parser, so a
    command that wraps a subcommand inherits its exact semantics.
    """

    service: object = None
    settings: object = None
    config: object = None
    ux: object = None
    run_argv: Callable[[list[str]], int] | None = None
    logger: object = None

    def dispatch(self, argv: list[str]) -> CommandResult:
        """Run *argv* through the parser and wrap the code in a result."""
        if self.run_argv is None:  # pragma: no cover - misconfiguration
            return CommandResult(1, "command dispatch is unavailable")
        return CommandResult(int(self.run_argv(list(argv))))


@dataclass
class Command:
    """One discoverable action."""

    name: str
    summary: str
    group: str = "core"
    aliases: tuple[str, ...] = ()
    usage: str = ""
    examples: tuple[str, ...] = ()
    keys: tuple[str, ...] = ()
    handler: Callable[[CommandContext, list[str]], CommandResult] | None = None
    argv: tuple[str, ...] = ()
    dangerous: bool = False
    needs_terminal: bool = False

    @property
    def label(self) -> str:
        return self.name.replace("_", " ")

    def resolve_argv(self, args: list[str]) -> list[str]:
        """The argv to dispatch for this command (default args unless given)."""
        return list(args) if args else list(self.argv)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "summary": self.summary,
            "group": self.group,
            "aliases": list(self.aliases),
            "usage": self.usage,
            "examples": list(self.examples),
            "keys": list(self.keys),
            "dangerous": self.dangerous,
        }


class CommandRegistry:
    """An ordered, alias-aware collection of :class:`Command` objects."""

    def __init__(self) -> None:
        self._commands: list[Command] = []
        self._by_name: dict[str, Command] = {}
        self._aliases: dict[str, str] = {}

    # -- registration ------------------------------------------------------
    def register(self, command: Command) -> Command:
        """Add *command* (later registrations win for the same name)."""
        self._commands = [c for c in self._commands if c.name != command.name]
        self._commands.append(command)
        self._by_name[command.name] = command
        for alias in command.aliases:
            self._aliases[alias] = command.name
        return command

    def register_all(self, commands) -> None:
        for command in commands:
            self.register(command)

    # -- lookup ------------------------------------------------------------
    def get(self, name: str) -> Command | None:
        """Return the command for *name* or one of its aliases."""
        if not name:
            return None
        key = name.strip().lower()
        canonical = self._aliases.get(key, key)
        return self._by_name.get(canonical)

    def resolve(self, name: str) -> str | None:
        """Canonical command name for *name*/*alias*, or ``None``."""
        command = self.get(name)
        return command.name if command else None

    def canonical(self, name: str) -> str:
        """Canonical name when known, otherwise *name* unchanged."""
        return self.resolve(name) or (name or "")

    @property
    def aliases(self) -> dict[str, str]:
        return dict(self._aliases)

    def names(self) -> tuple[str, ...]:
        return tuple(command.name for command in self._commands)

    def all(self) -> list[Command]:
        return list(self._commands)

    def by_group(self) -> dict[str, list[Command]]:
        grouped: dict[str, list[Command]] = {group: [] for group in COMMAND_GROUPS}
        for command in self._commands:
            grouped.setdefault(command.group, []).append(command)
        return {group: items for group, items in grouped.items() if items}

    # -- search ------------------------------------------------------------
    def match_names(self, query: str, limit: int = 12) -> list[Command]:
        """Prefix/fuzzy match on names and aliases only (never summaries).

        Help and palette *hint* text must stay invisible to the matcher: a
        summary that mentions another command (``--set theme=tokyo``) would
        otherwise surface that command for unrelated queries.
        """
        return [
            command
            for command in self._match_names_or_summaries(query, limit, summaries=False)
        ]

    def match(self, query: str, limit: int = 12) -> list[Command]:
        """Prefix/fuzzy match across names, aliases and summaries."""
        return self._match_names_or_summaries(query, limit, summaries=True)

    def _match_names_or_summaries(
        self, query: str, limit: int, *, summaries: bool
    ) -> list[Command]:
        query = (query or "").strip().lower()
        if not query:
            return self.all()[:limit]
        scored: list[tuple[float, Command]] = []
        for command in self._commands:
            haystacks = (command.name, *command.aliases)
            if summaries:
                haystacks = (*haystacks, command.summary.lower())
            best = 0.0
            for haystack in haystacks:
                text = haystack.lower()
                if text.startswith(query):
                    best = max(best, 1.0)
                elif query in text:
                    best = max(best, 0.8)
                else:
                    ratio = difflib.SequenceMatcher(None, query, text).ratio()
                    if ratio >= 0.6:
                        best = max(best, ratio * 0.7)
            if best > 0:
                scored.append((best, command))
        scored.sort(key=lambda item: (-item[0], item[1].name))
        return [command for _, command in scored[:limit]]

    def suggestions(self, name: str, limit: int = 3) -> list[str]:
        """Close names for a typo, e.g. ``crate`` -> ``create``."""
        pool = list(self._by_name) + list(self._aliases)
        return difflib.get_close_matches((name or "").lower(), pool, n=limit, cutoff=0.6)

    def __len__(self) -> int:
        return len(self._commands)

    def __contains__(self, name: str) -> bool:
        return self.get(name) is not None


__credit__ = "ZipBomb Lab - zipbomb_lab.commands.registry - made by Xv @XvRendering https://github.com/MamadXV"
