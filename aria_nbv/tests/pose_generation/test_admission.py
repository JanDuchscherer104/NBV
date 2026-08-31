"""Fail-closed invariants for immutable candidate-admission evidence."""

from __future__ import annotations

import pytest
import torch

from aria_nbv.pose_generation.admission import (
    AdmissionCriterionOutcome,
    admission_criterion_outcome,
    assemble_admission_evidence,
)
from aria_nbv.pose_generation.candidate_errors import CandidateAlignmentCorruptionError
from aria_nbv.pose_generation.candidate_interface import CriterionReasonCode, CriterionSourceRole


def _outcome(
    *,
    criterion_id: str = "support_envelope",
    previous: tuple[bool, ...] = (True, True),
    applicable: tuple[bool, ...] = (True, True),
    evaluated: tuple[bool, ...] = (True, True),
    rejected: tuple[bool, ...] = (False, True),
) -> AdmissionCriterionOutcome:
    return admission_criterion_outcome(
        criterion_id=criterion_id,
        previous_valid=torch.tensor(previous),
        applicable=torch.tensor(applicable),
        evaluated=torch.tensor(evaluated),
        rejected=torch.tensor(rejected),
        margin=torch.tensor((1.0, -1.0)),
        failure_reason=CriterionReasonCode.OUTSIDE_SUPPORT_ENVELOPE,
        source_role=CriterionSourceRole.ORACLE_ADMISSION,
    )


@pytest.mark.parametrize(
    ("applicable", "evaluated", "rejected"),
    [
        ((False, True), (True, True), (False, False)),
        ((True, True), (False, True), (True, False)),
    ],
)
def test_admission_outcome_rejects_contradictory_local_semantics(
    applicable: tuple[bool, ...],
    evaluated: tuple[bool, ...],
    rejected: tuple[bool, ...],
) -> None:
    with pytest.raises(CandidateAlignmentCorruptionError, match="evaluation must be applicable"):
        _outcome(applicable=applicable, evaluated=evaluated, rejected=rejected)


def test_admission_assembly_rejects_final_mask_drift() -> None:
    outcome = _outcome()

    with pytest.raises(CandidateAlignmentCorruptionError, match="end at final_mask"):
        assemble_admission_evidence(torch.tensor((True, True)), ((outcome,),))


def test_admission_assembly_rejects_nonmonotone_cumulative_masks() -> None:
    first = _outcome(previous=(True, True), rejected=(True, False))
    second = _outcome(criterion_id="endpoint_clearance", previous=(True, True), rejected=(False, False))

    with pytest.raises(CandidateAlignmentCorruptionError, match="monotone"):
        assemble_admission_evidence(torch.tensor((True, True)), ((first, second),))
