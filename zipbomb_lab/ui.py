# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Presentation layer: theme + ux + branding.

"""

from __future__ import annotations


# -- theme --
"""Design tokens and premium widgets for the ZIP BOMB LAB CLI.

A single strict palette - **orange, white and gray only** - drives every
surface. All legacy colour names used across the toolkit (``green``,
``red``, ``amber``, ``ember``...) are remapped here onto palette-compliant
tokens, so old call sites stay on brand automatically.

Widgets in this module are rendered through a rich :class:`Console`. In
non-ANSI modes the caller falls back to plain text (see ``ux.UX``).
"""


from rich import box as rich_box
from rich.console import Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from .core import format_duration as _format_duration
from .core import format_size as _format_size

__all__ = [
    "PALETTE",
    "RICH_THEME",
    "style_name",
    "wordmark",
    "hero",
    "stat_cards",
    "menu_grid",
    "kv_card",
    "verdict_badge",
    "bar",
]

# --------------------------------------------------------------------------
# palette
# --------------------------------------------------------------------------

#: Hex tokens. Dark black, white, and orange - a focused premium palette.
PALETTE = {
    "orange": "#FF6B00",
    "orange_bright": "#FF8C33",
    "orange_deep": "#CC5500",
    "white": "#FFFFFF",
    "soft_white": "#E0E0E0",
    "gray": "#777777",
    "gray_dark": "#3A3A3A",
    "gray_light": "#B0B0B0",
}

#: Semantic roles mapped onto the palette. Legacy names included so every
#: existing ``ux.style(text, "green")`` call renders on brand.
_ROLE_TO_TOKEN = {
    "primary": "orange",
    "secondary": "orange_bright",
    "tertiary": "orange_deep",
    "title": "orange",
    "subtitle": "gray_light",
    "muted": "gray",
    "faint": "gray_dark",
    "value": "white",
    "label": "gray_light",
    "success": "orange_bright",
    "warning": "orange_bright",
    "error": "orange_deep",
    "danger": "orange_deep",
    "accent": "orange",
    "accent2": "orange_bright",
    # legacy names -> on-brand tokens
    "green": "orange_bright",
    "amber": "orange_bright",
    "ember": "orange_bright",
    "red": "orange_deep",
    "yellow": "orange_bright",
    "orange": "orange",
    "grey": "gray",
    "cyan": "orange_bright",
    "blue": "gray_light",
    "white": "white",
    "bold": "white",
}


def style_name(name: str) -> str:
    """Translate a palette/legacy name into a rich style string.

    Resolves against the *active* theme; while the default ``ember`` theme
    is active this is identical to the static :data:`PALETTE`.
    """
    token = _ROLE_TO_TOKEN.get(name, name)
    try:
        active = _ACTIVE
    except NameError:  # pragma: no cover - module still importing
        active = PALETTE
    return active.get(token, token)


#: rich theme registered in the console, enables ``[orange]``-style markup.
RICH_THEME = Theme(
    {
        name: PALETTE.get(token, token)
        for token in PALETTE
        for name in [token]
    }
    | {name: PALETTE[token] for name, token in _ROLE_TO_TOKEN.items()}
)


# --------------------------------------------------------------------------
# widgets
# --------------------------------------------------------------------------


def wordmark() -> Text:
    """Block-letter wordmark of the tool name, in the primary accent."""
    letters = {
        "Z": ["███╗ ", "╚═██╗", "  ██║", " ██╔╝", "╚██╝ "],
        "I": ["██╗ ", "██║ ", "██║ ", "██║ ", "██║ "],
        "P": ["███╗ ", "██╔═╝", "████║", "██╔═╝", "██║  "],
        " ": ["   ", "   ", "   ", "   ", "   "],
        "O": [" █████╗ ", "██╔═══╝ ", "███████╗", "██╔═══╝ ", " ╚████╔╝ "],
        "M": ["███╗   ███╗", "████╗ ████║", "██╔████╔██║", "██║╚██╔╝██║", "██║ ╚═╝ ██║"],
        "B": ["██████╗ ", "██╔══██╗", "██████╔╝", "██╔══██╗", "██████╔╝"],
        "A": [" █████╗ ", "██╔══██╗", "███████║", "██╔══██║", "██║  ██║"],
        "L": ["██╗     ", "██║     ", "██║     ", "██║     ", "███████╗"],
    }

    def glyph(ch: str) -> list[str]:
        if ch in letters:
            return letters[ch]
        if ch.islower():
            return letters.get(ch.upper(), ["   "] * 5)
        return ["   "] * 5

    name = "ZIP BOMB"
    rows: list[Text] = []
    for row in range(5):
        line = Text()
        for ch in name:
            line.append(glyph(ch)[row] + " ", style=style_name("orange"))
        rows.append(line)
    return Text("\n").join(rows)


def hero(
    ux,
    *,
    title: str | None = None,
    subtitle: str | None = None,
    tagline: str | None = None,
    made_by: str | None = None,
    contacts: list[tuple[str, str]] | None = None,
    footer: str | None = None,
) -> Panel:
    """The premium hero banner: wordmark left, identity card right.

    Below 100 columns the wordmark is dropped so the layout never wraps
    into an unreadable jumble.
    """
    from . import __version__
    # NOTE: branding was folded into this module; AUTHOR/GITHUB/TAGLINE/
    # TELEGRAM/TOOL are module-level names here, no import needed.
    _TAG = TAGLINE

    wide = True
    try:
        wide = ux.console.size.width >= 100
    except Exception:  # pragma: no cover - headless consoles
        wide = False

    left_rows: list = []
    if wide and not getattr(ux, "compact", False):
        left_rows.append(wordmark())
        left_rows.append(Text())
    left_rows.extend(
        [
            Text(
                f"{(title or TOOL)} v{__version__}",
                style="bold " + style_name("white"),
            ),
            Text(tagline or _TAG, style=style_name("gray")),
        ]
    )
    left = Group(*left_rows)

    right_rows = [
        Text("MADE BY", style=style_name("gray")),
        Text(AUTHOR, style="bold " + style_name("orange")),
        Text(),
        Text("TELEGRAM", style=style_name("gray")),
        Text(TELEGRAM, style=style_name("white")),
        Text(),
        Text("GITHUB", style=style_name("gray")),
        Text(GITHUB, style=style_name("white")),
    ]
    if contacts:
        right_rows.append(Text())
        for label, value in contacts:
            right_rows.append(Text(f"{label} {value}", style=style_name("gray")))
    right = Group(*right_rows)

    columns = Table.grid(padding=(0, 4))
    columns.add_column(ratio=3, justify="left")
    columns.add_column(ratio=2, justify="left")
    columns.add_row(left, right)

    return Panel(
        columns,
        border_style=style_name("orange"),
        box=rich_box.ROUNDED,
        padding=(0, 2),
        subtitle=Text(subtitle, style=style_name("gray")) if subtitle else None,
        subtitle_align="right",
    )


def stat_cards(
    cards: list[tuple[str, str, str | None]],
    *,
    key_style: str = "title",
    value_style: str = "value",
    note_style: str = "muted",
) -> Table:
    """A row of stat cards - bold label, big value, optional note.

    ``cards`` is a list of ``(label, value, note)`` triples.
    """
    grid = Table.grid(expand=True)
    per_card_cols = 3 if any(note for _, _, note in cards) else 2
    for _ in range(per_card_cols):
        grid.add_column(ratio=1)
    row = []
    for label, value, note in cards:
        lines = [
            Text(label.upper(), style=style_name(key_style)),
            Text(value, style="bold " + style_name(value_style)),
        ]
        if per_card_cols == 3:
            lines.append(Text(note or "", style=style_name(note_style)))
        row.append(Group(*lines))
    grid.add_row(*row)
    return grid


def menu_grid(
    items: list[tuple[str, str, str]],
    *,
    columns: int = 2,
    width: int | None = None,
    key_style: str = "orange",
    label_style: str = "white",
    hint_style: str = "gray",
) -> Table:
    """A premium command menu.

    Each entry is an orange key badge, a white label on a shared alignment
    column, and a right-aligned gray hint at the column edge. Two page
    columns with a wide gutter when the terminal allows it; a single clean
    column below 96 columns.

    ``items`` is a list of ``(key, label, hint)`` triples.
    """
    if width is None:
        width = 100
    if width < 96:
        columns = 1
    key_width = max((len(key) for key, _, _ in items), default=1)
    label_width = max((len(label) for _, label, _ in items), default=1)

    outer = Table.grid(expand=True)
    outer.add_column(width=2)  # left indent, matches the section titles
    outer.add_column(ratio=1)
    if columns == 2:
        outer.add_column(width=4)  # fixed gutter between the page columns
        outer.add_column(ratio=1)

    def _cell(key: str, label: str, hint: str):
        line = Text()
        line.append(key.ljust(key_width), style="bold " + style_name(key_style))
        line.append("  ")
        line.append(label.ljust(label_width), style=style_name(label_style))
        inner = Table.grid(expand=True)
        inner.add_column(no_wrap=True)
        inner.add_column(justify="right", no_wrap=True, style=style_name(hint_style))
        inner.add_row(line, Text(hint, style=style_name(hint_style)) if hint else Text())
        return inner

    rows = [items[index : index + columns] for index in range(0, len(items), columns)]
    for row in rows:
        cells = [_cell(key, label, hint) for key, label, hint in row]
        if columns == 2:
            while len(cells) < columns:
                cells.append(Text())
            outer.add_row(Text(), cells[0], Text(), cells[1])
        else:
            outer.add_row(Text(), cells[0])
    return outer


def kv_card(title: str, pairs: list[tuple[str, str]]) -> Panel:
    """A compact result card: title bar plus label/value rows."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style=style_name("label"), justify="right")
    grid.add_column(style=style_name("value"))
    for label, value in pairs:
        grid.add_row(label, Text(value))
    return Panel(
        grid,
        title=Text(title, style="bold " + style_name("orange")),
        border_style=style_name("gray_dark"),
        box=rich_box.ROUNDED,
        padding=(0, 1),
    )


