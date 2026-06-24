"""Trainable scene-field projection modules for VIN scorers.

Scene-field construction is deterministic and lives in
`aria_nbv.vin.scorer_context.build_vin_scorer_scene_field`. This module owns the
small learnable projection that maps those ordered scalar channels into the
voxel feature width consumed by pose-conditioned pooling.
"""

from __future__ import annotations

from pydantic import Field
from torch import nn

from ...utils import TargetConfig
from .normalization import largest_divisor_leq


class SceneFieldProjection(nn.Sequential):
    """Project scalar voxel evidence channels into VIN field features.

    The class subclasses `torch.nn.Sequential` so models can assign it directly
    to `field_proj` while preserving historical checkpoint keys such as
    `field_proj.0.weight`, `field_proj.1.weight`, and `field_proj.1.bias`.
    """

    def __init__(self, config: "SceneFieldProjectionConfig") -> None:
        """Build the ``1x1x1 Conv3d + GroupNorm + GELU`` projection.

        Args:
            config: Config-as-factory object that owns input channel count,
                output field width, and requested GroupNorm groups.
        """
        field_dim = int(config.field_dim)
        groups = largest_divisor_leq(field_dim, int(config.field_gn_groups))
        super().__init__(
            nn.Conv3d(
                int(config.in_channels),
                field_dim,
                kernel_size=1,
                bias=False,
            ),
            nn.GroupNorm(num_groups=groups, num_channels=field_dim),
            nn.GELU(),
        )
        self.config = config


class SceneFieldProjectionConfig(TargetConfig[SceneFieldProjection]):
    """Configure the trainable VIN scene-field projection."""

    @property
    def target_type(self) -> type[SceneFieldProjection]:
        """Factory target for `BaseConfig.setup_target`."""
        return SceneFieldProjection

    in_channels: int = Field(gt=0)
    """Number of ordered scalar scene-field channels."""

    field_dim: int = Field(default=32, gt=0)
    """Projected voxel feature dimension."""

    field_gn_groups: int = Field(default=4, gt=0)
    """Requested GroupNorm groups, clamped to a divisor of `field_dim`."""


__all__ = ["SceneFieldProjection", "SceneFieldProjectionConfig"]
