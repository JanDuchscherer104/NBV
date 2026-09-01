"""Canonical immutable candidate evidence and live/stored adapters."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Literal, Protocol, cast

import numpy as np
import torch

from .read_model import StoredRollout, StoredStep, StoredTarget

if TYPE_CHECKING:
    from ..pose_generation import CandidateSet


class _TensorContainer(Protocol):
    """Private typed view of EFM3D tensor-wrapper access."""

    def tensor(self) -> torch.Tensor:
        """Return the wrapped tensor without changing device or ownership."""

        ...


def _finite_or_none(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


class CandidateFactAvailability(StrEnum):
    """Typed provenance for facts that current or legacy sources may omit."""

    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    LEGACY_MISSING = "legacy_missing"
    INAPPLICABLE = "inapplicable"


class CandidateProjectionUnavailableReason(StrEnum):
    """Typed reason why canonical target-relative support is unavailable."""

    TARGET_MISSING = "target_missing"
    TARGET_ANCHOR_MISMATCH = "target_anchor_mismatch"
    DEGENERATE_TARGET_BEARING = "degenerate_target_bearing"
    POSE_NONFINITE = "pose_nonfinite"


@dataclass(frozen=True, slots=True)
class CandidateRolloutOverlay:
    """Optional rollout-only context attached after candidate generation.

    Direct generation uses :meth:`unavailable`; only a rollout composition or
    stored-step adapter may provide temporal values. Candidate generation must
    never infer these facts from a request or shell width.
    """

    horizon: int | None
    """Configured rollout horizon ``H`` in actions, or ``None`` when unavailable."""

    factual_step: int | None
    """Zero-based factual rollout step ``t``, or ``None`` for direct evidence."""

    remaining_budget: int | None
    """Current-decision-inclusive remaining action budget, or ``None``."""

    history_coverage: int | None = None
    """Number of prior factual actions covered by the evidence, when persisted."""

    @classmethod
    def unavailable(cls) -> CandidateRolloutOverlay:
        """Return the explicit direct-generation overlay with no invented values."""

        return cls(None, None, None, None)

    def __post_init__(self) -> None:
        for name in ("horizon", "factual_step", "remaining_budget", "history_coverage"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise ValueError(f"{name} must be a non-negative integer or None")
        if self.horizon is not None and self.factual_step is not None and self.factual_step >= self.horizon:
            raise ValueError("factual_step must be smaller than horizon")
        if self.horizon is not None and self.factual_step is not None and self.remaining_budget is not None:
            expected = self.horizon - self.factual_step
            if self.remaining_budget != expected:
                raise ValueError("remaining_budget must equal H - factual_step")

    @property
    def available(self) -> bool:
        """Whether any rollout-owned overlay fact is available."""

        return any(
            value is not None
            for value in (self.horizon, self.factual_step, self.remaining_budget, self.history_coverage)
        )


@dataclass(frozen=True, slots=True)
class CandidateCriterionSnapshot:
    """Immutable scalar admission evidence for one candidate and criterion."""

    criterion_id: str
    """Stable admission criterion identity."""

    cumulative_valid: bool
    """Cumulative hard-valid state after this criterion."""

    available: bool
    """Whether all criterion-local facts below were available for this row."""

    applicable: bool | None
    """Criterion applicability, or ``None`` when local evidence is unavailable."""

    evaluated: bool | None
    """Backend evaluation state, or ``None`` when unavailable."""

    passed: bool | None
    """Criterion-local pass state, or ``None`` when unavailable."""

    reason_code: int | None
    """Revisioned criterion reason code, or ``None`` when unavailable."""

    margin: float | None
    """Signed single-unit admission margin, or ``None`` when unavailable."""

    source_role: int | None
    """Revisioned evidence-source role, or ``None`` when unavailable."""

    reason_revision: str
    """Closed reason-code revision."""

    source_role_revision: str
    """Closed source-role revision."""

    def __post_init__(self) -> None:
        if not self.criterion_id:
            raise ValueError("criterion_id must be nonempty")
        if self.margin is not None and not math.isfinite(self.margin):
            raise ValueError("criterion margin must be finite when available")
        local = (self.applicable, self.evaluated, self.passed, self.reason_code, self.margin, self.source_role)
        if self.available != all(value is not None for value in local):
            raise ValueError("criterion availability must agree with all local facts")


@dataclass(frozen=True, slots=True)
class CandidateEvidenceRow:
    """One presentation-free attempted candidate row.

    Coordinates ending in ``_world_m`` use ARIA world metres. Coordinates
    ending in ``_target_normalized`` use the target-aligned Z-up frame divided
    by the root-to-target Euclidean distance. Gaze vectors are unitless unit
    vectors in the named frame.
    """

    attempted_index: int
    """Zero-based row on the full attempted axis ``N``."""

    candidate_id: int | None
    """Persisted source-row identity, or ``None`` for live/unidentified evidence."""

    center_world_m: tuple[float, float, float] | None
    """Candidate camera centre in ARIA world metres."""

    world_pose_availability: CandidateFactAvailability
    """Availability of the source world pose used by inspection."""

    world_pose_unavailable_reason: CandidateProjectionUnavailableReason | None
    """Typed source-pose failure; currently only ``POSE_NONFINITE``."""

    center_target_normalized: tuple[float, float, float] | None
    """Root-relative centre in target-aligned normalized support, when available."""

    gaze_target_unit: tuple[float, float, float] | None
    """Camera-forward unit vector in target-aligned axes, when available."""

    projection_availability: CandidateFactAvailability
    """Availability of this row's target-relative projected centre."""

    projection_unavailable_reason: CandidateProjectionUnavailableReason | None
    """Typed row-local projection failure, or ``None`` when available/missing."""

    hard_valid: bool
    """Final hard-admission membership on ``N``."""

    action: bool | None
    """Membership in ordered scoreable actions ``A``, or ``None`` for legacy rows."""

    selected: bool | None
    """Downstream selection state, or ``None`` when selection is unavailable."""

    semantic_group_id: str | None
    """Stable positional group identity."""

    center_family_id: str | None
    """Stable center-family identity."""

    gaze_family_id: str | None
    """Stable gaze-family identity."""

    candidate_family_id: str | None
    """Stable combined center/gaze family identity."""

    legacy_family_label: str | None
    """Explicit non-semantic family label retained for legacy display parity."""

    legacy_invalid_reason_bitset: int | None
    """Persisted legacy invalid-reason bitset, when available."""

    legacy_primary_invalid_reason: str | None
    """Persisted legacy primary invalid-reason label, when available."""

    legacy_admission_measurements: tuple[tuple[str, float], ...]
    """Sorted persisted legacy admission diagnostics with explicit names/units."""

    center_id: int | None
    """Shared-center lineage identifier."""

    position_pair_id: int | None
    """Paired-position lineage identifier."""

    gaze_variant_id: int | None
    """Ordered gaze-variant identifier."""

    legacy_position_pair_id: int | None
    """Persisted legacy pair identity, never upgraded to canonical lineage."""

    legacy_gaze_variant_id: int | None
    """Persisted legacy gaze-variant identity, never upgraded to canonical lineage."""

    attempt_round_id: int | None
    """Completion-attempt round identifier."""

    draw_id: int | None
    """Within-family draw identifier."""

    proposal_key: str | None
    """Semantic sampling path/proposal identity."""

    proposal_probability: float | None
    """Proposal probability or density supplied by generation."""

    view_jitter_yaw_deg: float | None
    """Realized local yaw residual in degrees."""

    view_jitter_pitch_deg: float | None
    """Realized local pitch residual in degrees."""

    view_jitter_is_bounded: bool | None
    """Whether this row uses a configured bounded yaw/pitch box."""

    view_jitter_azimuth_limit_deg: float | None
    """Configured non-negative yaw envelope in degrees."""

    view_jitter_elevation_limit_deg: float | None
    """Configured non-negative pitch envelope in degrees."""

    target_frame_identity: str | None
    """Generation-owned target-frame identity, or ``None`` when unavailable."""

    admission: tuple[CandidateCriterionSnapshot, ...]
    """Ordered criterion-local and cumulative admission evidence."""

    semantic_lineage_availability: CandidateFactAvailability
    """Availability/source state of semantic family and lineage fields."""

    action_availability: CandidateFactAvailability
    """Availability/source state of the action projection fact."""

    selection_availability: CandidateFactAvailability
    """Availability/source state of factual selection."""

    proposal_key_availability: CandidateFactAvailability
    """Availability/source state of the semantic proposal key."""

    proposal_probability_availability: CandidateFactAvailability
    """Availability/source state of proposal probability/density."""

    jitter_availability: CandidateFactAvailability
    """Availability/source state of view-jitter evidence."""

    admission_availability: CandidateFactAvailability
    """Availability/source state of criterion-local admission evidence."""

    generation_frame_availability: CandidateFactAvailability
    """Availability/source state of generation-owned target-frame evidence."""

    legacy_family_label_availability: CandidateFactAvailability
    """Availability/source state of the legacy display-only family label."""

    legacy_admission_availability: CandidateFactAvailability
    """Availability/source state of legacy invalid-reason and margin facts."""

    legacy_pair_lineage_availability: CandidateFactAvailability
    """Availability of persisted legacy pair/gaze lineage or inapplicability."""

    def __post_init__(self) -> None:
        if self.attempted_index < 0 or (self.candidate_id is not None and self.candidate_id < 0):
            raise ValueError("candidate row identities must be non-negative")
        for name in ("center_world_m", "center_target_normalized", "gaze_target_unit"):
            values = getattr(self, name)
            if values is not None and (len(values) != 3 or not all(math.isfinite(value) for value in values)):
                raise ValueError(f"{name} must be a finite 3-vector when available")
        if self.gaze_target_unit is not None and not math.isclose(
            sum(value * value for value in self.gaze_target_unit), 1.0, abs_tol=1.0e-4
        ):
            raise ValueError("gaze_target_unit must be unit length")
        if self.world_pose_availability is CandidateFactAvailability.AVAILABLE:
            if self.center_world_m is None or self.world_pose_unavailable_reason is not None:
                raise ValueError("available world pose requires a finite centre and no failure")
        elif self.world_pose_availability is CandidateFactAvailability.UNAVAILABLE:
            if (
                self.center_world_m is not None
                or self.world_pose_unavailable_reason is not CandidateProjectionUnavailableReason.POSE_NONFINITE
            ):
                raise ValueError("unavailable world pose requires the nonfinite-pose reason")
        elif self.world_pose_availability is CandidateFactAvailability.LEGACY_MISSING:
            if self.center_world_m is not None or self.world_pose_unavailable_reason is not None:
                raise ValueError("legacy-missing world pose cannot retain source-pose facts")
        else:
            raise ValueError("world-pose availability must be available, unavailable, or legacy-missing")
        if self.projection_availability is CandidateFactAvailability.AVAILABLE:
            if self.center_target_normalized is None or self.projection_unavailable_reason is not None:
                raise ValueError("available row projection requires a centre and no failure")
        elif self.projection_availability is CandidateFactAvailability.UNAVAILABLE:
            if (
                self.center_target_normalized is not None
                or self.gaze_target_unit is not None
                or self.projection_unavailable_reason is None
            ):
                raise ValueError("unavailable row projection requires one typed failure and no coordinates")
        elif self.projection_availability is CandidateFactAvailability.LEGACY_MISSING:
            if (
                self.center_target_normalized is not None
                or self.gaze_target_unit is not None
                or self.projection_unavailable_reason is not None
            ):
                raise ValueError("legacy-missing row projection cannot retain coordinates")
        else:
            raise ValueError("row projection availability must be available, unavailable, or legacy-missing")
        if self.action is True and not self.hard_valid:
            raise ValueError("scoreable actions must be hard-valid")
        if self.selected is True and self.action is False:
            raise ValueError("selected candidates must be scoreable actions")
        for value in (
            self.proposal_probability,
            self.view_jitter_yaw_deg,
            self.view_jitter_pitch_deg,
            self.view_jitter_azimuth_limit_deg,
            self.view_jitter_elevation_limit_deg,
        ):
            if value is not None and not math.isfinite(value):
                raise ValueError("candidate proposal and jitter values must be finite")
        if (
            self.view_jitter_azimuth_limit_deg is not None
            and self.view_jitter_azimuth_limit_deg < 0.0
            or self.view_jitter_elevation_limit_deg is not None
            and self.view_jitter_elevation_limit_deg < 0.0
        ):
            raise ValueError("candidate jitter limits must be non-negative")
        availability_fields = (
            self.world_pose_availability,
            self.projection_availability,
            self.semantic_lineage_availability,
            self.action_availability,
            self.selection_availability,
            self.proposal_key_availability,
            self.proposal_probability_availability,
            self.jitter_availability,
            self.admission_availability,
            self.generation_frame_availability,
            self.legacy_family_label_availability,
            self.legacy_admission_availability,
            self.legacy_pair_lineage_availability,
        )
        if any(not isinstance(value, CandidateFactAvailability) for value in availability_fields):
            raise ValueError("candidate evidence availability must use the closed enum")
        if (self.action is not None) != (self.action_availability is CandidateFactAvailability.AVAILABLE):
            raise ValueError("action availability must agree with the action value")
        if (self.selected is not None) != (self.selection_availability is CandidateFactAvailability.AVAILABLE):
            raise ValueError("selection availability must agree with the selected value")
        if (self.proposal_key is not None) != (self.proposal_key_availability is CandidateFactAvailability.AVAILABLE):
            raise ValueError("proposal-key availability must agree with the key value")
        if (self.proposal_probability is not None) != (
            self.proposal_probability_availability is CandidateFactAvailability.AVAILABLE
        ):
            raise ValueError("proposal-probability availability must agree with the value")
        jitter = (
            self.view_jitter_yaw_deg,
            self.view_jitter_pitch_deg,
            self.view_jitter_is_bounded,
            self.view_jitter_azimuth_limit_deg,
            self.view_jitter_elevation_limit_deg,
        )
        if (all(value is not None for value in jitter)) != (
            self.jitter_availability is CandidateFactAvailability.AVAILABLE
        ):
            raise ValueError("jitter availability must agree with the complete jitter bundle")
        required_semantic_values = (
            self.semantic_group_id,
            self.center_family_id,
            self.gaze_family_id,
            self.candidate_family_id,
            self.center_id,
            self.attempt_round_id,
            self.draw_id,
        )
        paired = self.position_pair_id is not None or self.gaze_variant_id is not None
        if paired != (self.position_pair_id is not None and self.gaze_variant_id is not None):
            raise ValueError("canonical pair and gaze-variant identities must be both present or both inapplicable")
        integer_lineage = (
            self.center_id,
            self.position_pair_id,
            self.gaze_variant_id,
            self.attempt_round_id,
            self.draw_id,
        )
        if any(value is not None and value < 0 for value in integer_lineage):
            raise ValueError("canonical lineage identities must be non-negative")
        has_semantic = any(
            value is not None for value in (*required_semantic_values, self.position_pair_id, self.gaze_variant_id)
        )
        if self.semantic_lineage_availability is CandidateFactAvailability.AVAILABLE:
            if not all(value is not None for value in required_semantic_values):
                raise ValueError("available semantic lineage requires all non-pair semantic identities")
        elif self.semantic_lineage_availability is CandidateFactAvailability.LEGACY_MISSING:
            if has_semantic:
                raise ValueError("legacy-missing semantic lineage cannot retain canonical identities")
        elif self.semantic_lineage_availability is CandidateFactAvailability.PARTIAL:
            if not has_semantic or all(value is not None for value in required_semantic_values):
                raise ValueError("partial semantic lineage requires an incomplete nonempty identity set")
        else:
            raise ValueError("semantic lineage must be available, partial, or legacy-missing")
        legacy_pair = self.legacy_position_pair_id is not None or self.legacy_gaze_variant_id is not None
        if legacy_pair != (self.legacy_position_pair_id is not None and self.legacy_gaze_variant_id is not None):
            raise ValueError("legacy pair and gaze-variant identities must be both present or both absent")
        if any(
            value is not None and value < 0 for value in (self.legacy_position_pair_id, self.legacy_gaze_variant_id)
        ):
            raise ValueError("legacy pair/gaze identities must be non-negative")
        if legacy_pair != (self.legacy_pair_lineage_availability is CandidateFactAvailability.AVAILABLE):
            if not (
                not legacy_pair
                and self.legacy_pair_lineage_availability
                in {
                    CandidateFactAvailability.INAPPLICABLE,
                    CandidateFactAvailability.UNAVAILABLE,
                    CandidateFactAvailability.LEGACY_MISSING,
                    CandidateFactAvailability.PARTIAL,
                }
            ):
                raise ValueError("legacy pair-lineage availability must agree with retained values")
        if (self.legacy_family_label is not None) != (
            self.legacy_family_label_availability is CandidateFactAvailability.AVAILABLE
        ):
            raise ValueError("legacy family-label availability must agree with its value")
        if (self.target_frame_identity is not None) != (
            self.generation_frame_availability is CandidateFactAvailability.AVAILABLE
        ):
            raise ValueError("generation-frame availability must agree with its identity")
        if self.admission_availability is CandidateFactAvailability.AVAILABLE and any(
            not criterion.available for criterion in self.admission
        ):
            raise ValueError("available admission evidence cannot contain unavailable criterion rows")
        has_legacy_admission = (
            self.legacy_invalid_reason_bitset is not None
            or self.legacy_primary_invalid_reason is not None
            or bool(self.legacy_admission_measurements)
        )
        if has_legacy_admission != (
            self.legacy_admission_availability
            in {CandidateFactAvailability.AVAILABLE, CandidateFactAvailability.PARTIAL}
        ):
            raise ValueError("legacy admission availability must agree with retained reason and measurement facts")


