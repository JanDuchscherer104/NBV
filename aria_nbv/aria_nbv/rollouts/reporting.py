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
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Literal, cast

import numpy as np
import pandas as pd

from .inspection import (
    CANDIDATE_GROUP_FIELDS,
    candidate_audit_rows,  # noqa: F401 - retained for direct consumer compatibility
    candidate_population_evidence,
    discounted_rollout_return_rows,
    oracle_headroom_evidence,
    promoted_store_validation_error,
    q_h_evidence_rows,
    reconstruction_endpoint_rows,
    reconstruction_endpoint_summary_rows,
    reconstruction_metric_summary_rows,
    rollout_header_summary,
    rollout_statistics,
    rollout_step_objective_rows,
    rollout_tree_summary_rows,
    runtime_storage_statistics,
    selected_depth_summary_rows,
    suspicious_rollout_rows,
    target_audit_rows,
    validity_waterfall_rows,
)
from .zarr_store import RolloutZarrStoreReader

THESIS_REPORT_BUNDLE_VERSION = "aria-nbv-thesis-report-v2"
"""Schema version for compact thesis-report JSON bundles."""

THESIS_REPORT_BUNDLE_ROLE = "evidence"
"""Semantic role required by submission-facing Typst report consumers."""

ANALYSIS_FACT_SIDECAR_VERSION = "aria-nbv-analysis-facts-v2"
"""Schema version for sidecars that promote analysis outputs into facts."""

_ANALYSIS_FACT_SIDECAR_ROLE = "analysis_facts"
_ANALYSIS_FACT_FIELDS = frozenset({"store_id", "key", "value", "unit", "n", "aggregation", "provenance"})
_EMPIRICAL_RESULT_FIELDS = frozenset(
    {
        "result_id",
        "store_id",
        "experimental_unit",
        "denominator_name",
        "denominator_value",
        "data_identity",
        "split_identity",
        "estimand",
        "estimate",
        "unit",
        "aggregation",
        "uncertainty_type",
        "uncertainty_lower",
        "uncertainty_upper",
        "uncertainty_inapplicable_reason",
        "variability_source",
        "comparison_family",
        "outcome",
        "status",
        "actor_visible_inputs_json",
        "oracle_only_inputs_json",
        "source_revision",
        "environment",
        "command",
        "artifact_path",
        "artifact_sha256",
        "wall_time_s",
        "gpu_hours",
        "peak_gpu_memory_bytes",
        "storage_bytes",
        "provenance",
        "sidecar_id",
        "reason",
    }
)
_EVIDENCE_STATUSES = frozenset({"exploratory", "pilot", "confirmatory"})
_OUTCOMES = frozenset({"supporting", "negative", "failed", "missing"})
_GIT_OID = re.compile(r"^[0-9a-f]{40}$")
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
    "empirical_results": (
        "result_id",
        "store_id",
        "experimental_unit",
        "denominator_name",
        "denominator_value",
        "data_identity",
        "split_identity",
        "estimand",
        "estimate",
        "unit",
        "aggregation",
        "uncertainty_type",
        "uncertainty_lower",
        "uncertainty_upper",
        "uncertainty_inapplicable_reason",
        "variability_source",
        "comparison_family",
        "outcome",
        "status",
        "actor_visible_inputs_json",
        "oracle_only_inputs_json",
        "source_revision",
        "environment",
        "command",
        "artifact_path",
        "artifact_sha256",
        "wall_time_s",
        "gpu_hours",
        "peak_gpu_memory_bytes",
        "storage_bytes",
        "provenance",
        "sidecar_id",
        "reason",
    ),
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


