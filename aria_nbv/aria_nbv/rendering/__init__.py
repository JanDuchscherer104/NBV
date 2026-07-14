"""Rendering utilities used by oracle RRI and rollout diagnostics.

This package facade exports candidate-depth DTOs and renderer configs/backends,
plus depth-to-world-point-cloud conversion. Backend modules own rasterization
and ray casting; pose generation supplies cameras, while RRI modules own
target-aware scoring and validity interpretation.

Candidate renders are metric depth images generated from ASE/EFM meshes and
candidate `PoseTW` cameras. PyTorch3D returns z-depth in the physical camera
frame; unprojection converts valid pixels back into world-frame point clouds
that can be joined with semidense history before point-mesh RRI scoring.

Rendering code is an oracle/evaluation dependency. Actor-visible datasets may
store poses, masks, and selected diagnostics, but rendered GT-depth point clouds
are supervision artifacts unless an experiment explicitly exposes them.
"""

from .candidate_depth_renderer import (
    CandidateDepthRenderer,
    CandidateDepthRendererConfig,
    CandidateDepths,
)
from .candidate_pointclouds import CandidatePointClouds, build_candidate_pointclouds
from .efm3d_depth_renderer import Efm3dDepthRenderer, Efm3dDepthRendererConfig
from .pytorch3d_depth_renderer import Pytorch3DDepthRenderer, Pytorch3DDepthRendererConfig

__all__ = [
    "CandidateDepths",
    "CandidateDepthRenderer",
    "CandidateDepthRendererConfig",
    "CandidatePointClouds",
    "build_candidate_pointclouds",
    "Efm3dDepthRenderer",
    "Efm3dDepthRendererConfig",
    "Pytorch3DDepthRenderer",
    "Pytorch3DDepthRendererConfig",
]
