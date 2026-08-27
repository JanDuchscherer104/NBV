"""Deterministic pandas projections and JSON bundles for rollout evidence.

The module is a read-only adapter over :mod:`aria_nbv.rollouts.inspection`.
It gives Streamlit, thesis authoring, and offline analysis one stable table
contract without reimplementing rollout statistics or parsing Zarr arrays in
presentation code. Heavy candidate rows remain in the rollout store.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import pandas as pd

from .candidate_benchmark import CandidateBenchmarkBundle, read_bundle
from .inspection import (
    CANDIDATE_GROUP_FIELDS,
    SchemaValidation,
    build_compact_statistics,
    build_effective_streamlit_trust,
    build_manifest_facts,
    build_promotion_evidence,
    candidate_audit_rows,  # noqa: F401 - retained for direct consumer compatibility
    candidate_population_evidence,
    discounted_rollout_return_rows,
    oracle_headroom_evidence,
    q_h_evidence_rows,
    reconstruction_endpoint_rows,
    reconstruction_endpoint_summary_rows,
    reconstruction_metric_summary_rows,
    rollout_header_summary,
    rollout_step_objective_rows,
    rollout_tree_summary_rows,
    runtime_storage_statistics,
    selected_depth_summary_rows,
    suspicious_rollout_rows,
    target_audit_rows,
    validity_waterfall_rows,
)
from .zarr_store import RolloutZarrStoreReader, RolloutZarrValidationResult


def read_candidate_benchmark_bundle(
    path: Path | str, *, expected_binding: Mapping[str, str]
) -> CandidateBenchmarkBundle:
    """Read benchmark evidence through the canonical immutable reader."""

    return read_bundle(path, expected_binding=expected_binding)


def candidate_benchmark_report_frames(
    path: Path | str, *, expected_binding: Mapping[str, str]
) -> dict[str, pd.DataFrame]:
    """Project an immutable benchmark bundle into report-owned data frames.

    The bundle reader remains the sole authority for validation and DTO
    decoding.  This adapter is intentionally small so Typst/report exports
    consume exactly the same canonical records as the Streamlit inspector.
    """

    bundle = read_candidate_benchmark_bundle(path, expected_binding=expected_binding)
    records = [record.to_record() for record in bundle.records]
    families: list[dict[str, Any]] = []
    points: list[dict[str, Any]] = []
    for record in bundle.records:
        for family in record.families:
            families.append({"scene_key": record.scene_key, "state_key": record.state_key, **asdict(family)})
        for point in record.points:
            points.append({"scene_key": record.scene_key, **asdict(point)})
    return {
        "records": pd.DataFrame(records),
        "families": pd.DataFrame(families),
        "points": pd.DataFrame(points),
    }


class _ManifestSnapshotReader(RolloutZarrStoreReader):
    """Reader view that reuses one already-read manifest snapshot."""

    def __init__(self, reader: RolloutZarrStoreReader, manifest_payload: dict[str, Any]) -> None:
        self._reader = reader
        self._manifest_payload = manifest_payload
        self.store_dir = reader.store_dir

    def array(self, path: str) -> np.ndarray:
        """Read one array through the underlying fixed-generation reader."""

        return self._reader.array(path)

    def validate(self, *, validate_selected_depth_payload: bool = True) -> RolloutZarrValidationResult:
        """Validate through the underlying fixed-generation reader."""

        return self._reader.validate(validate_selected_depth_payload=validate_selected_depth_payload)

    def manifest(self) -> dict[str, Any]:
        """Return the fixed manifest snapshot for this report projection."""

        return self._manifest_payload

    def q_h_view(self, *, discount_gamma: float | None = None) -> dict[str, np.ndarray]:
        """Read the Q_H view through the underlying fixed-generation reader."""

        return self._reader.q_h_view(discount_gamma=discount_gamma)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._reader, name)


THESIS_REPORT_BUNDLE_VERSION = "aria-nbv-thesis-report-v1"
"""Schema version for compact thesis-report JSON bundles."""

THESIS_REPORT_BUNDLE_ROLE = "evidence"
"""Semantic role required by submission-facing Typst report consumers."""

ANALYSIS_FACT_SIDECAR_VERSION = "aria-nbv-analysis-facts-v1"
"""Schema version for sidecars that promote analysis outputs into facts."""

_ANALYSIS_FACT_SIDECAR_ROLE = "analysis_facts"
_ANALYSIS_FACT_FIELDS = frozenset({"store_id", "key", "value", "unit", "n", "aggregation", "provenance"})
_VALUE_COLUMNS = (
    "value_type",
    "value_bool",
    "value_int",
    "value_float",
    "value_text",
    "is_missing",
)

THESIS_REPORT_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "stores": (
        "store_id",
        "name",
        "manifest_sha256",
        "schema_version",
        "schema_id",
        "manifest_version",
        "created_at_utc",
        "validation_ok",
        "rollouts",
        "steps",
        "candidates",
        "targets",
        "sources",
        "split_manifest_hash",
        "source_offline_store_version",
    ),
    "parameters": ("store_id", "key", *_VALUE_COLUMNS),
    "statistics": ("store_id", "key", *_VALUE_COLUMNS),
    "facts": ("store_id", "key", "value", "unit", "n", "aggregation", "status", "source"),
    "source_coverage": ("store_id", "dimension", "value", "count"),
    "targets": (
        "store_id",
        "target_row_id",
        "target_id",
        "source",
        "source_index",
        "class",
        "sem_id",
        "inst_id",
        "confidence",
        "selection_rank",
        "selection_score",
        "selection_probability",
        "target_valid",
        "target_invalid_reason",
        "gt_label_valid",
        "gt_match_status",
        "gt_match_iou",
        "gt_match_score",
        "projected_area_pixels",
        "projected_area_fraction",
        "semidense_support",
        "evl_support",
        "effective_support",
        "visibility_score",
        "support_score",
        "deficit_score",
    ),
    "validity": ("store_id", "stage", "count", "fraction_of_full"),
    "candidate_composition": (
        "store_id",
        "group_by",
        "generation_cohort_id",
        "generation_cohort",
        "family",
        "allocated_count",
        "actor_valid_count",
        "oracle_valid_count",
        "trainable_count",
        "selected_count",
        "state_count",
        "scene_count",
        "macro_actor_valid_rate",
        "macro_oracle_valid_rate",
        "macro_trainable_rate",
        "macro_selected_rate",
        "aggregation",
    ),
    "candidate_calibration": (
        "store_id",
        "group_by",
        "generation_cohort_id",
        "generation_cohort",
        "family",
        "candidate_count",
        "finite_probability_count",
        "state_count",
        "scene_count",
        "empirical_denominator",
        "proposal_denominator",
        "selected_denominator",
        "proposal_available",
        "proposal_unavailable_reason",
        "population_empirical_frequency",
        "population_proposal_mass",
        "population_calibration_gap",
        "population_selected_share",
        "population_selection_enrichment",
        "empirical_frequency",
        "proposal_mass",
        "calibration_gap",
        "selected_share",
        "selection_enrichment",
        "aggregation",
    ),
    "candidate_collision_support": (
        "store_id",
        "generation_cohort_id",
        "generation_cohort",
        "candidate_count",
        "collision_available_count",
        "collision_evaluated_count",
        "collision_not_applicable_count",
        "collision_unavailable_count",
        "collision_count",
        "collision_denominator",
        "population_collision_rate",
        "collision_rate",
        "clearance_finite_count",
        "clearance_denominator",
        "population_clearance_mean_m",
        "clearance_mean_m",
        "state_count",
        "scene_count",
        "available",
        "reason",
    ),
    "q_h_evidence": (
        "store_id",
        "available",
        "blocking_reason",
        "deep_count",
        "view_role",
        "return_semantics",
        "td_semantics",
        "reward_metric",
        "discount_gamma",
        "state_count",
        "max_candidates",
        "actor_valid_count",
        "oracle_valid_count",
        "trainable_count",
        "padding_count",
        "counted_state_rows",
        "total_state_rows",
        "truncated",
        "count_reason",
    ),
    "candidate_groups": (
        "store_id",
        "group_by",
        "group",
        "total",
        "actor_valid",
        "actor_valid_fraction",
        "q_train",
        "selected",
        "mean_target_root_gain",
    ),
    "steps": (
        "store_id",
        "rollout_row_id",
        "step_row_id",
        "step_index",
        "chain_id",
        "scene",
        "split",
        "policy",
        "target_row_id",
        "horizon",
        "branch_factor",
        "beam_width",
        "temperature",
        "generation_cohort_id",
        "generation_cohort",
        "cumulative_target_rri",
        "marginal_target_rri",
        "cumulative_scene_rri",
        "cumulative_target_root_gain",
        "cumulative_scene_root_gain",
        "num_candidates",
        "num_valid_candidates",
        "invalid_fraction",
        "selected_candidate_row_id",
        "selected_target_rri",
        "selected_target_root_gain",
        "selected_scene_rri",
        "selected_probability",
        "selected_entropy",
        "selected_sampler_probability",
        "selected_strategy",
        "selected_position",
        "selected_mixture",
        "selected_invalid_reason",
    ),
    "rollout_tree": (
        "store_id",
        "policy",
        "horizon",
        "branch_factor",
        "beam_width",
        "temperature",
        "step_index",
        "step_label",
        "selected_position",
        "selected_strategy",
        "selected_mixture",
        "selected_steps",
        "mean_valid_fanout",
        "mean_invalid_fraction",
        "mean_marginal_target_rri",
        "mean_selected_target_root_gain",
        "mean_selected_probability",
        "mean_selected_entropy",
    ),
    "selected_depth": (
        "store_id",
        "rollout_row_id",
        "step_row_id",
        "step_index",
        "selected_candidate_row_id",
        "candidate_row_id",
        "available",
        "warning",
        "valid_pixels",
        "finite_pixels",
        "pixel_count",
        "valid_fraction",
        "finite_fraction",
        "depth_min_m",
        "depth_mean_m",
        "depth_max_m",
        "image_height",
        "image_width",
        "focal_x_px",
        "focal_y_px",
        "principal_x_px",
        "principal_y_px",
        "selected_position",
        "selected_strategy",
        "selected_mixture",
        "selected_target_root_gain",
        "selected_target_rri",
    ),
    "runtime_storage": (
        "store_id",
        "file_count",
        "total_bytes",
        "bytes_per_candidate",
        "bytes_per_candidate_reason",
        "file_count_limit",
        "bytes_per_candidate_limit",
        "status",
        "source",
    ),
    "rollout_header": (
        "store_id",
        "scenes",
        "targets",
        "rollouts",
        "candidate_rows",
        "source_rows",
        "reference_scene_count",
        "reference_scene_covered",
        "reference_scene_gap",
        "reference_scene_fraction",
        "reference_source_row_count",
        "reference_source_rows_covered",
        "reference_source_row_gap",
        "reference_source_row_fraction",
        "reference_coverage_reason",
        "logical_source_rows_json",
        "physical_store_bytes",
        "physical_bytes_per_rollout",
        "physical_bytes_per_candidate",
        "return_semantics",
        "discount_gamma",
    ),
    "reconstruction_metrics": (
        "store_id",
        "family",
        "metric",
        "label",
        "units",
        "row_count",
        "rollout_count",
        "finite_count",
        "missing_count",
        "mean",
        "std",
        "median",
        "q25",
        "q75",
        "min",
        "max",
        "endpoint_total_count",
        "endpoint_finite_count",
        "endpoint_missing_count",
        "endpoint_mean",
        "endpoint_std",
        "endpoint_median",
        "endpoint_q25",
        "endpoint_q75",
        "endpoint_min",
        "endpoint_max",
        "evidence_class",
        "metric_source",
        "endpoint_kind",
        "independent_endpoint_evaluation",
    ),
    "reconstruction_endpoints": (
        "store_id",
        "rollout_row_id",
        "scene",
        "policy",
        "horizon",
        "step_index",
        "cumulative_target_root_gain",
        "cumulative_target_rri",
        "selected_target_root_gain",
        "selected_target_rri",
        "selected_probability",
        "selected_entropy",
        "evidence_class",
        "metric_source",
        "endpoint_kind",
        "independent_endpoint_evaluation",
    ),
    "reconstruction_endpoint_summary": (
        "store_id",
        "policy",
        "horizon",
        "family",
        "metric",
        "label",
        "units",
        "total_count",
        "finite_count",
        "missing_count",
        "mean",
        "std",
        "median",
        "q25",
        "q75",
        "min",
        "max",
        "evidence_class",
        "metric_source",
        "endpoint_kind",
        "independent_endpoint_evaluation",
    ),
    "discounted_return": (
        "store_id",
        "rollout_row_id",
        "scene",
        "policy",
        "horizon",
        "discount_gamma",
        "discounted_return",
        "available",
        "reason",
        "contract_status",
        "factual_rollout_count",
    ),
    "oracle_headroom_contrasts": (
        "store_id",
        "contrast",
        "status",
        "exclusion_reason",
        "value",
        "headroom_denominator",
        "headroom_invariant_key",
        "scene",
        "normalized_conditions_json",
        "role_treatments_json",
        "evidence_class",
        "metric_source",
        "endpoint_kind",
        "independent_endpoint_evaluation",
    ),
    "oracle_headroom_summary": (
        "store_id",
        "contrast",
        "eligible_count",
        "included_count",
        "excluded_count",
        "exclusion_reason_counts_json",
        "scene_support",
        "evidence_class",
        "metric_source",
        "endpoint_kind",
        "independent_endpoint_evaluation",
    ),
    "failures": (
        "store_id",
        "kind",
        "severity",
        "rollout_row_id",
        "step_row_id",
        "candidate_row_id",
        "message",
        "status",
        "source",
    ),
    "sidecars": ("sidecar_id", "path", "name", "sha256", "format", "status"),
    "sidecar_values": ("sidecar_id", "key", *_VALUE_COLUMNS),
}
"""Stable table names and column order consumed by the thesis bundle."""

_FACT_SPECS = (
    ("candidate_validity.valid", "count", "candidate_validity.total", "count"),
    ("candidate_validity.total", "count", "candidate_validity.total", "count"),
    ("candidate_validity.fraction", "fraction", "candidate_validity.total", "fraction"),
    ("candidate_validity.valid_per_step.mean", "count", "candidate_validity.valid_per_step.count", "mean"),
    ("candidate_validity.valid_per_step.median", "count", "candidate_validity.valid_per_step.count", "median"),
    ("selected.total", "count", "selected.total", "count"),
    ("selected.path_length_m.mean", "m", "selected.path_length_m.count", "mean"),
    ("selected.path_length_m.median", "m", "selected.path_length_m.count", "median"),
    ("selected.path_length_m.p5", "m", "selected.path_length_m.count", "p5"),
    ("selected.path_length_m.p95", "m", "selected.path_length_m.count", "p95"),
)


@dataclass(frozen=True, slots=True)
class RolloutCorpusSummary:
    """Safe additive evidence across explicitly selected rollout stores."""

    verdict: Literal["Ready", "Incomplete", "Blocked"]
    """Whether every selected store contributed validated evidence."""

    selected_paths: tuple[Path, ...]
    """Normalized requested store paths in deterministic order."""

    included_stores: tuple[dict[str, Any], ...]
    """Validated store identities and profiles included in all totals."""

    excluded_stores: tuple[dict[str, str], ...]
    """Selected stores excluded with exact validation or projection reasons."""

    totals: dict[str, Any]
    """Additive store, rollout, storage, and complete deep-Q_H counts."""

    candidate_support: pd.DataFrame
    """Additive candidate support grouped by exact generation cohort and family."""

    endpoints: pd.DataFrame
    """Store-qualified diagnostic endpoint rows, preserving profile, policy, and horizon."""

    failure_counts: pd.DataFrame
    """Failure counts grouped only by kind and severity."""

    q_h_stores: pd.DataFrame
    """Per-store deep Q_H counts and any explicit unavailability reason."""

    temporal_summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    """Factual finite-only depth summaries, separated by persisted contract."""

    target_admission: pd.DataFrame = field(default_factory=pd.DataFrame)
    """Additive target-admission counts across validated stores."""

    feasibility: pd.DataFrame = field(default_factory=pd.DataFrame)
    """Additive collision and clearance availability evidence by exact cohort."""

    contract_totals: pd.DataFrame = field(default_factory=pd.DataFrame)
    """Deterministic additive totals faceted by persisted compatibility contract."""


def build_thesis_report_frames(
    store_paths: Iterable[Path | str],
    *,
    sidecar_paths: Iterable[Path | str] = (),
    evidence_status: Literal["pilot", "confirmatory"],
    table_names: Iterable[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Build deterministic named DataFrames from rollout stores and sidecars.

    Args:
        store_paths: Current-schema rollout Zarr stores. Every store is fully
            validated before its facts enter the report.
        sidecar_paths: Optional caller-selected JSON or JSONL evidence files.
            Selected paths are required to exist; missing files never disappear
            silently from provenance.
        evidence_status: Explicit scientific status for all projected facts.
            Callers must choose ``pilot`` or ``confirmatory``; file names and
            paths never determine this status.
        table_names: Optional output dependency closure. ``None`` preserves the
            complete report-v1 projection. The bounded ``stores``/``facts``
            reporting path may stop before unrelated target, tree, depth, and
            Q_H diagnostics while retaining full store admission.

    Returns:
        Mapping whose keys and columns exactly match
        :data:`THESIS_REPORT_TABLE_COLUMNS`. Config values, statistics, and
        sidecar leaves use typed long-form rows so missing values remain
        distinguishable from zero or an empty string.
    """

    if evidence_status not in {"pilot", "confirmatory"}:
        raise ValueError("evidence_status must be 'pilot' or 'confirmatory'.")
    required_tables = set(THESIS_REPORT_TABLE_COLUMNS) if table_names is None else set(table_names)
    unknown_tables = required_tables - set(THESIS_REPORT_TABLE_COLUMNS)
    if unknown_tables:
        raise ValueError(f"Unknown thesis report tables: {sorted(unknown_tables)}")
    rows: dict[str, list[dict[str, Any]]] = {name: [] for name in THESIS_REPORT_TABLE_COLUMNS}
    resolved_stores = sorted({Path(path).expanduser().resolve() for path in store_paths}, key=Path.as_posix)
    if not resolved_stores:
        raise ValueError("At least one rollout store is required to build thesis report frames.")
    for store_path in resolved_stores:
        _append_store_rows(
            rows,
            store_path,
            evidence_status=evidence_status,
            required_tables=required_tables,
        )
    for sidecar_path in sorted(
        {Path(path).expanduser().resolve() for path in sidecar_paths},
        key=Path.as_posix,
    ):
        _append_sidecar_rows(rows, sidecar_path, evidence_status=evidence_status)

    return {name: _frame(name, table_rows) for name, table_rows in rows.items()}


