"""Geometry helpers shared by VIN scorer implementations.

The modules in this package own stateless SE(3), camera, frustum, and voxel
geometry contracts used by :mod:`aria_nbv.vin.model_v3` and related diagnostic
surfaces. Neural modules should import these helpers rather than keeping shape
normalization or camera-space math in model classes.
"""

from __future__ import annotations

from .frustum import build_frustum_points_world_p3d, frustum_points_world_from_cameras
from .pose_batch import ensure_candidate_batch, ensure_pose_batch

__all__ = [
    "build_frustum_points_world_p3d",
    "ensure_candidate_batch",
    "ensure_pose_batch",
    "frustum_points_world_from_cameras",
]