@dataclass(frozen=True, slots=True)
class CandidateEvidenceSnapshot:
    """Canonical immutable candidate evidence shared by all presentation leaves.

    The live and stored adapters construct this exact class from already
    acquired evidence. It owns no generator, reader, Plotly figure, or mutable
    tensor and therefore cannot regenerate candidates or reacquire geometry.
    """

    schema_revision: Literal["candidate-evidence-snapshot-v1"]
    """Closed snapshot schema revision."""

    state_key: str
    """Stable direct or rollout factual-state identity."""

    rows: tuple[CandidateEvidenceRow, ...]
    """Attempted candidate rows ordered on ``N``."""

    completion_mode: str | None
    """Score-independent completion algorithm identity, or ``None`` when missing."""

    attempted_count: int
    """Full attempted shell width ``N``."""

    valid_count: int
    """Hard-valid row count ``V``."""

    action_count: int | None
    """Scoreable action count ``A``, or ``None`` when legacy rows lack it."""

    selected_count: int | None
    """Selected row count, or ``None`` when no selection evidence was supplied."""

    projection_frame_identity: str | None
    """Inspection-owned target-relative projection identity, or ``None``."""

    target_target_normalized: tuple[float, float, float] | None
    """Observed target centre in normalized target axes, when available."""

    candidate_program_hash: str | None
    """Immutable candidate-program digest, or ``None`` for legacy stored evidence."""

    request_binding_hash: str | None
    """Immutable request digest, or ``None`` for legacy stored evidence."""

    execution_hash: str | None
    """Execution/config lineage digest supplied by persistence, when available."""

    overlay: CandidateRolloutOverlay
    """Optional rollout-owned horizon/step/budget facts."""

    completion_availability: CandidateFactAvailability
    """Availability/source state of completion identity and counts."""

    projection_frame_availability: CandidateFactAvailability
    """Availability/source state of canonical target-relative projection."""

    projection_unavailable_reason: CandidateProjectionUnavailableReason | None
    """Typed support failure; ``None`` exactly when projection is available."""

    program_hash_availability: CandidateFactAvailability
    """Availability/source state of ``candidate_program_hash``."""

    request_hash_availability: CandidateFactAvailability
    """Availability/source state of ``request_binding_hash``."""

    execution_hash_availability: CandidateFactAvailability
    """Availability/source state of ``execution_hash``."""

    def __post_init__(self) -> None:
        if self.schema_revision != "candidate-evidence-snapshot-v1":
            raise ValueError("candidate evidence snapshot revision is unsupported")
        if not self.state_key:
            raise ValueError("candidate evidence state key is required")
        availability_fields = (
            self.completion_availability,
            self.projection_frame_availability,
            self.program_hash_availability,
            self.request_hash_availability,
            self.execution_hash_availability,
        )
        if any(not isinstance(value, CandidateFactAvailability) for value in availability_fields):
            raise ValueError("snapshot availability must use the closed enum")
        if tuple(row.attempted_index for row in self.rows) != tuple(range(len(self.rows))):
            raise ValueError("candidate evidence rows must be ordered densely on N")
        action_values = tuple(row.action for row in self.rows)
        derived_action_count = (
            None
            if any(value is None for value in action_values) or not action_values and self.action_count is None
            else sum(bool(value) for value in action_values)
        )
        selection_values = tuple(row.selected for row in self.rows)
        derived_selected_count = (
            None
            if any(value is None for value in selection_values) or not selection_values and self.selected_count is None
            else sum(bool(value) for value in selection_values)
        )
        counts = (
            len(self.rows),
            sum(row.hard_valid for row in self.rows),
            derived_action_count,
            derived_selected_count,
        )
        if counts != (self.attempted_count, self.valid_count, self.action_count, self.selected_count):
            raise ValueError("candidate evidence counts disagree with row facts")
        identities = {row.target_frame_identity for row in self.rows if row.target_frame_identity is not None}
        if len(identities) > 1:
            raise ValueError("candidate evidence must use at most one generation target-frame identity")
        if self.target_target_normalized is not None and (
            len(self.target_target_normalized) != 3
            or not all(math.isfinite(value) for value in self.target_target_normalized)
        ):
            raise ValueError("normalized target centre must be a finite 3-vector")
        if (self.completion_mode is None) != (self.completion_availability is not CandidateFactAvailability.AVAILABLE):
            raise ValueError("completion availability must agree with completion_mode")
        row_projection = tuple(row.projection_availability for row in self.rows)
        if self.projection_frame_availability is CandidateFactAvailability.AVAILABLE:
            if (
                self.projection_frame_identity is None
                or self.target_target_normalized is None
                or self.projection_unavailable_reason is not None
                or any(value is not CandidateFactAvailability.AVAILABLE for value in row_projection)
            ):
                raise ValueError("available projection requires complete frame and row coordinates")
        elif self.projection_frame_availability is CandidateFactAvailability.PARTIAL:
            if (
                self.projection_frame_identity is None
                or self.target_target_normalized is None
                or self.projection_unavailable_reason is not None
                or not any(value is CandidateFactAvailability.UNAVAILABLE for value in row_projection)
            ):
                raise ValueError("partial projection requires a frame and mixed available/unavailable rows")
        elif self.projection_frame_availability is CandidateFactAvailability.UNAVAILABLE:
            if (
                self.projection_frame_identity is not None
                or self.target_target_normalized is not None
                or self.projection_unavailable_reason is None
                or any(value is not CandidateFactAvailability.UNAVAILABLE for value in row_projection)
            ):
                raise ValueError("unavailable projection requires one typed failure and no coordinates")
        elif self.projection_frame_availability is CandidateFactAvailability.LEGACY_MISSING:
            if (
                self.projection_frame_identity is not None
                or self.target_target_normalized is not None
                or self.projection_unavailable_reason is not None
                or any(value is not CandidateFactAvailability.LEGACY_MISSING for value in row_projection)
            ):
                raise ValueError("legacy-missing projection cannot retain frame facts")
        else:
            raise ValueError("projection availability must be available, unavailable, or legacy-missing")
        for value, availability, label in (
            (self.candidate_program_hash, self.program_hash_availability, "program hash"),
            (self.request_binding_hash, self.request_hash_availability, "request hash"),
            (self.execution_hash, self.execution_hash_availability, "execution hash"),
        ):
            if (value is not None) != (availability is CandidateFactAvailability.AVAILABLE):
                raise ValueError(f"{label} availability must agree with its value")

    @property
    def source_sha256(self) -> str:
        """Return a collision-resistant digest of immutable snapshot facts."""

        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class _CompleteStoredCandidateTransport:
    """Internal contract-complete byte payload expected from the PR5 codec."""

    canonical_json: bytes