def build_rollout_corpus_summary(store_paths: Iterable[Path | str]) -> RolloutCorpusSummary:
    """Build safe multi-store counts without pooling scientific macro estimates.

    Every store first crosses the canonical report validation and promotion
    seam. Invalid selections remain visible in :attr:`excluded_stores`. Valid
    stores contribute additive counts, exact-cohort candidate support, raw
    store-qualified diagnostic endpoints, and grouped failure counts. Q_H mask
    totals are reported only when every included store completes the explicit
    deep count.
    """

    selected = tuple(sorted({Path(path).expanduser().resolve() for path in store_paths}, key=Path.as_posix))
    if not selected:
        raise ValueError("At least one rollout store is required to build a corpus summary.")

    included: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    valid_frames: list[dict[str, pd.DataFrame]] = []
    q_h_rows: list[dict[str, Any]] = []
    for path in selected:
        try:
            frames = build_thesis_report_frames((path,), evidence_status="pilot")
            store_row = frames["stores"].iloc[0]
            store_id = str(store_row["store_id"])
            profile = _report_profile(frames, store_id)
            contract = _persisted_rollout_contract(frames, store_id, profile)
            reader = RolloutZarrStoreReader(path)
            validation = reader.validate()
            q_h_row = q_h_evidence_rows(reader, deep_count=True, validation_result=validation)[0]
        except Exception as exc:
            excluded.append({"path": path.as_posix(), "reason": f"{type(exc).__name__}: {exc}"})
            continue
        included.append(
            {
                "path": path.as_posix(),
                "store_id": store_id,
                "name": str(store_row["name"]),
                "profile": profile,
                "contract_id": contract["id"],
                "contract": contract["label"],
                "contract_payload_json": json.dumps(contract["payload"], sort_keys=True, separators=(",", ":")),
            }
        )
        valid_frames.append(frames)
        q_h_rows.append(
            {
                "path": path.as_posix(),
                "store_id": store_id,
                "contract_id": contract["id"],
                "contract": contract["label"],
                "profile": contract["profile"],
                "contract_payload_json": json.dumps(contract["payload"], sort_keys=True, separators=(",", ":")),
                **q_h_row,
            }
        )

    stores = _concat_report_frames(valid_frames, "stores")
    runtime = _concat_report_frames(valid_frames, "runtime_storage")
    candidate = _candidate_corpus_support(_contract_frames(valid_frames, included, "candidate_composition"))
    endpoints = _corpus_endpoints(valid_frames, included)
    failures = _corpus_failure_counts(_contract_frames(valid_frames, included, "failures"))
    temporal = _corpus_temporal_summary(valid_frames, included)
    target_admission = _corpus_target_admission(_contract_frames(valid_frames, included, "targets"))
    feasibility = _corpus_feasibility(_contract_frames(valid_frames, included, "candidate_collision_support"))
    contract_totals = _contract_additive_totals(valid_frames, included, q_h_rows)
    q_h_stores = (
        pd.DataFrame(q_h_rows).sort_values(["store_id"], kind="stable").reset_index(drop=True)
        if q_h_rows
        else pd.DataFrame(
            columns=(
                "path",
                "store_id",
                "contract_id",
                "contract",
                "contract_payload_json",
                "profile",
                "available",
                "blocking_reason",
                "deep_count",
                "state_count",
                "trainable_count",
                "padding_count",
            )
        )
    )
    q_h_complete = bool(q_h_rows) and all(
        bool(row.get("available"))
        and bool(row.get("deep_count"))
        and not bool(row.get("truncated"))
        and all(_is_nonnegative_int(row.get(field)) for field in ("state_count", "trainable_count", "padding_count"))
        for row in q_h_rows
    )
    totals = {
        "selected_store_count": len(selected),
        "included_store_count": len(included),
        "excluded_store_count": len(excluded),
        "rollout_count": _frame_int_sum(stores, "rollouts"),
        "step_count": _frame_int_sum(stores, "steps"),
        "candidate_count": _frame_int_sum(stores, "candidates"),
        "target_row_count": _frame_int_sum(stores, "targets"),
        "source_row_count": _frame_int_sum(stores, "sources"),
        "physical_sample_count": _frame_int_sum(stores, "sources"),
        "storage_bytes": _frame_int_sum(runtime, "total_bytes"),
        "q_h_chain_count": _frame_int_sum(stores, "rollouts") if q_h_complete else None,
        "q_h_chain_available": q_h_complete,
        "q_h_chain_unavailable_reason": None if q_h_complete else "Q_H evidence unavailable or incomplete",
        "q_h_state_count": _row_int_sum(q_h_rows, "state_count") if q_h_complete else None,
        "q_h_trainable_count": _row_int_sum(q_h_rows, "trainable_count") if q_h_complete else None,
        "q_h_padding_count": _row_int_sum(q_h_rows, "padding_count") if q_h_complete else None,
    }
    verdict: Literal["Ready", "Incomplete", "Blocked"]
    if not included:
        verdict = "Blocked"
    elif excluded:
        verdict = "Incomplete"
    else:
        verdict = "Ready"
    return RolloutCorpusSummary(
        verdict=verdict,
        selected_paths=selected,
        included_stores=tuple(included),
        excluded_stores=tuple(excluded),
        totals=totals,
        candidate_support=candidate,
        endpoints=endpoints,
        failure_counts=failures,
        q_h_stores=q_h_stores,
        temporal_summary=temporal,
        target_admission=target_admission,
        feasibility=feasibility,
        contract_totals=contract_totals,
    )


