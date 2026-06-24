"""Structural scorer contract for VIN-compatible candidate models.

This module names the narrow interface that `aria_nbv.lightning.lit_module`
needs from a candidate scorer. The current implementation is
`aria_nbv.vin.models.v3.VinModelV3`, the seminar-era one-step RRI scorer. Future
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

from typing import TYPE_CHECKING, Any, Literal, Protocol, TypeAlias

from torch import Tensor

from .models.multi_step import MultiStepCandidateScorerConfig
from .models.target_conditioned_myopic import TargetConditionedMyopicScorerConfig
from .models.v3 import VinModelV3Config
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
        `aria_nbv.vin.models.v3.VinModelV3` is the current one-step scorer.
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


CandidateScorerConfig: TypeAlias = (
    VinModelV3Config | TargetConditionedMyopicScorerConfig | MultiStepCandidateScorerConfig
)
"""Config-as-factory type for candidate scorer architecture slots.

The union keeps the preserved `VinModelV3Config` as the default runnable
implementation while letting experiment configs name the planned
target-conditioned myopic and finite-horizon families. Those planned configs
are still non-runnable scaffolds; their `setup_target()` methods fail
explicitly until the corresponding model semantics are implemented.
"""

CandidateScorerTrainingContract: TypeAlias = Literal[
    "coral_candidate",
    "target_myopic_coral_scaffold",
    "finite_horizon_q_scaffold",
]
"""Training-objective contract selected by a candidate scorer config.

`VinLightningModule` currently implements the ``"coral_candidate"`` contract:
per-candidate `VinPrediction` rows with CORAL logits, probabilities, and a
``head_coral`` helper. `TargetConditionedMyopicScorerConfig` with
``target_descriptor_dim == 0`` uses that same contract as a v3-backed baseline;
positive descriptor widths remain a scaffold until target-token ownership is
implemented. The finite-horizon ``Q_H`` scaffold is intentionally classified
separately because it needs rollout-return targets and hard valid-action masks
instead of one-step ordinal RRI labels.
"""


def candidate_scorer_training_contract(config: CandidateScorerConfig) -> CandidateScorerTrainingContract:
    """Classify a candidate scorer config by its Lightning objective contract.

    Args:
        config: Candidate scorer config accepted by experiment and Lightning
            configuration parsing.

    Returns:
        Contract string used by training entry points to reject incompatible
        objective families before constructing placeholder modules.
    """

    if isinstance(config, MultiStepCandidateScorerConfig):
        return "finite_horizon_q_scaffold"
    if isinstance(config, TargetConditionedMyopicScorerConfig):
        if int(config.target_descriptor_dim) == 0:
            return "coral_candidate"
        return "target_myopic_coral_scaffold"
    return "coral_candidate"


__all__ = [
    "CandidateScorer",
    "CandidateScorerConfig",
    "CandidateScorerPrediction",
    "CandidateScorerTrainingContract",
    "candidate_scorer_training_contract",
]
