"""Cache and read-model boundary for stored-rollout panels."""

from __future__ import annotations

import hashlib
import json
from functools import wraps
from pathlib import Path
from typing import Any

import streamlit as st

from ....configs import PathConfig
from ....dataset_topology import build_dataset_topology
from ....rollouts import RolloutZarrStoreReader
from ....rollouts.inspection import (
    RolloutSuspiciousQueryConfig,
    candidate_audit_rows,
    candidate_flow_rows,
    candidate_group_summary_rows,
    candidate_population_evidence,
    comparable_policy_cohorts,
    discounted_rollout_return_rows,
    discover_rollout_store_paths,
    mask_combination_rows,
    oracle_headroom_evidence,
    paired_policy_comparison_rows,
    promoted_store_validation_error,
    q_h_evidence_rows,
    reconstruction_endpoint_summary_rows,
    reconstruction_metric_summary_rows,
    rollout_header_summary,
    rollout_step_objective_rows,
    rollout_store_inventory_rows,
    rollout_tree_summary_rows,
    root_relative_candidate_rows,
    root_relative_rollout_anchor_rows,
    selected_candidate_rank_rows,
    selected_depth_summary_rows,
    store_invariant_rows,
    suspicious_rollout_rows,
    target_audit_rows,
    temporal_metric_summary_rows,
)
from ....rollouts.reporting import (
    RolloutCorpusSummary,
    build_rollout_corpus_summary,
    build_thesis_report_frames,
    serialize_thesis_report_bundle,
)

CORPUS_SUMMARY_STATE_KEY = "stored_rollouts_corpus_summary"
_PROJECTION_CACHE_REVISIONS = {
    # Root geometry gained target-distance normalized coordinates.  Keep an
    # existing Streamlit process from serving the prior projection shape.
    "root_geometry": 3,
    "root_anchors": 2,
}


@st.cache_resource(show_spinner=False)
def _cached_store_bundle_cached(
    store_path: str, *, store_identity: str = ""
) -> tuple[RolloutZarrStoreReader, Any, dict[str, Any]]:
    """Open and validate one replacement-sensitive rollout store identity."""

    reader = RolloutZarrStoreReader(Path(store_path))
    validation = reader.validate()
    try:
        manifest_payload = reader.manifest()
    except Exception:
        manifest_payload = {"root_attrs": {}, "manifest": {}}
    if promotion_error := promoted_store_validation_error(reader, manifest_payload=manifest_payload):
        validation.errors.append(promotion_error)
    return reader, validation, manifest_payload


@wraps(_cached_store_bundle_cached.__wrapped__)
def _cached_store_bundle(store_path: str) -> tuple[RolloutZarrStoreReader, Any, dict[str, Any]]:
    """Open one store through a cache key that changes when its manifest is replaced."""

    return _cached_store_bundle_cached(store_path, store_identity=_store_projection_identity(store_path))