def _report_profile(frames: Mapping[str, pd.DataFrame], store_id: str) -> str:
    """Return the first persisted writer-profile spelling for one store."""

    parameters = frames["parameters"]
    candidates = ("writer_config.profile", "writer_config.recipe_profile", "writer_config.name")
    for key in candidates:
        rows = parameters[(parameters["store_id"] == store_id) & (parameters["key"] == key)]
        if not rows.empty and isinstance(rows.iloc[0]["value_text"], str):
            return str(rows.iloc[0]["value_text"])
    binding = parameters[
        (parameters["store_id"] == store_id) & (parameters["key"] == "shard.campaign_binding.profile_hash")
    ]
    if not binding.empty and isinstance(binding.iloc[0]["value_text"], str):
        return f"profile_hash={str(binding.iloc[0]['value_text'])[:12]}"
    return "unknown"


def _corpus_temporal_summary(
    frames: list[dict[str, pd.DataFrame]],
    included: list[dict[str, Any]],
) -> pd.DataFrame:
    """Recompute factual depth summaries over compatible validated shards.

    Campaign shards combine only when their full persisted compatibility payload
    matches. Policy, temperature, and rollout controls stay as explicit plot
    strata rather than being pooled into a single trace.
    """

    columns = (
        "metric",
        "units",
        "contract_id",
        "contract",
        "contract_payload_json",
        "profile",
        "generation_cohort_id",
        "generation_series_id",
        "generation_series",
        "generation_cohort_ids_json",
        "generation_cohort_payloads_json",
        "policy",
        "temperature",
        "horizon",
        "branch_factor",
        "beam_width",
        "step_index",
        "store_count",
        "total_count",
        "finite_count",
        "missing_count",
        "median",
        "q25",
        "q75",
        "iqr_width",
        "mean",
        "min",
        "max",
    )
    annotated: list[pd.DataFrame] = []
    for bundle, store in zip(frames, included, strict=True):
        steps = bundle["steps"].copy()
        if steps.empty:
            continue
        contract = _persisted_rollout_contract(bundle, str(store["store_id"]), str(store["profile"]))
        # A content-derived ``store_id`` can legitimately be equal for two
        # separately selected shards in a reproducibility fixture. Corpus
        # presence is about the explicit physical selection, not that digest.
        steps["corpus_store_path"] = str(store["path"])
        steps["contract_id"] = contract["id"]
        steps["contract"] = contract["label"]
        steps["contract_payload_json"] = json.dumps(contract.get("payload", {}), sort_keys=True, separators=(",", ":"))
        steps["profile"] = contract["profile"]
        # Older report frames do not persist this optional cohort identity;
        # fall back to the exact contract so current shards still pool while
        # richer frames retain candidate/rollout lineage explicitly.
        if "generation_cohort_id" not in steps:
            steps["generation_cohort_id"] = contract["id"]
        if "generation_cohort" not in steps:
            steps["generation_cohort"] = steps["generation_cohort_id"].map(str)
        series_by_cohort: dict[str, tuple[str, str]] = {}
        for cohort_id, cohort_rows in steps.groupby("generation_cohort_id", dropna=False, sort=False):
            cohort_id = str(_temporal_group_scalar(cohort_id))
            cohort_json = cohort_rows.get("generation_cohort", pd.Series(dtype=object)).dropna()
            series_by_cohort[cohort_id] = _scientific_temporal_series_identity(
                bundle,
                store_id=str(store["store_id"]),
                contract=contract,
                cohort_id=cohort_id,
                cohort_payload=None if cohort_json.empty else str(cohort_json.iloc[0]),
            )

        def series_identity(value: Any, index: int, mapping: Mapping[str, tuple[str, str]] = series_by_cohort) -> str:
            return mapping[str(_temporal_group_scalar(value))][index]

        steps["generation_series_id"] = steps["generation_cohort_id"].map(lambda value: series_identity(value, 0))
        steps["generation_series"] = steps["generation_cohort_id"].map(lambda value: series_identity(value, 1))
        annotated.append(steps)
    if not annotated:
        return pd.DataFrame(columns=columns)

    from .inspection import temporal_metric_summary_rows

    source = pd.concat(annotated, ignore_index=True)
    groups = (
        "contract_id",
        "contract",
        "contract_payload_json",
        "profile",
        "generation_series_id",
        "policy",
        "temperature",
        "horizon",
        "branch_factor",
        "beam_width",
    )
    for group_field in groups:
        source[group_field] = source[group_field].map(_temporal_group_scalar)
    outer_groups = (
        "contract_id",
        "contract",
        "contract_payload_json",
        "profile",
        "generation_series_id",
        "generation_series",
    )
    inner_groups = (
        "policy",
        "temperature",
        "horizon",
        "branch_factor",
        "beam_width",
    )
    summaries: list[pd.DataFrame] = []
    for outer_key, partition in source.groupby(list(outer_groups), dropna=False, sort=True):
        outer_values: dict[str, Any] = dict(
            zip(outer_groups, outer_key if isinstance(outer_key, tuple) else (outer_key,), strict=True)
        )
        partition_records = cast(list[Mapping[str, Any]], partition.to_dict("records"))
        cohort_ids = sorted({str(value) for value in partition["generation_cohort_id"].dropna()})
        cohort_payloads = {
            str(row["generation_cohort_id"]): row.get("generation_cohort")
            for row in partition[["generation_cohort_id", "generation_cohort"]].drop_duplicates().to_dict("records")
        }
        store_counts = (
            partition.groupby([*inner_groups, "step_index"], dropna=False, sort=True)["corpus_store_path"]
            .nunique()
            .rename("store_count")
            .reset_index()
        )
        for metric in (
            "cumulative_target_root_gain",
            "selected_target_root_gain",
            "selected_probability",
            "selected_entropy",
            "cumulative_target_rri",
            "valid_fanout",
            "invalid_fraction",
        ):
            rows = temporal_metric_summary_rows(partition_records, metric=metric, group_fields=inner_groups)
            if not rows:
                continue
            frame = pd.DataFrame(rows).merge(
                store_counts,
                on=[*inner_groups, "step_index"],
                how="left",
                validate="one_to_one",
            )
            for outer_field, value in outer_values.items():
                frame[outer_field] = value
            frame["generation_cohort_id"] = cohort_ids[0] if len(cohort_ids) == 1 else "multiple"
            frame["generation_cohort_ids_json"] = json.dumps(cohort_ids, separators=(",", ":"))
            frame["generation_cohort_payloads_json"] = json.dumps(
                cohort_payloads, sort_keys=True, separators=(",", ":"), default=str
            )
            frame["store_count"] = frame["store_count"].astype(np.int64)
            frame["iqr_width"] = frame["q75"] - frame["q25"]
            summaries.append(cast(pd.DataFrame, frame.loc[:, columns]))
    if not summaries:
        return pd.DataFrame(columns=columns)
    return (
        pd.concat(summaries, ignore_index=True)
        .sort_values(
            ["metric", "contract_id", "generation_series_id", "policy", "temperature", "horizon", "step_index"],
            kind="stable",
        )
        .reset_index(drop=True)
    )


