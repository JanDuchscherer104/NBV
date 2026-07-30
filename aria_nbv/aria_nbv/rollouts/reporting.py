"""Deterministic scientific-report readiness, tables, and JSON bundles.

This module owns the single reporting boundary over
:mod:`aria_nbv.rollouts.inspection` and sealed scientific-audit artifacts. It
binds one audit to one validated store, derives exact confirmatory blockers,
projects a fixed table registry, and serializes byte-stable bundles for
Streamlit, thesis authoring, and offline analysis. Reporting verifies and
reduces precomputed evidence; it never executes independent evaluators,
reinterprets Zarr arrays, or promotes persisted proxy statistics to
confirmatory facts. Heavy candidate rows remain in the rollout store.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from .inspection import (
    candidate_group_summary_rows,
    policy_effect_evidence,
    rollout_statistics,
    rollout_step_objective_rows,
    rollout_tree_summary_rows,
    runtime_storage_statistics,
    selected_depth_summary_rows,
    suspicious_rollout_rows,
    target_audit_rows,
    validity_audit_evidence,
    validity_waterfall_rows,
)
from .scientific_audit import (
    AuditComparisonProtocol,
    AuditStatus,
    EquivalenceVerdict,
    MandatoryCohortStatus,
    RowEvaluationStatus,
    ScientificAuditArtifact,
    load_scientific_audit,
    require_confirmatory_audit,
    verify_scientific_audit_sha256,
)
from .zarr_store import RolloutZarrStoreReader

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
    "audit_provenance": (
        "store_id",
        "bundle_sha256",
        "cohort_sha256",
        "artifact_status",
        "readiness",
        "comparison_protocol",
        "audit_rollout_store_sha256",
        "source_store_sha256",
        "split_manifest_sha256",
        "raw_asset_count",
        "evaluator_id",
        "implementation_revision",
        "resolved_config_sha256",
        "endpoint_row_count",
        "validity_row_count",
        "observed_distinct_scenes",
        "min_scenes_for_cluster_ci",
        "cluster_ci_eligible",
        "cluster_ci_suppression_reason",
        "evidence_tier",
    ),
    "audit_raw_assets": ("store_id", "name", "sha256", "evidence_tier"),
    "audit_cohorts": (
        "store_id",
        "cohort_id",
        "endpoint_row_count",
        "validity_row_count",
        "mandatory_status",
        "reason",
        "evidence_tier",
    ),
    "audit_blockers": ("store_id", "scope", "cohort_id", "code", "detail"),
    "scientific_fact_registry": (
        "store_id",
        "evidence_id",
        "fact",
        "declared_tier",
        "evidence_tier",
        "status",
        "reason",
        "source",
    ),
}
"""Stable table names and column order consumed by the thesis bundle."""

_GROUP_FIELDS = ("position", "strategy", "mixture", "invalid_reason", "policy")
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

_SCIENTIFIC_FACT_REGISTRY = (
    ("E1", "independent_endpoint_gain", "thesis_primary"),
    ("E2", "raw_qh_endpoint_effect", "thesis_primary"),
    ("E3", "oracle_lookahead_headroom", "thesis_primary_setup_gate"),
    ("E4", "recovered_headroom", "thesis_support"),
    ("E5", "endpoint_telescoping_equivalence", "audit_gate"),
    ("E6", "fixed_budget_termination_path_cost", "thesis_primary_companion"),
    ("E7", "scene_macro_endpoint_effect", "thesis_primary_at_scene_gate"),
    ("E8", "horizon_trajectory", "thesis_support_descriptive"),
    ("G1", "candidate_family_composition", "thesis_support"),
    ("G2", "proposal_mass_calibration", "development_support"),
    ("G3", "equal_area_directional_density", "thesis_support"),
    ("G4", "spherical_cap_coverage", "thesis_support"),
    ("G5", "angular_separation", "thesis_support"),
    ("G6", "spatial_support", "thesis_support"),
    ("G7", "target_view_support", "thesis_support"),
    ("G8", "target_los", "thesis_support"),
    ("G9", "motion_support", "thesis_support"),
    ("G10", "behavior_evaluation_support", "thesis_support"),
    ("G11", "selected_rank_and_regret", "thesis_support"),
    ("V1", "candidate_flow", "thesis_support_audit"),
    ("V2", "mask_intersections", "thesis_support_audit"),
    ("V3", "conditional_actor_validity", "thesis_support"),
    ("V4", "reason_bitset_intersections", "thesis_support"),
    ("V5", "signed_predicate_margins", "thesis_support"),
    ("V6", "spatial_invalidity", "development_support"),
    ("V7", "same_contract_validity_confusion", "audit_gate"),
    ("V8", "boundary_agreement", "audit_gate"),
    ("V9", "oracle_label_coverage", "thesis_support"),
    ("O1", "target_protocol_matching", "thesis_support_appendix"),
    ("O2", "store_identity_audit_readiness", "audit_gate"),
    ("O3", "exact_row_drilldown", "development_only"),
)
"""Closed registry of reportable evidence IDs, meanings, and declared tiers.

