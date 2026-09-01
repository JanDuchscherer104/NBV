"""Minimal rollout replay inputs shared by the Zarr writer.

`rollouts.zarr` stores facts derived from existing counterfactual rollout
results. This module owns frozen invalidity codecs and composed lineage facts;
generation-pipeline aggregates remain outside replay and storage. It does not
define a second serializable trace hierarchy.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

import numpy as np
import torch
from numpy.typing import NDArray

from ..pose_generation.admission import derive_invalid_reason_evidence
from .replay.policy import CounterfactualSelectionPolicy
from .replay.state import CounterfactualRolloutResult, CounterfactualTrajectory

if TYPE_CHECKING:
    from ..pose_generation import CandidateSet

CANDIDATE_TRACE_CODEC_VERSION = "candidate-trace-v1"
"""Version of the additive typed candidate persistence projection."""


@dataclass(frozen=True, slots=True)
class CandidateCriterionTrace:
    """One admission criterion projected to immutable CPU arrays.

    Every array is aligned to the full attempted candidate axis ``N``. Local
    arrays are absent together when the criterion owner did not evaluate them.
    """

    criterion_id: str
    """Stable nonempty criterion identity, unique within one trace."""
    legacy_cumulative_valid: NDArray[np.bool_]
    """Immutable cumulative validity ``ndarray[bool, N]`` on CPU."""
    local_availability: NDArray[np.bool_]
    """Immutable local-evidence availability ``ndarray[bool, N]`` on CPU."""
    applicable: NDArray[np.bool_] | None
    """Immutable applicability ``ndarray[bool, N]``; absent with local bundle."""
    evaluated: NDArray[np.bool_] | None
    """Immutable evaluation state ``ndarray[bool, N]``."""
    passed: NDArray[np.bool_] | None
    """Immutable pass state ``ndarray[bool, N]``."""
    reason_code: NDArray[np.int64] | None
    """Immutable closed reason codes ``ndarray[int64, N]``."""
    margin: NDArray[np.float32] | None
    """Immutable criterion-owned-unit margins ``ndarray[float32, N]``."""
    source_role: NDArray[np.int64] | None
    """Immutable audit source roles ``ndarray[int64, N]``; not actor input."""
    reason_revision: str
    """Closed semantic revision governing ``reason_code``."""
    source_role_revision: str
    """Closed semantic revision governing ``source_role``."""

    def __post_init__(self) -> None:
        n = self.legacy_cumulative_valid.shape[0]
        if type(self.criterion_id) is not str or not self.criterion_id or self.legacy_cumulative_valid.shape != (n,):
            raise ValueError("Candidate criterion identity and cumulative axis must be valid.")
        if self.legacy_cumulative_valid.dtype != np.bool_ or self.local_availability.dtype != np.bool_:
            raise ValueError("Candidate criterion validity and availability must be bool[N].")
        if self.local_availability.shape != (n,):
            raise ValueError("Candidate criterion availability must align over N.")
        local_values = (self.applicable, self.evaluated, self.passed, self.reason_code, self.margin, self.source_role)
        if any(value is None for value in local_values) != all(value is None for value in local_values):
            raise ValueError("Candidate criterion local arrays must be all present or all absent.")
        if self.applicable is None:
            if np.any(self.local_availability):
                raise ValueError("Unavailable criterion-local evidence cannot mark rows available.")
        else:
            for value in (self.applicable, self.evaluated, self.passed):
                if value is None or value.shape != (n,) or value.dtype != np.bool_:
                    raise ValueError("Criterion local booleans must be bool[N].")
            if self.reason_code is None or self.reason_code.shape != (n,) or self.reason_code.dtype != np.int64:
                raise ValueError("Criterion reason codes must be int64[N].")
            if self.margin is None or self.margin.shape != (n,) or self.margin.dtype != np.float32:
                raise ValueError("Criterion margins use the explicit float32 persistence codec.")
            if self.source_role is None or self.source_role.shape != (n,) or self.source_role.dtype != np.int64:
                raise ValueError("Criterion source roles must be int64[N].")
            if self.passed is None:
                raise ValueError("Criterion passed rows must be present with local evidence.")
            reason_code = self.reason_code
            source_role = self.source_role
            passed = self.passed
            available = self.local_availability
            applicable = self.applicable
            evaluated = self.evaluated
            margin = self.margin
            if applicable is None or evaluated is None or margin is None:  # pragma: no cover - guarded above.
                raise ValueError("Candidate criterion local evidence is incomplete.")
            if np.any(evaluated[available] & ~applicable[available]) or np.any(
                passed[available] & ~evaluated[available]
            ):
                raise ValueError("Candidate criterion applicability/evaluation subsets are invalid.")
            if np.any(~np.isfinite(margin[available])):
                raise ValueError("Available candidate criterion margins must be finite.")
            if np.any((reason_code[available] < -1) | (reason_code[available] > 7)) or np.any(
                ~np.isin(source_role[available], np.asarray([1, 2], dtype=np.int64))
            ):
                raise ValueError("Candidate criterion reason/source axes contain undeclared codes.")
            if np.any(passed[available] != (reason_code[available] == 0)):
                raise ValueError("Candidate criterion passed rows must use the PASSED reason code exactly.")
            if np.any((~evaluated[available]) != (reason_code[available] == -1)):
                raise ValueError("Candidate criterion unevaluated rows must use the UNAVAILABLE reason exactly.")
        allowed_revisions = {"unavailable_v1", "candidate_admission_v1"}
        if (
            type(self.reason_revision) is not str
            or self.reason_revision not in allowed_revisions
            or type(self.source_role_revision) is not str
            or self.source_role_revision not in allowed_revisions
        ):
            raise ValueError("Candidate criterion revisions are unsupported.")
        for value in (self.legacy_cumulative_valid, self.local_availability, *local_values):
            if isinstance(value, np.ndarray) and value.flags.writeable:
                raise ValueError("Candidate criterion arrays must be immutable.")


@dataclass(frozen=True, slots=True)
class CandidateTraceFacts:
    """Versioned persistence projection of one canonical attempted shell.

    Attributes:
        semantic_group_id: ``N`` stable center-group identities.
        center_family_id: ``N`` positional-family identities.
        gaze_family_id: ``N`` gaze-family identities.
        candidate_family_id: ``N`` combined semantic family identities.
        center_id: ``ndarray["N", int64]`` shared-center lineage.
        position_pair_id: ``ndarray["N", int64]`` paired-position lineage.
        gaze_variant_id: ``ndarray["N", int64]`` ordered gaze variants.
        attempt_round_id: ``ndarray["N", int64]`` completion rounds.
        draw_id: ``ndarray["N", int64]`` within-center draws.
        proposal_key: ``N`` semantic sampling paths.
        target_frame_identity: ``N`` generation-frame identities.
        target_frame_availability: ``N`` typed availability values.
        criteria: Ordered admission facts, each aligned to ``N``.
        valid_indices: Immutable ``int64[V]`` projection into the attempted shell.
        action_indices: Immutable ``int64[A]`` ordered actor projection, a subset of ``V``.
        candidate_program_hash: Lowercase SHA-256 of the frozen candidate program.
        request_binding_hash: Lowercase SHA-256 of the bound generation request.
        candidate_substream_revision: Closed candidate randomness revision.
        action_order_revision: Closed ordered-action projection revision.
        completion_mode: Closed candidate completion policy.
        attempted_count: Attempted-shell cardinality ``N``.
        valid_count: Hard-valid cardinality ``V``.
        action_count: Actor-action cardinality ``A``.
        proposal_key_revision: Composition-owned proposal-key revision, if available.
        proposal_replica: Non-negative proposal replica paired with its revision.
        legacy_candidate_config_hash: Independently supplied legacy config hash.

    The DTO owns immutable CPU arrays at the rollout persistence boundary. It
    is audit-only: criterion margins retain their criterion-defined units and
    are never projected into actor/training tensors.
    """

    codec_version: str
    """Closed additive rollout candidate-trace layout revision."""
    semantic_group_id: tuple[str, ...]
    """Stable semantic center-group identities ``str[N]``."""
    center_family_id: tuple[str, ...]
    """Stable center-family identities ``str[N]``."""
    gaze_family_id: tuple[str, ...]
    """Stable gaze-family identities ``str[N]``."""
    candidate_family_id: tuple[str, ...]
    """Stable combined candidate-family identities ``str[N]``."""
    center_id: NDArray[np.int64]
    """Immutable shared-center lineage ``ndarray[int64, N]`` on CPU."""
    position_pair_id: NDArray[np.int64]
    """Immutable pair lineage ``ndarray[int64, N]``; ``-1`` inapplicable."""
    gaze_variant_id: NDArray[np.int64]
    """Immutable gaze lineage ``ndarray[int64, N]``; paired ``-1`` sentinel."""
    attempt_round_id: NDArray[np.int64]
    """Immutable completion-round lineage ``ndarray[int64, N]``."""
    draw_id: NDArray[np.int64]
    """Immutable within-round draw lineage ``ndarray[int64, N]``."""
    proposal_key: tuple[str, ...]
    """Semantic random-draw identities ``str[N]``."""
    target_frame_identity: tuple[str, ...]
    """Generation-frame identities ``str[N]``; empty when unavailable."""
    target_frame_availability: tuple[str, ...]
    """Closed target-frame availability values ``str[N]``."""
    criteria: tuple[CandidateCriterionTrace, ...]
    """Ordered immutable admission audit criteria, each aligned to ``N``."""
    valid_indices: NDArray[np.int64]
    """Immutable ordered shell projection ``ndarray[int64, V]`` on CPU."""
    action_indices: NDArray[np.int64]
    """Immutable ordered shell projection ``ndarray[int64, A]``, subset of V."""
    candidate_program_hash: str
    """Lowercase SHA-256 binding the frozen candidate program."""
    request_binding_hash: str
    """Lowercase SHA-256 binding the generation request and scene."""
    candidate_substream_revision: str
    """Closed sampling-substream revision."""
    action_order_revision: str
    """Closed actor-action ordering revision."""
    completion_mode: str
    """Closed candidate completion-policy identity."""
    attempted_count: int
    """Attempted-shell cardinality ``N``."""
    valid_count: int
    """Hard-valid cardinality ``V``."""
    action_count: int
    """Actor-action cardinality ``A``, with ``A <= V <= N``."""
    proposal_key_revision: str | None
    """Composition-owned proposal revision, jointly optional with replica."""
    proposal_replica: int | None
    """Non-negative proposal replica, jointly optional with revision."""
    legacy_candidate_config_hash: str | None
    """Independent legacy candidate-config identity for dual-write audit."""

    def __post_init__(self) -> None:
        if self.codec_version != CANDIDATE_TRACE_CODEC_VERSION:
            raise ValueError(f"Unsupported candidate trace codec {self.codec_version!r}.")
        n = self.attempted_count
        string_axes = (
            self.semantic_group_id,
            self.center_family_id,
            self.gaze_family_id,
            self.candidate_family_id,
            self.proposal_key,
            self.target_frame_identity,
            self.target_frame_availability,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) for value in (n, self.valid_count, self.action_count)
        ):
            raise ValueError("Candidate trace counts must be exact integers.")
        if n < 0 or self.valid_count < 0 or self.action_count < 0 or self.valid_count > n:
            raise ValueError("Candidate trace counts must satisfy 0 <= V <= N.")
        if any(len(values) != n for values in string_axes):
            raise ValueError("Candidate trace string axes must align over N.")
        if any(type(value) is not str or not value for values in string_axes[:5] for value in values):
            raise ValueError("Candidate semantic and proposal identities must be nonempty.")
        if any(type(value) is not str for value in self.target_frame_identity):
            raise ValueError("Candidate target-frame identities must contain strings.")
        for values in (
            self.center_id,
            self.position_pair_id,
            self.gaze_variant_id,
            self.attempt_round_id,
            self.draw_id,
        ):
            if values.shape != (n,) or values.dtype != np.int64:
                raise ValueError("Candidate trace lineage arrays must be int64[N].")
        if any(
            type(value) is not str or not value
            for value in (self.candidate_program_hash, self.request_binding_hash, self.completion_mode)
        ):
            raise ValueError("Candidate trace hashes and completion mode must be nonempty.")
        if self.candidate_substream_revision != "shipped_mixture_seed_paths_v1":
            raise ValueError("Candidate trace substream revision is unsupported.")
        if self.action_order_revision != "ordered_hard_valid_v1" or self.completion_mode != "fixed_attempts":
            raise ValueError("Candidate trace action/completion revisions are unsupported.")
        if any(criterion.legacy_cumulative_valid.shape != (n,) for criterion in self.criteria):
            raise ValueError("Candidate criterion traces must align over N.")
        if len({criterion.criterion_id for criterion in self.criteria}) != len(self.criteria):
            raise ValueError("Candidate criterion identities must be unique.")
        for name, indices, count in (
            ("valid", self.valid_indices, self.valid_count),
            ("action", self.action_indices, self.action_count),
        ):
            if indices.ndim != 1 or indices.dtype != np.int64 or indices.shape[0] != count:
                raise ValueError(f"Candidate {name} indices must be int64 and match their count.")
            if indices.flags.writeable:
                raise ValueError(f"Candidate {name} indices must be immutable.")
            if np.any(indices < 0) or np.any(indices >= n) or np.unique(indices).shape[0] != indices.shape[0]:
                raise ValueError(f"Candidate {name} indices must be unique references into N.")
        if not set(self.action_indices.tolist()).issubset(self.valid_indices.tolist()):
            raise ValueError("Candidate action indices must be a subset of valid indices.")
        if np.any(self.center_id < 0) or np.any(self.attempt_round_id < 0) or np.any(self.draw_id < 0):
            raise ValueError("Candidate center, round, and draw identities must be non-negative.")
        pair_inapplicable = (self.position_pair_id == -1) & (self.gaze_variant_id == -1)
        pair_available = (self.position_pair_id >= 0) & (self.gaze_variant_id >= 0)
        if not np.all(pair_inapplicable | pair_available):
            raise ValueError("Candidate pair/gaze identities must be jointly non-negative or exactly -1.")
        if self.criteria:
            previous: NDArray[np.bool_] = np.ones(n, dtype=np.bool_)
            for criterion in self.criteria:
                current = criterion.legacy_cumulative_valid
                if np.any(current & ~previous):
                    raise ValueError("Candidate cumulative admission masks must be monotone.")
                if criterion.evaluated is not None and criterion.passed is not None:
                    available = criterion.local_availability
                    expected = previous & (~criterion.evaluated | criterion.passed)
                    if np.any(current[available] != expected[available]):
                        raise ValueError("Candidate cumulative admission mask contradicts local criterion evidence.")
                previous = current
            expected_valid: NDArray[np.bool_] = np.zeros(n, dtype=np.bool_)
            expected_valid[self.valid_indices] = True
            if not np.array_equal(previous, expected_valid):
                raise ValueError("Candidate terminal cumulative admission mask must equal V.")
        for values in (
            self.center_id,
            self.position_pair_id,
            self.gaze_variant_id,
            self.attempt_round_id,
            self.draw_id,
        ):
            if values.flags.writeable:
                raise ValueError("Candidate trace arrays must be immutable.")
        if any(
            type(value) is not str or value not in {"available", "unavailable"}
            for value in self.target_frame_availability
        ):
            raise ValueError("Candidate target-frame availability is undeclared.")
        if any(
            (availability == "available") != bool(identity)
            for identity, availability in zip(self.target_frame_identity, self.target_frame_availability, strict=True)
        ):
            raise ValueError("Candidate target-frame identity must agree with row availability.")
        if (self.proposal_key_revision is None) != (self.proposal_replica is None):
            raise ValueError("Proposal-key revision and replica must be present together.")
        if self.proposal_key_revision is not None and (
            type(self.proposal_key_revision) is not str or not self.proposal_key_revision
        ):
            raise ValueError("Proposal-key revision must be nonempty when available.")
        if self.proposal_replica is not None and (
            isinstance(self.proposal_replica, bool)
            or not isinstance(self.proposal_replica, int)
            or self.proposal_replica < 0
        ):
            raise ValueError("Proposal replica must be non-negative.")
        for digest in (self.candidate_program_hash, self.request_binding_hash):
            if type(digest) is not str or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError("Candidate trace hashes must be lowercase SHA-256 digests.")
        if self.legacy_candidate_config_hash is not None and (
            type(self.legacy_candidate_config_hash) is not str or not self.legacy_candidate_config_hash
        ):
            raise ValueError("Legacy candidate config hash must be nonempty when available.")


def candidate_trace_facts(
    candidate_set: CandidateSet,
    *,
    proposal_key_revision: str | None = None,
    proposal_replica: int | None = None,
    legacy_candidate_config_hash: str | None = None,
) -> CandidateTraceFacts:
    """Project a canonical candidate set into rollout-owned persistence facts.

    This is the sole rollout codec boundary from the frozen candidate model.
    It performs one explicit device-to-host materialization and does not retain
    candidate tensors or mutate the source set.
    """

    table = candidate_set.attempts
    candidate_set.validate_semantics()

    def cpu_array(value: torch.Tensor, *, dtype: torch.dtype) -> NDArray[Any]:
        result = value.detach().to(device="cpu", dtype=dtype).numpy().copy()
        result.setflags(write=False)
        return result

    criteria = []
    for criterion in candidate_set.admission.criteria:
        local = criterion.local
        criteria.append(
            CandidateCriterionTrace(
                criterion_id=criterion.criterion_id,
                legacy_cumulative_valid=cpu_array(criterion.legacy_cumulative_valid, dtype=torch.bool),
                local_availability=cpu_array(criterion.local_availability, dtype=torch.bool),
                applicable=None if local is None else cpu_array(local.applicable, dtype=torch.bool),
                evaluated=None if local is None else cpu_array(local.evaluated, dtype=torch.bool),
                passed=None if local is None else cpu_array(local.passed, dtype=torch.bool),
                reason_code=None if local is None else cpu_array(local.reason_code, dtype=torch.int64),
                margin=None if local is None else cpu_array(local.margin, dtype=torch.float32),
                source_role=None if local is None else cpu_array(local.source_role, dtype=torch.int64),
                reason_revision=criterion.reason_revision.value,
                source_role_revision=criterion.source_role_revision.value,
            )
        )
    return CandidateTraceFacts(
        codec_version=CANDIDATE_TRACE_CODEC_VERSION,
        semantic_group_id=table.semantic_group_id,
        center_family_id=table.center_family_id,
        gaze_family_id=table.gaze_family_id,
        candidate_family_id=table.candidate_family_id,
        center_id=cpu_array(table.center_id, dtype=torch.int64),
        position_pair_id=cpu_array(table.position_pair_id, dtype=torch.int64),
        gaze_variant_id=cpu_array(table.gaze_variant_id, dtype=torch.int64),
        attempt_round_id=cpu_array(table.attempt_round_id, dtype=torch.int64),
        draw_id=cpu_array(table.draw_id, dtype=torch.int64),
        proposal_key=table.proposal_key,
        target_frame_identity=table.target_frame_identity,
        target_frame_availability=tuple(value.value for value in table.target_frame_availability),
        criteria=tuple(criteria),
        valid_indices=cpu_array(candidate_set.valid_indices, dtype=torch.int64),
        action_indices=cpu_array(candidate_set.action_indices, dtype=torch.int64),
        candidate_program_hash=candidate_set.candidate_program_hash,
        request_binding_hash=candidate_set.request_binding_hash,
        candidate_substream_revision=candidate_set.candidate_substream_revision.value,
        action_order_revision=candidate_set.action_order_revision.value,
        completion_mode=candidate_set.completion.mode.value,
        attempted_count=candidate_set.completion.attempted_count,
        valid_count=candidate_set.completion.valid_count,
        action_count=int(candidate_set.action_indices.shape[0]),
        proposal_key_revision=proposal_key_revision,
        proposal_replica=proposal_replica,
        legacy_candidate_config_hash=legacy_candidate_config_hash,
    )


INVALID_REASON_CODES: dict[str, int] = {
    "VALID": 0,
    "POSE_NONFINITE": 1,
    "POSE_OUT_OF_EXTENT": 2,
    "CAMERA_OUT_OF_EXTENT": 3,
    "COLLISION_MESH": 4,
    "CLEARANCE_TOO_SMALL": 5,
    "PATH_SEGMENT_COLLISION": 6,
    "FRUSTUM_OUT_OF_BOUNDS": 7,
    "DEPTH_NO_HIT": 8,
    "DEPTH_TOO_SPARSE": 9,
    "BACKPROJECT_EMPTY": 10,
    "CANDIDATE_DUPLICATE": 11,
    "SAMPLER_RULE_REJECTED": 12,
    "TARGET_NOT_ACTOR_VISIBLE": 13,
    "TARGET_GT_UNMATCHED": 14,
    "TARGET_CROP_EMPTY": 15,
    "TARGET_SUPPORT_TOO_LOW": 16,
    "TARGET_VISIBILITY_TOO_LOW": 17,
    "SEMIDENSE_SUPPORT_TOO_LOW": 18,
    "EVL_EVIDENCE_MISSING": 19,
    "MESH_REFERENCE_MISSING": 20,
    "ORACLE_DISTANCE_FAILED": 21,
    "CANDIDATE_ORDER_GUARD_FAILED": 22,
    "RUNTIME_ERROR": 23,
}
"""Version-1 invalidity reason bit positions for rollout replay tables."""

INVALID_REASON_VERSION = "rollout-invalidity-v1"
"""Version label for `INVALID_REASON_CODES`."""

_RULE_REASON_BITS = {
    "FreeSpaceRule": INVALID_REASON_CODES["POSE_OUT_OF_EXTENT"],
    "MinDistanceToMeshRule": INVALID_REASON_CODES["CLEARANCE_TOO_SMALL"],
    "PathCollisionRule": INVALID_REASON_CODES["PATH_SEGMENT_COLLISION"],
}

_HARD_DIAGNOSTIC_REASON_BITS = {
    "path_collision_mask": INVALID_REASON_CODES["PATH_SEGMENT_COLLISION"],
}

_PRIMARY_INVALID_REASON_PRIORITY = (
    "POSE_NONFINITE",
    "PATH_SEGMENT_COLLISION",
    "CLEARANCE_TOO_SMALL",
    "POSE_OUT_OF_EXTENT",
    "CAMERA_OUT_OF_EXTENT",
    "FRUSTUM_OUT_OF_BOUNDS",
    "DEPTH_NO_HIT",
    "DEPTH_TOO_SPARSE",
    "BACKPROJECT_EMPTY",
    "TARGET_SUPPORT_TOO_LOW",
    "TARGET_VISIBILITY_TOO_LOW",
    "SAMPLER_RULE_REJECTED",
)


@dataclass(slots=True)
class SourceLineage:
    """Immutable VIN source identity for one generated rollout root."""

    scene_id: str | None = None
    """Source scene identifier copied from the immutable VIN index."""

    snippet_id: str | None = None
    """Source snippet identifier copied from the immutable VIN index."""

    mesh_version: str | None = None
    """Fingerprint/version of the oracle mesh used for rendering and labels."""

    source_cache_version: str | None = None
    """Schema/version label of the immutable VIN offline source cache."""

    split: str | None = None
    """VIN source split associated with this rollout root."""

    campaign_split: str | None = None
    """Authoritative campaign split; never overwrites VIN ``split``."""

    source_offline_store_manifest_hash: str | None = None
    """Hash of the complete VIN source-store manifest."""

    source_row_id: int | None = None
    """Dense source-table row id assigned by the rollout store writer."""

    source_sample_index: int | None = None
    """Stable VIN dataset sample index used to reopen the source row."""

    source_sample_key: str | None = None
    """Canonical VIN sample key used to detect source-index drift."""

    split_manifest_hash: str | None = None
    """Hash binding the split name and ordered source-row ownership records."""

    source_shard_id: str | None = None
    """Identifier of the immutable VIN storage shard containing the source."""

    source_shard_row: int | None = None
    """Zero-based row within ``source_shard_id``."""


@dataclass(slots=True)
class TargetLineage:
    """Actor descriptor and privileged Oracle target lineage."""

    target_row_id: int | None = None
    """Dense target-table row id assigned by the rollout store writer."""

    target_id: str | None = None
    """Stable target-task identifier from selection or oracle task sampling."""

    target_protocol_version: str | None = None
    """Versioned contract governing target evidence and label boundaries."""

    target_crop_policy: str | None = None
    """Versioned oracle geometry-crop policy used for target RRI labels."""

    target_selection_policy: str | None = None
    """Policy that admitted this target task before rollout generation."""

    target_selection_rank: int | None = None
    """Zero-based target rank within the source sample's selected set."""

    target_selection_score: float | None = None
    """Target-interest score under the recorded selection protocol."""

    target_selection_probability: float | None = None
    """Sampling probability assigned to the selected target task."""

    target_selection_temperature: float | None = None
    """Temperature used by stochastic target selection, when applicable."""

    target_source: str | None = None
    """Target source protocol, distinguishing observed and oracle task inputs."""

    target_source_index: int | None = None
    """Row index in the source OBB/task table before target filtering."""

    descriptor_source: str | None = None
    """Source block that constructed the actor-facing descriptor."""

    descriptor_provenance: str | None = None
    """Typed construction provenance for the actor-facing descriptor."""

    descriptor_hash: str | None = None
    """Canonical hash of the actor-facing descriptor identity."""

    explicit_target_hash: str | None = None
    """Canonical hash binding an explicit observed target to its GT proof."""

    target_sem_id: int | None = None
    """Semantic class id carried by the chosen target task."""

    target_inst_id: int | None = None
    """Instance id carried by the chosen target task."""

    target_class_name: str | None = None
    """Human-readable semantic class label for audit and inspection."""

    target_confidence: float | None = None
    """Source OBB confidence; actor-visible only for observed-target protocols."""

    target_projected_area_pixels: float | None = None
    """Largest clipped target projection area, in square pixels."""

    target_projected_area_fraction: float | None = None
    """Projected area divided by the target selector's image normalizer."""

    target_semidense_support_count: int | None = None
    """Semidense world points inside the selected target volume."""

    target_evl_support_count: int | None = None
    """Positive EVL evidence points inside the selected target volume."""

    target_effective_support_count: float | None = None
    """Weighted support count used by the target-selection protocol."""

    target_visibility_score: float | None = None
    """Projected-visibility factor used when selecting observed targets."""

    target_support_score: float | None = None
    """Support-sufficiency factor used by target ranking."""

    target_deficit_score: float | None = None
    """Unsaturated-support factor favoring targets with improvement headroom."""

    target_center_world: tuple[float, float, float] | None = None
    """Target OBB center ``(x, y, z)`` in world metres."""

    target_extents: tuple[float, float, float] | None = None
    """Full target OBB side lengths in object axes, in metres."""

    target_pose_world_object: tuple[float, ...] | None = None
    """Flattened 12-value physical transform from target object to world."""

    target_relative_pose_reference_object: tuple[float, ...] | None = None
    """Flattened 12-value transform from target object to snippet reference."""

    target_invalid_reason_bitset: int | None = None
    """Versioned bitset of target-level invalidity facts; never encoded as score."""

    target_primary_invalid_reason: int | None = None
    """Prioritized target invalidity code for compact inspection."""

    target_reason_code_version: str | None = None
    """Version of target-selection invalidity bit positions."""

    matched_gt_target_row_id: int | None = None
    """Oracle-only GT target row matched after target selection."""

    matched_gt_target_id: str | None = None
    """Oracle-only stable identifier of the matched GT target."""

    gt_match_iou: float | None = None
    """Oracle-only oriented-box IoU used for target-label auditing."""

    gt_match_score: float | None = None
    """Oracle-only composite score used to choose the GT match."""

    gt_match_status: str | None = None
    """Oracle-only match outcome controlling target-label admissibility."""