def verdict_badge(text: str, *, positive: bool) -> Text:
    """A bracketed verdict badge: bright for clean, deep for hostile."""
    token = "success" if positive else "danger"
    return Text(f" {text} ", style="bold " + style_name(token))


def bar(fraction: float, width: int = 28) -> Text:
    """Palette meter: orange fill on dark gray track."""
    fraction = max(0.0, min(float(fraction), 1.0))
    filled = int(round(fraction * width))
    text = Text()
    text.append("█" * filled, style=style_name("orange"))
    text.append("░" * (width - filled), style=style_name("gray_dark"))
    return text


def duration(seconds: float) -> str:
    """Human duration, re-exported for widget callers."""
    return _format_duration(seconds)


def size(num_bytes: int) -> str:
    """Human size, re-exported for widget callers."""
    return _format_size(num_bytes)


# -- ux --
"""Terminal output helpers, powered by `rich`_ and the strict lab theme.

Every colour comes from the theme section of this module (orange / white / gray
only). Hand-written lines use true-color ANSI escapes generated from the
palette hexes, so redirected output stays byte-for-byte stable and no user
supplied text (file names, sizes) is ever parsed as markup. Rich-native
widgets (spinners, live bars, tables, panels) render through a themed
:class:`rich.console.Console`.

Output modes:

``ansi``   full rendering: colour, spinners, live progress, tables
``plain``  same layout, no colour, no live redraws
``log``    one line per progress step, ideal for redirects and log files
``none``   errors and warnings only

.. _rich: https://github.com/Textualize/rich
"""


import os
import sys
import time

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    ProgressColumn,
    Progress as RichProgress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from .core import format_duration as _format_duration
from .core import format_size as _format_size

__all__ = ["UX", "RichSpinner", "Progress", "resolve_mode", "format_duration"]

_MODES = ("ansi", "plain", "log", "none")

_RESET = "\x1b[0m"


def _ansi_hex(hex_color: str) -> str:
    """Convert ``#RRGGBB`` into a true-color ANSI escape."""
    value = hex_color.lstrip("#")
    red, green, blue = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    return f"\x1b[38;2;{red};{green};{blue}m"


#: Every palette token and semantic role (including legacy names) maps to a
#: true-color ANSI sequence derived from the theme hexes.
_STYLES = {
    "bold": "\x1b[1m",
    "dim": "\x1b[2m",
    "underline": "\x1b[4m",
    **{
        name: _ansi_hex(style_name(name))
        for name in (
            "orange",
            "orange_bright",
            "orange_deep",
            "white",
            "soft_white",
            "gray",
            "gray_dark",
            "gray_light",
            # semantic roles and legacy names
            "primary",
            "secondary",
            "tertiary",
            "title",
            "subtitle",
            "muted",
            "faint",
            "value",
            "label",
            "success",
            "warning",
            "error",
            "danger",
            "accent",
            "accent2",
            "green",
            "amber",
            "ember",
            "red",
            "yellow",
            "grey",
            "cyan",
            "blue",
        )
    },
}

