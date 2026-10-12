# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Terminal capability detection used to choose between TUI and line mode.

A full-screen interface is only ever entered when *all* of the following hold:
stdout and stdin are real terminals, the stream can render the Unicode the lab
uses, and colours are not disabled. Everywhere else (pipes, CI, ``NO_COLOR``,
``TERM=dumb``) the caller stays in the classic line-based output.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass

__all__ = ["TerminalCaps", "detect_caps", "size"]

#: Glyphs the TUI relies on; a stream that cannot encode them gets line mode.
_PROBE = "\u2588\u2591\u256d\u256e\u2570\u256f\u2502\u2500\u00b7\u2713\u2717"


@dataclass(frozen=True)
class TerminalCaps:
    """A snapshot of what the current terminal can do."""

    width: int
    height: int
    stdin_tty: bool
    stdout_tty: bool
    unicode: bool
    colour: bool
    verbose: bool  # True when full interactive output is requested

    @property
    def can_tui(self) -> bool:
        """Whether the interactive application should be started."""
        return self.stdin_tty and self.stdout_tty and self.unicode and self.colour

    def as_dict(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "stdin_tty": self.stdin_tty,
            "stdout_tty": self.stdout_tty,
            "unicode": self.unicode,
            "colour": self.colour,
        }


def size(default: tuple[int, int] = (80, 24)) -> tuple[int, int]:
    """Terminal ``(columns, rows)`` with a sane fallback."""
    try:
        found = shutil.get_terminal_size()
        return max(int(found.columns), 20), max(int(found.lines), 8)
    except Exception:  # pragma: no cover - exotic streams
        return default


def _is_tty(stream) -> bool:
    try:
        return bool(stream.isatty())
    except Exception:  # pragma: no cover - closed/odd stream
        return False


def _stream_supports_unicode(stream) -> bool:
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        _PROBE.encode(encoding)
        return True
    except (LookupError, UnicodeEncodeError):
        return False


def detect_caps(stream=None) -> TerminalCaps:
    """Measure the current terminal without side effects."""
    stream = stream if stream is not None else sys.stdout
    width, height = size()
    colour = not os.environ.get("NO_COLOR") and os.environ.get("TERM") != "dumb"
    return TerminalCaps(
        width=width,
        height=height,
        stdin_tty=_is_tty(sys.stdin),
        stdout_tty=_is_tty(stream),
        unicode=_stream_supports_unicode(stream),
        colour=bool(colour),
        verbose=True,
    )


__credit__ = "ZipBomb Lab - zipbomb_lab.infrastructure.terminal - made by Xv @XvRendering https://github.com/MamadXV"
