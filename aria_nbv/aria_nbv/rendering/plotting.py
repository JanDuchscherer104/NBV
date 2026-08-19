"""Plot candidate depth, world-frame geometry, and projected OBB diagnostics.

This module provides depth-grid/histogram helpers, projected-box overlays, and
the :class:`RenderingPlotBuilder` composition surface. It owns display
conversion only; renderers produce metric depth, geometry modules own
projection transforms, and stored camera/OBB data remain immutable.

Display-only CW90/image rotations reconcile physical Aria camera orientation
with Plotly conventions; they never alter stored `PoseTW` or `CameraTW`
geometry.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

import numpy as np
import plotly.express as px  # type: ignore[import-untyped]
import plotly.graph_objects as go  # type: ignore[import-untyped]
import torch
from efm3d.aria import CameraTW, PoseTW
from plotly.subplots import make_subplots  # type: ignore[import-untyped]
from pytorch3d.renderer.cameras import PerspectiveCameras  # type: ignore[import-untyped]
from torch import Tensor

from ..pose_generation.plotting import CandidatePlotBuilder
from ..utils import rotate_yaw_cw90
from ..utils.data_plotting import FrameGridBuilder, _depth_to_color
from .candidate_pointclouds import CandidatePointClouds
from .unproject import backproject_depths_p3d_batch

if TYPE_CHECKING:
    from ..data_handling import EfmSnippetView

_BOX_EDGE_IDX = np.array(
    [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 4),
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),
    ],
    dtype=np.int64,
)


@dataclass(frozen=True, slots=True)
class DepthBoxOverlay:
    """Projected OBB wireframe overlay for one depth-grid panel."""

    corners_px: np.ndarray
    name: str
    color: str
    width: int = 3


def depth_grid(
    depths: Tensor,
    *,
    titles: Iterable[str] | None = None,
    max_cols: int = 3,
    zmax: float | None = None,
    zfar: float | None = None,
) -> go.Figure:
    """Visualise depth maps using the shared image grid utilities."""

    if depths.ndim != 3:
        raise ValueError(f"depth_grid expects (N,H,W) tensor, got shape {tuple(depths.shape)}")

    num = depths.shape[0]
    cols = max(1, min(max_cols, num))
    rows = int(math.ceil(num / cols))
    provided_titles = list(titles) if titles is not None else []
    subplot_titles = [provided_titles[i] if i < len(provided_titles) else f"Candidate {i}" for i in range(num)]

    builder = FrameGridBuilder(
        rows=rows, cols=cols, titles=subplot_titles, height=320 * rows, width=360 * cols, title=""
    )

    vmax = float(depths.max().item()) if zmax is None else zmax
    for idx in range(num):
        r = idx // cols + 1
        c = idx % cols + 1
        depth = depths[idx]
        rgb = _depth_to_color(depth, percentile=99.5)
        rgb = np.rot90(rgb, k=1)
        builder.add_image(rgb, row=r, col=c)

    threshold = zfar if zfar is not None else vmax + 1e-6
    hit_ratio = float(((depths.float() < threshold).float().mean()).item())
    fig = builder.finalize()
    fig.update_layout(title=f"Candidate depth renders (hit_ratio={hit_ratio:.3f})")
    return fig


def depth_grid_with_box_overlays(
    depths: Tensor,
    *,
    overlays: Iterable[Iterable[DepthBoxOverlay]],
    titles: Iterable[str] | None = None,
    max_cols: int = 3,
    zmax: float | None = None,
    zfar: float | None = None,
) -> go.Figure:
    """Visualise depth maps with projected 2D OBB wireframes.

    The image conversion matches `depth_grid`: depth maps are colorized through
    the shared `FrameGridBuilder` path and rotated for display. Overlay pixel
    coordinates are transformed by the same display rotation before Plotly
    scatter traces are added.
    """

    if depths.ndim != 3:
        raise ValueError(f"depth_grid_with_box_overlays expects (N,H,W) tensor, got shape {tuple(depths.shape)}")

    overlay_rows = [list(row) for row in overlays]
    num = depths.shape[0]
    if len(overlay_rows) != num:
        raise ValueError(f"Expected overlays for {num} depth maps, got {len(overlay_rows)}.")

    cols = max(1, min(max_cols, num))
    rows = int(math.ceil(num / cols))
    provided_titles = list(titles) if titles is not None else []
    subplot_titles = [provided_titles[i] if i < len(provided_titles) else f"Candidate {i}" for i in range(num)]

    builder = FrameGridBuilder(
        rows=rows, cols=cols, titles=subplot_titles, height=320 * rows, width=360 * cols, title=""
    )

    vmax = float(depths.max().item()) if zmax is None else zmax
    for idx in range(num):
        row = idx // cols + 1
        col = idx % cols + 1
        depth = depths[idx]
        rgb = _depth_to_color(depth, percentile=99.5)
        rgb = np.rot90(rgb, k=1)
        builder.add_image(rgb, row=row, col=col)
        for overlay in overlay_rows[idx]:
            points = _rotate_pixel_points_for_depth_grid(np.asarray(overlay.corners_px, dtype=float), depth.shape)
            x, y = _projected_box_edges_for_plotly(points)
            if x.size == 0:
                continue
            builder.fig.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    mode="lines",
                    line={"color": overlay.color, "width": overlay.width},
                    name=overlay.name,
                    hoverinfo="name",
                    showlegend=True,
                ),
                row=row,
                col=col,
            )

    threshold = zfar if zfar is not None else vmax + 1e-6
    hit_ratio = float(((depths.float() < threshold).float().mean()).item())
    fig = builder.finalize()
    fig.update_layout(title=f"Candidate depth renders with OBB overlays (hit_ratio={hit_ratio:.3f})")
    return fig


def project_world_points_to_image(
    points_world: Tensor,
    pose_world_cam: PoseTW,
    *,
    focal_px: tuple[float, float],
    principal_point_px: tuple[float, float],
) -> np.ndarray:
    """Project world-frame points into retained selected-depth pixel coordinates."""

    points = torch.as_tensor(points_world, dtype=torch.float32)
    pose = pose_world_cam.to(device=points.device, dtype=points.dtype)
    points_cam = pose.inverse().transform(points.reshape(-1, 3)).reshape(-1, 3)
    z = points_cam[:, 2]
    fx, fy = (float(focal_px[0]), float(focal_px[1]))
    cx, cy = (float(principal_point_px[0]), float(principal_point_px[1]))
    u = points_cam[:, 0] / z.clamp_min(1e-6) * fx + cx
    v = points_cam[:, 1] / z.clamp_min(1e-6) * fy + cy
    projected = torch.stack([u, v], dim=1)
    projected = torch.where((z > 1e-6).unsqueeze(-1), projected, torch.full_like(projected, torch.nan))
    return projected.detach().cpu().numpy()


def _rotate_pixel_points_for_depth_grid(
    points_px: np.ndarray, image_shape_hw: torch.Size | tuple[int, int]
) -> np.ndarray:
    points = np.asarray(points_px, dtype=float).reshape(-1, 2)
    height_width = tuple(int(value) for value in image_shape_hw)
    if len(height_width) != 2:
        raise ValueError(f"Expected image shape (H,W), got {image_shape_hw}.")
    _, width = height_width
    rotated = np.empty_like(points)
    rotated[:, 0] = points[:, 1]
    rotated[:, 1] = float(width - 1) - points[:, 0]
    rotated[~np.isfinite(points).all(axis=1)] = np.nan
    return rotated


def _projected_box_edges_for_plotly(points_px: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    points = np.asarray(points_px, dtype=float).reshape(-1, 2)
    if points.shape != (8, 2):
        raise ValueError(f"Expected projected OBB corners shaped (8,2), got {points.shape}.")
    edges = points[_BOX_EDGE_IDX]
    finite_edge = np.isfinite(edges).all(axis=(1, 2))
    edges = edges[finite_edge]
    if edges.size == 0:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)
    edges_sep = np.concatenate([edges, np.full((edges.shape[0], 1, 2), np.nan, dtype=float)], axis=1)
    flat = edges_sep.reshape(-1, 2)
    return flat[:, 0], flat[:, 1]


def depth_histogram(depths: Tensor, *, bins: int = 50, zfar: float | None = None) -> go.Figure:
    """Histogram of depth values per candidate."""

    if depths.ndim != 3:
        raise ValueError(f"depth_histogram expects (N,H,W) tensor, got {tuple(depths.shape)}")
    depths_np = depths.detach().cpu().numpy()
    num = depths_np.shape[0]
    rows = int(math.ceil(num / 3))
    fig = make_subplots(rows=rows, cols=3, subplot_titles=[f"cand {i}" for i in range(num)])
    for i in range(num):
        r, c = i // 3 + 1, i % 3 + 1
        vals = depths_np[i].reshape(-1)
        if zfar is not None:
            vals = vals[vals < zfar]
        fig.add_trace(go.Histogram(x=vals, nbinsx=bins, name=f"cand {i}", showlegend=False), row=r, col=c)
    fig.update_layout(title="Depth histograms", height=240 * rows)
    return fig


class RenderingPlotBuilder(CandidatePlotBuilder):
    """Rendering-focused extensions on top of `CandidatePlotBuilder`.

    This keeps a single builder hierarchy: SnippetPlotBuilder -> CandidatePlotBuilder -> RenderingPlotBuilder.
    Rendering methods operate on explicit pose/camera/depth inputs and remain usable even when no
    candidate_results are attached.
    """

    def add_frusta_selection(
        self,
        poses: PoseTW,
        camera: CameraTW,
        *,
        color: str = "crimson",
        max_frustums: int = 16,
        name: str = "Rendered frusta",
        display_yaw_cw90: bool = False,
        candidate_indices: list[int] | None = None,
    ) -> Self:
        """Add camera frusta and their image-plane rectangles to the 3D scene."""

        pose_full = self._pose_list_from_input(poses)
        idxs = candidate_indices if candidate_indices is not None else list(range(len(pose_full)))
        pose_list = [pose_full[i] for i in idxs]
        if display_yaw_cw90:
            pose_list = [rotate_yaw_cw90(p) for p in pose_list]

        # Align cameras to poses: accept per-candidate CameraTW or broadcast single.
        if isinstance(camera, CameraTW) and camera.tensor().ndim == 2 and camera.shape[0] > 1:
            cam_full = [camera[i] for i in range(camera.shape[0])]
        else:
            cam_full = [camera]
        if len(cam_full) == 1 and len(pose_full) > 1:
            cam_full = cam_full * len(pose_full)
        cam_list = [cam_full[min(i, len(cam_full) - 1)] for i in idxs]

        # Reuse existing frusta edges from SnippetPlotBuilder for geometry.
        self._add_frusta_for_poses(
            cams=cam_list,
            poses=pose_list,
            scale=1.0,
            color=color,
            name=name,
            max_frustums=max_frustums,
            include_axes=False,
            include_center=False,
        )

        return self

    def add_depth_hits(
        self,
        depths: Tensor,
        poses: PoseTW,
        camera: PerspectiveCameras,
        valid_masks: Tensor,
        *,
        stride: int = 8,
        max_points: int = 20_000,
        color: str = "teal",
        name: str = "Depth hits",
        zfar: float | None = None,
        candidate_indices: list[int] | None = None,
    ) -> Self:
        """Scatter hit points back-projected from rendered depth maps."""

        if depths.ndim != 3:
            raise ValueError(f"depths must be (N,H,W), got {tuple(depths.shape)}")

        all_indices = list(range(min(depths.shape[0], poses.shape[0])))
        use_indices = candidate_indices if candidate_indices is not None else all_indices

        idx_t = torch.tensor(use_indices, device=depths.device)
        padded, lengths = backproject_depths_p3d_batch(
            depths=depths[idx_t],
            mask_valid=valid_masks[idx_t],
            cameras=camera[idx_t],
            stride=stride,
        )
        pts_all = [padded[i, : int(lengths[i].item())] for i in range(len(use_indices)) if lengths[i] > 0]

        if not pts_all:
            return self

        pts_world_t = torch.cat(pts_all, dim=0)
        if pts_world_t.shape[0] > max_points:
            idx = torch.randperm(pts_world_t.shape[0], device=pts_world_t.device)[:max_points]
            pts_world_t = pts_world_t[idx]
        self.add_points(
            pts_world_t,
            name=name,
            color=color,
            size=3,
            opacity=0.8,
        )
        return self

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    @staticmethod
    def _camera_scalar_intrinsics(camera: CameraTW) -> tuple[float, float, float, float, float, float]:
        size = camera.size.reshape(-1, 2)[0].float()
        focals = camera.f.reshape(-1, 2)[0].float()
        centers = camera.c.reshape(-1, 2)[0].float()
        return (
            float(size[0].item()),
            float(size[1].item()),
            float(focals[0].item()),
            float(focals[1].item()),
            float(centers[0].item()),
            float(centers[1].item()),
        )

    @staticmethod
    def _image_plane_corners_world(
        pose: PoseTW,
        *,
        w: float,
        h: float,
        fx: float,
        fy: float,
        cx: float,
        cy: float,
        dist: float,
    ) -> torch.Tensor:
        """Return 4x3 world coords of image-plane corners at distance ``dist``."""

        device = pose.device
        dtype = pose.dtype
        corners_px = torch.tensor(
            [[0.0, 0.0], [w, 0.0], [w, h], [0.0, h]], device=device, dtype=dtype
        )  # TL, TR, BR, BL
        x = (corners_px[:, 0] - cx) / fx * dist
        y = (corners_px[:, 1] - cy) / fy * dist
        z = torch.full_like(x, dist)
        pts_cam = torch.stack([x, y, z], dim=1)
        pts_world = pose.transform(pts_cam)
        return pts_world

    def _backproject_depth(
        self,
        depth: Tensor,
        pose: PoseTW,
        camera: CameraTW,
        *,
        stride: int,
        zfar: float | None = None,
    ) -> torch.Tensor:
        """Back-project a depth map into world points on a strided grid."""

        h, w = depth.shape
        grid_y = torch.arange(0, h, stride, device=depth.device, dtype=depth.dtype)
        grid_x = torch.arange(0, w, stride, device=depth.device, dtype=depth.dtype)
        yy, xx = torch.meshgrid(grid_y, grid_x, indexing="ij")
        depth_s = depth[yy.long(), xx.long()].reshape(-1)
        depth_max = torch.max(depth)
        threshold = depth_max if zfar is None else min(float(zfar), float(depth_max))
        mask = torch.isfinite(depth_s) & (depth_s < threshold * 0.95)
        depth_s = depth_s[mask]
        xx = xx.reshape(-1)[mask]
        yy = yy.reshape(-1)[mask]

        # If nothing valid remains, return empty point set.
        if depth_s.numel() == 0:
            return torch.empty(0, 3, device=depth.device, dtype=depth.dtype)

        # Use the pinhole model matching the PyTorch3D render (intrinsics only; extrinsics via pose).
        cam_single = camera if camera.tensor().ndim == 1 else camera[0]
        _, _, fx, fy, cx, cy = self._camera_scalar_intrinsics(cam_single)
        fx_t = torch.tensor(fx, device=depth.device, dtype=depth.dtype)
        fy_t = torch.tensor(fy, device=depth.device, dtype=depth.dtype)
        cx_t = torch.tensor(cx, device=depth.device, dtype=depth.dtype)
        cy_t = torch.tensor(cy, device=depth.device, dtype=depth.dtype)

        x_cam = (xx - cx_t) / fx_t * depth_s
        y_cam = (yy - cy_t) / fy_t * depth_s
        z_cam = depth_s
        pts_cam = torch.stack([x_cam, y_cam, z_cam], dim=1)
        return pose.transform(pts_cam)


def plot_candidate_pointcloud_scene(
    sample: EfmSnippetView,
    poses: PoseTW,
    camera: CameraTW,
    pointclouds: CandidatePointClouds,
    *,
    candidate_ids: Sequence[int],
    selected_ids: Sequence[int],
    color_map: Mapping[str, str],
    title: str,
    max_sem_pts: int,
    show_frusta: bool,
) -> go.Figure:
    """Plot a snippet and selected candidate point clouds in world coordinates."""

    builder = (
        RenderingPlotBuilder.from_snippet(sample, title=title)
        .add_mesh()
        .add_semidense(last_frame_only=False, max_points=max_sem_pts)
    )
    selected_set = {int(candidate_id) for candidate_id in selected_ids}
    if show_frusta and selected_set:
        candidate_to_local = {int(candidate_id): index for index, candidate_id in enumerate(candidate_ids)}
        selected_local = [
            candidate_to_local[candidate_id] for candidate_id in selected_set if candidate_id in candidate_to_local
        ]
        if selected_local:
            builder.add_frusta_selection(
                poses=poses,
                camera=camera,
                max_frustums=min(16, len(selected_local)),
                candidate_indices=selected_local,
            )

    for index in range(min(len(candidate_ids), pointclouds.points.shape[0])):
        candidate_id = int(candidate_ids[index])
        if candidate_id not in selected_set:
            continue
        points = pointclouds.points[index, : int(pointclouds.lengths[index].item())]
        fallback = px.colors.qualitative.Plotly[index % len(px.colors.qualitative.Plotly)]
        builder.add_points(
            points,
            name=f"Candidate {candidate_id}",
            color=color_map.get(str(candidate_id), fallback),
            size=3,
            opacity=0.7,
        )
    return builder.finalize()


__all__ = [
    "DepthBoxOverlay",
    "depth_grid",
    "depth_grid_with_box_overlays",
    "depth_histogram",
    "project_world_points_to_image",
    "plot_candidate_pointcloud_scene",
    "RenderingPlotBuilder",
]