def _wire_optional_tuple3(value: object) -> tuple[float, float, float] | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("stored candidate vector must have three elements")
    numbers = tuple(_wire_required_float(item) for item in value)
    return numbers[0], numbers[1], numbers[2]


def _wire_required_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("stored candidate integer fact has an invalid type")
    return value


def _wire_required_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("stored candidate floating fact has an invalid type")
    return float(value)


def _wire_required_bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError("stored candidate boolean fact has an invalid type")
    return value


def _wire_optional_int(value: object) -> int | None:
    return None if value is None else _wire_required_int(value)


def _wire_optional_float(value: object) -> float | None:
    return None if value is None else _wire_required_float(value)


def _wire_optional_bool(value: object) -> bool | None:
    return None if value is None else _wire_required_bool(value)


def _wire_optional_str(value: object) -> str | None:
    if value is not None and not isinstance(value, str):
        raise ValueError("stored candidate string fact has an invalid type")
    return value


def _wire_availability(value: object) -> CandidateFactAvailability:
    if not isinstance(value, str):
        raise ValueError("stored candidate availability has an invalid type")
    return CandidateFactAvailability(value)


def _wire_projection_reason(value: object) -> CandidateProjectionUnavailableReason | None:
    if value is not None and not isinstance(value, str):
        raise ValueError("stored projection reason has an invalid type")
    return None if value is None else CandidateProjectionUnavailableReason(value)


