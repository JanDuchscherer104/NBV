"""Sole Streamlit lifecycle and cache owner for stored-rollout inspection.

This module owns opening one canonical read-only store selection, validating it, and
exposes lazy typed projections from :mod:`aria_nbv.rollouts.inspection` and
:mod:`aria_nbv.rollouts.reporting`. Cache identities bind the live store
manifest, selected audit path, and lazily measured audit content so stale or
wrong-store evidence fails closed. Section modules consume
:class:`StoredRolloutSession` methods and never decode Zarr arrays, load audit
artifacts, run independent evaluators, or invent export-readiness rules.
"""

from __future__ import annotations

import hashlib
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
    candidate_direction_evidence,
    candidate_evidence_availability_rows,
    candidate_family_composition_rows,
    candidate_geometry_evidence_rows,
    candidate_motion_support_evidence,
    candidate_spatial_support_evidence,
    candidate_state_composition_evidence,
    candidate_target_view_evidence,
    candidate_validity_evidence,
    comparable_policy_cohorts,
    deterministic_candidate_display_sample,
    discounted_rollout_return_rows,
    discover_rollout_store_paths,
    mask_combination_rows,
    oracle_headroom_evidence,
    policy_effect_evidence,
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
    validity_audit_evidence,
)
from ....rollouts.reporting import (
    build_thesis_report_frames,
    scientific_report_blockers,
    serialize_thesis_report_bundle,
)
from ....rollouts.scientific_audit import ScientificAuditArtifact, load_scientific_audit
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
class ScientificAuditState:
    """Typed, fail-closed status of the optional selected audit side artifact."""

    path: Path | None
    """Canonical selected JSON path, or ``None`` when no artifact is selected."""
    content_sha256: str | None
    """Selection-time file fingerprint used for cache invalidation."""
    bundle_sha256: str | None
    """Verified canonical artifact seal when strict loading succeeds."""
    artifact_status: str
    """Strict artifact status, or ``absent``/``invalid`` before reduction."""
    readiness: str
    """Permitted evidence use declared by the artifact contract."""
    comparison_protocol: str | None
    """Same-contract or robustness-characterization audit protocol."""
    selected_store_sha256: str
    """Manifest/content identity of the live selected rollout store."""
    audit_store_sha256: str | None
    """Rollout-store identity sealed into the audit provenance."""
    store_identity_matches: bool
    """Whether selected and audited rollout-store identities match exactly."""
    evidence_tier: Literal["confirmatory", "characterization", "blocked"]
    """Fail-closed UI tier after seal, readiness, and store-identity checks."""
    blockers: tuple[str, ...]
    """Stable reasons preventing confirmatory use; empty only when admissible."""


@dataclass(frozen=True, slots=True)
class CandidateScientificEvidence:
    """Full-population candidate reducers plus a bounded display-only sample."""

    generation_cohort_id: str
    """Exact candidate-generation context hash reduced by this DTO."""
    population_count: int
    """Complete candidate count used by every scientific reducer."""
    composition_rows: tuple[dict[str, object], ...]
    """State-then-scene macro family composition rows."""
    direction_evidence: dict[str, list[dict[str, object]]]
    """Equal-area density, spherical-cap, and angular-separation evidence."""
    spatial_rows: tuple[dict[str, object], ...]
    """Root-frame radius, distance, and height support in metres."""
    target_view_rows: tuple[dict[str, object], ...]
    """Target-distance summaries and explicit missing FOV/LOS evidence."""
    motion_rows: tuple[dict[str, object], ...]
    """Actor-valid motion, yaw, clearance, and collision-support summaries."""
    display_sample: dict[str, object]
    r"""Bounded stratified plot sample carrying $N_h$, $n_h$, $\pi_h$, and seed."""
    unavailable_rows: tuple[dict[str, object], ...]
    """Evidence families that cannot be inferred from persisted inputs."""