@dataclass(slots=True)
class PolicyLineage:
    """Candidate, Oracle, and replay-policy configuration lineage."""

    candidate_config_hash: str | None = None
    """Stable hash of candidate-shell generation and hard-validity controls."""

    oracle_config_hash: str | None = None
    """Stable hash of Oracle rendering, crop, fusion, and RRI controls."""

    model_checkpoint_hash: str | None = None
    """Optional learned-policy checkpoint hash; absent for built-in policies."""

    random_seed: int | None = None
    """Recipe/root seed from which deterministic node seeds were derived."""

    rollout_policy: str = "unknown"
    """Action-selection policy used for this retained rollout chain."""

    rollout_config_hash: str | None = None
    """Stable hash of horizon, branching, policy, and diversity controls."""

    branch_schedule_id: str | None = None
    """Human-stable recipe or schedule identifier for branch provenance."""

    reason_code_version: str = INVALID_REASON_VERSION
    """Version of rollout candidate invalidity bit positions."""

    selection_rng_state_hash: str | None = None
    """Hash of target-selection RNG state for deterministic replay audits."""


@dataclass(slots=True)
class RolloutLineage:
    """Composed source, target, and policy lineage flattened only by the writer."""

    source: SourceLineage = field(default_factory=SourceLineage)
    """Immutable VIN source identity for the rollout root."""

    target: TargetLineage = field(default_factory=TargetLineage)
    """Actor descriptor and privileged Oracle target lineage."""

    policy: PolicyLineage = field(default_factory=PolicyLineage)
    """Candidate, Oracle, and replay-policy configuration lineage."""

    rollout_id: str = ""
    """Stable identifier assigned to one retained rollout chain."""

    chain_id: int = 0
    """Zero-based retained trajectory index within the rollout root."""

    def for_chain(self, chain_id: int, *, rollout_id: str, rollout_policy: str) -> "RolloutLineage":
        """Return persisted lineage identifiers for one retained chain."""

        return replace(
            self,
            rollout_id=rollout_id,
            chain_id=int(chain_id),
            policy=replace(self.policy, rollout_policy=rollout_policy),
        )


