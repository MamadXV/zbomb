# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Adapters that turn the engine's byte ticks into structured events.

The engine reports progress through a tiny duck-typed object: it constructs a
bar, calls ``advance(size)`` and then ``close()``. :class:`BridgeProgress`
implements exactly that surface and republishes each tick as an
:class:`~zipbomb_lab.services.events.ArchiveProgressEvent`, so the same real
numbers reach the TUI without the engine knowing a UI exists.
"""

from __future__ import annotations

import time

from .events import EventBus, ArchiveProgressEvent, ArchiveStartedEvent

__all__ = ["BridgeProgress", "NullProgress"]


class BridgeProgress:
    """Forward real byte counts to an :class:`EventBus` (throttled)."""

    def __init__(
        self,
        bus: EventBus,
        label: str = "writing",
        total: int = 0,
        *,
        min_interval: float = 0.06,
        output: str = "",
        recipe: str = "flat",
    ) -> None:
        self._bus = bus
        self._label = label
        self._total = max(int(total), 0)
        self._written = 0
        self._min_interval = max(min_interval, 0.0)
        self._last = 0.0
        self._closed = False
        bus.publish(
            ArchiveStartedEvent(
                job_label=label,
                output=output,
                total_bytes=self._total,
                recipe=recipe,
            )
        )
        self._emit(force=True)

    @property
    def written(self) -> int:
        return self._written

    @property
    def total(self) -> int:
        return self._total

    def advance(self, count: int) -> None:
        """Record *count* more written bytes (emits when the throttle allows)."""
        self._written += max(int(count), 0)
        self._emit()

    def _emit(self, force: bool = False) -> None:
        now = time.monotonic()
        at_end = self._total > 0 and self._written >= self._total
        if not force and not at_end and (now - self._last) < self._min_interval:
            return
        self._last = now
        self._bus.publish(
            ArchiveProgressEvent(
                job_label=self._label,
                written=self._written,
                total=self._total,
            )
        )

    def close(self) -> None:
        """Flush a final sample (no-op when already at the end)."""
        if self._closed:
            return
        self._closed = True
        self._emit(force=True)


class NullProgress:
    """A progress sink that does nothing (used for silent/`--quiet` runs)."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: D401 - trivial
        self.written = 0
        self.total = int(kwargs.get("total", 0) or 0)

    def advance(self, count: int) -> None:
        self.written += max(int(count), 0)

    def close(self) -> None:
        pass


__credit__ = "ZipBomb Lab - zipbomb_lab.services.progress - made by Xv @XvRendering https://github.com/MamadXV"
