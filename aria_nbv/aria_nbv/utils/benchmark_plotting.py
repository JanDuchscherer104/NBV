"""Ingest, aggregate, plot, and persist paired Python/Mojo benchmarks.

This module provides typed benchmark records/summaries, CSV ingestion,
within-stratum aggregation, Plotly latency/speedup/scaling/throughput figures,
and report persistence. It owns comparative summarization and presentation;
benchmark execution and raw timing collection remain with the benchmark
harnesses.

The records preserve raw trial identity while summaries compare implementations
only within the same benchmark and problem-size stratum.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from statistics import geometric_mean, mean, median, pstdev
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots  # type: ignore[import-untyped]

FONT_FAMILY = "DejaVu Sans, Arial, sans-serif"
PYTHON_COLOR = "#3776AB"
MOJO_COLOR = "#FF6B35"
SPEEDUP_COLOR = "#2E8B57"
NEUTRAL_GRID = "rgba(33, 41, 52, 0.12)"
PLOT_BG = "#FBFCFE"
PAPER_BG = "#FFFFFF"
IMPLEMENTATION_ORDER = ["python", "mojo"]

IMPLEMENTATION_COLORS: dict[str, str] = {
    "python": PYTHON_COLOR,
    "mojo": MOJO_COLOR,
}


@dataclass(frozen=True, slots=True)
class BenchmarkRecord:
    """One measured implementation trial before statistical aggregation.

    Latency is stored in milliseconds; throughput, when available, is measured
    in processed workload items per second.
    """

    benchmark: str
    """Stable workload name used to pair implementations."""

    implementation: str
    """Implementation label, conventionally `python` or `mojo`."""

    latency_ms: float
    """Wall-clock latency for this trial in milliseconds."""

    problem_size: str = "default"
    """Human-readable workload-size stratum for like-for-like aggregation."""

    throughput_items_per_s: float | None = None
    """Optional processed-item rate in items per second."""

    trial: str | None = None
    """Optional source trial or repetition identifier."""


@dataclass(frozen=True, slots=True)
class BenchmarkSummary:
    """Aggregated statistics for one benchmark / implementation / size tuple."""

    benchmark: str
    """Stable workload name shared with the contributing records."""

    implementation: str
    """Implementation summarized by this row."""

    problem_size: str
    """Workload-size stratum; implementations are never mixed across strata."""

    count: int
    """Number of raw trials included in the summary."""

    latency_median_ms: float
    """Median wall-clock latency in milliseconds."""

    latency_mean_ms: float
    """Arithmetic mean wall-clock latency in milliseconds."""

    latency_std_ms: float
    """Population standard deviation of latency in milliseconds."""

    throughput_mean_items_per_s: float | None = None
    """Mean item throughput when every contributing row reports throughput."""

    @property
    def key(self) -> tuple[str, str]:
        """Return the logical grouping key excluding implementation."""

        return self.benchmark, self.problem_size

    @property
    def display_label(self) -> str:
        """Return a compact label for grouped bar charts."""

        if self.problem_size == "default":
            return self.benchmark
        return f"{self.benchmark}<br><sup>{self.problem_size}</sup>"


def load_benchmark_csv(path: str | Path) -> list[BenchmarkRecord]:
    """Load benchmark trials from CSV.

    Expected columns:
    - required: ``benchmark`` (or ``kernel``/``workload``), ``implementation``,
      ``latency_ms`` (or ``time_ms``/``duration_ms``)
    - optional: ``problem_size`` (or ``size``/``n``), ``throughput_items_per_s``,
      ``trial``
    """

    csv_path = Path(path)
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    records: list[BenchmarkRecord] = []
    for row in rows:
        benchmark = _first_present(row, "benchmark", "kernel", "workload")
        implementation = _first_present(row, "implementation", "impl", "runtime")
        latency_raw = _first_present(row, "latency_ms", "time_ms", "duration_ms")
        if benchmark is None or implementation is None or latency_raw is None:
            raise ValueError(
                "Benchmark CSV requires benchmark/kernel, implementation/impl, and latency_ms/time_ms columns.",
            )
        size = _first_present(row, "problem_size", "size", "n") or "default"
        throughput_raw = _first_present(
            row,
            "throughput_items_per_s",
            "throughput",
            "items_per_s",
        )
        trial = _first_present(row, "trial", "repeat", "run")
        records.append(
            BenchmarkRecord(
                benchmark=str(benchmark).strip(),
                implementation=str(implementation).strip().lower(),
                latency_ms=float(latency_raw),
                problem_size=str(size).strip(),
                throughput_items_per_s=float(throughput_raw) if throughput_raw not in (None, "") else None,
                trial=str(trial).strip() if trial not in (None, "") else None,
            )
        )
    return records


def summarize_benchmarks(records: list[BenchmarkRecord]) -> list[BenchmarkSummary]:
    """Aggregate raw trials into median/mean/std summaries."""

    grouped: dict[tuple[str, str, str], list[BenchmarkRecord]] = {}
    for record in records:
        grouped.setdefault((record.benchmark, record.implementation, record.problem_size), []).append(record)

    summaries: list[BenchmarkSummary] = []
    for (benchmark, implementation, problem_size), group in grouped.items():
        latencies = [record.latency_ms for record in group]
        throughput_vals = [
            record.throughput_items_per_s for record in group if record.throughput_items_per_s is not None
        ]
        summaries.append(
            BenchmarkSummary(
                benchmark=benchmark,
                implementation=implementation,
                problem_size=problem_size,
                count=len(group),
                latency_median_ms=float(median(latencies)),
                latency_mean_ms=float(mean(latencies)),
                latency_std_ms=float(pstdev(latencies) if len(latencies) > 1 else 0.0),
                throughput_mean_items_per_s=float(mean(throughput_vals)) if throughput_vals else None,
            )
        )

    summaries.sort(key=lambda item: (item.benchmark, _sort_key_for_size(item.problem_size), item.implementation))
    return summaries


def build_latency_figure(
    summaries: list[BenchmarkSummary],
    *,
    title: str = "Python vs Mojo Latency",
) -> go.Figure:
    """Build a grouped latency comparison chart."""

    categories = _ordered_categories(summaries)
    by_impl = _group_by_implementation(summaries)

    fig = go.Figure()
    for implementation, rows in by_impl.items():
        row_map = {row.display_label: row for row in rows}
        fig.add_trace(
            go.Bar(
                x=categories,
                y=[row_map[label].latency_median_ms if label in row_map else None for label in categories],
                error_y={
                    "type": "data",
                    "array": [row_map[label].latency_std_ms if label in row_map else 0.0 for label in categories],
                    "visible": True,
                },
                text=[f"{row_map[label].latency_median_ms:.1f}" if label in row_map else "" for label in categories],
                textposition="outside",
                marker_color=_implementation_color(implementation),
                name=_display_implementation_name(implementation),
                cliponaxis=False,
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    + f"Implementation: {_display_implementation_name(implementation)}<br>"
                    + "Median latency: %{y:.3f} ms<br>"
                    + "Std: %{customdata[0]:.3f} ms<br>"
                    + "Trials: %{customdata[1]}<extra></extra>"
                ),
                customdata=[
                    (
                        row_map[label].latency_std_ms if label in row_map else 0.0,
                        row_map[label].count if label in row_map else 0,
                    )
                    for label in categories
                ],
            )
        )

    fig.update_layout(
        title=title,
        barmode="group",
        plot_bgcolor=PLOT_BG,
        paper_bgcolor=PAPER_BG,
        font={"family": FONT_FAMILY, "size": 14},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1.0},
        margin={"l": 70, "r": 30, "t": 90, "b": 105},
        width=1180,
        height=620,
        bargap=0.14,
        bargroupgap=0.05,
        uniformtext_minsize=10,
        uniformtext_mode="hide",
        yaxis_title="Median latency (ms)",
        xaxis_title="Benchmark",
    )
    fig.update_yaxes(gridcolor=NEUTRAL_GRID, zeroline=False, automargin=True)
    fig.update_xaxes(tickangle=0, automargin=True)
    return fig


def build_speedup_figure(
    summaries: list[BenchmarkSummary],
    *,
    baseline_impl: str = "python",
    target_impl: str = "mojo",
    title: str = "Mojo Speedup Over Python",
) -> go.Figure:
    """Build a speedup chart using median latency ratios."""

    speedups = compute_speedups(summaries, baseline_impl=baseline_impl, target_impl=target_impl)
    labels = [item["label"] for item in speedups]
    values = [item["speedup"] for item in speedups]
    geo_mean_speedup = geometric_mean(values) if values else None

    fig = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker_color=SPEEDUP_COLOR,
            text=[f"{value:.2f}x" for value in values],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="<b>%{x}</b><br>Speedup: %{y:.3f}x<extra></extra>",
            name="Speedup",
        )
    )
    fig.add_hline(y=1.0, line_dash="dash", line_color="rgba(33, 41, 52, 0.45)")
    if geo_mean_speedup is not None:
        fig.add_hline(y=geo_mean_speedup, line_dash="dot", line_color="rgba(46, 139, 87, 0.6)")
        fig.add_annotation(
            xref="paper",
            yref="y",
            x=0.01,
            y=geo_mean_speedup,
            text=f"Geo mean {geo_mean_speedup:.2f}x",
            showarrow=False,
            xanchor="left",
            yanchor="bottom",
            font={"size": 12, "color": SPEEDUP_COLOR},
            bgcolor="rgba(255, 255, 255, 0.85)",
        )
    fig.update_layout(
        title=title,
        plot_bgcolor=PLOT_BG,
        paper_bgcolor=PAPER_BG,
        font={"family": FONT_FAMILY, "size": 14},
        margin={"l": 70, "r": 30, "t": 90, "b": 105},
        width=1180,
        height=620,
        uniformtext_minsize=10,
        uniformtext_mode="hide",
        yaxis_title=f"{baseline_impl.title()} / {target_impl.title()} latency (higher is better)",
        xaxis_title="Benchmark",
    )
    fig.update_yaxes(gridcolor=NEUTRAL_GRID, zeroline=False, automargin=True)
    fig.update_xaxes(tickangle=0, automargin=True)
    return fig


def build_scaling_figure(
    summaries: list[BenchmarkSummary],
    *,
    title: str = "Latency Scaling Across Problem Size",
) -> go.Figure:
    """Build per-benchmark scaling curves across problem sizes."""

    benchmarks = sorted({summary.benchmark for summary in summaries})
    fig = make_subplots(
        rows=len(benchmarks),
        cols=1,
        shared_xaxes=True,
        subplot_titles=benchmarks,
        vertical_spacing=0.09,
    )

    for row_index, benchmark in enumerate(benchmarks, start=1):
        rows = [summary for summary in summaries if summary.benchmark == benchmark]
        by_impl = _group_by_implementation(rows)
        for implementation, impl_rows in by_impl.items():
            impl_rows_sorted = sorted(impl_rows, key=lambda item: _sort_key_for_size(item.problem_size))
            x_vals = [_size_display_value(item.problem_size) for item in impl_rows_sorted]
            y_vals = [item.latency_median_ms for item in impl_rows_sorted]
            fig.add_trace(
                go.Scatter(
                    x=x_vals,
                    y=y_vals,
                    mode="lines+markers",
                    marker={
                        "size": 10,
                        "color": _implementation_color(implementation),
                        "line": {"width": 1.5, "color": PAPER_BG},
                    },
                    line={"width": 3, "color": _implementation_color(implementation)},
                    name=_display_implementation_name(implementation),
                    legendgroup=implementation,
                    showlegend=row_index == 1,
                    hovertemplate=(
                        f"{_display_implementation_name(implementation)}<br>"
                        + "Problem size: %{x}<br>"
                        + "Median latency: %{y:.3f} ms<extra></extra>"
                    ),
                ),
                row=row_index,
                col=1,
            )

    fig.update_layout(
        title=title,
        plot_bgcolor=PLOT_BG,
        paper_bgcolor=PAPER_BG,
        font={"family": FONT_FAMILY, "size": 14},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1.0},
        margin={"l": 70, "r": 30, "t": 100, "b": 70},
        width=1180,
        height=max(420, 280 * len(benchmarks)),
        hovermode="x unified",
    )
    fig.update_yaxes(title_text="Median latency (ms)", gridcolor=NEUTRAL_GRID, zeroline=False, automargin=True)
    fig.update_xaxes(showgrid=False, automargin=True)
    fig.update_xaxes(title_text="Problem size", row=len(benchmarks), col=1)
    return fig


def build_throughput_figure(
    summaries: list[BenchmarkSummary],
    *,
    title: str = "Python vs Mojo Throughput",
) -> go.Figure:
    """Build a grouped throughput comparison chart when throughput data is available."""

    throughput_summaries = [summary for summary in summaries if summary.throughput_mean_items_per_s is not None]
    categories = _ordered_categories(throughput_summaries)
    by_impl = _group_by_implementation(throughput_summaries)

    fig = go.Figure()
    for implementation, rows in by_impl.items():
        row_map = {row.display_label: row for row in rows}
        fig.add_trace(
            go.Bar(
                x=categories,
                y=[
                    row_map[label].throughput_mean_items_per_s / 1000.0 if label in row_map else None
                    for label in categories
                ],
                text=[
                    f"{row_map[label].throughput_mean_items_per_s / 1000.0:.0f}k" if label in row_map else ""
                    for label in categories
                ],
                textposition="outside",
                marker_color=_implementation_color(implementation),
                name=_display_implementation_name(implementation),
                cliponaxis=False,
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    + f"Implementation: {_display_implementation_name(implementation)}<br>"
                    + "Mean throughput: %{customdata[0]:,.0f} items/s<br>"
                    + "Trials: %{customdata[1]}<extra></extra>"
                ),
                customdata=[
                    (
                        row_map[label].throughput_mean_items_per_s if label in row_map else 0.0,
                        row_map[label].count if label in row_map else 0,
                    )
                    for label in categories
                ],
            )
        )

    fig.update_layout(
        title=title,
        barmode="group",
        plot_bgcolor=PLOT_BG,
        paper_bgcolor=PAPER_BG,
        font={"family": FONT_FAMILY, "size": 14},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1.0},
        margin={"l": 70, "r": 30, "t": 90, "b": 105},
        width=1180,
        height=620,
        bargap=0.14,
        bargroupgap=0.05,
        uniformtext_minsize=10,
        uniformtext_mode="hide",
        yaxis_title="Mean throughput (k items/s)",
        xaxis_title="Benchmark",
    )
    fig.update_yaxes(gridcolor=NEUTRAL_GRID, zeroline=False, automargin=True)
    fig.update_xaxes(tickangle=0, automargin=True)
    return fig


def compute_speedups(
    summaries: list[BenchmarkSummary],
    *,
    baseline_impl: str = "python",
    target_impl: str = "mojo",
) -> list[dict[str, Any]]:
    """Compute speedup ratios from paired summary rows."""

    by_key: dict[tuple[str, str], dict[str, BenchmarkSummary]] = {}
    for summary in summaries:
        by_key.setdefault(summary.key, {})[summary.implementation] = summary

    speedups: list[dict[str, Any]] = []
    ordered_items = sorted(by_key.items(), key=lambda item: (item[0][0], _sort_key_for_size(item[0][1])))
    for (benchmark, problem_size), rows in ordered_items:
        baseline = rows.get(baseline_impl)
        target = rows.get(target_impl)
        if baseline is None or target is None or target.latency_median_ms <= 0:
            continue
        label = benchmark if problem_size == "default" else f"{benchmark}<br><sup>{problem_size}</sup>"
        speedups.append(
            {
                "benchmark": benchmark,
                "problem_size": problem_size,
                "label": label,
                "speedup": baseline.latency_median_ms / target.latency_median_ms,
            }
        )
    return speedups


def write_benchmark_report(
    records: list[BenchmarkRecord],
    *,
    out_dir: str | Path,
    title_prefix: str = "Python vs Mojo",
    write_png: bool = False,
) -> dict[str, Path]:
    """Write interactive benchmark figures and optional PNG snapshots.

    Returns:
        Mapping from figure kind to each generated artifact path.
    """

    summaries = summarize_benchmarks(records)
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    figures = {
        "latency": build_latency_figure(summaries, title=f"{title_prefix}: latency"),
        "speedup": build_speedup_figure(summaries, title=f"{title_prefix}: speedup"),
        "scaling": build_scaling_figure(summaries, title=f"{title_prefix}: scaling"),
    }
    if any(summary.throughput_mean_items_per_s is not None for summary in summaries):
        figures["throughput"] = build_throughput_figure(summaries, title=f"{title_prefix}: throughput")

    written: dict[str, Path] = {}
    for name, figure in figures.items():
        html_path = output_dir / f"{name}.html"
        figure.write_html(html_path, include_plotlyjs="cdn")
        written[f"{name}_html"] = html_path
        if write_png:
            png_path = output_dir / f"{name}.png"
            figure.write_image(png_path)
            written[f"{name}_png"] = png_path

    summary_csv = output_dir / "summary.csv"
    with summary_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "benchmark",
                "implementation",
                "problem_size",
                "count",
                "latency_median_ms",
                "latency_mean_ms",
                "latency_std_ms",
                "throughput_mean_items_per_s",
            ]
        )
        for summary in summaries:
            writer.writerow(
                [
                    summary.benchmark,
                    summary.implementation,
                    summary.problem_size,
                    summary.count,
                    f"{summary.latency_median_ms:.6f}",
                    f"{summary.latency_mean_ms:.6f}",
                    f"{summary.latency_std_ms:.6f}",
                    (
                        f"{summary.throughput_mean_items_per_s:.6f}"
                        if summary.throughput_mean_items_per_s is not None
                        else ""
                    ),
                ]
            )
    written["summary_csv"] = summary_csv
    return written


def _first_present(row: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        if key in row and row[key] not in ("", None):
            return row[key]
    return None


def _ordered_categories(summaries: list[BenchmarkSummary]) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for summary in sorted(summaries, key=lambda item: (item.benchmark, _sort_key_for_size(item.problem_size))):
        label = summary.display_label
        if label not in seen:
            labels.append(label)
            seen.add(label)
    return labels


def _group_by_implementation(summaries: list[BenchmarkSummary]) -> dict[str, list[BenchmarkSummary]]:
    grouped: dict[str, list[BenchmarkSummary]] = {}
    for summary in summaries:
        grouped.setdefault(summary.implementation, []).append(summary)
    ordered_implementations = IMPLEMENTATION_ORDER + sorted(
        implementation for implementation in grouped if implementation not in IMPLEMENTATION_ORDER
    )
    return {
        implementation: grouped[implementation]
        for implementation in ordered_implementations
        if implementation in grouped
    }


def _sort_key_for_size(problem_size: str) -> tuple[int, float | str]:
    try:
        return (0, float(problem_size))
    except ValueError:
        return (1, problem_size)


def _size_display_value(problem_size: str) -> float | str:
    try:
        return float(problem_size)
    except ValueError:
        return problem_size


def _implementation_color(implementation: str) -> str:
    return IMPLEMENTATION_COLORS.get(implementation.lower(), "#7F7F7F")


def _display_implementation_name(implementation: str) -> str:
    return implementation.upper() if implementation.lower() == "mojo" else implementation.title()


__all__ = [
    "BenchmarkRecord",
    "BenchmarkSummary",
    "build_latency_figure",
    "build_scaling_figure",
    "build_speedup_figure",
    "build_throughput_figure",
    "compute_speedups",
    "load_benchmark_csv",
    "summarize_benchmarks",
    "write_benchmark_report",
]