def _scientific_temporal_series_identity(
    frames: Mapping[str, pd.DataFrame],
    *,
    store_id: str,
    contract: Mapping[str, Any],
    cohort_id: str,
    cohort_payload: str | None,
) -> tuple[str, str]:
    """Build a temporal-series identity while retaining stochastic provenance.

    ``generation_cohort_id`` is deliberately a full provenance identity and
    may differ for every work-unit seed.  Temporal statistics may pool those
    cohorts only when the persisted recipe payload is available and agrees
    after stochastic fields are removed.  Missing recipe evidence therefore
    fails closed to the full cohort rather than silently pooling unknown
    configurations.
    """

    parameters = frames.get("parameters", pd.DataFrame())
    recipe_rows = parameters[
        (parameters.get("store_id", pd.Series(dtype=object)) == store_id)
        & parameters.get("key", pd.Series(dtype=str)).astype(str).str.startswith("writer_config.recipes[")
    ]

    def scalar(row: pd.Series) -> Any:
        for value_field in ("value_text", "value_float", "value_int", "value_bool"):
            value = row.get(value_field)
            if pd.notna(value):
                return value.item() if isinstance(value, np.generic) else value
        return None

    def semantic_key(key: str) -> str | None:
        # Seeds, RNG/work-unit identifiers, and execution-only controls are
        # provenance, not scientific recipe choices.
        leaf = key.rsplit(".", 1)[-1].lower()
        volatile = ("seed", "rng", "random", "work_unit", "sample_key", "store_dir", "path")
        return None if any(token in leaf for token in volatile) else key

    recipe_payload = {
        str(row["key"]): scalar(row) for _, row in recipe_rows.iterrows() if semantic_key(str(row["key"])) is not None
    }
    cohort_fields: dict[str, Any]
    try:
        parsed = json.loads(cohort_payload) if cohort_payload else None
    except (TypeError, json.JSONDecodeError):
        parsed = None
    if not recipe_payload or not isinstance(parsed, dict):
        # Full cohort fallback is the conservative behavior for legacy or
        # incomplete stores.
        payload = {"generation_cohort_id": cohort_id, "reason": "recipe_payload_unavailable"}
    else:
        cohort_fields = {
            key: parsed.get(key)
            for key in (
                "policy",
                "horizon",
                "branch_factor",
                "beam_width",
                "temperature",
                "candidate_config",
                "branch_schedule",
            )
        }
        payload = {
            "contract": contract.get("payload", {}),
            "cohort": cohort_fields,
            "recipe": recipe_payload,
        }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16], encoded


def _persisted_rollout_contract(frames: Mapping[str, pd.DataFrame], store_id: str, profile: str) -> dict[str, Any]:
    """Return the exact persisted compatibility contract for one store.

    The human label is intentionally compact, but the identity is derived from
    every persisted parameter that can change the meaning of a report row.  In
    particular, two shards with the same display profile are not pooled when a
    target protocol, source/split lineage, Q_H/return contract, or selected
    depth modality differs.
    """

    parameters = frames["parameters"]

    def values(key: str) -> tuple[Any, ...]:
        rows = parameters[
            (parameters["store_id"] == store_id)
            & ((parameters["key"] == key) | parameters["key"].str.startswith(f"{key}["))
        ]
        output: list[Any] = []
        for _, row in rows.iterrows():
            for column in ("value_text", "value_float", "value_int", "value_bool"):
                candidate = row[column]
                if pd.notna(candidate):
                    output.append(candidate.item() if isinstance(candidate, np.generic) else candidate)
                    break
        return tuple(output)

    def value(key: str) -> Any:
        return values(key)[0] if values(key) else None

    # Compatibility is semantic, not work-unit identity.  In particular,
    # rollout/source/split hashes, seeds, sample keys, temporary store paths,
    # and recipe controls are intentionally excluded: they vary across shards
    # while the persisted scientific contract remains comparable.
    config_hash_suffixes = {
        "candidate",
        "oracle",
        "target_crop_policy",
        "target_protocol",
    }
    volatile_tokens = ("seed", "path", "paths", "store_dir", "sample_keys", "verbosity", "is_debug", "device")
    writer_semantic_prefixes = (
        "writer_config.candidate_mixture.",
        "writer_config.store.",
        "writer_config.target_scorer.",
    )
    writer_excluded_suffixes = {
        "writer_config.store.split_manifest_hash",
        "writer_config.store.store_dir",
        "writer_config.store.paths",
    }
    root_attr_suffixes = {
        "schema_id",
        "schema_version",
        "target_protocol_version",
        "reason_code_version",
        "return_semantics",
        "discount_gamma",
        "q_h_return_semantics",
        "q_h_reward_metric",
        "q_h_td_semantics",
        "q_h_horizon",
        "q_h_max_candidates",
        "q_h_view_role",
        "view_role",
        "source_offline_store_version",
        "source_split",
        "campaign_split",
        "q_h_source_tables",
        "q_h_view_persisted",
        "selected_depth_enabled",
        "selected_depth_role",
        "selected_depth_renderer",
        "selected_depth_source_resolution",
        "selected_depth_units",
        "selected_depth_dtype",
        "selected_depth_width_px",
        "selected_depth_height_px",
        "selected_depth_znear_m",
        "selected_depth_zfar_m",
        "selected_depth_invalid_fill_value",
        "selected_depth_valid_mask_dtype",
        "selected_depth_codec",
    }

    def json_value(row: pd.Series) -> Any:
        for column in ("value_text", "value_float", "value_int", "value_bool"):
            candidate = row[column]
            if pd.notna(candidate):
                candidate = candidate.item() if isinstance(candidate, np.generic) else candidate
                if isinstance(candidate, float) and not math.isfinite(candidate):
                    return str(candidate)
                return candidate
        return None

    exact_rows: list[dict[str, Any]] = []
    for _, row in parameters[parameters["store_id"] == store_id].iterrows():
        key = str(row["key"])
        root_attr_key = key.removeprefix("root_attrs.")
        config_hash_key = key.removeprefix("config_hashes.")
        is_config_hash = key.startswith("config_hashes.") and any(
            config_hash_key == suffix or config_hash_key.startswith(f"{suffix}[") for suffix in config_hash_suffixes
        )
        is_writer_semantic = key.startswith(writer_semantic_prefixes) and key not in writer_excluded_suffixes
        if is_writer_semantic and any(token in key for token in volatile_tokens):
            is_writer_semantic = False
        is_root_attr = key.startswith("root_attrs.") and root_attr_key in root_attr_suffixes
        if key == "store_id" or not (is_config_hash or is_writer_semantic or is_root_attr):
            continue
        exact_rows.append({"key": key, "value": json_value(row)})
    exact_rows.sort(key=lambda item: (str(item["key"]), json.dumps(item["value"], sort_keys=True, default=str)))
    payload: dict[str, Any] = {"profile": profile, "parameters": exact_rows}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    candidate_configs = values("config_hashes.candidate")
    return {
        "id": hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16],
        "profile": profile,
        "payload": payload,
        "label": (f"{profile} · candidate {str(candidate_configs[0] if candidate_configs else 'unknown')[:12]}"),
    }


def _temporal_group_scalar(value: Any) -> Any:
    """Match the inspection owner's explicit unknown-group normalization."""

    return "unknown" if value is None or (not isinstance(value, str) and bool(pd.isna(value))) else value