def _decode_criterion_wire(value: object) -> CandidateCriterionSnapshot:
    row = cast(dict[str, object], value)
    return CandidateCriterionSnapshot(
        criterion_id=str(row["criterion_id"]),
        cumulative_valid=_wire_required_bool(row["cumulative_valid"]),
        available=_wire_required_bool(row["available"]),
        applicable=_wire_optional_bool(row["applicable"]),
        evaluated=_wire_optional_bool(row["evaluated"]),
        passed=_wire_optional_bool(row["passed"]),
        reason_code=_wire_optional_int(row["reason_code"]),
        margin=_wire_optional_float(row["margin"]),
        source_role=_wire_optional_int(row["source_role"]),
        reason_revision=str(row["reason_revision"]),
        source_role_revision=str(row["source_role_revision"]),
    )


def _decode_candidate_row_wire(value: object) -> CandidateEvidenceRow:
    row = cast(dict[str, object], value)
    legacy_measurements = tuple(
        (str(item[0]), _wire_required_float(item[1]))
        for item in cast(list[list[object]], row["legacy_admission_measurements"])
    )
    return CandidateEvidenceRow(
        attempted_index=_wire_required_int(row["attempted_index"]),
        candidate_id=_wire_optional_int(row["candidate_id"]),
        center_world_m=_wire_optional_tuple3(row["center_world_m"]),
        world_pose_availability=_wire_availability(row["world_pose_availability"]),
        world_pose_unavailable_reason=_wire_projection_reason(row["world_pose_unavailable_reason"]),
        center_target_normalized=_wire_optional_tuple3(row["center_target_normalized"]),
        gaze_target_unit=_wire_optional_tuple3(row["gaze_target_unit"]),
        projection_availability=_wire_availability(row["projection_availability"]),
        projection_unavailable_reason=_wire_projection_reason(row["projection_unavailable_reason"]),
        hard_valid=_wire_required_bool(row["hard_valid"]),
        action=_wire_optional_bool(row["action"]),
        selected=_wire_optional_bool(row["selected"]),
        semantic_group_id=_wire_optional_str(row["semantic_group_id"]),
        center_family_id=_wire_optional_str(row["center_family_id"]),
        gaze_family_id=_wire_optional_str(row["gaze_family_id"]),
        candidate_family_id=_wire_optional_str(row["candidate_family_id"]),
        legacy_family_label=_wire_optional_str(row["legacy_family_label"]),
        legacy_invalid_reason_bitset=_wire_optional_int(row["legacy_invalid_reason_bitset"]),
        legacy_primary_invalid_reason=_wire_optional_str(row["legacy_primary_invalid_reason"]),
        legacy_admission_measurements=legacy_measurements,
        center_id=_wire_optional_int(row["center_id"]),
        position_pair_id=_wire_optional_int(row["position_pair_id"]),
        gaze_variant_id=_wire_optional_int(row["gaze_variant_id"]),
        legacy_position_pair_id=_wire_optional_int(row["legacy_position_pair_id"]),
        legacy_gaze_variant_id=_wire_optional_int(row["legacy_gaze_variant_id"]),
        attempt_round_id=_wire_optional_int(row["attempt_round_id"]),
        draw_id=_wire_optional_int(row["draw_id"]),
        proposal_key=_wire_optional_str(row["proposal_key"]),
        proposal_probability=_wire_optional_float(row["proposal_probability"]),
        view_jitter_yaw_deg=_wire_optional_float(row["view_jitter_yaw_deg"]),
        view_jitter_pitch_deg=_wire_optional_float(row["view_jitter_pitch_deg"]),
        view_jitter_is_bounded=_wire_optional_bool(row["view_jitter_is_bounded"]),
        view_jitter_azimuth_limit_deg=_wire_optional_float(row["view_jitter_azimuth_limit_deg"]),
        view_jitter_elevation_limit_deg=_wire_optional_float(row["view_jitter_elevation_limit_deg"]),
        target_frame_identity=_wire_optional_str(row["target_frame_identity"]),
        admission=tuple(_decode_criterion_wire(item) for item in cast(list[object], row["admission"])),
        semantic_lineage_availability=_wire_availability(row["semantic_lineage_availability"]),
        action_availability=_wire_availability(row["action_availability"]),
        selection_availability=_wire_availability(row["selection_availability"]),
        proposal_key_availability=_wire_availability(row["proposal_key_availability"]),
        proposal_probability_availability=_wire_availability(row["proposal_probability_availability"]),
        jitter_availability=_wire_availability(row["jitter_availability"]),
        admission_availability=_wire_availability(row["admission_availability"]),
        generation_frame_availability=_wire_availability(row["generation_frame_availability"]),
        legacy_family_label_availability=_wire_availability(row["legacy_family_label_availability"]),
        legacy_admission_availability=_wire_availability(row["legacy_admission_availability"]),
        legacy_pair_lineage_availability=_wire_availability(row["legacy_pair_lineage_availability"]),
    )


