"""Retained candidate-evidence products for Streamlit presentation leaves.

This module is Streamlit-free.  It is the application boundary between
canonical rollout evidence and rerun-driven presentation: controllers acquire
and reduce evidence once, while panels only reconstruct the selected Plotly
figure from immutable bytes.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..pose_generation import CandidateSet
from ..rollouts.candidate_evidence import (
    CandidateEvidenceSnapshot,
    CandidateRolloutOverlay,
    candidate_evidence_snapshot_from_live,
)
from ..rollouts.candidate_plotting import CandidatePlotModel, candidate_support_plot_models

_CANDIDATE_PLOT_KEYS = (
    "candidate-ground-support",
    "candidate-support-3d",
    "candidate-family-survival",
    "candidate-view-jitter",
)


@dataclass(frozen=True, slots=True)
class CandidateEvidenceView:
    """One identity-bound candidate snapshot collection and retained plots.

    Attributes:
        source_identity: Stable request or persisted-store identity.  A view is
            stale as soon as its controller/session owner reports a different
            identity.
        snapshots: Immutable attempted-shell evidence in factual-state order.
        show_view_directions: Whether the retained models include optical-axis
            arrows.  This option is part of the acquisition identity.
        plot_models: Canonical plots for the retained option set.

    The view owns no readers, generators, configurations, or Streamlit state.
    Construct it once at an acquisition boundary and retain it per user.
    """

    source_identity: str
    snapshots: tuple[CandidateEvidenceSnapshot, ...]
    show_view_directions: bool
    plot_models: tuple[CandidatePlotModel, ...]

    def __post_init__(self) -> None:
        if not self.source_identity:
            raise ValueError("candidate evidence source_identity must be nonempty")
        if not self.snapshots:
            raise ValueError("candidate evidence view must retain at least one snapshot")
        if tuple(model.key for model in self.plot_models) != _CANDIDATE_PLOT_KEYS:
            raise ValueError("candidate evidence view must retain the four canonical plot models in order")
        expected_sources = tuple(
            dict.fromkeys(f"candidate-snapshot:{snapshot.source_sha256}" for snapshot in self.snapshots)
        )
        if any(model.figure.source_ids != expected_sources for model in self.plot_models):
            raise ValueError("candidate plot source identities must bind every retained snapshot")


@dataclass(frozen=True, slots=True)
class LiveCandidateEvidenceRequest:
    """Complete cache identity for one externally composed live candidate view.

    Attributes:
        request_binding_hash: Canonical request value binding from generation.
        selected_attempt_indices: Optional selected rows on the attempted ``N``
            axis, or ``None`` when selection is unavailable.
        execution_hash: Optional execution receipt supplied by composition.
        state_key: Optional direct or rollout factual-state identity.
        overlay: Optional rollout horizon/step/budget facts.
        show_view_directions: Whether the retained models contain gaze arrows.
    """

    request_binding_hash: str
    selected_attempt_indices: tuple[int, ...] | None
    execution_hash: str | None
    state_key: str | None
    overlay: CandidateRolloutOverlay | None
    show_view_directions: bool


def candidate_evidence_view_from_snapshots(
    snapshots: tuple[CandidateEvidenceSnapshot, ...],
    *,
    source_identity: str,
    show_view_directions: bool = False,
) -> CandidateEvidenceView:
    """Build one bounded presentation variant once from frozen snapshots."""

    return CandidateEvidenceView(
        source_identity=source_identity,
        snapshots=snapshots,
        show_view_directions=show_view_directions,
        plot_models=candidate_support_plot_models(snapshots, show_view_directions=show_view_directions),
    )


def candidate_evidence_view_from_live(
    candidate_set: CandidateSet,
    *,
    selected_attempt_indices: tuple[int, ...] | None = None,
    execution_hash: str | None = None,
    state_key: str | None = None,
    overlay: CandidateRolloutOverlay | None = None,
    show_view_directions: bool = False,
) -> CandidateEvidenceView:
    """Retain canonical live evidence supplied by its composition owner.

    This adapter deliberately accepts :class:`CandidateSet`, never the legacy
    ``CandidateSamplingResult``.  The caller remains responsible for truthful
    actor/scene/program composition; the app does not fabricate those facts.
    """

    snapshot = candidate_evidence_snapshot_from_live(
        candidate_set,
        selected_attempt_indices=selected_attempt_indices,
        execution_hash=execution_hash,
        state_key=state_key,
        overlay=overlay,
    )
    return candidate_evidence_view_from_snapshots(
        (snapshot,),
        source_identity=f"candidate-snapshot:{snapshot.source_sha256}:directions={int(show_view_directions)}",
        show_view_directions=show_view_directions,
    )


__all__ = [
    "CandidateEvidenceView",
    "LiveCandidateEvidenceRequest",
    "candidate_evidence_view_from_live",
    "candidate_evidence_view_from_snapshots",
]