_PRIMARY = "orange"
_SECONDARY = "orange_bright"
_MUTED = "gray"

#: Characters the premium widgets rely on (block letters, meters, box
#: borders, step marks). Streams whose encoding cannot represent them are
#: hardened to UTF-8 or downgraded to ``plain`` mode.
_GLYPH_PROBE = "\u2588\u2591\u256d\u256e\u2570\u256f\u2502\u2500\u00bb\u2713\u2717\u00b7"


def _glyph_safe(stream, mode: str) -> str:
    """Return a mode the stream can actually render.

    Piped output on legacy Windows uses codepages such as cp1252, which
    cannot encode the premium glyphs. Try to switch the stream to UTF-8;
    if that is impossible, fall back to ``plain`` (pure ASCII) output.
    """
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        _GLYPH_PROBE.encode(encoding)
        return mode
    except (LookupError, UnicodeEncodeError):
        pass
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8", errors="replace")
            return mode
        except Exception:  # pragma: no cover - exotic stream wrappers
            pass
    # The stream cannot be hardened; render the ASCII-perfect fallback.
    return "plain" if mode == "ansi" else mode


def _rich_style(name: str) -> str:
    """Translate a palette/legacy name into a rich style string."""
    return style_name(name)


def _enable_windows_vt(stream) -> bool:
    """Best effort enabling of ANSI escapes in the classic Windows console."""
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11 if stream is sys.stdout else -12)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        enable_vt = 0x0004
        return bool(kernel32.SetConsoleMode(handle, mode.value | enable_vt))
    except Exception:
        return False


def resolve_mode(requested: str | None) -> str:
    """Pick an output mode, honouring NO_COLOR / TERM / TTY detection."""
    if requested and requested != "auto":
        if requested not in _MODES:
            raise ValueError("unknown output mode %r" % (requested,))
        return requested
    if os.environ.get("NO_COLOR"):
        return "plain"
    if os.environ.get("TERM") == "dumb":
        return "plain"
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return "log"
    return "ansi" if _enable_windows_vt(sys.stdout) else "plain"


def format_duration(seconds: float) -> str:
    """Format a duration for estimates and ETAs.

    Thin re-export of :func:`zipbomb_lab.core.format_duration` so callers can
    import every presentation helper from this module.
    """
    return _format_duration(seconds)


class _BytesColumn(ProgressColumn):
    """Rich progress column showing completed / total bytes, human formatted."""

    def render(self, task) -> Text:
        text = f"{_format_size(int(task.completed))} / {_format_size(int(task.total))}"
        return Text(text, style=style_name("muted"))


class RichSpinner:
    """Context-manager spinner built on ``rich``'s live status line.

    Usable as a context manager::

        with ux.spin("calibrating") as spin:
            ...work...
            spin.update("halfway")
        # leaving the block prints the check-mark line
    """

    def __init__(self, ux: "UX", label: str, enabled: bool = True) -> None:
        self.ux = ux
        self.label = label
        self.enabled = enabled and ux.verbose
        self.detail = ""
        self.started = time.time()
        self._status = None

    def __enter__(self) -> "RichSpinner":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.finish(ok=True)
        elif exc_type is KeyboardInterrupt:
            self.finish(ok=None)
        else:
            self.finish(ok=False)

    def start(self) -> None:
        if not self.enabled:
            return
        if self.ux.mode == "ansi" and self.ux.console is not None:
            self._status = self.ux.console.status(
                Text(self.label, style="bold " + style_name("white")),
                spinner="dots",
                spinner_style=style_name("orange"),
            )
            self._status.start()
        elif self.ux.mode == "plain":
            self.ux.write(f"  {self.label} ...")

    def update(self, detail: str) -> None:
        """Change the sub-text shown after the label."""
        self.detail = detail
        if self._status is not None:
            text = f"{self.label} - {detail}" if detail else self.label
            self._status.update(Text(text, style="bold " + style_name("white")))

    def finish(self, ok: bool | None = True, detail: str = "") -> None:
        """Stop the animation and print the outcome line."""
        if self._status is not None:
            self._status.stop()
            self._status = None
        if not self.enabled:
            return
        elapsed = _format_duration(time.time() - self.started)
        suffix = f" ({elapsed})" if elapsed else ""
        text = f"{self.label}{suffix}"
        if ok is True:
            self.ux.step_ok(text)
        elif ok is False:
            self.ux.step_fail(text)
        else:
            self.ux.step_cancelled(text)


#: Backwards-compatible alias for the original spinner class name.
Spinner = RichSpinner


