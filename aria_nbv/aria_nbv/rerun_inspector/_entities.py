"""Stable Rerun entity-path vocabulary shared by inspector loggers.

This module owns only string roots for the world, actor-visible EFM evidence,
oracle GT overlays, candidate diagnostics, and metadata panels. Logger modules
own entity contents, static/dynamic timelines, and recording lifecycle.
"""

from __future__ import annotations

ENTITY_WORLD = "world"
ENTITY_SEMIDENSE = "world/ase/semidense"
ENTITY_REFERENCE_POSE = "world/ase/reference/rig"
ENTITY_METADATA_SAMPLE = "metadata/sample"
ENTITY_MESH = "world/gt/mesh"
ENTITY_CANDIDATE_ROOT = "world/candidates"
ENTITY_GT_OBBS = "world/gt/obbs"
ENTITY_DETECTED_OBBS = "world/efm/obbs/detected"
ENTITY_TRAJECTORY = "world/ase/trajectory/rig"
ENTITY_RGB_KEYFRAMES = "world/ase/cameras/rgb"
ENTITY_DEPTH_KEYFRAMES = "world/ase/cameras/rgb"
ENTITY_EFM_VOXELS = "world/efm/voxels"
ENTITY_EFM_VOXEL_EXTENT = "world/efm/voxels/extent"


__all__ = [
    "ENTITY_CANDIDATE_ROOT",
    "ENTITY_DEPTH_KEYFRAMES",
    "ENTITY_DETECTED_OBBS",
    "ENTITY_EFM_VOXELS",
    "ENTITY_EFM_VOXEL_EXTENT",
    "ENTITY_GT_OBBS",
    "ENTITY_MESH",
    "ENTITY_METADATA_SAMPLE",
    "ENTITY_REFERENCE_POSE",
    "ENTITY_RGB_KEYFRAMES",
    "ENTITY_SEMIDENSE",
    "ENTITY_TRAJECTORY",
    "ENTITY_WORLD",
]
