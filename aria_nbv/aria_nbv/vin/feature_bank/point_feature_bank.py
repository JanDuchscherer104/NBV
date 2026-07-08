"""Read-only point-feature bank container."""

from __future__ import annotations

from dataclasses import dataclass

from torch import Tensor

from .provenance import validate_actor_feature_provenance


@dataclass(slots=True)
class PointFeatureBank:
    """Read-only feature bank derived from logged actor-visible observations.

    Attributes:
        points_world: ``Tensor["B N 3"]`` semidense or fused world points.
        features: ``Tensor["B N C"]`` pooled point descriptors.
        valid_mask: ``Tensor["B N", bool]`` descriptor-valid mask.
        valid_frame_count: ``Tensor["B N", int64]`` number of valid frame samples.
        weight_sum: ``Tensor["B N"]`` sum of valid pooling weights.
        per_frame_valid: ``Tensor["B T N", bool]`` logged projection-valid mask.
        source_frame_indices: ``Tensor["B T"]`` or ``Tensor["T"]`` source frame ids.
        feature_source: Human-readable feature source id.
        source_role: Actor/oracle provenance role. Actor banks must be actor-visible.
        compression_id: Descriptor compression provenance id.
        point_support: Optional per-point or per-sample support weights.
    """

    points_world: Tensor
    features: Tensor
    valid_mask: Tensor
    valid_frame_count: Tensor
    weight_sum: Tensor
    per_frame_valid: Tensor
    source_frame_indices: Tensor
    feature_source: str
    source_role: str = "actor_visible"
    compression_id: str = "raw"
    point_support: Tensor | None = None

    def __post_init__(self) -> None:
        """Validate provenance immediately for direct dataclass construction."""
        self.validate_actor_visible()

    def validate_actor_visible(self) -> None:
        """Raise if this bank is not valid as an actor-visible descriptor source."""
        validate_actor_feature_provenance(
            feature_source=self.feature_source,
            source_role=self.source_role,
        )


__all__ = ["PointFeatureBank"]
