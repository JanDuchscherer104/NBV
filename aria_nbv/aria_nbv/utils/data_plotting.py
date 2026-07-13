"""Plotting utilities for the Streamlit data view.

Conventions (efm3d / ATEK):
- Camera frame is **LUF** (x left, y up, z forward) per Project Aria docs; world is Z-up (gravity = [0,0,-g]).
- Pose: T_world_cam = T_world_rig @ T_camera_rig.inverse() (matches efm3d.render_frustum).
- Images are rotated -90° for display using rotate_yaw_cw90.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Self

import numpy as np
import plotly.graph_objects as go  # type: ignore[import-untyped]
import torch
import trimesh
from efm3d.aria.camera import CameraTW
from efm3d.aria.obb import ObbTW
from efm3d.aria.pose import PoseTW
from matplotlib import colormaps
from plotly import colors as plotly_colors
from plotly.subplots import make_subplots  # type: ignore[import-untyped]

from ..data_handling import EfmSnippetView
from ..data_handling.raw.views import EfmCameraView
from .console import Console
from .frames import rotate_yaw_cw90

console = Console.with_prefix("plotting")
ROTATE_90_CW = -1
BBOX_EDGE_IDX = np.array(
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


def pose_world_cam(
    sample: EfmSnippetView,
    cam_view: EfmCameraView,
    frame_idx: int,
) -> tuple[PoseTW, CameraTW]:
    """Return the world<-camera pose and camera intrinsics for a given frame."""
    cam_ts = cam_view.time_ns.cpu().numpy()
    traj_ts = sample.trajectory.time_ns.cpu().numpy()
    traj_idx = int(np.argmin(np.abs(traj_ts - cam_ts[frame_idx])))

    t_world_rig = sample.trajectory.t_world_rig[traj_idx]
    t_cam_rig = cam_view.calib.T_camera_rig[frame_idx]
    return t_world_rig @ t_cam_rig.inverse(), cam_view.calib[frame_idx]


def semidense_points_for_frame(
    sample: EfmSnippetView,
    frame_idx: int | None,
    *,
    all_frames: bool,
) -> torch.Tensor:
    """Collect semidense points for one frame or the full snippet."""
    sem = sample.semidense
    if sem is None or sem.points_world.numel() == 0:
        return torch.zeros((0, 3), dtype=torch.float32)

    pts = sem.points_world
    lengths = sem.lengths
    if all_frames:
        if lengths is not None:
            max_len = pts.shape[1]
            mask_valid = torch.arange(max_len, device=pts.device).unsqueeze(
                0,
            ) < lengths.clamp_max(max_len).unsqueeze(
                -1,
            )
            pts = torch.where(mask_valid.unsqueeze(-1), pts, torch.nan)
        pts = pts.reshape(-1, 3)
    else:
        if frame_idx is None:
            frame_idx = int(torch.argmax(lengths).item()) if lengths.numel() else 0
        frame_idx = max(0, min(int(frame_idx), pts.shape[0] - 1))
        n_valid = int(lengths[frame_idx].item()) if lengths is not None else pts.shape[1]
        pts = pts[frame_idx, :n_valid]

    finite = torch.isfinite(pts).all(dim=-1)
    return pts[finite]


def get_frustum_segments(
    cam: CameraTW,
    pose_world_cam: PoseTW,
    scale: float = 1.0,
) -> list[np.ndarray]:
    """Return frustum wireframe segments in world frame using CameraTW.unproject.

    The four image-plane corners are first unprojected in the camera's intrinsic
    frame, then transformed to world frame using pose_world_cam.
    """
    # Keep all intermediate tensors on the same device/dtype as the camera to
    # avoid CPU/GPU mismatches when candidate poses live on CUDA.
    pose_world_cam = pose_world_cam.to(device=cam.device, dtype=cam.dtype)

    # Construct four pixel corners on an inscribed square
    c = cam.c.squeeze(0)  # (2,)
    rs = cam.valid_radius.squeeze(0) / np.sqrt(2.0)  # inscribed square radius per axis

    corners_px = torch.stack(
        [
            c + torch.tensor([-rs[0], -rs[1]], device=cam.device, dtype=cam.dtype),  # TL
            c + torch.tensor([-rs[0], rs[1]], device=cam.device, dtype=cam.dtype),  # BL
            c + torch.tensor([rs[0], rs[1]], device=cam.device, dtype=cam.dtype),  # BR
            c + torch.tensor([rs[0], -rs[1]], device=cam.device, dtype=cam.dtype),  # TR
        ],
        dim=0,
    ).unsqueeze(0)  # 1 x 4 x 2

    # Unproject to camera-frame rays (LUF) and normalise
    rays_cam = cam.unproject(corners_px)[0].squeeze(0)  # 4 x 3
    rays_cam = torch.nn.functional.normalize(rays_cam, dim=-1, eps=1e-6)
    frustum_cam = rays_cam * scale  # 4 x 3

    # Transform to world frame and build triangular faces
    frustum_np = pose_world_cam.transform(frustum_cam).detach().cpu().numpy()  # (4, 3)
    center_np = pose_world_cam.t.detach().cpu().numpy()  # (3,)

    segments: list[np.ndarray] = []
    ring_edges = [(0, 1), (1, 2), (2, 3), (3, 0)]
    for i, j in ring_edges:
        segments.append(np.vstack([center_np, frustum_np[i], frustum_np[j]]))

    # Top-edge "hat": offset along physical camera +Y
    edge_top = (frustum_np[2], frustum_np[1])
    mid_top = 0.5 * (edge_top[0] + edge_top[1])

    # camera +Y = "up" in LUF
    up_dir = pose_world_cam.R @ torch.tensor([0.0, 1.0, 0.0], device=cam.device, dtype=cam.dtype)

    up_dir_np = up_dir.detach().cpu().numpy()
    up_dir_np = up_dir_np / np.linalg.norm(up_dir_np)

    hat_h = 0.1 * scale  # height of the cue relative to frustum scale
    top_pts = np.array(
        [
            edge_top[0] + hat_h * up_dir_np,
            mid_top + 2.5 * hat_h * up_dir_np,
            edge_top[1] + hat_h * up_dir_np,
        ]
    )
    segments.append(top_pts)

    return segments


def bbox_edges(min_pt: np.ndarray, max_pt: np.ndarray) -> np.ndarray:
    """Return AABB wireframe segments as (2, 3) arrays in Plotly order.

    Args:
        min_pt: XYZ lower bounds (metres) for the axis-aligned box.
        max_pt: XYZ upper bounds (metres) for the axis-aligned box.

    Returns:
        Array of shape ``(12, 2, 3)`` ready for ``Scatter3d``. The edge ordering
        matches the efm3d frustum/box helpers to keep consistent legend/colour
        usage when overlaying boxes.
    """

    min_pt = np.asarray(min_pt, dtype=float).reshape(3)
    max_pt = np.asarray(max_pt, dtype=float).reshape(3)

    corners = np.array(
        [
            [min_pt[0], min_pt[1], min_pt[2]],
            [max_pt[0], min_pt[1], min_pt[2]],
            [max_pt[0], max_pt[1], min_pt[2]],
            [min_pt[0], max_pt[1], min_pt[2]],
            [min_pt[0], min_pt[1], max_pt[2]],
            [max_pt[0], min_pt[1], max_pt[2]],
            [max_pt[0], max_pt[1], max_pt[2]],
            [min_pt[0], max_pt[1], max_pt[2]],
        ],
        dtype=float,
    )
    return corners[BBOX_EDGE_IDX]


def _flatten_edges_for_plotly(edges: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert ``(N, 2, 3)`` edges to NaN-separated XYZ for a single Scatter3d trace."""

    edges = np.asarray(edges, dtype=float).reshape(-1, 2, 3)
    edges_sep = np.concatenate([edges, np.full((edges.shape[0], 1, 3), np.nan, dtype=float)], axis=1)
    flat = edges_sep.reshape(-1, 3)
    return flat[:, 0], flat[:, 1], flat[:, 2]


