# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Typed domain layer for the lab.

The domain package is deliberately free of any text-UI import: the CLI, the
services and the TUI all speak in these types, and the core can be exercised
without a terminal.

* :mod:`zipbomb_lab.domain.models`  explicit dataclasses (jobs, options, …)
* :mod:`zipbomb_lab.domain.data`    read-only helpers over the registries
"""

from __future__ import annotations

from .models import (
    ArchiveError,
    ArchiveJob,
    ArchiveOptions,
    ArchivePlan,
    ArchiveProgress,
    FileSelection,
    OperationOutcome,
    RiskLevel,
    RiskWarning,
    ScanOutcome,
    AppSettings,
)

__all__ = [
    "ArchiveError",
    "ArchiveJob",
    "ArchiveOptions",
    "ArchivePlan",
    "ArchiveProgress",
    "FileSelection",
    "OperationOutcome",
    "RiskLevel",
    "RiskWarning",
    "ScanOutcome",
    "AppSettings",
]


__credit__ = "ZipBomb Lab - zipbomb_lab.domain - made by Xv @XvRendering https://github.com/MamadXV"