def _full_candidate_vector(
    values: torch.Tensor,
    candidate_valid: torch.Tensor,
    *,
    fill_value: float | int | None = None,
    require_full_shell: bool = False,
) -> torch.Tensor:
    valid_values = values.detach().cpu().reshape(-1)
    valid_mask = candidate_valid.detach().cpu().to(dtype=torch.bool).reshape(-1)
    if require_full_shell:
        if valid_values.numel() != valid_mask.numel():
            raise ValueError(f"Expected {valid_mask.numel()} full-shell values, got {valid_values.numel()}.")
        return valid_values
    valid_count = int(valid_mask.sum().item())
    if valid_values.numel() != valid_count:
        raise ValueError(f"Expected {valid_count} valid values, got {valid_values.numel()}.")
    if fill_value is None:
        fill_value = float("nan") if torch.is_floating_point(valid_values) else 0
    full = torch.full(valid_mask.shape, fill_value, dtype=valid_values.dtype, device=valid_values.device)
    full[valid_mask] = valid_values
    return full


def _full_shell_or_default(
    values: torch.Tensor | None,
    candidate_valid: torch.Tensor,
    *,
    fill_value: float | int,
) -> torch.Tensor:
    valid_mask = candidate_valid.detach().cpu().to(dtype=torch.bool).reshape(-1)
    if values is None:
        dtype = torch.float32 if isinstance(fill_value, float) else torch.int64
        return torch.full(valid_mask.shape, fill_value, dtype=dtype)
    return _full_candidate_vector(values, candidate_valid, fill_value=fill_value, require_full_shell=True)


