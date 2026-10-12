# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Recipes screen: the structural bomb families, with a live sample."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import DataTable, Input, Select, Static

from ...core import format_size
from ...domain.data import method_rows, recipe_entries
from ...domain.models import ArchiveError, ArchiveJob, ArchiveOptions
from ...engine import format_ratio
from ..widgets.preview import PlanPreview
from .base import LabScreen

__all__ = ["RecipesScreen"]


class RecipesScreen(LabScreen):
    """Show every structural recipe and model one of them."""

    key_context = "form"
    scroll_body = True

    def compose_body(self) -> ComposeResult:
        methods = [(f"{m['key']} - {m['label']}", m["key"]) for m in method_rows()]
        recipes = [(f"{r['key']} - {r['label']}", r["key"]) for r in recipe_entries()]
        yield Static("Structural bomb recipes", classes="title")
        yield Static("shape, not payload: nesting, codec chains and entry floods", classes="tagline")
        with Horizontal(classes="field-row"):
            yield Static("recipe", classes="field-label")
            yield Select(recipes, value="layered", allow_blank=False, id="recipe")
        with Horizontal(classes="field-row"):
            yield Static("method", classes="field-label")
            yield Select(methods, value="bzip2", allow_blank=False, id="method")
        with Horizontal(classes="field-row"):
            yield Static("target size", classes="field-label")
            yield Input(value="64MiB", id="size")
        yield PlanPreview(id="plan")
        yield DataTable(id="table", zebra_stripes=True, cursor_type="row")

    def on_mount(self) -> None:
        super().on_mount()
        self.call_after_refresh(self._initialise)

    def _initialise(self) -> None:
        table = self.query_one("#table", DataTable)
        table.add_columns("recipe", "knobs", "shape")
        for entry in recipe_entries():
            table.add_row(
                entry["key"],
                ", ".join(entry["knobs"]) or "-",
                entry["summary"],
            )
        self.recompute()
        self.query_one("#recipe", Select).focus()

    def reload_view(self) -> None:
        self.recompute()

    def recompute(self) -> None:
        from ...core import parse_size

        preview = self.query_one("#plan", PlanPreview)
        recipe = str(self.query_one("#recipe", Select).value or "layered")
        method = str(self.query_one("#method", Select).value or "bzip2")
        try:
            target = parse_size(self.query_one("#size", Input).value.strip() or "64MiB")
        except Exception as exc:
            preview.update(f"[red]cannot parse size: {exc}[/red]")
            return
        job = ArchiveJob(
            output=None,  # type: ignore[arg-type]
            target_bytes=target,
            options=ArchiveOptions(method=method, recipe=recipe, level=9),
        )
        try:
            prepared = self.app.service.plan(job)
        except ArchiveError as exc:
            preview.update(f"[red]{exc.message}[/red]")
            return
        preview.show(prepared.summary, source="generated zeros", headline=f"{recipe} plan")

    def on_select_changed(self, event: Select.Changed) -> None:
        self.recompute()

    def on_input_changed(self, event: Input.Changed) -> None:
        self.recompute()


__credit__ = "ZipBomb Lab - zipbomb_lab.tui.screens.recipes - made by Xv @XvRendering https://github.com/MamadXV"
