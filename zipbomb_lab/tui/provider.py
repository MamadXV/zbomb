# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Command palette provider: fuzzy search over the command registry.

Backs ``Ctrl+K``. It lists every registered command (from
:func:`zipbomb_lab.commands.build_registry`) and runs it through the app, so
the palette can never drift from the real command set.
"""

from __future__ import annotations

from functools import partial

from textual.command import DiscoveryHit, Hit, Hits, Provider

from ..commands import build_registry

__all__ = ["LabCommandsProvider"]


class LabCommandsProvider(Provider):
    """A Textual command-palette provider over the lab's registry."""

    def _run(self, name: str) -> None:
        self.app.open_command(name)  # type: ignore[attr-defined]

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for command in build_registry().all():
            score = matcher.match(f"{command.name} {command.summary}")
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(command.name),
                    partial(self._run, command.name),
                    text=command.name,
                    help=command.summary,
                )

    async def discover(self) -> Hits:
        for command in build_registry().all():
            yield DiscoveryHit(
                command.name,
                partial(self._run, command.name),
                text=command.name,
                help=command.summary,
            )


__credit__ = "ZipBomb Lab - zipbomb_lab.tui.provider - made by Xv @XvRendering https://github.com/MamadXV"
