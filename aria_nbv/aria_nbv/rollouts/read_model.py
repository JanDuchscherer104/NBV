"""Typed, presentation-free projections over persisted rollout stores.

This module is the shared read-side owner for persisted rollout, step, target,
and selected-depth meaning.  Consumers such as the Rerun inspector may choose
their own entities, colours, transforms, and plots, but obtain the ordered
full-shell rows, action masks, selected transitions, and decoded dictionaries
from these projections.  It performs no store mutation or display policy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from ..pose_generation import CandidatePositionMode, candidate_position_id
from .trace import INVALID_REASON_CODES
from .zarr_store import RolloutZarrStoreReader, _CandidateCodecTables

_INVALID_REASON_NAMES = {int(code): name for name, code in INVALID_REASON_CODES.items()}
_POSITION_NAMES = {candidate_position_id(mode): mode.value for mode in CandidatePositionMode}


@dataclass(frozen=True, slots=True)
class StoredRollout:
    """One persisted rollout row with decoded context and ordered step links."""

    row_position: int
    rollout_row_id: int
    chain_id: int
    source_row_id: int
    target_row_id: int
    scene: str
    snippet: str
    split: str
    policy: str
    horizon: int
    branch_factor: int
    beam_width: int
    temperature: float
    root_pose_world: NDArray[np.float32]
    final_cumulative_target_rri: float
    final_cumulative_scene_rri: float
    step_row_positions: NDArray[np.int64]


@dataclass(frozen=True, slots=True)
class StoredCandidateCriterion:
    """One immutable decoded criterion aligned to an attempted shell.

    Attributes:
        criterion_id: Stable criterion identity, unique within the step.
        legacy_cumulative_valid: Cumulative legacy validity mask ``bool[N]``.
        local_available: Availability of criterion-local facts ``bool[N]``.
        applicable: Criterion applicability ``bool[N]``; false when unavailable.
        evaluated: Evaluation state ``bool[N]``, a subset of applicability.
        passed: Pass state ``bool[N]``, a subset of evaluation.
        reason_code: Closed reason codes ``int64[N]``; ``-1`` when unavailable.
        margin: Criterion-owned-unit margins ``float32[N]``; NaN when unavailable.
        source_role: Closed audit source roles ``int64[N]``; ``-1`` when unavailable.
        reason_revision: Closed reason-code semantic revision.
        source_role_revision: Closed source-role semantic revision.
    """

    criterion_id: str
    """Stable nonempty criterion identity, unique within one stored step."""
    legacy_cumulative_valid: NDArray[np.bool_]
    """Immutable cumulative validity ``ndarray[bool, N]``."""
    local_available: NDArray[np.bool_]
    """Immutable criterion-local availability ``ndarray[bool, N]``."""
    applicable: NDArray[np.bool_]
    """Immutable applicability ``ndarray[bool, N]``; false when unavailable."""
    evaluated: NDArray[np.bool_]
    """Immutable evaluation state ``ndarray[bool, N]``."""
    passed: NDArray[np.bool_]
    """Immutable pass state ``ndarray[bool, N]``."""
    reason_code: NDArray[np.int64]
    """Immutable closed reason codes ``ndarray[int64, N]``."""
    margin: NDArray[np.float32]
    """Immutable criterion-owned-unit margins ``ndarray[float32, N]``."""
    source_role: NDArray[np.int64]
    """Immutable audit source roles ``ndarray[int64, N]``; not actor input."""
    reason_revision: str
    """Closed semantic revision governing ``reason_code``."""
    source_role_revision: str
    """Closed semantic revision governing ``source_role``."""

    def __post_init__(self) -> None:
        n = self.legacy_cumulative_valid.shape[0]
        arrays = (
            self.legacy_cumulative_valid,
            self.local_available,
            self.applicable,
            self.evaluated,
            self.passed,
            self.reason_code,
            self.margin,
            self.source_role,
        )
        if not self.criterion_id or any(array.shape != (n,) for array in arrays):
            raise ValueError("Stored candidate criterion arrays must align over N.")
        if any(
            array.dtype != np.bool_
            for array in (
                self.legacy_cumulative_valid,
                self.local_available,
                self.applicable,
                self.evaluated,
                self.passed,
            )
        ):
            raise ValueError("Stored criterion state axes must be bool[N].")
        if self.reason_code.dtype != np.int64 or self.source_role.dtype != np.int64 or self.margin.dtype != np.float32:
            raise ValueError("Stored criterion reason/source/margin dtypes must match the codec.")
        if np.any((self.reason_code < -1) | (self.reason_code > 7)) or np.any(
            ~np.isin(self.source_role, np.asarray([-1, 1, 2], dtype=np.int64))
        ):
            raise ValueError("Stored criterion reason/source axes contain undeclared codes.")
        if any(array.flags.writeable for array in arrays):
            raise ValueError("Stored candidate criterion arrays must be immutable.")
        if np.any(self.evaluated & ~self.applicable) or np.any(self.passed != (self.evaluated & self.passed)):
            raise ValueError("Stored candidate criterion applicability/evaluation subsets are invalid.")
        unavailable = ~self.local_available
        if np.any(self.applicable[unavailable] | self.evaluated[unavailable] | self.passed[unavailable]):
            raise ValueError("Unavailable stored criterion rows must use false local-state sentinels.")
        if np.any(self.reason_code[unavailable] != -1) or np.any(self.source_role[unavailable] != -1):
            raise ValueError("Unavailable stored criterion rows must use integer sentinels.")
        if np.any(np.isfinite(self.margin[unavailable])) or np.any(~np.isfinite(self.margin[self.local_available])):
            raise ValueError("Stored criterion margin availability must be explicit and finite.")
        if np.any(self.passed[self.local_available] != (self.reason_code[self.local_available] == 0)):
            raise ValueError("Stored criterion passed rows must use the PASSED reason code exactly.")
        if np.any((~self.evaluated[self.local_available]) != (self.reason_code[self.local_available] == -1)):
            raise ValueError("Stored criterion unevaluated rows must use the UNAVAILABLE reason exactly.")
        if self.reason_revision not in {
            "unavailable_v1",
            "candidate_admission_v1",
        } or self.source_role_revision not in {
            "unavailable_v1",
            "candidate_admission_v1",
        }:
            raise ValueError("Stored candidate criterion revisions are undeclared.")


@dataclass(frozen=True, slots=True)
class StoredCandidateCodecFacts:
    """One fully decoded current candidate-codec projection for a stored step.

    All row axes are immutable NumPy arrays aligned to the step's attempted
    shell ``N``. ``valid_indices`` and ``action_indices`` retain the ordered
    ``V`` and ``A`` projections independently of legacy masks. Pair/gaze ``-1``
    values mean jointly inapplicable; proposal revision/replica are jointly
    absent or available. Hashes and closed revisions bind the stored rows to
    their program, request, randomness, completion, and action-order owners.
    Criterion facts remain audit-only and preserve criterion-defined units.
    """

    semantic_group_ids: NDArray[np.str_]
    """Immutable semantic center-group identities ``ndarray[str, N]``."""
    center_family_ids: NDArray[np.str_]
    """Immutable center-family identities ``ndarray[str, N]``."""
    gaze_family_ids: NDArray[np.str_]
    """Immutable gaze-family identities ``ndarray[str, N]``."""
    candidate_family_ids: NDArray[np.str_]
    """Immutable combined candidate-family identities ``ndarray[str, N]``."""
    center_ids: NDArray[np.int64]
    """Immutable shared-center lineage ``ndarray[int64, N]``."""
    position_pair_ids: NDArray[np.int64]
    """Immutable pair lineage ``ndarray[int64, N]``; ``-1`` inapplicable."""
    gaze_variant_ids: NDArray[np.int64]
    """Immutable gaze lineage ``ndarray[int64, N]``; paired ``-1`` sentinel."""
    attempt_round_ids: NDArray[np.int64]
    """Immutable completion-round lineage ``ndarray[int64, N]``."""
    draw_ids: NDArray[np.int64]
    """Immutable within-round draw lineage ``ndarray[int64, N]``."""
    proposal_keys: NDArray[np.str_]
    """Immutable semantic random-draw identities ``ndarray[str, N]``."""
    target_frame_identities: NDArray[np.str_]
    """Immutable generation-frame identities ``ndarray[str, N]``."""
    target_frame_availability: NDArray[np.str_]
    """Immutable closed frame-availability values ``ndarray[str, N]``."""
    criteria: tuple[StoredCandidateCriterion, ...]
    """Ordered immutable admission audit criteria, each aligned to ``N``."""
    valid_indices: NDArray[np.int64]
    """Immutable ordered shell projection ``ndarray[int64, V]``."""
    action_indices: NDArray[np.int64]
    """Immutable ordered shell projection ``ndarray[int64, A]``, subset of V."""
    codec_version: str
    """Closed additive candidate-trace layout revision."""
    candidate_program_hash: str
    """Lowercase SHA-256 binding the frozen candidate program."""
    request_binding_hash: str
    """Lowercase SHA-256 binding the generation request and scene."""
    legacy_candidate_config_hash: str | None
    """Independent legacy candidate-config identity for dual-write audit."""
    candidate_substream_revision: str
    """Closed sampling-substream revision."""
    action_order_revision: str
    """Closed actor-action ordering revision."""
    completion_mode: str
    """Closed candidate completion-policy identity."""
    proposal_key_revision: str | None
    """Composition-owned proposal revision, jointly optional with replica."""
    proposal_replica: int | None
    """Non-negative proposal replica, jointly optional with revision."""

    def __post_init__(self) -> None:
        n = len(self.semantic_group_ids)
        row_axes = (
            self.semantic_group_ids,
            self.center_family_ids,
            self.gaze_family_ids,
            self.candidate_family_ids,
            self.center_ids,
            self.position_pair_ids,
            self.gaze_variant_ids,
            self.attempt_round_ids,
            self.draw_ids,
            self.proposal_keys,
            self.target_frame_identities,
            self.target_frame_availability,
        )
        if any(len(axis) != n for axis in row_axes):
            raise ValueError("Stored candidate codec axes must align over N.")
        if any(not value for axis in row_axes[:4] + (self.proposal_keys,) for value in axis):
            raise ValueError("Stored semantic and proposal identities must be nonempty.")
        arrays = tuple(axis for axis in row_axes if isinstance(axis, np.ndarray)) + (
            self.valid_indices,
            self.action_indices,
        )
        if any(array.flags.writeable for array in arrays):
            raise ValueError("Stored candidate codec arrays must be immutable.")
        if not set(self.action_indices.tolist()).issubset(self.valid_indices.tolist()):
            raise ValueError("Stored action indices must be a subset of valid indices.")
        for name, indices in (("valid", self.valid_indices), ("action", self.action_indices)):
            if indices.dtype != np.int64 or indices.ndim != 1:
                raise ValueError(f"Stored {name} indices must be int64 vectors.")
            if np.any(indices < 0) or np.any(indices >= n) or np.unique(indices).size != indices.size:
                raise ValueError(f"Stored {name} indices must uniquely reference N.")
        paired = self.position_pair_ids >= 0
        gaze = self.gaze_variant_ids >= 0
        inapplicable = (self.position_pair_ids == -1) & (self.gaze_variant_ids == -1)
        if np.any(self.center_ids < 0) or np.any(self.attempt_round_ids < 0) or np.any(self.draw_ids < 0):
            raise ValueError("Stored center, round, and draw identities must be non-negative.")
        if np.any(~(inapplicable | (paired & gaze))):
            raise ValueError("Stored pair/gaze identities must be jointly non-negative or exactly -1.")
        if any(criterion.legacy_cumulative_valid.shape != (n,) for criterion in self.criteria):
            raise ValueError("Stored candidate criteria must align over N.")
        if len({criterion.criterion_id for criterion in self.criteria}) != len(self.criteria):
            raise ValueError("Stored candidate criterion identities must be unique.")
        if self.criteria:
            previous: NDArray[np.bool_] = np.ones(n, dtype=np.bool_)
            for criterion in self.criteria:
                current = criterion.legacy_cumulative_valid
                if np.any(current & ~previous):
                    raise ValueError("Stored cumulative admission masks must be monotone.")
                expected = previous & (~criterion.evaluated | criterion.passed)
                available = criterion.local_available
                if np.any(current[available] != expected[available]):
                    raise ValueError("Stored cumulative admission mask contradicts local criterion evidence.")
                previous = current
            expected_valid: NDArray[np.bool_] = np.zeros(n, dtype=np.bool_)
            expected_valid[self.valid_indices] = True
            if not np.array_equal(previous, expected_valid):
                raise ValueError("Stored terminal cumulative admission mask must equal V.")
        if self.codec_version != "candidate-trace-v1":
            raise ValueError("Stored candidate codec version is unsupported.")
        if self.candidate_substream_revision != "shipped_mixture_seed_paths_v1":
            raise ValueError("Stored candidate substream revision is unsupported.")
        if self.action_order_revision != "ordered_hard_valid_v1" or self.completion_mode != "fixed_attempts":
            raise ValueError("Stored action/completion revisions are unsupported.")
        if any(value not in {"available", "unavailable"} for value in self.target_frame_availability):
            raise ValueError("Stored target-frame availability is undeclared.")
        if any(
            (availability == "available") != bool(identity)
            for identity, availability in zip(
                self.target_frame_identities.tolist(), self.target_frame_availability.tolist(), strict=True
            )
        ):
            raise ValueError("Stored target-frame identity must agree with availability.")
        for digest in (self.candidate_program_hash, self.request_binding_hash):
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError("Stored candidate hashes must be lowercase SHA-256 digests.")
        if (self.proposal_key_revision is None) != (self.proposal_replica is None):
            raise ValueError("Stored proposal revision and replica must be available together.")


@dataclass(frozen=True, slots=True)
class StoredCandidateIdentity:
    """Narrow immutable semantic identity for one persisted candidate row.

    Attributes:
        candidate_row_id: Store-local attempted-row identity.
        proposal_key: Stable semantic proposal path.
        candidate_family_id: Canonical combined center/gaze family.
        center_family_id: Canonical center-family identity.
        gaze_family_id: Canonical gaze-family identity.

    This read-model projection is retained by inspection consumers and does
    not acquire pose, diagnostic, admission, or action payloads.
    """

    candidate_row_id: int
    """Non-negative store-local attempted-row identity."""
    proposal_key: str
    """Stable semantic proposal path for the persisted row."""
    candidate_family_id: str
    """Canonical combined candidate-family identity."""
    center_family_id: str
    """Canonical center-family identity."""
    gaze_family_id: str
    """Canonical gaze-family identity."""

    def __post_init__(self) -> None:
        if isinstance(self.candidate_row_id, bool) or not isinstance(self.candidate_row_id, int):
            raise ValueError("Stored candidate row identity must be an exact integer.")
        if self.candidate_row_id < 0:
            raise ValueError("Stored candidate row identity must be non-negative.")
        values = (self.proposal_key, self.candidate_family_id, self.center_family_id, self.gaze_family_id)
        if any(type(value) is not str or not value for value in values):
            raise ValueError("Stored candidate semantic identities must be nonempty strings.")


@dataclass(frozen=True, slots=True)
class StoredStep:
    """One step row with shell-ordered candidate columns shared by readers."""

    row_position: int
    step_row_id: int
    rollout_row_id: int
    step_index: int
    selected_candidate_row_id: int
    selected_local_index: int
    num_candidates: int
    num_valid_candidates: int
    cumulative_target_rri: float
    cumulative_scene_rri: float
    cumulative_target_root_gain: float
    cumulative_scene_root_gain: float
    candidate_row_positions: NDArray[np.int64]
    candidate_row_ids: NDArray[np.int64]
    shell_indices: NDArray[np.int32]
    compact_valid_indices: NDArray[np.int32]
    actor_action_mask: NDArray[np.bool_]
    selected_mask: NDArray[np.bool_]
    pose_world_cam: NDArray[np.float32]
    target_rri: NDArray[np.float32]
    target_root_gain: NDArray[np.float32]
    scene_rri: NDArray[np.float32]
    selection_probabilities: NDArray[np.float32]
    mixture_ids: NDArray[np.int32]
    mixture_names: NDArray[np.str_]
    gaze_variant_ids: NDArray[np.int8]
    gaze_variant_ids_persisted: bool
    position_pair_ids: NDArray[np.int64]
    position_pair_ids_persisted: bool
    sampler_probabilities: NDArray[np.float32]
    position_ids: NDArray[np.int32]
    position_names: NDArray[np.str_]
    invalid_reason_bitsets: NDArray[np.uint32]
    primary_invalid_reason_ids: NDArray[np.uint16]
    primary_invalid_reason_names: NDArray[np.str_]
    mesh_distance_m: NDArray[np.float32]
    path_min_clearance_m: NDArray[np.float32]
    motion_step_length_m: NDArray[np.float32]
    target_distance_m: NDArray[np.float32]
    view_jitter_yaw_deg: NDArray[np.float32] | None
    view_jitter_pitch_deg: NDArray[np.float32] | None
    view_jitter_azimuth_limit_deg: NDArray[np.float32] | None
    view_jitter_elevation_limit_deg: NDArray[np.float32] | None
    view_jitter_is_bounded: NDArray[np.bool_] | None
    candidate_codec: StoredCandidateCodecFacts | None = None


@dataclass(frozen=True, slots=True)
class StoredTarget:
    """One persisted target row with decoded audit fields and factual geometry."""

    row_position: int
    target_row_id: int
    target_id: str
    source: str
    source_index: int
    class_name: str
    sem_id: int
    inst_id: int
    confidence: float
    selection_rank: int
    selection_score: float
    selection_probability: float
    target_valid: bool
    primary_invalid_reason_id: int
    gt_label_valid: bool
    matched_gt_target_row_id: int
    matched_gt_target_id: str
    gt_match_status: str
    gt_match_iou: float
    gt_match_score: float
    projected_area_pixels: float
    projected_area_fraction: float
    semidense_support_count: float
    evl_support_count: float
    effective_support_count: float
    visibility_score: float
    support_score: float
    deficit_score: float
    center_world: NDArray[np.float32]
    extents: NDArray[np.float32]
    pose_world_object: NDArray[np.float32]


@dataclass(frozen=True, slots=True)
class StoredSelectedDepth:
    """One selected-depth lookup outcome without display-specific processing."""

    available: bool
    warning: str | None
    step_row_id: int
    candidate_row_id: int | None
    depth_m: NDArray[np.float32] | None
    valid_mask: NDArray[np.bool_] | None
    focal_px: NDArray[np.float32] | None
    principal_point_px: NDArray[np.float32] | None
    image_size_hw: tuple[int, int] | None


def decode_invalid_reason(reason: int | np.integer[Any]) -> str:
    """Return the frozen invalid-reason name for one numeric code."""
    return str(_INVALID_REASON_NAMES.get(int(reason), f"reason_{int(reason)}"))


def decode_position_id(position_id: int | np.integer[Any]) -> str:
    """Return the frozen candidate-position name for one numeric id."""

    value = int(position_id)
    return str(_POSITION_NAMES.get(value, "unknown" if value < 0 else f"position_{value}"))


def rollout_at(reader: RolloutZarrStoreReader, row_position: int) -> StoredRollout:
    """Resolve one rollout by physical row position."""

    rollouts = reader.root["rollouts"]
    steps = reader.root["steps"]
    rollout_ids = np.asarray(rollouts["rollout_row_id"], dtype=np.int64).reshape(-1)
    position = int(row_position)
    if position < 0 or position >= rollout_ids.shape[0]:
        raise IndexError(f"rollout row position {position} is outside [0, {rollout_ids.shape[0]}).")

    rollout_row_id = int(rollout_ids[position])
    step_rollout_ids = np.asarray(steps["rollout_row_id"], dtype=np.int64).reshape(-1)
    step_indices = np.asarray(steps["step_index"], dtype=np.int64).reshape(-1)
    step_positions: NDArray[np.int64] = np.flatnonzero(step_rollout_ids == rollout_row_id).astype(np.int64)
    if step_positions.size == 0:
        raise ValueError(f"Rollout row {rollout_row_id} has no step rows.")
    step_positions = step_positions[np.argsort(step_indices[step_positions], kind="stable")]

    return _stored_rollout(
        reader,
        row_position=position,
        rollout_row_id=rollout_row_id,
        step_positions=step_positions,
        dictionaries=_rollout_dictionaries(reader),
    )


def rollout_rows(reader: RolloutZarrStoreReader) -> tuple[StoredRollout, ...]:
    """Read every rollout while indexing the shared step table once.

    This is the full-table counterpart to :func:`rollout_at`. It materializes
    rollout and step identifiers once, groups step positions by stable rollout
    row id, and preserves factual step order. Full-store reducers should use
    this projection so their join cost grows linearly with the number of
    rollout and step rows rather than rescanning both tables per rollout.

    Returns:
        Persisted rollout rows in physical rollout-table order.

    Raises:
        ValueError: If any persisted rollout has no associated step row.
    """

    rollouts = reader.root["rollouts"]
    steps = reader.root["steps"]
    rollout_ids = np.asarray(rollouts["rollout_row_id"], dtype=np.int64).reshape(-1)
    step_rollout_ids = np.asarray(steps["rollout_row_id"], dtype=np.int64).reshape(-1)
    step_indices = np.asarray(steps["step_index"], dtype=np.int64).reshape(-1)
    step_positions_by_rollout: dict[int, list[int]] = {}
    for step_position, rollout_row_id in enumerate(step_rollout_ids.tolist()):
        step_positions_by_rollout.setdefault(int(rollout_row_id), []).append(step_position)

    dictionaries = _rollout_dictionaries(reader)
    rows: list[StoredRollout] = []
    for row_position, rollout_row_id in enumerate(rollout_ids.tolist()):
        positions = step_positions_by_rollout.get(int(rollout_row_id), [])
        if not positions:
            raise ValueError(f"Rollout row {int(rollout_row_id)} has no step rows.")
        step_positions = np.asarray(positions, dtype=np.int64)
        step_positions = step_positions[np.argsort(step_indices[step_positions], kind="stable")]
        rows.append(
            _stored_rollout(
                reader,
                row_position=row_position,
                rollout_row_id=int(rollout_row_id),
                step_positions=step_positions,
                dictionaries=dictionaries,
            )
        )
    return tuple(rows)


def _rollout_dictionaries(reader: RolloutZarrStoreReader) -> tuple[list[str], list[str], list[str], list[str]]:
    """Decode the four rollout dictionaries once for a read transaction."""

    return (
        _string_dictionary(reader, "scene"),
        _string_dictionary(reader, "snippet"),
        _string_dictionary(reader, "split"),
        _string_dictionary(reader, "policy"),
    )


def _stored_rollout(
    reader: RolloutZarrStoreReader,
    *,
    row_position: int,
    rollout_row_id: int,
    step_positions: NDArray[np.int64],
    dictionaries: tuple[list[str], list[str], list[str], list[str]],
) -> StoredRollout:
    """Decode one rollout from already-indexed row and dictionary context."""

    rollouts = reader.root["rollouts"]
    position = int(row_position)
    scene_names, snippet_names, split_names, policy_names = dictionaries

    def decoded(values: list[str], index: int | np.integer[Any]) -> str:
        value = int(index)
        return values[value] if 0 <= value < len(values) else ""

    return StoredRollout(
        row_position=position,
        rollout_row_id=rollout_row_id,
        chain_id=int(rollouts["chain_id"][position]),
        source_row_id=int(rollouts["source_row_id"][position]),
        target_row_id=int(rollouts["target_row_id"][position]),
        scene=decoded(scene_names, rollouts["scene_id"][position]),
        snippet=decoded(snippet_names, rollouts["snippet_id"][position]),
        split=decoded(split_names, rollouts["split_id"][position]),
        policy=decoded(policy_names, rollouts["policy_id"][position]),
        horizon=int(rollouts["horizon"][position]),
        branch_factor=int(rollouts["branch_factor"][position]),
        beam_width=int(rollouts["beam_width"][position]),
        temperature=float(rollouts["temperature"][position]),
        root_pose_world=np.asarray(rollouts["root_pose_world"][position], dtype=np.float32).reshape(12),
        final_cumulative_target_rri=float(rollouts["final_cumulative_target_rri"][position]),
        final_cumulative_scene_rri=float(rollouts["final_cumulative_scene_rri"][position]),
        step_row_positions=step_positions,
    )


def rollout_by_id(reader: RolloutZarrStoreReader, rollout_row_id: int) -> StoredRollout:
    """Resolve one rollout by its stable row id."""

    rollout_ids = np.asarray(reader.array("rollouts/rollout_row_id"), dtype=np.int64).reshape(-1)
    matches = np.flatnonzero(rollout_ids == int(rollout_row_id))
    if matches.size != 1:
        raise KeyError(f"rollout_row_id {rollout_row_id} is not present in rollouts/rollout_row_id.")
    return rollout_at(reader, int(matches[0]))


def rollout_steps(reader: RolloutZarrStoreReader, rollout: StoredRollout) -> tuple[StoredStep, ...]:
    """Read shell-ordered shared candidate columns for one rollout."""

    candidates = reader.root["candidates"]
    diagnostics = reader.root["candidate_diagnostics"]
    step_table = reader.root["steps"]
    shell_index = reader.candidate_shell_index()
    codec_tables = reader.candidate_codec_tables()
    candidate_fact_dictionary = list(codec_tables.dictionary) if codec_tables is not None else []

    steps: list[StoredStep] = []
    for step_position in rollout.step_row_positions.tolist():
        step_row_id = int(step_table["step_row_id"][step_position])
        row_positions = shell_index.positions_by_step.get(step_row_id, np.empty(0, dtype=np.int64)).copy()

        def take(group: Any, name: str, dtype: Any, positions: np.ndarray = row_positions) -> np.ndarray:
            values: np.ndarray = np.asarray(group[name][positions], dtype=dtype)
            return values

        canonical = _stored_candidate_codec_facts(
            reader,
            codec_tables,
            dictionary=candidate_fact_dictionary,
            step_row_id=step_row_id,
            candidate_row_positions=row_positions,
            candidate_row_ids=shell_index.candidate_ids[row_positions],
        )
        if canonical is not None:
            legacy_valid: NDArray[np.int64] = np.flatnonzero(
                take(candidates, "compact_valid_index", np.int32) >= 0
            ).astype(np.int64)
            if not np.array_equal(canonical.valid_indices, legacy_valid):
                raise ValueError("Current canonical V projection must equal the dual-written legacy valid shell.")
            legacy_action: NDArray[np.int64] = np.flatnonzero(take(candidates, "actor_action_mask", np.bool_)).astype(
                np.int64
            )
            if not np.array_equal(canonical.action_indices, legacy_action):
                raise ValueError("Current canonical A projection must equal the dual-written legacy action shell.")

        selected_mask = take(candidates, "selected_mask", np.bool_)
        selected_matches = np.flatnonzero(selected_mask)
        selected_local_index = int(selected_matches[0]) if selected_matches.size else -1
        mixture_ids = take(candidates, "mixture_id", np.int32)
        gaze_variant_ids_persisted = "gaze_variant_id" in candidates
        gaze_variant_ids = (
            take(candidates, "gaze_variant_id", np.int8)
            if gaze_variant_ids_persisted
            else np.full(row_positions.shape, -1, dtype=np.int8)
        )
        position_ids = take(diagnostics, "position_id", np.int32)
        reason_ids = take(candidates, "primary_invalid_reason", np.uint16)
        view_bundle = (
            "view_jitter_yaw_deg",
            "view_jitter_pitch_deg",
            "view_jitter_azimuth_limit_deg",
            "view_jitter_elevation_limit_deg",
            "view_jitter_is_bounded",
        )
        view_bundle_presence = tuple(name in diagnostics for name in view_bundle)
        if any(view_bundle_presence) and not all(view_bundle_presence):
            raise ValueError("persisted view-jitter evidence must contain the complete five-array bundle")
        has_view_bundle = all(view_bundle_presence)
        steps.append(
            StoredStep(
                row_position=int(step_position),
                step_row_id=step_row_id,
                rollout_row_id=rollout.rollout_row_id,
                step_index=int(step_table["step_index"][step_position]),
                selected_candidate_row_id=int(step_table["selected_candidate_row_id"][step_position]),
                selected_local_index=selected_local_index,
                num_candidates=int(step_table["num_candidates"][step_position]),
                num_valid_candidates=int(step_table["num_valid_candidates"][step_position]),
                cumulative_target_rri=float(step_table["cumulative_target_rri"][step_position]),
                cumulative_scene_rri=float(step_table["cumulative_scene_rri"][step_position]),
                cumulative_target_root_gain=float(step_table["cumulative_target_root_gain"][step_position]),
                cumulative_scene_root_gain=float(step_table["cumulative_scene_root_gain"][step_position]),
                candidate_row_positions=row_positions,
                candidate_row_ids=shell_index.candidate_ids[row_positions],
                shell_indices=take(candidates, "shell_index", np.int32),
                compact_valid_indices=take(candidates, "compact_valid_index", np.int32),
                actor_action_mask=take(candidates, "actor_action_mask", np.bool_),
                selected_mask=selected_mask,
                pose_world_cam=take(candidates, "pose_world_cam", np.float32).reshape(-1, 12),
                target_rri=take(candidates, "target_rri", np.float32),
                target_root_gain=take(candidates, "target_root_gain", np.float32),
                scene_rri=take(candidates, "scene_rri", np.float32),
                selection_probabilities=take(candidates, "selection_probabilities", np.float32),
                mixture_ids=mixture_ids,
                mixture_names=(
                    candidate_mixture_family_names(reader, mixture_ids, gaze_variant_ids)
                    if canonical is None
                    else np.full(row_positions.shape, "", dtype=np.str_)
                ),
                gaze_variant_ids=gaze_variant_ids,
                gaze_variant_ids_persisted=gaze_variant_ids_persisted,
                position_pair_ids=(
                    take(candidates, "position_pair_id", np.int64)
                    if "position_pair_id" in candidates
                    else np.full(row_positions.shape, -1, dtype=np.int64)
                ),
                position_pair_ids_persisted="position_pair_id" in candidates,
                sampler_probabilities=take(candidates, "sampler_probability", np.float32),
                position_ids=position_ids,
                position_names=np.asarray([decode_position_id(value) for value in position_ids], dtype=np.str_),
                invalid_reason_bitsets=take(candidates, "invalid_reason_bitset", np.uint32),
                primary_invalid_reason_ids=reason_ids,
                primary_invalid_reason_names=np.asarray(
                    [decode_invalid_reason(value) for value in reason_ids], dtype=np.str_
                ),
                mesh_distance_m=take(diagnostics, "mesh_distance_m", np.float32),
                path_min_clearance_m=take(diagnostics, "path_min_clearance_m", np.float32),
                motion_step_length_m=take(diagnostics, "motion_step_length_m", np.float32),
                target_distance_m=take(diagnostics, "target_distance_m", np.float32),
                view_jitter_yaw_deg=(take(diagnostics, "view_jitter_yaw_deg", np.float32) if has_view_bundle else None),
                view_jitter_pitch_deg=(
                    take(diagnostics, "view_jitter_pitch_deg", np.float32) if has_view_bundle else None
                ),
                view_jitter_azimuth_limit_deg=(
                    take(diagnostics, "view_jitter_azimuth_limit_deg", np.float32) if has_view_bundle else None
                ),
                view_jitter_elevation_limit_deg=(
                    take(diagnostics, "view_jitter_elevation_limit_deg", np.float32) if has_view_bundle else None
                ),
                view_jitter_is_bounded=(
                    take(diagnostics, "view_jitter_is_bounded", np.bool_) if has_view_bundle else None
                ),
                candidate_codec=canonical,
            )
        )
    return tuple(steps)


def candidate_semantic_identities(
    reader: RolloutZarrStoreReader,
    candidate_row_ids: NDArray[np.int64],
) -> tuple[StoredCandidateIdentity, ...] | None:
    """Read only proposal/family identities for requested current-codec rows.

    Returns ``None`` for a pure legacy store. The reader-local index is reused;
    no pose, diagnostic, admission, or rollout table is materialized.
    """

    tables = reader.candidate_codec_tables()
    if tables is None:
        return None
    requested = np.asarray(candidate_row_ids, dtype=np.int64).reshape(-1)
    if np.unique(requested).size != requested.size:
        raise ValueError("Candidate semantic identity requests must contain unique row ids.")
    try:
        positions = np.asarray([tables.semantic_positions[int(value)] for value in requested], dtype=np.int64)
    except KeyError as exc:
        raise ValueError("Candidate semantic identity request references an unknown current-codec row.") from exc

    def decoded(field_name: str) -> list[str]:
        ids = np.asarray(reader.root[f"candidate_semantics/{field_name}"].oindex[positions], dtype=np.int64)
        if np.any(ids < 0) or np.any(ids >= len(tables.dictionary)):
            raise ValueError("Candidate semantic identity references an invalid dictionary row.")
        return [tables.dictionary[int(value)] for value in ids.tolist()]

    proposal = decoded("proposal_key_id")
    family = decoded("candidate_family_id")
    center = decoded("center_family_id")
    gaze = decoded("gaze_family_id")
    return tuple(
        StoredCandidateIdentity(
            candidate_row_id=int(candidate_row_id),
            proposal_key=proposal[index],
            candidate_family_id=family[index],
            center_family_id=center[index],
            gaze_family_id=gaze[index],
        )
        for index, candidate_row_id in enumerate(requested.tolist())
    )


def _stored_candidate_codec_facts(
    reader: RolloutZarrStoreReader,
    tables: _CandidateCodecTables | None,
    *,
    dictionary: list[str],
    step_row_id: int,
    candidate_row_positions: NDArray[np.int64],
    candidate_row_ids: NDArray[np.int64],
) -> StoredCandidateCodecFacts | None:
    """Decode one complete additive candidate codec bundle or legacy absence."""

    if tables is None:
        return None

    def readonly(values: np.ndarray) -> np.ndarray:
        values.setflags(write=False)
        return values

    def decode(ids: np.ndarray) -> NDArray[np.str_]:
        values = np.asarray(ids, dtype=np.int64).reshape(-1)
        if np.any(values < 0) or np.any(values >= len(dictionary)):
            raise ValueError("Candidate codec dictionary id is outside the persisted dictionary.")
        return readonly(np.asarray([dictionary[int(value)] for value in values], dtype=np.str_))

    step_position = tables.step_positions.get(step_row_id)
    if step_position is None:
        raise ValueError("Current candidate codec requires exactly one fact row per persisted step.")

    def row_values(group_name: str, field_name: str, positions: NDArray[np.int64]) -> np.ndarray:
        array = reader.root[f"{group_name}/{field_name}"]
        values: np.ndarray = np.asarray(array.oindex[positions])
        return values

    def scalar(group_name: str, field_name: str, position: int) -> Any:
        return reader.root[f"{group_name}/{field_name}"][position]

    def step_value(name: str) -> str:
        return str(decode(np.asarray([scalar("step_candidate_facts", f"{name}_id", step_position)]))[0])

    attempted_count = int(scalar("step_candidate_facts", "attempted_count", step_position))
    valid_count = int(scalar("step_candidate_facts", "valid_count", step_position))
    action_count = int(scalar("step_candidate_facts", "action_count", step_position))
    proposal_revision_id = int(scalar("step_candidate_facts", "proposal_key_revision_id", step_position))
    proposal_replica_value = int(scalar("step_candidate_facts", "proposal_replica", step_position))
    legacy_config_hash_id = int(scalar("step_candidate_facts", "legacy_candidate_config_hash_id", step_position))
    if proposal_revision_id < -1 or proposal_replica_value < -1:
        raise ValueError("Stored proposal-key missing-value sentinel must be exactly -1.")
    if (proposal_revision_id == -1) != (proposal_replica_value == -1):
        raise ValueError("Stored proposal-key revision and replica must be available together.")
    if legacy_config_hash_id < -1:
        raise ValueError("Stored legacy candidate-config hash sentinel must be exactly -1.")
    if attempted_count != candidate_row_positions.shape[0]:
        raise ValueError("Candidate codec attempted count does not match the stored step shell.")

    try:
        semantic_positions = np.asarray(
            [tables.semantic_positions[int(candidate_id)] for candidate_id in candidate_row_ids], dtype=np.int64
        )
    except KeyError as exc:
        raise ValueError("Candidate semantic rows do not bind the stored attempted shell.") from exc
    if semantic_positions.shape[0] != attempted_count or np.unique(semantic_positions).size != attempted_count:
        raise ValueError("Candidate semantic rows do not bind one-to-one to the stored attempted shell.")

    action_positions = tables.action_positions_by_step.get(step_row_id, np.empty(0, dtype=np.int64))
    order = row_values("candidate_actions", "action_position", action_positions)
    if action_positions.shape[0] != action_count or not np.array_equal(order, np.arange(action_count)):
        raise ValueError("Candidate action rows must provide one dense ordered A projection.")
    action_indices: NDArray[np.int64] = row_values("candidate_actions", "shell_index", action_positions).astype(
        np.int64, copy=True
    )
    if (
        np.any(action_indices < 0)
        or np.any(action_indices >= attempted_count)
        or np.unique(action_indices).size != action_count
    ):
        raise ValueError("Candidate action rows contain invalid or duplicate shell indices.")
    valid_positions = tables.valid_positions_by_step.get(step_row_id, np.empty(0, dtype=np.int64))
    valid_order = row_values("candidate_valids", "valid_position", valid_positions)
    if valid_positions.shape[0] != valid_count or not np.array_equal(valid_order, np.arange(valid_count)):
        raise ValueError("Candidate valid rows must provide one dense ordered V projection.")
    valid_indices: NDArray[np.int64] = row_values("candidate_valids", "shell_index", valid_positions).astype(
        np.int64, copy=True
    )
    if (
        np.any(valid_indices < 0)
        or np.any(valid_indices >= attempted_count)
        or np.unique(valid_indices).size != valid_count
    ):
        raise ValueError("Candidate valid rows contain invalid or duplicate shell indices.")
    if not set(action_indices.tolist()).issubset(valid_indices.tolist()):
        raise ValueError("Candidate action indices must be a subset of valid indices.")

    criteria_rows = np.concatenate(
        [
            tables.criterion_positions_by_candidate.get(int(candidate_id), np.empty(0, dtype=np.int64))
            for candidate_id in candidate_row_ids
        ]
    )
    criterion_candidate_ids: NDArray[np.int64] = row_values(
        "candidate_criteria", "candidate_row_id", criteria_rows
    ).astype(np.int64)
    criterion_indices: NDArray[np.int64] = row_values("candidate_criteria", "criterion_index", criteria_rows).astype(
        np.int64
    )
    criterion_candidate_by_position = {
        int(position): int(candidate_id)
        for position, candidate_id in zip(criteria_rows.tolist(), criterion_candidate_ids.tolist(), strict=True)
    }
    unique_criterion_indices = sorted(set(criterion_indices.tolist()))
    if unique_criterion_indices != list(range(len(unique_criterion_indices))):
        raise ValueError("Candidate criterion indices must be dense from zero.")
    criteria: list[StoredCandidateCriterion] = []
    for criterion_index in unique_criterion_indices:
        rows = criteria_rows[criterion_indices == criterion_index]
        row_by_id = {criterion_candidate_by_position[int(position)]: int(position) for position in rows}
        if len(row_by_id) != rows.shape[0] or set(row_by_id) != {int(value) for value in candidate_row_ids}:
            raise ValueError("Candidate criterion rows must align one-to-one with the attempted shell.")
        positions = np.asarray([row_by_id[int(value)] for value in candidate_row_ids], dtype=np.int64)
        criterion_names = decode(row_values("candidate_criteria", "criterion_id", positions))
        reason_revisions = decode(row_values("candidate_criteria", "reason_revision_id", positions))
        source_revisions = decode(row_values("candidate_criteria", "source_role_revision_id", positions))
        if (
            len(set(criterion_names.tolist())) != 1
            or len(set(reason_revisions.tolist())) != 1
            or len(set(source_revisions.tolist())) != 1
        ):
            raise ValueError("Candidate criterion identity and revisions must be constant across N.")
        criteria.append(
            StoredCandidateCriterion(
                criterion_id=str(criterion_names[0]),
                legacy_cumulative_valid=readonly(
                    row_values("candidate_criteria", "legacy_cumulative_valid", positions).astype(np.bool_)
                ),
                local_available=readonly(
                    row_values("candidate_criteria", "local_available", positions).astype(np.bool_)
                ),
                applicable=readonly(row_values("candidate_criteria", "applicable", positions).astype(np.bool_)),
                evaluated=readonly(row_values("candidate_criteria", "evaluated", positions).astype(np.bool_)),
                passed=readonly(row_values("candidate_criteria", "passed", positions).astype(np.bool_)),
                reason_code=readonly(row_values("candidate_criteria", "reason_code", positions).astype(np.int64)),
                margin=readonly(row_values("candidate_criteria", "margin", positions).astype(np.float32)),
                source_role=readonly(row_values("candidate_criteria", "source_role", positions).astype(np.int64)),
                reason_revision=str(reason_revisions[0]),
                source_role_revision=str(source_revisions[0]),
            )
        )
    return StoredCandidateCodecFacts(
        semantic_group_ids=decode(row_values("candidate_semantics", "semantic_group_id", semantic_positions)),
        center_family_ids=decode(row_values("candidate_semantics", "center_family_id", semantic_positions)),
        gaze_family_ids=decode(row_values("candidate_semantics", "gaze_family_id", semantic_positions)),
        candidate_family_ids=decode(row_values("candidate_semantics", "candidate_family_id", semantic_positions)),
        center_ids=readonly(row_values("candidate_semantics", "center_id", semantic_positions).astype(np.int64)),
        position_pair_ids=readonly(
            row_values("candidate_semantics", "position_pair_id", semantic_positions).astype(np.int64)
        ),
        gaze_variant_ids=readonly(
            row_values("candidate_semantics", "gaze_variant_id", semantic_positions).astype(np.int64)
        ),
        attempt_round_ids=readonly(
            row_values("candidate_semantics", "attempt_round_id", semantic_positions).astype(np.int64)
        ),
        draw_ids=readonly(row_values("candidate_semantics", "draw_id", semantic_positions).astype(np.int64)),
        proposal_keys=decode(row_values("candidate_semantics", "proposal_key_id", semantic_positions)),
        target_frame_identities=decode(
            row_values("candidate_semantics", "target_frame_identity_id", semantic_positions)
        ),
        target_frame_availability=decode(
            row_values("candidate_semantics", "target_frame_availability_id", semantic_positions)
        ),
        criteria=tuple(criteria),
        valid_indices=readonly(valid_indices),
        action_indices=readonly(action_indices),
        codec_version=step_value("codec_version"),
        candidate_program_hash=step_value("candidate_program_hash"),
        request_binding_hash=step_value("request_binding_hash"),
        legacy_candidate_config_hash=(
            None if legacy_config_hash_id < 0 else str(decode(np.asarray([legacy_config_hash_id]))[0])
        ),
        candidate_substream_revision=step_value("candidate_substream_revision"),
        action_order_revision=step_value("action_order_revision"),
        completion_mode=step_value("completion_mode"),
        proposal_key_revision=(
            None if proposal_revision_id < 0 else str(decode(np.asarray([proposal_revision_id]))[0])
        ),
        proposal_replica=None if proposal_replica_value < 0 else proposal_replica_value,
    )


def candidate_mixture_family_names(
    reader: RolloutZarrStoreReader,
    mixture_ids: NDArray[np.int32],
    gaze_variant_ids: NDArray[np.int8],
) -> NDArray[np.str_]:
    """Decode base/paired family identity from config and persisted gaze provenance."""

    if mixture_ids.shape != gaze_variant_ids.shape:
        raise ValueError("mixture and gaze-variant arrays must align")
    component_names: dict[int, tuple[str, str | None]] = {}
    try:
        writer_config = reader.manifest().get("manifest", {}).get("generation", {}).get("writer_config")
        candidate_mixture = writer_config.get("candidate_mixture") if isinstance(writer_config, dict) else None
        components = candidate_mixture.get("components") if isinstance(candidate_mixture, dict) else None
        if isinstance(components, list):
            for index, component in enumerate(components):
                if isinstance(component, dict):
                    name = component.get("name") or component.get("family") or component.get("position_mode")
                    if name is not None:
                        paired = component.get("paired_view_mode")
                        paired_name = None if paired is None else f"{name}__paired_{paired}"
                        component_names[index] = (str(name), paired_name)
    except (KeyError, TypeError, ValueError):
        component_names = {}
    names = []
    for mixture_id, gaze_variant_id in zip(mixture_ids.tolist(), gaze_variant_ids.tolist(), strict=True):
        identity = component_names.get(int(mixture_id))
        variant = int(gaze_variant_id)
        if identity is None:
            if variant >= 0:
                raise ValueError("paired gaze family cannot be decoded without component provenance")
            names.append("unknown" if int(mixture_id) < 0 else f"component_{int(mixture_id)}")
            continue
        base_name, paired_name = identity
        if paired_name is None:
            if variant >= 0:
                raise ValueError(f"unpaired component {base_name!r} carries paired gaze provenance")
            names.append(base_name)
        elif variant == 0:
            names.append(base_name)
        elif variant == 1:
            names.append(paired_name)
        else:
            raise ValueError(f"paired component {base_name!r} is missing canonical gaze-variant provenance")
    return np.asarray(names, dtype=np.str_)


def target_rows(reader: RolloutZarrStoreReader) -> tuple[StoredTarget, ...]:
    """Read all persisted target rows with decoded factual fields."""

    if "targets" not in reader.root:
        return ()
    targets = reader.root["targets"]
    target_row_ids = np.asarray(targets["target_row_id"], dtype=np.int64).reshape(-1)
    target_names = _string_dictionary(reader, "target")
    source_names = _string_dictionary(reader, "target_source")
    class_names = _string_dictionary(reader, "class_name")
    status_names = _string_dictionary(reader, "target_match_status")

    def decoded(values: list[str], index: int | np.integer[Any]) -> str:
        value = int(index)
        return values[value] if 0 <= value < len(values) else ""

    def optional(name: str, index: int, default: float = float("nan")) -> float:
        try:
            values = np.asarray(targets[name]).reshape(-1)
        except KeyError:
            return default
        return float(values[index]) if index < values.shape[0] else default

    rows: list[StoredTarget] = []
    for index, target_row_id in enumerate(target_row_ids.tolist()):
        rows.append(
            StoredTarget(
                row_position=index,
                target_row_id=int(target_row_id),
                target_id=decoded(target_names, targets["target_id"][index]),
                source=decoded(source_names, targets["target_source_id"][index]),
                source_index=int(targets["target_source_index"][index]),
                class_name=decoded(class_names, targets["target_class_name_id"][index]),
                sem_id=int(targets["target_sem_id"][index]),
                inst_id=int(targets["target_inst_id"][index]),
                confidence=float(targets["target_confidence"][index]),
                selection_rank=int(targets["target_selection_rank"][index]),
                selection_score=float(targets["target_selection_score"][index]),
                selection_probability=float(targets["target_selection_probability"][index]),
                target_valid=bool(targets["target_valid_mask"][index]),
                primary_invalid_reason_id=int(targets["target_primary_invalid_reason"][index]),
                gt_label_valid=bool(targets["gt_label_valid_mask"][index]),
                matched_gt_target_row_id=int(targets["matched_gt_target_row_id"][index]),
                matched_gt_target_id=decoded(target_names, targets["matched_gt_target_id"][index]),
                gt_match_status=decoded(status_names, targets["gt_match_status_id"][index]),
                gt_match_iou=float(targets["gt_match_iou"][index]),
                gt_match_score=float(targets["gt_match_score"][index]),
                projected_area_pixels=optional("target_projected_area_pixels", index),
                projected_area_fraction=optional("target_projected_area_fraction", index),
                semidense_support_count=optional("target_semidense_support_count", index),
                evl_support_count=optional("target_evl_support_count", index),
                effective_support_count=optional("target_effective_support_count", index),
                visibility_score=optional("target_visibility_score", index),
                support_score=optional("target_support_score", index),
                deficit_score=optional("target_deficit_score", index),
                center_world=np.asarray(targets["target_center_world"][index], dtype=np.float32).reshape(3),
                extents=np.asarray(targets["target_extents"][index], dtype=np.float32).reshape(3),
                pose_world_object=np.asarray(targets["target_pose_world_object"][index], dtype=np.float32).reshape(12),
            )
        )
    return tuple(rows)


def target_by_id(reader: RolloutZarrStoreReader, target_row_id: int) -> StoredTarget | None:
    """Return one target by stable row id, or None when absent."""

    return next((row for row in target_rows(reader) if row.target_row_id == int(target_row_id)), None)


def selected_depth_for_step(reader: RolloutZarrStoreReader, step: StoredStep) -> StoredSelectedDepth:
    """Read and validate one selected-depth row without presentation policy."""

    def unavailable(message: str, candidate_row_id: int | None = None) -> StoredSelectedDepth:
        return StoredSelectedDepth(
            available=False,
            warning=message,
            step_row_id=step.step_row_id,
            candidate_row_id=candidate_row_id,
            depth_m=None,
            valid_mask=None,
            focal_px=None,
            principal_point_px=None,
            image_size_hw=None,
        )

    if not bool(reader.root.attrs.get("selected_depth_enabled", False)):
        return unavailable("selected_depth unavailable: store metadata has selected_depth_enabled=false.")
    try:
        group = reader.root["selected_depth"]
        step_ids = np.asarray(group["step_row_id"], dtype=np.int64).reshape(-1)
        candidate_ids = np.asarray(group["candidate_row_id"], dtype=np.int64).reshape(-1)
    except KeyError as exc:
        return unavailable(f"selected_depth unavailable: missing array {exc}.")

    matches = np.flatnonzero(step_ids == step.step_row_id)
    if matches.size != 1:
        return unavailable(
            f"selected_depth unavailable: expected one row for step_row_id={step.step_row_id}, found {matches.size}."
        )
    row = int(matches[0])
    candidate_row_id = int(candidate_ids[row])
    if candidate_row_id != step.selected_candidate_row_id:
        return unavailable(
            "selected_depth candidate mismatch: "
            f"depth candidate_row_id={candidate_row_id}, "
            f"step selected_candidate_row_id={step.selected_candidate_row_id}.",
            candidate_row_id,
        )
    try:
        depth = np.asarray(group["depth_m"][row], dtype=np.float32)
        valid_mask = np.asarray(group["valid_mask"][row], dtype=np.bool_)
        focal = np.asarray(group["focal_px"][row], dtype=np.float32).reshape(-1)
        principal = np.asarray(group["principal_point_px"][row], dtype=np.float32).reshape(-1)
        image_size = np.asarray(group["image_size_hw"][row], dtype=np.int32).reshape(-1)
    except KeyError as exc:
        return unavailable(f"selected_depth unavailable: missing dense array {exc}.", candidate_row_id)
    if depth.ndim != 2 or valid_mask.shape != depth.shape:
        return unavailable(
            f"selected_depth shape mismatch: depth_m={tuple(depth.shape)} valid_mask={tuple(valid_mask.shape)}.",
            candidate_row_id,
        )
    if focal.shape[0] != 2 or principal.shape[0] != 2 or image_size.shape[0] != 2:
        return unavailable("selected_depth camera metadata must have two values per row.", candidate_row_id)
    height, width = int(image_size[0]), int(image_size[1])
    if (height, width) != tuple(depth.shape):
        return unavailable(
            f"selected_depth image_size_hw={(height, width)} does not match depth shape {tuple(depth.shape)}.",
            candidate_row_id,
        )
    depth = depth.copy()
    depth[~(valid_mask & np.isfinite(depth))] = np.nan
    return StoredSelectedDepth(
        available=True,
        warning=None,
        step_row_id=step.step_row_id,
        candidate_row_id=candidate_row_id,
        depth_m=depth,
        valid_mask=valid_mask.copy(),
        focal_px=focal.copy(),
        principal_point_px=principal.copy(),
        image_size_hw=(height, width),
    )


def _string_dictionary(reader: RolloutZarrStoreReader, name: str) -> list[str]:
    try:
        encoded = np.asarray(reader.array(f"dictionaries/{name}"), dtype=np.uint8).reshape(-1).tobytes()
        values = json.loads(encoded.decode("utf-8"))
    except (KeyError, json.JSONDecodeError, UnicodeDecodeError):
        return []
    return [str(value) for value in values] if isinstance(values, list) else []


__all__ = (
    "StoredCandidateCodecFacts StoredCandidateCriterion StoredCandidateIdentity StoredRollout StoredSelectedDepth "
    "StoredStep StoredTarget candidate_semantic_identities "
    "candidate_mixture_family_names "
    "decode_invalid_reason decode_position_id "
    "rollout_at rollout_by_id rollout_rows rollout_steps selected_depth_for_step target_by_id target_rows"
).split()
