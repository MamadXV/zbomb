# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""A read-only panel that renders one archived plan and its warnings.

Pure presentation over :class:`~zipbomb_lab.domain.models.ArchivePlan`, so the
create screen, the estimate screen and the recipe screen all show the same
numbers in the same layout.
"""

from __future__ import annotations

from pathlib import Path

from textual.widgets import Static

from ...core import format_duration, format_size
from ...domain.models import ArchivePlan, RiskLevel
from ...engine import format_ratio

__all__ = ["PlanPreview", "format_plan_text"]


def _severity_markup(level: RiskLevel) -> str:
    return {
        RiskLevel.DANGER: "bold red",
        RiskLevel.WARNING: "yellow",
        RiskLevel.INFO: "dim",
    }.get(level, "yellow")


def format_plan_text(
    plan: ArchivePlan,
    *,
    output: Path | None = None,
    source: str = "",
    warnings=(),
) -> str:
    """Build the Rich-markup body of a plan preview (stable, testable)."""
    lines = [
        f"[b]recipe[/b]      {plan.recipe}",
        f"[b]method[/b]      {plan.method}"
        + (f" level {plan.level}" if plan.level is not None else ""),
    ]
    if source:
        lines.append(f"[b]source[/b]      {source}")
    lines += [
        f"[b]expands to[/b]  {format_size(plan.expanded_bytes or plan.target_bytes)}"
        + (" (recursively)" if plan.expanded_bytes > plan.target_bytes else ""),
        f"[b]projected[/b]   {format_size(plan.output_bytes)} on disk",
        f"[b]ratio[/b]       {format_ratio(plan.ratio)}",
        f"[b]runtime[/b]     ~{format_duration(plan.seconds)}",
        f"[b]entries[/b]     {plan.entries:,}",
        f"[b]zip64[/b]       {'yes' if plan.zip64 else 'no'}",
    ]
    if plan.encoder_memory:
        lines.append(f"[b]memory[/b]      ~{format_size(plan.encoder_memory)}")
    if not plan.measured:
        lines.append("[dim]the archive size is modelled, not assembled[/dim]")
    if output is not None:
        lines.append(f"[b]output[/b]      {output}")
    for warning in warnings:
        level = warning.level if hasattr(warning, "level") else RiskLevel.WARNING
        message = warning.message if hasattr(warning, "message") else str(warning)
        lines.append(f"[{_severity_markup(level)}]! {message}[/]")
    return "\n".join(lines)


class PlanPreview(Static):
    """A bordered panel showing the current plan."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.add_class("preview")
        self._last = ""

    def update(self, content) -> None:
        """Remember the markup passed in (tests read :attr:`text`)."""
        self._last = str(content)
        super().update(content)

    @property
    def text(self) -> str:
        """The last markup string assigned to this panel."""
        return self._last

    def show(
        self,
        plan: ArchivePlan | None,
        *,
        output: Path | None = None,
        source: str = "",
        warnings=(),
        headline: str = "plan",
    ) -> None:
        if plan is None:
            self.update("[dim]nothing modelled yet[/dim]")
            return
        body = format_plan_text(plan, output=output, source=source, warnings=warnings)
        self.update(f"[b]{headline}[/b]\n{body}")

    def clear_plan(self) -> None:
        self.update("[dim]nothing modelled yet[/dim]")


__credit__ = "ZipBomb Lab - zipbomb_lab.tui.widgets.preview - made by Xv @XvRendering https://github.com/MamadXV"