def _candidate_evidence_snapshot_from_complete_stored(
    transport: _CompleteStoredCandidateTransport,
) -> CandidateEvidenceSnapshot:
    """Decode and validate a contract-complete PR5-shaped byte transport."""

    payload = cast(dict[str, object], json.loads(transport.canonical_json))
    if payload.get("schema_revision") != "candidate-evidence-snapshot-v1":
        raise ValueError("stored candidate evidence revision is unsupported")
    overlay = cast(dict[str, object], payload["overlay"])
    return CandidateEvidenceSnapshot(
        schema_revision="candidate-evidence-snapshot-v1",
        state_key=str(payload["state_key"]),
        rows=tuple(_decode_candidate_row_wire(item) for item in cast(list[object], payload["rows"])),
        completion_mode=_wire_optional_str(payload["completion_mode"]),
        attempted_count=int(cast(int, payload["attempted_count"])),
        valid_count=int(cast(int, payload["valid_count"])),
        action_count=_wire_optional_int(payload["action_count"]),
        selected_count=_wire_optional_int(payload["selected_count"]),
        projection_frame_identity=_wire_optional_str(payload["projection_frame_identity"]),
        target_target_normalized=_wire_optional_tuple3(payload["target_target_normalized"]),
        candidate_program_hash=_wire_optional_str(payload["candidate_program_hash"]),
        request_binding_hash=_wire_optional_str(payload["request_binding_hash"]),
        execution_hash=_wire_optional_str(payload["execution_hash"]),
        overlay=CandidateRolloutOverlay(
            horizon=_wire_optional_int(overlay["horizon"]),
            factual_step=_wire_optional_int(overlay["factual_step"]),
            remaining_budget=_wire_optional_int(overlay["remaining_budget"]),
            history_coverage=_wire_optional_int(overlay["history_coverage"]),
        ),
        completion_availability=_wire_availability(payload["completion_availability"]),
        projection_frame_availability=_wire_availability(payload["projection_frame_availability"]),
        projection_unavailable_reason=_wire_projection_reason(payload["projection_unavailable_reason"]),
        program_hash_availability=_wire_availability(payload["program_hash_availability"]),
        request_hash_availability=_wire_availability(payload["request_hash_availability"]),
        execution_hash_availability=_wire_availability(payload["execution_hash_availability"]),
    )


