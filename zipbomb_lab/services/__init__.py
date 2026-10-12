# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Application services: orchestration, events, progress and settings access.

Services are the only layer the front ends talk to. They own the workflow
(plan → gate → write → audit), publish structured events, and never import a
widget or print to the terminal themselves.
"""

from __future__ import annotations

from .events import (
    ArchiveCompletedEvent,
    ArchiveEvent,
    ArchiveFailedEvent,
    ArchivePlannedEvent,
    ArchiveProgressEvent,
    ArchiveStartedEvent,
    ArchiveWarningEvent,
    EventBus,
    ScanCompletedEvent,
)
from .archive_service import ArchiveService, PreparedArchive
from .progress import BridgeProgress, NullProgress
from .settings_service import SettingsService

__all__ = [
    "ArchiveService",
    "PreparedArchive",
    "SettingsService",
    "EventBus",
    "ArchiveEvent",
    "ArchivePlannedEvent",
    "ArchiveStartedEvent",
    "ArchiveProgressEvent",
    "ArchiveWarningEvent",
    "ArchiveCompletedEvent",
    "ArchiveFailedEvent",
    "ScanCompletedEvent",
    "BridgeProgress",
    "NullProgress",
]


__credit__ = "ZipBomb Lab - zipbomb_lab.services - made by Xv @XvRendering https://github.com/MamadXV"
