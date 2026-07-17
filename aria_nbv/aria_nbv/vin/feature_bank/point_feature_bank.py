"""Point-feature bank container with actor-source validation.

The module owns the structured payload returned by logged-view feature
sampling; projection, pooling, and provenance validation remain separate.
"""

from __future__ import annotations

from dataclasses import dataclass

from torch import Tensor

from .provenance import validate_actor_feature_provenance


@dataclass(slots=True)
class PointFeatureBank:
    """Feature bank derived from logged actor-visible observations.

    The dataclass validates provenance at construction but is not frozen;
    callers that require immutable cache records must enforce immutability at
    the storage boundary.

    Descriptor values are learned-source-local rather than globally comparable.
    ``feature_source`` and ``compression_id`` are human-readable provenance
    labels, not content hashes. Persistent EVL-derived banks must be paired by
    their cache owner with source-config and checkpoint hashes.

    """

    points_world: Tensor
    """``Tensor["B N_p 3", float32]`` world-frame point coordinates in metres."""

    features: Tensor
    """``Tensor["B N_p C", float32]`` logged-view descriptors pooled per point."""

    valid_mask: Tensor
    """``Tensor["B N_p", bool]`` mask for points with descriptor support."""

    valid_frame_count: Tensor
    """``Tensor["B N_p", int64]`` valid logged-frame samples per point."""

    weight_sum: Tensor
    """``Tensor["B N_p", float32]`` pooling-weight sum before epsilon."""

    per_frame_valid: Tensor
    """``Tensor["B T N_p", bool]`` per-frame projection-valid mask."""

    source_frame_indices: Tensor
    """``Tensor["B T", int64]`` logged source-frame indices."""

    feature_source: str
    """Approved actor-visible source label; not a checkpoint content hash."""

    source_role: str = "actor_visible"
    """Provenance role; actor banks accept only ``"actor_visible"``."""

    compression_id: str = "raw"
    """Descriptor compression label; not a projection-matrix content hash."""

    point_support: Tensor | None = None
    """Optional point/sample weights broadcast by the multiview pooler."""

    def __post_init__(self) -> None:
        """Validate provenance immediately for direct dataclass construction."""
        self.validate_actor_visible()

    def validate_actor_visible(self) -> None:
        """Reject oracle, GT, future-candidate, or unapproved feature sources."""
        validate_actor_feature_provenance(
            feature_source=self.feature_source,
            source_role=self.source_role,
        )


__all__ = ["PointFeatureBank"]