Registry membership declares what reporting knows how to name, not that a fact
is available. Each selected store receives exactly one row per evidence ID;
status and reason are derived from verified artifact content and fail closed
when the required estimand, cohort, or inference gate is absent.
"""

ScientificAuditReference = ScientificAuditArtifact | Path | str | None


def scientific_report_blockers(
    store_path: Path | str,
    scientific_audit: ScientificAuditReference,
) -> tuple[str, ...]:
    """Return reporting-owned blockers for one confirmatory store/audit binding.

    The same store validation, artifact seal, provenance identities, mandatory
    cohorts, endpoint equivalence, and validity-contract gates used by
    :func:`build_thesis_report_frames` are applied here. An empty tuple means
    eligible under current evidence; it does not create or run an audit.
    """

    resolved_store = Path(store_path).expanduser().resolve()
    artifact, load_blockers = _resolve_scientific_audit(scientific_audit, evidence_status="pilot")
    if artifact is None:
        return load_blockers
    reader = RolloutZarrStoreReader(resolved_store)
    validation = reader.validate()
    if not validation.ok:
        detail = "; ".join(validation.errors[:3]) or "unknown validation error"
        return (f"rollout_store_invalid:{detail}",)
    store_id = str(reader.root.attrs.get("manifest_sha256", ""))
    blocker_rows = _scientific_audit_blockers(resolved_store, store_id=store_id, artifact=artifact)
    return tuple(f"{row['code']}:{row['detail']}" for row in blocker_rows)


def build_thesis_report_frames(
    store_paths: Iterable[Path | str],
    *,
    sidecar_paths: Iterable[Path | str] = (),
    evidence_status: Literal["pilot", "confirmatory"],
    scientific_audit: ScientificAuditReference = None,
) -> dict[str, pd.DataFrame]:
    """Build deterministic named DataFrames with fail-closed evidence tiers.

    Args:
        store_paths: Current-schema rollout Zarr stores. Every store is fully
            validated before its facts enter the report.
        sidecar_paths: Optional caller-selected JSON or JSONL evidence files.
            Selected paths are required to exist; missing files never disappear
            silently from provenance.
        evidence_status: Requested export tier. Persisted proxy statistics
            remain labelled ``pilot`` even inside an admitted confirmatory
            bundle; only the audit-backed registry may become confirmatory.
        scientific_audit: Explicit precomputed audit artifact or JSON path.
            Reporting may verify and reduce it but never executes the audit
            evaluator. Confirmatory export requires an exact PASS artifact.

    Returns:
        Mapping whose keys and columns exactly match
        :data:`THESIS_REPORT_TABLE_COLUMNS`. Config values, statistics, and
        sidecar leaves use typed long-form rows so missing values remain
        distinguishable from zero or an empty string.

    Notes:
        Persisted rollout summaries remain pilot proxies in every bundle.
        Confirmatory status is available only through one verified audit bound
        to one validated store, and the scientific-fact registry records both
        available and unavailable declared facts exactly once per store.
    """

    if evidence_status not in {"pilot", "confirmatory"}:
        raise ValueError("evidence_status must be 'pilot' or 'confirmatory'.")
    rows: dict[str, list[dict[str, object]]] = {name: [] for name in THESIS_REPORT_TABLE_COLUMNS}
    resolved_stores = sorted({Path(path).expanduser().resolve() for path in store_paths}, key=Path.as_posix)
    if not resolved_stores:
        raise ValueError("At least one rollout store is required to build thesis report frames.")
    artifact, audit_load_blockers = _resolve_scientific_audit(
        scientific_audit,
        evidence_status=evidence_status,
    )
    if artifact is not None and len(resolved_stores) != 1:
        raise ValueError("One scientific audit can be bound to exactly one selected rollout store.")
    for store_path in resolved_stores:
        _append_store_rows(rows, store_path, evidence_status=evidence_status)
    _append_scientific_audit_rows(
        rows,
        store_paths=resolved_stores,
        artifact=artifact,
        load_blockers=audit_load_blockers,
        evidence_status=evidence_status,
    )
    for sidecar_path in sorted(
        {Path(path).expanduser().resolve() for path in sidecar_paths},
        key=Path.as_posix,
    ):
        _append_sidecar_rows(rows, sidecar_path, evidence_status=evidence_status)

    return {name: _frame(name, table_rows) for name, table_rows in rows.items()}


def _resolve_scientific_audit(
    reference: ScientificAuditReference,
    *,
    evidence_status: Literal["pilot", "confirmatory"],
) -> tuple[ScientificAuditArtifact | None, tuple[str, ...]]:
    if reference is None:
        if evidence_status == "confirmatory":
            raise ValueError("Confirmatory evidence export requires an explicit scientific audit artifact or path.")
        return None, ("scientific_audit_absent",)
    try:
        if isinstance(reference, ScientificAuditArtifact):
            artifact = ScientificAuditArtifact.model_validate(reference.model_dump(mode="python"))
            verify_scientific_audit_sha256(artifact)
        else:
            artifact = load_scientific_audit(Path(reference).expanduser().resolve())
        if evidence_status == "confirmatory":
            require_confirmatory_audit(artifact)
        return artifact, ()
    except Exception as exc:
        if evidence_status == "confirmatory":
            raise ValueError(f"Confirmatory scientific audit is invalid: {type(exc).__name__}: {exc}") from exc
        return None, (f"scientific_audit_invalid:{type(exc).__name__}:{exc}",)


def _append_scientific_audit_rows(
    rows: dict[str, list[dict[str, object]]],
    *,
    store_paths: list[Path],
    artifact: ScientificAuditArtifact | None,
    load_blockers: tuple[str, ...],
    evidence_status: Literal["pilot", "confirmatory"],
) -> None:
    store_ids = tuple(str(row["store_id"]) for row in rows["stores"])
    if artifact is None:
        for store_id in store_ids:
            for blocker in load_blockers:
                rows["audit_blockers"].append(
                    {"store_id": store_id, "scope": "artifact", "cohort_id": None, "code": blocker, "detail": blocker}
                )
            _append_scientific_fact_registry(
                rows,
                store_id=store_id,
                evidence_tier="blocked",
                availability=_unavailable_scientific_facts("confirmatory_scientific_audit_unavailable"),
                source="scientific_audit.unavailable",
            )
        return

    assert len(store_paths) == len(store_ids) == 1
    store_id = store_ids[0]
    blockers = _scientific_audit_blockers(store_paths[0], store_id=store_id, artifact=artifact)
    if evidence_status == "confirmatory" and blockers:
        details = "; ".join(f"{row['code']}: {row['detail']}" for row in blockers)
        raise ValueError(f"Confirmatory scientific audit is not admissible for the selected store: {details}")

    evidence_tier: Literal["confirmatory", "characterization", "blocked"] = (
        "confirmatory" if evidence_status == "confirmatory" and not blockers else "characterization"
    )
    rows["audit_provenance"].append(
        {
            "store_id": store_id,
            "bundle_sha256": artifact.bundle_sha256,
            "cohort_sha256": artifact.cohort.cohort_sha256,
            "artifact_status": artifact.status.value,
            "readiness": artifact.readiness.value,
            "comparison_protocol": artifact.comparison_protocol.value,
            "audit_rollout_store_sha256": artifact.provenance.rollout_store_sha256,
            "source_store_sha256": artifact.provenance.source_store_sha256,
            "split_manifest_sha256": artifact.provenance.split_manifest_sha256,
            "raw_asset_count": len(artifact.provenance.raw_assets),
            "evaluator_id": artifact.provenance.evaluator_id,
            "implementation_revision": artifact.provenance.implementation_revision,
            "resolved_config_sha256": artifact.provenance.resolved_config_sha256,
            "endpoint_row_count": len(artifact.endpoint_rows),
            "validity_row_count": len(artifact.validity_rows),
            "observed_distinct_scenes": artifact.observed_distinct_scenes,
            "min_scenes_for_cluster_ci": artifact.config.min_scenes_for_cluster_ci,
            "cluster_ci_eligible": artifact.cluster_ci_eligible,
            "cluster_ci_suppression_reason": artifact.cluster_ci_suppression_reason,
            "evidence_tier": evidence_tier,
        }
    )
    rows["audit_raw_assets"].extend(
        {
            "store_id": store_id,
            "name": item.name,
            "sha256": item.sha256,
            "evidence_tier": evidence_tier,
        }
        for item in artifact.provenance.raw_assets
    )
    rows["audit_cohorts"].extend(
        {
            "store_id": store_id,
            "cohort_id": summary.cohort_id,
            "endpoint_row_count": summary.endpoint_row_count,
            "validity_row_count": summary.validity_row_count,
            "mandatory_status": summary.mandatory_status.value,
            "reason": summary.reason,
            "evidence_tier": evidence_tier,
        }
        for summary in artifact.cohort_summaries
    )
    rows["audit_blockers"].extend(blockers)
    if evidence_status == "pilot":
        rows["audit_blockers"].append(
            {
                "store_id": store_id,
                "scope": "export",
                "cohort_id": None,
                "code": "pilot_mode_confirmatory_claims_suppressed",
                "detail": "Pilot exports retain provenance and characterization only.",
            }
        )
    availability = (
        _scientific_fact_availability(artifact)
        if evidence_tier == "confirmatory"
        else _unavailable_scientific_facts("pilot_or_blocked_evidence_tier")
    )
    _append_scientific_fact_registry(
        rows,
        store_id=store_id,
        evidence_tier=evidence_tier,
        availability=availability,
        source=f"scientific_audit:{artifact.bundle_sha256}",
    )


def _scientific_audit_blockers(
    store_path: Path,
    *,
    store_id: str,
    artifact: ScientificAuditArtifact,
) -> list[dict[str, object]]:
    blockers: list[dict[str, object]] = []

    def append(scope: str, code: str, detail: str, *, cohort_id: str | None = None) -> None:
        blockers.append({"store_id": store_id, "scope": scope, "cohort_id": cohort_id, "code": code, "detail": detail})

    if artifact.provenance.rollout_store_sha256 != store_id:
        append(
            "identity",
            "wrong_rollout_store",
            f"expected={store_id}:observed={artifact.provenance.rollout_store_sha256}",
        )
    manifest = RolloutZarrStoreReader(store_path).manifest().get("manifest", {})
    config_hashes = manifest.get("config_hashes", {}) if isinstance(manifest, dict) else {}
    _append_identity_hash_blocker(
        append,
        label="source_store",
        observed=config_hashes.get("source_manifest") if isinstance(config_hashes, dict) else None,
        expected=artifact.provenance.source_store_sha256,
    )
    _append_identity_hash_blocker(
        append,
        label="split_manifest",
        observed=config_hashes.get("split_manifest") if isinstance(config_hashes, dict) else None,
        expected=artifact.provenance.split_manifest_sha256,
    )
    if artifact.status is not AuditStatus.PASS:
        append("artifact", "audit_status_not_pass", artifact.status.value)
    if artifact.comparison_protocol is not AuditComparisonProtocol.SAME_CONTRACT:
        append("artifact", "comparison_protocol_mismatch", artifact.comparison_protocol.value)
    for summary in artifact.cohort_summaries:
        if summary.mandatory_status is not MandatoryCohortStatus.PASS:
            append("cohort", "mandatory_cohort_not_pass", summary.reason, cohort_id=summary.cohort_id)
    for row in artifact.endpoint_rows:
        if row.evaluation_status is not RowEvaluationStatus.COMPLETE:
            append("endpoint", "endpoint_incomplete", row.unit_id, cohort_id=row.cohort_id)
        elif row.equivalence_verdict is not EquivalenceVerdict.PASS:
            append("endpoint", "endpoint_equivalence_failed", row.unit_id, cohort_id=row.cohort_id)
        if row.source_store_sha256 != artifact.provenance.source_store_sha256:
            append("endpoint", "endpoint_source_identity_mismatch", row.unit_id, cohort_id=row.cohort_id)
        if row.split_manifest_sha256 != artifact.provenance.split_manifest_sha256:
            append("endpoint", "endpoint_split_identity_mismatch", row.unit_id, cohort_id=row.cohort_id)
    validity = validity_audit_evidence(artifact)
    if not bool(validity["same_contract_eligible"]):
        append("validity", "required_validity_contract_incomplete", str(validity["fallback_reason"]))
    validity_blockers = validity["blocker_rows"]
    if not isinstance(validity_blockers, list):
        raise TypeError("validity_audit_evidence blocker_rows must be a list.")
    for row in validity_blockers:
        if not isinstance(row, dict):
            raise TypeError("validity_audit_evidence blocker rows must be mappings.")
        append(
            "validity",
            str(row["blocker"]),
            f"predicate_kind={row['predicate_kind']}",
            cohort_id=str(row["cohort_id"]),
        )
    return sorted(
        blockers,
        key=lambda row: tuple(
            "" if row[key] is None else str(row[key]) for key in THESIS_REPORT_TABLE_COLUMNS["audit_blockers"]
        ),
    )


def _append_identity_hash_blocker(
    append: Callable[[str, str, str], None],
    *,
    label: str,
    observed: object,
    expected: str,
) -> None:
    observed_values = tuple(str(value) for value in observed) if isinstance(observed, list | tuple) else ()
    if observed_values != (expected,):
        append("identity", f"wrong_{label}_identity", f"expected={expected}:observed={observed_values}")


def _scientific_fact_availability(artifact: ScientificAuditArtifact) -> dict[str, str | None]:
    availability = _unavailable_scientific_facts("not_projected_by_scientific_audit")
    endpoints = artifact.endpoint_rows
    endpoints_complete = bool(endpoints) and all(
        row.evaluation_status is RowEvaluationStatus.COMPLETE and row.endpoint_gain is not None for row in endpoints
    )
    availability["E1"] = None if endpoints_complete else "complete_independent_endpoints_absent"
    equivalence_complete = endpoints_complete and all(
        row.equivalence_verdict is EquivalenceVerdict.PASS for row in endpoints
    )
    availability["E5"] = None if equivalence_complete else "endpoint_equivalence_not_complete_pass"
    companion_complete = endpoints_complete and all(
        row.achieved_steps is not None
        and row.budget is not None
        and row.termination_reason is not None
        and row.path_length_m is not None
        and row.evaluation_cost_s is not None
        for row in endpoints
    )
    availability["E6"] = None if companion_complete else "fixed_budget_path_or_cost_fields_incomplete"

    effects = policy_effect_evidence(artifact)
    summary_rows = effects["summary_rows"]
    if not isinstance(summary_rows, list):
        raise TypeError("policy_effect_evidence summary_rows must be a list.")
    summaries = {str(row["contrast"]): row for row in summary_rows if isinstance(row, dict) and "contrast" in row}
    for evidence_id, contrast in (("E2", "raw_qh"), ("E3", "delta_look"), ("E4", "eta_q")):
        summary = summaries.get(contrast)
        availability[evidence_id] = (
            None if summary is not None and bool(summary.get("estimable")) else f"{contrast}_not_estimable"
        )
    inferential_summaries = [
        summary
        for contrast, summary in summaries.items()
        if contrast in {"raw_qh", "delta_look", "eta_q"} and summary.get("inference_status") == "cluster_ci"
    ]
    availability["E7"] = None if inferential_summaries else "scene_cluster_ci_gate_not_met"

    validity = validity_audit_evidence(artifact)
    confusion_rows = validity["confusion_rows"]
    boundary_rows = validity["boundary_rows"]
    validity_gate = bool(validity["same_contract_eligible"])
    confusion_available = (
        validity_gate
        and isinstance(confusion_rows, list)
        and bool(confusion_rows)
        and all(isinstance(row, dict) and bool(row.get("eligible")) for row in confusion_rows)
    )
    boundary_available = validity_gate and isinstance(boundary_rows, list) and bool(boundary_rows)
    availability["V7"] = None if confusion_available else "eligible_same_contract_confusion_absent"
    availability["V8"] = None if boundary_available else "eligible_boundary_agreement_absent"
    availability["O2"] = None
    return availability


def _unavailable_scientific_facts(reason: str) -> dict[str, str | None]:
    return {evidence_id: reason for evidence_id, _, _ in _SCIENTIFIC_FACT_REGISTRY}


def _append_scientific_fact_registry(
    rows: dict[str, list[dict[str, object]]],
    *,
    store_id: str,
    evidence_tier: Literal["confirmatory", "characterization", "blocked"],
    availability: Mapping[str, str | None],
    source: str,
) -> None:
    registry_rows: list[dict[str, object]] = [
        {
            "store_id": store_id,
            "evidence_id": evidence_id,
            "fact": fact,
            "declared_tier": declared_tier,
            "evidence_tier": evidence_tier,
            "status": "available" if availability[evidence_id] is None else "unavailable",
            "reason": availability[evidence_id],
            "source": source,
        }
        for evidence_id, fact, declared_tier in _SCIENTIFIC_FACT_REGISTRY
    ]
    identities = {(str(row["store_id"]), str(row["evidence_id"])) for row in registry_rows}
    if len(identities) != len(registry_rows) or len(registry_rows) != len(_SCIENTIFIC_FACT_REGISTRY):
        raise ValueError("Scientific fact registry must contain exactly one row per (store_id, evidence_id).")
    rows["scientific_fact_registry"].extend(registry_rows)


def serialize_thesis_report_bundle(frames: Mapping[str, pd.DataFrame]) -> bytes:
    """Serialize report frames as strict, compact, byte-stable JSON.

    The serializer rejects missing or extra tables, column drift, and infinite
    floats. Pandas and NumPy missing scalars become JSON ``null``. It adds no
    build timestamp, so identical frames produce identical bytes.

    This is serialization only: scientific readiness and fact availability
    must already have been established by :func:`build_thesis_report_frames`.
    """

    _validate_frame_schema(frames)
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


def write_thesis_report_bundle(path: Path | str, frames: Mapping[str, pd.DataFrame]) -> str:
    """Atomically write validated report bytes and return their SHA-256.

    The digest covers the exact bytes written by
    :func:`serialize_thesis_report_bundle`; no timestamp or path enters bundle
    identity.
    """

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
    evidence_status: Literal["pilot", "confirmatory"],
) -> None:
    reader = RolloutZarrStoreReader(store_path)
    validation = reader.validate()
    if not validation.ok:
        detail = "; ".join(validation.errors[:3]) or "unknown validation error"
        raise ValueError(f"Rollout store {store_path} failed validation: {detail}")
    manifest_payload = reader.manifest()
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
    parameter_payload = {
        "writer_config": generation.get("writer_config") if isinstance(generation, dict) else None,
        "invocation": _without_raw_toml(generation.get("invocation")) if isinstance(generation, dict) else None,
        "runtime": generation.get("runtime") if isinstance(generation, dict) else None,
        "shard": generation.get("shard") if isinstance(generation, dict) else None,
        "config_hashes": manifest.get("config_hashes") if isinstance(manifest, dict) else None,
        "root_attrs": root_attrs,
    }
    rows["parameters"].extend(_typed_leaf_rows("store_id", store_id, parameter_payload))
    stats = rollout_statistics(reader, manifest_payload=manifest_payload)
    rows["statistics"].extend(_typed_leaf_rows("store_id", store_id, stats))
    rows["facts"].extend(_fact_rows(store_id, stats))
    rows["source_coverage"].extend(_source_coverage_rows(store_id, stats.get("source_coverage", {})))
    rows["targets"].extend(_with_store_id(store_id, target_audit_rows(reader)))
    rows["validity"].extend(_with_store_id(store_id, validity_waterfall_rows(reader)))
    rows["steps"].extend(_with_store_id(store_id, rollout_step_objective_rows(reader)))
    rows["rollout_tree"].extend(_with_store_id(store_id, rollout_tree_summary_rows(reader)))
    rows["selected_depth"].extend(_with_store_id(store_id, selected_depth_summary_rows(reader, limit=None)))
    storage = runtime_storage_statistics(store_path, candidate_count=int(counts.get("candidates") or 0))
    rows["runtime_storage"].append(
        {
            "store_id": store_id,
            **storage,
            "status": "pilot",
            "source": "inspection.runtime_storage_statistics",
        }
    )
    rows["failures"].extend(
        {
            "store_id": store_id,
            **failure,
            "status": "pilot",
            "source": "inspection.suspicious_rollout_rows",
        }
        for failure in suspicious_rollout_rows(reader)
    )
    for group_by in _GROUP_FIELDS:
        for group_row in candidate_group_summary_rows(reader, group_by=group_by):
            group = group_row.pop(group_by)
            rows["candidate_groups"].append({"store_id": store_id, "group_by": group_by, "group": group, **group_row})


def _append_sidecar_rows(
    rows: dict[str, list[dict[str, object]]],
    sidecar_path: Path,
    *,
    evidence_status: Literal["pilot", "confirmatory"],
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
    evidence_status: Literal["pilot", "confirmatory"],
    known_store_ids: set[str],
) -> list[dict[str, object]]:
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

    output: list[dict[str, object]] = []
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
) -> list[dict[str, object]]:
    return [
        {
            "store_id": store_id,
            "key": key,
            "value": _nested_value(statistics, key),
            "unit": unit,
            "n": _nested_value(statistics, n_key),
            "aggregation": aggregation,
            "status": "pilot",
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
    "ScientificAuditReference",
    "THESIS_REPORT_BUNDLE_ROLE",
    "THESIS_REPORT_BUNDLE_VERSION",
    "THESIS_REPORT_TABLE_COLUMNS",
    "build_thesis_report_frames",
    "serialize_thesis_report_bundle",
    "scientific_report_blockers",
    "write_thesis_report_bundle",
]
