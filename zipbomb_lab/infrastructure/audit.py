# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Append-only audit log of every archive that was created or refused.

Delegates to the existing ``core`` helpers so the ``ZIPBOMB_LAB_LOG`` override
and the JSON-lines format stay identical; the wrapper only gives callers a
named object and a couple of helpers.
"""

from __future__ import annotations

import json
from pathlib import Path

__all__ = ["AuditLog", "default_audit_log"]


class AuditLog:
    """Record and read back the artifact audit trail."""

    def __init__(self, path: Path | None = None) -> None:
        self._explicit = Path(path) if path else None

    @property
    def path(self) -> Path:
        from ..core import log_path

        return self._explicit or log_path()

    def append(self, record: dict) -> None:
        """Append one JSON line; never raises (the log is a convenience)."""
        from ..core import append_audit

        append_audit(record, self._explicit)

    def read(self, limit: int = 20) -> list[str]:
        """Return the newest *limit* raw lines, oldest first."""
        from ..core import read_audit

        return read_audit(limit, self._explicit)

    def entries(self, limit: int = 20) -> list[dict]:
        """Return the newest *limit* records decoded into dictionaries."""
        decoded: list[dict] = []
        for line in self.read(limit):
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if isinstance(item, dict):
                decoded.append(item)
        return decoded


def default_audit_log() -> AuditLog:
    return AuditLog()


__credit__ = "ZipBomb Lab - zipbomb_lab.infrastructure.audit - made by Xv @XvRendering https://github.com/MamadXV"
