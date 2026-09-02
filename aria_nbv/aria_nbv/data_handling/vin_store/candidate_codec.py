"""Versioned optional candidate-fact codec for immutable VIN records.

The legacy ``oracle.candidates`` record remains byte-for-byte owned by
``CandidateSamplingResult``. This module adds a separate lazy audit record over
the frozen candidate interface; it never enters actor or training tensors.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

import torch

if TYPE_CHECKING:
    from ...pose_generation import CandidateSet

VIN_CANDIDATE_FACTS_CODEC_VERSION = "vin-candidate-facts-v1"
"""Closed layout and validation revision for ``oracle.candidate_facts``."""


@dataclass(frozen=True, slots=True)
class VinCandidateCriterionFacts:
    """One criterion's immutable ``N``-aligned VIN audit projection.

    Attributes:
        criterion_id: Stable nonempty criterion identity.
        cumulative_valid: Legacy cumulative validity over attempted rows.
        local_available: Whether criterion-local evidence exists per row.
        applicable: Optional local applicability axis; false when unavailable.
        evaluated: Optional local evaluation axis; implies applicability.
        passed: Optional local pass axis; equivalent to reason code ``0``.
        reason_code: Closed candidate-admission reason codes, or ``-1`` sentinel.
        margin: Criterion-owned scalar margin and units; NaN when unavailable.
        source_role: Closed actor/oracle role codes, or ``-1`` sentinel.
        reason_revision: Version governing reason-code meaning.
        source_role_revision: Version governing source-role meaning.
    """

    criterion_id: str
    """Stable nonempty criterion identity, unique within one payload."""
    cumulative_valid: tuple[bool, ...]
    """Cumulative legacy validity axis ``bool[N]``."""
    local_available: tuple[bool, ...]
    """Criterion-local evidence availability axis ``bool[N]``."""
    applicable: tuple[bool, ...] | None
    """Applicability ``bool[N]``; absent with the complete local bundle."""
    evaluated: tuple[bool, ...] | None
    """Evaluation state ``bool[N]``; a subset of applicability."""
    passed: tuple[bool, ...] | None
    """Pass state ``bool[N]``; a subset of evaluation."""
    reason_code: tuple[int, ...] | None
    """Closed admission reasons ``int64[N]``; ``-1`` means unevaluated."""
    margin: tuple[float, ...] | None
    """Criterion-owned-unit margins ``float32[N]``; NaN when unavailable."""
    source_role: tuple[int, ...] | None
    """Audit source-role codes ``int64[N]``; never actor input."""
    reason_revision: str
    """Closed semantic revision governing ``reason_code``."""
    source_role_revision: str
    """Closed semantic revision governing ``source_role``."""

    def __post_init__(self) -> None:
        n = len(self.cumulative_valid)
        if type(self.criterion_id) is not str or not self.criterion_id or len(self.local_available) != n:
            raise ValueError("VIN criterion identity and availability must align over N.")
        local = (self.applicable, self.evaluated, self.passed, self.reason_code, self.margin, self.source_role)
        if any(value is None for value in local) != all(value is None for value in local):
            raise ValueError("VIN criterion local facts must be all present or all absent.")
        if any(type(value) is not bool for value in (*self.cumulative_valid, *self.local_available)):
            raise ValueError("VIN criterion validity and availability must contain booleans.")
        if self.applicable is None:
            if any(self.local_available):
                raise ValueError("Absent VIN criterion-local facts cannot be marked available.")
        else:
            if any(len(value) != n for value in local if value is not None):
                raise ValueError("VIN criterion-local axes must align over N.")
            if self.evaluated is None or self.passed is None:
                raise ValueError("VIN criterion local boolean axes must be present together.")
            if any(
                type(value) is not bool for axis in (self.applicable, self.evaluated, self.passed) for value in axis
            ):
                raise ValueError("VIN criterion local state axes must contain booleans.")
            if self.reason_code is None or self.source_role is None or self.margin is None:
                raise ValueError("VIN criterion local scalar axes must be present together.")
            if any(
                isinstance(value, bool) or not isinstance(value, int)
                for value in (*self.reason_code, *self.source_role)
            ):
                raise ValueError("VIN criterion reason/source axes must contain exact integers.")
            if any(value not in range(-1, 8) for value in self.reason_code) or any(
                value not in {-1, 1, 2} for value in self.source_role
            ):
                raise ValueError("VIN criterion reason/source axes contain undeclared codes.")
            for index, (available, margin) in enumerate(zip(self.local_available, self.margin, strict=True)):
                if isinstance(margin, bool) or not isinstance(margin, float):
                    raise ValueError("VIN criterion margins must contain floats.")
                if available and not math.isfinite(margin):
                    raise ValueError("Available VIN criterion margins must be finite.")
                if not available and (
                    self.applicable[index]
                    or self.evaluated[index]
                    or self.passed[index]
                    or self.reason_code[index] != -1
                    or self.source_role[index] != -1
                    or math.isfinite(margin)
                ):
                    raise ValueError("Unavailable VIN criterion rows must use codec sentinels.")
            if any(
                evaluated and not applicable
                for applicable, evaluated in zip(self.applicable, self.evaluated, strict=True)
            ):
                raise ValueError("VIN criterion evaluated rows must be applicable.")
            if any(passed and not evaluated for evaluated, passed in zip(self.evaluated, self.passed, strict=True)):
                raise ValueError("VIN criterion passed rows must be evaluated.")
            if any(
                available and (passed != (reason == 0))
                for available, passed, reason in zip(
                    self.local_available,
                    self.passed,
                    self.reason_code,
                    strict=True,
                )
            ):
                raise ValueError("VIN criterion passed rows must use the PASSED reason code exactly.")
            if any(
                available and ((not evaluated) != (reason == -1))
                for available, evaluated, reason in zip(
                    self.local_available,
                    self.evaluated,
                    self.reason_code,
                    strict=True,
                )
            ):
                raise ValueError("VIN criterion unevaluated rows must use the UNAVAILABLE reason exactly.")
        if (
            type(self.reason_revision) is not str
            or self.reason_revision
            not in {
                "unavailable_v1",
                "candidate_admission_v1",
            }
            or type(self.source_role_revision) is not str
            or self.source_role_revision
            not in {
                "unavailable_v1",
                "candidate_admission_v1",
            }
        ):
            raise ValueError("VIN criterion revisions are undeclared.")


@dataclass(frozen=True, slots=True)
class VinCandidateFacts:
    """Lazy VIN audit payload retaining the canonical N/V/A candidate facts.

    This DTO is not part of :class:`VinOracleBatch`; criterion source roles may
    include Oracle admission and therefore remain diagnostic-only.

    Attributes:
        codec_version: Closed VIN candidate payload revision.
        attempted_count: Full attempted shell width ``N``.
        valid_count: Ordered hard-valid projection width ``V``.
        action_count: Ordered actor-action projection width ``A``.
        labeled_prefix_count: Rendered training-label prefix within ``V``.
        valid_indices: Ordered shell indices ``tuple[int, V]``.
        action_indices: Ordered shell indices ``tuple[int, A]``, a subset of V.
        semantic_group_id: N-row semantic group identities.
        center_family_id: N-row positional-family identities.
        gaze_family_id: N-row gaze-family identities.
        candidate_family_id: N-row combined candidate-family identities.
        center_id: Non-negative shared-center IDs over N.
        position_pair_id: Non-negative pair IDs, or exact ``-1`` inapplicable sentinel.
        gaze_variant_id: Non-negative gaze IDs paired with `position_pair_id`, or ``-1``.
        attempt_round_id: Non-negative completion-round IDs over N.
        draw_id: Non-negative within-round draw IDs over N.
        proposal_key: N-row semantic random-draw identities.
        target_frame_identity: N-row generation-frame identities; empty when unavailable.
        target_frame_availability: N-row ``available``/``unavailable`` values.
        criteria: Ordered immutable audit criteria aligned over N.
        candidate_program_hash: Lowercase SHA-256 of the canonical program.
        request_binding_hash: Lowercase SHA-256 of the bound request.
        candidate_substream_revision: Closed sampling-substream revision.
        action_order_revision: Closed action-order revision.
        completion_mode: Closed completion-policy identity.
        proposal_key_revision: Composition-owned proposal revision, when available.
        proposal_replica: Non-negative composition-owned replica paired with its revision.
        legacy_candidate_config_hash: Independent legacy config identity for dual-write.
    """

    codec_version: str
    """Closed layout revision for the optional VIN audit record."""
    attempted_count: int
    """Attempted-shell cardinality ``N``."""
    valid_count: int
    """Ordered hard-valid cardinality ``V``."""
    action_count: int
    """Ordered actor-action cardinality ``A``, with ``A <= V <= N``."""
    labeled_prefix_count: int
    """Training-label prefix length within ordered ``V``."""
    valid_indices: tuple[int, ...]
    """Ordered shell projection ``int64[V]`` into ``N``."""
    action_indices: tuple[int, ...]
    """Ordered shell projection ``int64[A]``, a subset of ``valid_indices``."""
    semantic_group_id: tuple[str, ...]
    """Stable semantic center-group identities ``str[N]``."""
    center_family_id: tuple[str, ...]
    """Stable center-family identities ``str[N]``."""
    gaze_family_id: tuple[str, ...]
    """Stable gaze-family identities ``str[N]``."""
    candidate_family_id: tuple[str, ...]
    """Stable combined candidate-family identities ``str[N]``."""
    center_id: tuple[int, ...]
    """Non-negative shared-center lineage ``int64[N]``."""
    position_pair_id: tuple[int, ...]
    """Pair lineage ``int64[N]``; exact ``-1`` means inapplicable."""
    gaze_variant_id: tuple[int, ...]
    """Gaze-variant lineage ``int64[N]``; paired exact ``-1`` sentinel."""
    attempt_round_id: tuple[int, ...]
    """Non-negative completion-round lineage ``int64[N]``."""
    draw_id: tuple[int, ...]
    """Non-negative within-round draw lineage ``int64[N]``."""
    proposal_key: tuple[str, ...]
    """Semantic random-draw identities ``str[N]``."""
    target_frame_identity: tuple[str, ...]
    """Generation-frame identities ``str[N]``; empty only when unavailable."""
    target_frame_availability: tuple[str, ...]
    """Closed target-frame availability values ``str[N]``."""
    criteria: tuple[VinCandidateCriterionFacts, ...]
    """Ordered immutable admission audit criteria, each aligned to ``N``."""
    candidate_program_hash: str
    """Lowercase SHA-256 binding the frozen candidate program."""
    request_binding_hash: str
    """Lowercase SHA-256 binding the generation request and scene."""
    candidate_substream_revision: str
    """Closed sampling-substream revision."""
    action_order_revision: str
    """Closed action-projection ordering revision."""
    completion_mode: str
    """Closed candidate completion policy identity."""
    proposal_key_revision: str | None
    """Composition-owned proposal revision, jointly optional with replica."""
    proposal_replica: int | None
    """Non-negative composition-owned replica, jointly optional with revision."""
    legacy_candidate_config_hash: str | None
    """Independent legacy candidate-config identity for dual-write audit."""

    def __post_init__(self) -> None:
        n = self.attempted_count
        if (
            self.codec_version != VIN_CANDIDATE_FACTS_CODEC_VERSION
            or isinstance(n, bool)
            or not isinstance(n, int)
            or n < 0
        ):
            raise ValueError("Unsupported or invalid VIN candidate-facts codec.")
        axes = (
            self.semantic_group_id,
            self.center_family_id,
            self.gaze_family_id,
            self.candidate_family_id,
            self.center_id,
            self.position_pair_id,
            self.gaze_variant_id,
            self.attempt_round_id,
            self.draw_id,
            self.proposal_key,
            self.target_frame_identity,
            self.target_frame_availability,
        )
        if any(len(axis) != n for axis in axes):
            raise ValueError("VIN candidate-fact axes must align over N.")
        for name, count in (
            ("valid_count", self.valid_count),
            ("action_count", self.action_count),
            ("labeled_prefix_count", self.labeled_prefix_count),
        ):
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError(f"VIN {name} must be a non-negative integer.")
        if self.valid_count != len(self.valid_indices) or self.action_count != len(self.action_indices):
            raise ValueError("VIN candidate V/A counts must agree with explicit indices.")
        if self.labeled_prefix_count > self.valid_count:
            raise ValueError("VIN labeled prefix cannot exceed V.")
        for name, indices in (("valid", self.valid_indices), ("action", self.action_indices)):
            if any(isinstance(index, bool) or not isinstance(index, int) for index in indices):
                raise ValueError(f"VIN {name} indices must contain exact integers.")
            if len(set(indices)) != len(indices) or any(index < 0 or index >= n for index in indices):
                raise ValueError(f"VIN {name} indices must uniquely reference N.")
        if not set(self.action_indices).issubset(self.valid_indices):
            raise ValueError("VIN action indices must be a subset of valid indices.")
        if len({criterion.criterion_id for criterion in self.criteria}) != len(self.criteria):
            raise ValueError("VIN criterion identities must be unique.")
        if any(len(criterion.cumulative_valid) != n for criterion in self.criteria):
            raise ValueError("VIN criteria must align over N.")
        for axis in (self.center_id, self.position_pair_id, self.gaze_variant_id, self.attempt_round_id, self.draw_id):
            if any(isinstance(value, bool) or not isinstance(value, int) for value in axis):
                raise ValueError("VIN lineage axes must contain exact integers.")
        if any(value < 0 for axis in (self.center_id, self.attempt_round_id, self.draw_id) for value in axis):
            raise ValueError("VIN center, round, and draw identities must be non-negative.")
        if any(
            not ((pair_id == -1 and variant_id == -1) or (pair_id >= 0 and variant_id >= 0))
            for pair_id, variant_id in zip(self.position_pair_id, self.gaze_variant_id, strict=True)
        ):
            raise ValueError("VIN pair/gaze identities must be jointly non-negative or exactly -1.")
        if self.criteria:
            previous = (True,) * n
            for criterion in self.criteria:
                if any(
                    current and not prior for prior, current in zip(previous, criterion.cumulative_valid, strict=True)
                ):
                    raise ValueError("VIN cumulative admission masks must be monotone.")
                if criterion.evaluated is not None and criterion.passed is not None:
                    expected = tuple(
                        prior and ((not evaluated) or passed)
                        for prior, evaluated, passed in zip(
                            previous,
                            criterion.evaluated,
                            criterion.passed,
                            strict=True,
                        )
                    )
                    if any(
                        available and current != expected_value
                        for available, current, expected_value in zip(
                            criterion.local_available,
                            criterion.cumulative_valid,
                            expected,
                            strict=True,
                        )
                    ):
                        raise ValueError("VIN cumulative admission mask contradicts local criterion evidence.")
                previous = criterion.cumulative_valid
            valid_index_set = set(self.valid_indices)
            expected_valid = tuple(index in valid_index_set for index in range(n))
            if previous != expected_valid:
                raise ValueError("VIN terminal cumulative admission mask must equal V.")
        if any(type(value) is not str or not value for axis in axes[:4] + (self.proposal_key,) for value in axis):
            raise ValueError("VIN semantic and proposal identities must be nonempty.")
        if any(
            type(value) is not str or value not in {"available", "unavailable"}
            for value in self.target_frame_availability
        ):
            raise ValueError("VIN target-frame availability is undeclared.")
        if any(type(value) is not str for value in self.target_frame_identity):
            raise ValueError("VIN target-frame identities must contain strings.")
        if any(
            (availability == "available") != bool(identity)
            for identity, availability in zip(self.target_frame_identity, self.target_frame_availability, strict=True)
        ):
            raise ValueError("VIN target-frame identity must agree with row availability.")
        if (
            type(self.candidate_substream_revision) is not str
            or self.candidate_substream_revision != "shipped_mixture_seed_paths_v1"
        ):
            raise ValueError("VIN candidate substream revision is unsupported.")
        if (
            type(self.action_order_revision) is not str
            or type(self.completion_mode) is not str
            or self.action_order_revision != "ordered_hard_valid_v1"
            or self.completion_mode != "fixed_attempts"
        ):
            raise ValueError("VIN action/completion revisions are unsupported.")
        if (self.proposal_key_revision is None) != (self.proposal_replica is None):
            raise ValueError("VIN proposal revision and replica must be present together.")
        if self.proposal_replica is not None and (
            isinstance(self.proposal_replica, bool)
            or not isinstance(self.proposal_replica, int)
            or self.proposal_replica < 0
        ):
            raise ValueError("VIN proposal replica must be a non-negative integer.")
        if self.proposal_key_revision is not None and (
            type(self.proposal_key_revision) is not str or not self.proposal_key_revision
        ):
            raise ValueError("VIN proposal-key revision must be nonempty when available.")
        for digest in (self.candidate_program_hash, self.request_binding_hash):
            if type(digest) is not str or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError("VIN candidate hashes must be lowercase SHA-256 digests.")
        if self.legacy_candidate_config_hash is not None and (
            type(self.legacy_candidate_config_hash) is not str or not self.legacy_candidate_config_hash
        ):
            raise ValueError("VIN legacy candidate config hash must be nonempty when available.")

    def to_record(self) -> dict[str, Any]:
        """Return the msgspec-compatible lazy record representation."""

        return {
            name: ([asdict(criterion) for criterion in value] if name == "criteria" else value)
            for name, value in ((field, getattr(self, field)) for field in self.__dataclass_fields__)
        }

    @classmethod
    def from_record(cls, payload: dict[str, Any]) -> VinCandidateFacts:
        """Decode one exact-version record and reject missing or extra fields."""

        expected = set(cls.__dataclass_fields__)
        if set(payload) != expected:
            raise ValueError("VIN candidate-facts record fields do not match the declared codec.")
        criteria_payload = payload["criteria"]
        if not isinstance(criteria_payload, (list, tuple)):
            raise ValueError("VIN candidate criteria must be a sequence.")
        values = dict(payload)
        criterion_tuple_fields = {
            "cumulative_valid",
            "local_available",
            "applicable",
            "evaluated",
            "passed",
            "reason_code",
            "margin",
            "source_role",
        }
        decoded_criteria = []
        for raw_criterion in criteria_payload:
            if not isinstance(raw_criterion, dict):
                raise ValueError("VIN candidate criterion entries must be mappings.")
            criterion = dict(raw_criterion)
            if set(criterion) != set(VinCandidateCriterionFacts.__dataclass_fields__):
                raise ValueError("VIN candidate criterion fields do not match the declared codec.")
            for name in criterion_tuple_fields:
                if criterion[name] is not None:
                    if not isinstance(criterion[name], (list, tuple)):
                        raise ValueError(f"VIN criterion field {name!r} must be a sequence.")
                    criterion[name] = tuple(criterion[name])
            decoded_criteria.append(VinCandidateCriterionFacts(**criterion))
        values["criteria"] = tuple(decoded_criteria)
        tuple_fields = {
            "valid_indices",
            "action_indices",
            "semantic_group_id",
            "center_family_id",
            "gaze_family_id",
            "candidate_family_id",
            "center_id",
            "position_pair_id",
            "gaze_variant_id",
            "attempt_round_id",
            "draw_id",
            "proposal_key",
            "target_frame_identity",
            "target_frame_availability",
        }
        for name in tuple_fields:
            if not isinstance(values[name], (list, tuple)):
                raise ValueError(f"VIN candidate field {name!r} must be a sequence.")
            values[name] = tuple(values[name])
        return cls(**values)


def vin_candidate_facts(
    candidate_set: CandidateSet,
    *,
    proposal_key_revision: str | None = None,
    proposal_replica: int | None = None,
    legacy_candidate_config_hash: str | None = None,
    labeled_prefix_count: int | None = None,
) -> VinCandidateFacts:
    """Project one canonical candidate set into the VIN-owned lazy codec."""

    table = candidate_set.attempts
    candidate_set.validate_semantics()

    def values(tensor: torch.Tensor) -> tuple[Any, ...]:
        return tuple(tensor.detach().cpu().reshape(-1).tolist())

    criteria_values: list[VinCandidateCriterionFacts] = []
    for criterion in candidate_set.admission.criteria:
        availability = tuple(bool(value) for value in values(criterion.local_availability))
        local = criterion.local
        if local is None:
            applicable = evaluated = passed = reason_code = margin = source_role = None
        else:
            applicable = tuple(
                bool(value) if available else False
                for value, available in zip(values(local.applicable), availability, strict=True)
            )
            evaluated = tuple(
                bool(value) if available else False
                for value, available in zip(values(local.evaluated), availability, strict=True)
            )
            passed = tuple(
                bool(value) if available else False
                for value, available in zip(values(local.passed), availability, strict=True)
            )
            reason_code = tuple(
                int(value) if available else -1
                for value, available in zip(values(local.reason_code), availability, strict=True)
            )
            margin = tuple(
                float(value) if available else math.nan
                for value, available in zip(values(local.margin), availability, strict=True)
            )
            source_role = tuple(
                int(value) if available else -1
                for value, available in zip(values(local.source_role), availability, strict=True)
            )
        criteria_values.append(
            VinCandidateCriterionFacts(
                criterion_id=criterion.criterion_id,
                cumulative_valid=tuple(bool(value) for value in values(criterion.legacy_cumulative_valid)),
                local_available=availability,
                applicable=applicable,
                evaluated=evaluated,
                passed=passed,
                reason_code=reason_code,
                margin=margin,
                source_role=source_role,
                reason_revision=criterion.reason_revision.value,
                source_role_revision=criterion.source_role_revision.value,
            )
        )
    criteria = tuple(criteria_values)
    return VinCandidateFacts(
        codec_version=VIN_CANDIDATE_FACTS_CODEC_VERSION,
        attempted_count=candidate_set.completion.attempted_count,
        valid_count=candidate_set.completion.valid_count,
        action_count=int(candidate_set.action_indices.shape[0]),
        labeled_prefix_count=(
            candidate_set.completion.valid_count if labeled_prefix_count is None else labeled_prefix_count
        ),
        valid_indices=tuple(int(value) for value in values(candidate_set.valid_indices)),
        action_indices=tuple(int(value) for value in values(candidate_set.action_indices)),
        semantic_group_id=table.semantic_group_id,
        center_family_id=table.center_family_id,
        gaze_family_id=table.gaze_family_id,
        candidate_family_id=table.candidate_family_id,
        center_id=tuple(int(value) for value in values(table.center_id)),
        position_pair_id=tuple(int(value) for value in values(table.position_pair_id)),
        gaze_variant_id=tuple(int(value) for value in values(table.gaze_variant_id)),
        attempt_round_id=tuple(int(value) for value in values(table.attempt_round_id)),
        draw_id=tuple(int(value) for value in values(table.draw_id)),
        proposal_key=table.proposal_key,
        target_frame_identity=table.target_frame_identity,
        target_frame_availability=tuple(value.value for value in table.target_frame_availability),
        criteria=criteria,
        candidate_program_hash=candidate_set.candidate_program_hash,
        request_binding_hash=candidate_set.request_binding_hash,
        candidate_substream_revision=candidate_set.candidate_substream_revision.value,
        action_order_revision=candidate_set.action_order_revision.value,
        completion_mode=candidate_set.completion.mode.value,
        proposal_key_revision=proposal_key_revision,
        proposal_replica=proposal_replica,
        legacy_candidate_config_hash=legacy_candidate_config_hash,
    )


__all__ = [
    "VIN_CANDIDATE_FACTS_CODEC_VERSION",
    "VinCandidateCriterionFacts",
    "VinCandidateFacts",
    "vin_candidate_facts",
]
