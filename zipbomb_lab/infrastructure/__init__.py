# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Infrastructure: filesystem, settings storage, audit log, logging, terminal.

Nothing here renders anything. These modules are the boundary between the lab
and the outside world (the settings file, the audit log, platform quirks), so
they are the only place that is allowed to know about environment variables
and on-disk formats.
"""

from __future__ import annotations

from .config_store import ConfigStore, default_config_store
from .audit import AuditLog, default_audit_log
from .terminal import TerminalCaps, detect_caps
from .logging import get_logger, debug_enabled
from .platform import bitness, disk_free, is_32bit, is_windows, python_version

__all__ = [
    "ConfigStore",
    "AuditLog",
    "TerminalCaps",
    "default_config_store",
    "default_audit_log",
    "detect_caps",
    "get_logger",
    "debug_enabled",
    "bitness",
    "disk_free",
    "is_32bit",
    "is_windows",
    "python_version",
]


__credit__ = "ZipBomb Lab - zipbomb_lab.infrastructure - made by Xv @XvRendering https://github.com/MamadXV"