class UX:
    """Printer driven by the lab theme, with rich-native widgets.

    Hand-written lines go straight to the stream (true-color ANSI generated
    from the palette), while ``table``, ``panel``, ``hero`` and friends render
    through the themed rich :class:`Console`.
    """

    def __init__(self, mode: str = "auto", stream=None) -> None:
        self.mode = resolve_mode(mode)
        self.stream = stream if stream is not None else sys.stdout
        if self.mode == "ansi":
            self.mode = _glyph_safe(self.stream, self.mode)
        self.verbose = self.mode != "none"
        self.compact = False  # set by the CLI from --compact / saved config
        self.console = Console(
            file=self.stream,
            theme=RICH_THEME,
            highlight=False,
            emoji=False,
            # The legacy Windows renderer mishandles modern glyphs; our ANSI
            # mode is only entered after VT was confirmed available, so the
            # modern renderer is always the right choice here.
            legacy_windows=False,
        )

    # -- styling -----------------------------------------------------------
    @property
    def is_ansi(self) -> bool:
        """True when colours and live redraws are safe."""
        return self.mode == "ansi"

    def style(self, text: str, *styles: str) -> str:
        if self.mode != "ansi" or not styles:
            return text
        prefix = "".join(_STYLES.get(s, "") for s in styles)
        return f"{prefix}{text}{_RESET}"

    def accent(self, text: str) -> str:
        """Wrap *text* in the primary (orange) accent."""
        return self.style(text, _PRIMARY)

    def verdict(self, text: str, suspicious: bool) -> str:
        """Colour a scan verdict: deep orange for hostile, bright for clean."""
        return self.style(text, "bold", "danger" if suspicious else "success")

    def bar(self, fraction: float, width: int = 28) -> str:
        """A small inline meter: orange fill on a dark gray track."""
        fraction = max(0.0, min(float(fraction), 1.0))
        filled = int(round(fraction * width))
        if self.mode == "ansi":
            return self.style("█" * filled, _PRIMARY) + self.style(
                "░" * (width - filled), "faint"
            )
        return "[" + "#" * filled + "-" * (width - filled) + "]"

    # -- writing -----------------------------------------------------------
    def write(self, text: str = "") -> None:
        if not self.verbose:
            return
        try:
            self.stream.write(text + "\n")
            self.stream.flush()
        except Exception:  # pragma: no cover - closed stream / broken pipe
            pass

    def info(self, text: str = "") -> None:
        self.write(text)

    def detail(self, text: str) -> None:
        self.write("  " + self.style(text, _MUTED))

    def bullet(self, text: str) -> None:
        mark = "·" if self.is_ansi else "-"
        self.write("  " + self.style(mark, _SECONDARY) + " " + text)

    def ok(self, text: str) -> None:
        self.write(self.style("[ok] ", "success") + text)

    def warn(self, text: str) -> None:
        self.write(self.style("[warn] ", "warning") + text)

    def error(self, text: str) -> None:
        self.write(self.style("[error] ", "danger") + text)

    def title(self, text: str) -> None:
        self.write(self.style(text, "bold", _PRIMARY))

    def header(self, text: str, subtitle: str | None = None) -> None:
        """A section header: blank line, an accented title, optional subtitle."""
        if not getattr(self, "compact", False):
            self.write("")
        self.write(self.style("» " + text, "bold", _PRIMARY))
        if subtitle:
            self.write("  " + self.style(subtitle, "subtitle"))

    def rule(self, char: str = "-", width: int = 68) -> None:
        self.write(self.style(char * width, "faint"))

    def field(self, label: str, value: str) -> None:
        self.write(
            f"  {self.style(f'{label:<22}', 'label')}{self.style(value, 'value')}"
        )

    def hrule(self) -> None:
        """A rich full-width rule (ansi mode); a plain rule elsewhere."""
        if self.mode == "ansi" and self.console is not None:
            self.console.print(Rule(style=style_name("gray_dark")))
        else:
            self.rule()

    # -- rich-native widgets (ansi mode) ------------------------------------
    def table(
        self,
        headers: list[str],
        rows: list[list[str]],
        column_styles: list[str | None] | None = None,
    ) -> None:
        """Render a themed rich table in ``ansi`` mode; aligned text otherwise."""
        if self.mode != "ansi" or self.console is None:
            self.write(
                "  " + self.style("".join(f"{h:<18}" for h in headers), "bold")
            )
            for row in rows:
                self.write("  " + "".join(f"{cell:<18}" for cell in row))
            return
        table = Table(
            box=box.SIMPLE_HEAD,
            padding=(0, 1),
            border_style=style_name("gray_dark"),
            header_style="bold " + style_name("white"),
        )
        for index, header in enumerate(headers):
            style_name = (
                column_styles[index] if column_styles and index < len(column_styles) else None
            )
            table.add_column(
                Text(header, style=style_name(style_name) if style_name else "")
            )
        for row in rows:
            cells = []
            for index, cell in enumerate(row):
                style_name = (
                    column_styles[index] if column_styles and index < len(column_styles) else None
                )
                cells.append(
                    Text(str(cell), style=style_name(style_name) if style_name else "")
                )
            table.add_row(*cells)
        self.console.print(table)

    def panel(self, text: str, title: str | None = None) -> None:
        """A rounded themed panel in ``ansi`` mode; a ruled block otherwise."""
        if self.mode != "ansi" or self.console is None:
            self.rule("=")
            for line in text.splitlines():
                self.write(f"  {line}")
            self.rule("=")
            return
        self.console.print(
            Panel(
                Text(text),
                title=Text(title, style="bold " + style_name("orange"))
                if title
                else None,
                border_style=style_name("gray_dark"),
                box=box.ROUNDED,
            )
        )

    def banner(self) -> None:
        """Printed before every real archive write."""
        self.rule("=")
        self.write(
            self.style(
                " ZIP BOMB LAB - this writes a real compression bomb", "bold", "warning"
            )
        )
        self.write("  Use it only on a machine you own, in an isolated VM or container,")
        self.write("  with disk quotas. Never upload, share or ship the artifacts, and")
        self.write("  never extract one on a system you care about. Antivirus software")
        self.write("  may quarantine the output; that is expected behaviour.")
        self.rule("=")

    # -- agent-style steps ----------------------------------------------
    def step_ok(self, text: str) -> None:
        """A completed pipeline step, marked with a check mark."""
        mark = self.style("✓", "success", "bold") if self.is_ansi else "+"
        self.write(f"  {mark} {text}")

    def step_fail(self, text: str) -> None:
        """A failed step, marked with a cross."""
        mark = self.style("✗", "danger", "bold") if self.is_ansi else "x"
        self.write(f"  {mark} {text}")

    def step_cancelled(self, text: str) -> None:
        """A step the user interrupted, marked with a dash."""
        mark = self.style("–", "muted", "bold") if self.is_ansi else "-"
        self.write(f"  {mark} {text}")

    # -- spinner ----------------------------------------------------------
    def spin(self, label: str, enabled: bool = True) -> RichSpinner:
        """Create a :class:`RichSpinner` bound to this printer."""
        return RichSpinner(self, label, enabled=enabled)


