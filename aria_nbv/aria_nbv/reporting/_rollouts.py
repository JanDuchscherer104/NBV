"""Internal adapter from rollout-owned report-v1 frames to report results."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ..rollouts import RolloutZarrStoreReader
from ..rollouts.inspection import build_manifest_facts, s2_target_direction_histogram
from ..rollouts.reporting import build_thesis_report_frames, serialize_thesis_report_bundle
from ..rollouts.s2_reporting import S2Channel, s2_direction_figure
from .config import (
    ReportThemeConfig,
    RolloutReportSectionConfig,
    RolloutSourceConfig,
    S2RolloutReportSectionConfig,
)
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
    s2_stores: tuple["_S2StoreEvidence", ...] = ()


@dataclass(frozen=True, slots=True)
class _S2StoreEvidence:
    """One immutable store's complete spherical reducer output."""

    slot: int
    store_id: str
    path: Path
    azimuth_bins: int
    elevation_bins: int
    projection_limit: int
    payload: dict[str, Any]
    payload_sha256: str


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
    s2_specs: frozenset[tuple[int, int, int]] = frozenset(),
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
    s2_stores: list[_S2StoreEvidence] = []
    s2_sources: list[tuple[str, Path, RolloutZarrStoreReader]] = []
    if s2_specs:
        for path in _resolved_store_paths(source):
            reader = RolloutZarrStoreReader(path)
            manifest_payload = build_manifest_facts(reader).payload
            store_id = str(manifest_payload["root_attrs"]["manifest_sha256"])
            s2_sources.append((store_id, path, reader))
    for slot, (store_id, path, reader) in enumerate(sorted(s2_sources, key=lambda item: (item[0], item[1])), start=1):
        for azimuth_bins, elevation_bins, projection_limit in sorted(s2_specs):
            payload_mapping = asdict(
                s2_target_direction_histogram(
                    reader,
                    azimuth_bins=azimuth_bins,
                    elevation_bins=elevation_bins,
                    projection_limit=projection_limit,
                )
            )
            payload_bytes = _canonical_s2_payload(payload_mapping)
            payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()
            provenance_rows.append(
                (
                    f"store.{slot - 1}.s2.{azimuth_bins}x{elevation_bins}.{projection_limit}.sha256",
                    payload_sha256,
                )
            )
            s2_stores.append(
                _S2StoreEvidence(
                    slot=slot,
                    store_id=store_id,
                    path=path,
                    azimuth_bins=azimuth_bins,
                    elevation_bins=elevation_bins,
                    projection_limit=projection_limit,
                    payload=payload_mapping,
                    payload_sha256=payload_sha256,
                )
            )
    identity_payload = payload + b"".join(item.payload_sha256.encode("ascii") for item in s2_stores)
    identity = SourceIdentity(
        id="rollout",
        kind="rollout",
        sha256=hashlib.sha256(identity_payload).hexdigest(),
        provenance=tuple(sorted(provenance_rows)),
    )
    return _RolloutEvidence(identity=identity, frames=frames, s2_stores=tuple(s2_stores))


def _build_rollout_section(
    evidence: _RolloutEvidence,
    section: RolloutReportSectionConfig | S2RolloutReportSectionConfig,
    theme: ReportThemeConfig,
    *,
    requested_result_ids: frozenset[str] | None,
) -> _SectionResults:
    if isinstance(section, S2RolloutReportSectionConfig):
        return _build_s2_section(evidence, section, theme, requested_result_ids=requested_result_ids)
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


def _build_s2_section(
    evidence: _RolloutEvidence,
    section: S2RolloutReportSectionConfig,
    theme: ReportThemeConfig,
    *,
    requested_result_ids: frozenset[str] | None,
) -> _SectionResults:
    """Freeze support, named values, and shared Plotly S2 specifications."""

    stores = tuple(
        store
        for store in evidence.s2_stores
        if (
            store.azimuth_bins,
            store.elevation_bins,
            store.projection_limit,
        )
        == (section.azimuth_bins, section.elevation_bins, section.projection_limit)
    )
    if not stores:
        raise ValueError(f"No acquired S2 evidence matches report section {section.id!r}.")
    table_id = f"{section.id}.table.support"
    table = _s2_support_table(table_id, stores, evidence.identity.id)
    figure_ids = {
        f"{section.id}.figure.s{store.slot:02d}.{channel.replace('_', '-')}"
        for store in stores
        for channel in section.channels
    }
    table_required = _requested(table_id, requested_result_ids) or (
        requested_result_ids is not None and bool(figure_ids.intersection(requested_result_ids))
    )
    tables = (table,) if table_required else ()
    quantities = tuple(
        quantity
        for store in stores
        for quantity in _s2_quantities(section.id, store, evidence.identity.id)
        if _requested(quantity.id, requested_result_ids)
    )
    figures: list[ReportFigure] = []
    for store in stores:
        slot = f"s{store.slot:02d}"
        title_suffix = f"{slot} · {store.store_id[:12]}"
        for channel in section.channels:
            figure_id = f"{section.id}.figure.{slot}.{channel.replace('_', '-')}"
            if not _requested(figure_id, requested_result_ids):
                continue
            figure = s2_direction_figure(
                store.payload,
                channel=channel,
                template=theme.template,
                font_family=theme.font_family,
                surface_colorscale=theme.s2_surface_colorscale,
                rollout_colorscale=theme.s2_rollout_colorscale,
                title_suffix=title_suffix,
            )
            figures.append(
                ReportFigure(
                    id=figure_id,
                    plotly_json=canonical_plotly_json(figure),
                    source_ids=(evidence.identity.id,),
                    source_result_ids=(table_id,),
                    symbol_ids=_S2_FIGURE_SYMBOLS[channel],
                    uses_webgl=True,
                )
            )
    return _SectionResults(quantities=quantities, tables=tables, figures=tuple(figures))