def _concat_report_frames(frames: list[dict[str, pd.DataFrame]], name: str) -> pd.DataFrame:
    """Concatenate one canonical report table in deterministic row order."""

    if not frames:
        return pd.DataFrame(columns=THESIS_REPORT_TABLE_COLUMNS[name])
    return (
        pd.concat([bundle[name] for bundle in frames], ignore_index=True)
        .sort_values(list(THESIS_REPORT_TABLE_COLUMNS[name]), kind="stable", na_position="last")
        .reset_index(drop=True)
    )


def _contract_frames(
    frames: list[dict[str, pd.DataFrame]],
    included: list[dict[str, Any]],
    name: str,
) -> pd.DataFrame:
    """Attach persisted contract identity before any corpus grouping."""

    annotated: list[pd.DataFrame] = []
    for bundle, store in zip(frames, included, strict=True):
        frame = bundle[name].copy()
        if frame.empty:
            continue
        store_id = str(store["store_id"])
        contract = _persisted_rollout_contract(bundle, store_id, str(store["profile"]))
        frame["corpus_store_path"] = str(store["path"])
        frame.insert(1, "contract_id", contract["id"])
        frame.insert(2, "contract", contract["label"])
        frame.insert(3, "profile", contract["profile"])
        frame["contract_payload_json"] = json.dumps(contract["payload"], sort_keys=True, separators=(",", ":"))
        annotated.append(frame)
    if not annotated:
        return pd.DataFrame()
    return pd.concat(annotated, ignore_index=True)


def _contract_additive_totals(
    frames: list[dict[str, pd.DataFrame]],
    included: list[dict[str, Any]],
    q_h_rows: list[dict[str, Any]],
) -> pd.DataFrame:
    """Return additive physical totals without pooling incompatible contracts."""

    columns = (
        "contract_id",
        "contract",
        "contract_payload_json",
        "profile",
        "store_count",
        "rollout_count",
        "step_count",
        "candidate_count",
        "target_row_count",
        "source_row_count",
        "storage_bytes",
        "q_h_chain_count",
        "q_h_chain_available",
        "q_h_chain_unavailable_reason",
        "q_h_state_count",
        "q_h_trainable_count",
        "q_h_padding_count",
    )
    if not frames:
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, Any]] = []
    for bundle, store in zip(frames, included, strict=True):
        stores = bundle["stores"]
        runtime = bundle["runtime_storage"]
        store_row: Mapping[str, Any] = cast(dict[str, Any], stores.iloc[0].to_dict()) if not stores.empty else {}
        runtime_row: Mapping[str, Any] = cast(dict[str, Any], runtime.iloc[0].to_dict()) if not runtime.empty else {}
        store_path = store.get("path")
        q_h = next(
            (
                row
                for row in q_h_rows
                if store_path is not None and row.get("path") is not None and str(row["path"]) == str(store_path)
            ),
            next((row for row in q_h_rows if row["store_id"] == store["store_id"]), {}),
        )
        q_h_counts_available = all(
            _is_nonnegative_int(q_h.get(field)) for field in ("state_count", "trainable_count", "padding_count")
        )
        q_h_chain_available = (
            bool(q_h.get("available"))
            and bool(q_h.get("deep_count"))
            and not bool(q_h.get("truncated"))
            and q_h_counts_available
        )
        rows.append(
            {
                "contract_id": store["contract_id"],
                "contract": store["contract"],
                "contract_payload_json": store.get("contract_payload_json", "{}"),
                "profile": store["profile"],
                "store_count": 1,
                "rollout_count": int(store_row.get("rollouts", 0)),
                "step_count": int(store_row.get("steps", 0)),
                "candidate_count": int(store_row.get("candidates", 0)),
                "target_row_count": int(store_row.get("targets", 0)),
                "source_row_count": int(store_row.get("sources", 0)),
                "storage_bytes": int(runtime_row.get("total_bytes", 0)),
                "q_h_chain_count": int(store_row.get("rollouts", 0)) if q_h_chain_available else None,
                "q_h_chain_available": q_h_chain_available,
                "q_h_chain_unavailable_reason": None
                if q_h_chain_available
                else q_h.get("blocking_reason", "Q_H evidence unavailable or incomplete"),
                "q_h_state_count": _optional_qh_count(q_h, "state_count") if q_h_chain_available else None,
                "q_h_trainable_count": _optional_qh_count(q_h, "trainable_count") if q_h_chain_available else None,
                "q_h_padding_count": _optional_qh_count(q_h, "padding_count") if q_h_chain_available else None,
            }
        )
    source = pd.DataFrame(rows)
    additive: dict[str, Any] = {
        field: (field, "sum")
        for field in columns[4:]
        if field
        not in {
            "store_count",
            "q_h_chain_available",
            "q_h_chain_unavailable_reason",
            "q_h_state_count",
            "q_h_trainable_count",
            "q_h_padding_count",
        }
    }
    for field_name in ("q_h_state_count", "q_h_trainable_count", "q_h_padding_count"):
        additive[field_name] = (field_name, lambda values: values.sum(min_count=1))
    additive["q_h_chain_count"] = ("q_h_chain_count", lambda values: values.sum(min_count=1))
    grouped = cast(
        pd.DataFrame,
        source.groupby(["contract_id", "contract", "contract_payload_json", "profile"], dropna=False, sort=True)
        .agg(store_count=("store_count", "sum"), **additive)
        .reset_index(),
    )
    contract_keys = ["contract_id", "contract", "contract_payload_json", "profile"]
    availability = (
        source.groupby(contract_keys, dropna=False, sort=True)["q_h_chain_available"]
        .all()
        .reset_index(name="q_h_chain_available")
    )
    grouped = grouped.drop(columns="q_h_chain_available", errors="ignore").merge(
        availability, on=contract_keys, how="left", validate="one_to_one"
    )
    reason_rows: list[dict[str, Any]] = []
    for contract_key, partition in source.groupby(contract_keys, dropna=False, sort=True):
        key_values = contract_key if isinstance(contract_key, tuple) else (contract_key,)
        reasons_for_contract = tuple(
            sorted(
                {
                    str(value)
                    for value in partition["q_h_chain_unavailable_reason"].tolist()
                    if pd.notna(value) and str(value)
                }
            )
        )
        reason_rows.append(
            {
                **dict(zip(contract_keys, key_values, strict=True)),
                "_q_h_reasons": reasons_for_contract,
            }
        )
    reasons = pd.DataFrame(reason_rows)
    grouped = grouped.merge(reasons, on=contract_keys, how="left", validate="one_to_one")
    grouped["q_h_chain_unavailable_reason"] = [_q_h_unavailable_reason(row) for _, row in grouped.iterrows()]
    unavailable = ~grouped["q_h_chain_available"].astype(bool)
    grouped.loc[
        unavailable,
        [
            "q_h_chain_count",
            "q_h_state_count",
            "q_h_trainable_count",
            "q_h_padding_count",
        ],
    ] = None
    grouped = grouped.drop(columns="_q_h_reasons")
    result = cast(pd.DataFrame, grouped.loc[:, columns])
    return result.sort_values("contract_id", kind="stable").reset_index(drop=True)


def _q_h_unavailable_reason(row: pd.Series[Any]) -> str | None:
    """Return the aggregate reason for one exact-contract Q_H row."""

    if bool(row["q_h_chain_available"]):
        return None
    reasons = cast(tuple[str, ...], row["_q_h_reasons"])
    return "; ".join(reasons) or "Q_H evidence unavailable or incomplete"


def _optional_qh_count(row: Mapping[str, Any], field: str) -> int | None:
    """Keep unavailable deep counts distinct from an observed zero."""

    value = row.get(field)
    if not _is_nonnegative_int(value):
        return None
    assert isinstance(value, int | np.integer)
    return int(value)


def _candidate_corpus_support(composition: pd.DataFrame) -> pd.DataFrame:
    """Recompute additive family support from exact generation cohorts."""

    columns = (
        "contract_id",
        "contract",
        "contract_payload_json",
        "profile",
        "generation_cohort_id",
        "generation_cohort",
        "family",
        "store_count",
        "allocated_count",
        "actor_valid_count",
        "oracle_valid_count",
        "trainable_count",
        "selected_count",
        "actor_valid_rate",
        "oracle_valid_rate",
        "trainable_rate",
        "selected_rate",
        "aggregation",
    )
    if composition.empty:
        return pd.DataFrame(columns=columns)
    if "group_by" not in composition:
        raise ValueError("Candidate composition rows require group_by.")
    source = composition[composition["group_by"] == "mixture"].copy()
    if source.empty:
        return pd.DataFrame(columns=columns)
    if "corpus_store_path" not in source:
        source["corpus_store_path"] = source["store_id"]
    count_columns = (
        "allocated_count",
        "actor_valid_count",
        "oracle_valid_count",
        "trainable_count",
        "selected_count",
    )
    for column in count_columns:
        source[column] = pd.to_numeric(source[column], errors="coerce").fillna(0).astype(np.int64)
    grouped = (
        source.groupby(
            ["contract_id", "contract", "contract_payload_json", "profile", "generation_cohort_id", "family"],
            dropna=False,
            sort=True,
        )
        .agg(
            generation_cohort=("generation_cohort", "first"),
            store_count=("corpus_store_path", "nunique"),
            **{column: (column, "sum") for column in count_columns},
        )
        .reset_index()
    )
    allocated = grouped["allocated_count"].replace(0, np.nan)
    grouped["actor_valid_rate"] = grouped["actor_valid_count"] / allocated
    grouped["oracle_valid_rate"] = grouped["oracle_valid_count"] / allocated
    grouped["trainable_rate"] = grouped["trainable_count"] / allocated
    grouped["selected_rate"] = grouped["selected_count"] / allocated
    grouped["aggregation"] = "additive counts within exact generation cohort and family"
    result = cast(pd.DataFrame, grouped.loc[:, columns])
    return result.sort_values(
        ["contract_id", "generation_cohort_id", "family"], kind="stable", na_position="last"
    ).reset_index(drop=True)