def mesh_to_plotly(
    mesh: trimesh.Trimesh,
) -> go.Mesh3d:
    """Convert a Trimesh to Plotly Mesh3d traces."""

    vertices = mesh.vertices
    faces = mesh.faces

    return go.Mesh3d(
        x=vertices[:, 0],
        y=vertices[:, 1],
        z=vertices[:, 2],
        i=faces[:, 0],
        j=faces[:, 1],
        k=faces[:, 2],
        color="lightgray",
        opacity=0.35,
        flatshading=True,
        lighting={"ambient": 1.0, "diffuse": 0.3, "specular": 0.0, "fresnel": 0.0, "roughness": 1.0},
        name="GT Mesh",
        hoverinfo="skip",
    )


def _pose_positions(poses: PoseTW | torch.Tensor) -> np.ndarray:
    """Return positions (...,3) as numpy from PoseTW or compatible tensor shapes."""

    arr = poses.t if isinstance(poses, PoseTW) else poses

    if arr.dim() == 2 and arr.shape == torch.Size([3, 4]):
        pos = arr[:3, 3].unsqueeze(0)
    elif arr.dim() == 2 and arr.shape[1] == 12:
        pos = arr.view(-1, 3, 4)[..., :3, 3]
    elif arr.dim() == 3 and arr.shape[1:] == (3, 4):
        pos = arr[..., :3, 3]
    elif arr.dim() == 2 and arr.shape[1] == 3:
        pos = arr
    else:
        pos = arr[..., :3]
    return pos.detach().cpu().numpy()