def candidate_evidence_snapshot_from_live(
    candidate_set: CandidateSet,
    *,
    selected_attempt_indices: Iterable[int] | None = None,
    state_key: str | None = None,
    overlay: CandidateRolloutOverlay | None = None,
    execution_hash: str | None = None,
) -> CandidateEvidenceSnapshot:
    """Freeze one live ``CandidateSet`` without geometry reacquisition.

    Tensor values cross to CPU exactly once at this explicit inspection
    boundary. The adapter uses only the immutable candidate table, admission,
    completion, and selection projection supplied by upstream owners.
    """

    from aria_nbv.geometry import TargetRelativeFrame, TargetRelativeFrameDegeneracyError
    from aria_nbv.pose_generation import CandidateSet
    from aria_nbv.pose_generation.candidate_interface import EvidenceAvailability

    if not isinstance(candidate_set, CandidateSet):
        raise TypeError("candidate_set must be CandidateSet")
    selected = None if selected_attempt_indices is None else frozenset(int(index) for index in selected_attempt_indices)
    n = candidate_set.completion.attempted_count
    if selected is not None and any(index < 0 or index >= n for index in selected):
        raise ValueError("selected attempted indices must index N")
    action_indices = tuple(int(value) for value in candidate_set.action_indices.detach().cpu().tolist())
    action_set = frozenset(action_indices)
    if selected is not None and not selected.issubset(action_set):
        raise ValueError("selected candidates must be scoreable actions")
    table = candidate_set.attempts
    centers = table.centers_world.detach().to(device="cpu", dtype=torch.float64)
    gaze = table.gaze_directions_world.detach().to(device="cpu", dtype=torch.float64)
    world_poses = (
        cast(_TensorContainer, table.world_poses).tensor().reshape(n, 12).detach().to(device="cpu", dtype=torch.float64)
    )
    finite_pose = (
        torch.isfinite(world_poses).all(dim=1) & torch.isfinite(centers).all(dim=1) & torch.isfinite(gaze).all(dim=1)
    )
    valid = candidate_set.admission.mask_valid.detach().cpu()
    reference_tensor = (
        cast(_TensorContainer, table.reference_pose_world)
        .tensor()
        .reshape(-1, 12)
        .detach()
        .to(device="cpu", dtype=torch.float64)
    )
    origin = reference_tensor[0, 9:12]
    target_frame: TargetRelativeFrame | None = None
    projection_unavailable_reason: CandidateProjectionUnavailableReason | None = None
    anchors = table.target_anchor_world.detach().to(device="cpu", dtype=torch.float64)
    finite_anchors = torch.isfinite(anchors).all(dim=1)
    all_finite = bool(finite_anchors.all().item())
    anchors_agree = n > 0 and bool((anchors == anchors[:1]).all().item())
    if all_finite and anchors_agree:
        target = anchors[0]
        generation_frame_identities = {
            identity
            for identity, availability in zip(table.target_frame_identity, table.target_frame_availability, strict=True)
            if availability is EvidenceAvailability.AVAILABLE
        }
        if len(generation_frame_identities) > 1:
            raise ValueError("candidate generation target-frame identities disagree across N")
        projection_frame_identity = _candidate_projection_frame_identity(origin, target)
        try:
            target_frame = TargetRelativeFrame.from_origin_target(
                origin,
                target,
                frame_identity=projection_frame_identity,
            )
        except TargetRelativeFrameDegeneracyError:
            target_frame = None
            projection_unavailable_reason = CandidateProjectionUnavailableReason.DEGENERATE_TARGET_BEARING
    elif not all_finite:
        projection_unavailable_reason = CandidateProjectionUnavailableReason.TARGET_MISSING
    else:
        projection_unavailable_reason = CandidateProjectionUnavailableReason.TARGET_ANCHOR_MISMATCH
    normalized_centers = target_frame.world_to_frame_points(centers) if target_frame is not None else None
    target_gaze = target_frame.world_to_frame_vectors(gaze) if target_frame is not None else None
    normalized_target = target_frame.world_to_frame_points(target) if target_frame is not None else None
    criterion_axes = []
    for criterion in candidate_set.admission.criteria:
        local = criterion.local
        criterion_axes.append(
            (
                criterion,
                criterion.legacy_cumulative_valid.detach().cpu(),
                criterion.local_availability.detach().cpu(),
                None
                if local is None
                else tuple(
                    value.detach().cpu()
                    for value in (
                        local.applicable,
                        local.evaluated,
                        local.passed,
                        local.reason_code,
                        local.margin,
                        local.source_role,
                    )
                ),
            )
        )
    criteria_by_row: list[tuple[CandidateCriterionSnapshot, ...]] = []
    for index in range(n):
        criteria: list[CandidateCriterionSnapshot] = []
        for criterion, cumulative_cpu, availability_cpu, local_cpu in criterion_axes:
            local_available = bool(availability_cpu[index])
            criteria.append(
                CandidateCriterionSnapshot(
                    criterion_id=criterion.criterion_id,
                    cumulative_valid=bool(cumulative_cpu[index]),
                    available=local_available and local_cpu is not None,
                    applicable=(bool(local_cpu[0][index]) if local_available and local_cpu else None),
                    evaluated=(bool(local_cpu[1][index]) if local_available and local_cpu else None),
                    passed=(bool(local_cpu[2][index]) if local_available and local_cpu else None),
                    reason_code=(int(local_cpu[3][index]) if local_available and local_cpu else None),
                    margin=(float(local_cpu[4][index]) if local_available and local_cpu else None),
                    source_role=(int(local_cpu[5][index]) if local_available and local_cpu else None),
                    reason_revision=criterion.reason_revision.value,
                    source_role_revision=criterion.source_role_revision.value,
                )
            )
        criteria_by_row.append(tuple(criteria))

    def vector(values: torch.Tensor, index: int) -> tuple[float, float, float]:
        row = values[index].tolist()
        return float(row[0]), float(row[1]), float(row[2])

    def integers(values: torch.Tensor) -> tuple[int, ...]:
        return tuple(int(value) for value in values.detach().cpu().tolist())

    center_ids = integers(table.center_id)
    raw_pair_ids = integers(table.position_pair_id)
    raw_variant_ids = integers(table.gaze_variant_id)
    if any(
        not ((pair_id == -1 and variant_id == -1) or (pair_id >= 0 and variant_id >= 0))
        for pair_id, variant_id in zip(raw_pair_ids, raw_variant_ids, strict=True)
    ):
        raise ValueError("candidate pair/gaze lineage must be paired or jointly inapplicable")
    pair_ids = tuple(None if value < 0 else value for value in raw_pair_ids)
    variant_ids = tuple(None if value < 0 else value for value in raw_variant_ids)
    round_ids = integers(table.attempt_round_id)
    draw_ids = integers(table.draw_id)
    probabilities = tuple(float(value) for value in table.proposal_probability.detach().cpu().tolist())
    yaw = tuple(float(value) for value in table.view_residual_yaw_deg.detach().cpu().tolist())
    pitch = tuple(float(value) for value in table.view_residual_pitch_deg.detach().cpu().tolist())
    bounded = tuple(bool(value) for value in table.view_jitter_is_bounded.detach().cpu().tolist())
    yaw_limits = tuple(float(value) for value in table.view_jitter_azimuth_limit_deg.detach().cpu().tolist())
    pitch_limits = tuple(float(value) for value in table.view_jitter_elevation_limit_deg.detach().cpu().tolist())
    finite_pose_values = tuple(bool(value) for value in finite_pose.tolist())
    rows = tuple(
        CandidateEvidenceRow(
            attempted_index=index,
            candidate_id=None,
            center_world_m=(vector(centers, index) if finite_pose_values[index] else None),
            world_pose_availability=(
                CandidateFactAvailability.AVAILABLE
                if finite_pose_values[index]
                else CandidateFactAvailability.UNAVAILABLE
            ),
            world_pose_unavailable_reason=(
                None if finite_pose_values[index] else CandidateProjectionUnavailableReason.POSE_NONFINITE
            ),
            center_target_normalized=(
                vector(normalized_centers, index)
                if normalized_centers is not None and finite_pose_values[index]
                else None
            ),
            gaze_target_unit=(
                vector(target_gaze, index) if target_gaze is not None and finite_pose_values[index] else None
            ),
            projection_availability=(
                CandidateFactAvailability.AVAILABLE
                if target_frame is not None and finite_pose_values[index]
                else CandidateFactAvailability.UNAVAILABLE
            ),
            projection_unavailable_reason=(
                None
                if target_frame is not None and finite_pose_values[index]
                else CandidateProjectionUnavailableReason.POSE_NONFINITE
                if not finite_pose_values[index]
                else projection_unavailable_reason
            ),
            hard_valid=bool(valid[index].item()),
            action=index in action_set,
            selected=(None if selected is None else index in selected),
            semantic_group_id=table.semantic_group_id[index],
            center_family_id=table.center_family_id[index],
            gaze_family_id=table.gaze_family_id[index],
            candidate_family_id=table.candidate_family_id[index],
            legacy_family_label=None,
            legacy_invalid_reason_bitset=None,
            legacy_primary_invalid_reason=None,
            legacy_admission_measurements=(),
            center_id=center_ids[index],
            position_pair_id=pair_ids[index],
            gaze_variant_id=variant_ids[index],
            legacy_position_pair_id=None,
            legacy_gaze_variant_id=None,
            attempt_round_id=round_ids[index],
            draw_id=draw_ids[index],
            proposal_key=table.proposal_key[index],
            proposal_probability=probabilities[index],
            view_jitter_yaw_deg=yaw[index],
            view_jitter_pitch_deg=pitch[index],
            view_jitter_is_bounded=bounded[index],
            view_jitter_azimuth_limit_deg=yaw_limits[index],
            view_jitter_elevation_limit_deg=pitch_limits[index],
            target_frame_identity=(
                table.target_frame_identity[index]
                if table.target_frame_availability[index] is EvidenceAvailability.AVAILABLE
                else None
            ),
            admission=criteria_by_row[index],
            semantic_lineage_availability=CandidateFactAvailability.AVAILABLE,
            action_availability=CandidateFactAvailability.AVAILABLE,
            selection_availability=(
                CandidateFactAvailability.UNAVAILABLE if selected is None else CandidateFactAvailability.AVAILABLE
            ),
            proposal_key_availability=CandidateFactAvailability.AVAILABLE,
            proposal_probability_availability=CandidateFactAvailability.AVAILABLE,
            jitter_availability=CandidateFactAvailability.AVAILABLE,
            admission_availability=(
                CandidateFactAvailability.AVAILABLE
                if all(criterion.available for criterion in criteria_by_row[index])
                else CandidateFactAvailability.PARTIAL
            ),
            generation_frame_availability=(
                CandidateFactAvailability.AVAILABLE
                if table.target_frame_availability[index] is EvidenceAvailability.AVAILABLE
                else CandidateFactAvailability.UNAVAILABLE
            ),
            legacy_family_label_availability=CandidateFactAvailability.UNAVAILABLE,
            legacy_admission_availability=CandidateFactAvailability.UNAVAILABLE,
            legacy_pair_lineage_availability=CandidateFactAvailability.UNAVAILABLE,
        )
        for index in range(n)
    )
    projection_frame_identity = target_frame.frame_identity if target_frame is not None else None
    return CandidateEvidenceSnapshot(
        "candidate-evidence-snapshot-v1",
        state_key or f"direct:{candidate_set.request_binding_hash}",
        rows,
        candidate_set.completion.mode.value,
        n,
        candidate_set.completion.valid_count,
        len(action_indices),
        (None if selected is None else len(selected)),
        projection_frame_identity,
        (vector(normalized_target.reshape(1, 3), 0) if normalized_target is not None else None),
        candidate_set.candidate_program_hash,
        candidate_set.request_binding_hash,
        execution_hash,
        overlay or CandidateRolloutOverlay.unavailable(),
        CandidateFactAvailability.AVAILABLE,
        (
            CandidateFactAvailability.AVAILABLE
            if target_frame is not None and all(finite_pose_values)
            else CandidateFactAvailability.PARTIAL
            if target_frame is not None
            else CandidateFactAvailability.UNAVAILABLE
        ),
        projection_unavailable_reason,
        CandidateFactAvailability.AVAILABLE,
        CandidateFactAvailability.AVAILABLE,
        (CandidateFactAvailability.AVAILABLE if execution_hash is not None else CandidateFactAvailability.UNAVAILABLE),
    )