def _corpus_target_admission(targets: pd.DataFrame) -> pd.DataFrame:
    """Count target-admission outcomes without translating invalidity into RRI."""

    columns = (
        "contract_id",
        "contract",
        "contract_payload_json",
        "profile",
        "target_valid",
        "gt_label_valid",
        "gt_match_status",
        "count",
        "store_count",
    )
    if targets.empty:
        return pd.DataFrame(columns=columns)
    targets = targets.copy()
    if "corpus_store_path" not in targets:
        targets["corpus_store_path"] = targets["store_id"]
    result = cast(
        pd.DataFrame,
        targets.groupby(
            [
                "contract_id",
                "contract",
                "contract_payload_json",
                "profile",
                "target_valid",
                "gt_label_valid",
                "gt_match_status",
            ],
            dropna=False,
            sort=True,
        )
        .agg(count=("target_row_id", "size"), store_count=("corpus_store_path", "nunique"))
        .reset_index()
        .loc[:, columns],
    )
    return result


def _corpus_feasibility(collision: pd.DataFrame) -> pd.DataFrame:
    """Recompute only additive collision and clearance denominators by cohort."""

    columns = (
        "contract_id",
        "contract",
        "contract_payload_json",
        "profile",
        "generation_cohort_id",
        "generation_cohort",
        "store_count",
        "candidate_count",
        "collision_evaluated_count",
        "collision_count",
        "collision_rate",
        "clearance_finite_count",
        "clearance_denominator",
        "clearance_coverage",
    )
    if collision.empty:
        return pd.DataFrame(columns=columns)
    count_columns = (
        "candidate_count",
        "collision_evaluated_count",
        "collision_count",
        "clearance_finite_count",
        "clearance_denominator",
    )
    source = collision.copy()
    if "corpus_store_path" not in source:
        source["corpus_store_path"] = source["store_id"]
    for column in count_columns:
        source[column] = pd.to_numeric(source[column], errors="coerce").fillna(0).astype(np.int64)
    grouped = (
        source.groupby(
            [
                "contract_id",
                "contract",
                "contract_payload_json",
                "profile",
                "generation_cohort_id",
                "generation_cohort",
            ],
            dropna=False,
            sort=True,
        )
        .agg(store_count=("corpus_store_path", "nunique"), **{column: (column, "sum") for column in count_columns})
        .reset_index()
    )
    grouped["collision_rate"] = grouped["collision_count"] / grouped["collision_evaluated_count"].replace(0, np.nan)
    grouped["clearance_coverage"] = grouped["clearance_finite_count"] / grouped["clearance_denominator"].replace(
        0, np.nan
    )
    return cast(pd.DataFrame, grouped.loc[:, columns])


def _corpus_endpoints(
    frames: list[dict[str, pd.DataFrame]],
    included: list[dict[str, Any]],
) -> pd.DataFrame:
    """Retain raw diagnostic endpoints with store and exact contract identity."""

    rows: list[pd.DataFrame] = []
    for bundle, store in zip(frames, included, strict=True):
        frame = bundle["reconstruction_endpoints"].copy()
        contract = _persisted_rollout_contract(bundle, str(store["store_id"]), str(store["profile"]))
        frame.insert(1, "store_path", str(store["path"]))
        frame.insert(2, "profile", str(store["profile"]))
        frame.insert(3, "contract_id", contract["id"])
        frame.insert(4, "contract", contract["label"])
        frame.insert(
            5,
            "contract_payload_json",
            json.dumps(contract.get("payload", {}), sort_keys=True, separators=(",", ":")),
        )
        rows.append(frame)
    columns = (
        "store_id",
        "store_path",
        "profile",
        "contract_id",
        "contract",
        "contract_payload_json",
        *THESIS_REPORT_TABLE_COLUMNS["reconstruction_endpoints"][1:],
    )
    if not rows:
        return pd.DataFrame(columns=columns)
    result = cast(pd.DataFrame, pd.concat(rows, ignore_index=True).loc[:, columns])
    return result.sort_values(
        ["contract_id", "policy", "horizon", "store_id", "rollout_row_id"],
        kind="stable",
        na_position="last",
    ).reset_index(drop=True)


def _corpus_failure_counts(failures: pd.DataFrame) -> pd.DataFrame:
    """Count suspicious rows by kind and severity without pooling causes."""

    columns = (
        "contract_id",
        "contract",
        "contract_payload_json",
        "profile",
        "kind",
        "severity",
        "count",
        "store_count",
    )
    if failures.empty:
        return pd.DataFrame(columns=columns)
    failures = failures.copy()
    if "corpus_store_path" not in failures:
        failures["corpus_store_path"] = failures["store_id"]
    result = cast(
        pd.DataFrame,
        failures.groupby(
            ["contract_id", "contract", "contract_payload_json", "profile", "kind", "severity"],
            dropna=False,
            sort=True,
        )
        .agg(count=("message", "size"), store_count=("corpus_store_path", "nunique"))
        .reset_index()
        .loc[:, columns],
    )
    return result


def _frame_int_sum(frame: pd.DataFrame, column: str) -> int:
    """Sum one canonical nonnegative count column, treating no rows as zero."""

    if frame.empty:
        return 0
    values = pd.to_numeric(frame[column], errors="raise")
    if values.isna().any() or (values < 0).any():
        raise ValueError(f"Corpus count column {column!r} must contain nonnegative integers.")
    return int(values.sum())


def _row_int_sum(rows: list[dict[str, Any]], field: str) -> int:
    """Sum a deep-Q_H count after completeness has been proven."""

    return sum(int(row[field]) for row in rows)


def _is_nonnegative_int(value: Any) -> bool:
    """Return whether a value is a factual nonnegative integer count."""

    return isinstance(value, int | np.integer) and not isinstance(value, bool) and int(value) >= 0