def _candidate_invalid_reasons(candidates: Any) -> tuple[torch.Tensor, torch.Tensor]:
    valid_mask = candidates.mask_valid.detach().cpu().to(dtype=torch.bool).reshape(-1)
    masks = {name: values.detach().cpu().to(dtype=torch.bool).reshape(-1) for name, values in candidates.masks.items()}
    diagnostics = {
        name: _full_shell_bool_extra(candidates.extras, name, valid_mask) for name in _HARD_DIAGNOSTIC_REASON_BITS
    }
    shell = candidates.shell_poses.tensor().detach().cpu()
    nonfinite = ~torch.isfinite(shell.reshape(shell.shape[0], -1)).all(dim=1)
    return derive_invalid_reason_evidence(
        valid_mask=valid_mask,
        cumulative_masks=masks,
        diagnostic_rejections=diagnostics,
        pose_nonfinite=nonfinite,
        reason_codes=INVALID_REASON_CODES,
        rule_reason_codes=_RULE_REASON_BITS,
        diagnostic_reason_codes=_HARD_DIAGNOSTIC_REASON_BITS,
        primary_reason_priority=_PRIMARY_INVALID_REASON_PRIORITY,
    )


def _full_shell_bool_extra(extras: dict[str, Any], name: str, valid_mask: torch.Tensor) -> torch.Tensor:
    value = extras.get(name)
    if value is None:
        return torch.zeros_like(valid_mask)
    tensor = torch.as_tensor(value).detach().cpu().to(dtype=torch.bool).reshape(-1)
    if tensor.numel() == valid_mask.numel():
        return tensor
    if tensor.numel() != int(valid_mask.sum().item()):
        return torch.zeros_like(valid_mask)
    full = torch.zeros_like(valid_mask)
    full[valid_mask] = tensor
    return full


