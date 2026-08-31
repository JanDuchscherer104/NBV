"""Immutable, N-aligned hard-admission evidence assembly.

Numerical rules remain responsible for evaluating geometry. This module alone
turns their local rejection facts into cumulative validity, typed reasons,
source roles, and immutable candidate-interface evidence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import torch

from .candidate_errors import CandidateAlignmentCorruptionError
from .candidate_interface import (
    AdmissionEvidence,
    CriterionEvidence,
    CriterionLocalEvidence,
    CriterionReasonCode,
    CriterionReasonRevision,
    CriterionSourceRole,
    CriterionSourceRoleRevision,
)


@dataclass(frozen=True, slots=True)
class AdmissionCriterionOutcome:
    """One evaluated criterion before cross-variant concatenation."""

    criterion_id: str
    """Stable criterion identity owned by hard admission."""

    cumulative_valid: torch.Tensor
    """Cumulative validity ``Tensor["N", bool]`` after this criterion."""

    local: CriterionLocalEvidence
    """Criterion-local applicability, evaluation, reason, role, and margin."""

    local_availability: torch.Tensor
    """Availability ``Tensor["N", bool]`` for the complete local evidence row."""


def _compose_admission_criterion_outcome(
    *,
    criterion_id: str,
    previous_valid: torch.Tensor,
    applicable: torch.Tensor,
    evaluated: torch.Tensor,
    rejected: torch.Tensor,
    margin: torch.Tensor,
    failure_reason: CriterionReasonCode,
    source_role: CriterionSourceRole,
    local_availability: torch.Tensor | None = None,
) -> AdmissionCriterionOutcome:
    """Compose trusted rule output without synchronizing accelerator tensors.

    ``margin`` uses the uniform convention positive=inside the admissible set,
    zero=boundary, negative=violation. Rows that were not evaluated retain the
    unavailable reason code and never become newly invalid.

    Args:
        criterion_id: Stable criterion identity.
        previous_valid ``Tensor["N", bool]``: Cumulative input validity.
        applicable ``Tensor["N", bool]``: Rows to which the criterion applies.
        evaluated ``Tensor["N", bool]``: Rows evaluated by the backend.
        rejected ``Tensor["N", bool]``: Evaluated rows rejected here.
        margin ``Tensor["N", float]``: Signed criterion margin in the
            criterion's documented unit.
        failure_reason: Closed failure code assigned to rejected rows.
        source_role: Actor-visible or Oracle source role used for evaluation.
        local_availability ``Tensor["N", bool] | None``: Complete-row evidence
            availability; defaults to available for every row.

    Returns:
        Immutable criterion outcome aligned over the attempted shell.
    """

    n = previous_valid.numel()
    axes = (applicable, evaluated, rejected, margin)
    if any(axis.shape != (n,) or axis.device != previous_valid.device for axis in axes):
        raise CandidateAlignmentCorruptionError("Admission criterion inputs must align over one device.")
    if previous_valid.dtype is not torch.bool or any(axis.dtype is not torch.bool for axis in axes[:3]):
        raise CandidateAlignmentCorruptionError("Admission masks must be boolean.")
    if not margin.is_floating_point():
        raise CandidateAlignmentCorruptionError("Admission margins must be floating point.")
    cumulative = previous_valid & ~rejected
    passed = evaluated & ~rejected
    reason = torch.full((n,), int(CriterionReasonCode.UNAVAILABLE), device=previous_valid.device, dtype=torch.int64)
    reason[passed] = int(CriterionReasonCode.PASSED)
    reason[rejected] = int(failure_reason)
    roles = torch.full((n,), int(source_role), device=previous_valid.device, dtype=torch.int64)
    availability = torch.ones_like(previous_valid) if local_availability is None else local_availability
    return AdmissionCriterionOutcome(
        criterion_id=criterion_id,
        cumulative_valid=cumulative,
        local=CriterionLocalEvidence(
            applicable=applicable,
            evaluated=evaluated,
            passed=passed,
            reason_code=reason,
            margin=margin,
            source_role=roles,
        ),
        local_availability=availability,
    )


def admission_criterion_outcome(
    *,
    criterion_id: str,
    previous_valid: torch.Tensor,
    applicable: torch.Tensor,
    evaluated: torch.Tensor,
    rejected: torch.Tensor,
    margin: torch.Tensor,
    failure_reason: CriterionReasonCode,
    source_role: CriterionSourceRole,
    local_availability: torch.Tensor | None = None,
) -> AdmissionCriterionOutcome:
    """Cold diagnostic constructor for untrusted criterion-local evidence.

    This boundary performs value-level subset checks and may synchronize an
    accelerator. Production rules use the private composer because they own
    the masks by construction and must not introduce host/device transfers.
    """

    outcome = _compose_admission_criterion_outcome(
        criterion_id=criterion_id,
        previous_valid=previous_valid,
        applicable=applicable,
        evaluated=evaluated,
        rejected=rejected,
        margin=margin,
        failure_reason=failure_reason,
        source_role=source_role,
        local_availability=local_availability,
    )
    semantic_valid = ((~evaluated | applicable) & (~rejected | evaluated)).all()
    if not bool(semantic_valid.item()):
        raise CandidateAlignmentCorruptionError(
            "Admission evaluation must be applicable, and rejection must be evaluated."
        )
    return outcome


def _compose_admission_evidence(
    final_mask: torch.Tensor,
    outcomes_by_variant: tuple[tuple[AdmissionCriterionOutcome, ...], ...],
) -> AdmissionEvidence:
    """Concatenate trusted outcomes without value reductions or host syncs.

    Args:
        final_mask ``Tensor["N", bool]``: Final hard-valid candidate mask.
        outcomes_by_variant: Ordered criterion outcomes for each gaze variant.

    Returns:
        Frozen admission evidence with every tensor aligned over ``N`` rows.
    """

    if final_mask.ndim != 1 or final_mask.dtype is not torch.bool:
        raise CandidateAlignmentCorruptionError("Final admission mask must be 1-D boolean evidence.")
    if not outcomes_by_variant:
        return AdmissionEvidence(final_mask, ())
    criterion_order = tuple(outcome.criterion_id for outcome in outcomes_by_variant[0])
    if any(tuple(outcome.criterion_id for outcome in outcomes) != criterion_order for outcomes in outcomes_by_variant):
        raise CandidateAlignmentCorruptionError("Admission criteria must have one stable order across variants.")
    criteria: list[CriterionEvidence] = []
    for criterion_index, criterion_id in enumerate(criterion_order):
        outcomes = tuple(items[criterion_index] for items in outcomes_by_variant)
        criteria.append(
            CriterionEvidence(
                criterion_id=criterion_id,
                legacy_cumulative_valid=torch.cat(tuple(outcome.cumulative_valid for outcome in outcomes)),
                local=CriterionLocalEvidence(
                    applicable=torch.cat(tuple(outcome.local.applicable for outcome in outcomes)),
                    evaluated=torch.cat(tuple(outcome.local.evaluated for outcome in outcomes)),
                    passed=torch.cat(tuple(outcome.local.passed for outcome in outcomes)),
                    reason_code=torch.cat(tuple(outcome.local.reason_code for outcome in outcomes)),
                    margin=torch.cat(tuple(outcome.local.margin for outcome in outcomes)),
                    source_role=torch.cat(tuple(outcome.local.source_role for outcome in outcomes)),
                ),
                local_availability=torch.cat(tuple(outcome.local_availability for outcome in outcomes)),
                reason_revision=CriterionReasonRevision.CANDIDATE_ADMISSION_V1,
                source_role_revision=CriterionSourceRoleRevision.CANDIDATE_ADMISSION_V1,
            )
        )
    derived_final = criteria[-1].legacy_cumulative_valid if criteria else final_mask
    return AdmissionEvidence(derived_final, tuple(criteria))


def assemble_admission_evidence(
    final_mask: torch.Tensor,
    outcomes_by_variant: tuple[tuple[AdmissionCriterionOutcome, ...], ...],
) -> AdmissionEvidence:
    """Cold diagnostic assembly for untrusted admission evidence.

    Production generation calls the private composer, whose cumulative and
    passed masks are structurally derived by the admission owner. This public
    diagnostic verifies the complete semantic chain and may synchronize an
    accelerator.
    """

    evidence = _compose_admission_evidence(final_mask, outcomes_by_variant)
    previous = torch.ones_like(final_mask)
    semantic_valid = torch.ones((), device=final_mask.device, dtype=torch.bool)
    for criterion in evidence.criteria:
        local = criterion.local
        if local is None:
            semantic_valid &= torch.zeros((), device=final_mask.device, dtype=torch.bool)
            continue
        semantic_valid &= (
            (~local.evaluated | local.applicable)
            & (~local.passed | local.evaluated)
            & (~local.passed | (local.reason_code == int(CriterionReasonCode.PASSED)))
            & (local.passed | (local.reason_code != int(CriterionReasonCode.PASSED)))
            & (~criterion.legacy_cumulative_valid | previous)
        ).all()
        previous = criterion.legacy_cumulative_valid
    semantic_valid &= previous.eq(final_mask).all()
    if not bool(semantic_valid.item()):
        raise CandidateAlignmentCorruptionError(
            "Admission evidence must be monotone, semantically consistent, and end at final_mask."
        )
    return evidence


def derive_invalid_reason_evidence(
    *,
    valid_mask: torch.Tensor,
    cumulative_masks: Mapping[str, torch.Tensor],
    diagnostic_rejections: Mapping[str, torch.Tensor],
    pose_nonfinite: torch.Tensor,
    reason_codes: Mapping[str, int],
    rule_reason_codes: Mapping[str, int],
    diagnostic_reason_codes: Mapping[str, int],
    primary_reason_priority: Sequence[str],
) -> tuple[torch.Tensor, torch.Tensor]:
    """Derive the immutable invalidity bitset and one precedence-owned reason.

    Inputs are already projected onto one CPU boolean axis by the compatibility
    boundary. The algorithm preserves shipped cumulative-rule ordering and
    diagnostic precedence exactly while giving generation, inspection, and
    persistence one reason owner.

    Args:
        valid_mask ``Tensor["N", bool]``: Final actor-action validity.
        cumulative_masks: Ordered legacy cumulative rule masks over ``N``.
        diagnostic_rejections: Named hard rejection masks over ``N``.
        pose_nonfinite ``Tensor["N", bool]``: Non-finite pose rows.
        reason_codes: Persisted reason name-to-bit-position codec.
        rule_reason_codes: Legacy rule-to-reason mapping.
        diagnostic_reason_codes: Hard diagnostic-to-reason mapping.
        primary_reason_priority: Highest-to-lowest invalid-reason precedence.

    Returns:
        Tuple of invalid-reason bitset and primary reason code, both
        ``Tensor["N", int64]`` on CPU.
    """

    bitset = torch.zeros(valid_mask.shape, dtype=torch.int64)
    bitset[valid_mask] = 1 << reason_codes["VALID"]
    previous = torch.ones_like(valid_mask)
    for rule_name, current in cumulative_masks.items():
        if current.shape != valid_mask.shape:
            continue
        failed_here = previous & ~current
        reason_bit = rule_reason_codes.get(rule_name, reason_codes["SAMPLER_RULE_REJECTED"])
        bitset[failed_here] |= 1 << reason_bit
        previous = current
    for diagnostic_name, rejection in diagnostic_rejections.items():
        if rejection.shape != valid_mask.shape:
            continue
        bitset[rejection] |= 1 << diagnostic_reason_codes[diagnostic_name]
    bitset[pose_nonfinite] |= 1 << reason_codes["POSE_NONFINITE"]
    unresolved_invalid = (~valid_mask) & (bitset == 0)
    bitset[unresolved_invalid] = 1 << reason_codes["SAMPLER_RULE_REJECTED"]

    primary = torch.full(bitset.shape, reason_codes["SAMPLER_RULE_REJECTED"], dtype=torch.int64)
    primary[valid_mask] = reason_codes["VALID"]
    unresolved = ~valid_mask
    for reason_name in primary_reason_priority:
        reason_code = reason_codes[reason_name]
        has_reason = unresolved & ((bitset & (1 << reason_code)) != 0)
        primary[has_reason] = reason_code
        unresolved &= ~has_reason
    return bitset, primary


__all__ = [
    "AdmissionCriterionOutcome",
    "admission_criterion_outcome",
    "assemble_admission_evidence",
    "derive_invalid_reason_evidence",
]
