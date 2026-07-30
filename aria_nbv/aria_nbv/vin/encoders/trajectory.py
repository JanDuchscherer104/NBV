"""Trajectory encoders for EFM snippet rig poses.

This module owns a trajectory encoder that reuses the VIN candidate pose encoder per frame
and then pools the encoded sequence into optional global context features.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from efm3d.aria.pose import PoseTW
from pydantic import Field
from torch import Tensor, nn

from ...data_handling.ase_efm.views import EfmTrajectoryView
from ...utils import TargetConfig
from .pose import PoseEncodingOutput, R6dLffPoseEncoder, R6dLffPoseEncoderConfig


@dataclass(slots=True)
class TrajectoryEncodingOutput:
    """Trajectory encoding outputs.

    Attributes:
        per_frame: PoseEncodingOutput for each frame.
        pooled: ``Tensor["B E", float32]`` pooled trajectory embedding (or None).
    """

    per_frame: PoseEncodingOutput
    """Per-frame pose encoding outputs."""

    pooled: Tensor | None
    """``Tensor["B E", float32]`` pooled trajectory embedding (or None)."""


class TrajectoryEncoderConfig(TargetConfig["TrajectoryEncoder"]):
    """Configure per-frame pose encoding and sequence reduction."""

    @property
    def target_type(self) -> type["TrajectoryEncoder"]:
        """Factory target for `aria_nbv.utils.base_config.BaseConfig.setup_target`."""
        return TrajectoryEncoder

    pose_encoder: R6dLffPoseEncoderConfig = Field(default_factory=R6dLffPoseEncoderConfig)
    """Pose encoder configuration (R6D + LFF)."""

    pool_mode: Literal["mean", "final", "none"] = "mean"
    """Pooling mode over frames: ``mean``, ``final``, or ``none``."""


class TrajectoryEncoder(nn.Module):
    """Encode EFM trajectory poses with an R6D + LFF pose encoder."""

    def __init__(self, config: TrajectoryEncoderConfig) -> None:
        super().__init__()
        self.config = config
        self.pose_encoder = R6dLffPoseEncoder(self.config.pose_encoder)

    @property
    def out_dim(self) -> int:
        """Return the per-frame and pooled trajectory embedding width."""
        return int(self.pose_encoder.out_dim)

    def _ensure_batch(self, pose: PoseTW) -> PoseTW:
        """Ensure trajectory poses are batched as ``(B,F,12)``."""
        if pose.ndim == 2:
            return PoseTW(pose._data.unsqueeze(0))
        if pose.ndim != 3:
            raise ValueError(
                f"Expected trajectory pose shape (F,12) or (B,F,12), got ndim={pose.ndim}.",
            )
        return pose

    def encode_poses(self, poses: PoseTW) -> TrajectoryEncodingOutput:
        """Encode a batch of trajectory poses.

        Args:
            poses: ``PoseTW["B F 12"]`` or ``PoseTW["F 12"]`` trajectory poses.

        Returns:
            TrajectoryEncodingOutput with per-frame encodings and pooled embedding.
        """
        poses = self._ensure_batch(poses)
        per_frame = self.pose_encoder.encode(poses)

        pooled: Tensor | None
        match self.config.pool_mode:
            case "mean":
                pooled = per_frame.pose_enc.mean(dim=1)
            case "final":
                pooled = per_frame.pose_enc[:, -1]
            case "none":
                pooled = None
            case _:
                raise ValueError(f"Unknown pool_mode: {self.config.pool_mode}")

        return TrajectoryEncodingOutput(per_frame=per_frame, pooled=pooled)

    def forward(self, trajectory: EfmTrajectoryView) -> TrajectoryEncodingOutput:
        """Encode a trajectory's world←rig poses.

        Args:
            trajectory: `aria_nbv.data_handling.ase_efm.views.EfmTrajectoryView`.

        Returns:
            TrajectoryEncodingOutput with per-frame encodings and pooled embedding.
        """
        return self.encode_poses(trajectory.t_world_rig)


__all__ = ["TrajectoryEncoder", "TrajectoryEncoderConfig", "TrajectoryEncodingOutput"]