def termination_reason(result: CounterfactualRolloutResult, trajectory: CounterfactualTrajectory) -> str:
    """Classify why a replay chain stopped without inventing a partial label.

    Early termination takes precedence over horizon completion.  A trajectory
    shorter than ``result.horizon`` without the explicit early-stop marker is
    reported as ``incomplete_rollout`` so persisted stores can distinguish a
    valid terminal transition from missing generation output.
    """

    if trajectory.terminated_early:
        return "terminated_early"
    if len(trajectory.steps) >= int(result.horizon):
        return "fixed_horizon"
    return "incomplete_rollout"


def policy_name(policy: str | CounterfactualSelectionPolicy) -> str:
    """Return the stable persisted policy label for enum or string inputs."""

    return policy.value if isinstance(policy, CounterfactualSelectionPolicy) else str(policy)


# Preserve the original private imports used by persisted-store code.
_termination_reason = termination_reason
_policy_name = policy_name


__all__ = [
    "CANDIDATE_TRACE_CODEC_VERSION",
    "CandidateCriterionTrace",
    "CandidateTraceFacts",
    "INVALID_REASON_CODES",
    "INVALID_REASON_VERSION",
    "PolicyLineage",
    "RolloutLineage",
    "SourceLineage",
    "TargetLineage",
    "candidate_trace_facts",
    "termination_reason",
    "policy_name",
]
