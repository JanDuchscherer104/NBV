"""Cache and identity owner for the stored-rollout Streamlit panel.

The page remains responsible for rendering.  This module owns replacement-
sensitive cache keys, lazy inspection projections, and explicit invalidation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import streamlit as st

from ...configs import PathConfig
from ...dataset_topology import build_dataset_topology
from ...rollouts import RolloutZarrStoreReader
from ...rollouts.inspection import (
    PromotionEvidence,
    RolloutSuspiciousQueryConfig,
    build_effective_streamlit_trust,
    build_schema_validation,
    candidate_audit_rows,
    candidate_flow_rows,
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
    """Return a constant-size replacement identity without reading payload chunks."""

    path = Path(store_path)
    try:
        success = _read_json_mapping(path / "_SUCCESS.json")
        manifest = _read_json_mapping(path / "manifest.json")
        success_seal = success.get("rollout_store_content_sha256") if success is not None else None
        generation = manifest.get("generation") if manifest is not None else None
        revision = generation.get("generation_revision_hash") if isinstance(generation, dict) else None
        marker_parts = []
        for name in ("manifest.json", "_SUCCESS.json", "_owner.json", "zarr.json"):
            marker = path / name
            try:
                stat = marker.stat()
            except OSError:
                continue
            marker_parts.append(f"{name}:{stat.st_size}:{stat.st_mtime_ns}:{stat.st_ino}")
        root_stat = path.stat()
        marker_parts.append(f".root:{root_stat.st_mtime_ns}:{root_stat.st_ino}")
        digest = hashlib.sha256("|".join(marker_parts).encode()).hexdigest()[:24]
        return f"store:{success_seal or 'unpromoted'}:{revision or 'unknown'}:{digest}"
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
    schema = build_schema_validation(reader)
    # Manifest provenance is part of the trust decision.  Never substitute an
    # empty payload: an unreadable manifest must prevent session creation and
    # every downstream scientific projection.
    manifest_payload = reader.manifest()
    promotion = PromotionEvidence(promoted_store_validation_error(reader, manifest_payload=manifest_payload))
    validation = build_effective_streamlit_trust(schema, promotion)
    return reader, validation, manifest_payload


@st.cache_data(show_spinner="Scanning rollout stores…", max_entries=8)
def _cached_inventory(cache_root: str) -> list[dict[str, object]]:
    """Project immutable rollout-store inventory once per cache root."""

    return rollout_store_inventory_rows(discover_rollout_store_paths(Path(cache_root)), validate=False)


def cached_inventory(cache_root: str) -> list[dict[str, object]]:
    """Return the shallow inventory used by the page selector."""

    return _cached_inventory(cache_root)


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_candidate_population_cached(
    store_path: str, store_identity: str, sample_size: int = 500
) -> dict[str, object]:
    """Build candidate evidence once per immutable store identity."""

    reader, _, _ = _cached_store_bundle_cached(store_path, store_identity=store_identity)
    return candidate_population_evidence(reader, sample_size=sample_size)


def _projection_reader(store_path: str, store_identity: str) -> tuple[RolloutZarrStoreReader, Any, dict[str, Any]]:
    """Return the validated reader shared by explicit projection owners."""

    return _cached_store_bundle_cached(store_path, store_identity=store_identity)


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_invariants_cached(store_path: str, *, store_identity: str = "") -> Any:
    reader, _, manifest = _projection_reader(store_path, store_identity)
    return store_invariant_rows(reader, manifest_payload=manifest)


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_header_cached(store_path: str, *, store_identity: str = "") -> Any:
    reader, _, manifest = _projection_reader(store_path, store_identity)
    return rollout_header_summary(reader, manifest_payload=manifest)


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_cohorts_cached(store_path: str, *, store_identity: str = "") -> Any:
    reader, _, _ = _projection_reader(store_path, store_identity)
    return comparable_policy_cohorts(reader)


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_paired_cached(store_path: str, *, store_identity: str = "") -> Any:
    reader, _, _ = _projection_reader(store_path, store_identity)
    return paired_policy_comparison_rows(reader)


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_steps_cached(store_path: str, *, rollout_row_id: int | None = None, store_identity: str = "") -> Any:
    reader, _, _ = _projection_reader(store_path, store_identity)
    return rollout_step_objective_rows(reader, rollout_row_id=rollout_row_id)


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_reconstruction_metrics_cached(store_path: str, *, store_identity: str = "") -> Any:
    reader, _, _ = _projection_reader(store_path, store_identity)
    return reconstruction_metric_summary_rows(reader)


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_reconstruction_endpoints_cached(store_path: str, *, store_identity: str = "") -> Any:
    reader, _, _ = _projection_reader(store_path, store_identity)
    return reconstruction_endpoint_summary_rows(reader)


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_discounted_returns_cached(store_path: str, *, store_identity: str = "") -> Any:
    reader, _, manifest = _projection_reader(store_path, store_identity)
    attrs = manifest.get("root_attrs", {})
    attrs = attrs if isinstance(attrs, dict) else {}
    return discounted_rollout_return_rows(
        reader, return_semantics=attrs.get("return_semantics"), discount_gamma=attrs.get("discount_gamma")
    )


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_headroom_cached(store_path: str, *, store_identity: str = "") -> Any:
    reader, _, _ = _projection_reader(store_path, store_identity)
    return oracle_headroom_evidence(reader)


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_temporal_cached(
    store_path: str, *, metric: str, group_fields: tuple[str, ...] = (), store_identity: str = ""
) -> Any:
    reader, _, _ = _projection_reader(store_path, store_identity)
    return temporal_metric_summary_rows(reader, metric=metric, group_fields=group_fields)


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_candidate_flow_cached(
    store_path: str,
    *,
    policies: tuple[str, ...] | None = None,
    step_indices: tuple[int, ...] | None = None,
    store_identity: str = "",
) -> Any:
    reader, _, _ = _projection_reader(store_path, store_identity)
    return candidate_flow_rows(reader, policies=policies, step_indices=step_indices)


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_ranks_cached(
    store_path: str,
    *,
    policies: tuple[str, ...] | None = None,
    step_indices: tuple[int, ...] | None = None,
    store_identity: str = "",
) -> Any:
    reader, _, _ = _projection_reader(store_path, store_identity)
    return selected_candidate_rank_rows(reader, policies=policies, step_indices=step_indices)


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_targets_cached(store_path: str, *, store_identity: str = "") -> Any:
    reader, _, _ = _projection_reader(store_path, store_identity)
    return target_audit_rows(reader)


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_masks_cached(store_path: str, *, store_identity: str = "") -> Any:
    reader, _, _ = _projection_reader(store_path, store_identity)
    return mask_combination_rows(reader)


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_candidates_cached(
    store_path: str,
    *,
    rollout_row_id: int | None = None,
    step_row_id: int | None = None,
    limit: int | None = None,
    store_identity: str = "",
) -> list[dict[str, object]]:
    reader, _, _ = _projection_reader(store_path, store_identity)
    rows: list[dict[str, object]] = []
    candidate_audit_rows(
        reader, rollout_row_id=rollout_row_id, step_row_id=step_row_id, limit=limit, row_callback=rows.append
    )
    return rows


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_q_h_cached(
    store_path: str,
    *,
    deep_count: bool = False,
    q_h_chunk_size: int = 1024,
    q_h_state_limit: int | None = None,
    store_identity: str = "",
) -> Any:
    reader, validation, _ = _projection_reader(store_path, store_identity)
    return q_h_evidence_rows(
        reader,
        deep_count=deep_count,
        chunk_size=q_h_chunk_size,
        state_row_limit=q_h_state_limit,
        validation_result=validation,
    )


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_tree_cached(store_path: str, *, store_identity: str = "") -> Any:
    reader, _, _ = _projection_reader(store_path, store_identity)
    return rollout_tree_summary_rows(reader)


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_root_geometry_cached(store_path: str, *, limit: int | None = None, store_identity: str = "") -> Any:
    reader, _, _ = _projection_reader(store_path, store_identity)
    rows = root_relative_candidate_rows(reader, actor_valid_only=False)
    return rows if limit is None else rows[:limit]


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_depth_summary_cached(
    store_path: str, *, rollout_row_id: int | None = None, limit: int | None = None, store_identity: str = ""
) -> Any:
    reader, _, _ = _projection_reader(store_path, store_identity)
    return selected_depth_summary_rows(reader, rollout_row_id=rollout_row_id, limit=limit)


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


@st.cache_data(show_spinner="Building deterministic evidence bundle…", max_entries=16)
def _cached_evidence_bundle_cached(store_path: str, evidence_status: str, *, store_identity: str = "") -> bytes:
    """Build one deterministic report bundle for a replacement-sensitive store."""

    return serialize_thesis_report_bundle(
        build_thesis_report_frames([Path(store_path)], evidence_status=evidence_status)
    )


def clear_stored_rollout_caches() -> None:
    """Clear every stored-rollout cache owner, including inventory and candidates."""

    for owner in (
        _cached_inventory,
        _cached_store_bundle_cached,
        _cached_invariants_cached,
        _cached_header_cached,
        _cached_cohorts_cached,
        _cached_paired_cached,
        _cached_steps_cached,
        _cached_reconstruction_metrics_cached,
        _cached_reconstruction_endpoints_cached,
        _cached_discounted_returns_cached,
        _cached_headroom_cached,
        _cached_temporal_cached,
        _cached_candidate_flow_cached,
        _cached_ranks_cached,
        _cached_targets_cached,
        _cached_masks_cached,
        _cached_candidates_cached,
        _cached_q_h_cached,
        _cached_tree_cached,
        _cached_root_geometry_cached,
        _cached_depth_summary_cached,
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

    def _assert_current_identity(self) -> str:
        """Reject projections after the selected path was atomically replaced."""

        current = _store_projection_identity(self.canonical_path)
        if current != self.store_identity:
            raise RuntimeError(
                "selected rollout store changed after this session opened; reopen the store before projecting evidence"
            )
        return self.store_identity

    def candidate_population(self, sample_size: int = 500) -> dict[str, object]:
        return _cached_candidate_population_cached(self.canonical_path.as_posix(), self.store_identity, sample_size)

    def invariants(self) -> Any:
        return _cached_invariants_cached(self.canonical_path.as_posix(), store_identity=self.store_identity)

    def header(self) -> Any:
        return _cached_header_cached(self.canonical_path.as_posix(), store_identity=self.store_identity)

    def cohorts(self) -> Any:
        return _cached_cohorts_cached(self.canonical_path.as_posix(), store_identity=self.store_identity)

    def paired(self) -> Any:
        return _cached_paired_cached(self.canonical_path.as_posix(), store_identity=self.store_identity)

    def steps(self, **kwargs: Any) -> Any:
        return _cached_steps_cached(self.canonical_path.as_posix(), store_identity=self.store_identity, **kwargs)

    def reconstruction_metrics(self) -> Any:
        return _cached_reconstruction_metrics_cached(self.canonical_path.as_posix(), store_identity=self.store_identity)

    def reconstruction_endpoints(self) -> Any:
        return _cached_reconstruction_endpoints_cached(
            self.canonical_path.as_posix(), store_identity=self.store_identity
        )

    def discounted_returns(self) -> Any:
        return _cached_discounted_returns_cached(self.canonical_path.as_posix(), store_identity=self.store_identity)

    def headroom(self) -> Any:
        return _cached_headroom_cached(self.canonical_path.as_posix(), store_identity=self.store_identity)

    def temporal(self, **kwargs: Any) -> Any:
        return _cached_temporal_cached(self.canonical_path.as_posix(), store_identity=self.store_identity, **kwargs)

    def candidate_flow(self, **kwargs: Any) -> Any:
        return _cached_candidate_flow_cached(
            self.canonical_path.as_posix(), store_identity=self.store_identity, **kwargs
        )

    def ranks(self, **kwargs: Any) -> Any:
        return _cached_ranks_cached(self.canonical_path.as_posix(), store_identity=self.store_identity, **kwargs)

    def targets(self) -> Any:
        return _cached_targets_cached(self.canonical_path.as_posix(), store_identity=self.store_identity)

    def masks(self) -> Any:
        return _cached_masks_cached(self.canonical_path.as_posix(), store_identity=self.store_identity)

    def candidates(self, **kwargs: Any) -> Any:
        return _cached_candidates_cached(self.canonical_path.as_posix(), store_identity=self.store_identity, **kwargs)

    def q_h(self, **kwargs: Any) -> Any:
        return _cached_q_h_cached(self.canonical_path.as_posix(), store_identity=self.store_identity, **kwargs)

    def tree(self) -> Any:
        return _cached_tree_cached(self.canonical_path.as_posix(), store_identity=self.store_identity)

    def root_geometry(self, **kwargs: Any) -> Any:
        return _cached_root_geometry_cached(
            self.canonical_path.as_posix(), store_identity=self.store_identity, **kwargs
        )

    def depth_summary(self, **kwargs: Any) -> Any:
        return _cached_depth_summary_cached(
            self.canonical_path.as_posix(), store_identity=self.store_identity, **kwargs
        )

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
        return _cached_topology_cached(
            self.canonical_path.as_posix(),
            vin_store_dirs,
            paths,
            selected_source_row_id,
            store_identity=self._assert_current_identity(),
        )

    def evidence_bundle(self, evidence_status: str) -> bytes:
        identity = self._assert_current_identity()
        bundle = _cached_evidence_bundle_cached(
            self.canonical_path.as_posix(), evidence_status, store_identity=identity
        )
        if _store_projection_identity(self.canonical_path) != identity:
            raise RuntimeError("selected rollout store changed while serializing evidence; reopen the store")
        return bundle


def open_stored_rollout_session(
    path: str | Path, inventory_row: dict[str, object] | None = None
) -> StoredRolloutSession:
    """Open one fixed-identity selected-store session without deep reads."""

    canonical_path = Path(path).expanduser().resolve()
    identity = _store_projection_identity(canonical_path.as_posix())
    reader, validation, manifest_payload = _cached_store_bundle_cached(
        canonical_path.as_posix(), store_identity=identity
    )
    return StoredRolloutSession(canonical_path, identity, reader, validation, manifest_payload, inventory_row)
