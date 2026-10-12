# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Command line interface.

Subcommands::

    create     build an archive (capped by policy)
    estimate   model a target size without writing anything
    inspect    scan archives for bomb signatures (metadata first)
    methods    calibration table: measured ratio and throughput per method
    panel      start the interactive control panel
    config     show or change remembered defaults
    selftest   exercise the whole pipeline on 8 MiB payloads
    version    print the version

Exit codes: ``0`` success/clean, ``1`` usage, policy or IO error, ``2`` the
scan found something suspicious, ``3`` a file could not be inspected, and
``130`` a create run was interrupted by the user (the archive is finalised and
can be continued with ``create --resume``).
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

from rich import box
from rich.panel import Panel as RichPanel
from rich.table import Table
from rich.text import Text

from .core import (
    ACK_PHRASE,
    MAX_SPLITS,
    Config,
    Policy,
    append_audit,
    check_create as _check_create_unused,
    check_recipe as _check_recipe_unused,
    config_path as _config_path_unused,
    load as _load_unused,
    log_path,
    read_audit,
    save as _save_unused,
)
from . import __version__
from . import core as _core
from . import engine as _engine
from . import ui as _ui
from . import credits as _z
from .ui import (
    AUTHOR, GITHUB, TELEGRAM, TOOL, TAGLINE, WATERMARK, PROG,
    UX, brand_footer, welcome_box, brand_panel,
    hero, menu_grid, kv_card, stat_cards, verdict_badge, bar, style_name,
    Selector, did_you_mean, section, error_card,
    clear_screen, paint_black, reset_screen,
    THEMES, THEME_NAMES, DEFAULT_THEME, set_theme, active_theme_name,
    theme_swatch, cursor_color, block, status_line, shortcuts_bar, diamond,
)
import zipbomb_lab.core as _core_mod
config_mod = _core_mod
craft = _engine
detect = _engine
make = _engine
methods = _core_mod
policy = _core_mod
recipes = _engine
sizes = _core_mod
_theme = _ui
welcome_box_fallback = welcome_box  # compat: panel.py import alias

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_SUSPICIOUS = 2
EXIT_UNREADABLE = 3
EXIT_INTERRUPTED = 130

#: Single source of truth for command metadata (names, aliases, summaries).
#: The parser, the welcome screen, the line shell and the TUI palette all read
#: from here, so a command is described exactly once.
from .commands import build_registry as _build_registry  # noqa: E402

REGISTRY = _build_registry()

#: Friendly shorthand so the common verbs can be typed the obvious way. Every
#: alias dispatches to the same handler as its canonical command.
ALIASES = dict(REGISTRY.aliases)

#: Canonical commands (used for typo suggestions and the showcase menu).
_COMMANDS = REGISTRY.names()

EPILOG = """\
typical use:
  {PROG} demo                       build a tiny bomb and scan it back
  {PROG} create -s 16MiB            make a small demo archive
  {PROG} plan -s 1TiB --compare     model every method, write nothing
  {PROG} scan archive.zip --deep    scan an untrusted archive
  {PROG} recipes                    list the structural bomb families
  {PROG} create --recipe layered -s 1TiB   build a 42.zip-class bomb
  {PROG} panel                      friendly interactive menu

shorthand: build, new, plan, size, scan, check, table, menu, settings, doctor,
           try, recipes. Sizes accept 512MiB, 100GB, 1.5TiB, 2TB, 1PiB.

run only on hardware you own. See readme.md before creating anything large.

{TOOL} v{__version__} - made by {AUTHOR} - {TELEGRAM} - {GITHUB}
""".format(TOOL=TOOL, __version__=__version__, AUTHOR=AUTHOR, TELEGRAM=TELEGRAM, GITHUB=GITHUB, PROG=PROG)

def _add_common_options(parser: argparse.ArgumentParser, suppress_defaults: bool = False) -> None:
    """Add the options shared by every subcommand.

    The subcommand copies use ``SUPPRESS`` defaults so that a value given
    *before* the subcommand (``zbomb --progress plain estimate``) is not
    overwritten by the subparser's own default.
    """
    default = argparse.SUPPRESS if suppress_defaults else "auto"
    parser.add_argument(
        "--progress",
        choices=("auto", "ansi", "plain", "log", "none"),
        default=default,
        help="output mode; 'log' is chosen automatically when stdout is not a terminal",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        default=argparse.SUPPRESS if suppress_defaults else False,
        help="same as --progress none (errors still print)",
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default=argparse.SUPPRESS if suppress_defaults else None,
        help="settings file to use instead of the default location",
    )
    parser.add_argument(
        "--no-brand",
        action="store_true",
        default=argparse.SUPPRESS if suppress_defaults else False,
        help="hide the watermark footer and branded welcome",
    )
    parser.add_argument(
        "--theme",
        choices=THEME_NAMES,
        default=argparse.SUPPRESS if suppress_defaults else None,
        help="color theme for this run (default: remembered setting, else ember)",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        default=argparse.SUPPRESS if suppress_defaults else False,
        help="tight layout: smaller hero, no blank padding lines",
    )


def _common_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    _add_common_options(common, suppress_defaults=True)
    return common


def _add_recipe_options(parser: argparse.ArgumentParser) -> None:
    """Add the structural-bomb options shared by create and estimate."""
    parser.add_argument(
        "--recipe",
        choices=sorted(recipes.RECIPES),
        help="structural bomb family (default: flat)",
    )
    parser.add_argument("--layers", type=int, help="nesting depth for layered/cascade")
    parser.add_argument("--fanout", type=int, help="copies per level for layered/cascade")
    parser.add_argument("--entries", type=int, help="entry count for the wide recipe")
    parser.add_argument(
        "--names", choices=recipes.NAME_STYLES, help="entry naming style (plain or mimic)"
    )
    parser.add_argument(
        "--preamble",
        choices=sorted(craft.PREAMBLES),
        help="polyglot preamble prepended so the file also looks like another type",
    )


class StunningHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Help with loud section headers and aligned examples (plain-text safe)."""

    def start_section(self, heading):
        if heading:
            heading = f"== {heading.upper()} =="
        super().start_section(heading)


class ZipBombParser(argparse.ArgumentParser):
    """ArgumentParser that suggests the right command on typos."""

    def error(self, message):
        import re as _re

        munged = message
        found = _re.search(r"invalid choice: '([^']+)'", message)
        if found:
            bad = found.group(1)
            known = list(_COMMANDS) + sorted(ALIASES) + list(THEME_NAMES)
            suggestions = did_you_mean(bad, known)
            if suggestions:
                munged += f" (did you mean '{suggestions[0]}'?)"
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {munged}\n")


def build_parser() -> argparse.ArgumentParser:
    """Assemble the full argument parser."""
    common = _common_parser()
    parser = ZipBombParser(
        prog=PROG,
        description=(
            "Build, measure and detect compression bombs - a small lab toolkit.\n"
            "Run it only on hardware you own, in an isolated VM or container."
        ),
        epilog=EPILOG,
        formatter_class=StunningHelpFormatter,
    )
    _add_common_options(parser)
    parser.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="command")

    create = sub.add_parser(
        "create",
        aliases=["build", "new"],
        parents=[common],
        help="build an archive (writes real data)",
        description="Stream a zero-filled archive to disk. Policy gated.",
        epilog=(
            "examples:\n"
            f"  {PROG} create -s 16MiB                     small demo archive\n"
            f"  {PROG} create -s 1TiB -m bzip2 --split 8GiB  resumable parts\n"
            f"  {PROG} create -s 2TiB --dry-run            plan only, write nothing\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    create.add_argument("-s", "--size", help="uncompressed target, e.g. 100MB, 1GiB, 1TiB")
    create.add_argument("-o", "--output", help="archive path (default: generated name)")
    create.add_argument(
        "-m", "--method", choices=sorted(methods.METHODS), help="compression method"
    )
    create.add_argument("-l", "--level", type=int, help="level (deflate/bzip2) or preset (lzma)")
    create.add_argument("--chunk", help="write buffer size, e.g. 4MiB")
    create.add_argument("--split", help="split into entries of this size (enables --resume)")
    create.add_argument(
        "--verify",
        choices=("none", "sample", "full"),
        help="read the archive back afterwards (full decompresses everything)",
    )
    create.add_argument("--resume", action="store_true", help="continue an existing archive")
    create.add_argument("--no-overwrite", action="store_true", help="refuse to replace a file")
    create.add_argument("--force", action="store_true", help="allow targets above the cap")
    create.add_argument("--ack", help=f'cap override phrase: "{policy.ACK_PHRASE}"')
    create.add_argument("--no-banner", action="store_true", help="hide the safety banner")
    create.add_argument("--dry-run", action="store_true", help="plan and check, write nothing")
    create.add_argument("--json", action="store_true", help="machine readable result")
    _add_recipe_options(create)

    estimate = sub.add_parser(
        "estimate",
        aliases=["plan", "size"],
        parents=[common],
        help="model output size and runtime (writes nothing)",
    )
    estimate.add_argument("-s", "--size", help="uncompressed target, e.g. 1TiB, 500GB")
    estimate.add_argument("-m", "--method", choices=sorted(methods.METHODS))
    estimate.add_argument("-l", "--level", type=int)
    estimate.add_argument("--split", help="assume entries of this size")
    estimate.add_argument("--compare", action="store_true", help="table for every method")
    estimate.add_argument("--json", action="store_true")
    _add_recipe_options(estimate)

    inspect = sub.add_parser(
        "inspect",
        aliases=["scan", "check"],
        parents=[common],
        help="scan archives for bomb signatures",
    )
    inspect.add_argument("paths", nargs="+", help="zip files to scan")
    inspect.add_argument("--max-ratio", type=float, help="flag entries above this ratio")
    inspect.add_argument("--max-total", help="flag archives declaring more than this")
    inspect.add_argument("--deep", action="store_true", help="probe entries for nested archives")
    inspect.add_argument("--max-depth", type=int, help="nesting depth to follow (deep mode)")
    inspect.add_argument("--probe-bytes", help="decompressed budget per entry (deep mode)")
    inspect.add_argument("--json", action="store_true")

    demo = sub.add_parser(
        "demo",
        aliases=["try"],
        parents=[common],
        help="build a tiny bomb and scan it back",
        description="One command that shows the whole loop: a small archive, then a scan.",
    )
    demo.add_argument("-s", "--size", default="16MiB", help="payload size (default 16MiB)")
    demo.add_argument("-m", "--method", choices=sorted(methods.METHODS), default="bzip2")
    demo.add_argument("-o", "--output", help="archive path (default: generated name)")
    demo.add_argument("--no-banner", action="store_true", help="hide the safety banner")

    table = sub.add_parser(
        "methods", aliases=["table"], parents=[common], help="calibration table"
    )
    table.add_argument("-s", "--size", default="1TiB", help="target used for the table")
    table.add_argument("--json", action="store_true")

    recipe_cmd = sub.add_parser(
        "recipes",
        aliases=["arsenal", "families"],
        parents=[common],
        help="list the structural bomb families",
        description=(
            "Show every structural recipe with a small live estimate: flat, "
            "layered (42.zip class), cascade (codec chain) and wide (entry count)."
        ),
    )
    recipe_cmd.add_argument("-s", "--size", default="1TiB", help="target used for the sample")
    recipe_cmd.add_argument("--json", action="store_true")

    panel = sub.add_parser(
        "panel", aliases=["menu"], parents=[common], help="interactive control panel"
    )
    panel.add_argument("--plain", action="store_true", help="numbered menu instead of ANSI")

    sub.add_parser(
        "tui",
        aliases=["gui"],
        parents=[common],
        help="interactive full-screen console (falls back to the menu)",
    )

    config_cmd = sub.add_parser(
        "config", aliases=["settings"], parents=[common], help="show or change defaults"
    )
    config_cmd.add_argument("--show", action="store_true", help="print the settings file")
    config_cmd.add_argument(
        "--set", action="append", metavar="KEY=VALUE", help="change a remembered default"
    )

    theme_cmd = sub.add_parser(
        "theme", parents=[common], help="list themes or switch the color theme"
    )
    theme_cmd.add_argument(
        "name", nargs="?", help=f"theme to preview and remember ({', '.join(THEME_NAMES)})"
    )
    theme_cmd.add_argument("--json", action="store_true", help="machine readable registry")

    sub.add_parser(
        "selftest",
        aliases=["doctor"],
        parents=[common],
        help="exercise the pipeline on 8 MiB payloads",
    )
    sub.add_parser("about", parents=[common], help="show project credits and description")
    sub.add_parser("version", help="print the version")
    return parser


def ux_for(args) -> UX:
    """Build the output helper for parsed arguments."""
    mode = "none" if getattr(args, "quiet", False) else getattr(args, "progress", "auto")
    ux = UX(mode)
    cfg = getattr(args, "_cfg", None)
    ux.compact = bool(
        getattr(args, "compact", False) or (getattr(cfg, "compact", False) if cfg else False)
    )
    return ux


def _apply_ux_theme(args, ux: UX, cfg: config_mod.Config) -> None:
    """Activate the --theme flag or remembered theme on this UX."""
    name = getattr(args, "theme", None) or getattr(cfg, "theme", None) or DEFAULT_THEME
    try:
        set_theme(name)
    except ValueError:
        ux.warn(f"unknown theme {name!r} in settings; using {DEFAULT_THEME}")
        set_theme(DEFAULT_THEME)
    ux.compact = bool(getattr(args, "compact", False) or getattr(cfg, "compact", False))


def load_config(args, ux: UX) -> config_mod.Config:
    """Load remembered defaults, reporting any warning.

    Also activates the theme and compact flag on ``ux``. The config is
    stashed on ``args`` so repeated calls never read the file twice.
    """
    cached = getattr(args, "_cfg", None)
    if cached is not None:
        _apply_ux_theme(args, ux, cached)
        return cached
    path = Path(args.config) if getattr(args, "config", None) else None
    cfg, warnings = config_mod.load(path)
    for warning in warnings:
        ux.warn(warning)
    args._cfg = cfg
    _apply_ux_theme(args, ux, cfg)
    return cfg


def default_output_name(
    size_text: str, method: str, level: int | None = None, recipe: str = "flat"
) -> str:
    """Generate an archive name that describes what is inside."""
    safe = "".join(ch if ch.isalnum() else "-" for ch in size_text).strip("-") or "target"
    method_def = methods.get_method(method)
    suffix = (
        f"{method_def.key}{methods.normalize_level(method_def.key, level)}"
        if method_def.supports_level
        else method_def.key
    )
    tag = f"_{recipe}" if recipe and recipe != "flat" else ""
    return f"zeros_{safe}_{suffix}{tag}.zip"


def _spinner(ux: UX, label: str, enabled: bool = True):
    """A spinner disabled automatically for machine-readable output."""
    return ux.spin(label, enabled=enabled and ux.verbose)


def print_plan(ux: UX, plan: recipes.BombPlan, title: str = "recipe plan") -> None:
    """Print a structural bomb plan in the same shape as a plain estimate."""
    ux.header(title, f"{plan.label} - modeled by assembling in memory, nothing written")
    for line in plan.summary_lines():
        label, _, value = line.partition("  ")
        label = label.strip()
        value = value.strip()
        if label == "expansion ratio":
            value = ux.accent(value)
        ux.field(label, value)


def print_estimate(ux: UX, est: methods.Estimate, title: str = "estimate") -> None:
    """Print one estimate as a labelled block with an expansion meter."""
    ux.header(title, "modeled from a live in-memory calibration - nothing written")
    if ux.is_ansi and ux.console is not None:
        from rich.text import Text

        runtime = (
            f"{sizes.format_size(int(est.megabytes_per_second * sizes.MIB))}/s "
            f"-> ~{_duration(est.seconds)}"
        )
        entries = f"{est.entries:,}" + (
            f" of {sizes.format_size(est.split_bytes)}" if est.split_bytes else ""
        )
        grid = Table.grid(padding=(0, 2), expand=True)
        grid.add_column(justify="right", style=_theme.style_name("gray_light"))
        grid.add_column(style=_theme.style_name("white"))
        grid.add_row("method", Text(methods.describe_method(est.method, est.level)))
        grid.add_row("target", Text(sizes.format_size(est.target_bytes)))
        grid.add_row(
            "projected output",
            Text(
                sizes.format_size(est.output_bytes),
                style="bold " + _theme.style_name("orange"),
            ),
        )
        grid.add_row(
            "expansion ratio",
            Text(
                methods.format_ratio(est.ratio),
                style="bold " + _theme.style_name("orange"),
            ),
        )
        grid.add_row("runtime", Text(runtime))
        grid.add_row("entries", Text(entries))
        grid.add_row("zip64", Text("yes" if est.zip64_required else "no"))
        grid.add_row("encoder memory", Text(sizes.format_size(est.encoder_memory)))
        ux.console.print(
            RichPanel(
                grid,
                title=Text(title.upper(), style="bold " + _theme.style_name("orange")),
                border_style=_theme.style_name("gray_dark"),
                box=box.ROUNDED,
                padding=(0, 1),
            )
        )
    else:
        ux.field("method", methods.describe_method(est.method, est.level))
        ux.field("target (uncompressed)", sizes.format_size(est.target_bytes))
        ux.field("projected output", sizes.format_size(est.output_bytes))
        ux.field("expansion ratio", ux.accent(methods.format_ratio(est.ratio)))
        ux.field(
            "estimated runtime",
            f"{sizes.format_size(int(est.megabytes_per_second * sizes.MIB))}/s "
            f"-> ~{_duration(est.seconds)}",
        )
        ux.field("entries", f"{est.entries:,}" + (f" of {sizes.format_size(est.split_bytes)}" if est.split_bytes else ""))
        ux.field("zip64 required", "yes" if est.zip64_required else "no")
        ux.field("encoder memory", sizes.format_size(est.encoder_memory))
    # A 100 MiB reference bar makes the expansion feel real at a glance.
    reference = methods.estimate(100 * sizes.MIB, est.method, est.level)
    if reference.output_bytes > 0:
        ux.write(
            "  "
            + ux.style("100 MiB becomes", "gray")
            + " "
            + ux.accent(sizes.format_size(reference.output_bytes))
        )


def _duration(seconds: float) -> str:
    from .core import format_duration

    return format_duration(seconds)


def print_create_result(ux: UX, result) -> None:
    """Print the fields of a finished build in the ember theme."""
    ux.header(
        f"result: {sizes.format_size(result.archive_bytes)} on disk",
        f"expands to {sizes.format_size(result.declared_bytes)}",
    )
    for line in result.summary_lines():
        label, _, value = line.partition("  ")
        label = label.strip()
        value = value.strip()
        if label == "expansion ratio":
            value = ux.accent(value)
        ux.field(label, value)


def print_comparison(ux: UX, target: int, level: int | None = None) -> list[methods.Estimate]:
    """Print and return the per-method comparison table."""
    ux.header(
        f"method comparison for {sizes.format_size(target)} of repetitive data",
        "ratios and speeds measured in memory on this machine just now",
    )
    rows = methods.compare_methods(target, level)
    smallest = min(rows, key=lambda e: e.output_bytes)
    fastest = min(rows, key=lambda e: e.seconds)
    table_rows = []
    for est in rows:
        name = methods.describe_method(est.method, est.level)
        if est.method == smallest.method:
            name += "  ★ smallest"
        if est.method == fastest.method:
            name += "  ★ fastest"
        table_rows.append(
            [
                name,
                methods.format_ratio(est.ratio),
                sizes.format_size(est.output_bytes),
                _duration(est.seconds),
                sizes.format_size(est.encoder_memory),
            ]
        )
    ux.table(
        ["method", "ratio", "output", "runtime", "memory"],
        table_rows,
        column_styles=[None, "orange", None, None, None],
    )
    ux.detail(
        "visible archives use deflate, bzip2 or lzma according to --method; "
        "pick with the smallest output you can wait for"
    )
    return rows


def cmd_estimate(args) -> int:
    """Model a size without touching the disk."""
    ux = ux_for(args)
    cfg = load_config(args, ux)
    try:
        target = sizes.parse_size(args.size or cfg.size)
        split = sizes.parse_size(args.split) if args.split else None
    except sizes.SizeError as exc:
        ux.error(str(exc))
        return EXIT_ERROR

    policy_obj = policy.Policy()
    try:
        policy_obj.check_estimate_target(target)
    except policy.PolicyError as exc:
        ux.error(str(exc))
        return EXIT_ERROR

    if args.compare:
        if args.json:
            ux.write(
                json.dumps(
                    [row.as_dict() for row in methods.compare_methods(target, args.level)],
                    indent=2,
                    sort_keys=True,
                )
            )
            return EXIT_OK
        print_comparison(ux, target, args.level)
        return EXIT_OK

    if getattr(args, "recipe", None) and args.recipe != "flat":
        try:
            bomb = recipes.plan(
                args.recipe,
                target,
                args.method or cfg.method,
                args.level,
                args.layers,
                args.fanout,
                args.entries,
                args.names or "plain",
                args.preamble or "none",
            )
        except ValueError as exc:
            ux.error(str(exc))
            return EXIT_ERROR
        if args.json:
            ux.write(json.dumps(bomb.as_dict(), indent=2, sort_keys=True))
            return EXIT_OK
        print_plan(ux, bomb)
        for warning in bomb.warnings:
            ux.warn(warning)
        return EXIT_OK

    try:
        with _spinner(ux, "calibrating", enabled=not args.json):
            est = methods.estimate(target, args.method or cfg.method, args.level, split)
    except ValueError as exc:
        ux.error(str(exc))
        return EXIT_ERROR

    if args.json:
        ux.write(json.dumps(est.as_dict(), indent=2, sort_keys=True))
        return EXIT_OK
    print_estimate(ux, est)
    for warning in est.warnings:
        ux.warn(warning)
    return EXIT_OK


def cmd_methods(args) -> int:
    """Show the calibration table and a projection for one target size."""
    ux = ux_for(args)
    try:
        target = sizes.parse_size(args.size)
    except sizes.SizeError as exc:
        ux.error(str(exc))
        return EXIT_ERROR

    if args.json:
        ux.write(
            json.dumps(
                [row.as_dict() for row in methods.compare_methods(target)],
                indent=2,
                sort_keys=True,
            )
        )
        return EXIT_OK

    ux.header(
        "calibration on this interpreter",
        "every number is measured in RAM right before it is shown",
    )

    print_comparison(ux, target)
    ux.write("")
    ux.title("method details")
    notes = {
        "stored": "baseline: no compression at all",
        "deflate": "what most zip tools use",
        "bzip2": "RLE pre-pass makes long runs collapse",
        "lzma": "slowest here; zipfile ignores its level, we do not",
    }
    ux.table(
        ["method", "zip constant", "levels", "default", "notes"],
        [
            [
                key,
                str(method_def.zip_constant),
                str(method_def.level_range),
                "-" if method_def.default_level is None else str(method_def.default_level),
                notes.get(key, ""),
            ]
            for key, method_def in methods.METHODS.items()
        ],
        column_styles=["orange", None, None, None, None],
    )
    return EXIT_OK


def _create_recipe(
    args, ux: UX, cfg, recipe_key: str, name_style: str, output: Path,
    target: int, size_text: str, method: str, level: int | None, split,
) -> int:
    """Plan, gate and build a structural (non-flat) recipe."""
    if split:
        ux.warn("--split does not apply to structural recipes and was ignored")
    if getattr(args, "resume", False):
        ux.warn("--resume does not apply to structural recipes and was ignored")

    try:
        bomb = recipes.plan(
            recipe_key,
            target,
            method,
            level,
            getattr(args, "layers", None),
            getattr(args, "fanout", None),
            getattr(args, "entries", None),
            name_style,
            getattr(args, "preamble", None) or "none",
        )
    except ValueError as exc:
        ux.error(str(exc))
        return EXIT_ERROR

    if not args.json:
        print_plan(ux, bomb, "recipe plan")
        free = policy.disk_free(output.parent)
        ux.field("output path", str(output))
        ux.field(
            "free on target", sizes.format_size(free) if free is not None else "unknown"
        )

    try:
        warnings = policy.check_recipe(
            output, bomb, force=args.force, ack=args.ack, overwrite=not args.no_overwrite
        )
    except policy.PolicyError as exc:
        ux.error(str(exc))
        config_mod.append_audit(
            {
                "event": "refused",
                "reason": exc.kind,
                "path": str(output),
                "recipe": recipe_key,
                "expanded_bytes": bomb.expanded_bytes,
                "method": method,
            }
        )
        return EXIT_ERROR

    for warning in warnings:
        if not args.json:
            ux.warn(warning)

    if args.dry_run:
        if args.json:
            ux.write(
                json.dumps(
                    {
                        "dry_run": True,
                        "output": str(output),
                        "plan": bomb.as_dict(),
                        "warnings": warnings,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            ux.ok("dry run complete - nothing was written")
        return EXIT_OK

    if not args.no_banner and not args.json:
        ux.banner()

    test_ux = UX("none") if args.json else ux
    try:
        result = recipes.build_bomb(
            output,
            bomb,
            ux=test_ux,
            verify=args.verify or cfg.verify,
            overwrite=not args.no_overwrite,
            show_progress=not args.quiet and not args.json,
        )
    except (FileExistsError, ValueError, OSError) as exc:
        ux.error(str(exc))
        return EXIT_ERROR

    if not args.json:
        print_create_result(ux, result)
        for warning in result.warnings:
            ux.warn(warning)

    config_mod.append_audit(
        {
            "event": "created",
            "path": str(result.path),
            "recipe": result.recipe,
            "layers": result.layers,
            "fanout": result.fanout,
            "target_bytes": result.target_bytes,
            "expanded_bytes": result.expanded_bytes,
            "declared_bytes": result.declared_bytes,
            "archive_bytes": result.archive_bytes,
            "method": result.method,
            "level": result.level,
            "ratio": round(result.ratio, 2),
            "seconds": round(result.seconds, 2),
            "entries": result.entries,
        }
    )
    if args.json:
        ux.write(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    else:
        ux.ok(
            f"created {result.path} - {sizes.format_size(result.archive_bytes)} on disk, "
            f"expands to {sizes.format_size(result.expanded_bytes)}"
        )
    return EXIT_OK


def cmd_create(args) -> int:
    """Plan, gate and then build one archive."""
    ux = ux_for(args)
    cfg = load_config(args, ux)

    try:
        size_text = args.size or cfg.size
        target = sizes.parse_size(size_text)
        split = (
            sizes.parse_size(args.split)
            if args.split
            else (sizes.parse_size(cfg.split) if cfg.split else None)
        )
        chunk = sizes.parse_size(args.chunk or cfg.chunk)
    except sizes.SizeError as exc:
        ux.error(str(exc))
        return EXIT_ERROR

    method = (args.method or cfg.method).lower()
    level = args.level
    if level is None and method == (cfg.method or "").lower():
        level = cfg.level

    recipe_key = getattr(args, "recipe", None) or "flat"
    name_style = getattr(args, "names", None) or "plain"

    output = Path(args.output) if args.output else Path(cfg.output_dir) / default_output_name(
        size_text, method, level, recipe_key
    )

    if recipe_key != "flat":
        return _create_recipe(
            args, ux, cfg, recipe_key, name_style, output, target, size_text,
            method, level, split,
        )

    try:
        with _spinner(ux, "planning", enabled=not args.json):
            est = methods.estimate(target, method, level, split)
    except ValueError as exc:
        ux.error(str(exc))
        return EXIT_ERROR

    if not args.json:
        print_estimate(ux, est, "plan")
        free = policy.disk_free(output.parent)
        ux.field("output path", str(output))
        ux.field("free on target", sizes.format_size(free) if free is not None else "unknown")

    try:
        warnings = policy.check_create(
            output, est, force=args.force, ack=args.ack, overwrite=not args.no_overwrite
        )
    except policy.PolicyError as exc:
        ux.error(str(exc))
        config_mod.append_audit(
            {
                "event": "refused",
                "reason": exc.kind,
                "path": str(output),
                "target_bytes": target,
                "method": method,
            }
        )
        return EXIT_ERROR

    for warning in warnings:
        if not args.json:
            ux.warn(warning)

    if args.dry_run:
        if not args.json:
            ux.ok("dry run complete - nothing was written")
        if args.json:
            ux.write(
                json.dumps(
                    {
                        "dry_run": True,
                        "output": str(output),
                        "plan": est.as_dict(),
                        "warnings": warnings,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        return EXIT_OK

    if not args.no_banner and not args.json:
        ux.banner()

    test_ux = UX("none") if args.json else ux
    if not args.json:
        ux.step_ok(f"plan ready - {sizes.format_size(target)} with {method}")
    try:
        result = make.create_archive(
            output,
            target,
            method=method,
            level=level,
            chunk_bytes=chunk,
            split=split,
            ux=test_ux,
            show_progress=not args.quiet and not args.json,
            verify=args.verify or cfg.verify,
            resume=args.resume,
            overwrite=not args.no_overwrite,
            warnings=warnings,
        )
    except (FileExistsError, ValueError, OSError) as exc:
        ux.error(str(exc))
        return EXIT_ERROR
    if not args.json:
        ux.step_ok(f"verified {result.entries} entrie(s) with {args.verify or cfg.verify}")

    if not args.json:
        print_create_result(ux, result)
        for warning in result.warnings:
            ux.warn(warning)

    config_mod.append_audit(
        {
            "event": "created",
            "path": str(result.path),
            "target_bytes": result.target_bytes,
            "declared_bytes": result.declared_bytes,
            "archive_bytes": result.archive_bytes,
            "method": result.method,
            "level": result.level,
            "ratio": round(result.ratio, 2),
            "seconds": round(result.seconds, 2),
            "entries": result.entries,
            "interrupted": result.interrupted,
        }
    )
    if args.json:
        ux.write(json.dumps(result.as_dict(), indent=2, sort_keys=True))

    if result.interrupted:
        if not args.json:
            ux.warn("the run was interrupted; continue it with:")
            ux.detail(
                f'{PROG} create -s {size_text} -m {method} '
                f'-o "{result.path}" --resume'
            )
        return EXIT_INTERRUPTED

    if not args.json:
        ux.ok(
            f"created {result.path} - {sizes.format_size(result.archive_bytes)} on disk, "
            f"{sizes.format_size(result.declared_bytes)} when expanded"
        )
    return EXIT_OK


def cmd_inspect(args) -> int:
    """Scan one or more archives."""
    ux = ux_for(args)
    try:
        max_total = (
            sizes.parse_size(args.max_total) if args.max_total else detect.DEFAULT_MAX_TOTAL
        )
        probe = (
            sizes.parse_size(args.probe_bytes)
            if args.probe_bytes
            else detect.DEFAULT_PROBE_BYTES
        )
    except sizes.SizeError as exc:
        ux.error(str(exc))
        return EXIT_ERROR

    reports = []
    worst = EXIT_OK
    for raw in args.paths:
        try:
            report = detect.scan_archive(
                Path(raw),
                max_ratio=(
                    args.max_ratio if args.max_ratio is not None else detect.DEFAULT_MAX_RATIO
                ),
                max_total=max_total,
                deep=args.deep,
                max_depth=args.max_depth or detect.DEFAULT_MAX_DEPTH,
                probe_bytes=probe,
            )
        except detect.ZipBombError as exc:
            ux.error(str(exc))
            worst = max(worst, EXIT_UNREADABLE)
            continue

        reports.append(report)
        if args.json:
            continue  # machine-readable output only; printed once below
        ux.rule()
        ux.header(str(report.path), "metadata-first scan, nothing extracted")
        ux.field("verdict", ux.verdict(report.verdict(), report.suspicious))
        ux.field("entries", f"{report.entry_count:,}")
        ux.field("declared contents", sizes.format_size(report.total_uncompressed))
        ux.field("stored payload", sizes.format_size(report.total_compressed))
        ux.field(
            "largest ratio",
            f"{methods.format_ratio(report.max_ratio)} on {report.max_ratio_entry or 'n/a'}",
        )
        ux.field("zip64", "yes" if report.zip64 else "no")
        if report.families:
            ux.field("bomb family", ux.accent(", ".join(report.families)))
        if args.deep:
            ux.field("bytes probed", sizes.format_size(report.probed_bytes))
        for note in report.notes:
            ux.detail(note)
        for reason in report.reasons:
            ux.warn(reason)
        for finding in report.findings[:20]:
            ux.write(
                f"    {finding.name}  ratio {methods.format_ratio(finding.ratio)}  "
                f"method {finding.method}"
            )
            for flag in finding.flags:
                ux.detail(f"- {flag}")
        if len(report.findings) > 20:
            ux.detail(
                f"... {len(report.findings) - 20:,} more flagged entries (--json has all)"
            )
        if not report.suspicious:
            ux.ok("no bomb signature found at these thresholds")

    if args.json:
        ux.write(json.dumps([r.as_dict() for r in reports], indent=2, sort_keys=True))

    if reports:
        worst = max(worst, max(report.exit_code for report in reports))
    return worst


def cmd_recipes(args) -> int:
    """List the structural bomb families with a small live estimate."""
    ux = ux_for(args)
    try:
        target = sizes.parse_size(args.size)
    except sizes.SizeError as exc:
        ux.error(str(exc))
        return EXIT_ERROR
    try:
        policy.Policy().check_estimate_target(target)
    except policy.PolicyError as exc:
        ux.error(str(exc))
        return EXIT_ERROR

    sample_method = "bzip2"
    bombs = []
    with _spinner(ux, "assembling recipes", enabled=not args.json):
        for recipe in recipes.describe_recipes():
            try:
                bombs.append(recipes.plan(recipe.key, target, sample_method))
            except ValueError as exc:
                ux.warn(f"{recipe.key}: {exc}")

    if args.json:
        ux.write(json.dumps([bomb.as_dict() for bomb in bombs], indent=2, sort_keys=True))
        return EXIT_OK

    ux.header(
        f"structural recipes for {sizes.format_size(target)}",
        "each row is assembled in memory just now - nothing is written",
    )
    shapes = {
        "flat": "one stream of zeros",
        "layered": "recursive, fanout ** layers",
        "cascade": "recursive, codec per level",
        "wide": "one level, many entries",
        "traversal": "symlink loop + special files",
        "onopen": "long-named index flood",
        "stack": "gzip/xz/bzip2 chain in a zip",
        "overlap": "local vs central disagreement",
    }
    ux.table(
        ["recipe", "shape", "archive", "expands to", "ratio"],
        [
            [
                bomb.recipe,
                shapes.get(bomb.recipe, ""),
                sizes.format_size(bomb.archive_bytes),
                sizes.format_size(bomb.expanded_bytes),
                methods.format_ratio(bomb.ratio),
            ]
            for bomb in bombs
        ],
        column_styles=["orange", None, None, None, "orange"],
    )
    ux.write("")
    for recipe in recipes.describe_recipes():
        ux.write(
            "  "
            + ux.style(f"{recipe.key:<9}", "bold", "orange")
            + recipe.summary
        )
    ux.detail(f"build one with: {PROG} create --recipe layered -s 1TiB")
    ux.detail("recipes are structural; --method still chooses the codec")
    ux.detail(
        "--names mimic disguises the entry names; --preamble pdf|html|gif makes "
        "the file a polyglot"
    )
    ux.detail(
        "traversal/onopen bite on open or on a recursive walk; overlap and stack "
        "defeat metadata-only and zip-only scanners"
    )
    ux.detail(
        "a true self-replicating quine still needs hand-crafted raw bytes and is "
        "out of scope here"
    )
    return EXIT_OK


def cmd_welcome(args) -> int:
    """Friendly landing page shown when no command is given."""
    ux = ux_for(args)
    if ux.is_ansi and not getattr(args, "no_brand", False):
        ux.console.print(_theme.hero(ux, footer=f"run '{PROG} <command> --help' for options"))
        section(ux, "❯", "GET STARTED", "pick a command — every write is policy gated")
        ux.console.print(
            _theme.menu_grid(
                [
                    ("demo", "Guided tour", "tiny bomb, scanned"),
                    ("create", "Build an archive", "policy gated"),
                    ("estimate", "Model a size", "writes nothing"),
                    ("inspect", "Scan an archive", "never extracts"),
                    ("panel", "Interactive menu", "arrow-key picker"),
                    ("recipes", "Bomb families", "8 structures"),
                    ("methods", "Speed and ratio", "measured live"),
                    ("config", "Defaults", "saved settings"),
                    ("selftest", "Pipeline check", "verifies all"),
                ],
                width=ux.console.size.width,
            )
        )
        section(ux, "»", "TRY FIRST", "safe on any machine, finishes in seconds")
        ux.write("  " + ux.style(f"{PROG} demo", "bold", "orange") + ux.style("   build a tiny bomb and scan it back", "gray"))
        ux.write("  " + ux.style(f"{PROG} panel", "bold", "orange") + ux.style("  guided menus with live estimates", "gray"))
        ux.write("")
        shortcuts_bar(ux, [("↑↓", "navigate"), ("Enter", "run"), ("--help", "options"), ("--theme", "theme")])
        ux.write("  " + ux.style("for isolated lab use, on hardware you own", "gray"))
        brand_footer(ux)
        return EXIT_OK
    if not getattr(args, "no_brand", False):
        welcome_box(ux)
    else:
        ux.header(TOOL, "build, measure and detect compression bombs")
    ux.write("  " + ux.style("for isolated lab use, on hardware you own", "gray"))
    ux.write("")
    ux.write("  " + ux.style("GET STARTED", "bold", "white"))
    commands = (
        ("demo", "build a tiny bomb and scan it back (safe, seconds)"),
        ("create", "build an archive - policy gated, writes real data"),
        ("estimate", "model any size without writing anything"),
        ("inspect", "scan an untrusted archive before you touch it"),
        ("panel", "colourful interactive menu"),
        ("recipes", "structural bomb families: layered, cascade, wide"),
        ("methods", "measured compression table for this machine"),
        ("config", "remembered defaults"),
        ("selftest", "check the whole pipeline works"),
    )
    for name, blurb in commands:
        ux.bullet(ux.accent(f"{name:<10}") + blurb)
    ux.write("")
    ux.detail(f"run '{PROG} <command> --help' for options and examples")
    if not getattr(args, "no_brand", False):
        brand_footer(ux)
    return EXIT_OK


def cmd_demo(args) -> int:
    """Build a small demo archive and immediately scan it back."""
    ux = ux_for(args)
    cfg = load_config(args, ux)
    size_text = args.size
    method = args.method
    try:
        target = sizes.parse_size(size_text)
        est = methods.estimate(target, method)
    except (sizes.SizeError, ValueError) as exc:
        ux.error(str(exc))
        return EXIT_ERROR

    output = (
        Path(args.output)
        if args.output
        else Path(cfg.output_dir) / default_output_name(size_text, method)
    )
    try:
        policy.check_create(output, est, overwrite=True)
    except policy.PolicyError as exc:
        ux.error(str(exc))
        return EXIT_ERROR

    ux.header("demo", f"{sizes.format_size(target)} of zeros -> one tiny archive")
    print_estimate(ux, est, "plan")
    ux.field("output path", str(output))

    if not args.no_banner:
        ux.banner()

    try:
        result = make.create_archive(
            output,
            target,
            method=method,
            ux=ux,
            verify="sample",
            overwrite=True,
        )
    except (FileExistsError, ValueError, OSError) as exc:
        ux.error(str(exc))
        return EXIT_ERROR

    config_mod.append_audit(
        {
            "event": "created",
            "source": "demo",
            "path": str(result.path),
            "declared_bytes": result.declared_bytes,
            "archive_bytes": result.archive_bytes,
            "method": result.method,
            "level": result.level,
            "ratio": round(result.ratio, 2),
            "seconds": round(result.seconds, 2),
            "entries": result.entries,
        }
    )
    print_create_result(ux, result)

    report = detect.scan_archive(output, deep=True)
    ux.header("scan", f"reading {output} back with the detector")
    ux.field("verdict", ux.verdict(report.verdict(), report.suspicious))
    ux.field("largest ratio", ux.accent(methods.format_ratio(report.max_ratio)))
    for reason in report.reasons:
        ux.warn(reason)
    ux.detail("this is what a scanner sees; extract only on a machine you own")
    return EXIT_OK


def cmd_selftest(args) -> int:
    """Exercise create, verify and scan on small payloads."""
    import tempfile

    ux = ux_for(args)
    payload = 8 * sizes.MIB
    failures = 0
    ux.title(f"selftest: {sizes.format_size(payload)} of zeros per method")
    machine_readable = getattr(args, "json", False)

    with tempfile.TemporaryDirectory(prefix="zipbomb_lab_") as temp_dir:
        for method_key in methods.METHODS:
            path = Path(temp_dir) / f"{method_key}.zip"
            try:
                with _spinner(ux, f"testing {method_key}", enabled=not machine_readable):
                    result = make.create_archive(
                        path,
                        payload,
                        method=method_key,
                        ux=UX("none") if machine_readable else ux,
                        show_progress=False,
                        verify="none",
                    )
                report = detect.scan_archive(path)
                verify = make.verify_archive(path, "full")
            except Exception as exc:  # noqa: BLE001 - any failure is a failed check
                ux.error(f"{method_key}: create failed: {exc}")
                failures += 1
                continue

            checks = [
                ("declared size", result.declared_bytes == payload),
                ("single entry", result.entries == 1),
                ("ratio measured", result.ratio >= 1.0),
                ("full verify", verify.ok and verify.bytes_read == payload),
            ]
            if method_key == "stored":
                checks.append(("scan stays quiet", not report.suspicious))
            else:
                checks.append(("scan flags it", report.suspicious))
            bad = [name for name, ok in checks if not ok]
            if bad:
                ux.error(f"{method_key}: failed {', '.join(bad)}")
                failures += 1
            else:
                ux.step_ok(
                    f"{method_key}: {result.archive_bytes:,} bytes on disk, "
                    f"ratio {methods.format_ratio(result.ratio)}"
                )

    if failures:
        ux.error(f"{failures} method(s) failed")
        return EXIT_ERROR
    ux.ok("selftest passed")
    return EXIT_OK


def cmd_config(args) -> int:
    """Show or change remembered defaults."""
    ux = ux_for(args)
    explicit = getattr(args, "config", None)
    path = Path(explicit) if explicit else config_mod.config_path()
    cfg, warnings = config_mod.load(Path(explicit) if explicit else None)
    for warning in warnings:
        ux.warn(warning)

    if args.set:
        problems: list[str] = []
        for item in args.set:
            if "=" not in item:
                problems.append(f"expected KEY=VALUE, got {item!r}")
                continue
            key, _, raw = item.partition("=")
            key = key.strip()
            if not hasattr(cfg, key):
                problems.append(f"unknown setting {key!r}")
                continue
            current = getattr(cfg, key)
            value = raw.strip()
            if key == "theme":
                choice = value.lower()
                if choice not in THEMES:
                    suggestions = did_you_mean(choice, THEME_NAMES)
                    hint = f" - did you mean '{suggestions[0]}'?" if suggestions else ""
                    problems.append(
                        f"unknown theme {value!r}{hint} - choose one of: {', '.join(THEME_NAMES)}"
                    )
                    continue
                setattr(cfg, key, choice)
            elif isinstance(current, bool):
                setattr(cfg, key, value.lower() in ("1", "true", "yes", "on"))
            elif isinstance(current, int):
                try:
                    setattr(cfg, key, int(value))
                except ValueError:
                    problems.append(f"{key} needs a whole number, got {value!r}")
            else:
                setattr(cfg, key, value)
        if problems:
            for problem in problems:
                ux.error(problem)
            return EXIT_ERROR
        saved = config_mod.save(cfg, Path(explicit) if explicit else None)
        ux.ok(f"saved {saved}")

    ux.title(f"settings: {path}")
    for field_name in (
        "output_dir",
        "method",
        "level",
        "size",
        "chunk",
        "split",
        "progress",
        "verify",
        "confirm_before_write",
        "theme",
        "compact",
    ):
        ux.field(field_name, str(getattr(cfg, field_name)))
    ux.detail(f"audit log: {config_mod.log_path()}")
    return EXIT_OK


def cmd_panel(args) -> int:
    """Start the interactive console (full-screen TUI, or the classic menu).

    The full-screen interface is only used when the terminal can render it;
    ``--plain`` (or a non-interactive stream) keeps the numbered menu so
    scripts and tests behave exactly as before.
    """
    ux = ux_for(args)
    plain = bool(getattr(args, "plain", False))
    config_path = Path(args.config) if getattr(args, "config", None) else None
    if not plain and _tui_available():
        from .tui import run_tui

        return run_tui(config_path=config_path)
    return panel_main(ux=ux, config_path=config_path, plain=plain)


def cmd_tui(args) -> int:
    """Launch the full-screen console, explaining why if that is impossible."""
    config_path = Path(args.config) if getattr(args, "config", None) else None
    if not _tui_available():
        ux = ux_for(args)
        ux.error("the full-screen console cannot run in this terminal")
        ux.detail(f"use a real terminal (tty) with a UTF-8 locale, or run '{PROG} panel --plain'")
        return EXIT_ERROR
    from .tui import run_tui

    return run_tui(config_path=config_path)


def _tui_available() -> bool:
    """True when Textual is installed and the terminal is interactive."""
    try:
        from .tui.app import can_use_tui
    except Exception:  # pragma: no cover - textual missing or broken
        return False
    try:
        return bool(can_use_tui())
    except Exception:  # pragma: no cover - defensive
        return False


def cmd_theme(args) -> int:
    """List the color themes, or preview one and remember it."""
    ux = ux_for(args)
    cfg = load_config(args, ux)
    if getattr(args, "json", False):
        ux.write(
            json.dumps(
                [
                    {
                        "name": name,
                        "label": entry["label"],
                        "description": entry["description"],
                        "dark": entry["dark"],
                        "active": name == active_theme_name(),
                    }
                    for name, entry in THEMES.items()
                ],
                indent=2,
                sort_keys=True,
            )
        )
        return EXIT_OK

    name = (getattr(args, "name", None) or "").strip().lower()
    if not name:
        # Picker when interactive, plain table otherwise.
        if ux.is_ansi and ux.console is not None and sys.stdin.isatty():
            options = [
                f"{entry['label']} - {entry['description']}"
                + ("  (active)" if key == active_theme_name() else "")
                for key, entry in THEMES.items()
            ]
            picked = Selector(ux, "theme").ask(options, list(THEMES).index(active_theme_name()) + 1)
            name = list(THEMES)[picked - 1]
        else:
            rows = []
            for key, entry in THEMES.items():
                marker = "(active)" if key == active_theme_name() else ""
                rows.append([key, entry["label"], entry["description"], marker])
            ux.table(
                ["theme", "label", "look", ""],
                rows,
                column_styles=["orange", None, None, None],
            )
            ux.detail(f"preview one with: {PROG} theme <name>  ({', '.join(THEME_NAMES)})")
            return EXIT_OK

    if name not in THEMES:
        suggestions = did_you_mean(name, THEME_NAMES)
        error_card(ux, f"unknown theme {name!r}", suggestions)
        return EXIT_ERROR
    previous = set_theme(name)
    ux.write("")
    diamond(ux, f"theme preview: {THEMES[name]['label']} - {THEMES[name]['description']}")
    if ux.is_ansi and ux.console is not None:
        ux.console.print(hero(ux, footer=f"theme {name} (was {previous})"))
    else:
        ux.detail(f"theme {name} active (was {previous})")
    if name != getattr(cfg, "theme", DEFAULT_THEME):
        cfg.theme = name
        explicit = getattr(args, "config", None)
        try:
            saved = config_mod.save(cfg, Path(explicit) if explicit else None)
        except OSError as exc:
            ux.error(f"could not save settings: {exc}")
            return EXIT_ERROR
        ux.ok(f"remembered {name} as the default theme ({saved})")
    else:
        ux.ok(f"theme {name} active")
    return EXIT_OK


def cmd_version(args) -> int:
    """Print the package version."""
    print(f"{PROG} {__version__}")
    return EXIT_OK


def cmd_about(args) -> int:
    """Show project credits and description."""
    from .ui import AUTHOR, TELEGRAM, GITHUB
    from . import __version__

    print(f"ZIP BOMB LAB v{__version__}")
    print("Build, measure and detect compression bombs - for isolated lab use")
    print()
    print(f"Author: {AUTHOR}")
    print(f"Telegram: {TELEGRAM}")
    print(f"GitHub: {GITHUB}")
    print()
    print("This tool is a research-grade lab for building, measuring and detecting")
    print("compression bombs. It supports:")
    print()
    print("  * Flat zero-fill bombs (any size the policy allows)")
    print("  * Structural recipes: layered, cascade, wide, traversal, onopen, stack, overlap")
    print("  * Live calibration on the current interpreter")
    print("  * Deep scanning for nested/ambiguous archives")
    print()
    print("All artifacts are created in an isolated directory you control.")
    print("Never extract a bomb on a system you care about.")
    print()
    print(f"Made by {AUTHOR} - {TELEGRAM} - {GITHUB}")
    return EXIT_OK


def main_entry() -> None:
    """Console-script entry point (setuptools calls this with no args)."""
    raise SystemExit(main())


def main(argv=None) -> int:
    """Entry point used by ``python -m zipbomb_lab`` and the legacy script."""
    _z.n()
    parser = build_parser()
    args = parser.parse_args(argv)
    # Warm the theme globally (and stash the config) so even commands that
    # never call load_config render in the right theme.
    load_config(args, ux_for(args))
    handlers = {
        "create": cmd_create,
        "estimate": cmd_estimate,
        "inspect": cmd_inspect,
        "demo": cmd_demo,
        "methods": cmd_methods,
        "recipes": cmd_recipes,
        "panel": cmd_panel,
        "tui": cmd_tui,
        "config": cmd_config,
        "theme": cmd_theme,
        "selftest": cmd_selftest,
        "version": cmd_version,
        "about": cmd_about,
    }
    command = ALIASES.get(args.command, args.command)
    if command is None:
        # No subcommand: a capable terminal gets the full-screen console,
        # everything else (pipes, CI, tests) keeps the classic welcome screen.
        if _tui_available():
            return cmd_tui(args)
        return cmd_welcome(args)
    try:
        code = handlers[command](args)
    except KeyboardInterrupt:
        UX("plain").warn("interrupted")
        return EXIT_INTERRUPTED
    # Watermark footer after every command, unless suppressed or writing a
    # machine-readable stream (--json must stay byte-for-byte parseable).
    if not getattr(args, "no_brand", False) and not getattr(args, "json", False):
        brand_footer(ux_for(args))
    return code


# ======================================================================
# merged from panel.py — interactive control panel (same file = fewer files)
# ======================================================================
SIZE_PRESETS = ("10MB", "100MB", "1GB", "10GB", "100GB", "500GB", "1TiB")

MENU = (
    "",
    "  1) Create an archive            (writes real data, policy gated)",
    "  2) Estimate a size              (writes nothing)",
    "  3) Inspect / scan an archive    (bounded, never extracts)",
    "  4) Compare methods              (measured on this machine)",
    "  5) Configure defaults           (remembered in the settings file)",
    "  6) Safety policy and limits",
    "  7) Audit log",
    "  8) Bomb recipes                (layered, cascade, wide)",
    "  0) Exit",
)


class _Quit(Exception):
    """Raised to leave the panel when input ends."""


class ControlPanel:
    """The interactive session."""

    def __init__(self, ux: UX, config_path: Path | None = None, plain: bool = False) -> None:
        self.ux = ux
        self.config_path = Path(config_path) if config_path else None
        self.plain = plain
        self.config, warnings = _core_mod.load(self.config_path)
        for warning in warnings:
            ux.warn(warning)

    # -- input helpers -----------------------------------------------------
    def _prompt(self, text: str) -> str:
        try:
            self.ux.stream.write(text)
            self.ux.stream.flush()
        except Exception:  # pragma: no cover - closed stream
            pass
        try:
            return input().strip()
        except (EOFError, StopIteration) as exc:
            raise _Quit() from exc

    def ask(self, label: str, default: str = "") -> str:
        suffix = f" [{default}]" if default else ""
        answer = self._prompt(f"{label}{suffix}: ")
        return answer or default

    def ask_int(self, label: str, default: int, low: int, high: int) -> int:
        while True:
            answer = self.ask(label, str(default))
            try:
                value = int(answer)
            except ValueError:
                self.ux.warn("please enter a whole number")
                continue
            if not low <= value <= high:
                self.ux.warn(f"value must be between {low} and {high}")
                continue
            return value

    def ask_choice(self, label: str, options: list[str], default: int = 1) -> int:
        """Arrow-key picker on a real terminal, numbered list everywhere else."""
        if self.plain:
            self.ux.write(f"  {label}")
            for index, option in enumerate(options, start=1):
                marker = " (default)" if index == default else ""
                self.ux.write(f"    {index}) {option}{marker}")
            while True:
                answer = self.ask("choose", str(default))
                try:
                    choice = int(answer)
                except ValueError:
                    self.ux.warn("please enter a number from the list")
                    continue
                if 1 <= choice <= len(options):
                    return choice
                self.ux.warn(f"choose between 1 and {len(options)}")
        return Selector(self.ux, label).ask(options, default)
        # NOTE: Selector falls back to a numbered list with defaults when the
        # session is not interactive; EOF there returns the default, while the
        # plain branch above raises _Quit so `panel.main([])` still exits.

    def confirm(self, question: str, default: bool = False) -> bool:
        default_text = "Y/n" if default else "y/N"
        answer = self.ask(f"{question} ({default_text})", "").lower()
        if not answer:
            return default
        return answer in ("y", "yes")

    @staticmethod
    def _preset_index(default: str) -> int:
        try:
            value = sizes.parse_size(default)
        except sizes.SizeError:
            return len(SIZE_PRESETS) + 1
        for index, preset in enumerate(SIZE_PRESETS, start=1):
            if sizes.parse_size(preset) == value:
                return index
        return len(SIZE_PRESETS) + 1

    def ask_size(self, label: str, default: str) -> tuple[int, str]:
        """Ask for a size, returning ``(bytes, text_as_typed)``."""
        while True:
            options = list(SIZE_PRESETS) + ["type a custom size"]
            choice = self.ask_choice(label, options, default=self._preset_index(default))
            if choice <= len(SIZE_PRESETS):
                text = SIZE_PRESETS[choice - 1]
            else:
                text = self.ask("size (e.g. 1TiB, 500GB, 4GiB)", default)
            try:
                return sizes.parse_size(text), text
            except sizes.SizeError as exc:
                self.ux.warn(str(exc))

    def save_config(self) -> None:
        try:
            path = _core_mod.save(self.config, self.config_path)
        except OSError as exc:
            self.ux.error(f"could not save settings: {exc}")
            return
        self.ux.ok(f"settings saved to {path}")

    # -- slash commands ------------------------------------------------------
    #: Panel slash commands (grok-style `/` prefix), handled in typed mode.
    SLASH_COMMANDS = ("theme", "compact", "status", "clear", "help", "quit")

    def slash(self, line: str) -> None:
        """Run one `/command [args]` line typed at the panel prompt."""
        ux = self.ux
        parts = line.strip().split()
        if not parts:
            return
        cmd, rest = parts[0].lower(), parts[1:]
        if cmd in ("quit", "exit", "q"):
            raise _Quit()
        if cmd == "help":
            block(
                ux,
                "slash commands",
                [
                    "/theme [name]  - pick a color theme, live preview, optional save",
                    "/compact on|off - tight layout without padding lines",
                    "/status       - show the bottom status segments now",
                    "/clear        - wipe and repaint the panel",
                    "/help         - this list",
                    "/quit         - leave the panel",
                ],
            )
            ux.detail("numbered menus also accept shortcuts: c e s m o p a r q")
            return
        if cmd == "clear":
            if ux.is_ansi:
                self.repaint()
            return
        if cmd == "status":
            status_line(ux, self.status_segments())
            for seg in self.status_segments():
                ux.detail(f"- {seg}")
            return
        if cmd == "compact":
            if rest:
                want = rest[0].lower() in ("1", "true", "yes", "on")
            else:
                want = not bool(self.config.compact)
            self.config.compact = want
            ux.compact = want
            self.save_config()
            ux.ok(f"compact mode {'on' if want else 'off'}")
            return
        if cmd == "theme":
            self.theme_flow(rest[0] if rest else None)
            return
        suggestions = did_you_mean(cmd, self.SLASH_COMMANDS)
        error_card(ux, f"unknown slash command '/{cmd}'", [f"/{s}" for s in suggestions])

    def theme_flow(self, name: str | None = None) -> None:
        """Pick a color theme with preview, optional keep + save."""
        ux = self.ux
        if name is not None:
            key = name.strip().lower()
            if key not in THEMES:
                error_card(ux, f"unknown theme {name!r}", did_you_mean(key, THEME_NAMES))
                return
            picked = key
        else:
            options = [
                f"{entry['label']} - {entry['description']}"
                + ("  (active)" if key == active_theme_name() else "")
                for key, entry in THEMES.items()
            ]
            picked = list(THEMES)[self.ask_choice("color theme", options, 1) - 1]
        previous = set_theme(picked)
        ux.write("")
        diamond(ux, f"preview: {THEMES[picked]['label']} - {THEMES[picked]['description']}")
        if ux.is_ansi and ux.console is not None:
            ux.console.print(hero(ux, footer=f"theme {picked} (was {previous})"))
        else:
            ux.detail(f"theme {picked} active (was {previous})")
        if not self.confirm(f"keep the {picked} theme?", True):
            set_theme(previous)
            ux.warn(f"reverted to {previous}")
            return
        self.config.theme = picked
        if self.confirm("remember it as the default theme?", True):
            self.save_config()
        else:
            ux.ok(f"theme {picked} active for this session")


    # -- menu --------------------------------------------------------------
    def status_segments(self) -> list[str]:
        """Segments for the bottom status row (grok-style)."""
        cfg = self.config
        return [
            Path.cwd().name,
            f"{cfg.method}-{cfg.level}",
            str(cfg.size),
            active_theme_name(),
        ]

    def repaint(self) -> None:
        """Clean slate + black canvas + hero, used at open and on /clear."""
        clear_screen(self.ux)
        paint_black(self.ux)
        cursor_color(self.ux)
        if self.ux.console is not None:
            self.ux.console.print(hero(self.ux), style="on black")

    def run(self) -> int:
        full_screen = Selector(self.ux, "panel")._interactive() and not self.plain
        if full_screen:
            # Clean slate: wipe the terminal, flood it black, then render.
            self.repaint()
        elif self.ux.is_ansi and self.ux.console is not None:
            brand_panel(self.ux)
        elif not self.plain:
            welcome_box_fallback(self.ux)
        else:
            self.ux.header("ZIP BOMB LAB", "interactive control panel")
        self.ux.field("settings", str(self.config_path or _core_mod.config_path()))
        self.ux.field("output dir", self.config.output_dir)
        self.ux.field("create cap", sizes.format_size(policy.MAX_CREATE_BYTES))
        self.ux.detail("isolated lab use only; Ctrl+C at a prompt cancels the step")

        shortcuts = {
            "c": "1", "create": "1",
            "e": "2", "estimate": "2",
            "s": "3", "scan": "3", "inspect": "3",
            "m": "4", "methods": "4", "compare": "4",
            "o": "5", "config": "5", "configure": "5",
            "p": "6", "policy": "6", "safety": "6",
            "a": "7", "audit": "7",
            "r": "8", "recipes": "8",
        }
        use_picker = full_screen
        shortcuts_hint = [("↑↓", "navigate"), ("Enter", "select"), ("/", "commands"), ("q", "quit")]
        while True:
            if self.ux.is_ansi:
                status_line(self.ux, self.status_segments())
            if self.ux.is_ansi and self.ux.console is not None and not use_picker:
                # merged-away

                items = [
                    ("1", "Create an archive", "writes real data"),
                    ("2", "Estimate a size", "writes nothing"),
                    ("3", "Scan an archive", "bounded probe"),
                    ("4", "Compare methods", "measured live"),
                    ("5", "Configure defaults", ""),
                    ("6", "Safety policy", "caps and limits"),
                    ("7", "Audit log", ""),
                    ("8", "Bomb recipes", "8 structures"),
                    ("0", "Exit", ""),
                ]
                section(self.ux, "◈", "CONTROL PANEL", "type a number/shortcut")
                self.ux.console.print(
                    _theme.menu_grid(items, width=self.ux.console.size.width)
                )
            elif not self.ux.is_ansi or self.ux.console is None:
                for line in MENU:
                    if line and line.strip()[:1].isdigit():
                        number, _, rest = line.partition(")")
                        self.ux.write(self.ux.accent(number) + ")" + rest)
                    else:
                        self.ux.write(line)
            # NOTE: in picker mode the menu is NOT printed here — the arrow
            # picker below renders its own list in place, so the two can never
            # overlap and garble each other.
            if self.ux.is_ansi and not use_picker:
                shortcuts_bar(self.ux, shortcuts_hint)
            try:
                if use_picker:
                    picked = Selector(self.ux, "select").ask(
                        [
                            "Create an archive", "Estimate a size", "Scan an archive",
                            "Compare methods", "Configure defaults", "Safety policy",
                            "Audit log", "Bomb recipes", "Exit",
                        ],
                        9,
                    )
                    choice = str(picked) if picked <= 8 else "0"
                else:
                    raw = self._prompt("select> ")
                    if raw.startswith("/"):
                        self.slash(raw[1:])
                        continue
                    choice = shortcuts.get(raw.lower(), raw.lower())
            except _Quit:
                self.ux.info("")
                self.ux.ok("bye")
                reset_screen(self.ux)
                return EXIT_OK
            if choice in ("", "0", "q", "quit", "exit"):
                self.ux.ok("bye")
                reset_screen(self.ux)
                return EXIT_OK
            try:
                if choice == "1":
                    self.create_flow()
                elif choice == "2":
                    self.estimate_flow()
                elif choice == "3":
                    self.inspect_flow()
                elif choice == "4":
                    with self.ux.spin("measuring"):
                        rows = print_comparison(self.ux, sizes.parse_size(self.config.size))
                elif choice == "5":
                    self.configure_flow()
                elif choice == "6":
                    self.policy_flow()
                elif choice == "7":
                    self.audit_flow()
                elif choice == "8":
                    self.recipes_flow()
                else:
                    suggestions = did_you_mean(choice, list(shortcuts))
                    error_card(self.ux, f"unknown option '{choice}'", suggestions)
            except _Quit:
                self.ux.info("")
                self.ux.ok("bye")
                reset_screen(self.ux)
                return EXIT_OK
            except KeyboardInterrupt:
                self.ux.info("")
                self.ux.warn("cancelled")

    def _choose_method(self, extra: list[str] | None = None) -> tuple[str, int | None]:
        """Ask for a method and, when it has one, a level."""
        keys = list(methods.METHODS)
        labels = [f"{key} - {methods.METHODS[key].label}" for key in keys]
        if extra:
            labels = labels + extra
        default = keys.index(self.config.method) + 1 if self.config.method in keys else 2
        choice = self.ask_choice("compression method", labels, default)
        if extra and choice > len(keys):
            return keys[0], None
        method = keys[choice - 1]
        method_def = methods.METHODS[method]
        if not method_def.supports_level:
            return method, 0
        default_level = (
            self.config.level
            if method == self.config.method
            else (method_def.default_level or method_def.max_level)
        )
        level = self.ask_int(
            f"{method} {method_def.level_label} ({method_def.level_range})",
            default_level,
            method_def.min_level,
            method_def.max_level,
        )
        return method, level


    def create_flow(self) -> None:
        """Collect choices, show the plan, confirm, then write."""
        ux = self.ux
        ux.title("create an archive")
        method, level = self._choose_method()
        target, size_text = self.ask_size("target uncompressed size", self.config.size)

        split = None
        if self.confirm(
            "split the payload into several entries (makes Ctrl+C resume work)?",
            bool(self.config.split),
        ):
            while split is None:
                try:
                    split = sizes.parse_size(
                        self.ask("entry size", self.config.split or "256MiB")
                    )
                except sizes.SizeError as exc:
                    ux.warn(str(exc))

        suggested = str(
            Path(self.config.output_dir) / default_output_name(size_text, method, level)
        )
        output = Path(self.ask("output file", suggested)).expanduser()

        try:
            with ux.spin("planning"):
                est = methods.estimate(target, method, level, split)
        except ValueError as exc:
            ux.error(str(exc))
            return

        print_estimate(ux, est, "plan")
        free = policy.disk_free(output.parent)
        ux.field("output path", str(output))
        ux.field("free on target", sizes.format_size(free) if free is not None else "unknown")

        if output.exists() and not self.confirm(f"{output} exists - replace it?", False):
            ux.warn("kept the existing file; nothing was written")
            return

        warnings: list[str] = []
        try:
            warnings = policy.check_create(output, est)
        except policy.PolicyError as exc:
            ux.error(str(exc))
            if exc.kind != "cap":
                return
            if not self.confirm("override the cap? it requires an exact phrase", False):
                ux.detail("tip: option 2 models any size without writing anything")
                return
            ack = self.ask("type the phrase exactly", "")
            if ack != policy.ACK_PHRASE:
                ux.warn("the phrase did not match - cancelled")
                return
            try:
                warnings = policy.check_create(output, est, force=True, ack=ack)
            except policy.PolicyError as inner:
                ux.error(str(inner))
                return

        for warning in warnings:
            ux.warn(warning)

        if self.config.confirm_before_write and not self.confirm(
            "write the archive now?", True
        ):
            ux.warn("cancelled")
            return

        ux.banner()
        try:
            with ux.spin("writing", enabled=not ux.is_ansi):
                result = make.create_archive(
                    output,
                    target,
                    method=method,
                    level=level,
                    chunk_bytes=sizes.parse_size(self.config.chunk),
                    split=split,
                    ux=ux,
                    verify=self.config.verify,
                    warnings=warnings,
                )
        except (FileExistsError, ValueError, OSError) as exc:
            ux.error(str(exc))
            return

        print_create_result(ux, result)
        _core_mod.append_audit(
            {
                "event": "created",
                "source": "panel",
                "path": str(result.path),
                "declared_bytes": result.declared_bytes,
                "archive_bytes": result.archive_bytes,
                "method": result.method,
                "level": result.level,
                "ratio": round(result.ratio, 2),
                "seconds": round(result.seconds, 2),
                "entries": result.entries,
            }
        )
        ux.ok(f"created {result.path}")

        self.config.method = method
        if level:
            self.config.level = level
        self.config.output_dir = str(output.parent)
        if split and split < target:
            self.config.split = size_text
        if self.confirm("remember these choices?", False):
            self.save_config()


    def estimate_flow(self) -> None:
        """Model a size, including an all-method comparison."""
        ux = self.ux
        ux.title("estimate a size")
        target, _ = self.ask_size("target uncompressed size", self.config.size)
        method, level = self._choose_method(extra=["compare every method"])
        if level is None:
            with ux.spin("measuring"):
                print_comparison(ux, target)
            return
        try:
            with ux.spin("calibrating"):
                est = methods.estimate(target, method, level)
        except ValueError as exc:
            ux.error(str(exc))
            return
        print_estimate(ux, est)
        for warning in est.warnings:
            ux.warn(warning)
        ux.detail("nothing was written; choose option 1 when you want the real archive")

    def inspect_flow(self) -> None:
        """Scan an archive chosen from the current folder or typed in."""
        ux = self.ux
        ux.title("inspect / scan an archive")
        candidates: list[Path] = []
        seen: set[str] = set()
        for directory in {Path.cwd(), Path(self.config.output_dir)}:
            try:
                found = sorted(directory.glob("*.zip"))
            except OSError:
                continue
            for path in found:
                key = str(path.resolve())
                if key not in seen:
                    seen.add(key)
                    candidates.append(path)

        options = [str(path) for path in candidates[:12]] + ["type a path"]
        choice = self.ask_choice("archives found", options, 1)
        if choice == len(options):
            path = Path(self.ask("path to scan", self.config.output_dir)).expanduser()
        else:
            path = candidates[choice - 1]

        deep = self.confirm(
            "probe entries for nested archives (bounded decompression in memory)?", False
        )
        raw_ratio = self.ask("ratio threshold", str(int(detect.DEFAULT_MAX_RATIO)))
        raw_total = self.ask(
            "total size threshold",
            sizes.format_size(detect.DEFAULT_MAX_TOTAL).replace(" ", ""),
        )
        try:
            max_ratio = float(raw_ratio)
            max_total = sizes.parse_size(raw_total)
        except (ValueError, sizes.SizeError) as exc:
            ux.error(str(exc))
            return

        args = argparse.Namespace(
            paths=[str(path)],
            max_ratio=max_ratio,
            max_total=max_total,
            deep=deep,
            max_depth=None,
            probe_bytes=None,
            json=False,
        )
        exit_code = cmd_inspect(args)
        if exit_code == EXIT_SUSPICIOUS:
            ux.warn("treat this archive as hostile: do not extract it")

    def configure_flow(self) -> None:
        """Edit the remembered defaults."""
        ux = self.ux
        ux.title("configure defaults")
        cfg = self.config
        cfg.output_dir = self.ask("output directory", cfg.output_dir)
        keys = list(methods.METHODS)
        default = keys.index(cfg.method) + 1 if cfg.method in keys else 2
        cfg.method = keys[self.ask_choice("default method", keys, default) - 1]
        method_def = methods.METHODS[cfg.method]
        if method_def.supports_level:
            cfg.level = self.ask_int(
                "default level",
                cfg.level,
                method_def.min_level,
                method_def.max_level,
            )
        while True:
            value = self.ask("default size", cfg.size)
            try:
                sizes.parse_size(value)
            except sizes.SizeError as exc:
                ux.warn(str(exc))
                continue
            cfg.size = value
            break
        while True:
            value = self.ask("write buffer (chunk)", cfg.chunk)
            try:
                sizes.parse_size(value)
            except sizes.SizeError as exc:
                ux.warn(str(exc))
                continue
            cfg.chunk = value
            break
        cfg.split = self.ask("split size (blank for a single entry)", cfg.split)
        cfg.verify = self.ask_choice("verify after writing", ["none", "sample", "full"], 2)
        cfg.verify = ["none", "sample", "full"][cfg.verify - 1]
        cfg.progress = self.ask_choice(
            "output mode", ["auto", "ansi", "plain", "log", "none"], 1
        )
        cfg.progress = ["auto", "ansi", "plain", "log", "none"][cfg.progress - 1]
        cfg.confirm_before_write = self.confirm(
            "ask for confirmation before writing?", cfg.confirm_before_write
        )
        self.save_config()

    def policy_flow(self) -> None:
        """Show the limits and where they live."""
        ux = self.ux
        ux.title("safety policy")
        for line in policy.describe_limits():
            ux.write("  " + line)
        ux.write("")
        ux.field("python", f"{sys.version.split()[0]} ({'64' if not policy.is_32bit() else '32'} bit)")
        free = policy.disk_free(Path(self.config.output_dir))
        ux.field("free space", sizes.format_size(free) if free is not None else "unknown")

    def recipes_flow(self) -> None:
        """Model and optionally build one structural bomb recipe."""
        ux = self.ux
        ux.title("structural bomb recipes")
        families = [recipe for recipe in recipes.describe_recipes() if recipe.key != "flat"]
        labels = [f"{recipe.key} - {recipe.summary}" for recipe in families]
        choice = self.ask_choice("recipe", labels, 1)
        recipe = families[choice - 1]

        method, level = self._choose_method()
        target, size_text = self.ask_size("recursive expansion target", self.config.size)

        layers = fanout = entries = None
        if "fanout" in recipe.knobs:
            fanout = self.ask_int("fanout (copies per level)", recipes.DEFAULT_FANOUT, 1, recipes.MAX_FANOUT)
        if "layers" in recipe.knobs and self.confirm(
            "choose the nesting depth yourself (otherwise it is chosen for you)?", False
        ):
            layers = self.ask_int("layers", 4, 1, recipes.MAX_LAYERS)
        if "entries" in recipe.knobs:
            entries = self.ask_int("entries", recipe.default_entries, 1, policy.MAX_SPLITS)
        names = "plain"
        if "names" in recipe.knobs and self.confirm("disguise the entry names (mimic)?", False):
            names = "mimic"
        preamble = "none"
        if self.confirm("prepend a polyglot preamble (pdf/html/gif)?", False):
            preamble = ["pdf", "html", "gif"][
                self.ask_choice("preamble", ["pdf", "html", "gif"], 1) - 1
            ]

        try:
            with ux.spin("planning"):
                bomb = recipes.plan(recipe.key, target, method, level, layers, fanout, entries, names, preamble)
        except ValueError as exc:
            ux.error(str(exc))
            return

        print_plan(ux, bomb)
        suggested = str(
            Path(self.config.output_dir)
            / default_output_name(size_text, method, level, recipe.key)
        )
        output = Path(self.ask("output file", suggested)).expanduser()

        if output.exists() and not self.confirm(f"{output} exists - replace it?", False):
            ux.warn("kept the existing file; nothing was written")
            return
        try:
            warnings = policy.check_recipe(output, bomb, overwrite=True)
        except policy.PolicyError as exc:
            ux.error(str(exc))
            ux.detail("tip: option 2 models any size without writing anything")
            return
        for warning in warnings:
            ux.warn(warning)

        if self.config.confirm_before_write and not self.confirm("write the archive now?", True):
            ux.warn("cancelled")
            return

        ux.banner()
        try:
            with ux.spin("writing", enabled=not ux.is_ansi):
                result = recipes.build_bomb(output, bomb, ux=ux, verify=self.config.verify)
        except (FileExistsError, ValueError, OSError) as exc:
            ux.error(str(exc))
            return

        print_create_result(ux, result)
        _core_mod.append_audit(
            {
                "event": "created",
                "source": "panel",
                "recipe": result.recipe,
                "layers": result.layers,
                "fanout": result.fanout,
                "path": str(result.path),
                "declared_bytes": result.declared_bytes,
                "expanded_bytes": result.expanded_bytes,
                "archive_bytes": result.archive_bytes,
                "method": result.method,
                "level": result.level,
                "ratio": round(result.ratio, 2),
                "seconds": round(result.seconds, 2),
                "entries": result.entries,
            }
        )
        ux.ok(f"created {result.path}")

    def audit_flow(self) -> None:
        """Show the tail of the audit log."""
        ux = self.ux
        ux.title(f"audit log: {_core_mod.log_path()}")
        lines = _core_mod.read_audit(15)
        if not lines:
            ux.detail("nothing recorded yet")
            return
        for line in lines:
            ux.write("  " + line)


def panel_main(ux: UX | None = None, config_path: Path | None = None, plain: bool = False) -> int:
    """Run the control panel until the user leaves it."""
    ux = ux or UX("auto")
    return ControlPanel(ux, config_path=config_path, plain=plain).run()


# compat alias: ControlPanel was panel.Panel before the fold.
Panel = ControlPanel  # noqa: F401


__credit__ = "ZipBomb Lab - zipbomb_lab.cli - made by Xv @XvRendering https://github.com/MamadXV"
