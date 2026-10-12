# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Transient UI state for the Textual application.

This holds *session* state (where we are, what is selected, what is running).
Persistent preferences deliberately live in the settings file, never here.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path

from ..domain.models import ArchiveJob, ArchivePlan, OperationOutcome

__all__ = ["OperationState", "NavigationState", "AppState"]


@dataclass
class OperationState:
    """What the app is busy with right now (or nothing)."""

    running: bool = False
    kind: str = ""
    label: str = ""
    written: int = 0
    total: int = 0
    warnings: list[str] = field(default_factory=list)
    outcome: OperationOutcome | None = None

    @property
    def fraction(self) -> float:
        return 0.0 if self.total <= 0 else min(self.written / self.total, 1.0)

    @property
    def percent(self) -> float:
        return self.fraction * 100.0

    def reset(self) -> None:
        self.running = False
        self.kind = ""
        self.label = ""
        self.written = 0
        self.total = 0
        self.warnings = []
        self.outcome = None


@dataclass
class NavigationState:
    """Where the user is, and what recent actions exist for the home screen."""

    screen: str = "home"
    directory: Path = field(default_factory=Path.cwd)
    history: list[str] = field(default_factory=list)
    recent_actions: list[str] = field(default_factory=list)
    status_message: str = "ready"

    def note(self, text: str) -> None:
        self.status_message = text

    def remember(self, action: str, limit: int = 6) -> None:
        self.history.append(action)
        self.recent_actions = [a for a in self.recent_actions if a != action]
        self.recent_actions.insert(0, action)
        del self.recent_actions[limit:]


@dataclass
class AppState:
    """The single object the screens read from and write to."""

    navigation: NavigationState = field(default_factory=NavigationState)
    operation: OperationState = field(default_factory=OperationState)
    active_job: ArchiveJob | None = None
    active_plan: ArchivePlan | None = None
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    # -- locked convenience accessors -------------------------------------
    def begin(self, kind: str, label: str, total: int) -> None:
        with self._lock:
            self.operation.running = True
            self.operation.kind = kind
            self.operation.label = label
            self.operation.written = 0
            self.operation.total = int(total or 0)
            self.operation.warnings = []
            self.operation.outcome = None
            self.navigation.note(f"{kind} running")

    def advance(self, written: int, total: int) -> None:
        with self._lock:
            self.operation.written = int(written)
            self.operation.total = int(total or self.operation.total)

    def warn(self, message: str) -> None:
        with self._lock:
            self.operation.warnings.append(message)

    def finish(self, outcome: OperationOutcome) -> None:
        with self._lock:
            self.operation.running = False
            self.operation.outcome = outcome
            if outcome.ok:
                self.navigation.note(f"{outcome.kind} complete")
            else:
                self.navigation.note("failed")


__credit__ = "ZipBomb Lab - zipbomb_lab.tui.state - made by Xv @XvRendering https://github.com/MamadXV"
