"""Cache and identity owner for the stored-rollout Streamlit panel.

The page remains responsible for rendering.  This module owns replacement-
sensitive cache keys, lazy inspection projections, and explicit invalidation.
"""

from __future__ import annotations

import hashlib
import json
from functools import wraps
from pathlib import Path
from typing import Any

import streamlit as st

from ...configs import PathConfig
from ...dataset_topology import build_dataset_topology
from ...rollouts import RolloutZarrStoreReader
from ...rollouts.inspection import (
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
    selected_candidate_rank_rows,
    selected_depth_summary_rows,
    store_invariant_rows,
    suspicious_rollout_rows,
    target_audit_rows,
    temporal_metric_summary_rows,
)
from ...rollouts.reporting import build_thesis_report_frames, serialize_thesis_report_bundle


def _store_projection_identity(store_path: str | Path) -> str:
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
        return f"store:{seal or 'unpromoted'}:{digest.hexdigest()}"
    except OSError:
        try:
            stat = path.stat()
            return f"store:{stat.st_size}:{stat.st_mtime_ns}"
        except OSError:
            return "missing"


def _read_json_mapping(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


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


def _cached_store_bundle(store_path: str) -> tuple[RolloutZarrStoreReader, Any, dict[str, Any]]:
    """Open a store through its current replacement-sensitive identity."""

    return _cached_store_bundle_cached(store_path, store_identity=_store_projection_identity(store_path))


def cached_store_bundle(store_path: str) -> tuple[RolloutZarrStoreReader, Any, dict[str, Any]]:
    return _cached_store_bundle(store_path)


@st.cache_data(show_spinner="Scanning rollout stores…", max_entries=8)
def _cached_inventory(cache_root: str) -> list[dict[str, object]]:
    """Project immutable rollout-store inventory once per cache root."""

    return rollout_store_inventory_rows(discover_rollout_store_paths(Path(cache_root)), validate=False)


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_candidate_population_cached(
    store_path: str, store_identity: str, sample_size: int = 500
) -> dict[str, object]:
    """Build candidate evidence once per immutable store identity."""

    reader, _, _ = _cached_store_bundle_cached(store_path, store_identity=store_identity)
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
    step_indices: tuple[int, ...] | None = None,
    deep_count: bool = False,
    q_h_chunk_size: int = 1024,
    q_h_state_limit: int | None = None,
    store_identity: str = "",
) -> Any:
    """Cache a named inspection projection for one validated store identity."""

    reader, _, manifest_payload = _cached_store_bundle_cached(store_path, store_identity=store_identity)
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
        attrs = manifest_payload.get("root_attrs", {})
        attrs = attrs if isinstance(attrs, dict) else {}
        return discounted_rollout_return_rows(
            reader, reader, return_semantics=attrs.get("return_semantics"), discount_gamma=attrs.get("discount_gamma")
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
            reader, rollout_row_id=rollout_row_id, step_row_id=step_row_id, limit=limit, row_callback=rows.append
        )
        return rows
    if projection == "candidate_group":
        if group_by is None:
            raise ValueError("candidate_group projection requires group_by")
        if not hasattr(reader, "array"):
            audit_rows = _cached_projection(store_path, "candidates", limit=limit)
            return candidate_group_summary_rows(reader, group_by=group_by, audit_rows=audit_rows)
        evidence = _cached_candidate_population_cached(store_path, store_identity)
        return evidence["groups"][group_by]
    if projection in {"candidate_composition", "candidate_calibration"}:
        if group_by is None:
            raise ValueError(f"{projection} projection requires group_by")
        evidence = _cached_candidate_population_cached(store_path, store_identity)
        return evidence["composition" if projection == "candidate_composition" else "calibration"][group_by]
    if projection == "candidate_collision":
        return _cached_candidate_population_cached(store_path, store_identity)["collision"]
    if projection == "candidate_sample":
        size = 500 if limit is None else limit
        return _cached_candidate_population_cached(store_path, store_identity, size)["sample"]
    if projection == "candidate_population":
        return _cached_candidate_population_cached(store_path, store_identity)
    if projection == "q_h":
        _, validation, _ = _cached_store_bundle_cached(store_path, store_identity=store_identity)
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
    if projection == "depth_summary":
        return selected_depth_summary_rows(reader, rollout_row_id=rollout_row_id, limit=limit)
    raise ValueError(f"Unknown cached rollout projection: {projection}")