class SnippetPlotBuilder:
    """Composable builder for mesh/points/frusta visuals using a stored snippet.

    All data comes from the snippet; methods only accept visual/customisation params.
    """

    def __init__(self, snippet: EfmSnippetView, *, title: str, height: int = 900):
        self.snippet = snippet
        self.fig = go.Figure()
        self.title = title
        self.height = height
        self._bounds = self._compute_bounds()
        self.scene_ranges = self._build_scene_ranges(*self._bounds)

    @classmethod
    def from_snippet(cls, snippet: EfmSnippetView, *, title: str, height: int = 900) -> Self:
        return cls(snippet, title=title, height=height)

    def _default_scene_ranges(self) -> dict:
        self._bounds = self._compute_bounds()
        return self._build_scene_ranges(*self._bounds)

    def _compute_bounds(self) -> tuple[np.ndarray, np.ndarray]:
        mesh = self.snippet.mesh
        traj_positions = self.snippet.trajectory.t_world_rig.t.detach().cpu().numpy()
        pts_np = np.zeros((0, 3), dtype=np.float32)
        sem = self.snippet.semidense
        if sem is not None and hasattr(sem, "points_world"):
            pts_np = sem.last_frame_points_np(20000)

        bbox = np.vstack(
            [
                pts_np,
                traj_positions,
                mesh.vertices if mesh is not None else np.zeros((0, 3)),
            ]
        )
        finite_mask = np.isfinite(bbox).all(axis=1)
        bbox = bbox[finite_mask]
        if bbox.shape[0] == 0:
            bbox = np.array([[0.0, 0.0, 0.0]])

        vmin, vmax = bbox.min(axis=0), bbox.max(axis=0)
        return vmin, vmax

    def _build_scene_ranges(self, vmin: np.ndarray, vmax: np.ndarray) -> dict:
        max_extent = (vmax - vmin).max()
        padding = max(0.5, 0.1 * max_extent)
        return {
            "xaxis": {"title": "X (m)", "range": [float(vmin[0] - padding), float(vmax[0] + padding)]},
            "yaxis": {"title": "Y (m)", "range": [float(vmin[1] - padding), float(vmax[1] + padding)]},
            "zaxis": {"title": "Z (m)", "range": [float(vmin[2] - padding), float(vmax[2] + padding)]},
        }

    def _update_scene_ranges(self, pts: np.ndarray) -> None:
        pts_np = np.asarray(pts)
        pts_np = np.atleast_2d(pts_np)
        if pts_np.shape[1] != 3:
            pts_np = pts_np.reshape(-1, 3)

        finite = np.isfinite(pts_np).all(axis=1)
        if not finite.any():
            return
        vmin, vmax = self._bounds
        pts_min = pts_np[finite].min(axis=0)
        pts_max = pts_np[finite].max(axis=0)
        vmin = np.minimum(vmin, pts_min)
        vmax = np.maximum(vmax, pts_max)
        self._bounds = (vmin, vmax)
        self.scene_ranges = self._build_scene_ranges(vmin, vmax)

    def add_mesh(self, *, color: str = "lightgray", opacity: float = 0.35) -> Self:
        mesh = self.snippet.mesh
        if mesh is None:
            return self
        trace = mesh_to_plotly(mesh)
        trace.update(color=color, opacity=opacity)
        self.fig.add_trace(trace)
        return self

    def add_semidense(
        self,
        *,
        name: str = "Semidense points",
        max_points: int | None = 20000,
        last_frame_only: bool = True,
        color: str = "Viridis",
    ) -> Self:
        sem = self.snippet.semidense
        if sem is None:
            return self
        pts_np = (
            sem.last_frame_points_np(max_points) if last_frame_only else sem.collapse_points(max_points).cpu().numpy()
        )
        if pts_np.size == 0:
            return self
        self.fig.add_trace(
            go.Scatter3d(
                x=pts_np[:, 0],
                y=pts_np[:, 1],
                z=pts_np[:, 2],
                mode="markers",
                marker={"size": 2, "color": pts_np[:, 2], "colorscale": color, "opacity": 0.5},
                name=name,
            )
        )
        return self

    def add_semidense_in_oriented_box(
        self,
        *,
        pose_world_object: np.ndarray | torch.Tensor | PoseTW | Sequence[float],
        extents: np.ndarray | torch.Tensor | Sequence[float],
        name: str = "Target semidense points",
        max_points: int | None = 20000,
        last_frame_only: bool = False,
        color: str = "gold",
        size: int = 3,
        opacity: float = 0.8,
    ) -> Self:
        """Add semidense points cropped by a world-frame oriented box."""

        sem = self.snippet.semidense
        if sem is None:
            return self
        pts_np = (
            sem.last_frame_points_np(max_points) if last_frame_only else sem.collapse_points(max_points).cpu().numpy()
        )
        if pts_np.size == 0:
            return self
        points = torch.as_tensor(pts_np[:, :3], dtype=torch.float32)
        pose = self._pose_from_tw_payload(pose_world_object).to(device=points.device, dtype=points.dtype)
        extents_np = (
            extents.detach().cpu().numpy()
            if isinstance(extents, torch.Tensor)
            else np.asarray(extents, dtype=np.float32)
        )
        half = torch.as_tensor(extents_np.reshape(3), dtype=points.dtype, device=points.device) / 2.0
        local = pose.inverse().transform(points)
        mask = (local.abs() <= half.reshape(1, 3)).all(dim=1)
        cropped = points[mask].detach().cpu().numpy()
        if cropped.size == 0:
            return self
        return self.add_points(cropped, name=name, color=color, size=size, opacity=opacity)

    def add_points(
        self,
        points: np.ndarray | torch.Tensor | PoseTW,
        *,
        name: str = "Points",
        color: str = "royalblue",
        size: int = 4,
        opacity: float = 0.7,
        symbol: str = "circle",
    ) -> Self:
        """Scatter arbitrary 3D points onto the figure and update bounds."""

        pts_np = _pose_positions(points) if isinstance(points, (PoseTW, torch.Tensor)) else np.asarray(points)
        pts_np = np.array(pts_np, copy=False)
        if pts_np.ndim == 1:
            pts_np = pts_np.reshape(1, -1)
        if pts_np.size == 0:
            return self

        self._update_scene_ranges(pts_np)
        self.fig.add_trace(
            go.Scatter3d(
                x=pts_np[:, 0],
                y=pts_np[:, 1],
                z=pts_np[:, 2],
                mode="markers",
                marker={"size": size, "color": color, "opacity": opacity, "symbol": symbol},
                name=name,
            )
        )
        return self

    def add_trajectory(
        self,
        *,
        mark_first_last: bool = True,
        first_color: str = "green",
        last_color: str = "red",
        show: bool = True,
    ) -> Self:
        if not show:
            return self
        traj_positions = self.snippet.trajectory.t_world_rig.t.detach().cpu().numpy()
        traj_x, traj_y, traj_z = traj_positions.T
        self.fig.add_trace(
            go.Scatter3d(
                x=traj_x,
                y=traj_y,
                z=traj_z,
                mode="lines+markers",
                marker={"size": 3, "color": "black"},
                line={"color": "black", "width": 4},
                name="Trajectory",
            )
        )
        if mark_first_last and traj_positions.shape[0] > 0:
            first = traj_positions[0]
            last = traj_positions[-1]
            self.fig.add_trace(
                go.Scatter3d(
                    x=[first[0]],
                    y=[first[1]],
                    z=[first[2]],
                    mode="markers",
                    marker={"size": 4, "color": first_color, "symbol": "diamond"},
                    name="Start",
                )
            )
            if traj_positions.shape[0] > 1:
                self.fig.add_trace(
                    go.Scatter3d(
                        x=[last[0]],
                        y=[last[1]],
                        z=[last[2]],
                        mode="markers",
                        marker={"size": 4, "color": last_color, "symbol": "x"},
                        name="Final",
                    )
                )
        return self

    def add_frusta(
        self,
        *,
        camera: Literal["rgb", "slaml", "slamr"] = "rgb",
        frame_indices: list[int] | None = None,
        scale: float = 1.0,
        include_axes: bool = True,
        include_center: bool = True,
        is_rotate_yaw_cw90: bool = True,
        name: str = "Frustum",
    ) -> Self:
        cam_view = self.snippet.get_camera(camera)
        traj = self.snippet.trajectory
        cam_idx, traj_idx = cam_view.nearest_traj_indices(traj.time_ns, frame_indices, default_last=False)
        if cam_idx.numel() == 0 or traj_idx.numel() == 0:
            return self

        t_world_rig = traj.t_world_rig[traj_idx]
        t_cam_rig = cam_view.calib.T_camera_rig[cam_idx]
        t_world_cam = t_world_rig @ t_cam_rig.inverse()
        if is_rotate_yaw_cw90:
            t_world_cam = rotate_yaw_cw90(t_world_cam)

        pose_list = self._pose_list_from_input(t_world_cam)
        cam_list = cam_view.calib[cam_idx]

        self._add_frusta_for_poses(
            cams=cam_list,
            poses=pose_list,
            scale=scale,
            color="red",
            name=name,
            max_frustums=None,
            include_axes=include_axes,
            include_center=include_center,
        )
        return self

    def add_frame_axes(
        self,
        *,
        frame: Literal["rgb", "slaml", "slamr", "rig"] | PoseTW = "rgb",
        frame_indices: list[int] | None = None,
        title: str = "Frame axes",
        is_rotate_yaw_cw90: bool = True,
    ) -> Self:
        """Add axes for a camera stream or the rig itself.

        Args:
            frame: Camera label, "rig" for the rig frame to retrieve the poses form `sample.trajectory`, or a custom PoseTW.
            If frame is a PoseTW it must be
        """

        if isinstance(frame, PoseTW):
            t_world_frame = frame
        else:
            traj = self.snippet.trajectory
            if traj.time_ns.shape.numel() == 0:
                console.warn("No trajectory data; cannot add frame axes.")
                return self

            if frame == "rig":
                # Anchor rig axes to camera timestamps for consistent indexing/alignment.
                cam_view = self.snippet.get_camera("rgb")
                if cam_view is None:
                    console.warn("No camera stream available; cannot add rig axes.")
                    return self

                cam_idx, traj_idx = cam_view.nearest_traj_indices(traj.time_ns, frame_indices, default_last=True)
                if cam_idx.numel() == 0 or traj_idx.numel() == 0:
                    console.warn("No valid frame indices for rig axes.")
                    return self

                t_world_frame = traj.t_world_rig[traj_idx]
            else:
                cam_view = self.snippet.get_camera(frame)
                n_cam = cam_view.num_frames
                if n_cam == 0:
                    return self
                cam_idx, traj_idx = cam_view.nearest_traj_indices(traj.time_ns, frame_indices, default_last=True)
                if cam_idx.numel() == 0 or traj_idx.numel() == 0:
                    return self

                t_world_rig = traj.t_world_rig[traj_idx]  # PoseTW[K]
                t_cam_rig = cam_view.calib.T_camera_rig[cam_idx]  # PoseTW[K]
                t_world_frame = t_world_rig @ t_cam_rig.inverse()

        if is_rotate_yaw_cw90:
            t_world_frame = rotate_yaw_cw90(t_world_frame)
        centers = t_world_frame.t.detach().cpu().numpy()
        axes = t_world_frame.R.detach().cpu().numpy()  # (K, 3, 3)

        self._update_scene_ranges(centers)
        self._add_camera_axes(centers, axes, title)

        return self

    # Backwards compatibility shim
    def add_camera_axes(
        self,
        *,
        camera: Literal["rgb", "slaml", "slamr"] = "rgb",
        frame_indices: list[int] | None = None,
        title: str = "Camera axes",
    ) -> Self:
        return self.add_frame_axes(frame=camera, frame_indices=frame_indices, title=title)

    @staticmethod
    def add_frame_axes_to_fig(
        fig: go.Figure, cam_centers: np.ndarray, cam_axes: np.ndarray, title: str = "Camera axes", scale: float = 1.0
    ) -> go.Figure:
        """Add LUF axes for multiple cameras in one go."""

        if cam_centers.ndim == 1:
            cam_centers = cam_centers.reshape(1, 3)
        if cam_axes.ndim == 2:
            cam_axes = cam_axes.reshape(1, 3, 3)

        axis_colors = ["red", "green", "blue"]
        for axis, color in enumerate(axis_colors):
            axis_start = cam_centers
            axis_end = cam_centers + cam_axes[:, axis] * scale
            seg = np.stack([axis_start, axis_end], axis=1)  # (K, 2, 3)
            seg = np.concatenate([seg, np.full((seg.shape[0], 1, 3), np.nan, dtype=float)], axis=1).reshape(-1, 3)
            fig.add_trace(
                go.Scatter3d(
                    x=seg[:, 0],
                    y=seg[:, 1],
                    z=seg[:, 2],
                    mode="lines",
                    line={"color": color, "width": 8},
                    name=title if axis == 0 else None,
                    showlegend=axis == 0,
                )
            )

        return fig

    def _add_camera_axes(self, cam_centers: np.ndarray, cam_axes: np.ndarray, title: str = "Camera axes") -> Self:
        """Add LUF axes for multiple cameras in one go."""

        self.fig = self.add_frame_axes_to_fig(self.fig, cam_centers, cam_axes, title=title, scale=0.4)

        return self

    def _add_camera_center(self, cam_center: np.ndarray, *, color: str = "red", symbol: str = "diamond") -> Self:
        self.fig.add_trace(
            go.Scatter3d(
                x=[cam_center[0]],
                y=[cam_center[1]],
                z=[cam_center[2]],
                mode="markers",
                marker={"size": 10, "color": color, "symbol": symbol},
                name="Camera center",
            )
        )
        return self

    def _pose_list_from_input(self, poses: Sequence[PoseTW] | PoseTW | torch.Tensor) -> list[PoseTW]:
        if isinstance(poses, PoseTW):
            mat = poses.matrix3x4
            if mat.dim() == 3:
                return [PoseTW.from_matrix3x4(m) for m in mat]
            return [poses]
        if isinstance(poses, torch.Tensor):
            tensor = poses
            if tensor.dim() == 2 and tensor.shape[1] == 12:
                tensor = tensor.view(-1, 3, 4)
            if tensor.dim() == 2 and tensor.shape == torch.Size([3, 4]):
                tensor = tensor.unsqueeze(0)
            if tensor.dim() == 3 and tensor.shape[1:] == (3, 4):
                return [PoseTW.from_matrix3x4(t) for t in tensor]
            if tensor.dim() == 2 and tensor.shape[1] == 3:
                return [PoseTW.from_Rt(torch.eye(3, device=tensor.device, dtype=tensor.dtype), tensor)]
            raise ValueError(f"Unsupported pose tensor shape: {tuple(tensor.shape)}")
        if isinstance(poses, Sequence):
            pose_list: list[PoseTW] = []
            for item in poses:
                if isinstance(item, PoseTW):
                    pose_list.append(item)
                elif isinstance(item, torch.Tensor):
                    pose_list.append(PoseTW.from_matrix3x4(item))
                else:
                    raise TypeError(f"Unsupported pose element type: {type(item)!r}")
            return pose_list
        raise TypeError(f"Unsupported poses input type: {type(poses)!r}")

    def _center_from_input(self, center: np.ndarray | torch.Tensor | PoseTW) -> np.ndarray:
        if isinstance(center, PoseTW):
            return center.t.detach().cpu().numpy()
        if isinstance(center, torch.Tensor):
            arr = center.detach().cpu().numpy()
            return arr.reshape(-1, 3)[0]
        arr_np = np.asarray(center)
        return arr_np.reshape(-1, 3)[0]

    def _pose_from_tw_payload(self, pose: np.ndarray | torch.Tensor | PoseTW | Sequence[float]) -> PoseTW:
        """Return a single `PoseTW` from a flattened PoseTW or matrix payload."""

        if isinstance(pose, PoseTW):
            data = pose.tensor().detach().cpu().to(dtype=torch.float32)
            if data.ndim > 1:
                data = data.reshape(-1, data.shape[-1])[0]
            return PoseTW(data)
        if isinstance(pose, torch.Tensor):
            data_np = pose.detach().cpu().numpy()
        else:
            data_np = np.asarray(pose, dtype=np.float32)
        data_np = np.asarray(data_np, dtype=np.float32)
        if data_np.shape == (3, 4):
            return PoseTW.from_matrix3x4(torch.from_numpy(data_np))
        if data_np.shape == (4, 4):
            return PoseTW.from_matrix3x4(torch.from_numpy(data_np[:3, :4]))
        flat = data_np.reshape(-1)
        if flat.size != 12:
            raise ValueError(f"Expected a flattened PoseTW payload with 12 values, got {flat.size}.")
        return PoseTW(torch.from_numpy(flat.astype(np.float32, copy=False)))

    def add_oriented_box_corners(
        self,
        corners_world: np.ndarray | torch.Tensor,
        *,
        name: str,
        color: str,
        width: int = 5,
        opacity: float = 0.95,
    ) -> Self:
        """Add one or more oriented boxes from world-frame corners."""

        corners_np = (
            corners_world.detach().cpu().numpy()
            if isinstance(corners_world, torch.Tensor)
            else np.asarray(corners_world)
        )
        corners_np = np.asarray(corners_np, dtype=float)
        if corners_np.ndim == 2:
            corners_np = corners_np.reshape(1, 8, 3)
        if corners_np.shape[-2:] != (8, 3):
            raise ValueError(f"Expected OBB corners shaped (8, 3) or (K, 8, 3), got {corners_np.shape}.")

        self._update_scene_ranges(corners_np.reshape(-1, 3))
        edges = corners_np[:, BBOX_EDGE_IDX]
        x, y, z = _flatten_edges_for_plotly(edges.reshape(-1, 2, 3))
        self.fig.add_trace(
            go.Scatter3d(
                x=x,
                y=y,
                z=z,
                mode="lines",
                line={"color": color, "width": width},
                name=name,
                showlegend=True,
                opacity=opacity,
                hoverinfo="name",
            )
        )
        return self

    def add_oriented_box(
        self,
        *,
        pose_world_object: np.ndarray | torch.Tensor | PoseTW | Sequence[float],
        extents: np.ndarray | torch.Tensor | Sequence[float],
        name: str,
        color: str,
        width: int = 5,
        opacity: float = 0.95,
    ) -> Self:
        """Add an oriented box from a world<-object pose and XYZ side lengths."""

        pose = self._pose_from_tw_payload(pose_world_object)
        extents_np = (
            extents.detach().cpu().numpy()
            if isinstance(extents, torch.Tensor)
            else np.asarray(extents, dtype=np.float32)
        )
        half = np.asarray(extents_np, dtype=np.float32).reshape(3) / 2.0
        signs = np.array(
            [[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1], [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]],
            dtype=np.float32,
        )
        local = torch.from_numpy(signs * half).to(device=pose.device, dtype=pose.dtype)
        corners = pose.transform(local)
        return self.add_oriented_box_corners(
            corners,
            name=name,
            color=color,
            width=width,
            opacity=opacity,
        )

    def add_obb(
        self,
        obb: ObbTW,
        *,
        name: str,
        color: str,
        width: int = 5,
        opacity: float = 0.95,
    ) -> Self:
        """Add one or more `ObbTW` boxes using their world-frame corners."""

        return self.add_oriented_box_corners(
            obb.bb3corners_world,
            name=name,
            color=color,
            width=width,
            opacity=opacity,
        )

    def _add_frusta_for_poses(
        self,
        *,
        cams: CameraTW | Sequence[CameraTW],
        poses: Sequence[PoseTW] | PoseTW,
        scale: float,
        color: str,
        name: str,
        max_frustums: int | None,
        include_axes: bool,
        include_center: bool,
    ) -> Self:
        pose_list = self._pose_list_from_input(poses)
        if max_frustums is not None and len(pose_list) > max_frustums:
            ids = np.linspace(0, len(pose_list) - 1, num=max_frustums, dtype=int)
            pose_list = [pose_list[int(i)] for i in ids]

        if isinstance(cams, CameraTW):
            cam_len = cams.shape[0] if cams.ndim > 1 else 1
            if cam_len > 1:
                cam_list = [cams[i] for i in range(cam_len)]
            else:
                cam_list = [cams]
        elif isinstance(cams, Sequence):
            cam_list = list(cams)
        else:
            raise TypeError(f"Unsupported cams input type: {type(cams)!r}")

        if len(cam_list) == 1 and len(pose_list) > 1:
            cam_list = cam_list * len(pose_list)

        seg_points_all: list[np.ndarray] = []
        seg_traces: list[np.ndarray] = []
        for idx, pose in enumerate(pose_list):
            cam_for_pose = cam_list[min(idx, len(cam_list) - 1)]
            frustum_segments = get_frustum_segments(cam_for_pose, pose, scale=scale)
            seg_points = np.vstack(frustum_segments)
            seg_points_all.append(seg_points)

            seg_with_breaks = np.concatenate(
                [np.vstack([seg, np.full((1, 3), np.nan, dtype=float)]) for seg in frustum_segments],
                axis=0,
            )
            seg_traces.append(seg_with_breaks)

        if seg_traces:
            all_segments = np.concatenate(seg_traces, axis=0)
            self._update_scene_ranges(np.vstack(seg_points_all))
            self.fig.add_trace(
                go.Scatter3d(
                    x=all_segments[:, 0],
                    y=all_segments[:, 1],
                    z=all_segments[:, 2],
                    mode="lines",
                    line={"color": color, "width": 4},
                    name=name,
                    showlegend=True,
                )
            )

        if include_axes or include_center:
            cam_centers = np.stack([p.t.detach().cpu().numpy() for p in pose_list], axis=0)
            cam_axes = np.stack([p.R.detach().cpu().numpy().T for p in pose_list], axis=0)
            if include_axes:
                self._add_camera_axes(cam_centers, cam_axes)
            if include_center and cam_centers.size > 0:
                self._add_camera_center(cam_centers[0], color=color)
            self._update_scene_ranges(cam_centers)
        return self

    def add_bounds_box(
        self,
        *,
        name: str,
        color: str = "gray",
        dash: str = "dash",
        width: int = 2,
        aabb: tuple[np.ndarray, np.ndarray] | None = None,
    ) -> Self:
        if aabb is None:
            sem = self.snippet.semidense
            if sem is not None and hasattr(sem, "volume_min") and hasattr(sem, "volume_max"):
                min_pt = sem.volume_min.detach().cpu().numpy()
                max_pt = sem.volume_max.detach().cpu().numpy()
            else:
                traj_positions = self.snippet.trajectory.t_world_rig.t.detach().cpu().numpy()
                min_pt, max_pt = traj_positions.min(axis=0), traj_positions.max(axis=0)
        else:
            min_pt, max_pt = aabb

        edges = bbox_edges(min_pt, max_pt)
        x, y, z = _flatten_edges_for_plotly(edges)
        self.fig.add_trace(
            go.Scatter3d(
                x=x,
                y=y,
                z=z,
                mode="lines",
                line={"color": color, "width": width, "dash": dash},
                name=name,
                showlegend=True,
                hoverinfo="skip",
            )
        )
        return self

    def add_gt_obbs(
        self,
        *,
        camera: str = "rgb",
        timestamp: str | int | None = None,
        color: str = "purple",
        name: str = "GT OBBs",
        opacity: float = 0.35,
    ) -> Self:
        """Add oriented boxes defined by world←object poses and dimensions."""

        if self.snippet.gt is None:
            return self

        ts_key = (
            timestamp
            if timestamp is not None
            else (self.snippet.gt.timestamps[0] if self.snippet.gt.timestamps else None)
        )
        if ts_key is None:
            return self

        cam_id_map = {"rgb": "camera-rgb", "slam-l": "camera-slam-left", "slamr": "camera-slamright"}
        try:
            cam_gt = self.snippet.gt.cameras_at(ts_key)[cam_id_map.get(camera, "camera-rgb")]
        except KeyError:
            return self

        ts_world_object = cam_gt.ts_world_object.detach().cpu().numpy()
        object_dimensions = cam_gt.object_dimensions.detach().cpu().numpy()
        if ts_world_object.size == 0 or object_dimensions.size == 0:
            return self

        signs = np.array(
            [[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1], [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]],
            dtype=float,
        )
        half_dims = object_dimensions / 2.0  # (K, 3)
        local = half_dims[:, None, :] * signs[None, :, :]  # (K, 8, 3)
        corners = np.einsum("kij,kmj->kmi", ts_world_object[:, :3, :3], local) + ts_world_object[:, None, :3, 3]
        corners_flat = corners.reshape(-1, 3)
        self._update_scene_ranges(corners_flat)

        cat_ids = np.asarray(cam_gt.category_ids.detach().cpu().numpy()) if hasattr(cam_gt, "category_ids") else None
        cat_names = np.asarray(cam_gt.category_names) if hasattr(cam_gt, "category_names") else None

        if cat_ids is None or cat_ids.size == 0:
            edges = corners[:, BBOX_EDGE_IDX]  # (K, 12, 2, 3)
            x, y, z = _flatten_edges_for_plotly(edges.reshape(-1, 2, 3))
            self.fig.add_trace(
                go.Scatter3d(
                    x=x,
                    y=y,
                    z=z,
                    mode="lines",
                    line={"color": color, "width": 3},
                    name=name,
                    showlegend=True,
                    opacity=opacity,
                )
            )
            return self

        unique_ids, inv = np.unique(cat_ids, return_inverse=True)

        def _rgb_to_hex(rgb: tuple[float, float, float]) -> str:
            return plotly_colors.label_rgb(tuple(int(255 * c) for c in rgb))

        palette = colormaps.get_cmap("tab20")
        id_to_color = {
            uid: _rgb_to_hex(palette(idx / max(1, len(unique_ids) - 1))[:3]) for idx, uid in enumerate(unique_ids)
        }

        edges = corners[:, BBOX_EDGE_IDX]  # (K, 12, 2, 3)
        for cls_idx, uid in enumerate(unique_ids):
            mask = inv == cls_idx
            edges_cls = edges[mask]
            if edges_cls.size == 0:
                continue
            x, y, z = _flatten_edges_for_plotly(edges_cls.reshape(-1, 2, 3))
            label = None
            if cat_names is not None and cat_names.size > 0:
                first_idx = np.flatnonzero(mask)[0]
                label = f"{name} ({cat_names[first_idx]})"
            else:
                label = f"{name} (class {int(uid)})"
            self.fig.add_trace(
                go.Scatter3d(
                    x=x,
                    y=y,
                    z=z,
                    mode="lines",
                    line={"color": id_to_color[uid], "width": 3},
                    name=label,
                    showlegend=True,
                    opacity=opacity,
                )
            )
        return self

    def finalize(self) -> go.Figure:
        self.fig.update_layout(title=self.title, scene=dict(aspectmode="data", **self.scene_ranges), height=self.height)
        return self.fig