@st.cache_data(show_spinner="Scanning rollout stores…", max_entries=8)
def _cached_inventory(cache_root: str) -> list[dict[str, object]]:
    """Project the immutable rollout-store inventory once per cache root."""

    return rollout_store_inventory_rows(
        discover_rollout_store_paths(Path(cache_root)),
        validate=False,
    )


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_candidate_population_cached(
    store_path: str, store_identity: str, sample_size: int = 500
) -> dict[str, object]:
    """Build the complete candidate bundle once per immutable store identity."""

    reader, _, _ = _cached_store_bundle(store_path)
    return candidate_population_evidence(reader, sample_size=sample_size)


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_projection_cached(
    store_path: str,
    projection: str,
    *,
    rollout_row_id: int | None = None,
    step_row_id: int | None = None,
    limit: int | None = None,
    group_by: str | None = None,
    metric: str | None = None,
    group_fields: tuple[str, ...] = (),
    policies: tuple[str, ...] | None = None,
    rollout_row_ids: tuple[int, ...] | None = None,
    step_indices: tuple[int, ...] | None = None,
    deep_count: bool = False,
    q_h_chunk_size: int = 1024,
    q_h_state_limit: int | None = None,
    projection_revision: int = 1,
    store_identity: str = "",
) -> Any:
    """Cache serializable inspection projections for one validated store identity."""

    reader, _, manifest_payload = _cached_store_bundle(store_path)
    if projection == "invariants":
        return store_invariant_rows(reader, manifest_payload=manifest_payload)
    if projection == "header":
        return rollout_header_summary(reader, manifest_payload=manifest_payload)
    if projection == "cohorts":
        return comparable_policy_cohorts(reader)
    if projection == "paired":
        return paired_policy_comparison_rows(reader)
    if projection == "steps":
        return rollout_step_objective_rows(reader, rollout_row_id=rollout_row_id)
    if projection == "reconstruction_metrics":
        return reconstruction_metric_summary_rows(reader)
    if projection == "reconstruction_endpoints":
        return reconstruction_endpoint_summary_rows(reader)
    if projection == "discounted_returns":
        root_attrs = manifest_payload.get("root_attrs", {})
        root_attrs = root_attrs if isinstance(root_attrs, dict) else {}
        return discounted_rollout_return_rows(
            reader,
            return_semantics=root_attrs.get("return_semantics"),
            discount_gamma=root_attrs.get("discount_gamma"),
        )
    if projection == "headroom":
        return oracle_headroom_evidence(reader)
    if projection == "temporal":
        if metric is None:
            raise ValueError("temporal projection requires metric")
        return temporal_metric_summary_rows(reader, metric=metric, group_fields=group_fields)
    if projection == "candidate_flow":
        return candidate_flow_rows(reader, policies=policies, step_indices=step_indices)
    if projection == "ranks":
        return selected_candidate_rank_rows(reader, policies=policies, step_indices=step_indices)
    if projection == "targets":
        return target_audit_rows(reader)
    if projection == "masks":
        return mask_combination_rows(reader)
    if projection == "candidates":
        rows: list[dict[str, object]] = []
        candidate_audit_rows(
            reader,
            rollout_row_id=rollout_row_id,
            step_row_id=step_row_id,
            limit=limit,
            row_callback=rows.append,
        )
        return rows
    if projection == "candidate_group":
        if group_by is None:
            raise ValueError("candidate_group projection requires group_by")
        if not hasattr(reader, "array"):
            audit_rows = _cached_projection(store_path, "candidates", limit=limit)
            return candidate_group_summary_rows(reader, group_by=group_by, audit_rows=audit_rows)
        return _cached_candidate_population_cached(store_path, store_identity)["groups"][group_by]
    if projection in {"candidate_composition", "candidate_calibration"}:
        if group_by is None:
            raise ValueError(f"{projection} projection requires group_by")
        evidence = _cached_candidate_population_cached(store_path, store_identity)
        key = "composition" if projection == "candidate_composition" else "calibration"
        return evidence[key][group_by]
    if projection == "candidate_collision":
        return _cached_candidate_population_cached(store_path, store_identity)["collision"]
    if projection == "candidate_sample":
        return _cached_candidate_population_cached(store_path, store_identity, 500 if limit is None else limit)[
            "sample"
        ]
    if projection == "candidate_population":
        return _cached_candidate_population_cached(store_path, store_identity)
    if projection == "q_h":
        _, validation, _ = _cached_store_bundle(store_path)
        return q_h_evidence_rows(
            reader,
            deep_count=deep_count,
            chunk_size=q_h_chunk_size,
            state_row_limit=q_h_state_limit,
            validation_result=validation,
        )
    if projection == "tree":
        return rollout_tree_summary_rows(reader)
    if projection == "root_geometry":
        rows = root_relative_candidate_rows(reader, actor_valid_only=False)
        return rows if limit is None else rows[:limit]
    if projection == "root_anchors":
        return root_relative_rollout_anchor_rows(reader, rollout_row_ids=rollout_row_ids)
    if projection == "depth_summary":
        return selected_depth_summary_rows(reader, rollout_row_id=rollout_row_id, limit=limit)
    raise ValueError(f"Unknown cached rollout projection: {projection}")


def _store_projection_identity(store_path: str) -> str:
    """Return a replacement-sensitive identity without reading Zarr payloads."""

    path = Path(store_path)
    try:
        digest = hashlib.sha256()
        for child in sorted(
            (candidate for candidate in path.rglob("*") if candidate.is_file()), key=lambda p: p.as_posix()
        ):
            relative = child.relative_to(path).as_posix().encode()
            stat = child.stat()
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            digest.update(stat.st_size.to_bytes(8, "big"))
            digest.update(stat.st_mtime_ns.to_bytes(8, "big"))
            digest.update(stat.st_ctime_ns.to_bytes(8, "big"))
            digest.update(stat.st_ino.to_bytes(8, "big"))
        success = _read_json_mapping(path / "_SUCCESS.json")
        seal = success.get("rollout_store_content_sha256") if success is not None else None
        identity = f"store:{seal or 'unpromoted'}:{digest.hexdigest()}"
    except OSError:
        try:
            stat = path.stat()
            identity = f"store:{stat.st_size}:{stat.st_mtime_ns}"
        except OSError:
            identity = "missing"
    return identity


