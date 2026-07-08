"""Encoder modules for VIN candidate, trajectory, and coordinate features.

The package owns `torch.nn.Module` encoders used by VIN scorer architectures.
Use `fourier` for learnable continuous coordinate embeddings, `pose` for
candidate SE(3) pose encoders, `shell_pose` for shell-sampled candidates, and
`trajectory` for snippet trajectory summaries.
"""

from __future__ import annotations

from .fixed_fourier import FourierFeatures, FourierFeaturesConfig
from .fourier import LearnableFourierFeatures, LearnableFourierFeaturesConfig
from .pointnext import PointNeXtSEncoder, PointNeXtSEncoderConfig
from .pose import PoseEncoder, PoseEncodingOutput, R6dLffPoseEncoder, R6dLffPoseEncoderConfig
from .shell_pose import (
    PoseEncoderConfig,
    ShellLffPoseEncoder,
    ShellLffPoseEncoderConfig,
    ShellShPoseEncoderAdapter,
    ShellShPoseEncoderAdapterConfig,
    infer_pose_vec_groups,
)
from .spherical import ShellShPoseEncoder, ShellShPoseEncoderConfig
from .trajectory import TrajectoryEncoder, TrajectoryEncoderConfig, TrajectoryEncodingOutput
from .validation import validate_pos_grid_xyz_encoder

__all__ = [
    "FourierFeatures",
    "FourierFeaturesConfig",
    "LearnableFourierFeatures",
    "LearnableFourierFeaturesConfig",
    "PoseEncoder",
    "PoseEncoderConfig",
    "PoseEncodingOutput",
    "PointNeXtSEncoder",
    "PointNeXtSEncoderConfig",
    "R6dLffPoseEncoder",
    "R6dLffPoseEncoderConfig",
    "ShellLffPoseEncoder",
    "ShellLffPoseEncoderConfig",
    "ShellShPoseEncoder",
    "ShellShPoseEncoderAdapter",
    "ShellShPoseEncoderAdapterConfig",
    "ShellShPoseEncoderConfig",
    "TrajectoryEncoder",
    "TrajectoryEncoderConfig",
    "TrajectoryEncodingOutput",
    "infer_pose_vec_groups",
    "validate_pos_grid_xyz_encoder",
]
