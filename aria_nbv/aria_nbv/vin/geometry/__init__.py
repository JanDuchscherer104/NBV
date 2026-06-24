"""Geometry helpers shared by VIN scorer implementations.

The modules in this package own stateless SE(3), camera, frustum, and voxel
geometry contracts used by :mod:`aria_nbv.vin.model_v3` and related diagnostic
surfaces. Neural modules should import these helpers rather than keeping shape
normalization or camera-space math in model classes.
"""

from __future__ import annotations

from .frustum import build_frustum_points_world_p3d, frustum_points_world_from_cameras
from .pose_batch import ensure_candidate_batch, ensure_pose_batch
from .semidense_projection import (
    SEMIDENSE_GRID_CHANNELS,
    SEMIDENSE_PROJ_DIM,
    build_projection_grid,
    encode_projection_summary,
    project_points_to_candidate_cameras,
    sample_semidense_points,
    semidense_proj_feature_index,
)
from .voxel import (
    build_scene_field,
    candidate_valid_from_token,
    center_crop_grid,
    infer_padded_grid_shape,
    pool_voxel_points,
    pos_grid_from_pts_world,
    sample_voxel_field,
)

__all__ = [
    "build_scene_field",
    "build_frustum_points_world_p3d",
    "candidate_valid_from_token",
    "center_crop_grid",
    "ensure_candidate_batch",
    "ensure_pose_batch",
    "frustum_points_world_from_cameras",
    "infer_padded_grid_shape",
    "pool_voxel_points",
    "pos_grid_from_pts_world",
    "SEMIDENSE_GRID_CHANNELS",
    "SEMIDENSE_PROJ_DIM",
    "build_projection_grid",
    "encode_projection_summary",
    "project_points_to_candidate_cameras",
    "sample_voxel_field",
    "sample_semidense_points",
    "semidense_proj_feature_index",
]