def serialize_thesis_report_bundle(
    frames: Mapping[str, pd.DataFrame],
    *,
    candidate_benchmark_path: Path | str | None = None,
    candidate_benchmark_binding: Mapping[str, str] | None = None,
) -> bytes:
    """Serialize report frames as strict, compact, byte-stable JSON.

    The serializer rejects missing or extra tables, column drift, and infinite
    floats. Pandas and NumPy missing scalars become JSON ``null``. It adds no
    build timestamp, so identical frames produce identical bytes.
    """

    _validate_frame_schema(frames)
    benchmark_attachment = None
    if candidate_benchmark_path is not None:
        if candidate_benchmark_binding is None:
            raise ValueError("candidate_benchmark_binding is required with candidate_benchmark_path")
        benchmark_attachment = {
            name: json.loads(frame.to_json(orient="records", date_format="iso", double_precision=15))
            for name, frame in candidate_benchmark_report_frames(
                candidate_benchmark_path, expected_binding=candidate_benchmark_binding
            ).items()
        }
    elif candidate_benchmark_binding is not None:
        raise ValueError("candidate_benchmark_path is required with candidate_benchmark_binding")
    tables: dict[str, dict[str, Any]] = {}
    for name, columns in THESIS_REPORT_TABLE_COLUMNS.items():
        frame = frames[name]
        records = [
            {
                column: _json_scalar(value, table=name, column=column)
                for column, value in zip(columns, values, strict=True)
            }
            for values in frame.itertuples(index=False, name=None)
        ]
        tables[name] = {"columns": list(columns), "rows": records}
    payload = {
        "bundle_role": THESIS_REPORT_BUNDLE_ROLE,
        "schema_version": THESIS_REPORT_BUNDLE_VERSION,
        "tables": tables,
    }
    if benchmark_attachment is not None:
        payload["candidate_benchmark"] = benchmark_attachment
    return (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def write_thesis_report_bundle(
    path: Path | str,
    frames: Mapping[str, pd.DataFrame],
    *,
    candidate_benchmark_path: Path | str | None = None,
    candidate_benchmark_binding: Mapping[str, str] | None = None,
) -> str:
    """Atomically write a thesis-report bundle and return its SHA-256 digest."""

    output_path = Path(path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = serialize_thesis_report_bundle(
        frames,
        candidate_benchmark_path=candidate_benchmark_path,
        candidate_benchmark_binding=candidate_benchmark_binding,
    )
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    temporary.write_bytes(data)
    temporary.replace(output_path)
    return hashlib.sha256(data).hexdigest()


def _append_store_rows(
    rows: dict[str, list[dict[str, Any]]],
    store_path: Path,
    *,
    evidence_status: Literal["pilot", "confirmatory"],
    required_tables: set[str],
) -> None:
    reader = RolloutZarrStoreReader(store_path)
    validation = reader.validate()
    if not validation.ok:
        detail = "; ".join(validation.errors[:3]) or "unknown validation error"
        raise ValueError(f"Rollout store {store_path} failed validation: {detail}")
    schema = SchemaValidation(
        ok=bool(validation.ok),
        num_rollouts=int(validation.num_rollouts),
        num_steps=int(validation.num_steps),
        num_candidates=int(validation.num_candidates),
        errors=tuple(str(error) for error in validation.errors),
    )
    manifest_payload = build_manifest_facts(reader).payload
    promotion = build_promotion_evidence(reader, manifest_payload=manifest_payload)
    trust = build_effective_streamlit_trust(schema, promotion)
    if not trust.ok:
        detail = "; ".join(trust.errors[:3]) or "unknown promotion error"
        raise ValueError(f"Rollout store {store_path} failed promotion validation: {detail}")
    reader = _ManifestSnapshotReader(reader, manifest_payload)
    manifest = manifest_payload.get("manifest", {})
    root_attrs = manifest_payload.get("root_attrs", {})
    manifest_sha256 = str(root_attrs["manifest_sha256"])
    store_id = manifest_sha256
    counts = manifest.get("counts", {}) if isinstance(manifest, dict) else {}
    rows["stores"].append(
        {
            "store_id": store_id,
            "name": store_path.name,
            "manifest_sha256": manifest_sha256,
            "schema_version": root_attrs.get("schema_version"),
            "schema_id": root_attrs.get("schema_id"),
            "manifest_version": manifest.get("manifest_version"),
            "created_at_utc": manifest.get("created_at_utc"),
            "validation_ok": True,
            "rollouts": counts.get("rollouts"),
            "steps": counts.get("steps"),
            "candidates": counts.get("candidates"),
            "targets": counts.get("targets"),
            "sources": counts.get("sources"),
            "split_manifest_hash": root_attrs.get("split_manifest_hash"),
            "source_offline_store_version": root_attrs.get("source_offline_store_version"),
        }
    )

    generation = manifest.get("generation", {}) if isinstance(manifest, dict) else {}
    parameter_root_attrs = dict(root_attrs)
    discount_gamma = root_attrs.get("discount_gamma")
    parameter_root_attrs["discount_gamma"] = (
        float(discount_gamma)
        if isinstance(discount_gamma, (int, float, np.integer, np.floating))
        and not isinstance(discount_gamma, bool)
        and np.isfinite(discount_gamma)
        else None
    )
    parameter_payload = {
        "writer_config": generation.get("writer_config") if isinstance(generation, dict) else None,
        "invocation": _without_raw_toml(generation.get("invocation")) if isinstance(generation, dict) else None,
        "runtime": generation.get("runtime") if isinstance(generation, dict) else None,
        "shard": generation.get("shard") if isinstance(generation, dict) else None,
        "config_hashes": manifest.get("config_hashes") if isinstance(manifest, dict) else None,
        "root_attrs": parameter_root_attrs,
    }
    rows["parameters"].extend(_typed_leaf_rows("store_id", store_id, parameter_payload))
    stats = build_compact_statistics(reader, manifest_payload=manifest_payload).payload
    rows["statistics"].extend(_typed_leaf_rows("store_id", store_id, stats))
    rows["facts"].extend(_fact_rows(store_id, stats, evidence_status=evidence_status))
    rows["source_coverage"].extend(_source_coverage_rows(store_id, stats.get("source_coverage", {})))
    shallow_tables = {"stores", "parameters", "statistics", "facts", "source_coverage"}
    if required_tables.issubset(shallow_tables):
        return
    rows["targets"].extend(_with_store_id(store_id, target_audit_rows(reader)))
    rows["validity"].extend(_with_store_id(store_id, validity_waterfall_rows(reader)))
    step_rows = rollout_step_objective_rows(reader)
    rows["steps"].extend(_with_store_id(store_id, step_rows))
    rows["rollout_tree"].extend(_with_store_id(store_id, rollout_tree_summary_rows(reader, step_rows=step_rows)))
    rows["selected_depth"].extend(_with_store_id(store_id, selected_depth_summary_rows(reader, limit=None)))
    storage = runtime_storage_statistics(store_path, candidate_count=int(counts.get("candidates") or 0))
    rows["runtime_storage"].append(
        {
            "store_id": store_id,
            **{
                key: storage[key]
                for key in (
                    "file_count",
                    "total_bytes",
                    "bytes_per_candidate",
                    "bytes_per_candidate_reason",
                    "file_count_limit",
                    "bytes_per_candidate_limit",
                )
            },
            "status": evidence_status,
            "source": "inspection.runtime_storage_statistics",
        }
    )
    header = rollout_header_summary(reader, manifest_payload=manifest_payload)
    rows["rollout_header"].append(
        {
            "store_id": store_id,
            **{key: value for key, value in header.items() if key != "logical_source_rows"},
            "logical_source_rows_json": json.dumps(
                header["logical_source_rows"], sort_keys=True, separators=(",", ":")
            ),
        }
    )
    reconstruction_provenance = {
        "evidence_class": "diagnostic_proxy",
        "metric_source": "rollout_step_objective_rows",
        "endpoint_kind": "persisted_chain_terminal_step",
        "independent_endpoint_evaluation": False,
    }
    rows["reconstruction_metrics"].extend(
        _with_store_id(
            store_id,
            [{**row, **reconstruction_provenance} for row in reconstruction_metric_summary_rows(step_rows)],
        )
    )
    rows["reconstruction_endpoints"].extend(
        _with_store_id(
            store_id,
            [{**row, **reconstruction_provenance} for row in reconstruction_endpoint_rows(step_rows)],
        )
    )
    rows["reconstruction_endpoint_summary"].extend(
        _with_store_id(
            store_id,
            [{**row, **reconstruction_provenance} for row in reconstruction_endpoint_summary_rows(step_rows)],
        )
    )
    discounted = discounted_rollout_return_rows(
        step_rows,
        return_semantics=root_attrs.get("return_semantics"),
        discount_gamma=root_attrs.get("discount_gamma"),
    )
    discounted_rows = list(discounted["rows"])
    if not discounted_rows:
        discounted_rows = [
            {
                "rollout_row_id": None,
                "scene": None,
                "policy": None,
                "horizon": None,
                "discount_gamma": root_attrs.get("discount_gamma"),
                "discounted_return": None,
                "available": False,
                "reason": discounted.get("reason"),
            }
        ]
    rows["discounted_return"].extend(
        _with_store_id(
            store_id,
            [
                {
                    **row,
                    "contract_status": "available" if discounted.get("available") else "unavailable",
                    "factual_rollout_count": len(
                        {r.get("rollout_row_id") for r in step_rows if r.get("rollout_row_id") is not None}
                    ),
                }
                for row in discounted_rows
            ],
        )
    )
    headroom = oracle_headroom_evidence(reader)
    rows["oracle_headroom_contrasts"].extend(
        {
            "store_id": store_id,
            **{key: value for key, value in row.items() if key not in {"normalized_conditions", "role_treatments"}},
            "normalized_conditions_json": json.dumps(
                row["normalized_conditions"], sort_keys=True, separators=(",", ":")
            ),
            "role_treatments_json": json.dumps(row["role_treatments"], sort_keys=True, separators=(",", ":")),
            "evidence_class": headroom.get("evidence_status"),
            "metric_source": headroom.get("metric_source"),
            "endpoint_kind": headroom.get("endpoint_kind"),
            "independent_endpoint_evaluation": headroom.get("independent_endpoint_evaluation"),
        }
        for row in headroom["contrast_rows"]
    )
    rows["oracle_headroom_summary"].extend(
        {
            "store_id": store_id,
            **{key: value for key, value in row.items() if key != "exclusion_reason_counts"},
            "exclusion_reason_counts_json": json.dumps(
                row["exclusion_reason_counts"], sort_keys=True, separators=(",", ":")
            ),
            "evidence_class": headroom.get("evidence_status"),
            "metric_source": headroom.get("metric_source"),
            "endpoint_kind": headroom.get("endpoint_kind"),
            "independent_endpoint_evaluation": headroom.get("independent_endpoint_evaluation"),
        }
        for row in headroom["summary_rows"]
    )
    rows["failures"].extend(
        {
            "store_id": store_id,
            **failure,
            "status": evidence_status,
            "source": "inspection.suspicious_rollout_rows",
        }
        for failure in suspicious_rollout_rows(reader)
    )
    candidate_evidence = candidate_population_evidence(
        reader,
        scientific_support=False,
        audit_reader=candidate_audit_rows,
    )
    for group_by in CANDIDATE_GROUP_FIELDS:
        rows["candidate_composition"].extend(_with_store_id(store_id, candidate_evidence["composition"][group_by]))
        rows["candidate_calibration"].extend(_with_store_id(store_id, candidate_evidence["calibration"][group_by]))
    rows["candidate_collision_support"].extend(_with_store_id(store_id, candidate_evidence["collision"]))
    rows["q_h_evidence"].extend(_with_store_id(store_id, q_h_evidence_rows(reader, validation_result=validation)))
    for group_by in CANDIDATE_GROUP_FIELDS:
        for group_row in candidate_evidence["groups"][group_by]:
            group = group_row.pop(group_by)
            rows["candidate_groups"].append({"store_id": store_id, "group_by": group_by, "group": group, **group_row})


def _append_sidecar_rows(
    rows: dict[str, list[dict[str, Any]]],
    sidecar_path: Path,
    *,
    evidence_status: Literal["pilot", "confirmatory"],
) -> None:
    if not sidecar_path.is_file():
        raise FileNotFoundError(sidecar_path)
    data = sidecar_path.read_bytes()
    suffix = sidecar_path.suffix.lower()
    if suffix == ".json":
        payload: Any = json.loads(data)
        format_name = "json"
    elif suffix == ".jsonl":
        payload = [json.loads(line) for line in data.splitlines() if line.strip()]
        format_name = "jsonl"
    else:
        raise ValueError(f"Unsupported report sidecar format for {sidecar_path}; expected .json or .jsonl.")
    digest = hashlib.sha256(data).hexdigest()
    logical_name = _sidecar_logical_name(payload, fallback=sidecar_path.name)
    sidecar_id = hashlib.sha256(f"{logical_name}\0{digest}".encode()).hexdigest()
    if any(row["sidecar_id"] == sidecar_id for row in rows["sidecars"]):
        return
    promoted = _analysis_fact_rows(
        payload,
        sidecar_id=sidecar_id,
        evidence_status=evidence_status,
        known_store_ids={str(row["store_id"]) for row in rows["stores"]},
    )
    existing_fact_sources = {(str(row["store_id"]), str(row["key"])): str(row["source"]) for row in rows["facts"]}
    for fact in promoted:
        identity = (str(fact["store_id"]), str(fact["key"]))
        if identity in existing_fact_sources:
            raise ValueError(
                f"Analysis fact {identity[1]!r} for store {identity[0]!r} conflicts with "
                f"{existing_fact_sources[identity]!r}."
            )
        existing_fact_sources[identity] = str(fact["source"])
    rows["sidecars"].append(
        {
            "sidecar_id": sidecar_id,
            "path": logical_name,
            "name": logical_name,
            "sha256": digest,
            "format": format_name,
            "status": evidence_status,
        }
    )
    rows["sidecar_values"].extend(_typed_leaf_rows("sidecar_id", sidecar_id, payload))
    rows["facts"].extend(promoted)


def _sidecar_logical_name(payload: Any, *, fallback: str) -> str:
    if not isinstance(payload, dict) or payload.get("bundle_role") != _ANALYSIS_FACT_SIDECAR_ROLE:
        return fallback
    logical_name = payload.get("logical_name", fallback)
    if not isinstance(logical_name, str) or not logical_name.strip():
        raise ValueError("Analysis sidecar logical_name must be a non-empty string.")
    if logical_name != Path(logical_name).name or "\\" in logical_name:
        raise ValueError("Analysis sidecar logical_name must not contain a directory path.")
    return logical_name


def _analysis_fact_rows(
    payload: Any,
    *,
    sidecar_id: str,
    evidence_status: Literal["pilot", "confirmatory"],
    known_store_ids: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    role = payload.get("bundle_role")
    schema_version = payload.get("schema_version")
    if role != _ANALYSIS_FACT_SIDECAR_ROLE:
        if schema_version == ANALYSIS_FACT_SIDECAR_VERSION:
            raise ValueError(f"Analysis sidecar bundle_role must be {_ANALYSIS_FACT_SIDECAR_ROLE!r}.")
        return []
    if schema_version != ANALYSIS_FACT_SIDECAR_VERSION:
        raise ValueError(
            f"Analysis sidecar schema_version must be {ANALYSIS_FACT_SIDECAR_VERSION!r}; received {schema_version!r}."
        )
    expected_fields = {"schema_version", "bundle_role", "logical_name", "status", "facts"}
    required_fields = expected_fields - {"logical_name"}
    actual_fields = set(payload)
    if not required_fields.issubset(actual_fields) or not actual_fields.issubset(expected_fields):
        raise ValueError(
            f"Analysis sidecar fields must be {sorted(required_fields)} with optional logical_name; "
            f"received {sorted(actual_fields)}."
        )
    if payload["status"] != evidence_status:
        raise ValueError(
            f"Analysis sidecar status {payload['status']!r} does not match export status {evidence_status!r}."
        )
    facts = payload["facts"]
    if not isinstance(facts, list) or not facts:
        raise ValueError("Analysis sidecar facts must be a non-empty list.")

    output: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict) or set(fact) != _ANALYSIS_FACT_FIELDS:
            actual = sorted(fact) if isinstance(fact, dict) else type(fact).__name__
            raise ValueError(
                f"Analysis sidecar fact {index} fields must be {sorted(_ANALYSIS_FACT_FIELDS)}; received {actual}."
            )
        store_id = _required_text(fact["store_id"], field="store_id", index=index)
        if store_id not in known_store_ids:
            raise ValueError(f"Analysis sidecar fact {index} references unknown store_id {store_id!r}.")
        key = _required_text(fact["key"], field="key", index=index)
        identity = (store_id, key)
        if identity in identities:
            raise ValueError(f"Analysis sidecar contains duplicate fact {key!r} for store {store_id!r}.")
        identities.add(identity)
        value = _fact_scalar(fact["value"], index=index)
        n = fact["n"]
        if isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise ValueError(f"Analysis sidecar fact {index} n must be a non-negative integer.")
        unit = _required_text(fact["unit"], field="unit", index=index)
        aggregation = _required_text(fact["aggregation"], field="aggregation", index=index)
        provenance = _required_text(fact["provenance"], field="provenance", index=index)
        output.append(
            {
                "store_id": store_id,
                "key": key,
                "value": value,
                "unit": unit,
                "n": n,
                "aggregation": aggregation,
                "status": evidence_status,
                "source": f"{provenance}|sidecar:{sidecar_id}",
            }
        )
    return output


def _required_text(value: Any, *, field: str, index: int) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"Analysis sidecar fact {index} {field} must be a non-empty trimmed string.")
    return value


def _fact_scalar(value: Any, *, index: int) -> bool | int | float | str | None:
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"Analysis sidecar fact {index} value must be finite.")
        return value
    raise TypeError(f"Analysis sidecar fact {index} value must be a JSON scalar; received {type(value).__name__}.")