def _validate_stored_step_axes(step: StoredStep) -> None:
    """Fail closed on one current-schema stored shell before frame derivation."""

    aligned = (
        step.candidate_row_positions,
        step.candidate_row_ids,
        step.shell_indices,
        step.compact_valid_indices,
        step.actor_action_mask,
        step.selected_mask,
        step.target_rri,
        step.target_root_gain,
        step.scene_rri,
        step.selection_probabilities,
        step.mixture_ids,
        step.mixture_names,
        step.gaze_variant_ids,
        step.position_pair_ids,
        step.sampler_probabilities,
        step.position_ids,
        step.position_names,
        step.invalid_reason_bitsets,
        step.primary_invalid_reason_ids,
        step.primary_invalid_reason_names,
        step.mesh_distance_m,
        step.path_min_clearance_m,
        step.motion_step_length_m,
        step.target_distance_m,
    )
    optional_aligned = (
        step.view_jitter_yaw_deg,
        step.view_jitter_pitch_deg,
        step.view_jitter_azimuth_limit_deg,
        step.view_jitter_elevation_limit_deg,
        step.view_jitter_is_bounded,
    )
    poses = np.asarray(step.pose_world_cam).reshape(-1, 12)
    if (
        poses.shape != (step.num_candidates, 12)
        or any(np.asarray(axis).reshape(-1).size != step.num_candidates for axis in aligned)
        or any(
            axis is not None and np.asarray(axis).reshape(-1).size != step.num_candidates for axis in optional_aligned
        )
    ):
        raise ValueError("stored candidate arrays must align exactly over N")
    hard_valid = np.asarray(step.compact_valid_indices).reshape(-1) >= 0
    actions = np.asarray(step.actor_action_mask, dtype=np.bool_).reshape(-1)
    selected = np.asarray(step.selected_mask, dtype=np.bool_).reshape(-1)
    if not np.all(~actions | hard_valid) or not np.all(~selected | actions):
        raise ValueError("stored candidate action/selection masks violate subset invariants")
    compact = np.asarray(step.compact_valid_indices, dtype=np.int64).reshape(-1)
    expected_compact = np.full(step.num_candidates, -1, dtype=np.int64)
    expected_compact[hard_valid] = np.arange(int(hard_valid.sum()), dtype=np.int64)
    if not np.array_equal(compact, expected_compact) or step.num_valid_candidates != int(hard_valid.sum()):
        raise ValueError("stored compact-valid projection must be dense and agree with V")
    selected_positions = np.flatnonzero(selected)
    if selected_positions.size != 1:
        raise ValueError("stored current step must contain exactly one selected action")
    expected_selected_local = int(selected_positions[0])
    expected_selected_id = int(step.candidate_row_ids[expected_selected_local])
    if step.selected_local_index != expected_selected_local or step.selected_candidate_row_id != expected_selected_id:
        raise ValueError("stored selected identity must agree with the selected mask")


