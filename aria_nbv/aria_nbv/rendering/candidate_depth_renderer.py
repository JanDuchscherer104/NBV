"""Render valid candidate poses directly from dataset snippets.

`CandidateDepthRenderer` consumes an `EfmSnippetView` with an attached mesh and
a `CandidateSamplingResult`. It renders the compact valid candidate table but
returns `candidate_indices` into the full sampled shell so labels and heavy
diagnostics can be joined back to candidate provenance, validity masks, and
reason codes.

This module provides :class:`CandidateDepths`, its renderer config, and the
orchestrator that adapts snippet meshes/cameras to the configured depth backend.
The backend owns rasterization; candidate generation owns feasibility, and
point-cloud conversion plus RRI scoring remain downstream.

Depth output is metric PyTorch3D z-depth in the physical camera frame. The
renderer is used for oracle/evaluation labels; callers decide whether rendered
depths or backprojected point clouds are retained in a rollout store.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import torch
from pydantic import Field, field_validator, model_validator

from ..utils import BaseConfig, Console, TargetConfig, Verbosity
from ..utils.typed_payloads import from_serializable, to_serializable
from .pytorch3d_depth_renderer import (
    Pytorch3DDepthRenderer,
    Pytorch3DDepthRendererConfig,
)

if TYPE_CHECKING:
    from efm3d.aria import CameraTW, PoseTW
    from pytorch3d.renderer.cameras import PerspectiveCameras  # type: ignore[import-untyped]

    from ..data_handling import EfmSnippetView
    from ..pose_generation.types import CandidateSamplingResult


@dataclass(slots=True)
class CandidateDepths:
    """Typed result for candidate depth rendering.

    `candidate_indices` maps rendered compact rows back to the full candidate
    shell. That link is required when writing target-RRI labels or selected
    heavy diagnostics into `rollouts.zarr`.
    """

    depths: torch.Tensor
    """Metric camera z-depth ``Tensor[\"C H W\", float]`` in metres."""

    depths_valid_mask: torch.Tensor
    """Face-hit and near/far mask ``Tensor[\"C H W\", bool]`` for raw depths."""

    poses: PoseTW
    """Rendered world-from-camera poses with logical shape ``(C, 12)``."""

    reference_pose: PoseTW
    """Physical world-from-reference rig pose with logical shape ``(12,)``."""

    candidate_indices: torch.Tensor
    """Full-shell row indices ``Tensor[\"C\", int64]`` for rendered candidates."""

    camera: CameraTW
    """Physical calibration and camera-from-reference extrinsics aligned over ``C``."""

    p3d_cameras: PerspectiveCameras
    """PyTorch3D cameras with world-to-view transforms aligned over ``C``."""

    def to_serializable(self) -> dict[str, object]:
        """Serialize this batch into a cache-friendly CPU payload."""

        return to_serializable(self)

    @classmethod
    def from_serializable(
        cls,
        payload: dict[str, object],
        *,
        device: torch.device,
    ) -> "CandidateDepths":
        """Reconstruct one batch from a serialized payload.

        Args:
            payload: Serialized payload produced by `to_serializable`.
            device: Destination device for tensors and wrappers.

        Returns:
            Reconstructed candidate-depth batch.
        """

        return from_serializable(cls, payload, device=device)


class CandidateDepthRendererConfig(TargetConfig["CandidateDepthRenderer"]):
    """Compose camera calibration, render sizing, and backend selection.

    Rendering is an oracle/evaluation stage: its mesh-derived depths must not
    be exposed as actor-visible state. ``max_candidates_final`` bounds work on
    the already compact valid-candidate table rather than changing validity.
    """

    @property
    def target_type(self) -> type["CandidateDepthRenderer"]:
        """Return the high-level candidate renderer constructed by this config."""
        return CandidateDepthRenderer

    device: torch.device = Field(default="auto")
    """Device used by the configured renderer and returned tensor payloads."""

    renderer: Pytorch3DDepthRendererConfig = Field(
        default_factory=Pytorch3DDepthRendererConfig,
    )
    """Nested config describing the underlying renderer (PyTorch3D or CPU)."""

    max_candidates_final: int = 60
    """Maximum number of already-pruned candidate views to render."""

    resolution_scale: float | None = 0.5
    """Optional uniform scale (0<scale<=1) applied to H,W for rendering. """

    output_width_px: int | None = Field(default=None, ge=1)
    """Optional exact rendered width in pixels; overrides ``resolution_scale`` when paired with height."""

    output_height_px: int | None = Field(default=None, ge=1)
    """Optional exact rendered height in pixels; overrides ``resolution_scale`` when paired with width."""

    verbosity: Verbosity = Field(
        default=Verbosity.VERBOSE,
    )
    """Verbosity level for logging."""

    is_debug: bool = False
    """Enable detailed debug logging."""

    _resolve_device = field_validator("device", mode="before")(BaseConfig._resolve_device)

    @model_validator(mode="after")
    def _validate_output_size(self) -> "CandidateDepthRendererConfig":
        """Reject half-specified exact render sizes."""

        if (self.output_width_px is None) != (self.output_height_px is None):
            raise ValueError("output_width_px and output_height_px must be set together.")
        return self


class CandidateDepthRenderer:
    """High-level wrapper that renders depth for compact valid candidate poses."""

    def __init__(self, config: CandidateDepthRendererConfig) -> None:
        self.config = config
        self.console = (
            Console.with_prefix(self.__class__.__name__)
            .set_verbosity(self.config.verbosity)
            .set_debug(self.config.is_debug)
        )
        self.renderer = self.config.renderer.setup_target()

    def render(
        self,
        sample: EfmSnippetView,
        candidates: CandidateSamplingResult,
    ) -> CandidateDepths:
        """Render depth maps for valid candidate poses within a snippet."""
        return self._render_subset(sample, candidates, compact_indices=None)

    def render_compact_indices(
        self,
        sample: EfmSnippetView,
        candidates: CandidateSamplingResult,
        compact_indices: torch.Tensor | list[int] | tuple[int, ...],
    ) -> CandidateDepths:
        """Render depth maps for explicit compact-valid candidate rows.

        Args:
            sample: Snippet with an attached mesh.
            candidates: Full candidate sampling result.
            compact_indices: Row indices into ``candidates.views``. These are
                compact valid-candidate indices, not full-shell indices.

        Returns:
            Rendered depth batch aligned with ``compact_indices`` and carrying
            full-shell ``candidate_indices`` for joins.
        """

        return self._render_subset(sample, candidates, compact_indices=compact_indices)

    def _render_subset(
        self,
        sample: EfmSnippetView,
        candidates: CandidateSamplingResult,
        *,
        compact_indices: torch.Tensor | list[int] | tuple[int, ...] | None,
    ) -> CandidateDepths:
        """Render either the configured prefix or an explicit compact subset."""

        if not sample.has_mesh or sample.mesh is None:
            msg = "CandidateDepthRenderer requires snippets with attached meshes."
            self.console.error(msg)
            raise ValueError(msg)
        self.console.log(
            f"Rendering depths: candidates={candidates.views.tensor().shape[0]} on '{self.renderer.__class__.__name__}'",
        )
        self.console.log(
            f"Mesh stats verts={sample.mesh.vertices.shape[0]:,} faces={sample.mesh.faces.shape[0]:,}",
        )
        pose_batch, camera_calib, candidate_indices = self._select_candidate_views(
            candidates,
            compact_indices=compact_indices,
        )
        self.console.log(
            f"Attempting renders for {pose_batch.tensor().shape[0]} candidates (GUI slice).",
        )
        self.console.dbg_summary("candidate_indices", candidate_indices)

        if self.config.output_width_px is not None and self.config.output_height_px is not None:
            new_size = (int(self.config.output_width_px), int(self.config.output_height_px))
            self.console.log(f"Scaling candidate camera intrinsics to exact size {new_size}")
            camera_calib = camera_calib.scale_to_size(new_size)  # type: ignore[arg-type]
        elif self.config.resolution_scale is not None:
            scale = float(self.config.resolution_scale)
            self.console.log(f"Scaling candidate camera intrinsics by {scale}")
            base_size = camera_calib.size[0]
            new_size = (
                int(base_size[0].item() * scale),
                int(base_size[1].item() * scale),
            )
            camera_calib = camera_calib.scale_to_size(new_size)  # type: ignore[arg-type]

        self.console.dbg_summary("camera_calib_batch", camera_calib)
        self.console.dbg_summary("pose_batch_tensor", pose_batch)
        if not isinstance(self.renderer, Pytorch3DDepthRenderer):
            raise TypeError(
                f"Unsupported renderer type: {self.renderer.__class__.__name__}",
            )

        depths, pix_to_face, cameras = self.renderer.render(
            poses=pose_batch,
            mesh=(sample.mesh_verts, sample.mesh_faces),  # type: ignore[arg-type]
            camera=camera_calib,
            frame_index=None,
        )

        depths_valid_mask = (
            (pix_to_face >= 0)
            & (depths > self.renderer.config.znear * 1.01)
            & (depths < self.renderer.config.zfar * 0.99)
        )

        self.console.dbg(
            f"Rendered {depths.shape[0]} candidates | depth shape {tuple(depths.shape)} | "
            f"invalid pixels: {(~depths_valid_mask).sum().item():,}",
        )

        return CandidateDepths(
            depths=depths,
            depths_valid_mask=depths_valid_mask,
            poses=pose_batch,
            reference_pose=candidates.reference_pose.to(device=pose_batch.device),
            candidate_indices=candidate_indices,
            camera=camera_calib,
            p3d_cameras=cameras,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _select_candidate_views(
        self,
        candidates: CandidateSamplingResult,
        *,
        compact_indices: torch.Tensor | list[int] | tuple[int, ...] | None = None,
    ) -> tuple[PoseTW, CameraTW, torch.Tensor]:
        """Select a subset of candidate poses for rendering.

        Returns:
            ``PoseTW`` world<-camera candidate poses, ``CameraTW`` candidate
            cameras whose extrinsics are camera<-reference, and ``Tensor["K"]``
            indices into the full sampled candidate shell.
        """
        device = self.renderer.device
        cam_views = candidates.views.to(device)
        num_candidates = cam_views.tensor().shape[0]
        if num_candidates == 0:
            raise ValueError("No candidates provided for rendering.")

        if compact_indices is None:
            num_render = min(
                num_candidates,
                max(1, int(self.config.max_candidates_final)),
            )
            candidate_idx = torch.arange(num_render, device=device, dtype=torch.long)
        else:
            candidate_idx = torch.as_tensor(compact_indices, device=device, dtype=torch.long).reshape(-1)
            if candidate_idx.numel() == 0:
                raise ValueError("At least one compact candidate index is required for rendering.")
            if torch.any(candidate_idx < 0) or torch.any(candidate_idx >= num_candidates):
                raise IndexError(
                    f"Compact candidate indices must be in [0,{num_candidates}), got {candidate_idx.detach().cpu().tolist()}."
                )

        selected_views = cam_views[candidate_idx]
        poses_world_cam = candidates.poses_world_cam(device=device)[candidate_idx]
        candidate_shell_idx = candidates.candidate_shell_indices(device=device)

        return poses_world_cam, selected_views, candidate_shell_idx[candidate_idx]


__all__ = [
    "CandidateDepthRenderer",
    "CandidateDepthRendererConfig",
    "CandidateDepths",
]
