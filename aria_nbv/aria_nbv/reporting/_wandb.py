"""Internal exact W&B acquisition and canonical Plotly report products."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ..utils.wandb_utils import WandbApi, WandbRun, _resolve_x_key
from .config import ReportThemeConfig, WandbReportSectionConfig, WandbSourceConfig
from .errors import ScientificReportError
from .results import (
    JsonScalar,
    NamedQuantity,
    ReportColumn,
    ReportFigure,
    ReportTable,
    SourceIdentity,
    canonical_plotly_json,
)


@dataclass(frozen=True, slots=True)
class _FrozenRun:
    id: str
    name: str
    state: str
    config: tuple[tuple[str, JsonScalar], ...]
    summary: tuple[tuple[str, JsonScalar], ...]
    history: pd.DataFrame


@dataclass(frozen=True, slots=True)
class _WandbEvidence:
    identity: SourceIdentity
    runs: tuple[_FrozenRun, ...]
    history_mode: Literal["sampled", "complete"]


@dataclass(frozen=True, slots=True)
class _SectionResults:
    quantities: tuple[NamedQuantity, ...]
    tables: tuple[ReportTable, ...]
    figures: tuple[ReportFigure, ...]


def _acquire_wandb_evidence(
    source: WandbSourceConfig,
    *,
    evidence_status: Literal["pilot", "confirmatory"],
    api: WandbApi,
) -> _WandbEvidence:
    if not source.run_ids:
        raise ValueError("W&B report sources require exact run_ids.")
    runs: list[_FrozenRun] = []
    for run_id in sorted(source.run_ids):
        path = f"{source.entity}/{source.project}/{run_id}"
        run = api.run(path)
        initial = _run_metadata(run, fallback_id=run_id)
        actual_id, name, state, config, summary = initial
        if actual_id != run_id:
            raise ScientificReportError(
                "source_identity_changed",
                f"W&B returned run {actual_id!r} for requested run {run_id!r}.",
                source_id="wandb",
            )
        if evidence_status == "confirmatory" and state != "finished":
            raise ValueError(f"Confirmatory W&B run {run_id!r} is not finished.")
        history = _history_frame(run, source)
        if _run_metadata(run, fallback_id=run_id) != initial:
            raise ScientificReportError(
                "source_identity_changed",
                f"W&B run {run_id!r} metadata changed during acquisition.",
                source_id="wandb",
            )
        runs.append(
            _FrozenRun(
                id=actual_id,
                name=name,
                state=state,
                config=config,
                summary=summary,
                history=history,
            )
        )
    digest_payload = [
        {
            "id": run.id,
            "name": run.name,
            "state": run.state,
            "config": run.config,
            "summary": run.summary,
            "history": _frame_records(run.history),
        }
        for run in runs
    ]
    digest = hashlib.sha256(_canonical_json(digest_payload)).hexdigest()
    identity = SourceIdentity(
        id="wandb",
        kind="wandb",
        sha256=digest,
        provenance=tuple(
            sorted(
                (
                    ("entity", source.entity),
                    ("history_complete", source.history_mode == "complete"),
                    ("history_mode", source.history_mode),
                    ("project", source.project),
                    ("run_count", len(runs)),
                )
            )
        ),
    )
    return _WandbEvidence(identity=identity, runs=tuple(runs), history_mode=source.history_mode)


def _run_metadata(
    run: WandbRun,
    *,
    fallback_id: str,
) -> tuple[str, str, str, tuple[tuple[str, JsonScalar], ...], tuple[tuple[str, JsonScalar], ...]]:
    return (
        str(getattr(run, "id", fallback_id)),
        str(getattr(run, "name", fallback_id)),
        str(getattr(run, "state", "")),
        _mapping_items(getattr(run, "config", None)),
        _mapping_items(getattr(run, "summary", None)),
    )


def _build_wandb_section(
    evidence: _WandbEvidence,
    section: WandbReportSectionConfig,
    theme: ReportThemeConfig,
    *,
    requested_result_ids: frozenset[str] | None,
) -> _SectionResults:
    rows: list[tuple[JsonScalar, ...]] = []
    last_values: list[float] = []
    figure = go.Figure()
    for index, run in enumerate(evidence.runs):
        if section.metric not in run.history:
            continue
        x_key, history = _resolve_x_key(run.history.copy(), ("trainer/global_step", "global_step", "_step", "epoch"))
        metric = history[[x_key, section.metric]].replace([np.inf, -np.inf], np.nan).dropna().sort_values(x_key)
        if metric.empty:
            continue
        last = float(metric[section.metric].iloc[-1])
        last_values.append(last)
        rows.append((run.id, run.name, run.state, x_key, int(len(metric)), last, evidence.history_mode))
        color = theme.colorway[index % len(theme.colorway)]
        if section.show_raw:
            figure.add_scatter(
                x=metric[x_key],
                y=metric[section.metric],
                mode="lines",
                name=f"{run.name} (raw)",
                line={"color": color, "dash": "dot", "width": 1},
                opacity=0.65,
            )
        if section.ema_alpha > 0:
            figure.add_scatter(
                x=metric[x_key],
                y=metric[section.metric].ewm(alpha=section.ema_alpha, adjust=False).mean(),
                mode="lines",
                name=f"{run.name} (EMA)",
                line={"color": color},
            )
    figure.update_layout(
        template=theme.template,
        font={"family": theme.font_family},
        title=f"{section.metric} across frozen W&B runs",
        xaxis_title="Training step",
        yaxis_title=section.metric,
    )
    table_id = f"{section.id}.table.metric-summary"
    quantity_id = f"{section.id}.quantity.last-mean"
    figure_id = f"{section.id}.figure.metric-curves"
    tables: tuple[ReportTable, ...] = ()
    if _requested(table_id, requested_result_ids):
        tables = (
            ReportTable(
                id=table_id,
                columns=tuple(
                    ReportColumn(id=name, symbol_id=None)
                    for name in ("run_id", "run_name", "state", "x_key", "n", "last", "history_mode")
                ),
                rows=tuple(rows),
                source_ids=(evidence.identity.id,),
            ),
        )
    quantities: tuple[NamedQuantity, ...] = ()
    if last_values and _requested(quantity_id, requested_result_ids):
        quantities = (
            NamedQuantity(
                id=quantity_id,
                value=float(np.mean(last_values)),
                unit=None,
                n=len(last_values),
                aggregation="mean of per-run last values",
                source_ids=(evidence.identity.id,),
                symbol_id=section.symbol_id,
            ),
        )
    figures: tuple[ReportFigure, ...] = ()
    if _requested(figure_id, requested_result_ids):
        figures = (
            ReportFigure(
                id=figure_id,
                plotly_json=canonical_plotly_json(figure),
                source_ids=(evidence.identity.id,),
                source_result_ids=tuple([table.id for table in tables] + [quantity.id for quantity in quantities]),
                symbol_ids=tuple(identifier for identifier in (section.symbol_id,) if identifier is not None),
                uses_webgl=False,
            ),
        )
    return _SectionResults(quantities=quantities, tables=tables, figures=figures)


def _history_frame(run: WandbRun, source: WandbSourceConfig) -> pd.DataFrame:
    keys = list(source.history_keys) or None
    if source.history_mode == "complete":
        rows = run.scan_history(keys=keys)
        frame = pd.DataFrame(list(rows))
    else:
        frame = pd.DataFrame(run.history(keys=keys, samples=source.max_rows))
    selected_columns = sorted(frame.columns)
    return frame.loc[:, selected_columns].reset_index(drop=True)


def _mapping_items(raw: Any) -> tuple[tuple[str, JsonScalar], ...]:
    try:
        mapping = dict(raw or {})
    except (TypeError, ValueError):
        mapping = {}
    return tuple(sorted((str(key), _scalar(value)) for key, value in mapping.items() if not str(key).startswith("_")))


def _frame_records(frame: pd.DataFrame) -> list[dict[str, JsonScalar]]:
    return [
        {str(column): _scalar(value) for column, value in zip(frame.columns, row, strict=True)}
        for row in frame.itertuples(index=False, name=None)
    ]


def _scalar(value: Any) -> JsonScalar:
    if value is None:
        return None
    if isinstance(value, dict | list | tuple):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    if bool(pd.isna(value)):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, bool | int | float | str):
        return value
    return str(value)


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _requested(result_id: str, requested: frozenset[str] | None) -> bool:
    return requested is None or result_id in requested


__all__: list[str] = []
