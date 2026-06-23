"""Structural scorer contract for VIN-compatible candidate models.

This module names the narrow interface that `aria_nbv.lightning.lit_module`
needs from a candidate scorer. The current implementation is
`aria_nbv.vin.model_v3.VinModelV3`, the seminar-era one-step RRI scorer. Future
target-conditioned myopic and finite-horizon scorers should implement the same
forward surface when they are trainable through the existing Lightning loss
path, or provide a separate Lightning module when their objective is no longer
CORAL-over-candidate rows.

The contract deliberately keeps rollout value targets out of
`aria_nbv.vin.types.VinPrediction`. Multi-step labels such as endpoint gain,
selected-transition returns, and hard valid-action masks belong to
`aria_nbv.rollouts` stores and metrics until a concrete Q_H scorer owns that
training objective.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, TypeAlias

from torch import Tensor

from .model_v3 import VinModelV3Config
from .types import EvlBackboneOutput, VinPrediction

if TYPE_CHECKING:
    from efm3d.aria.pose import PoseTW
    from pytorch3d.renderer.cameras import PerspectiveCameras

    from aria_nbv.data_handling import EfmSnippetView, VinSnippetView


class CandidateScorer(Protocol):
    """Protocol for trainable candidate scorers consumed by VIN Lightning.

    Implementations score each candidate pose row from actor-visible scene
    evidence and return a `aria_nbv.vin.types.VinPrediction`. The current
    Lightning objective also expects a CORAL head at ``head_coral`` so it can
    compute expected RRI proxies and initialize ordinal bin values.

    Implementers:
        `aria_nbv.vin.model_v3.VinModelV3` is the current one-step scorer.
        Future target-conditioned myopic scorers can satisfy this protocol when
        they still emit per-candidate ordinal logits. Finite-horizon Q_H models
        should only reuse it if their training objective remains row-local and
        compatible with `VinPrediction`.
    """

    head_coral: Any
    """CORAL head used for ordinal probability and expected-value helpers."""

    def forward(
        self,
        efm: EfmSnippetView | VinSnippetView,
        *,
        candidate_poses_world_cam: PoseTW,
        reference_pose_world_rig: PoseTW,
        p3d_cameras: PerspectiveCameras,
        backbone_out: EvlBackboneOutput | None = None,
    ) -> VinPrediction:
        """Score candidate poses for one actor-visible snippet.

        Args:
            efm: Actor-visible EFM/VIN snippet view containing semidense scene
                evidence.
            candidate_poses_world_cam: ``PoseTW["B C 12"]`` world←camera
                candidate poses.
            reference_pose_world_rig: ``PoseTW["B 12"]`` world←rig reference
                pose used to express candidates in the local frame.
            p3d_cameras: PyTorch3D camera batch aligned with candidate poses.
            backbone_out: Optional cached EVL output; when omitted the scorer
                may compute it from ``efm`` if it owns a backbone.

        Returns:
            Per-candidate logits, probabilities, expected scores, and optional
            validity/coverage diagnostics.
        """

    def parameters(self, recurse: bool = True) -> Any:
        """Return trainable parameters, matching `torch.nn.Module.parameters`."""

    def summarize_vin(
        self,
        batch: Any,
        *,
        include_torchsummary: bool = True,
        torchsummary_depth: int = 3,
    ) -> str:
        """Return a debug summary for scorer inputs and modules."""


class CandidateScorerPrediction(Protocol):
    """Minimal prediction attributes used by the current Lightning loss path.

    This protocol documents the structural subset of
    `aria_nbv.vin.types.VinPrediction` consumed by `VinLightningModule`.
    Optional coverage fields are read with ``getattr`` in the trainer, so they
    do not need to be present on future prediction dataclasses unless coverage
    weighting or diagnostics should use them.
    """

    logits: Tensor
    """``Tensor["B C K-1"]`` CORAL logits or a flattened candidate equivalent."""

    prob: Tensor
    """``Tensor["B C K"]`` ordinal class probabilities."""

    expected_normalized: Tensor
    """``Tensor["B C"]`` expected normalized score used for ranking metrics."""

    candidate_valid: Tensor | None
    """Optional ``Tensor["B C"]`` hard candidate-valid mask from the scorer."""


CandidateScorerConfig: TypeAlias = VinModelV3Config
"""Config-as-factory type for the active candidate scorer slot.

This alias is intentionally narrow until a concrete target-conditioned or
finite-horizon scorer exists. The expected expansion point is a discriminated
union such as ``VinModelV3Config | TargetConditionedMyopicScorerConfig`` once
the second config can be instantiated and tested end-to-end.
"""


__all__ = [
    "CandidateScorer",
    "CandidateScorerConfig",
    "CandidateScorerPrediction",
]