@wraps(_cached_projection_cached.__wrapped__)
def _cached_projection(store_path: str, projection: str, **kwargs: Any) -> Any:
    """Dispatch a demand-backed projection with a fresh identity key."""

    return _cached_projection_cached(
        store_path, projection, store_identity=_store_projection_identity(store_path), **kwargs
    )


def cached_projection(store_path: str, projection: str, **kwargs: Any) -> Any:
    return _cached_projection(store_path, projection, **kwargs)


@st.cache_resource(show_spinner="Resolving dataset topology…", max_entries=16)
def _cached_topology_cached(
    store_path: str,
    vin_store_dirs: tuple[str, ...],
    paths: PathConfig,
    selected_source_row_id: int | None = None,
    *,
    store_identity: str = "",
) -> Any:
    """Resolve topology while retaining its structured cache arguments."""

    return build_dataset_topology(
        rollout_store_dir=Path(store_path),
        vin_store_dirs=[Path(value) for value in vin_store_dirs],
        path_config=paths,
        selected_source_row_id=selected_source_row_id,
    )


def _cached_topology(
    store_path: str, vin_store_dirs: tuple[str, ...], paths: PathConfig, selected_source_row_id: int | None = None
) -> Any:
    return _cached_topology_cached(
        store_path, vin_store_dirs, paths, selected_source_row_id, store_identity=_store_projection_identity(store_path)
    )


def cached_topology(
    store_path: str, vin_store_dirs: tuple[str, ...], paths: PathConfig, selected_source_row_id: int | None = None
) -> Any:
    return _cached_topology(store_path, vin_store_dirs, paths, selected_source_row_id)


@st.cache_data(show_spinner="Evaluating failure predicates…", max_entries=32)
def _cached_failures_cached(
    store_path: str,
    min_valid_candidates: int,
    dominant_invalid_fraction: float,
    max_step_distance_m: float,
    *,
    store_identity: str = "",
) -> list[dict[str, object]]:
    """Cache failure triage for one replacement-sensitive store."""

    reader, _, _ = _cached_store_bundle_cached(store_path, store_identity=store_identity)
    return suspicious_rollout_rows(
        reader,
        config=RolloutSuspiciousQueryConfig(
            min_valid_candidates=min_valid_candidates,
            dominant_invalid_fraction=dominant_invalid_fraction,
            max_step_distance_m=max_step_distance_m,
        ),
    )


def _cached_failures(
    store_path: str, min_valid_candidates: int, dominant_invalid_fraction: float, max_step_distance_m: float
) -> list[dict[str, object]]:
    return _cached_failures_cached(
        store_path,
        min_valid_candidates,
        dominant_invalid_fraction,
        max_step_distance_m,
        store_identity=_store_projection_identity(store_path),
    )


def cached_failures(
    store_path: str, min_valid_candidates: int, dominant_invalid_fraction: float, max_step_distance_m: float
) -> list[dict[str, object]]:
    return _cached_failures(store_path, min_valid_candidates, dominant_invalid_fraction, max_step_distance_m)


@st.cache_data(show_spinner="Building deterministic evidence bundle…", max_entries=16)
def _cached_evidence_bundle_cached(store_path: str, evidence_status: str, *, store_identity: str = "") -> bytes:
    """Build one deterministic report bundle for a replacement-sensitive store."""

    return serialize_thesis_report_bundle(
        build_thesis_report_frames([Path(store_path)], evidence_status=evidence_status)
    )


def _cached_evidence_bundle(store_path: str, evidence_status: str) -> bytes:
    return _cached_evidence_bundle_cached(
        store_path, evidence_status, store_identity=_store_projection_identity(store_path)
    )


def cached_evidence_bundle(store_path: str, evidence_status: str) -> bytes:
    return _cached_evidence_bundle(store_path, evidence_status)


def _named_projection(store_path: str, projection: str, **kwargs: Any) -> Any:
    """Invoke the private projection implementation through a named owner."""

    return _cached_projection(store_path, projection, **kwargs)


def cached_inventory(cache_root: str) -> list[dict[str, object]]:
    return _cached_inventory(cache_root)


def cached_invariants(store_path: str) -> Any:
    return _named_projection(store_path, "invariants")


def cached_header(store_path: str) -> Any:
    return _named_projection(store_path, "header")


def cached_cohorts(store_path: str) -> Any:
    return _named_projection(store_path, "cohorts")


def cached_paired(store_path: str) -> Any:
    return _named_projection(store_path, "paired")


def cached_steps(store_path: str, **kwargs: Any) -> Any:
    return _named_projection(store_path, "steps", **kwargs)


def cached_reconstruction_metrics(store_path: str) -> Any:
    return _named_projection(store_path, "reconstruction_metrics")