def _typed_leaf_rows(owner_key: str, owner: str, payload: Any) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for key, value in _flatten_leaves(payload):
        output.append({owner_key: owner, "key": key, **_typed_value(value)})
    return output


def _fact_rows(
    store_id: str,
    statistics: dict[str, Any],
    *,
    evidence_status: Literal["pilot", "confirmatory"],
) -> list[dict[str, Any]]:
    return [
        {
            "store_id": store_id,
            "key": key,
            "value": _nested_value(statistics, key),
            "unit": unit,
            "n": _nested_value(statistics, n_key),
            "aggregation": aggregation,
            "status": evidence_status,
            "source": "inspection.rollout_statistics",
        }
        for key, unit, n_key, aggregation in _FACT_SPECS
    ]


def _nested_value(payload: dict[str, Any], dotted_key: str) -> Any:
    value: Any = payload
    for part in dotted_key.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _flatten_leaves(payload: Any, *, prefix: str = "") -> list[tuple[str, Any]]:
    if isinstance(payload, dict):
        output: list[tuple[str, Any]] = []
        for key in sorted(payload, key=str):
            child = f"{prefix}.{key}" if prefix else str(key)
            output.extend(_flatten_leaves(payload[key], prefix=child))
        return output
    if isinstance(payload, list | tuple):
        output = []
        for index, value in enumerate(payload):
            child = f"{prefix}[{index}]"
            output.extend(_flatten_leaves(value, prefix=child))
        return output
    return [(prefix or "value", payload)]


def _typed_value(value: Any) -> dict[str, Any]:
    output = dict.fromkeys(_VALUE_COLUMNS[:-1])
    output["is_missing"] = value is None
    if value is None:
        output["value_type"] = "null"
    elif isinstance(value, bool | np.bool_):
        output["value_type"] = "bool"
        output["value_bool"] = bool(value)
    elif isinstance(value, int | np.integer):
        output["value_type"] = "int"
        output["value_int"] = int(value)
    elif isinstance(value, float | np.floating):
        if not math.isfinite(float(value)):
            raise ValueError("Report inputs contain a non-finite numeric value.")
        output["value_type"] = "float"
        output["value_float"] = float(value)
    elif isinstance(value, str):
        output["value_type"] = "str"
        output["value_text"] = value
    else:
        raise TypeError(f"Unsupported report leaf type {type(value).__name__}.")
    return output


def _source_coverage_rows(store_id: str, coverage: Any) -> list[dict[str, Any]]:
    if not isinstance(coverage, dict):
        return []
    output: list[dict[str, Any]] = []
    for key, value in sorted(coverage.items()):
        if not key.endswith("_counts") or not isinstance(value, dict):
            continue
        dimension = key.removesuffix("_counts")
        output.extend(
            {
                "store_id": store_id,
                "dimension": dimension,
                "value": str(label),
                "count": int(count),
            }
            for label, count in sorted(value.items(), key=lambda item: str(item[0]))
        )
    return output


def _with_store_id(store_id: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"store_id": store_id, **record} for record in records]


def _without_raw_toml(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    return {key: value for key, value in payload.items() if key != "raw_toml_text"}


def _frame(name: str, rows: list[dict[str, Any]]) -> pd.DataFrame:
    columns = THESIS_REPORT_TABLE_COLUMNS[name]
    frame = pd.DataFrame(rows, columns=columns)
    if frame.empty:
        return frame
    return frame.sort_values(list(columns), kind="stable", na_position="last").reset_index(drop=True)


def _validate_frame_schema(frames: Mapping[str, pd.DataFrame]) -> None:
    expected_names = tuple(THESIS_REPORT_TABLE_COLUMNS)
    actual_names = tuple(frames)
    if set(actual_names) != set(expected_names):
        raise ValueError(f"Report tables must be exactly {expected_names}; received {actual_names}.")
    for name, columns in THESIS_REPORT_TABLE_COLUMNS.items():
        actual_columns = tuple(frames[name].columns)
        if actual_columns != columns:
            raise ValueError(f"Report table {name!r} columns must be {columns}; received {actual_columns}.")


def _json_scalar(value: Any, *, table: str, column: str) -> Any:
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if not math.isfinite(value):
            raise ValueError(f"Report table {table!r} column {column!r} contains a non-finite value.")
        return value
    if isinstance(value, bool | int | str):
        return value
    if bool(pd.isna(value)):
        return None
    raise TypeError(f"Report table {table!r} column {column!r} contains unsupported {type(value).__name__}.")


__all__ = [
    "ANALYSIS_FACT_SIDECAR_VERSION",
    "RolloutCorpusSummary",
    "THESIS_REPORT_BUNDLE_ROLE",
    "THESIS_REPORT_BUNDLE_VERSION",
    "THESIS_REPORT_TABLE_COLUMNS",
    "build_rollout_corpus_summary",
    "build_thesis_report_frames",
    "candidate_benchmark_report_frames",
    "serialize_thesis_report_bundle",
    "write_thesis_report_bundle",
]