def build_thesis_report_frames(
    store_paths: Iterable[Path | str],
    *,
    sidecar_paths: Iterable[Path | str] = (),
    evidence_status: Literal["exploratory", "pilot", "confirmatory"],
) -> dict[str, pd.DataFrame]:
    """Build deterministic named DataFrames from rollout stores and sidecars.

    Args:
        store_paths: Current-schema rollout Zarr stores. Every store is fully
            validated before its facts enter the report.
        sidecar_paths: Optional caller-selected JSON or JSONL evidence files.
            Selected paths are required to exist; missing files never disappear
            silently from provenance.
        evidence_status: Explicit scientific status for all projected facts.
            Callers must choose ``exploratory``, ``pilot``, or ``confirmatory``; file names and
            paths never determine this status.

    Returns:
        Mapping whose keys and columns exactly match
        :data:`THESIS_REPORT_TABLE_COLUMNS`. Config values, statistics, and
        sidecar leaves use typed long-form rows so missing values remain
        distinguishable from zero or an empty string.
    """

    if evidence_status not in _EVIDENCE_STATUSES:
        raise ValueError("evidence_status must be 'exploratory', 'pilot', or 'confirmatory'.")
    rows: dict[str, list[dict[str, object]]] = {name: [] for name in THESIS_REPORT_TABLE_COLUMNS}
    resolved_stores = sorted({Path(path).expanduser().resolve() for path in store_paths}, key=Path.as_posix)
    if not resolved_stores:
        raise ValueError("At least one rollout store is required to build thesis report frames.")
    for store_path in resolved_stores:
        _append_store_rows(rows, store_path, evidence_status=evidence_status)
    for sidecar_path in sorted(
        {Path(path).expanduser().resolve() for path in sidecar_paths},
        key=Path.as_posix,
    ):
        _append_sidecar_rows(rows, sidecar_path, evidence_status=evidence_status)
    frames = {name: _frame(name, table_rows) for name, table_rows in rows.items()}
    _validate_empirical_bundle(frames)
    return frames


def serialize_thesis_report_bundle(frames: Mapping[str, pd.DataFrame]) -> bytes:
    """Serialize report frames as strict, compact, byte-stable JSON.

    The serializer rejects missing or extra tables, column drift, and infinite
    floats. Pandas and NumPy missing scalars become JSON ``null``. It adds no
    build timestamp, so identical frames produce identical bytes.
    """

    _validate_frame_schema(frames)
    _validate_bundle_statuses(frames)
    _validate_empirical_bundle(frames)
    source_revision = _bundle_source_revision(frames)
    tables: dict[str, dict[str, object]] = {}
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
        "source_revision": source_revision,
        "tables": tables,
    }
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


def deserialize_thesis_report_bundle(
    payload: bytes | str | Mapping[str, object],
) -> dict[str, pd.DataFrame]:
    """Deserialize and validate a serialized thesis report bundle.

    The inverse boundary accepts only the producer's exact envelope and table
    contracts.  It reconstructs object-typed frames so JSON nulls and scalar
    types remain distinguishable, then applies the same status, store-identity,
    and empirical-bundle validators used by serialization.
    """

    if isinstance(payload, bytes | str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as error:
            raise ValueError("Serialized thesis report bundle must be valid JSON.") from error
    if not isinstance(payload, Mapping):
        raise ValueError("Serialized thesis report bundle must be a JSON object.")

    schema_version = payload.get("schema_version")
    if schema_version != THESIS_REPORT_BUNDLE_VERSION:
        raise ValueError(f"Unsupported thesis report schema_version: {schema_version!r}.")
    expected_keys = {"bundle_role", "schema_version", "source_revision", "tables"}
    if set(payload) != expected_keys:
        raise ValueError(
            f"Thesis report top-level fields must be exactly {sorted(expected_keys)}; received {sorted(payload)}."
        )
    if payload.get("bundle_role") != THESIS_REPORT_BUNDLE_ROLE:
        raise ValueError("Thesis report bundle_role must be 'evidence'.")
    source_revision = payload["source_revision"]
    if source_revision is not None and (
        not isinstance(source_revision, str) or not _GIT_OID.fullmatch(source_revision) or source_revision == "0" * 40
    ):
        raise ValueError("Thesis report source_revision must be null or a full nonzero Git OID.")

    tables = payload.get("tables")
    if not isinstance(tables, Mapping) or set(tables) != set(THESIS_REPORT_TABLE_COLUMNS):
        raise ValueError("Thesis report tables must contain exactly the producer table names.")
    frames: dict[str, pd.DataFrame] = {}
    for name, columns in THESIS_REPORT_TABLE_COLUMNS.items():
        table = tables[name]
        if not isinstance(table, Mapping) or set(table) != {"columns", "rows"}:
            raise ValueError(f"Thesis report table {name!r} must contain only columns and rows.")
        if table["columns"] != list(columns):
            raise ValueError(f"Thesis report table {name!r} columns do not match the producer schema.")
        rows = table["rows"]
        if not isinstance(rows, list):
            raise ValueError(f"Thesis report table {name!r} rows must be a list.")
        normalized: list[dict[str, object]] = []
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping) or set(row) != set(columns):
                raise ValueError(f"Thesis report table {name!r} row {index} keys do not match its columns.")
            for column in columns:
                value = row[column]
                if value is not None and not isinstance(value, bool | int | float | str):
                    raise ValueError(
                        f"Thesis report table {name!r} row {index} column {column!r} must be a JSON scalar."
                    )
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError(f"Thesis report table {name!r} row {index} column {column!r} must be finite.")
            normalized.append(dict(row))
        frames[name] = pd.DataFrame(normalized, columns=columns, dtype=object)

    _validate_frame_schema(frames)
    _validate_bundle_statuses(frames)
    _validate_empirical_bundle(frames)
    if _bundle_source_revision(frames) != source_revision:
        raise ValueError("Thesis report source_revision does not match empirical results.")
    return frames


