"""CPU ray-based depth renderer using trimesh.

This renderer mirrors the public API of `Pytorch3DDepthRenderer`
but uses pure CPU ray-mesh intersection so it works without a GPU. It is
intended as a correctness-oriented fallback and for lightweight testing.

This module provides :class:`Efm3dDepthRendererConfig` and the trimesh-backed
renderer, owning mesh preparation, optional proxy walls, ray construction, and
chunked intersection. Candidate selection, depth-to-point-cloud conversion,
and RRI scoring remain outside this backend.

Key features:
    - Config-as-factory pattern (`BaseConfig.setup_target()`).
    - Optional proxy-wall insertion to seal incomplete meshes, using the
      union of mesh bounds and semidense occupancy extents.
    - Chunked ray casting to avoid excessive memory use on high-res
      images.
    - Optional PyEmbree backend when available for faster intersections.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import torch
import trimesh
from pydantic import AliasChoices, Field, field_validator
from trimesh import Trimesh

from ..utils import BaseConfig, Console, TargetConfig, Verbosity

if TYPE_CHECKING:
    from efm3d.aria import CameraTW, PoseTW
    from torch import Tensor
    from trimesh import Trimesh


class Efm3dDepthRendererConfig(TargetConfig["Efm3dDepthRenderer"]):
    """Configure correctness-oriented CPU ray casting for metric depth.

    Proxy-wall and chunk controls compensate for incomplete ASE room meshes
    and cap host-memory use. The backend always traces in world geometry, then
    returns camera z-depth in metres on the configured Torch output device.
    """

    @property
    def target_type(self) -> type["Efm3dDepthRenderer"]:
        """Factory target for `BaseConfig.setup_target`."""
        return Efm3dDepthRenderer

    device: str = "cpu"
    """Torch device for the returned depth tensor."""

    zfar: float = 20.0
    """Depth value (metres) for rays that miss the mesh."""

    add_proxy_walls: bool = True
    """If ``True`` seal missing walls with thin box proxies."""

    proxy_wall_area_threshold: float = 0.2
    """Minimum fraction of expected wall area required to skip proxies."""

    proxy_eps: float = 0.05
    """Epsilon (metres) for detecting faces near bounds."""

    chunk_rays: int = 200_000
    """Number of rays processed per chunk to limit memory."""

    backend: str = "auto"
    """Ray backend: ``'auto'`` (pyembree if available else native),
    ``'pyembree'`` or ``'trimesh'``."""

    verbosity: Verbosity = Field(
        default=Verbosity.NORMAL,
        validation_alias=AliasChoices("verbosity", "verbose"),
        description="Verbosity level for logging (0=quiet, 1=normal, 2=verbose).",
    )
    """Enable structured logging."""

    is_debug: bool = False
    """Enable extra debug logging."""

    _coerce_verbosity = field_validator("verbosity", mode="before")(BaseConfig._coerce_verbosity)


class Efm3dDepthRenderer:
    """CPU depth renderer built on trimesh ray tracing."""

    def __init__(self, config: Efm3dDepthRendererConfig) -> None:
        self.config = config
        self.console = (
            Console.with_prefix(self.__class__.__name__)
            .set_verbosity(self.config.verbosity)
            .set_debug(self.config.is_debug)
        )
        self._device = BaseConfig._resolve_device(self.config.device)
        self._ray_engine_cache: dict[tuple[int, int], tuple[Trimesh, object]] = {}
        self._camera_ray_grid_cache: dict[tuple[object, ...], np.ndarray] = {}

    @property
    def device(self) -> torch.device:
        """Return the Torch device receiving rendered ``Tensor[\"H W\"]`` maps."""

        return self._device

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def render_depth(
        self,
        pose_world_cam: PoseTW,
        mesh: Trimesh,
        camera: CameraTW,
        *,
        frame_index: int | None = None,
        occupancy_extent: Tensor | None = None,
    ) -> Tensor:
        """Render a depth map for a single pose.

        Args:
            pose_world_cam: ``T_world_camera`` pose to render from.
            mesh: Trimesh instance in world coordinates.
            camera: Camera intrinsics/extrinsics (``CameraTW``).
            frame_index: Optional frame index for the calib tensor; defaults
                to the last frame if omitted.
            occupancy_extent: Optional ``[6]`` tensor ``[xmin,xmax,ymin,ymax,zmin,zmax]``
                to expand bounds when synthesising proxy walls.

        Returns:
            Tensor[H, W] on ``config.device`` filled with ``zfar`` on misses.
        """

        if mesh.vertices.size == 0 or mesh.faces.size == 0:
            raise ValueError("Mesh must contain vertices and faces.")

        mesh_use = self._maybe_with_proxy_walls(mesh, occupancy_extent=occupancy_extent)
        cam_single = self._slice_camera(camera, frame_index)
        width, height, fx, fy, cx, cy = self._camera_parameters(cam_single)
        r_wc, t_wc = self._pose_rt(pose_world_cam)

        origins, directions = self._ray_grid(
            width=int(width),
            height=int(height),
            fx=fx,
            fy=fy,
            cx=cx,
            cy=cy,
            r_wc=r_wc,
            t_wc=t_wc,
        )
        depths = self._intersect(mesh_use, origins, directions)
        depth_map = depths.reshape(int(height), int(width))
        hit_ratio = float((depth_map < self.config.zfar).mean())
        if hit_ratio == 0.0:
            self.console.warn(
                "All rays missed the mesh (depth=zfar everywhere). Check poses, mesh bounds, or proxy walls."
            )
        if self.console.is_debug:
            self.console.dbg_summary(
                "depth_stats",
                {"hits_ratio": hit_ratio, "min": float(depth_map.min()), "max": float(depth_map.max())},
            )
        return torch.as_tensor(depth_map, dtype=torch.float32, device=self.device)

    def render_batch(
        self,
        poses: PoseTW,
        mesh: Trimesh,
        camera: CameraTW,
        *,
        frame_index: int | None = None,
        occupancy_extent: Tensor | None = None,
    ) -> torch.Tensor:
        """Render depth for a batch of poses (iterative CPU fallback)."""

        pose_tensor = poses.tensor()
        if pose_tensor.ndim == 1:
            poses_list = [poses]
        else:
            poses_list = [poses[i] for i in range(pose_tensor.shape[0])]

        mesh_use = self._maybe_with_proxy_walls(mesh, occupancy_extent=occupancy_extent)
        cam_single = self._slice_camera(camera, frame_index)
        width, height, fx, fy, cx, cy = self._camera_parameters(cam_single)

        depth_maps: list[torch.Tensor] = []
        for pose in poses_list:
            r_wc, t_wc = self._pose_rt(pose)
            origins, directions = self._ray_grid(
                width=int(width),
                height=int(height),
                fx=fx,
                fy=fy,
                cx=cx,
                cy=cy,
                r_wc=r_wc,
                t_wc=t_wc,
            )
            depths = self._intersect(mesh_use, origins, directions)
            depth_map = depths.reshape(int(height), int(width))
            depth_maps.append(torch.as_tensor(depth_map, dtype=torch.float32, device=self.device))

        return torch.stack(depth_maps, dim=0)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _slice_camera(self, camera: CameraTW, frame_index: int | None) -> CameraTW:
        """Return a single-frame ``CameraTW``."""

        data = camera.tensor()
        if data.ndim == 1:
            return camera
        idx = data.shape[0] - 1 if frame_index is None else frame_index
        idx = max(-data.shape[0], min(data.shape[0] - 1, idx))
        return camera[idx]

    def _camera_parameters(self, camera: CameraTW) -> tuple[float, float, float, float, float, float]:
        """Extract width, height, fx, fy, cx, cy."""

        size = camera.size.squeeze(0)
        focals = camera.f.reshape(-1, 2)
        centers = camera.c.reshape(-1, 2)
        width = float(size[0].item())
        height = float(size[1].item())
        fx = float(focals[0, 0].item())
        fy = float(focals[0, 1].item())
        cx = float(centers[0, 0].item())
        cy = float(centers[0, 1].item())
        return width, height, fx, fy, cx, cy

    def _pose_rt(self, pose_world_cam: PoseTW) -> tuple[np.ndarray, np.ndarray]:
        """Return rotation and translation (world←cam) as numpy arrays."""

        mat = pose_world_cam.matrix
        r_wc = mat[:3, :3] if mat.ndim == 2 else mat[0, :3, :3]
        t_wc = mat[:3, 3] if mat.ndim == 2 else mat[0, :3, 3]
        return r_wc.detach().cpu().numpy(), t_wc.detach().cpu().numpy()

    def _ray_grid(
        self,
        *,
        width: int,
        height: int,
        fx: float,
        fy: float,
        cx: float,
        cy: float,
        r_wc: np.ndarray,
        t_wc: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Generate per-pixel ray origins and directions in world frame."""

        key = (width, height, fx, fy, cx, cy)
        dirs_cam = self._camera_ray_grid_cache.get(key)
        if dirs_cam is None:
            u = np.arange(width, dtype=np.float32)
            v = np.arange(height, dtype=np.float32)
            uu, vv = np.meshgrid(u, v)
            dirs_cam = np.stack([(uu - cx) / fx, (vv - cy) / fy, np.ones_like(uu)], axis=-1)
            norms = np.linalg.norm(dirs_cam, axis=-1, keepdims=True) + 1e-8
            dirs_cam /= norms
            self._camera_ray_grid_cache = {key: dirs_cam}
        dirs_world = dirs_cam.reshape(-1, 3) @ r_wc.T
        origins = np.repeat(t_wc.reshape(1, 3), dirs_world.shape[0], axis=0)
        return origins.astype(np.float32), dirs_world.astype(np.float32)

    def _ray_engine(self, mesh: Trimesh):
        """Return a ray-mesh intersector."""

        key = (id(mesh), hash(mesh), self.config.backend)
        entry = self._ray_engine_cache.get(key)
        if entry is not None:
            return entry[1]

        if self.config.backend in {"auto", "pyembree"}:
            try:
                from trimesh.ray.ray_pyembree import RayMeshIntersector

                engine = RayMeshIntersector(mesh)
                self._ray_engine_cache = {key: (mesh, engine)}
                return engine
            except Exception as exc:  # pragma: no cover - optional dependency
                if self.config.backend == "pyembree":
                    raise ImportError("pyembree backend requested but unavailable") from exc
                self.console.warn("pyembree unavailable; falling back to trimesh.ray.")
        engine = mesh.ray
        self._ray_engine_cache = {key: (mesh, engine)}
        return engine

    def _intersect(self, mesh: Trimesh, origins: np.ndarray, directions: np.ndarray) -> np.ndarray:
        """Chunked ray-mesh intersection returning flat depth array."""

        max_depth = self.config.zfar
        depth = np.full(origins.shape[0], max_depth, dtype=np.float32)
        ray_engine = self._ray_engine(mesh)
        chunk = self.config.chunk_rays
        for start in range(0, origins.shape[0], chunk):
            end = min(start + chunk, origins.shape[0])
            loc, idx, _ = ray_engine.intersects_location(
                ray_origins=origins[start:end],
                ray_directions=directions[start:end],
                multiple_hits=False,
            )
            if len(loc) == 0:
                continue
            hit_orig = origins[start:end][idx]
            dist = np.linalg.norm(loc - hit_orig, axis=1)
            depth[start:end][idx] = dist
        return depth

    def _maybe_with_proxy_walls(
        self,
        mesh: Trimesh,
        occupancy_extent: Tensor | None = None,
    ) -> Trimesh:
        """Append proxy walls if large boundary areas are missing."""

        if not self.config.add_proxy_walls:
            return mesh

        mesh_vmin, mesh_vmax = mesh.bounds
        vmin = mesh_vmin
        vmax = mesh_vmax
        if occupancy_extent is not None and occupancy_extent.numel() == 6:
            extent_cpu = occupancy_extent.detach().cpu().float()
            xmin, xmax, ymin, ymax, zmin, zmax = extent_cpu.tolist()
            occ_vmin = np.array([xmin, ymin, zmin], dtype=np.float32)
            occ_vmax = np.array([xmax, ymax, zmax], dtype=np.float32)
            vmin = np.minimum(mesh_vmin, occ_vmin)
            vmax = np.maximum(mesh_vmax, occ_vmax)

        extents = vmax - vmin
        desired_area = {
            "xmin": extents[1] * extents[2],
            "xmax": extents[1] * extents[2],
            "ymin": extents[0] * extents[2],
            "ymax": extents[0] * extents[2],
            "zmin": extents[0] * extents[1],
            "zmax": extents[0] * extents[1],
        }
        centers = mesh.triangles_center
        areas = mesh.area_faces
        eps = self.config.proxy_eps
        planes = {
            "xmin": centers[:, 0] <= vmin[0] + eps,
            "xmax": centers[:, 0] >= vmax[0] - eps,
            "ymin": centers[:, 1] <= vmin[1] + eps,
            "ymax": centers[:, 1] >= vmax[1] - eps,
            "zmin": centers[:, 2] <= vmin[2] + eps,
            "zmax": centers[:, 2] >= vmax[2] - eps,
        }
        coverage = {k: areas[m].sum() for k, m in planes.items()}
        missing = [
            k
            for k, cov in coverage.items()
            if desired_area[k] > 0 and cov < desired_area[k] * self.config.proxy_wall_area_threshold
        ]
        if not missing:
            return mesh

        box = trimesh.creation.box(
            extents=extents,
            transform=trimesh.transformations.translation_matrix(vmin + extents / 2.0),
        )
        mask_keep = []
        for normal in box.face_normals:
            keep = (
                (np.allclose(normal, [1, 0, 0]) and "xmax" in missing)
                or (np.allclose(normal, [-1, 0, 0]) and "xmin" in missing)
                or (np.allclose(normal, [0, 1, 0]) and "ymax" in missing)
                or (np.allclose(normal, [0, -1, 0]) and "ymin" in missing)
                or (np.allclose(normal, [0, 0, 1]) and "zmax" in missing)
                or (np.allclose(normal, [0, 0, -1]) and "zmin" in missing)
            )
            mask_keep.append(keep)
        mask_keep = np.array(mask_keep, dtype=bool)
        if not mask_keep.any():
            return mesh
        proxy = Trimesh(vertices=box.vertices, faces=box.faces[mask_keep], process=False)
        merged = trimesh.util.concatenate([mesh, proxy])
        if self.console.is_debug:
            self.console.dbg(
                f"Added proxy walls for planes {missing}; proxy faces={proxy.faces.shape[0]}, total={merged.faces.shape[0]}"
            )
        return merged


__all__ = ["Efm3dDepthRenderer", "Efm3dDepthRendererConfig"]
