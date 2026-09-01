"""Static typing contract for canonical candidate evidence and plot models.

Run with ``uv run mypy tests/rollouts/public_api_typing_contract.py``.
"""

from typing import assert_type

from aria_nbv.pose_generation import CandidateSet
from aria_nbv.rollouts.candidate_plotting import CandidatePlotModel, candidate_support_plot_models
from aria_nbv.rollouts.inspection import (
    CandidateEvidenceSnapshot,
    CandidateRolloutOverlay,
    candidate_evidence_snapshot_from_live,
    candidate_evidence_snapshot_from_stored,
)
from aria_nbv.rollouts.read_model import StoredRollout, StoredStep, StoredTarget


def verify_candidate_evidence_contract(
    candidate_set: CandidateSet,
    rollout: StoredRollout,
    step: StoredStep,
    target: StoredTarget,
) -> None:
    """Prove public adapters and plot builders retain precise result types."""

    live = candidate_evidence_snapshot_from_live(candidate_set, overlay=CandidateRolloutOverlay.unavailable())
    stored = candidate_evidence_snapshot_from_stored(rollout, step, target)
    assert_type(live, CandidateEvidenceSnapshot)
    assert_type(stored, CandidateEvidenceSnapshot)
    models = candidate_support_plot_models((live, stored))
    assert_type(models, tuple[CandidatePlotModel, CandidatePlotModel, CandidatePlotModel, CandidatePlotModel])