def _read_json_mapping(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


@wraps(_cached_projection_cached.__wrapped__)
def _cached_projection(store_path: str, projection: str, **kwargs: Any) -> Any:
    """Dispatch through the projection cache with a replacement-sensitive store key."""

    return _cached_projection_cached(
        store_path,
        projection,
        projection_revision=_PROJECTION_CACHE_REVISIONS.get(projection, 1),
        store_identity=_store_projection_identity(store_path),
        **kwargs,
    )


@st.cache_resource(show_spinner="Resolving dataset topology…", max_entries=16)
def _cached_topology_cached(
    store_path: str,
    vin_store_dirs: tuple[str, ...],
    paths: PathConfig,
    selected_source_row_id: int | None = None,
    *,
    store_identity: str = "",
) -> Any:
    """Resolve one replacement-sensitive cross-store topology and reuse its Rich tree."""

    return build_dataset_topology(
        rollout_store_dir=Path(store_path),
        vin_store_dirs=[Path(value) for value in vin_store_dirs],
        path_config=paths,
        selected_source_row_id=selected_source_row_id,
    )


@wraps(_cached_topology_cached.__wrapped__)
def _cached_topology(
    store_path: str,
    vin_store_dirs: tuple[str, ...],
    paths: PathConfig,
    selected_source_row_id: int | None = None,
) -> Any:
    """Resolve topology through a cache key bound to the selected store identity."""

    return _cached_topology_cached(
        store_path,
        vin_store_dirs,
        paths,
        selected_source_row_id,
        store_identity=_store_projection_identity(store_path),
    )


@st.cache_data(show_spinner="Evaluating failure predicates…", max_entries=32)
def _cached_failures_cached(
    store_path: str,
    min_valid_candidates: int,
    dominant_invalid_fraction: float,
    max_step_distance_m: float,
    *,
    store_identity: str = "",
) -> list[dict[str, object]]:
    """Cache failure triage for one replacement-sensitive store and threshold tuple."""

    reader, _, _ = _cached_store_bundle(store_path)
    config = RolloutSuspiciousQueryConfig(
        min_valid_candidates=min_valid_candidates,
        dominant_invalid_fraction=dominant_invalid_fraction,
        max_step_distance_m=max_step_distance_m,
    )
    return suspicious_rollout_rows(reader, config=config)


@wraps(_cached_failures_cached.__wrapped__)
def _cached_failures(
    store_path: str,
    min_valid_candidates: int,
    dominant_invalid_fraction: float,
    max_step_distance_m: float,
) -> list[dict[str, object]]:
    """Evaluate failure triage through a cache key bound to the selected store identity."""

    return _cached_failures_cached(
        store_path,
        min_valid_candidates,
        dominant_invalid_fraction,
        max_step_distance_m,
        store_identity=_store_projection_identity(store_path),
    )


@st.cache_data(show_spinner="Building deterministic evidence bundle…", max_entries=16)
def _cached_evidence_bundle_cached(store_path: str, evidence_status: str, *, store_identity: str = "") -> bytes:
    """Build one deterministic bundle for a replacement-sensitive store identity."""

    frames = build_thesis_report_frames([Path(store_path)], evidence_status=evidence_status)
    return serialize_thesis_report_bundle(frames)


@wraps(_cached_evidence_bundle_cached.__wrapped__)
def _cached_evidence_bundle(store_path: str, evidence_status: str) -> bytes:
    """Build a report bundle through the replacement-sensitive store cache key."""

    return _cached_evidence_bundle_cached(
        store_path,
        evidence_status,
        store_identity=_store_projection_identity(store_path),
    )


def _clear_stored_rollout_caches() -> None:
    """Clear only the inspector caches after stores are created or replaced."""

    _cached_inventory.clear()
    _cached_candidate_population_cached.clear()
    _cached_projection_cached.clear()
    _cached_topology_cached.clear()
    _cached_failures_cached.clear()
    _cached_evidence_bundle_cached.clear()
    _cached_store_bundle_cached.clear()
    _cached_corpus_summary.clear()
    st.session_state.pop(CORPUS_SUMMARY_STATE_KEY, None)


def clear_rollout_page_caches() -> None:
    """Clear every read-only cache used by the rollout supervision pages.

    The training-dataset page owns its own read models, so its clear hook is
    imported lazily to avoid coupling either page's import path.  Store
    identities remain part of every cache key; this button is an operator
    escape hatch after an external artifact change, not the validity mechanism.
    """

    _clear_stored_rollout_caches()
    from ..training_dataset import _clear_training_dataset_caches

    _clear_training_dataset_caches()


@st.cache_data(show_spinner="Aggregating validated rollout stores…", max_entries=8)
def _cached_corpus_summary(
    store_paths: tuple[str, ...],
    store_identities: tuple[str, ...],
) -> RolloutCorpusSummary:
    """Build an explicit corpus summary bound to ordered store identities."""

    del store_identities
    return build_rollout_corpus_summary(Path(path) for path in store_paths)
