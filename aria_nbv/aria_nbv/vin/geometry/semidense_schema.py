"""Semidense projection feature schema for VIN geometry helpers.

This module owns the stable ordering of semidense projection summary features
and grid channels used by `aria_nbv.vin.geometry.semidense_projection` and
model-owned heads such as `aria_nbv.vin.models.scene_myopic.VinModelV3`. It is deliberately
pure metadata: no PyTorch, camera, or model imports belong here.
"""

from __future__ import annotations

SEMIDENSE_PROJ_FEATURES: tuple[str, ...] = (
    "coverage",
    "empty_frac",
    "semidense_candidate_vis_frac",
    "depth_mean",
    "depth_std",
)
"""Ordered per-candidate projection statistics used by VIN scorers."""

SEMIDENSE_PROJ_DIM = len(SEMIDENSE_PROJ_FEATURES)
"""Feature dimension for semidense projection summary tensors."""

SEMIDENSE_GRID_FEATURES: tuple[str, ...] = (
    "occupancy",
    "depth_mean",
    "depth_std",
)
"""Screen-space grid channels consumed by VIN semidense CNN encoders."""

SEMIDENSE_GRID_CHANNELS = len(SEMIDENSE_GRID_FEATURES)
"""Channel count for semidense projection grid tensors."""


def semidense_proj_feature_index(name: str) -> int:
    """Resolve a canonical semidense projection feature name to its index.

    Parameters
    ----------
    name:
        Canonical feature name from `SEMIDENSE_PROJ_FEATURES`.

    Returns
    -------
    int
        Zero-based channel index in the projection summary tensor.

    Raises
    ------
    ValueError
        If ``name`` does not identify a known projection summary feature.
    """
    if name in SEMIDENSE_PROJ_FEATURES:
        return SEMIDENSE_PROJ_FEATURES.index(name)
    raise ValueError(f"Unknown semidense projection feature '{name}'.")


__all__ = [
    "SEMIDENSE_GRID_CHANNELS",
    "SEMIDENSE_GRID_FEATURES",
    "SEMIDENSE_PROJ_DIM",
    "SEMIDENSE_PROJ_FEATURES",
    "semidense_proj_feature_index",
]