validate_thesis_report_bundle = deserialize_thesis_report_bundle


def validate_thesis_report_provenance(
    payload: bytes | str | Mapping[str, object] | Mapping[str, pd.DataFrame],
    *,
    evidence_root: Path | str,
    expected_source_revision: str | None = None,
) -> dict[str, pd.DataFrame]:
    """Validate a report bundle and revalidate its immutable evidence files.

    ``evidence_root`` contains the portable logical paths serialized for
    sidecars.  Empirical artifacts are resolved relative to each sidecar's
    parent directory.  The returned frames are the validated report owner
    representation suitable for release or thesis consumption.
    """

    if isinstance(payload, Mapping) and all(isinstance(value, pd.DataFrame) for value in payload.values()):
        frames = cast(dict[str, pd.DataFrame], dict(payload))
        _validate_frame_schema(frames)
        _validate_bundle_statuses(frames)
        _validate_empirical_bundle(frames)
        source_revision = _bundle_source_revision(frames)
    else:
        frames = deserialize_thesis_report_bundle(payload)
        source_revision = _bundle_source_revision(frames)
    if expected_source_revision is not None:
        if (
            not _GIT_OID.fullmatch(expected_source_revision)
            or expected_source_revision == "0" * 40
            or source_revision != expected_source_revision
        ):
            raise ValueError("Thesis report source_revision does not match expected_source_revision.")

    root = Path(evidence_root).expanduser().resolve()
    sidecar_files: dict[str, Path] = {}
    for index, row in frames["sidecars"].iterrows():
        logical_path = _portable_relative_path(row["path"], field=f"sidecars row {index} path")
        if row["name"] != row["path"]:
            raise ValueError(f"sidecars row {index} path and name must match.")
        sidecar_file = (root / logical_path).resolve()
        if not sidecar_file.is_relative_to(root) or not sidecar_file.is_file():
            raise ValueError(f"sidecar evidence does not exist under evidence_root: {row['path']!r}.")
        digest = hashlib.sha256(sidecar_file.read_bytes()).hexdigest()
        if digest != row["sha256"]:
            raise ValueError(f"sidecar row {index} sha256 does not match immutable evidence.")
        expected_id = hashlib.sha256(f"{row['path']}\0{row['sha256']}".encode()).hexdigest()
        if row["sidecar_id"] != expected_id or row["sidecar_id"] in sidecar_files:
            raise ValueError(f"sidecar row {index} sidecar_id relationship is invalid.")
        sidecar_files[str(row["sidecar_id"])] = sidecar_file

    for index, row in frames["empirical_results"].iterrows():
        artifact_parent = sidecar_files.get(str(row["sidecar_id"]))
        if artifact_parent is None:
            raise ValueError(f"empirical result row {index} references an unknown sidecar_id.")
        artifact_path = _portable_relative_path(row["artifact_path"], field=f"empirical row {index} artifact_path")
        artifact_file = (artifact_parent.parent / artifact_path).resolve()
        if not artifact_file.is_relative_to(artifact_parent.parent) or not artifact_file.is_file():
            raise ValueError(f"empirical result row {index} artifact does not exist.")
        if hashlib.sha256(artifact_file.read_bytes()).hexdigest() != row["artifact_sha256"]:
            raise ValueError(f"empirical result row {index} artifact_sha256 does not match immutable evidence.")
    return frames


