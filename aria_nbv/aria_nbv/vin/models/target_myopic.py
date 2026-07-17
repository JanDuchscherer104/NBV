"""Target-conditioned myopic VIN scorer family.

This module owns the one-step architecture-family name that should score each
candidate from actor-visible scene evidence plus an actor-visible target
descriptor. The zero-descriptor configuration is runnable today as a named
myopic baseline backed by `aria_nbv.vin.models.scene_myopic.VinModelV3`; nonzero target
descriptors remain blocked until the actor-visible target-token contract is
implemented.
"""

from __future__ import annotations

from typing import Any

from efm3d.aria.pose import PoseTW
from pydantic import Field
from pytorch3d.renderer.cameras import PerspectiveCameras  # type: ignore[import-untyped]
from torch import Tensor, nn

from ...data_handling import EfmSnippetView, VinSnippetView
from ...utils import TargetConfig
from ..types import EvlBackboneOutput, VinPrediction
from .scene_myopic import VinModelV3, VinModelV3Config


class TargetConditionedMyopicScorerConfig(TargetConfig["TargetConditionedMyopicScorer"]):
    """Config-as-factory for the one-step target-scorer family.

    Attributes:
        num_classes: Number of ordinal output classes for CORAL-style row
            scoring if the scorer uses the current VIN Lightning objective.
        target_descriptor_dim: Dimension of the actor-visible target token or
            descriptor that conditions candidate scoring. ``0`` selects the
            runnable v3-backed myopic baseline.
        candidate_token_dim: Internal candidate token width reserved for the
            first target-conditioned implementation.
        base_scorer: Architecture config for the v3-backed zero-descriptor
            myopic baseline. The top-level `num_classes` field remains
            authoritative for Lightning/binner compatibility.
    """

    @property
    def target_type(self) -> type["TargetConditionedMyopicScorer"]:
        """Factory target for `BaseConfig.setup_target` once implemented."""

        return TargetConditionedMyopicScorer

    num_classes: int = Field(default=15, ge=2)
    """Number of ordinal classes for candidate-row scoring."""

    target_descriptor_dim: int = Field(default=0, ge=0)
    """Actor-visible target-token width; only ``0`` is currently runnable."""

    candidate_token_dim: int = Field(default=128, gt=0)
    """Reserved hidden width for target-conditioned candidate tokens."""

    base_scorer: VinModelV3Config = Field(default_factory=VinModelV3Config)
    """V3 architecture used by the runnable zero-descriptor myopic baseline."""


class TargetConditionedMyopicScorer(nn.Module):
    """Runnable zero-target myopic scorer plus blocked target-conditioned scaffold.

    With ``target_descriptor_dim == 0`` this module delegates to
    `VinModelV3`, preserving the current CORAL `VinPrediction` training
    contract under a named myopic architecture family. Positive descriptor
    widths fail during construction because target-token ownership, actor-input
    visibility, and feature fusion are not implemented yet.
    """

    def __init__(self, config: TargetConditionedMyopicScorerConfig) -> None:
        """Construct the v3-backed myopic baseline or reject true target conditioning."""

        super().__init__()
        self.config = config
        if int(config.target_descriptor_dim) != 0:
            raise NotImplementedError(
                "TargetConditionedMyopicScorer target descriptor path is not implemented. "
                "Use target_descriptor_dim=0 for the v3-backed myopic CORAL baseline.",
            )
        base_config = config.base_scorer.model_copy(
            deep=True,
            update={"num_classes": int(config.num_classes)},
        )
        self.base_scorer = VinModelV3(base_config)

    @property
    def head_coral(self) -> Any:
        """CORAL head delegated to the underlying v3 myopic scorer."""

        return self.base_scorer.head_coral

    def init_bin_values(self, values: Tensor, *, overwrite: bool = False) -> None:
        """Initialize delegated v3 CORAL bin representatives."""

        self.base_scorer.init_bin_values(values, overwrite=overwrite)

    def forward(
        self,
        efm: EfmSnippetView | VinSnippetView,
        *,
        candidate_poses_world_cam: PoseTW,
        reference_pose_world_rig: PoseTW,
        p3d_cameras: PerspectiveCameras,
        backbone_out: EvlBackboneOutput | None = None,
    ) -> VinPrediction:
        """Score ``PoseTW["B N_q 12"]`` candidates through VIN v3.

        With the only runnable zero-descriptor configuration, this returns the
        same ``B``/``N_q``-aligned CORAL `VinPrediction` as `VinModelV3`; it
        does not consume a target token.
        """

        return self.base_scorer.forward(
            efm,
            candidate_poses_world_cam=candidate_poses_world_cam,
            reference_pose_world_rig=reference_pose_world_rig,
            p3d_cameras=p3d_cameras,
            backbone_out=backbone_out,
        )

    def summarize_vin(
        self,
        batch: Any,
        *,
        include_torchsummary: bool = True,
        torchsummary_depth: int = 3,
    ) -> str:
        """Return the underlying v3 debug summary for the myopic baseline."""

        return self.base_scorer.summarize_vin(
            batch,
            include_torchsummary=include_torchsummary,
            torchsummary_depth=torchsummary_depth,
        )


__all__ = [
    "TargetConditionedMyopicScorer",
    "TargetConditionedMyopicScorerConfig",
]