@dataclass(frozen=True, slots=True)
class ValidityScientificEvidence:
    """Persisted validity characterization and optional independent audit evidence."""

    characterization: dict[str, list[dict[str, object]]]
    """Full-population flow, mask, reason, and state/scene characterization."""
    audit: dict[str, object] | None
    """Weighted same-contract confusion/margin/boundary evidence when valid."""
    evidence_tier: Literal["confirmatory", "characterization", "blocked"]
    """Permitted interpretation after audit and store-identity gates."""
    blockers: tuple[str, ...]
    """Stable reasons suppressing independent validity claims."""


@dataclass(frozen=True, slots=True)
class StoredRolloutSession:
    """Immutable read-only view of one canonical rollout-store selection.

    The session owns reader lifecycle, validation, manifest/header projections,
    optional-payload capabilities, and selected inventory fallback. Projection
    methods are named cache seams over :mod:`aria_nbv.rollouts.inspection`.
    Candidate and validity scientific DTOs always separate full-population
    reducer inputs from bounded display samples. Audit I/O remains lazy until a
    projection or reporting gate explicitly requests it.
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

    audit_path: Path | None
    """Canonical optional audit JSON path; the artifact remains lazy."""

    audit_content_sha256: str | None
    """Always ``None`` at construction; :meth:`audit_state` hashes lazily."""

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

    def audit_state(self) -> ScientificAuditState:
        """Return typed audit identity/readiness without exposing the artifact."""

        store_sha256, audit_fingerprint = self._current_audit_cache_identity()
        return _cached_audit_state(self.identity, store_sha256, self._audit_path_key, audit_fingerprint)

    def audited_policy_effects(self) -> dict[str, object]:
        """Return independent exact-pair effects or explicit audit blockers."""

        store_sha256, audit_fingerprint = self._current_audit_cache_identity()
        return _cached_policy_effects(self.identity, store_sha256, self._audit_path_key, audit_fingerprint)

    def audited_endpoints(self) -> tuple[dict[str, object], ...]:
        """Return independently evaluated endpoint/budget rows when available."""

        store_sha256, audit_fingerprint = self._current_audit_cache_identity()
        return _cached_audited_endpoints(self.identity, store_sha256, self._audit_path_key, audit_fingerprint)

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

        selected_store_sha256 = str(self.reader.root.attrs.get("manifest_sha256", ""))
        return _cached_candidates(self.identity, selected_store_sha256, rollout_row_id, step_row_id, limit)

    def candidate_scientific_evidence(self, *, generation_cohort_id: str) -> CandidateScientificEvidence:
        """Run full-population candidate reducers for one explicit generation cohort."""

        store_sha256, audit_fingerprint = self._current_audit_cache_identity()
        return _cached_candidate_scientific_evidence(
            self.identity,
            store_sha256,
            generation_cohort_id,
            self._audit_path_key,
            audit_fingerprint,
        )

    def validity_scientific_evidence(self, *, generation_cohort_id: str) -> ValidityScientificEvidence:
        """Return persisted validity characterization and lazy independent audit evidence."""

        store_sha256, audit_fingerprint = self._current_audit_cache_identity()
        return _cached_validity_scientific_evidence(
            self.identity,
            store_sha256,
            generation_cohort_id,
            self._audit_path_key,
            audit_fingerprint,
        )

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
        """Build a deterministic bundle bound to the live store and selected audit."""

        store_sha256, audit_fingerprint = self._current_audit_cache_identity()
        return _cached_evidence_bundle(
            self.identity,
            store_sha256,
            self._audit_path_key,
            audit_fingerprint,
            evidence_status,
        )

    def confirmatory_export_blockers(self) -> tuple[str, ...]:
        """Return lazy reporting-owned blockers for confirmatory bundle export."""

        store_sha256, audit_fingerprint = self._current_audit_cache_identity()
        return _cached_confirmatory_export_blockers(
            self.identity,
            store_sha256,
            self._audit_path_key,
            audit_fingerprint,
        )

    @property
    def _audit_path_key(self) -> str | None:
        return None if self.audit_path is None else self.audit_path.as_posix()

    def _current_audit_cache_identity(self) -> tuple[str, str | None]:
        """Return live store identity and lazily measured audit content fingerprint."""

        store_sha256 = str(self.reader.root.attrs.get("manifest_sha256", ""))
        audit_fingerprint = None if self.audit_path is None else _lazy_audit_file_fingerprint(self.audit_path)
        return store_sha256, audit_fingerprint


def open_stored_rollout_session(
    store_path: Path,
    *,
    inventory_row: dict[str, object] | None,
    audit_path: Path | None = None,
) -> StoredRolloutSession:
    """Open one canonical read-only session using cached immutable store state."""

    canonical = store_path.expanduser().resolve()
    canonical_audit = None if audit_path is None else audit_path.expanduser().resolve()
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
        audit_path=canonical_audit,
        audit_content_sha256=None,
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


def _lazy_audit_file_fingerprint(path: Path) -> str:
    """Hash audit bytes only when an active session projection requests them."""

    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        return f"unreadable:{type(exc).__name__}:{exc.errno}"


def _content_sha256_or_none(fingerprint: str | None) -> str | None:
    """Expose only an actual lowercase SHA-256, not an unreadable cache token."""

    if fingerprint is None or len(fingerprint) != 64:
        return None
    return fingerprint if all(character in "0123456789abcdef" for character in fingerprint) else None


@st.cache_resource(show_spinner="Loading scientific audit…", max_entries=16)
def _cached_audit_artifact(
    store_path: str,
    selected_store_sha256: str,
    audit_path: str | None,
    audit_fingerprint: str | None,
) -> tuple[ScientificAuditArtifact | None, tuple[str, ...]]:
    del audit_fingerprint
    live_store_sha256 = str(_reader(store_path).root.attrs.get("manifest_sha256", ""))
    if live_store_sha256 != selected_store_sha256:
        return None, (f"selected_store_identity_changed:expected={selected_store_sha256}:observed={live_store_sha256}",)
    if audit_path is None:
        return None, ("scientific_audit_absent",)
    try:
        artifact = load_scientific_audit(Path(audit_path))
    except Exception as exc:
        return None, (f"scientific_audit_invalid:{type(exc).__name__}:{exc}",)
    if artifact.provenance.rollout_store_sha256 != selected_store_sha256:
        return artifact, (
            "scientific_audit_wrong_store:"
            f"expected={selected_store_sha256}:observed={artifact.provenance.rollout_store_sha256}",
        )
    return artifact, ()


@st.cache_data(show_spinner=False, max_entries=32)
def _cached_audit_state(
    store_path: str,
    selected_store_sha256: str,
    audit_path: str | None,
    audit_fingerprint: str | None,
) -> ScientificAuditState:
    artifact, blockers = _cached_audit_artifact(
        store_path,
        selected_store_sha256,
        audit_path,
        audit_fingerprint,
    )
    identity_matches = artifact is not None and artifact.provenance.rollout_store_sha256 == selected_store_sha256
    if blockers:
        tier: Literal["confirmatory", "characterization", "blocked"] = (
            "characterization" if blockers == ("scientific_audit_absent",) else "blocked"
        )
    elif artifact is not None and artifact.status.value == "pass" and artifact.readiness.value == "confirmatory":
        tier = "confirmatory"
    elif artifact is not None and artifact.status.value == "characterization":
        tier = "characterization"
    else:
        tier = "blocked"
    if artifact is None:
        artifact_status = "absent" if blockers == ("scientific_audit_absent",) else "invalid"
    else:
        artifact_status = artifact.status.value
    return ScientificAuditState(
        path=None if audit_path is None else Path(audit_path),
        content_sha256=_content_sha256_or_none(audit_fingerprint),
        bundle_sha256=None if artifact is None else artifact.bundle_sha256,
        artifact_status=artifact_status,
        readiness="unavailable" if artifact is None else artifact.readiness.value,
        comparison_protocol=None if artifact is None else artifact.comparison_protocol.value,
        selected_store_sha256=selected_store_sha256,
        audit_store_sha256=None if artifact is None else artifact.provenance.rollout_store_sha256,
        store_identity_matches=identity_matches,
        evidence_tier=tier,
        blockers=blockers,
    )


@st.cache_data(show_spinner="Reducing audited policy effects…", max_entries=32)
def _cached_policy_effects(
    store_path: str,
    selected_store_sha256: str,
    audit_path: str | None,
    audit_fingerprint: str | None,
) -> dict[str, object]:
    artifact, blockers = _cached_audit_artifact(
        store_path,
        selected_store_sha256,
        audit_path,
        audit_fingerprint,
    )
    if artifact is None or blockers:
        return {"available": False, "blocker_rows": [{"reason": reason} for reason in blockers]}
    evidence = policy_effect_evidence(artifact)
    return {"available": True, **evidence}


@st.cache_data(show_spinner="Loading audited endpoints…", max_entries=32)
def _cached_audited_endpoints(
    store_path: str,
    selected_store_sha256: str,
    audit_path: str | None,
    audit_fingerprint: str | None,
) -> tuple[dict[str, object], ...]:
    artifact, blockers = _cached_audit_artifact(
        store_path,
        selected_store_sha256,
        audit_path,
        audit_fingerprint,
    )
    if artifact is None or blockers:
        return ()
    return tuple(
        {
            **row.model_dump(mode="json"),
            "semantic_role": row.match_identity.treatment.semantic_role.value,
            "cohort_id": row.cohort_id,
            "unused_budget": None
            if row.achieved_steps is None or row.budget is None
            else row.budget - row.achieved_steps,
        }
        for row in artifact.endpoint_rows
    )


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
    selected_store_sha256: str,
    rollout_row_id: int | None,
    step_row_id: int | None,
    limit: int | None,
) -> list[dict[str, object]]:
    live_store_sha256 = str(_reader(store_path).root.attrs.get("manifest_sha256", ""))
    if live_store_sha256 != selected_store_sha256:
        raise ValueError(
            "Selected rollout-store identity changed while loading candidates: "
            f"expected {selected_store_sha256}, observed {live_store_sha256}."
        )
    return candidate_audit_rows(
        _reader(store_path),
        rollout_row_id=rollout_row_id,
        step_row_id=step_row_id,
        limit=limit,
    )


@st.cache_data(show_spinner="Reducing candidate scientific evidence…", max_entries=16)
def _cached_candidate_scientific_evidence(
    store_path: str,
    selected_store_sha256: str,
    generation_cohort_id: str,
    audit_path: str | None,
    audit_fingerprint: str | None,
) -> CandidateScientificEvidence:
    rows = [
        row
        for row in _cached_candidates(store_path, selected_store_sha256, None, None, None)
        if str(row.get("generation_cohort_id")) == generation_cohort_id
    ]
    if not rows:
        return CandidateScientificEvidence(
            generation_cohort_id=generation_cohort_id,
            population_count=0,
            composition_rows=(),
            direction_evidence={"density_rows": [], "cap_rows": [], "angular_support_rows": []},
            spatial_rows=(),
            target_view_rows=(),
            motion_rows=(),
            display_sample={"rows": [], "strata": [], "metadata": {"display_only": True}},
            unavailable_rows=({"reason": "generation_cohort_absent"},),
        )
    geometry = candidate_geometry_evidence_rows(rows)
    audit_state = _cached_audit_state(
        store_path,
        selected_store_sha256,
        audit_path,
        audit_fingerprint,
    )
    unavailable: list[dict[str, object]] = []
    if audit_state.evidence_tier != "confirmatory":
        unavailable.append(
            {
                "evidence": "independently_recomputed_target_view",
                "reason": "confirmatory_scientific_audit_unavailable",
                "audit_blockers": audit_state.blockers,
            }
        )
    return CandidateScientificEvidence(
        generation_cohort_id=generation_cohort_id,
        population_count=len(rows),
        composition_rows=tuple(candidate_state_composition_evidence(rows)),
        direction_evidence=candidate_direction_evidence(geometry),
        spatial_rows=tuple(candidate_spatial_support_evidence(geometry)),
        target_view_rows=tuple(candidate_target_view_evidence(geometry)),
        motion_rows=tuple(candidate_motion_support_evidence(rows)),
        display_sample=deterministic_candidate_display_sample(rows),
        unavailable_rows=tuple(unavailable),
    )


@st.cache_data(show_spinner="Reducing validity scientific evidence…", max_entries=16)
def _cached_validity_scientific_evidence(
    store_path: str,
    selected_store_sha256: str,
    generation_cohort_id: str,
    audit_path: str | None,
    audit_fingerprint: str | None,
) -> ValidityScientificEvidence:
    rows = [
        row
        for row in _cached_candidates(store_path, selected_store_sha256, None, None, None)
        if str(row.get("generation_cohort_id")) == generation_cohort_id
    ]
    characterization = candidate_validity_evidence(rows)
    artifact, blockers = _cached_audit_artifact(
        store_path,
        selected_store_sha256,
        audit_path,
        audit_fingerprint,
    )
    audit_state = _cached_audit_state(
        store_path,
        selected_store_sha256,
        audit_path,
        audit_fingerprint,
    )
    audited = None if artifact is None or blockers else validity_audit_evidence(artifact)
    tier: Literal["confirmatory", "characterization", "blocked"] = audit_state.evidence_tier
    if audited is None and tier == "blocked":
        tier = "characterization"
    return ValidityScientificEvidence(
        characterization=characterization,
        audit=audited,
        evidence_tier=tier,
        blockers=blockers,
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
    selected_store_sha256: str,
    audit_path: str | None,
    audit_fingerprint: str | None,
    evidence_status: Literal["pilot", "confirmatory"],
) -> bytes:
    del audit_fingerprint
    live_store_sha256 = str(_reader(store_path).root.attrs.get("manifest_sha256", ""))
    if live_store_sha256 != selected_store_sha256:
        raise ValueError(
            "Selected rollout-store identity changed before evidence export: "
            f"expected {selected_store_sha256}, observed {live_store_sha256}."
        )
    frames = build_thesis_report_frames(
        [Path(store_path)],
        evidence_status=evidence_status,
        scientific_audit=None if audit_path is None else Path(audit_path),
    )
    return serialize_thesis_report_bundle(frames)


@st.cache_data(show_spinner=False, max_entries=32)
def _cached_confirmatory_export_blockers(
    store_path: str,
    selected_store_sha256: str,
    audit_path: str | None,
    audit_fingerprint: str | None,
) -> tuple[str, ...]:
    del audit_fingerprint
    live_store_sha256 = str(_reader(store_path).root.attrs.get("manifest_sha256", ""))
    if live_store_sha256 != selected_store_sha256:
        return (f"selected_store_identity_changed:expected={selected_store_sha256}:observed={live_store_sha256}",)
    return scientific_report_blockers(
        Path(store_path),
        None if audit_path is None else Path(audit_path),
    )


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
    _cached_audit_artifact,
    _cached_audit_state,
    _cached_policy_effects,
    _cached_audited_endpoints,
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
    _cached_candidate_scientific_evidence,
    _cached_validity_scientific_evidence,
    _cached_selected_depth_summary,
    _cached_selected_depth_preview,
    _cached_failures,
    _cached_topology,
    _cached_rollout_ids,
    _cached_evidence_bundle,
    _cached_confirmatory_export_blockers,
)


def clear_stored_rollout_caches() -> None:
    """Invalidate every session-owned discovery, store, and projection cache."""

    for cached in _SESSION_CACHE_OWNERS:
        cached.clear()


__all__ = [
    "CandidateScientificEvidence",
    "ScientificAuditState",
    "StoredRolloutCapabilities",
    "StoredRolloutSession",
    "ValidityScientificEvidence",
    "clear_stored_rollout_caches",
    "open_stored_rollout_session",
    "rollout_store_inventory",
]
