"""Internal adapter from rollout-owned report-v1 frames to report results."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal

import pandas as pd
import plotly.graph_objects as go

from ..rollouts.reporting import build_thesis_report_frames, serialize_thesis_report_bundle
from .config import ReportThemeConfig, RolloutReportSectionConfig, RolloutSourceConfig
from .results import (
    JsonScalar,
    NamedQuantity,
    ReportColumn,
    ReportFigure,
    ReportTable,
    SourceIdentity,
    canonical_plotly_json,
)

_COLUMN_SYMBOLS: dict[str, str] = {
    "horizon": "rl.H",
    "cumulative_target_rri": "entity.target_rri_cumulative",
    "cumulative_target_root_gain": "entity.target_root_gain_cumulative",
    "target_rri": "entity.rri_e",
}


@dataclass(frozen=True, slots=True)
class _RolloutEvidence:
    """One validated report-v1 projection reused by all rollout sections."""

    identity: SourceIdentity
    frames: dict[str, pd.DataFrame]


@dataclass(frozen=True, slots=True)
class _SectionResults:
    quantities: tuple[NamedQuantity, ...]
    tables: tuple[ReportTable, ...]
    figures: tuple[ReportFigure, ...]


def _acquire_rollout_evidence(
    source: RolloutSourceConfig,
    *,
    evidence_status: Literal["pilot", "confirmatory"],
    required_tables: frozenset[str],
) -> _RolloutEvidence:
    frames = build_thesis_report_frames(
        source.store_paths,
        sidecar_paths=source.sidecar_paths,
        evidence_status=evidence_status,
        table_names=required_tables,
    )
    payload = serialize_thesis_report_bundle(frames)
    stores = frames["stores"].sort_values("store_id", kind="stable")
    provenance_rows = [
        (f"store.{index}.id", _scalar(row.store_id)) for index, row in enumerate(stores.itertuples(index=False))
    ]
    provenance_rows.extend(
        (f"store.{index}.manifest_sha256", _scalar(row.manifest_sha256))
        for index, row in enumerate(stores.itertuples(index=False))
    )
    identity = SourceIdentity(
        id="rollout",
        kind="rollout",
        sha256=hashlib.sha256(payload).hexdigest(),
        provenance=tuple(sorted(provenance_rows)),
    )
    return _RolloutEvidence(identity=identity, frames=frames)


def _build_rollout_section(
    evidence: _RolloutEvidence,
    section: RolloutReportSectionConfig,
    theme: ReportThemeConfig,
    *,
    requested_result_ids: frozenset[str] | None,
) -> _SectionResults:
    unknown_tables = set(section.include_tables) - set(evidence.frames)
    if unknown_tables:
        raise ValueError(f"Unknown rollout report tables: {sorted(unknown_tables)}")
    tables = tuple(
        _frame_table(f"{section.id}.table.{name}", evidence.frames[name], evidence.identity.id)
        for name in section.include_tables
        if _requested(f"{section.id}.table.{name}", requested_result_ids)
    )
    quantities = _fact_quantities(evidence, section, requested_result_ids=requested_result_ids)
    figure_id = f"{section.id}.figure.facts"
    figures: tuple[ReportFigure, ...] = ()
    if _requested(figure_id, requested_result_ids):
        figures = (_fact_figure(evidence, section, theme),)
    return _SectionResults(quantities=quantities, tables=tables, figures=figures)


def _fact_quantities(
    evidence: _RolloutEvidence,
    section: RolloutReportSectionConfig,
    *,
    requested_result_ids: frozenset[str] | None,
) -> tuple[NamedQuantity, ...]:
    facts = evidence.frames["facts"]
    selected = facts.loc[facts["key"] == section.quantity_fact_key].sort_values("store_id", kind="stable")
    quantities: list[NamedQuantity] = []
    for row in selected.itertuples(index=False):
        result_id = f"{section.id}.quantity.{row.store_id}.{section.quantity_fact_key}"
        if not _requested(result_id, requested_result_ids):
            continue
        support = _scalar(row.n)
        n = support if isinstance(support, int) and not isinstance(support, bool) else None
        quantities.append(
            NamedQuantity(
                id=result_id,
                value=_scalar(row.value),
                unit=None if pd.isna(row.unit) else str(row.unit),
                n=n,
                aggregation=str(row.aggregation),
                source_ids=(evidence.identity.id,),
                symbol_id=section.quantity_symbol_id,
            )
        )
    return tuple(quantities)


def _fact_figure(
    evidence: _RolloutEvidence,
    section: RolloutReportSectionConfig,
    theme: ReportThemeConfig,
) -> ReportFigure:
    facts = evidence.frames["facts"]
    selected = facts.loc[facts["key"].isin(section.figure_fact_keys)].sort_values(["store_id", "key"], kind="stable")
    figure = go.Figure()
    for index, (store_id, frame) in enumerate(selected.groupby("store_id", sort=True)):
        figure.add_bar(
            name=str(store_id),
            x=frame["key"].tolist(),
            y=frame["value"].tolist(),
            marker_color=theme.colorway[index % len(theme.colorway)],
        )
    figure.update_layout(
        template=theme.template,
        font={"family": theme.font_family},
        title="Rollout fact support by immutable store",
        xaxis_title="Rollout fact",
        yaxis_title="Value",
        barmode="group",
    )
    return ReportFigure(
        id=f"{section.id}.figure.facts",
        plotly_json=canonical_plotly_json(figure),
        source_ids=(evidence.identity.id,),
        source_result_ids=(),
        symbol_ids=tuple(identifier for identifier in (section.quantity_symbol_id,) if identifier is not None),
        uses_webgl=False,
    )


def _frame_table(result_id: str, frame: pd.DataFrame, source_id: str) -> ReportTable:
    columns = tuple(ReportColumn(id=str(name), symbol_id=_COLUMN_SYMBOLS.get(str(name))) for name in frame.columns)
    rows = tuple(tuple(_scalar(value) for value in row) for row in frame.itertuples(index=False, name=None))
    return ReportTable(id=result_id, columns=columns, rows=rows, source_ids=(source_id,))


def _requested(result_id: str, requested: frozenset[str] | None) -> bool:
    return requested is None or result_id in requested


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


__all__: list[str] = []
