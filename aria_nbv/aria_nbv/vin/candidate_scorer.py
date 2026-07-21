"""Structural scorer contract for VIN-compatible candidate models.

This module names the narrow interface that :mod:`aria_nbv.lightning.lit_module`
needs from a candidate scorer. The current implementation is
:class:`aria_nbv.vin.models.scene_myopic.VinModelV3`, the seminar-era one-step RRI scorer. Future
target-conditioned myopic and finite-horizon scorers should implement the same
forward surface when they are trainable through the existing Lightning loss
path, or provide a separate Lightning module when their objective is no longer
CORAL-over-candidate rows.

The contract deliberately keeps rollout value targets out of
:class:`aria_nbv.vin.types.VinPrediction`. Multi-step labels such as endpoint
gain, selected-transition returns, and hard valid-action masks belong to
:mod:`aria_nbv.rollouts`; the runnable ``Q_H`` scorer and objective remain
leaf-owned by :mod:`aria_nbv.vin.models.target_finite_horizon` and
:mod:`aria_nbv.lightning.qh_module`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Protocol, TypeAlias

from torch import Tensor

from .models.scene_myopic import VinModelV3Config
from .models.target_finite_horizon import MultiStepCandidateScorerConfig
from .models.target_myopic import TargetConditionedMyopicScorerConfig
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
        `aria_nbv.vin.models.scene_myopic.VinModelV3` is the current one-step scorer.
        Future target-conditioned myopic scorers can satisfy this protocol when
        they still emit per-candidate ordinal logits. Finite-horizon Q_H models
        should only reuse it if their training objective remains row-local and
        compatible with `VinPrediction`.
    """

    head_coral: Any
    """CORAL head used for ordinal probability and expected-value helpers."""

    def init_bin_values(self, values: Tensor, *, overwrite: bool = False) -> None:
        """Initialize scorer-owned CORAL bin representatives."""

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
            candidate_poses_world_cam: ``PoseTW["B N_q 12"]`` world←camera
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
    """``Tensor["B N_q K-1", float32]`` CORAL threshold logits."""

    prob: Tensor
    """``Tensor["B N_q K", float32]`` ordinal class probabilities."""

    expected_normalized: Tensor
    """``Tensor["B N_q", float32]`` expected normalized ranking score."""

    candidate_valid: Tensor | None
    """Optional ``Tensor["B N_q", bool]`` scorer diagnostic validity mask.

    The current one-step scorer does not automatically use this mask as a
    training or action-selection mask. The dedicated ``Q_H`` objective uses the
    authoritative hard valid-action mask stored with its rollout state.
    """


CandidateScorerConfig: TypeAlias = (
    VinModelV3Config | TargetConditionedMyopicScorerConfig | MultiStepCandidateScorerConfig
)
"""Config-as-factory type for candidate scorer architecture slots.

The union keeps the preserved `VinModelV3Config` as the default one-step
implementation. The finite-horizon config is runnable but has a distinct
rollout-value objective and is rejected by the one-step Lightning boundary.
"""

CandidateScorerTrainingContract: TypeAlias = Literal[
    "coral_candidate",
    "target_myopic_coral_scaffold",
    "finite_horizon_q",
]
"""Training-objective contract selected by a candidate scorer config.

`VinLightningModule` currently implements the ``"coral_candidate"`` contract:
per-candidate `VinPrediction` rows with CORAL logits, probabilities, and a
``head_coral`` helper. `TargetConditionedMyopicScorerConfig` with
``target_descriptor_dim == 0`` uses that same contract as a v3-backed baseline;
positive descriptor widths remain unsupported until target-token ownership is
implemented. The runnable finite-horizon ``Q_H`` family is classified
separately because it uses selected-transition rewards, bootstrap targets, and
hard action masks instead of one-step ordinal RRI labels.
"""


def candidate_scorer_training_contract(config: CandidateScorerConfig) -> CandidateScorerTrainingContract:
    """Classify a candidate scorer config by its Lightning objective contract.

    Args:
        config: Candidate scorer config accepted by experiment and Lightning
            configuration parsing.

    Returns:
        Contract string used by training entry points to reject incompatible
        objective families before constructing their modules.
    """

    if isinstance(config, MultiStepCandidateScorerConfig):
        return "finite_horizon_q"
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