def _to_uint8_image(img: torch.Tensor) -> np.ndarray:
    """Convert tensor image (C,H,W or H,W) to uint8 HWC."""
    arr = img.detach().cpu()
    if arr.ndim == 2:
        arr = arr.unsqueeze(0)
    if arr.shape[0] == 1:
        arr = arr.repeat(3, 1, 1)
    arr = arr.permute(1, 2, 0).clamp(0, 1).mul(255).to(torch.uint8).numpy()  # type: ignore

    return np.rot90(arr, k=ROTATE_90_CW)  # type: ignore


def _depth_to_color(depth: torch.Tensor, *, percentile: float = 99.5) -> np.ndarray:
    """Colorise a single depth/distance map to uint8 RGB using a perceptual colormap."""

    depth_np = depth.detach().cpu().squeeze().numpy()
    finite_mask = np.isfinite(depth_np)
    if not finite_mask.any():
        rgb = np.zeros(depth_np.shape + (3,), dtype=np.uint8)
    else:
        finite_vals = depth_np[finite_mask]
        vmin = max(np.nanmin(finite_vals), 0.0)
        vmax = np.nanpercentile(finite_vals, percentile)
        if vmax <= vmin:
            vmax = vmin + 1e-3
        norm = np.clip((depth_np - vmin) / (vmax - vmin), 0.0, 1.0)
        cmap = colormaps.get_cmap("viridis")
        rgb = (cmap(norm)[..., :3] * 255).astype(np.uint8)
    return np.rot90(rgb, k=ROTATE_90_CW)


