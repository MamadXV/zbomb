# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Methods screen: the live calibration table for this interpreter."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import DataTable, Input, Select, Static

from ...core import format_size
from ...domain.data import method_guide
from ...domain.models import ArchiveError, ArchiveJob, ArchiveOptions
from ...engine import format_ratio
from .base import LabScreen

__all__ = ["MethodsScreen"]


class MethodsScreen(LabScreen):
    """Measured ratio and throughput for every writable method."""

    key_context = "form"
    scroll_body = True

    def compose_body(self) -> ComposeResult:
        yield Static("Compression methods", classes="title")
        yield Static(
            "every number is measured in RAM right before it is shown", classes="tagline"
        )
        with Horizontal(classes="field-row"):
            yield Static("target size", classes="field-label")
            yield Input(value="1TiB", id="size")
        with Horizontal(classes="field-row"):
            yield Static("method", classes="field-label")
            yield Select(
                [(g["title"], g["key"]) for g in method_guide()],
                value="bzip2",
                allow_blank=False,
                id="method",
            )
        with Horizontal(classes="field-row"):
            yield Static("level", classes="field-label")
            yield Select(
                [("auto", "auto"), ("0", "0"), ("1", "1"), ("2", "2"), ("3", "3"),
                 ("4", "4"), ("5", "5"), ("6", "6"), ("7", "7"), ("8", "8"), ("9", "9")],
                value="9",
                allow_blank=False,
                id="level",
            )
        with Container(classes="card"):
            yield Static("Measured results", classes="heading", id="table-title")
            yield DataTable(id="table", zebra_stripes=True, cursor_type="row")
        with Container(classes="card"):
            yield Static("Guide", classes="heading", id="guide-title")
            yield Static("", id="method-guide")

    def on_mount(self) -> None:
        super().on_mount()
        self.reload_view()

    def reload_view(self) -> None:
        from ...core import METHODS, parse_size

        table = self.query_one("#table", DataTable)
        try:
            target = parse_size(self.query_one("#size", Input).value.strip() or "1TiB")
        except Exception:
            return
        # Re-set the columns on every reload; clear() keeps them otherwise
        table.clear(columns=True)
        table.add_columns("method", "levels", "projected", "ratio", "throughput", "zip64")
        service = self.app.service
        shown = 0
        for key, method in METHODS.items():
            job = ArchiveJob(
                output=None,  # type: ignore[arg-type]
                target_bytes=target,
                options=ArchiveOptions(method=key, level=self._level()),
            )
            try:
                plan = service.plan(job).summary
            except ArchiveError:
                continue
            speed = f"{plan.ratio and (plan.target_bytes / plan.seconds / (1024 * 1024)):,.0f} MiB/s"
            table.add_row(
                key,
                str(method.level_range),
                format_size(plan.output_bytes),
                format_ratio(plan.ratio),
                speed if plan.seconds > 0 else "-",
                "yes" if plan.zip64 else "no",
            )
            shown += 1
        self.query_one("#table-title", Static).update(
            f"Measured results  [dim]{shown} of {len(METHODS)} methods at {format_size(target)}[/dim]"
        )
        self._update_guide()

    def _update_guide(self) -> None:
        """Update the method guide panel based on selected method."""
        from ...domain.data import method_guide

        method_key = str(self.query_one("#method", Select).value or "bzip2")
        guide = method_guide(method_key)
        if guide:
            g = guide[0]
            self.query_one("#guide-title", Static).update(
                f"Guide  [dim]{g['title']}[/dim]"
            )
            guide_text = (
                f"{g['what']}\n\n"
                f"[#FF6B00 b]What to expect[/]  {g['expect']}\n\n"
                f"[#FF6B00 b]Level guidance[/]  {g['levels']}\n\n"
                f"[#FF6B00 b]Best for[/]  {g['use']}"
            )
        else:
            self.query_one("#guide-title", Static).update("Guide")
            guide_text = "[dim]select a method to see its guide[/dim]"
        self.query_one("#method-guide", Static).update(guide_text)

    def on_input_changed(self, event: Input.Changed) -> None:
        self.reload_view()

    def on_select_changed(self, event: Select.Changed) -> None:
        self._update_guide()
        self.reload_view()

    def _level(self) -> int | None:
        try:
            raw = self.query_one("#level", Select).value
            if raw == "auto":
                return None
            return int(raw)
        except Exception:
            return None


__credit__ = "ZipBomb Lab - zipbomb_lab.tui.screens.methods - made by Xv @XvRendering https://github.com/MamadXV"
