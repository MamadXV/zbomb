# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Estimate screen: model any size without writing anything."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Input, Select, Static

from ...core import format_size
from ...domain.data import method_rows
from ...domain.models import ArchiveError, ArchiveJob, ArchiveOptions
from ...engine import format_ratio
from ..widgets.preview import PlanPreview
from .base import LabScreen
from .settings import level_options

__all__ = ["EstimateScreen"]


class EstimateScreen(LabScreen):
    """Compare methods and model one target size."""

    key_context = "form"
    scroll_body = True

    def compose_body(self) -> ComposeResult:
        methods = [(f"{m['key']} - {m['label']}", m["key"]) for m in method_rows()]
        yield Static("Estimate a size", classes="title")
        yield Static("writes nothing - the numbers are measured live", classes="tagline")
        with Horizontal(classes="field-row"):
            yield Static("target size", classes="field-label")
            yield Input(value="1TiB", id="size")
        with Horizontal(classes="field-row"):
            yield Static("method", classes="field-label")
            yield Select(methods, value="bzip2", allow_blank=False, id="method")
        with Horizontal(classes="field-row"):
            yield Static("level", classes="field-label")
            yield Select(level_options(), value=9, allow_blank=False, id="level")
        with Horizontal(classes="buttons"):
            yield Button("Model", variant="primary", id="model-btn")
            yield Button("Compare all methods", id="compare-btn")
        yield PlanPreview(id="plan")
        yield DataTable(id="table", zebra_stripes=True, cursor_type="row")

    def on_mount(self) -> None:
        super().on_mount()
        self.call_after_refresh(self._initialise)

    def _initialise(self) -> None:
        table = self.query_one("#table", DataTable)
        table.add_columns("method", "projected", "ratio", "runtime", "zip64")
        self.recompute()

    def reload_view(self) -> None:
        self.recompute()

    def _method(self) -> str:
        return str(self.query_one("#method", Select).value or "bzip2")

    def _level(self) -> int | None:
        try:
            return int(self.query_one("#level", Select).value)
        except Exception:
            return None

    def recompute(self) -> None:
        from ...core import parse_size

        preview = self.query_one("#plan", PlanPreview)
        try:
            target = parse_size(self.query_one("#size", Input).value.strip() or "1TiB")
        except Exception as exc:
            preview.update(f"[red]cannot parse size: {exc}[/red]")
            return
        job = ArchiveJob(
            output=None,  # type: ignore[arg-type]  # estimates never write
            target_bytes=target,
            options=ArchiveOptions(method=self._method(), level=self._level()),
        )
        try:
            prepared = self.app.service.plan(job)
        except ArchiveError as exc:
            preview.update(f"[red]{exc.message}[/red]")
            return
        preview.show(prepared.summary, source="generated zeros", headline="estimate")
        self._fill_table()

    def _fill_table(self) -> None:
        from ...core import METHODS, parse_size

        table = self.query_one("#table", DataTable)
        # Re-set the columns on every reload; clear() keeps them otherwise
        table.clear(columns=True)
        table.add_columns("method", "projected", "ratio", "runtime", "zip64")
        try:
            target = parse_size(self.query_one("#size", Input).value.strip() or "1TiB")
        except Exception:
            return
        service = self.app.service
        for key in METHODS:  # key is the string, not the Method object
            try:
                job = ArchiveJob(
                    output=None,  # type: ignore[arg-type]
                    target_bytes=target,
                    options=ArchiveOptions(method=key, level=self._level()),  # pass string key
                )
                plan = service.plan(job).summary
            except ArchiveError as exc:
                table.add_row(key, exc.message, "-", "-", "-")
                continue
            table.add_row(
                key,
                format_size(plan.output_bytes),
                format_ratio(plan.ratio),
                f"~{plan.seconds:,.0f}s",
                "yes" if plan.zip64 else "no",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "compare-btn":
            self._fill_table()
        elif event.button.id == "model-btn":
            self.recompute()

    def on_select_changed(self, event: Select.Changed) -> None:
        self.recompute()

    def on_input_changed(self, event: Input.Changed) -> None:
        self.recompute()


__credit__ = "ZipBomb Lab - zipbomb_lab.tui.screens.estimate - made by Xv @XvRendering https://github.com/MamadXV"
