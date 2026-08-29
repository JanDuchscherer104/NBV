"""PyTorch3D depth renderer used for oracle RRI simulations.

This module contains a configurable renderer that turns candidate poses
(`efm3d.aria.PoseTW`) plus an ASE mesh into per-pixel depth maps.
It follows the project's config-as-factory pattern and keeps the public
API torch-native so it can slot into the NBV training loop without
intermediate numpy copies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal

import torch
from pydantic import Field, field_validator
from pytorch3d.renderer import MeshRasterizer, RasterizationSettings  # type: ignore[import-untyped]
from pytorch3d.renderer.cameras import PerspectiveCameras  # type: ignore[import-untyped]
from pytorch3d.structures import Meshes  # type: ignore[import-untyped]
from torch import Tensor

from ..utils import BaseConfig, Console, TargetConfig, Verbosity

if TYPE_CHECKING:
    from efm3d.aria import CameraTW, PoseTW


def camera_tw_to_pytorch3d(
    camera: CameraTW,
    pose_world_camera: PoseTW,
    *,
    device: torch.device,
    dtype: torch.dtype = torch.float32,
) -> PerspectiveCameras:
    """Convert calibrated world-from-camera poses to the project's PyTorch3D convention.

    This is the sole adapter for persisted linear ``CameraTW`` calibration and
    rendered ``camera_z`` depth. PyTorch3D uses row-vector world-to-view
    transforms, so the inverse ``PoseTW`` rotation is transposed explicitly.
    """

    camera = camera.to(device)
    pose_camera_world = pose_world_camera.inverse().to(device)
    batch_size = int(pose_camera_world.shape[0])
    focal, principal, image_size = _camera_intrinsics(
        camera,
        device=device,
        dtype=dtype,
        batch_size=batch_size,
    )
    return PerspectiveCameras(
        device=device,
        R=pose_camera_world.R.transpose(-1, -2).contiguous(),
        T=pose_camera_world.t,
        focal_length=focal,
        principal_point=principal,
        image_size=image_size,
        in_ndc=False,
    )


def _camera_intrinsics(
    camera: CameraTW,
    *,
    device: torch.device,
    dtype: torch.dtype,
    batch_size: int,
) -> tuple[Tensor, Tensor, Tensor]:
    """Return physical-image intrinsics aligned to a pose batch."""

    size_all = camera.size.reshape(-1, 2).to(device=device, dtype=torch.float32)
    if size_all.shape[0] not in (1, batch_size):
        raise ValueError(f"Camera size batch {size_all.shape[0]} does not match poses batch {batch_size}")
    size_base = size_all[0]
    if not torch.allclose(size_all, size_base):
        raise ValueError("Per-candidate varying image sizes are not supported.")
    focal_all = camera.f.reshape(-1, 2).to(device=device, dtype=dtype)
    principal_all = camera.c.reshape(-1, 2).to(device=device, dtype=dtype)
    if focal_all.shape[0] == 1 and batch_size > 1:
        focal_all = focal_all.expand(batch_size, -1)
        principal_all = principal_all.expand(batch_size, -1)
        size_all = size_all.expand(batch_size, -1)
    elif focal_all.shape[0] != batch_size:
        raise ValueError(f"Camera focal batch {focal_all.shape[0]} does not match poses batch {batch_size}")
    image_size = torch.stack((size_all[:, 1], size_all[:, 0]), dim=-1).to(dtype=dtype)
    return focal_all, principal_all, image_size


class Pytorch3DDepthRendererConfig(TargetConfig["Pytorch3DDepthRenderer"]):
    """Configuration for `Pytorch3DDepthRenderer`."""

    @property
    def target_type(self) -> type["Pytorch3DDepthRenderer"]:
        """Return the batched PyTorch3D rasterizer constructed by this config."""
        return Pytorch3DDepthRenderer

    device: Annotated[torch.device, Field(default="auto")]
    """Torch device to run rasterisation on (falls back to CPU if unavailable)."""

    zfar: float = 20.0
    """Far clipping plane in metres used by downstream validity checks."""

    znear: float = 1e-3
    """Near clipping plane (metres); triangles closer than this are clipped."""

    cull_backfaces: bool = False
    """If ``True`` drop triangles with normals pointing away from the camera.

    NBV cameras are typically *inside* closed meshes (rooms); back-face culling
    would therefore remove interior walls. The default renders both sides.
    """

    blur_radius: float = 0.0
    """Soft rasterizer blur radius; keep ``0`` for hard z-buffer."""

    bin_size: int | None = 0
    """Rasterisation bin size in pixels.

    Set to ``0`` to force naive rasterisation (avoids bin overflow warnings on dense meshes).
    Set to ``None`` to let PyTorch3D choose heuristics.
    """

    max_faces_per_bin: int | None = None
    """Performance knob mirroring ``RasterizationSettings.max_faces_per_bin``."""

    max_views_per_batch: int = Field(default=4, ge=1)
    """Maximum cameras rasterized together, bounding replicated mesh memory."""

    dtype: Literal["float32", "float16", "bfloat16"] = "float32"
    """Computation dtype; use float16/bfloat16 on CUDA for speed"""

    is_debug: bool = False
    """Enable debug logging on the renderer console."""

    verbosity: Verbosity = Field(
        default=Verbosity.VERBOSE,
        description="Verbosity level for logging (0=quiet, 1=normal, 2=verbose).",
    )
    """Enable `Console` logging."""

    _resolve_device = field_validator("device", mode="before")(BaseConfig._resolve_geometry_device)


class Pytorch3DDepthRenderer:
    """Depth rendering backend based on PyTorch3D."""

    def __init__(self, config: Pytorch3DDepthRendererConfig) -> None:
        self.config = config
        self.console = (
            Console.with_prefix(self.__class__.__name__)
            .set_verbosity(self.config.verbosity)
            .set_debug(self.config.is_debug)
        )

        self.device = self.config.device

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def render(
        self,
        poses: PoseTW,
        mesh: tuple[torch.Tensor, torch.Tensor],
        camera: CameraTW,
        *,
        frame_index: int | None = None,
    ) -> tuple[Tensor, Tensor, PerspectiveCameras]:
        """Rasterize metric z-depth for world-from-camera candidate poses.

        Args:
            poses: Batched ``PoseTW`` world-from-camera transforms with logical
                shape ``(C, 12)``.
            mesh: World-frame vertices ``Tensor[\"V 3\", float]`` in metres and
                triangle indices ``Tensor[\"F 3\", int64]``.
            camera: EFM camera calibration supplying physical-image intrinsics.
            frame_index: Optional calibration row. When omitted, ``camera``
                must already be singleton or aligned one-to-one with ``poses``.

        Returns:
            A tuple of raw z-buffer ``Tensor[\"C H W\", float]`` in metres,
            closest-face indices ``Tensor[\"C H W\", int64]`` with negative
            values for raster misses, and aligned PyTorch3D cameras. The
            caller combines face hits with near/far checks to form a mask.
        """

        dtype = {
            "float32": torch.float32,
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
        }[self.config.dtype]

        cam_single = self._slice_camera(camera, frame_index)
        cameras = camera_tw_to_pytorch3d(
            cam_single,
            poses,
            device=self.device,
            dtype=dtype,
        )
        focal_length = cameras.focal_length
        principal_point = cameras.principal_point
        image_size = cameras.image_size
        height, width = (int(value.item()) for value in image_size[0])
        self.console.plog(
            {
                "image_size": image_size[0, :],
                "focal_length": focal_length[0, :],
                "principal_point": principal_point[0, :],
                "width": width,
                "height": height,
            }
        )

        poses_cw = poses.inverse().to(self.device)
        self.console.dbg_summary("poses_cw", poses_cw)
        batch_size = poses_cw.shape[0]

        # Keep one base mesh and replicate it only for each bounded view batch.
        verts_t, faces_t = mesh

        mesh_struct_single = Meshes(verts=[verts_t.to(self.device)], faces=[faces_t.to(self.device)])
        raster_settings = RasterizationSettings(
            image_size=(int(height), int(width)),
            blur_radius=self.config.blur_radius,
            faces_per_pixel=1,  # Closest simplex only
            cull_backfaces=self.config.cull_backfaces,
            bin_size=self.config.bin_size,
            max_faces_per_bin=self.config.max_faces_per_bin,
            cull_to_frustum=False,
            z_clip_value=self.config.znear,
        )
        autocast_enable = dtype != torch.float32 and self.device.type == "cuda"
        depth_batches: list[Tensor] = []
        pix_to_face_batches: list[Tensor] = []
        num_faces = int(faces_t.shape[0])
        max_views_per_batch = min(batch_size, int(self.config.max_views_per_batch))
        for start in range(0, batch_size, max_views_per_batch):
            stop = min(start + max_views_per_batch, batch_size)
            batch_indices = torch.arange(start, stop, device=self.device, dtype=torch.long)
            batch_cameras = cameras[batch_indices]
            mesh_struct = mesh_struct_single.extend(stop - start)
            rasterizer = MeshRasterizer(cameras=batch_cameras, raster_settings=raster_settings)
            with torch.autocast(device_type=self.device.type, dtype=dtype, enabled=autocast_enable):
                fragments = rasterizer.forward(mesh_struct)
                depth_batches.append(fragments.zbuf.squeeze(-1))
                pix_to_face = fragments.pix_to_face.squeeze(-1)
                global_face_offset = start * num_faces
                pix_to_face_batches.append(torch.where(pix_to_face >= 0, pix_to_face + global_face_offset, pix_to_face))

        depth = torch.cat(depth_batches, dim=0)
        pix_to_face = torch.cat(pix_to_face_batches, dim=0)

        return (
            depth,
            pix_to_face,
            cameras,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _slice_camera(self, camera: CameraTW, frame_index: int | None) -> CameraTW:
        """Return a per-candidate or single-frame ``CameraTW`` entry."""

        camera = camera.to(self.device)
        data = camera.tensor()
        if data.ndim == 1:
            return camera
        if frame_index is None:
            # Already per-candidate intrinsics.
            return camera
        idx = data.shape[0] - 1 if frame_index is None else frame_index
        idx = max(-data.shape[0], min(data.shape[0] - 1, idx))
        return camera[idx]