class FrameGridBuilder:
    """Builder for image grids (2D modalities)."""

    def __init__(self, rows: int, cols: int, *, titles: list[str], height: int, width: int, title: str):
        self.fig = make_subplots(rows=rows, cols=cols, subplot_titles=titles, specs=[[{"type": "image"}] * cols] * rows)
        self.height = height
        self.width = width
        self.title = title

    def add_image(self, img: np.ndarray, *, row: int, col: int) -> "FrameGridBuilder":
        self.fig.add_trace(go.Image(z=img), row=row, col=col)
        return self

    def finalize(self) -> go.Figure:
        self.fig.update_layout(height=self.height, width=self.width, title_text=self.title)
        return self.fig


def collect_frame_modalities(
    sample: EfmSnippetView,
    *,
    include_depth: bool = True,
) -> tuple[list[tuple[str, np.ndarray, np.ndarray]], list[str]]:
    """Collect first/last-frame visualisations for available modalities."""

    missing: list[str] = []
    missing_set: set[str] = set()
    modalities: list[tuple[str, np.ndarray, np.ndarray]] = []

    cams: list[tuple[str, EfmCameraView]] = [
        ("RGB", sample.camera_rgb),
        ("SLAM-L", sample.camera_slam_left),
        ("slamr", sample.camera_slam_right),
    ]

    for name, cam in cams:
        if cam.images.numel() == 0:
            if name not in missing_set:
                missing.append(name)
                missing_set.add(name)
            continue
        modalities.append(
            (
                name,
                _to_uint8_image(cam.images[0]),
                _to_uint8_image(cam.images[-1]),
            )
        )

    if include_depth:
        depth_streams = [
            ("Depth (RGB)", sample.camera_rgb.distance_m),
        ]
        for name, depth in depth_streams:
            if depth is None or depth.numel() == 0:
                if name not in missing_set:
                    missing.append(name)
                    missing_set.add(name)
                    console.dbg(f"{name} missing in sample {sample.scene_id}/{sample.snippet_id}")
                continue
            modalities.append((name, _depth_to_color(depth[0]), _depth_to_color(depth[-1])))

    return modalities, missing