class Progress:
    """Byte-count progress reporter with ETA, backed by rich when live.

    ``ansi`` renders a themed bar (orange spinner and fill, gray track, white
    label); ``log`` prints a line every ``log_every`` seconds; ``plain`` and
    ``none`` stay quiet apart from the closing summary.
    """

    WIDTH = 88

    def __init__(
        self,
        total: int,
        ux: UX,
        label: str = "writing",
        enabled: bool = True,
        log_every: float = 5.0,
    ) -> None:
        self.total = max(int(total), 1)
        self.ux = ux
        self.label = label
        self.enabled = enabled and ux.mode != "none"
        self.log_every = log_every
        self.written = 0
        self.started = time.time()
        self._last_log = self.started
        self._last_render = 0.0
        self._rendered_line = False
        self._rich: RichProgress | None = None
        self._task_id = None
        if self.enabled and ux.mode == "ansi" and ux.console is not None:
            self._rich = RichProgress(
                SpinnerColumn(style=style_name("orange")),
                TextColumn("[bold]{task.description}"),
                BarColumn(
                    bar_width=24,
                    style=style_name("gray_dark"),
                    complete_style=style_name("orange"),
                    finished_style=style_name("orange"),
                ),
                TaskProgressColumn(),
                _BytesColumn(),
                TransferSpeedColumn(),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=ux.console,
                auto_refresh=True,
            )
            self._rich.start()
            self._task_id = self._rich.add_task(self.label, total=self.total)

    @property
    def elapsed(self) -> float:
        return max(time.time() - self.started, 1e-9)

    @property
    def speed(self) -> float:
        return self.written / self.elapsed

    @property
    def fraction(self) -> float:
        return min(self.written / self.total, 1.0)

    def _eta_text(self) -> str:
        remaining = max(self.total - self.written, 0)
        speed = self.speed
        eta = remaining / speed if speed > 0 else float("inf")
        return "?" if eta == float("inf") else format_duration(eta)

    def stats(self) -> str:
        """Plain one-line summary, used for ``log`` mode and the close message."""
        from .core import format_speed

        return (
            f"{self.fraction * 100:6.2f}%  {format_size(self.written)} / "
            f"{format_size(self.total)}  {format_speed(self.speed)}  eta {self._eta_text()}"
        )

    def render(self) -> str:
        """The coloured, bar-style line used for non-rich live redraws."""
        from .core import format_speed

        meter = self.ux.bar(self.fraction, width=24)
        label = self.ux.style(self.label, "warning")
        percent = self.ux.style(f"{self.fraction * 100:5.1f}%", "bold", _PRIMARY)
        return (
            f"{label} {meter} {percent} "
            f"{format_size(self.written)} / {format_size(self.total)} "
            f"{format_speed(self.speed)} eta {self._eta_text()}"
        )

    def advance(self, count: int) -> None:
        self.written += count
        if not self.enabled:
            return
        if self._rich is not None and self._task_id is not None:
            self._rich.update(self._task_id, completed=self.written)
            return
        now = time.time()
        if self.ux.mode == "ansi":
            if now - self._last_render < 0.1 and self.written < self.total:
                return
            self._last_render = now
            try:
                self.ux.stream.write(f"\r{self.render()}")
                self.ux.stream.flush()
            except Exception:  # pragma: no cover
                pass
            self._rendered_line = True
        elif self.ux.mode == "log" and now - self._last_log >= self.log_every:
            self._last_log = now
            self.ux.write(f"{self.label}: {self.stats()}")

    def close(self) -> None:
        if not self.enabled:
            return
        if self._rich is not None:
            self._rich.stop()
            self._rich = None
            return
        if self.ux.mode == "ansi":
            if self._rendered_line:
                try:
                    self.ux.stream.write("\r" + " " * self.WIDTH + "\r")
                    self.ux.stream.flush()
                except Exception:  # pragma: no cover
                    pass
        elif self.ux.mode == "log":
            self.ux.write(f"{self.label}: {self.stats()}")


# -- branding --
"""Branding and watermark.


Rendering degrades with the output mode: the rich hero panel in ANSI
terminals, ASCII frames in ``plain``/``log``, nothing in ``none``.
"""


from rich.rule import Rule
from rich.text import Text

from . import __version__

__all__ = [
    "AUTHOR",
    "TELEGRAM",
    "GITHUB",
    "WATERMARK",
    "PROG",
    "TAGLINE",
    "TOOL",
    "watermark_line",
    "brand_footer",
    "welcome_box",
    "brand_panel",
]

AUTHOR = "Xv"
TELEGRAM = "@XvRendering"
GITHUB = "https://github.com/MamadXV"
TOOL = "ZIP BOMB LAB"
TAGLINE = "build, measure and detect compression bombs"

#: Console command name (must match [project.scripts] in pyproject.toml).
PROG = "zbomb"

#: One-line footer shown after command output.
WATERMARK = f"made by {AUTHOR} - {TELEGRAM} - {GITHUB}"


def watermark_line(ux: UX) -> str:
    """The watermark, muted so it does not fight the content."""
    return ux.style(WATERMARK, "gray")


def brand_footer(ux: UX) -> None:
    """The watermark footer, drawn after command output.

    A rich rule in ANSI mode; a plain muted line elsewhere. Skipped in
    ``none`` mode so ``--quiet`` / ``--json`` streams stay byte-for-byte clean.
    """
    if not ux.verbose:
        return
    if ux.is_ansi and ux.console is not None:
        ux.console.print(
            Rule(Text(" " + WATERMARK, style=style_name("gray")), style=style_name("gray_dark"))
        )
        return
    ux.write("")
    ux.write(watermark_line(ux))


def brand_panel(ux: UX) -> None:
    """The compact branded hero, used by the panel and long-running flows."""
    if ux.is_ansi and ux.console is not None:
        ux.console.print(hero(ux))
        return
    welcome_box(ux)


def welcome_box(ux: UX) -> list[str]:
    """Render the branded welcome banner and print it; returns the plain lines.

    The rich hero panel in ANSI mode; an ASCII frame elsewhere so redirected
    output stays byte-for-byte safe.
    """
    inner = [
        f"{TOOL} v{__version__}",
        TAGLINE,
        "",
        f"made by {AUTHOR}",
        f"telegram {TELEGRAM}",
        f"github  {GITHUB}",
    ]
    if ux.is_ansi and ux.console is not None:
        ux.console.print(hero(ux))
        return inner
    width = max((len(line) for line in inner), default=0)
    frame = "+" + "-" * (width + 2) + "+"
    body = ["| " + text.ljust(width) + " |" for text in inner]
    for line in [frame, *body, frame]:
        ux.write(line)
    return inner

__all__ = ['AUTHOR', 'GITHUB', 'PALETTE', 'Progress', 'RICH_THEME', 'RichSpinner', 'TAGLINE', 'TELEGRAM', 'TOOL', 'UX', 'WATERMARK', 'bar', 'brand_footer', 'brand_panel', 'format_duration', 'hero', 'kv_card', 'menu_grid', 'resolve_mode', 'stat_cards', 'style_name', 'verdict_badge', 'watermark_line', 'welcome_box', 'wordmark']

# --- backward-compat: old module paths share this module object ---
import sys as _sys_compat3
for _alias in ("theme", "branding", "ux"):
    _sys_compat3.modules.setdefault(f"{__name__.rsplit('.', 1)[0]}.{_alias}", _sys_compat3.modules[__name__])
del _sys_compat3


# ======================================================================
# showcase widgets (redesign): suggestions, sections, arrow-key Selector
# ======================================================================
"""Showcase widgets appended during the CLI redesign (no legacy output changed)."""
import difflib as _difflib
import re as _re
import sys as _sys