def cached_reconstruction_endpoints(store_path: str) -> Any:
    return _named_projection(store_path, "reconstruction_endpoints")


def cached_discounted_returns(store_path: str) -> Any:
    return _named_projection(store_path, "discounted_returns")


def cached_headroom(store_path: str) -> Any:
    return _named_projection(store_path, "headroom")


def cached_temporal(store_path: str, **kwargs: Any) -> Any:
    return _named_projection(store_path, "temporal", **kwargs)


def cached_candidate_flow(store_path: str, **kwargs: Any) -> Any:
    return _named_projection(store_path, "candidate_flow", **kwargs)


def cached_ranks(store_path: str, **kwargs: Any) -> Any:
    return _named_projection(store_path, "ranks", **kwargs)


def cached_targets(store_path: str) -> Any:
    return _named_projection(store_path, "targets")


def cached_masks(store_path: str) -> Any:
    return _named_projection(store_path, "masks")


def cached_candidates(store_path: str, **kwargs: Any) -> Any:
    return _named_projection(store_path, "candidates", **kwargs)


def cached_candidate_group(store_path: str, **kwargs: Any) -> Any:
    return _named_projection(store_path, "candidate_group", **kwargs)


def cached_candidate_population(store_path: str, **kwargs: Any) -> Any:
    return _named_projection(store_path, "candidate_population", **kwargs)


def cached_q_h(store_path: str, **kwargs: Any) -> Any:
    return _named_projection(store_path, "q_h", **kwargs)


def cached_tree(store_path: str) -> Any:
    return _named_projection(store_path, "tree")


def cached_root_geometry(store_path: str, **kwargs: Any) -> Any:
    return _named_projection(store_path, "root_geometry", **kwargs)


def cached_depth_summary(store_path: str, **kwargs: Any) -> Any:
    return _named_projection(store_path, "depth_summary", **kwargs)


def clear_stored_rollout_caches() -> None:
    """Clear every stored-rollout cache owner, including inventory and candidates."""

    for owner in (
        _cached_inventory,
        _cached_store_bundle_cached,
        _cached_projection_cached,
        _cached_candidate_population_cached,
        _cached_topology_cached,
        _cached_failures_cached,
        _cached_evidence_bundle_cached,
    ):
        owner.clear()


class StoredRolloutSession:
    """Fixed-identity handle for one selected store and rerun."""

    def __init__(
        self,
        canonical_path: Path,
        store_identity: str,
        reader: Any,
        validation: Any,
        manifest_payload: dict[str, Any],
        inventory_row: dict[str, object] | None,
    ) -> None:
        self.canonical_path = canonical_path
        self.store_identity = store_identity
        self.reader = reader
        self.validation = validation
        self.manifest_payload = manifest_payload
        self.inventory_row = inventory_row

    def projection(self, projection: str, **kwargs: Any) -> Any:
        """Read a reader-bound projection using this handle's captured identity."""

        return _cached_projection_cached(
            self.canonical_path.as_posix(), projection, store_identity=self.store_identity, **kwargs
        )

    def candidate_population(self, sample_size: int = 500) -> dict[str, object]:
        return _cached_candidate_population_cached(self.canonical_path.as_posix(), self.store_identity, sample_size)

    def failures(
        self, min_valid_candidates: int, dominant_invalid_fraction: float, max_step_distance_m: float
    ) -> list[dict[str, object]]:
        return _cached_failures_cached(
            self.canonical_path.as_posix(),
            min_valid_candidates,
            dominant_invalid_fraction,
            max_step_distance_m,
            store_identity=self.store_identity,
        )

    def topology(
        self, vin_store_dirs: tuple[str, ...], paths: PathConfig, selected_source_row_id: int | None = None
    ) -> Any:
        return _cached_topology(self.canonical_path.as_posix(), vin_store_dirs, paths, selected_source_row_id)

    def evidence_bundle(self, evidence_status: str) -> bytes:
        return _cached_evidence_bundle(self.canonical_path.as_posix(), evidence_status)


def open_stored_rollout_session(
    path: str | Path, inventory_row: dict[str, object] | None = None
) -> StoredRolloutSession:
    """Open one fixed-identity selected-store session without deep reads."""

    canonical_path = Path(path).absolute()
    identity = _store_projection_identity(canonical_path.as_posix())
    reader, validation, manifest_payload = _cached_store_bundle_cached(
        canonical_path.as_posix(), store_identity=identity
    )
    return StoredRolloutSession(canonical_path, identity, reader, validation, manifest_payload, inventory_row)
