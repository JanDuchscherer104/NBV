"""Typed read-only session and named caches for rollout supervision.

This module is the only Streamlit-page owner of rollout-store lifecycle and
array-backed inspection calls. Section modules consume :class:`StoredRolloutSession`
methods and never decode Zarr arrays directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import streamlit as st

from ....configs import PathConfig
from ....dataset_topology import DatasetTopology, build_dataset_topology
from ....rollouts import RolloutZarrStoreReader
from ....rollouts.inspection import (
    RolloutSuspiciousQueryConfig,
    candidate_audit_rows,
    candidate_evidence_availability_rows,
    candidate_family_composition_rows,
    comparable_policy_cohorts,
    discounted_rollout_return_rows,
    discover_rollout_store_paths,
    mask_combination_rows,
    oracle_headroom_evidence,
    rollout_header_summary,
    rollout_step_objective_rows,
    rollout_store_inventory_rows,
    selected_candidate_rank_rows,
    selected_depth_preview,
    selected_depth_summary_rows,
    store_invariant_rows,
    suspicious_rollout_rows,
    target_audit_rows,
    temporal_metric_summary_rows,
)
from ....rollouts.reporting import build_thesis_report_frames, serialize_thesis_report_bundle
from ....rollouts.zarr_store import RolloutZarrValidationResult


@dataclass(frozen=True, slots=True)
class StoredRolloutCapabilities:
    """Optional persisted payloads available to one inspector session."""

    selected_depth: bool
    """Whether privileged selected-action depth payloads are declared enabled."""

    target_eval_crops: bool
    """Whether privileged target-evaluation crops are declared enabled."""

    candidate_diagnostics: bool
    """Whether the store contains the candidate-diagnostics group."""

    q_h: bool
    """Whether the derived finite-candidate ``q_h`` group is present."""


@dataclass(frozen=True, slots=True)
class StoredRolloutSession:
    """Immutable read-only view of one canonical rollout-store selection.

    The session owns reader lifecycle, validation, manifest/header projections,
    optional-payload capabilities, and selected inventory fallback. Projection
    methods are named cache seams over :mod:`aria_nbv.rollouts.inspection`.
    """

    store_path: Path
    """Canonical absolute path identifying the selected immutable Zarr store."""

    reader: RolloutZarrStoreReader
    """Cached read-only store reader; section code must not decode arrays directly."""

    validation: RolloutZarrValidationResult
    """Fresh schema, linkage, mask, label, and provenance validation result."""

    manifest_payload: dict[str, Any]
    """Root attributes and sidecar manifest, or an explicit empty fallback."""

    header_summary: dict[str, object]
    """Lightweight store facts with missing row counts filled from inventory."""

    capabilities: StoredRolloutCapabilities
    """Optional persisted payload families available to bounded inspector views."""

    inventory_row: dict[str, object] | None
    """Selected discovery row retained for stale-store diagnostics and metadata."""

    @property
    def identity(self) -> str:
        """Return the canonical cache and UI identity for this store."""

        return self.store_path.as_posix()

    @property
    def candidate_count(self) -> int:
        """Return the validated full-shell candidate-row count."""

        return int(self.validation.num_candidates)

    def invariants(self) -> list[dict[str, object]]:
        """Return scientific and structural invariant evidence rows."""

        return _cached_invariants(self.identity)

    def comparable_cohorts(self) -> dict[str, object]:
        """Return exact policy-comparison cohorts and mismatch evidence."""

        return _cached_comparable_cohorts(self.identity)

    def steps(self, *, rollout_row_id: int | None = None) -> list[dict[str, object]]:
        """Return factual selected-step rows, optionally for one rollout."""

        return _cached_steps(self.identity, rollout_row_id)

    def temporal_summary(self, *, metric: str, group_fields: tuple[str, ...]) -> list[dict[str, object]]:
        """Aggregate one validated temporal metric over depth and strata."""

        return _cached_temporal_summary(self.identity, metric, group_fields)

    def discounted_returns(self) -> dict[str, object]:
        """Return discounted factual returns when the manifest contract permits derivation."""

        return _cached_discounted_returns(
            self.identity,
            self.header_summary.get("q_h_return_semantics"),
            self.header_summary.get("discount_gamma"),
        )

    def oracle_headroom(self) -> dict[str, object]:
        """Return exact-role headroom evidence or structured blockers."""

        return _cached_oracle_headroom(self.identity)

    def candidate_composition(self) -> list[dict[str, object]]:
        """Return lightweight family composition and actor-valid availability."""

        return _cached_candidate_composition(self.identity)

    def candidate_evidence_availability(self) -> list[dict[str, object]]:
        """Return candidate plot prerequisites without loading candidate payloads."""

        return _cached_candidate_evidence_availability(self.identity)

    def selected_candidate_ranks(
        self,
        *,
        policies: tuple[str, ...] | None = None,
        step_indices: tuple[int, ...] | None = None,
    ) -> list[dict[str, object]]:
        """Return selected-action policy/oracle ranks over valid alternatives."""

        return _cached_selected_candidate_ranks(self.identity, policies, step_indices)

    def targets(self) -> list[dict[str, object]]:
        """Return persisted target-task and privileged matching audit rows."""

        return _cached_targets(self.identity)

    def mask_combinations(self) -> list[dict[str, object]]:
        """Return observed actor, oracle, training, and selection mask combinations."""

        return _cached_mask_combinations(self.identity)

    def candidates(
        self,
        *,
        rollout_row_id: int | None = None,
        step_row_id: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        """Return normalized candidate rows for an explicit bounded population."""

        return _cached_candidates(self.identity, rollout_row_id, step_row_id, limit)

    def selected_depth_summary(
        self,
        *,
        rollout_row_id: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        """Return bounded selected-action depth summaries for one rollout."""

        return _cached_selected_depth_summary(self.identity, rollout_row_id, limit)

    def selected_depth_preview(self, *, step_row_id: int) -> dict[str, object]:
        """Return one bounded privileged selected-depth preview."""

        return _cached_selected_depth_preview(self.identity, step_row_id)

    def failures(
        self,
        *,
        min_valid_candidates: int = 3,
        dominant_invalid_fraction: float = 0.8,
        max_step_distance_m: float = 1.25,
    ) -> list[dict[str, object]]:
        """Return heuristic anomaly rows for one explicit threshold tuple."""

        return _cached_failures(
            self.identity,
            min_valid_candidates,
            dominant_invalid_fraction,
            max_step_distance_m,
        )

    def topology(
        self,
        *,
        vin_store_dirs: tuple[str, ...],
        paths: PathConfig,
        selected_source_row_id: int | None = None,
    ) -> DatasetTopology:
        """Resolve cross-store topology for the selected rollout store."""

        return _cached_topology(self.identity, vin_store_dirs, paths, selected_source_row_id)

    def rollout_ids(self) -> list[int]:
        """Return stable rollout-row identifiers without exposing Zarr decoding to UI code."""

        return _cached_rollout_ids(self.identity)

    def evidence_bundle(self, *, evidence_status: Literal["pilot", "confirmatory"]) -> bytes:
        """Build a deterministic pilot or confirmatory evidence bundle."""

        return _cached_evidence_bundle(self.identity, evidence_status)


def open_stored_rollout_session(
    store_path: Path,
    *,
    inventory_row: dict[str, object] | None,
) -> StoredRolloutSession:
    """Open one canonical read-only session using cached immutable store state."""

    canonical = store_path.expanduser().resolve()
    reader, validation, manifest_payload, capabilities = _cached_store_core(canonical.as_posix())
    header = dict(_cached_header(canonical.as_posix()))
    _fill_header_counts_from_inventory(header, inventory_row)
    return StoredRolloutSession(
        store_path=canonical,
        reader=reader,
        validation=validation,
        manifest_payload=manifest_payload,
        header_summary=header,
        capabilities=capabilities,
        inventory_row=None if inventory_row is None else dict(inventory_row),
    )


@st.cache_data(show_spinner="Scanning rollout stores…", max_entries=8)
def rollout_store_inventory(cache_root: str) -> list[dict[str, object]]:
    """Discover immutable rollout stores below one canonical cache root."""

    return rollout_store_inventory_rows(discover_rollout_store_paths(Path(cache_root)), validate=False)


@st.cache_resource(show_spinner=False)
def _cached_store_core(
    store_path: str,
) -> tuple[
    RolloutZarrStoreReader,
    RolloutZarrValidationResult,
    dict[str, Any],
    StoredRolloutCapabilities,
]:
    reader = RolloutZarrStoreReader(Path(store_path))
    validation = reader.validate()
    try:
        manifest_payload = reader.manifest()
    except Exception:
        manifest_payload = {"root_attrs": {}, "manifest": {}}
    root_attrs = manifest_payload.get("root_attrs", {})
    capabilities = StoredRolloutCapabilities(
        selected_depth=bool(root_attrs.get("selected_depth_enabled", False)),
        target_eval_crops=bool(root_attrs.get("target_eval_crops_enabled", False)),
        candidate_diagnostics="candidate_diagnostics" in reader.root,
        q_h="q_h" in reader.root,
    )
    return reader, validation, manifest_payload, capabilities


def _reader(store_path: str) -> RolloutZarrStoreReader:
    return _cached_store_core(store_path)[0]


@st.cache_data(show_spinner="Loading rollout header…", max_entries=32)
def _cached_header(store_path: str) -> dict[str, object]:
    reader, _, manifest_payload, _ = _cached_store_core(store_path)
    return rollout_header_summary(reader, manifest_payload=manifest_payload)


@st.cache_data(show_spinner="Loading rollout invariants…", max_entries=32)
def _cached_invariants(store_path: str) -> list[dict[str, object]]:
    reader, _, manifest_payload, _ = _cached_store_core(store_path)
    return store_invariant_rows(reader, manifest_payload=manifest_payload)


@st.cache_data(show_spinner="Loading matched cohorts…", max_entries=32)
def _cached_comparable_cohorts(store_path: str) -> dict[str, object]:
    return comparable_policy_cohorts(_reader(store_path))


@st.cache_data(show_spinner="Loading factual rollout steps…", max_entries=128)
def _cached_steps(store_path: str, rollout_row_id: int | None) -> list[dict[str, object]]:
    return rollout_step_objective_rows(_reader(store_path), rollout_row_id=rollout_row_id)


@st.cache_data(show_spinner="Aggregating temporal evidence…", max_entries=128)
def _cached_temporal_summary(
    store_path: str,
    metric: str,
    group_fields: tuple[str, ...],
) -> list[dict[str, object]]:
    return temporal_metric_summary_rows(_reader(store_path), metric=metric, group_fields=group_fields)


@st.cache_data(show_spinner="Deriving discounted returns…", max_entries=32)
def _cached_discounted_returns(
    store_path: str,
    return_semantics: object,
    discount_gamma: object,
) -> dict[str, object]:
    return discounted_rollout_return_rows(
        _cached_steps(store_path, None),
        return_semantics=return_semantics,
        discount_gamma=discount_gamma,
    )


@st.cache_data(show_spinner="Evaluating exact oracle headroom…", max_entries=32)
def _cached_oracle_headroom(store_path: str) -> dict[str, object]:
    return oracle_headroom_evidence(_cached_comparable_cohorts(store_path))


@st.cache_data(show_spinner="Summarizing candidate composition…", max_entries=32)
def _cached_candidate_composition(store_path: str) -> list[dict[str, object]]:
    return candidate_family_composition_rows(_reader(store_path))


@st.cache_data(show_spinner=False, max_entries=32)
def _cached_candidate_evidence_availability(store_path: str) -> list[dict[str, object]]:
    return candidate_evidence_availability_rows(_reader(store_path))


@st.cache_data(show_spinner="Loading selected candidate ranks…", max_entries=64)
def _cached_selected_candidate_ranks(
    store_path: str,
    policies: tuple[str, ...] | None,
    step_indices: tuple[int, ...] | None,
) -> list[dict[str, object]]:
    return selected_candidate_rank_rows(_reader(store_path), policies=policies, step_indices=step_indices)


@st.cache_data(show_spinner="Loading target evidence…", max_entries=32)
def _cached_targets(store_path: str) -> list[dict[str, object]]:
    return target_audit_rows(_reader(store_path))


@st.cache_data(show_spinner="Loading mask combinations…", max_entries=32)
def _cached_mask_combinations(store_path: str) -> list[dict[str, object]]:
    return mask_combination_rows(_reader(store_path))


@st.cache_data(show_spinner="Loading candidate evidence…", max_entries=128)
def _cached_candidates(
    store_path: str,
    rollout_row_id: int | None,
    step_row_id: int | None,
    limit: int | None,
) -> list[dict[str, object]]:
    return candidate_audit_rows(
        _reader(store_path),
        rollout_row_id=rollout_row_id,
        step_row_id=step_row_id,
        limit=limit,
    )


@st.cache_data(show_spinner="Loading selected-depth summaries…", max_entries=64)
def _cached_selected_depth_summary(
    store_path: str,
    rollout_row_id: int | None,
    limit: int | None,
) -> list[dict[str, object]]:
    return selected_depth_summary_rows(_reader(store_path), rollout_row_id=rollout_row_id, limit=limit)


@st.cache_data(show_spinner="Loading selected-depth preview…", max_entries=32)
def _cached_selected_depth_preview(store_path: str, step_row_id: int) -> dict[str, object]:
    return selected_depth_preview(_reader(store_path), step_row_id=step_row_id)


@st.cache_data(show_spinner="Evaluating failure predicates…", max_entries=32)
def _cached_failures(
    store_path: str,
    min_valid_candidates: int,
    dominant_invalid_fraction: float,
    max_step_distance_m: float,
) -> list[dict[str, object]]:
    config = RolloutSuspiciousQueryConfig(
        min_valid_candidates=min_valid_candidates,
        dominant_invalid_fraction=dominant_invalid_fraction,
        max_step_distance_m=max_step_distance_m,
    )
    return suspicious_rollout_rows(_reader(store_path), config=config)


@st.cache_resource(show_spinner="Resolving dataset topology…", max_entries=16)
def _cached_topology(
    store_path: str,
    vin_store_dirs: tuple[str, ...],
    paths: PathConfig,
    selected_source_row_id: int | None,
) -> DatasetTopology:
    return build_dataset_topology(
        rollout_store_dir=Path(store_path),
        vin_store_dirs=[Path(value) for value in vin_store_dirs],
        path_config=paths,
        selected_source_row_id=selected_source_row_id,
    )


@st.cache_data(show_spinner="Loading rollout identities…", max_entries=32)
def _cached_rollout_ids(store_path: str) -> list[int]:
    values = _reader(store_path).array("rollouts/rollout_row_id").reshape(-1)
    return [int(value) for value in values.tolist()]


@st.cache_data(show_spinner="Building deterministic evidence bundle…", max_entries=16)
def _cached_evidence_bundle(
    store_path: str,
    evidence_status: Literal["pilot", "confirmatory"],
) -> bytes:
    frames = build_thesis_report_frames([Path(store_path)], evidence_status=evidence_status)
    return serialize_thesis_report_bundle(frames)


def _fill_header_counts_from_inventory(
    summary: dict[str, object],
    inventory_row: dict[str, object] | None,
) -> None:
    if inventory_row is None:
        return
    for header_key, inventory_key in (
        ("rollouts", "observed_rollouts"),
        ("steps", "observed_steps"),
        ("candidates", "observed_candidates"),
    ):
        if summary.get(header_key) is None:
            summary[header_key] = inventory_row.get(inventory_key)


_SESSION_CACHE_OWNERS = (
    rollout_store_inventory,
    _cached_store_core,
    _cached_header,
    _cached_invariants,
    _cached_comparable_cohorts,
    _cached_steps,
    _cached_temporal_summary,
    _cached_discounted_returns,
    _cached_oracle_headroom,
    _cached_candidate_composition,
    _cached_candidate_evidence_availability,
    _cached_selected_candidate_ranks,
    _cached_targets,
    _cached_mask_combinations,
    _cached_candidates,
    _cached_selected_depth_summary,
    _cached_selected_depth_preview,
    _cached_failures,
    _cached_topology,
    _cached_rollout_ids,
    _cached_evidence_bundle,
)


def clear_stored_rollout_caches() -> None:
    """Invalidate every session-owned discovery, store, and projection cache."""

    for cached in _SESSION_CACHE_OWNERS:
        cached.clear()


__all__ = [
    "StoredRolloutCapabilities",
    "StoredRolloutSession",
    "clear_stored_rollout_caches",
    "open_stored_rollout_session",
    "rollout_store_inventory",
]