def did_you_mean(word, options, n=3, cutoff=0.6):
    """Closest matches of *word* inside *options* (for typo suggestions)."""
    return _difflib.get_close_matches(str(word), [str(o) for o in options], n=n, cutoff=cutoff)


def section(ux, icon, title, subtitle=None):
    """A section header: icon + bold title + dim subtitle (keeps the » style)."""
    if not getattr(ux, "compact", False):
        ux.write("")
    ux.write(ux.style(f"{icon} {title}", "bold", "orange"))
    if subtitle:
        ux.write("  " + ux.style(subtitle, "gray"))


def hint(ux, text):
    """A dim tip line."""
    ux.write("  " + ux.style(text, "gray"))


def tip(ux, text):
    """A highlighted tip line (keeps the 'tip:' prefix tests rely on)."""
    ux.detail(f"tip: {text}")


def error_card(ux, message, suggestions=()):
    """An error plus optional 'did you mean …' suggestions and next steps."""
    ux.error(message)
    for sug in suggestions:
        ux.detail(f"did you mean '{sug}'?")
    if suggestions:
        ux.detail(f"run '{PROG} <command> --help' for options and examples")


class Selector:
    """Arrow-key option picker with a numbered-list fallback.

    * On a real terminal (ANSI + TTY on stdin/stdout) the user moves with
      Up/Down (or j/k), jumps with number keys and confirms with Enter.
    * Everywhere else — pipes, CI, tests, ``--plain`` — it prints the same
      numbered list the panel always used and reads a number with ``input()``,
      so scripts and mocked stdin keep working byte-for-byte.
    """

    def __init__(self, ux, prompt="select", input_fn=None):
        self.ux = ux
        self.prompt = prompt
        self.input_fn = input_fn

    # -- capability probe -------------------------------------------------
    def _interactive(self):
        try:
            stdin_tty = _sys.stdin.isatty()
        except Exception:
            stdin_tty = False
        try:
            stdout_tty = _sys.stdout.isatty()
        except Exception:
            stdout_tty = False
        try:
            stream_tty = self.ux.stream.isatty()
        except Exception:
            stream_tty = False
        return bool(
            self.ux.is_ansi and stdin_tty and stdout_tty and stream_tty
            and self.input_fn is None
        )

    # -- public API --------------------------------------------------------
    def ask(self, options, default=1):
        """Return the 1-based index chosen from *options* (list of str)."""
        options = [str(o) for o in options]
        default = max(1, min(int(default or 1), len(options)))
        if not self._interactive():
            return self._fallback(options, default)
        try:
            return self._arrow(options, default)
        except Exception:
            return self._fallback(options, default)

    # -- fallback: classic numbered list ----------------------------------
    def _fallback(self, options, default):
        ux = self.ux
        ux.write(f"  {self.prompt}")
        for index, option in enumerate(options, start=1):
            marker = " (default)" if index == default else ""
            prefix = ux.style(f"{index:>2})", "bold", "orange")
            ux.write(f"    {prefix} {option}{marker}")
        read = self.input_fn or input
        while True:
            try:
                ux.stream.write(f"  {self.prompt} [{default}]: ")
                ux.stream.flush()
            except Exception:
                pass
            try:
                answer = (read() or "").strip() or str(default)
            except (EOFError, StopIteration):
                return default
            try:
                choice = int(answer)
            except ValueError:
                ux.warn("please enter a number from the list")
                continue
            if 1 <= choice <= len(options):
                return choice
            ux.warn(f"choose between 1 and {len(options)}")

    # -- interactive: in-place arrow picker --------------------------------
    def _arrow(self, options, default):
        """Arrow-key picker; any failure falls back to the numbered list."""
        return _arrow_pick(self.ux, self.prompt, options, default)

    def _read_key_windows(self):
        import msvcrt

        first = msvcrt.getwch()
        if first in ("\x00", "\xe0"):
            second = msvcrt.getwch()
            return {"H": "up", "P": "down", "K": "left", "M": "right"}.get(second, "")
        if first in ("\r", "\n"):
            return "enter"
        if first == "\x1b":
            return "esc"
        if first == "\x03":
            raise KeyboardInterrupt
        return first

    def _read_key_posix(self):
        import termios
        import tty

        fd = _sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            first = _sys.stdin.read(1)
            if first == "\x1b":
                second = _sys.stdin.read(1)
                if second == "[":
                    third = _sys.stdin.read(1)
                    return {"A": "up", "B": "down", "C": "right", "D": "left"}.get(third, "esc")
                return "esc"
            if first in ("\r", "\n"):
                return "enter"
            if first == "\x03":
                raise KeyboardInterrupt
            return first
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _term_size():
    """Terminal (columns, rows) with a sane fallback."""
    import shutil

    try:
        size = shutil.get_terminal_size()
        return max(int(size.columns), 20), max(int(size.lines), 10)
    except Exception:
        return 80, 24


def clear_screen(ux):
    """Blank the whole terminal window (interactive sessions only)."""
    if not ux.is_ansi:
        return
    try:
        ux.stream.write("\x1b[2J\x1b[3J\x1b[H")
        ux.stream.flush()
    except Exception:
        pass


def paint_black(ux):
    """Flood the visible window with black so the panel sits on black."""
    if not ux.is_ansi:
        return
    try:
        cols, rows = _term_size()
        ux.stream.write("\x1b[40m" + "\n".join([" " * cols] * rows) + "\x1b[H")
        ux.stream.flush()
    except Exception:
        pass


def reset_screen(ux):
    """Restore default attributes, cursor color and cursor. Always safe."""
    try:
        ux.stream.write("\x1b[0m\x1b[?25h\x1b]112\x07")
        ux.stream.flush()
    except Exception:
        pass


