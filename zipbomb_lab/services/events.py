# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Structured events emitted by long-running operations.

The domain and services never import a widget: they publish these immutable
events, and whoever is listening (the classic printer, the TUI, a test) decides
how to show them. Progress is always *real* — every
:class:`ArchiveProgressEvent` is a genuine byte count.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable

__all__ = [
    "ArchiveEvent",
    "ArchivePlannedEvent",
    "ArchiveStartedEvent",
    "ArchiveProgressEvent",
    "ArchiveWarningEvent",
    "ArchiveCompletedEvent",
    "ArchiveFailedEvent",
    "ScanCompletedEvent",
    "EventBus",
]


@dataclass(frozen=True)
class ArchiveEvent:
    """Base class for everything the archive service publishes."""

    job_label: str = ""


@dataclass(frozen=True)
class ArchivePlannedEvent(ArchiveEvent):
    """A plan was modelled (nothing written yet)."""

    recipe: str = "flat"
    method: str = "deflate"
    output_bytes: int = 0
    ratio: float = 0.0
    seconds: float = 0.0
    detail: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ArchiveStartedEvent(ArchiveEvent):
    """Bytes are about to be written."""

    output: str = ""
    total_bytes: int = 0
    recipe: str = "flat"


@dataclass(frozen=True)
class ArchiveProgressEvent(ArchiveEvent):
    """A real progress sample: *written* of *total* bytes."""

    written: int = 0
    total: int = 0

    @property
    def fraction(self) -> float:
        return 0.0 if self.total <= 0 else min(self.written / self.total, 1.0)


@dataclass(frozen=True)
class ArchiveWarningEvent(ArchiveEvent):
    """A non-fatal problem worth surfacing."""

    message: str = ""
    level: str = "warning"


@dataclass(frozen=True)
class ArchiveCompletedEvent(ArchiveEvent):
    """The archive was written (and verified, when requested)."""

    result: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ArchiveFailedEvent(ArchiveEvent):
    """The operation failed; ``error`` is a friendly ``ArchiveError`` dict."""

    error: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ScanCompletedEvent(ArchiveEvent):
    """A scan finished (suspicious or clean)."""

    outcome: dict = field(default_factory=dict)


class EventBus:
    """A tiny synchronous, thread-safe publisher.

    Handlers are invoked in subscription order. Re-entrant publishing is
    allowed; an exception in one handler never stops the others (it is logged
    by the caller's logger instead).
    """

    def __init__(self) -> None:
        self._handlers: list[Callable[[ArchiveEvent], None]] = []
        self._lock = threading.RLock()

    def subscribe(self, handler: Callable[[ArchiveEvent], None]) -> Callable[[], None]:
        """Register *handler*; returns a callable that unsubscribes it."""
        with self._lock:
            self._handlers.append(handler)

        def unsubscribe() -> None:
            with self._lock:
                if handler in self._handlers:
                    self._handlers.remove(handler)

        return unsubscribe

    def publish(self, event: ArchiveEvent) -> None:
        """Deliver *event* to every current subscriber."""
        with self._lock:
            handlers = list(self._handlers)
        for handler in handlers:
            handler(event)

    def clear(self) -> None:
        with self._lock:
            self._handlers.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._handlers)


__credit__ = "ZipBomb Lab - zipbomb_lab.services.events - made by Xv @XvRendering https://github.com/MamadXV"
