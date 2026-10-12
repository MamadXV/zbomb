# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""The lab's command set, registered once.

Each entry describes an existing capability: its summary, group, aliases,
examples and the argv that reaches the real argparse handler. A few in-app
actions (``version``, ``policy``, ``audit``, ``help``) carry a small handler so
the line shell and the command palette can run them without a subprocess.
"""

from __future__ import annotations

from ..ui import PROG
from .registry import Command, CommandContext, CommandRegistry, CommandResult

__all__ = ["build_registry", "SESSION_COMMANDS"]

#: Slash commands the interactive shell handles itself (all discoverable).
SESSION_COMMANDS = ("help", "clear", "quit", "status", "cd", "settings", "about")


def _version(ctx: CommandContext, args: list[str]) -> CommandResult:
    from .. import __version__

    return CommandResult(0, f"{PROG} {__version__}")


def _policy(ctx: CommandContext, args: list[str]) -> CommandResult:
    from ..core import describe_limits

    return CommandResult(0, "\n".join(describe_limits()))


def _audit(ctx: CommandContext, args: list[str]) -> CommandResult:
    from ..infrastructure.audit import default_audit_log

    lines = default_audit_log().read(20)
    return CommandResult(0, "\n".join(lines) if lines else "nothing recorded yet")


def _help(ctx: CommandContext, args: list[str]) -> CommandResult:
    registry: CommandRegistry = getattr(ctx, "registry", None) or build_registry()
    text = ["keyboard: ? help   Ctrl+K palette   Esc back   q quit", ""]
    for group, commands in registry.by_group().items():
        text.append(f"{group}:")
        for command in commands:
            text.append(f"  {command.name:<10} {command.summary}")
    return CommandResult(0, "\n".join(text))


def build_registry() -> CommandRegistry:
    """Construct the full command registry (cheap; safe to call repeatedly)."""
    registry = CommandRegistry()
    registry.register_all(
        [
            Command(
                name="demo",
                summary="build a tiny bomb and scan it back (safe, seconds)",
                group="core",
                aliases=("try",),
                usage=f"{PROG} demo [-s SIZE] [-m METHOD] [-o FILE]",
                examples=(f"{PROG} demo", f"{PROG} demo -s 16MiB -m bzip2"),
                keys=("d",),
                argv=("demo",),
            ),
            Command(
                name="create",
                summary="build a real archive (policy gated, writes data)",
                group="core",
                aliases=("build", "new"),
                usage=f"{PROG} create -s SIZE -o FILE [-m METHOD] [-l LEVEL]",
                examples=(
                    f"{PROG} create -s 16MiB -o demo.zip",
                    f"{PROG} create --recipe layered -s 1TiB -o layered.zip",
                ),
                keys=("c", "n"),
                argv=("create",),
                dangerous=True,
            ),
            Command(
                name="estimate",
                summary="model output size and runtime (writes nothing)",
                group="core",
                aliases=("plan", "size"),
                usage=f"{PROG} estimate -s SIZE [--compare]",
                examples=(
                    f"{PROG} estimate -s 1TiB --compare",
                    f"{PROG} estimate --recipe layered -s 1TiB",
                ),
                keys=("e",),
                argv=("estimate",),
            ),
            Command(
                name="recipes",
                summary="list the structural bomb families",
                group="core",
                aliases=("arsenal", "families"),
                usage=f"{PROG} recipes [-s SIZE]",
                examples=(f"{PROG} recipes -s 16MiB",),
                keys=("r",),
                argv=("recipes",),
            ),
            Command(
                name="methods",
                summary="calibration table: measured ratio and throughput",
                group="core",
                aliases=("table", "compare"),
                usage=f"{PROG} methods [-s SIZE]",
                examples=(f"{PROG} methods -s 1GiB",),
                keys=("m",),
                argv=("methods",),
            ),
            Command(
                name="inspect",
                summary="scan archives for bomb signatures (never extracts)",
                group="inspect",
                aliases=("scan", "check"),
                usage=f"{PROG} inspect ARCHIVE.zip [--deep]",
                examples=(f"{PROG} inspect archive.zip --deep",),
                keys=("i", "s"),
                argv=("inspect",),
            ),
            Command(
                name="config",
                summary="show or change remembered defaults",
                group="configure",
                aliases=("settings",),
                usage=f"{PROG} config [--show] [--set KEY=VALUE]",
                examples=(f"{PROG} config --set theme=tokyo",),
                keys=("o",),
                argv=("config",),
            ),
            Command(
                name="theme",
                summary="list themes or switch the colour theme",
                group="configure",
                usage=f"{PROG} theme [NAME]",
                examples=(f"{PROG} theme tokyo",),
                keys=("t",),
                argv=("theme",),
            ),
            Command(
                name="panel",
                summary="interactive control panel",
                group="session",
                aliases=("menu",),
                usage=f"{PROG} panel [--plain]",
                examples=(f"{PROG} panel",),
                keys=("p",),
                argv=("panel",),
                needs_terminal=True,
            ),
            Command(
                name="tui",
                summary="interactive full-screen console (keyboard first)",
                group="session",
                aliases=("gui",),
                usage=f"{PROG} tui",
                examples=(f"{PROG} tui",),
                keys=("ctrl+k",),
                argv=("tui",),
                needs_terminal=True,
            ),
            Command(
                name="selftest",
                summary="exercise the whole pipeline on 8 MiB payloads",
                group="session",
                aliases=("doctor",),
                usage=f"{PROG} selftest",
                examples=(f"{PROG} selftest",),
                argv=("selftest",),
            ),
            Command(
                name="about",
                summary="show project credits and description",
                group="session",
                usage=f"{PROG} about",
                argv=("about",),
            ),
            Command(
                name="policy",
                summary="show the safety caps and limits",
                group="configure",
                keys=("6",),
                handler=_policy,
            ),
            Command(
                name="audit",
                summary="show the tail of the artifact audit log",
                group="configure",
                keys=("a",),
                handler=_audit,
            ),
            Command(
                name="version",
                summary="print the version",
                group="session",
                usage=f"{PROG} version",
                argv=("version",),
                handler=_version,
            ),
            Command(
                name="help",
                summary="show commands, shortcuts and examples",
                group="session",
                keys=("?", "/help"),
                handler=_help,
            ),
        ]
    )
    return registry


__credit__ = "ZipBomb Lab - zipbomb_lab.commands.builtins - made by Xv @XvRendering https://github.com/MamadXV"
