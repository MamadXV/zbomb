# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Turn advisory strings into typed, actionable risk warnings.

The policy layer answers with plain strings (that behaviour is preserved
verbatim for the CLI). This module upgrades them into
:class:`~zipbomb_lab.domain.models.RiskWarning` objects with a severity and a
source, and adds a couple of *contextual* warnings the raw policy cannot know
about (an existing destination file, low free space).
"""

from __future__ import annotations

from pathlib import Path

from ..domain.models import RiskLevel, RiskWarning

__all__ = ["classify", "from_messages", "contextual"]

#: Substrings that mark a message as more than an FYI.
_DANGER_HINTS = (
    "exceeds",
    "above the absolute",
    "ceiling",
    "cap",
    "would expand to",
    "malformed",
    "hostile",
    "destructive",
)
_INFO_HINTS = (
    "note",
    "tip:",
    "resuming",
    "skipped",
    "does not apply",
    "ignored",
)


def classify(message: str) -> RiskLevel:
    """Guess a severity from the wording of a policy message."""
    low = (message or "").lower()
    if any(hint in low for hint in _DANGER_HINTS):
        return RiskLevel.DANGER
    if any(hint in low for hint in _INFO_HINTS):
        return RiskLevel.INFO
    return RiskLevel.WARNING


def from_messages(messages, *, source: str = "policy") -> list[RiskWarning]:
    """Upgrade a sequence of advisory strings into risk warnings."""
    return [
        RiskWarning(str(message), classify(str(message)), source)
        for message in messages or ()
        if str(message).strip()
    ]


def contextual(
    output: Path,
    *,
    exists: bool,
    free_bytes: int | None,
    required_bytes: int | None = None,
) -> list[RiskWarning]:
    """Warnings that only make sense once we know the destination.

    ``exists``       the destination archive already exists
    ``free_bytes``   free space on the target volume, when measurable
    ``required_bytes`` the projected archive size that must fit
    """
    warnings: list[RiskWarning] = []
    if exists:
        warnings.append(
            RiskWarning(
                f"{output} already exists and will be replaced",
                RiskLevel.WARNING,
                "overwrite",
            )
        )
    if (
        free_bytes is not None
        and required_bytes is not None
        and required_bytes > 0
        and free_bytes < required_bytes
    ):
        warnings.append(
            RiskWarning(
                "the target volume has less free space than the projected archive needs",
                RiskLevel.DANGER,
                "disk",
            )
        )
    return warnings


__credit__ = "ZipBomb Lab - zipbomb_lab.services.risk - made by Xv @XvRendering https://github.com/MamadXV"