def write_thesis_report_bundle(path: Path | str, frames: Mapping[str, pd.DataFrame]) -> str:
    """Atomically write a thesis-report bundle and return its SHA-256 digest."""

    output_path = Path(path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = serialize_thesis_report_bundle(frames)
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    temporary.write_bytes(data)
    temporary.replace(output_path)
    return hashlib.sha256(data).hexdigest()


def _append_store_rows(
    rows: dict[str, list[dict[str, object]]],
    store_path: Path,
    *,
    evidence_status: Literal["exploratory", "pilot", "confirmatory"],
) -> None:
    reader = RolloutZarrStoreReader(store_path)
    validation = reader.validate()
    if not validation.ok:
        detail = "; ".join(validation.errors[:3]) or "unknown validation error"
        raise ValueError(f"Rollout store {store_path} failed validation: {detail}")
    manifest_payload = reader.manifest()
    if promotion_error := promoted_store_validation_error(reader, manifest_payload=manifest_payload):
        raise ValueError(f"Rollout store {store_path} failed promotion validation: {promotion_error}")
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
    stats = rollout_statistics(reader, manifest_payload=manifest_payload)
    rows["statistics"].extend(_typed_leaf_rows("store_id", store_id, stats))
    rows["facts"].extend(_fact_rows(store_id, stats, evidence_status=evidence_status))
    rows["source_coverage"].extend(_source_coverage_rows(store_id, stats.get("source_coverage", {})))
    rows["targets"].extend(_with_store_id(store_id, target_audit_rows(reader)))
    rows["validity"].extend(_with_store_id(store_id, validity_waterfall_rows(reader)))
    step_rows = rollout_step_objective_rows(reader)
    rows["steps"].extend(_with_store_id(store_id, step_rows))
    rows["rollout_tree"].extend(_with_store_id(store_id, rollout_tree_summary_rows(reader)))
    rows["selected_depth"].extend(_with_store_id(store_id, selected_depth_summary_rows(reader, limit=None)))
    storage = runtime_storage_statistics(store_path, candidate_count=int(counts.get("candidates") or 0))
    rows["runtime_storage"].append(
        {
            "store_id": store_id,
            **storage,
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
    candidate_evidence = candidate_population_evidence(reader, audit_reader=candidate_audit_rows)
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
    rows: dict[str, list[dict[str, object]]],
    sidecar_path: Path,
    *,
    evidence_status: Literal["exploratory", "pilot", "confirmatory"],
) -> None:
    if not sidecar_path.is_file():
        raise FileNotFoundError(sidecar_path)
    data = sidecar_path.read_bytes()
    suffix = sidecar_path.suffix.lower()
    if suffix == ".json":
        payload: object = json.loads(data)
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
    promoted, empirical = _analysis_fact_rows(
        payload,
        sidecar_id=sidecar_id,
        evidence_status=evidence_status,
        store_identities={
            str(row["store_id"]): (
                _canonical_store_identity(row["source_offline_store_version"], "source_offline_store_version"),
                _canonical_store_identity(row["split_manifest_hash"], "split_manifest_hash"),
            )
            for row in rows["stores"]
        },
        sidecar_path=sidecar_path,
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
    rows["empirical_results"].extend(empirical)


def _sidecar_logical_name(payload: object, *, fallback: str) -> str:
    if not isinstance(payload, dict) or payload.get("bundle_role") != _ANALYSIS_FACT_SIDECAR_ROLE:
        return fallback
    logical_name = payload.get("logical_name", fallback)
    if not isinstance(logical_name, str) or not logical_name.strip():
        raise ValueError("Analysis sidecar logical_name must be a non-empty string.")
    if logical_name != Path(logical_name).name or "\\" in logical_name:
        raise ValueError("Analysis sidecar logical_name must not contain a directory path.")
    return logical_name


def _analysis_fact_rows(
    payload: object,
    *,
    sidecar_id: str,
    evidence_status: Literal["exploratory", "pilot", "confirmatory"],
    store_identities: Mapping[str, tuple[str, str]],
    sidecar_path: Path,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    if not isinstance(payload, dict):
        return [], []
    role = payload.get("bundle_role")
    schema_version = payload.get("schema_version")
    if role != _ANALYSIS_FACT_SIDECAR_ROLE:
        if schema_version == ANALYSIS_FACT_SIDECAR_VERSION:
            raise ValueError(f"Analysis sidecar bundle_role must be {_ANALYSIS_FACT_SIDECAR_ROLE!r}.")
        return [], []
    if schema_version != ANALYSIS_FACT_SIDECAR_VERSION:
        raise ValueError(
            f"Analysis sidecar schema_version must be {ANALYSIS_FACT_SIDECAR_VERSION!r}; received {schema_version!r}."
        )
    expected_fields = {"schema_version", "bundle_role", "logical_name", "status", "facts", "empirical_results"}
    required_fields = expected_fields - {"logical_name", "empirical_results"}
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
    if not isinstance(facts, list):
        raise ValueError("Analysis sidecar facts must be a list.")

    output: list[dict[str, object]] = []
    identities: set[tuple[str, str]] = set()
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict) or set(fact) != _ANALYSIS_FACT_FIELDS:
            actual = sorted(fact) if isinstance(fact, dict) else type(fact).__name__
            raise ValueError(
                f"Analysis sidecar fact {index} fields must be {sorted(_ANALYSIS_FACT_FIELDS)}; received {actual}."
            )
        store_id = _required_text(fact["store_id"], field="store_id", index=index)
        if store_id not in store_identities:
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
    empirical_payload = payload.get("empirical_results", [])
    if not isinstance(empirical_payload, list):
        raise ValueError("Analysis sidecar empirical_results must be a list.")
    if not facts and not empirical_payload:
        raise ValueError("Analysis sidecar must contain facts or empirical_results.")
    empirical = [
        _empirical_result_row(
            result,
            index=index,
            sidecar_id=sidecar_id,
            sidecar_path=sidecar_path,
            evidence_status=evidence_status,
            store_identities=store_identities,
        )
        for index, result in enumerate(empirical_payload)
    ]
    return output, empirical


def _empirical_result_row(
    result: object,
    *,
    index: int,
    sidecar_id: str,
    sidecar_path: Path,
    evidence_status: str,
    store_identities: Mapping[str, tuple[str, str]],
) -> dict[str, object]:
    expected_result_fields = _EMPIRICAL_RESULT_FIELDS - {"sidecar_id"}
    if not isinstance(result, dict) or set(result) != expected_result_fields:
        actual = sorted(result) if isinstance(result, dict) else type(result).__name__
        raise ValueError(
            f"Analysis empirical result {index} fields must be {sorted(_EMPIRICAL_RESULT_FIELDS)}; received {actual}."
        )
    row = {**result, "sidecar_id": sidecar_id}
    if row["status"] not in _EVIDENCE_STATUSES or row["status"] != evidence_status:
        raise ValueError(f"Analysis empirical result {index} status must match export status {evidence_status!r}.")
    if row["outcome"] not in _OUTCOMES:
        raise ValueError(f"Analysis empirical result {index} outcome is invalid.")
    for field in (
        "result_id",
        "store_id",
        "experimental_unit",
        "denominator_name",
        "data_identity",
        "split_identity",
        "estimand",
        "unit",
        "aggregation",
        "uncertainty_type",
        "variability_source",
        "comparison_family",
        "environment",
        "command",
        "artifact_path",
        "artifact_sha256",
        "provenance",
        "sidecar_id",
    ):
        _required_text(row[field], field=field, index=index)
    store_id = row["store_id"]
    if store_id not in store_identities:
        raise ValueError(f"Analysis empirical result {index} references unknown store_id.")
    expected_data_identity, expected_split_identity = store_identities[store_id]
    if row["data_identity"] != expected_data_identity:
        raise ValueError(
            f"Analysis empirical result {index} data/split identity data_identity does not match its store."
        )
    if row["split_identity"] != expected_split_identity:
        raise ValueError(
            f"Analysis empirical result {index} data/split identity split_identity does not match its store."
        )
    denominator = _finite_number(row["denominator_value"], field="denominator_value", index=index)
    if denominator <= 0:
        raise ValueError(f"Analysis empirical result {index} denominator_value must be positive.")
    if row["denominator_name"].lower() in {"unknown", "ambiguous", "none", "n/a", "na"}:
        raise ValueError(
            f"Analysis empirical result {index} denominator_name must identify one unambiguous population."
        )
    if row["sidecar_id"] != sidecar_id:
        raise ValueError(f"Analysis empirical result {index} sidecar_id does not match its sidecar.")
    if row["data_identity"].lower() in {"unknown", "none"} or row["split_identity"].lower() in {"unknown", "none"}:
        raise ValueError(f"Analysis empirical result {index} data/split identity cannot be unknown.")
    actor = _identity_array(row["actor_visible_inputs_json"], field="actor_visible_inputs_json", index=index)
    oracle = _identity_array(row["oracle_only_inputs_json"], field="oracle_only_inputs_json", index=index)
    if set(actor) & set(oracle):
        raise ValueError(f"Analysis empirical result {index} actor-visible and oracle-only inputs must be disjoint.")
    revision = row["source_revision"]
    if not isinstance(revision, str) or not _GIT_OID.fullmatch(revision) or revision == "0" * 40:
        raise ValueError(f"Analysis empirical result {index} source_revision must be a full Git OID.")
    artifact = Path(row["artifact_path"])
    if artifact.is_absolute() or "\\" in row["artifact_path"] or artifact == Path(".") or ".." in artifact.parts:
        raise ValueError(f"Analysis empirical result {index} artifact_path must be a portable relative path.")
    artifact_file = (sidecar_path.parent / artifact).resolve()
    if not artifact_file.is_file():
        raise ValueError(f"Analysis empirical result {index} artifact_path does not exist: {row['artifact_path']!r}.")
    if hashlib.sha256(artifact_file.read_bytes()).hexdigest() != row["artifact_sha256"]:
        raise ValueError(f"Analysis empirical result {index} artifact_sha256 does not match artifact_path.")
    outcome = row["outcome"]
    estimate = row["estimate"]
    if outcome in {"missing", "failed"}:
        if estimate is not None or not isinstance(row["reason"], str) or not row["reason"].strip():
            raise ValueError(
                f"Analysis empirical result {index} missing/failed results require null estimate and reason."
            )
    else:
        _finite_number(estimate, field="estimate", index=index)
        lower, upper = row["uncertainty_lower"], row["uncertainty_upper"]
        if (lower is None) != (upper is None):
            raise ValueError(f"Analysis empirical result {index} uncertainty interval must provide both bounds.")
        interval = False
        if lower is not None and upper is not None:
            lower_value = _finite_number(lower, field="uncertainty_lower", index=index)
            upper_value = _finite_number(upper, field="uncertainty_upper", index=index)
            if lower_value > upper_value:
                raise ValueError(f"Analysis empirical result {index} uncertainty interval has invalid order.")
            interval = True
        rationale = row["uncertainty_inapplicable_reason"]
        if not (interval and row["variability_source"].strip()) and (
            not isinstance(rationale, str) or not rationale.strip()
        ):
            raise ValueError(
                f"Analysis empirical result {index} quantitative result requires uncertainty and variability or rationale."
            )
        if evidence_status == "confirmatory" and not any(
            row[field] is not None for field in ("wall_time_s", "gpu_hours", "peak_gpu_memory_bytes", "storage_bytes")
        ):
            raise ValueError(f"Analysis empirical result {index} confirmatory result requires material compute.")
    for field in ("wall_time_s", "gpu_hours", "peak_gpu_memory_bytes", "storage_bytes"):
        if row[field] is not None and _finite_number(row[field], field=field, index=index) < 0:
            raise ValueError(f"Analysis empirical result {index} {field} must be non-negative.")
    row["actor_visible_inputs_json"] = json.dumps(actor, separators=(",", ":"))
    row["oracle_only_inputs_json"] = json.dumps(oracle, separators=(",", ":"))
    return row


def _finite_number(value: object, *, field: str, index: int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"Analysis empirical result {index} {field} must be finite.")
    return float(value)


def _identity_array(value: object, *, field: str, index: int) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise ValueError(f"Analysis empirical result {index} {field} must be a JSON array.") from error
    if not isinstance(value, list):
        raise ValueError(f"Analysis empirical result {index} {field} must be a JSON array.")
    values = sorted({_required_text(item, field=field, index=index) for item in value})
    return values


def _required_text(value: object, *, field: str, index: int) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"Analysis sidecar fact {index} {field} must be a non-empty trimmed string.")
    return value


def _fact_scalar(value: object, *, index: int) -> bool | int | float | str | None:
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"Analysis sidecar fact {index} value must be finite.")
        return value
    raise TypeError(f"Analysis sidecar fact {index} value must be a JSON scalar; received {type(value).__name__}.")


def _typed_leaf_rows(owner_key: str, owner: str, payload: object) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for key, value in _flatten_leaves(payload):
        output.append({owner_key: owner, "key": key, **_typed_value(value)})
    return output


def _fact_rows(
    store_id: str,
    statistics: dict[str, object],
    *,
    evidence_status: Literal["exploratory", "pilot", "confirmatory"],
) -> list[dict[str, object]]:
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


def _nested_value(payload: dict[str, object], dotted_key: str) -> object:
    value: object = payload
    for part in dotted_key.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _flatten_leaves(payload: object, *, prefix: str = "") -> list[tuple[str, object]]:
    if isinstance(payload, dict):
        output: list[tuple[str, object]] = []
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


def _typed_value(value: object) -> dict[str, object]:
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


def _source_coverage_rows(store_id: str, coverage: object) -> list[dict[str, object]]:
    if not isinstance(coverage, dict):
        return []
    output: list[dict[str, object]] = []
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


def _with_store_id(store_id: str, records: list[dict[str, object]]) -> list[dict[str, object]]:
    return [{"store_id": store_id, **record} for record in records]


def _without_raw_toml(payload: object) -> object:
    if not isinstance(payload, dict):
        return payload
    return {key: value for key, value in payload.items() if key != "raw_toml_text"}


def _frame(name: str, rows: list[dict[str, object]]) -> pd.DataFrame:
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


def _validate_bundle_statuses(frames: Mapping[str, pd.DataFrame]) -> None:
    status_values: set[str] = set()
    for name in ("facts", "runtime_storage", "failures", "sidecars", "empirical_results"):
        if "status" in frames[name]:
            status_values.update(str(value) for value in frames[name]["status"].dropna())
    if not status_values.issubset(_EVIDENCE_STATUSES):
        raise ValueError("Report contains an invalid evidence status.")
    if "empirical_results" not in frames or frames["empirical_results"].empty:
        if "confirmatory" in status_values:
            raise ValueError("Confirmatory report export requires at least one empirical result.")
    elif "confirmatory" in status_values:
        if status_values != {"confirmatory"}:
            raise ValueError("Confirmatory report export cannot contain exploratory or pilot rows.")
        if not set(frames["empirical_results"]["status"]) == {"confirmatory"}:
            raise ValueError("Confirmatory report export cannot contain exploratory or pilot result rows.")
    store_ids = {str(value) for value in frames["stores"]["store_id"].dropna()}
    empirical = frames["empirical_results"]
    sidecar_ids = {str(value) for value in frames["sidecars"]["sidecar_id"].dropna()}
    sidecar_value_ids = {str(value) for value in frames["sidecar_values"]["sidecar_id"].dropna()}
    if not sidecar_value_ids <= sidecar_ids:
        raise ValueError("Sidecar value sidecar_id must identify a sidecar in the same bundle.")
    if not empirical.empty:
        if not {str(value) for value in empirical["store_id"]} <= store_ids:
            raise ValueError("Empirical result store_id must identify a store in the same bundle.")
        if not {str(value) for value in empirical["sidecar_id"]} <= sidecar_ids:
            raise ValueError("Empirical result sidecar_id must identify a sidecar in the same bundle.")


def _validate_empirical_bundle(frames: Mapping[str, pd.DataFrame]) -> None:
    """Validate empirical identities and uniqueness against serialized store rows."""

    store_identities = {
        str(row.store_id): (
            _canonical_store_identity(row.source_offline_store_version, "source_offline_store_version"),
            _canonical_store_identity(row.split_manifest_hash, "split_manifest_hash"),
        )
        for row in frames["stores"].itertuples(index=False)
    }
    empirical = frames["empirical_results"]
    result_ids = empirical["result_id"].astype(str)
    if result_ids.duplicated(keep=False).any():
        duplicate_ids = sorted(set(result_ids[result_ids.duplicated(keep=False)]))
        raise ValueError(f"empirical_results contains duplicate result_id values: {duplicate_ids!r}.")
    for index, row in empirical.iterrows():
        expected = store_identities.get(str(row["store_id"]))
        if expected is None:
            continue
        if row["data_identity"] != expected[0]:
            raise ValueError(f"empirical_results row {index} data_identity does not match its store.")
        if row["split_identity"] != expected[1]:
            raise ValueError(f"empirical_results row {index} split_identity does not match its store.")


def _bundle_source_revision(frames: Mapping[str, pd.DataFrame]) -> str | None:
    empirical = frames["empirical_results"]
    revisions = list(empirical["source_revision"].dropna())
    if empirical.empty:
        return None
    if len(revisions) != len(empirical):
        raise ValueError("Every empirical result must provide source_revision.")
    if any(
        not isinstance(revision, str) or not _GIT_OID.fullmatch(revision) or revision == "0" * 40
        for revision in revisions
    ):
        raise ValueError("Empirical result source_revision must be a full nonzero Git OID.")
    unique = set(revisions)
    if len(unique) != 1:
        raise ValueError("All empirical results must match one source_revision.")
    return cast(str, revisions[0])


def _portable_relative_path(value: object, *, field: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"{field} must be a portable relative path.")
    path = Path(value)
    if path.is_absolute() or path == Path(".") or ".." in path.parts:
        raise ValueError(f"{field} must be a portable relative path.")
    return path


def _canonical_store_identity(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"Store identity {field} must be a non-empty trimmed string.")
    return value


def _json_scalar(value: object, *, table: str, column: str) -> object:
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
    "THESIS_REPORT_BUNDLE_ROLE",
    "THESIS_REPORT_BUNDLE_VERSION",
    "THESIS_REPORT_TABLE_COLUMNS",
    "build_thesis_report_frames",
    "deserialize_thesis_report_bundle",
    "serialize_thesis_report_bundle",
    "validate_thesis_report_provenance",
    "validate_thesis_report_bundle",
    "write_thesis_report_bundle",
]