def candidate_evidence_snapshot_from_stored(
    rollout: StoredRollout,
    step: StoredStep,
    target: StoredTarget,
    *,
    previous_step: StoredStep | None = None,
) -> CandidateEvidenceSnapshot:
    """Freeze one already-acquired stored shell without reader or config access.

    The adapter derives the factual expansion frame from the rollout root at
    ``t=0`` or the previous selected pose at later steps. Current stores carry
    hard-valid/action/selection, raw poses, legacy admission diagnostics, and
    view jitter. Canonical semantic lineage, criterion-local admission,
    completion, and binding hashes remain explicitly ``LEGACY_MISSING`` until
    the PR5 persistence migration.
    """

    from aria_nbv.geometry import TargetRelativeFrame, TargetRelativeFrameDegeneracyError

    if step.rollout_row_id != rollout.rollout_row_id or target.target_row_id != rollout.target_row_id:
        raise ValueError("stored rollout, step, and target identities must agree")
    _validate_stored_step_axes(step)
    if step.step_index == 0:
        origin = torch.as_tensor(rollout.root_pose_world, dtype=torch.float64).reshape(12)[9:12]
    else:
        if (
            previous_step is None
            or previous_step.step_index != step.step_index - 1
            or previous_step.rollout_row_id != rollout.rollout_row_id
        ):
            raise ValueError("later stored steps require the immediately previous factual step")
        _validate_stored_step_axes(previous_step)
        selected_positions = np.flatnonzero(previous_step.selected_mask)
        selected_position = int(selected_positions[0])
        if previous_step.selected_local_index != selected_position or previous_step.selected_candidate_row_id != int(
            previous_step.candidate_row_ids[selected_position]
        ):
            raise ValueError("previous stored selection identity disagrees with its selected mask")
        origin = torch.as_tensor(previous_step.pose_world_cam[selected_position], dtype=torch.float64).reshape(12)[9:12]
    target_world = torch.as_tensor(target.center_world, dtype=torch.float64).reshape(3)
    frame_identity = _candidate_projection_frame_identity(origin, target_world)
    target_frame: TargetRelativeFrame | None = None
    normalized_target: tuple[float, float, float] | None = None
    projection_unavailable_reason: CandidateProjectionUnavailableReason | None = None
    try:
        target_frame = TargetRelativeFrame.from_origin_target(
            origin,
            target_world,
            frame_identity=frame_identity,
        )
    except TargetRelativeFrameDegeneracyError:
        target_frame = None
        projection_unavailable_reason = CandidateProjectionUnavailableReason.DEGENERATE_TARGET_BEARING
    else:
        target_values = target_frame.world_to_frame_points(target_world).tolist()
        normalized_target = float(target_values[0]), float(target_values[1]), float(target_values[2])
    poses = torch.as_tensor(step.pose_world_cam, dtype=torch.float64).reshape(-1, 12)
    centers = poses[:, 9:12]
    gaze_world = poses[:, :9].reshape(-1, 3, 3)[:, :, 2]
    finite_pose = (
        torch.isfinite(poses).all(dim=1) & torch.isfinite(centers).all(dim=1) & torch.isfinite(gaze_world).all(dim=1)
    )
    finite_pose_values = tuple(bool(value) for value in finite_pose.tolist())
    normalized_centers = target_frame.world_to_frame_points(centers) if target_frame is not None else None
    normalized_gaze = target_frame.world_to_frame_vectors(gaze_world) if target_frame is not None else None
    hard_valid = np.asarray(step.compact_valid_indices).reshape(-1) >= 0
    actions = np.asarray(step.actor_action_mask, dtype=np.bool_).reshape(-1)
    selected = np.asarray(step.selected_mask, dtype=np.bool_).reshape(-1)

    def vector(values: torch.Tensor, index: int) -> tuple[float, float, float]:
        row = values[index].tolist()
        return float(row[0]), float(row[1]), float(row[2])

    def stored_row(index: int) -> CandidateEvidenceRow:
        probability = _finite_or_none(step.sampler_probabilities[index])
        jitter, jitter_availability = _stored_jitter_bundle(step, index)
        measurements = tuple(
            sorted(
                (name, value)
                for name, raw in (
                    ("mesh_distance_m", step.mesh_distance_m[index]),
                    ("motion_step_length_m", step.motion_step_length_m[index]),
                    ("path_min_clearance_m", step.path_min_clearance_m[index]),
                    ("target_distance_m", step.target_distance_m[index]),
                )
                if (value := _finite_or_none(raw)) is not None
            )
        )
        raw_pair_id = int(step.position_pair_ids[index])
        raw_variant_id = int(step.gaze_variant_ids[index])
        legacy_pair_availability = (
            CandidateFactAvailability.LEGACY_MISSING
            if not step.position_pair_ids_persisted and not step.gaze_variant_ids_persisted
            else CandidateFactAvailability.PARTIAL
            if not step.position_pair_ids_persisted or not step.gaze_variant_ids_persisted
            else CandidateFactAvailability.INAPPLICABLE
            if raw_pair_id < 0 and raw_variant_id < 0
            else CandidateFactAvailability.AVAILABLE
            if raw_pair_id >= 0 and raw_variant_id >= 0
            else CandidateFactAvailability.PARTIAL
        )
        if legacy_pair_availability is CandidateFactAvailability.PARTIAL and (
            step.position_pair_ids_persisted and step.gaze_variant_ids_persisted
        ):
            raise ValueError("stored pair/gaze lineage must be jointly present or jointly inapplicable")
        return CandidateEvidenceRow(
            attempted_index=index,
            candidate_id=int(step.candidate_row_ids[index]),
            center_world_m=(vector(centers, index) if finite_pose_values[index] else None),
            world_pose_availability=(
                CandidateFactAvailability.AVAILABLE
                if finite_pose_values[index]
                else CandidateFactAvailability.UNAVAILABLE
            ),
            world_pose_unavailable_reason=(
                None if finite_pose_values[index] else CandidateProjectionUnavailableReason.POSE_NONFINITE
            ),
            center_target_normalized=(
                vector(normalized_centers, index)
                if normalized_centers is not None and finite_pose_values[index]
                else None
            ),
            gaze_target_unit=(
                vector(normalized_gaze, index) if normalized_gaze is not None and finite_pose_values[index] else None
            ),
            projection_availability=(
                CandidateFactAvailability.AVAILABLE
                if target_frame is not None and finite_pose_values[index]
                else CandidateFactAvailability.UNAVAILABLE
            ),
            projection_unavailable_reason=(
                None
                if target_frame is not None and finite_pose_values[index]
                else CandidateProjectionUnavailableReason.POSE_NONFINITE
                if not finite_pose_values[index]
                else projection_unavailable_reason
            ),
            hard_valid=bool(hard_valid[index]),
            action=bool(actions[index]),
            selected=bool(selected[index]),
            semantic_group_id=None,
            center_family_id=None,
            gaze_family_id=None,
            candidate_family_id=None,
            legacy_family_label=str(step.mixture_names[index]),
            legacy_invalid_reason_bitset=int(step.invalid_reason_bitsets[index]),
            legacy_primary_invalid_reason=str(step.primary_invalid_reason_names[index]),
            legacy_admission_measurements=measurements,
            center_id=None,
            position_pair_id=None,
            gaze_variant_id=None,
            legacy_position_pair_id=(
                raw_pair_id if legacy_pair_availability is CandidateFactAvailability.AVAILABLE else None
            ),
            legacy_gaze_variant_id=(
                raw_variant_id if legacy_pair_availability is CandidateFactAvailability.AVAILABLE else None
            ),
            attempt_round_id=None,
            draw_id=None,
            proposal_key=None,
            proposal_probability=probability,
            view_jitter_yaw_deg=(None if jitter is None else jitter[0]),
            view_jitter_pitch_deg=(None if jitter is None else jitter[1]),
            view_jitter_is_bounded=(None if jitter is None else jitter[2]),
            view_jitter_azimuth_limit_deg=(None if jitter is None else jitter[3]),
            view_jitter_elevation_limit_deg=(None if jitter is None else jitter[4]),
            target_frame_identity=None,
            admission=(),
            semantic_lineage_availability=CandidateFactAvailability.LEGACY_MISSING,
            action_availability=CandidateFactAvailability.AVAILABLE,
            selection_availability=CandidateFactAvailability.AVAILABLE,
            proposal_key_availability=CandidateFactAvailability.LEGACY_MISSING,
            proposal_probability_availability=(
                CandidateFactAvailability.AVAILABLE
                if probability is not None
                else CandidateFactAvailability.UNAVAILABLE
            ),
            jitter_availability=jitter_availability,
            admission_availability=CandidateFactAvailability.LEGACY_MISSING,
            generation_frame_availability=CandidateFactAvailability.LEGACY_MISSING,
            legacy_family_label_availability=CandidateFactAvailability.AVAILABLE,
            legacy_admission_availability=(
                CandidateFactAvailability.AVAILABLE if len(measurements) == 4 else CandidateFactAvailability.PARTIAL
            ),
            legacy_pair_lineage_availability=legacy_pair_availability,
        )

    evidence_rows = tuple(stored_row(index) for index in range(step.num_candidates))
    return CandidateEvidenceSnapshot(
        "candidate-evidence-snapshot-v1",
        f"rollout:{rollout.rollout_row_id}/step:{step.step_row_id}",
        evidence_rows,
        None,
        len(evidence_rows),
        sum(row.hard_valid for row in evidence_rows),
        sum(bool(row.action) for row in evidence_rows),
        sum(bool(row.selected) for row in evidence_rows),
        frame_identity if target_frame is not None else None,
        normalized_target,
        None,
        None,
        None,
        CandidateRolloutOverlay(
            horizon=rollout.horizon,
            factual_step=step.step_index,
            remaining_budget=rollout.horizon - step.step_index,
            history_coverage=step.step_index,
        ),
        CandidateFactAvailability.PARTIAL,
        (
            CandidateFactAvailability.AVAILABLE
            if target_frame is not None and all(finite_pose_values)
            else CandidateFactAvailability.PARTIAL
            if target_frame is not None
            else CandidateFactAvailability.UNAVAILABLE
        ),
        projection_unavailable_reason,
        CandidateFactAvailability.LEGACY_MISSING,
        CandidateFactAvailability.LEGACY_MISSING,
        CandidateFactAvailability.LEGACY_MISSING,
    )


def _candidate_projection_frame_identity(origin: torch.Tensor, target: torch.Tensor) -> str:
    """Bind the canonical inspection frame to float64 origin/target values."""

    payload = torch.cat((origin.reshape(3), target.reshape(3))).numpy().astype("<f8", copy=False).tobytes()
    return f"target-relative-z-up-v1:{hashlib.sha256(payload).hexdigest()}"


def _stored_jitter_bundle(
    step: StoredStep,
    index: int,
) -> tuple[tuple[float, float, bool, float, float] | None, CandidateFactAvailability]:
    """Return one finite persisted jitter bundle and its typed availability."""

    arrays = (
        step.view_jitter_yaw_deg,
        step.view_jitter_pitch_deg,
        step.view_jitter_azimuth_limit_deg,
        step.view_jitter_elevation_limit_deg,
    )
    all_arrays = (*arrays, step.view_jitter_is_bounded)
    if all(array is None for array in all_arrays):
        return None, CandidateFactAvailability.LEGACY_MISSING
    if any(array is None for array in all_arrays):
        return None, CandidateFactAvailability.PARTIAL
    floats = tuple(_finite_or_none(cast(np.ndarray, array)[index]) for array in arrays)
    if any(value is None for value in floats):
        return None, CandidateFactAvailability.UNAVAILABLE
    yaw, pitch, azimuth, elevation = cast(tuple[float, float, float, float], floats)
    return (
        (yaw, pitch, bool(cast(np.ndarray, step.view_jitter_is_bounded)[index]), azimuth, elevation),
        CandidateFactAvailability.AVAILABLE,
    )


__all__ = [
    "CandidateCriterionSnapshot",
    "CandidateEvidenceRow",
    "CandidateEvidenceSnapshot",
    "CandidateFactAvailability",
    "CandidateProjectionUnavailableReason",
    "CandidateRolloutOverlay",
    "candidate_evidence_snapshot_from_live",
    "candidate_evidence_snapshot_from_stored",
]