def _arrow_pick(ux, prompt, options, default):
    """In-place arrow picker; returns the 1-based index.

    The block is redrawn in place: the cursor moves up exactly N-1 lines,
    every row is cleared and rewritten full-width (plain text is truncated
    *before* styling, so escape codes are never sliced), and the block is
    erased on confirm. Cursor and attributes are restored even on Ctrl+C.
    """
    sel = Selector(ux, prompt)
    if _sys.platform == "win32":
        read_key = sel._read_key_windows
    else:
        read_key = sel._read_key_posix
    index = max(0, min(int(default or 1) - 1, len(options) - 1))
    stream = ux.stream
    selected = None
    drawn = 0
    try:
        try:
            stream.write("\x1b[?25l")
            stream.flush()
        except Exception:
            pass
        first = True
        while True:
            cols, _rows = _term_size()
            width = max(cols - 1, 1)
            rows = ["  %s  (up/down + Enter)" % prompt]
            for i, option in enumerate(options):
                marker = ">" if i == index else " "
                rows.append("  %s %d) %s" % (marker, i + 1, option))
            plain = [row[:width].ljust(width) for row in rows]
            lines = ["\x1b[40m" + plain[0] + "\x1b[0m"]
            for i, row in enumerate(plain[1:]):
                if i == index:
                    lines.append("\x1b[40m" + ux.style(row, "bold", "orange"))
                else:
                    lines.append("\x1b[40m" + ux.style(row, "gray"))
            try:
                if not first:
                    stream.write("\x1b[%dA\r" % (len(lines) - 1))
                stream.write("\r\x1b[2K" + "\n\r\x1b[2K".join(lines))
                stream.flush()
            except Exception:
                pass
            first = False
            drawn = len(lines)
            key = read_key()
            if key == "up" or key == "k":
                index = (index - 1) % len(options)
            elif key == "down" or key == "j":
                index = (index + 1) % len(options)
            elif key == "enter":
                selected = index
                break
            elif key == "esc":
                selected = index
                break
            elif isinstance(key, str) and key.isdigit():
                n = int(key)
                if 1 <= n <= len(options):
                    selected = n - 1
                    break
        # Erase the block: back to its first row, clear everything below to
        # black (the picker always lives at the bottom, so this is safe).
        try:
            stream.write("\x1b[%dA\r\x1b[40m\x1b[J\x1b[0m" % (len(lines) - 1))
            stream.flush()
        except Exception:
            pass
        cols, _rows = _term_size()
        tail = ("  %s: %s" % (prompt, options[selected]))[: max(cols - 1, 1)]
        ux.write("\x1b[40m" + ux.style(tail, "bold", "orange"))
        return selected + 1
    finally:
        if selected is None and drawn:
            # Aborted (Ctrl+C): wipe the stale block so no ghosts remain.
            try:
                stream.write("\x1b[%dA\r\x1b[40m\x1b[J\x1b[0m" % (drawn - 1))
                stream.flush()
            except Exception:
                pass
        try:
            stream.write("\x1b[?25h")
            stream.flush()
        except Exception:
            pass


# Extend exports with the showcase + screen helpers.
try:
    __all__ = sorted(
        set(__all__)
        | {
            "Selector", "did_you_mean", "section", "hint", "tip", "error_card",
            "clear_screen", "paint_black", "reset_screen",
            "THEMES", "THEME_NAMES", "DEFAULT_THEME", "active_theme_name",
            "active_theme", "set_theme", "theme_swatch", "cursor_color",
            "block", "status_line", "shortcuts_bar", "diamond",
        }
    )
except NameError:
    __all__ = [
        "Selector", "did_you_mean", "section", "hint", "tip", "error_card",
        "clear_screen", "paint_black", "reset_screen",
        "THEMES", "THEME_NAMES", "DEFAULT_THEME", "active_theme_name",
        "active_theme", "set_theme", "theme_swatch", "cursor_color",
        "block", "status_line", "shortcuts_bar", "diamond",
    ]


# ======================================================================
# Theme engine: named themes with live switching (grok-build inspired,
# original palettes). Token *names* stay stable so every existing widget
# keeps working; only the hex behind each token changes.
# ======================================================================

#: The theme used when nothing else is requested. PALETTE always describes
#: this theme, so the brand contract never drifts.
DEFAULT_THEME = "ember"

#: Registry of named themes. Each theme fills the same eight token slots:
#: primary / bright / deep accents, text / soft text, muted / faint / subtle
#: grays. ``paints_background`` decides whether full-screen surfaces may
#: flood the canvas (the ``terminal`` theme respects the user's own canvas).
THEMES = {
    "ember": {
        "label": "Ember",
        "description": "Dark black, white and orange - clean premium look. Default.",
        "dark": True,
        "paints_background": True,
        "cursor": "#FF6B00",
        "tokens": {
            "orange": "#FF6B00",
            "orange_bright": "#FF8C33",
            "orange_deep": "#CC5500",
            "white": "#FFFFFF",
            "soft_white": "#E0E0E0",
            "gray": "#777777",
            "gray_dark": "#3A3A3A",
            "gray_light": "#B0B0B0",
        },
    },
    "tokyo": {
        "label": "Tokyo",
        "description": "Cool blue-tinted dark. Needs truecolor to shine.",
        "dark": True,
        "paints_background": True,
        "cursor": "#7AA2F7",
        "tokens": {
            "orange": "#7AA2F7",
            "orange_bright": "#9ECBFF",
            "orange_deep": "#F7768E",
            "white": "#C0CAF5",
            "soft_white": "#A9B1D6",
            "gray": "#565F89",
            "gray_dark": "#24283B",
            "gray_light": "#9AA0B8",
        },
    },
    "rose": {
        "label": "Rose",
        "description": "Muted dark with mauve accents.",
        "dark": True,
        "paints_background": True,
        "cursor": "#C4A7E7",
        "tokens": {
            "orange": "#C4A7E7",
            "orange_bright": "#E5D9FB",
            "orange_deep": "#EB6F92",
            "white": "#E0DEF4",
            "soft_white": "#CFC9E8",
            "gray": "#6E6A86",
            "gray_dark": "#26233A",
            "gray_light": "#908CAA",
        },
    },
    "midnight": {
        "label": "Midnight",
        "description": "Deep dark base with violet accents.",
        "dark": True,
        "paints_background": True,
        "cursor": "#A78BFA",
        "tokens": {
            "orange": "#A78BFA",
            "orange_bright": "#C4B5FD",
            "orange_deep": "#F472B6",
            "white": "#EDEDF2",
            "soft_white": "#C9C9D6",
            "gray": "#63636E",
            "gray_dark": "#1C1C24",
            "gray_light": "#9C9CA8",
        },
    },
    "day": {
        "label": "Day",
        "description": "Light theme for bright terminal backgrounds.",
        "dark": False,
        "paints_background": False,
        "cursor": "#C2410C",
        "tokens": {
            "orange": "#C2410C",
            "orange_bright": "#047857",
            "orange_deep": "#B91C1C",
            "white": "#18181B",
            "soft_white": "#3F3F46",
            "gray": "#71717A",
            "gray_dark": "#E4E4E7",
            "gray_light": "#52525B",
        },
    },
    "terminal": {
        "label": "Terminal",
        "description": "Your terminal's own colors - no canvas of its own.",
        "dark": True,
        "paints_background": False,
        "cursor": "#FFFFFF",
        "tokens": {
            "orange": "#E8E8E8",
            "orange_bright": "#FFFFFF",
            "orange_deep": "#FF8080",
            "white": "#E8E8E8",
            "soft_white": "#C8C8C8",
            "gray": "#808080",
            "gray_dark": "#404040",
            "gray_light": "#A8A8A8",
        },
    },
}