def _rot_cw90_uv(uv: np.ndarray, width: int, height: int) -> np.ndarray:
    """Rotate UV coordinates 90° clockwise for display-aligned images.

    Args:
        uv: Pixel coordinates shaped ``(N, 2)``.
        width: Image width (pixels).
        height: Image height (pixels).

    Returns:
        Rotated coordinates matching the display-rotated image.
    """

    u, v = uv[:, 0], uv[:, 1]
    u_new = height - 1 - v
    v_new = u
    return np.stack([u_new, v_new], axis=-1)


def project_pointcloud_on_frame(
    *,
    img: torch.Tensor,
    cam: CameraTW,
    pose_world_cam: PoseTW,
    points_world: torch.Tensor,
    max_points: int | None = 20000,
    title: str = "Point cloud overlay",
    point_size: int = 5,
) -> go.Figure:
    """Project 3D points into image plane and overlay on the frame."""

    target_device = cam.device
    cam = cam.to(target_device)
    pose_world_cam = pose_world_cam.to(device=target_device)

    if points_world.numel() == 0:
        return go.Figure()

    img_np = _to_uint8_image(img)
    h, w = img_np.shape[:2]

    pts = points_world.to(target_device)
    if pts.ndim == 3:
        pts = pts.reshape(-1, pts.shape[-1])
    finite = torch.isfinite(pts).all(dim=-1)
    pts = pts[finite]
    if pts.numel() == 0:
        return go.Figure()
    if max_points is not None and pts.shape[0] > max_points:
        idx = torch.randperm(pts.shape[0], device=pts.device)[:max_points]
        pts = pts[idx]

    pts_cam = pose_world_cam.inverse().transform(pts)
    pts_cam_b = pts_cam.unsqueeze(0)  # 1 x N x 3 to satisfy fisheye projection utils
    p2d, valid = cam.project(pts_cam_b)
    # p2d: 1 x N x 2, valid: 1 x N (or 1 x N x 1)
    if valid.ndim == 3:
        valid = valid.squeeze(0)
    if valid.ndim > 2:
        valid = valid.squeeze()
    valid_flat = valid.squeeze()
    p2d = p2d.squeeze(0)[valid_flat]
    depth = pts_cam[valid_flat, -1]
    if p2d.numel() == 0:
        return go.Figure()

    uv = p2d.detach().cpu().numpy()
    depth_np = depth.detach().cpu().numpy()
    uv = _rot_cw90_uv(uv, width=w, height=h)

    depth_norm = np.clip((depth_np - depth_np.min()) / (depth_np.max() - depth_np.min() + 1e-6), 0, 1)
    cmap = colormaps.get_cmap("turbo")
    colors = (cmap(depth_norm)[..., :3] * 255).astype(np.uint8)
    colors_hex = ["#" + "".join(f"{c:02x}" for c in rgb) for rgb in colors]

    fig = go.Figure()
    fig.add_trace(go.Image(z=img_np))
    fig.add_trace(
        go.Scattergl(
            x=uv[:, 0],
            y=uv[:, 1],
            mode="markers",
            marker={"size": point_size, "color": colors_hex, "opacity": 0.8},
            name="Projected points",
        )
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(height=600, width=600, title=title)
    return fig


def plot_frames(sample: EfmSnippetView) -> go.Figure:
    """First RGB/SLAM frames side-by-side."""
    modalities, _ = collect_frame_modalities(sample, include_depth=False)
    if len(modalities) == 0:
        return go.Figure()

    cols = len(modalities)
    builder = FrameGridBuilder(
        rows=1,
        cols=cols,
        titles=[name for name, _, _ in modalities],
        height=500,
        width=max(800, 320 * cols),
        title="Camera views (frame 0)",
    )
    for col, (_, first_img, _) in enumerate(modalities, start=1):
        builder.add_image(first_img, row=1, col=col)
    return builder.finalize()


def plot_first_last_frames(sample: EfmSnippetView) -> go.Figure:
    """First and final frames for all available modalities (RGB/SLAM + optional depth/semantic)."""

    modalities, _ = collect_frame_modalities(sample, include_depth=True)
    if len(modalities) == 0:
        return go.Figure()

    cols = len(modalities)
    subplot_titles = [f"First {name}" for name, _, _ in modalities] + [f"Last {name}" for name, _, _ in modalities]
    builder = FrameGridBuilder(
        rows=2,
        cols=cols,
        titles=subplot_titles,
        height=500 if cols <= 3 else int(500 * cols / 3),
        width=max(1200, 320 * cols),
        title="First and final frames (rotated for display)",
    )
    for col, (_, first_img, last_img) in enumerate(modalities, start=1):
        builder.add_image(first_img, row=1, col=col)
        builder.add_image(last_img, row=2, col=col)

    return builder.finalize()


def plot_trajectory(
    sample: EfmSnippetView,
    camera: Literal["rgb", "slaml", "slamr"] = "rgb",
    show_semidense: bool = True,
    max_sem_points: int | None = 20000,
    pc_from_last_only: bool = True,
    show_scene_bounds: bool = True,
    show_crop_bounds: bool = False,
    crop_aabb: tuple[np.ndarray, np.ndarray] | None = None,
    show_frustum: bool = True,
    frustum_frame_indices: list[int] | None = None,
    frustum_scale: float = 1.0,
    mark_first_last: bool = True,
    show_gt_obbs: bool = False,
    gt_timestamp: str | int | None = None,
) -> go.Figure:
    """Mesh + semidense + trajectory + optional frusta/bounds."""

    builder = (
        SnippetPlotBuilder.from_snippet(sample, title="Mesh + semidense + trajectory + camera frustum")
        .add_mesh()
        .add_trajectory(mark_first_last=mark_first_last, show=True)
    )

    if show_semidense:
        builder.add_semidense(max_points=max_sem_points, last_frame_only=pc_from_last_only)

    if show_frustum:
        builder.add_frusta(
            camera=camera,
            frame_indices=frustum_frame_indices,
            scale=frustum_scale,
            include_axes=True,
            include_center=True,
        )

    if show_scene_bounds:
        builder.add_bounds_box(name="Scene bounds", color="gray", dash="dash", width=2)

    if show_gt_obbs:
        builder.add_gt_obbs(camera=camera, timestamp=gt_timestamp)

    if show_crop_bounds and crop_aabb is not None:
        builder.add_bounds_box(name="Crop bounds", color="orange", dash="solid", width=3, aabb=crop_aabb)
    elif show_crop_bounds and sample.mesh is not None:
        mesh_min, mesh_max = sample.mesh.bounds
        builder.add_bounds_box(name="Crop bounds", color="orange", dash="solid", width=3, aabb=(mesh_min, mesh_max))

    return builder.finalize()


if __name__ == "__main__":
    from aria_nbv.data_handling import AseEfmDatasetConfig
    from aria_nbv.utils import Console

    debug = True
    verbose = True
    console = Console.with_prefix("tst_import").set_verbose(True).set_debug(debug)

    ds_cfg = AseEfmDatasetConfig(
        scene_ids=["81283"],
        mesh_simplify_ratio=0.01,
        load_meshes=True,
        require_mesh=True,
        verbose=verbose,
        is_debug=debug,
    )
    dataset = ds_cfg.setup_target()
    sample = next(iter(dataset))

    plot_trajectory(sample, pc_from_last_only=False).show()
