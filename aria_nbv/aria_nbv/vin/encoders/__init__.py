"""Encoder modules for VIN candidate, trajectory, and coordinate features.

The package owns `torch.nn.Module` encoders used by VIN scorer architectures.
Use `fourier` for learnable continuous coordinate embeddings, `pose` for
candidate SE(3) pose encoders, and `trajectory` for snippet trajectory
summaries.
"""

from __future__ import annotations

from .fourier import LearnableFourierFeatures, LearnableFourierFeaturesConfig
from .pose import PoseEncoder, PoseEncodingOutput, R6dLffPoseEncoder, R6dLffPoseEncoderConfig
from .trajectory import TrajectoryEncoder, TrajectoryEncoderConfig, TrajectoryEncodingOutput

__all__ = [
    "LearnableFourierFeatures",
    "LearnableFourierFeaturesConfig",
    "PoseEncoder",
    "PoseEncodingOutput",
    "R6dLffPoseEncoder",
    "R6dLffPoseEncoderConfig",
    "TrajectoryEncoder",
    "TrajectoryEncoderConfig",
    "TrajectoryEncodingOutput",
]