THEME_NAMES = tuple(THEMES)

#: Live hexes behind each token. Starts as ember; ``set_theme`` swaps these
#: in place so every widget follows without re-imports. PALETTE itself is
#: never mutated, so the brand contract stays intact.
_ACTIVE = dict(THEMES[DEFAULT_THEME]["tokens"])

#: Name of the currently active theme.
_ACTIVE_NAME = DEFAULT_THEME


def active_theme_name() -> str:
    """Name of the currently active theme."""
    return _ACTIVE_NAME


def active_theme() -> dict:
    """Registry entry of the currently active theme."""
    return THEMES[_ACTIVE_NAME]


def _refresh_caches() -> None:
    """Rebuild every derived color cache from the active theme."""
    RICH_THEME.styles.clear()
    RICH_THEME.styles.update(
        {name: _ACTIVE.get(token, token) for token in _ACTIVE for name in [token]}
        | {name: _ACTIVE[token] for name, token in _ROLE_TO_TOKEN.items()}
    )
    for name in (
        "orange", "orange_bright", "orange_deep", "white", "soft_white",
        "gray", "gray_dark", "gray_light", "primary", "secondary", "tertiary",
        "title", "subtitle", "muted", "faint", "value", "label", "success",
        "warning", "error", "danger", "accent", "accent2", "green", "amber",
        "ember", "red", "yellow", "grey", "cyan", "blue",
    ):
        _STYLES[name] = _ansi_hex(_active_style(name))


def _active_style(name: str) -> str:
    """Resolve a token/role against the active theme (no legacy fallback)."""
    token = _ROLE_TO_TOKEN.get(name, name)
    return _ACTIVE.get(token, token)


def set_theme(name: str) -> str:
    """Activate a named theme, refreshing all caches. Returns previous name.

    Raises :class:`ValueError` with a suggestion when the name is unknown.
    """
    global _ACTIVE_NAME
    key = str(name or "").strip().lower()
    if key not in THEMES:
        suggestions = did_you_mean(key, THEME_NAMES)
        hint_text = f" - did you mean '{suggestions[0]}'?" if suggestions else ""
        raise ValueError(
            f"unknown theme {name!r}{hint_text} - choose one of: {', '.join(THEME_NAMES)}"
        )
    previous = _ACTIVE_NAME
    if key != previous:
        _ACTIVE_NAME = key
        _ACTIVE.clear()
        _ACTIVE.update(THEMES[key]["tokens"])
        _refresh_caches()
    return previous


def theme_swatch(name: str) -> Text:
    """A color swatch for a theme, rendered without switching themes."""
    entry = THEMES[str(name or "").strip().lower()]
    return Text("█████", style=entry["tokens"]["orange"])


def cursor_color(ux: UX) -> None:
    """Tint the terminal cursor to the theme accent (OSC 12, best effort)."""
    if not ux.is_ansi:
        return
    try:
        accent = THEMES[_ACTIVE_NAME].get("cursor") or _ACTIVE.get("orange", "#FFFFFF")
        ux.stream.write(f"\x1b]12;{accent}\x07")
        ux.stream.flush()
    except Exception:
        pass


# ======================================================================
# Premium blocks: accent-bordered groups, status row, shortcuts bar.
# (grok-build inspired layout language, original implementation.)
# ANSI-only renderers; silent in plain/log/none so scripts never change.
# ======================================================================

#: Glyph for the accent rail on blocks. Falls back to "|" where legacy
#: Windows consoles cannot render it (mirrors the _glyph_safe hardening).
_ACCENT_RAIL = "❙"


def block(ux: UX, title: str, lines: list[str], accent: str = "primary") -> None:
    """A scrollback-style block: accent rail + bold title + body lines.

    Used for verdicts, previews and grouped results. Plain modes get the
    same ruled-block shape as :meth:`UX.panel` so text stays identical.
    """
    if not ux.is_ansi or ux.console is None:
        ux.panel("\n".join([title, *lines]))
        return
    rail = _ACCENT_RAIL
    try:
        rail.encode(getattr(ux.stream, "encoding", None) or "utf-8")
    except (LookupError, UnicodeEncodeError):
        rail = "|"
    ux.write("  " + ux.style(f"{rail} {title}", "bold", accent))
    for line in lines:
        text = str(line)
        if text.strip():
            ux.write("  " + ux.style(f"{rail} ", "faint") + text)
        else:
            ux.write("  " + ux.style(rail, "faint"))


def status_line(ux: UX, segments: list[str]) -> None:
    """Bottom status row: dim ``seg │ seg │ seg`` segments, full width.

    ANSI-only; a no-op everywhere else so machine output never changes.
    """
    if not ux.is_ansi:
        return
    try:
        cols, _ = _term_size()
    except Exception:  # pragma: no cover - defensive
        cols = 80
    sep = ux.style(" │ ", "faint")
    row = sep.join(ux.style(seg, "muted") for seg in segments if seg)
    # Strip ANSI to measure, then truncate the plain text if needed.
    plain_len = len(_re.sub(r"\x1b\[[0-9;]*m", "", row))
    if plain_len > cols:
        text = (" │ ".join(s for s in segments if s))[: max(cols - 1, 1)]
        row = ux.style(text, "muted")
    ux.write(row)


def shortcuts_bar(ux: UX, items: list[tuple[str, str]]) -> None:
    """Bottom shortcuts bar: ``key label · key label`` in dim tones.

    ANSI-only; a no-op everywhere else.
    """
    if not ux.is_ansi:
        return
    sep = ux.style(" · ", "faint")
    parts = [
        ux.style(key, "bold", "secondary") + " " + ux.style(label, "muted")
        for key, label in items
    ]
    ux.write(sep.join(parts))


def diamond(ux: UX, text: str) -> None:
    """A pipeline step header marked with an accent diamond (◆)."""
    mark = "◆" if ux.is_ansi else "+"
    ux.write("  " + ux.style(mark, "accent", "bold") + " " + text)


__credit__ = "ZipBomb Lab - zipbomb_lab.ui - made by Xv @XvRendering https://github.com/MamadXV"
