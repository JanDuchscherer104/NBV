"""Public geometry and color helpers for ARIA-NBV Rerun inspection.

This package exports deterministic candidate coloring and frame-safe camera
frustum construction. Recording startup, dataset selection, offline logging,
and rollout-Zarr inspection remain owned by their internal runtime modules and
are reached through the configured CLI rather than this convenience surface.
"""

from __future__ import annotations

from ._colors import (
    INVALID_RGBA,
    TARGET_OBB_RGBA,
    UNKNOWN_RGBA,
    VALID_RGBA,
    ColorMode,
    RGBAArray,
    candidate_rgba,
    obb_semantic_rgba,
    oracle_rri_to_rgba,
    rank_to_rgba,
    step_to_rgba,
    validity_to_rgba,
)
from ._config import RerunInspectorLayerState, RerunInspectorRolloutLayersConfig
from ._frusta import (
    CandidateFrustumLineStrips,
    apply_display_cw90,
    candidate_labels,
    frusta_from_camera_tw,
    frusta_from_p3d_cameras,
)
from ._layers import RolloutLayerName, RolloutLayerPreset, resolve_rollout_layer_config

__all__ = [
    "ColorMode",
    "RGBAArray",
    "VALID_RGBA",
    "INVALID_RGBA",
    "TARGET_OBB_RGBA",
    "UNKNOWN_RGBA",
    "CandidateFrustumLineStrips",
    "RerunInspectorLayerState",
    "RerunInspectorRolloutLayersConfig",
    "RolloutLayerName",
    "RolloutLayerPreset",
    "apply_display_cw90",
    "candidate_labels",
    "candidate_rgba",
    "frusta_from_camera_tw",
    "frusta_from_p3d_cameras",
    "obb_semantic_rgba",
    "oracle_rri_to_rgba",
    "rank_to_rgba",
    "resolve_rollout_layer_config",
    "step_to_rgba",
    "validity_to_rgba",
]