_S2_SUPPORT_FIELDS = (
    "source_sample_count",
    "source_snippet_count",
    "source_scene_count",
    "target_count",
    "rollout_count",
    "store_rollout_count",
    "selected_step_count",
    "movement_count",
    "view_direction_count",
    "frustum_count",
    "frustum_missing_calibration_count",
    "movement_skipped_zero_count",
    "frustum_mean_fov_solid_angle_sr",
    "frustum_mean_target_surface_fraction_approx",
    "frustum_union_target_surface_fraction_approx",
)

_S2_FIGURE_SYMBOLS: dict[S2Channel, tuple[str, ...]] = {
    "movement": (
        "spatial.target_frame_motion_direction",
        "spatial.target_obb_scale",
        "rl.rollout_index",
    ),
    "view_direction": (
        "spatial.target_frame_view_direction",
        "rl.rollout_index",
    ),
    "frustum": (
        "spatial.target_frame_frustum",
        "spatial.target_frame_frustum_fraction",
        "spatial.frustum_solid_angle",
        "spatial.target_obb_scale",
        "rl.rollout_index",
    ),
}


def _s2_support_table(
    result_id: str,
    stores: tuple[_S2StoreEvidence, ...],
    source_id: str,
) -> ReportTable:
    columns = (
        ReportColumn("store_slot", None),
        ReportColumn("store_id", None),
        ReportColumn("payload_sha256", None),
        ReportColumn("azimuth_bins", None),
        ReportColumn("elevation_bins", None),
        ReportColumn("projection_limit", None),
        *(ReportColumn(field, _S2_COLUMN_SYMBOLS.get(field)) for field in _S2_SUPPORT_FIELDS),
        ReportColumn("issue_count", None),
    )
    rows = tuple(
        (
            f"s{store.slot:02d}",
            store.store_id,
            store.payload_sha256,
            store.azimuth_bins,
            store.elevation_bins,
            store.projection_limit,
            *(_scalar(store.payload[field]) for field in _S2_SUPPORT_FIELDS),
            len(store.payload["issues"]),
        )
        for store in stores
    )
    return ReportTable(id=result_id, columns=columns, rows=rows, source_ids=(source_id,))


_S2_COLUMN_SYMBOLS = {
    "frustum_mean_fov_solid_angle_sr": "spatial.frustum_solid_angle",
    "frustum_mean_target_surface_fraction_approx": "spatial.target_frame_frustum_fraction",
    "frustum_union_target_surface_fraction_approx": "spatial.target_frame_frustum_fraction",
}


def _s2_quantities(section_id: str, store: _S2StoreEvidence, source_id: str) -> tuple[NamedQuantity, ...]:
    slot = f"s{store.slot:02d}"
    specs = (
        ("source-sample-count", "source_sample_count", "count", "count", None, "source_sample_count"),
        ("source-snippet-count", "source_snippet_count", "count", "count", None, "source_snippet_count"),
        ("source-scene-count", "source_scene_count", "count", "count", None, "source_scene_count"),
        ("target-count", "target_count", "count", "count", None, "target_count"),
        ("rollout-count", "rollout_count", "count", "count", None, "store_rollout_count"),
        ("selected-step-count", "selected_step_count", "count", "count", None, "selected_step_count"),
        ("movement-count", "movement_count", "count", "count", None, "selected_step_count"),
        ("view-direction-count", "view_direction_count", "count", "count", None, "selected_step_count"),
        ("frustum-count", "frustum_count", "count", "count", None, "selected_step_count"),
        (
            "mean-frustum-solid-angle",
            "frustum_mean_fov_solid_angle_sr",
            "sr",
            "mean",
            "spatial.frustum_solid_angle",
            "frustum_count",
        ),
        (
            "mean-proxy-surface-fraction",
            "frustum_mean_target_surface_fraction_approx",
            "fraction",
            "mean",
            "spatial.target_frame_frustum_fraction",
            "frustum_count",
        ),
        (
            "union-proxy-surface-fraction",
            "frustum_union_target_surface_fraction_approx",
            "fraction",
            "union",
            "spatial.target_frame_frustum_fraction",
            "frustum_count",
        ),
    )
    return tuple(
        NamedQuantity(
            id=f"{section_id}.quantity.{slot}.{suffix}",
            value=_scalar(store.payload[field]),
            unit=unit,
            n=int(store.payload[support_field]),
            aggregation=aggregation,
            source_ids=(source_id,),
            symbol_id=symbol_id,
        )
        for suffix, field, unit, aggregation, symbol_id, support_field in specs
    )


def _resolved_store_paths(source: RolloutSourceConfig) -> tuple[Path, ...]:
    return tuple(sorted({path.expanduser().resolve() for path in source.store_paths}, key=Path.as_posix))


def _canonical_s2_payload(payload: dict[str, Any]) -> bytes:
    """Serialize one reducer result for immutable source identity."""

    def normalize(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): normalize(item) for key, item in sorted(value.items())}
        if isinstance(value, list | tuple):
            return [normalize(item) for item in value]
        if isinstance(value, np.ndarray):
            return normalize(value.tolist())
        if isinstance(value, np.generic):
            return value.item()
        return value

    return json.dumps(
        normalize(payload),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


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
