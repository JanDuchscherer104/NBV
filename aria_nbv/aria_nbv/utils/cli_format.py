"""Shared Rich formatting helpers for human-facing package CLIs.

The helpers in this module are intentionally small. CLI modules remain
responsible for building domain payloads, while this module centralizes common
terminal rendering choices: auto terminal detection, compact key/value panels,
count tables, and numeric distribution tables.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .console import Console


def cli_console() -> Console:
    """Return a project console that lets Rich detect terminal capabilities."""

    return Console(force_terminal=None, color_system="auto")


def format_value(value: Any, *, digits: int = 4) -> str:
    """Format a scalar value for compact CLI tables."""

    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.{digits}g}"
    if isinstance(value, Path):
        return value.as_posix()
    return str(value)


def key_value_panel(title: str, rows: Mapping[str, Any] | Sequence[tuple[str, Any]]) -> Panel:
    """Build a compact panel containing key/value rows."""

    table = Table.grid(padding=(0, 2))
    table.add_column(style="cyan", no_wrap=True)
    table.add_column()
    items = rows.items() if isinstance(rows, Mapping) else rows
    for key, value in items:
        table.add_row(str(key), format_value(value))
    return Panel(table, title=title, border_style="cyan", expand=False)


def counts_table(title: str, counts: Mapping[str, Any]) -> Table:
    """Build a two-column table for named counts."""

    table = Table(title=title, box=box.SIMPLE_HEAD, expand=False)
    table.add_column("Name", style="cyan")
    table.add_column("Count", justify="right")
    for name, value in sorted(counts.items()):
        table.add_row(str(name), format_value(value))
    return table


def summary_table(title: str, summaries: Mapping[str, Mapping[str, Any]]) -> Table:
    """Build a table for count/min/mean/max style summaries."""

    table = Table(title=title, box=box.SIMPLE_HEAD, expand=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Min", justify="right")
    table.add_column("Mean", justify="right")
    table.add_column("Max", justify="right")
    for name, summary in summaries.items():
        table.add_row(
            str(name),
            format_value(summary.get("count")),
            format_value(summary.get("minimum", summary.get("min"))),
            format_value(summary.get("mean")),
            format_value(summary.get("maximum", summary.get("max"))),
        )
    return table


def distribution_table(title: str, summaries: Mapping[str, Mapping[str, Any]]) -> Table:
    """Build a table for percentile distributions."""

    table = Table(title=title, box=box.SIMPLE_HEAD, expand=False)
    table.add_column("Metric", style="cyan")
    metric_columns = ("count", "min", "p5", "p25", "median", "mean", "p75", "p95", "max")
    for column in metric_columns:
        table.add_column(column, justify="right")
    for name, summary in summaries.items():
        table.add_row(str(name), *(format_value(summary.get(column)) for column in metric_columns))
    return table


def rows_table(title: str, columns: Sequence[str], rows: Iterable[Sequence[Any]]) -> Table:
    """Build a general table from column names and row values."""

    table = Table(title=title, box=box.SIMPLE_HEAD, expand=False)
    for index, column in enumerate(columns):
        justify = "right" if index > 0 and column.lower() not in {"key", "path", "scene", "snippet"} else "left"
        style = "cyan" if index == 0 else None
        table.add_column(column, justify=justify, style=style)
    for row in rows:
        table.add_row(*(format_value(value) for value in row))
    return table


def status_text(ok: bool) -> Text:
    """Return a green `ok` or red `failed` Rich text token."""

    return Text("ok", style="green") if ok else Text("failed", style="red")


__all__ = [
    "cli_console",
    "counts_table",
    "distribution_table",
    "format_value",
    "key_value_panel",
    "rows_table",
    "status_text",
    "summary_table",
]
