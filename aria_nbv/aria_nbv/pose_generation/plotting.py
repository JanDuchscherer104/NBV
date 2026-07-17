"""Plot candidate shells, validity diagnostics, and counterfactual rollouts.

This module provides compact plotting functions and Plotly builders for pose
axes, validity/rejection masks, directional marginals, and counterfactual path
metrics. It owns presentation and color mapping only; candidate generation,
rollout state, and score computation remain with their producing modules.

All 3D payloads are interpreted in world or explicitly named reference frames.
Plotly conversions detach to CPU and remain presentation-only; candidate masks,
poses, and rollout state are never modified by a builder.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import numpy as np
import plotly.graph_objects as go  # type: ignore[import]
import torch
from efm3d.aria.pose import PoseTW
from plotly.colors import sample_colorscale  # type: ignore[import]
from plotly.subplots import make_subplots  # type: ignore[import]

from ..data_handling import EfmSnippetView
from ..targets import TargetDescriptor
from ..utils import Console
from ..utils.data_plotting import SnippetPlotBuilder, get_frustum_segments

if TYPE_CHECKING:
    from ..rollouts.replay.state import CounterfactualRolloutResult, CounterfactualStepResult, CounterfactualTrajectory
    from .candidate_generation import CandidateViewGeneratorConfig
    from .types import CandidateSamplingResult

console = Console.with_prefix("pose_plotting")
COUNTERFACTUAL_COLORS = (
    "#636EFA",
    "#EF553B",
    "#00CC96",
    "#AB63FA",
    "#FFA15A",
    "#19D3F3",
    "#FF6692",
    "#B6E880",
)


def _pose_axes_np(candidates: "CandidateSamplingResult") -> tuple[np.ndarray, np.ndarray]:
    ref_pose = candidates.sampling_pose or candidates.reference_pose
    centers = ref_pose.t.detach().cpu().numpy()
    axes = ref_pose.R.detach().cpu().numpy()
    if centers.ndim == 1:
        centers = centers.reshape(1, 3)
    if axes.ndim == 2:
        axes = axes.reshape(1, 3, 3)
    return centers, axes


def plot_candidate_centers_simple(
    candidates: "CandidateSamplingResult",
    *,
    title: str,
    use_valid: bool = True,
) -> go.Figure:
    """Plot candidate centers without requiring a full snippet."""
    centers = candidates.shell_poses.t
    if use_valid:
        centers = centers[candidates.mask_valid]
    pts = centers.detach().cpu().numpy()
    fig = go.Figure(
        data=go.Scatter3d(
            x=pts[:, 0],
            y=pts[:, 1],
            z=pts[:, 2],
            mode="markers",
            marker={"size": 3, "color": "royalblue", "opacity": 0.7},
            name="Candidates",
        )
    )
    centers_np, axes_np = _pose_axes_np(candidates)
    fig = SnippetPlotBuilder.add_frame_axes_to_fig(
        fig=fig,
        cam_centers=centers_np,
        cam_axes=axes_np,
        title="Sampling frame",
        scale=0.4,
    )
    fig.update_layout(
        title=title,
        scene={"xaxis_title": "X (left)", "yaxis_title": "Y (up)", "zaxis_title": "Z (fwd)", "aspectmode": "data"},
    )
    return fig


def plot_candidate_frusta_simple(
    candidates: "CandidateSamplingResult",
    *,
    scale: float,
    max_frustums: int | None,
) -> go.Figure:
    """Plot candidate frusta without requiring a full snippet."""
    poses = candidates.poses_world_cam()
    cams = candidates.views
    n = poses._data.shape[0] if poses._data.ndim == 2 else 1
    if n == 0:
        return go.Figure()
    if max_frustums is not None and n > max_frustums:
        idxs = np.linspace(0, n - 1, num=max_frustums, dtype=int)
    else:
        idxs = np.arange(n)

    segments: list[np.ndarray] = []
    for idx in idxs:
        pose = poses[int(idx)] if n > 1 else poses
        cam = cams[int(idx)] if cams.ndim > 1 else cams
        segs = get_frustum_segments(cam, pose, scale=scale)
        for seg in segs:
            segments.append(np.vstack([seg, np.full((1, 3), np.nan, dtype=float)]))

    if segments:
        seg_all = np.vstack(segments)
        fig = go.Figure(
            data=go.Scatter3d(
                x=seg_all[:, 0],
                y=seg_all[:, 1],
                z=seg_all[:, 2],
                mode="lines",
                line={"color": "crimson", "width": 3},
                name="Frustum",
            )
        )
    else:
        fig = go.Figure()

    centers = poses.t.detach().cpu().numpy()
    fig.add_trace(
        go.Scatter3d(
            x=centers[:, 0],
            y=centers[:, 1],
            z=centers[:, 2],
            mode="markers",
            marker={"size": 2, "color": "royalblue", "opacity": 0.5},
            name="Candidates",
        )
    )
    centers_np, axes_np = _pose_axes_np(candidates)
    fig = SnippetPlotBuilder.add_frame_axes_to_fig(
        fig=fig,
        cam_centers=centers_np,
        cam_axes=axes_np,
        title="Sampling frame",
        scale=0.4,
    )
    fig.update_layout(
        title="Candidate frusta (cached)",
        scene={"xaxis_title": "X (left)", "yaxis_title": "Y (up)", "zaxis_title": "Z (fwd)", "aspectmode": "data"},
    )
    return fig


class CandidatePlotBuilder(SnippetPlotBuilder):
    """Fluent, snippet-aware builder for full-shell candidate diagnostics.

    The builder retains both the compact valid table and full sampled shell so
    plots can distinguish accepted actions, rejected positions, and rule masks.
    All cached center arrays have shape ``Array[\"N 3\", float]`` in world metres.
    """

    candidate_results: CandidateSamplingResult | None = None
    """Attached candidate sampling result, including full-shell provenance."""

    candidate_cfg: CandidateViewGeneratorConfig | None = None
    """Optional generation config used to annotate plots and thresholds."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.candidate_results = None
        self.candidate_cfg = None
        self._centers_valid: np.ndarray | None = None
        self._centers_all: np.ndarray | None = None
        self._ref_center: np.ndarray | None = None

    @classmethod
    def from_candidates(
        cls, snippet: EfmSnippetView, candidates: CandidateSamplingResult, *, title: str, height: int = 900
    ) -> Self:
        """Create a snippet plot with candidate results already attached."""
        return cls.from_snippet(snippet, title=title, height=height).attach_candidate_results(candidates)

    def attach_candidate_results(self, results: CandidateSamplingResult) -> Self:
        """Attach candidate sampling results for plotting."""
        self.candidate_results = results
        self._centers_all = None
        self._centers_valid = None
        self._ref_center = None
        return self

    def attach_candidate_cfg(self, cfg: CandidateViewGeneratorConfig) -> Self:
        """Attach candidate config for metadata-aware plotting."""
        self.candidate_cfg = cfg
        return self

    # ---------------- world-frame helpers ----------------
    def _world_positions(self, use_valid: bool = True) -> np.ndarray:
        if self.candidate_results is None:
            raise ValueError("Candidate results missing; call attach_candidate_results() first.")
        if use_valid:
            if self._centers_valid is None:
                shell = PoseTW(self.candidate_results.shell_poses._data[self.candidate_results.mask_valid])
                self._centers_valid = shell.t.detach().cpu().numpy()
            return self._centers_valid
        if self._centers_all is None:
            self._centers_all = self.candidate_results.shell_poses.t.detach().cpu().numpy()
        return self._centers_all

    def _mask_valid_np(self) -> np.ndarray:
        if self.candidate_results is None:
            raise ValueError("Candidate results missing; call attach_candidate_results() first.")
        return self.candidate_results.mask_valid.detach().cpu().numpy()

    def _ref_center_np(self) -> np.ndarray:
        if self.candidate_results is None:
            raise ValueError("Candidate results missing; call attach_candidate_results() first.")
        if self._ref_center is None:
            self._ref_center = self.candidate_results.reference_pose.t.detach().cpu().numpy()
        return self._ref_center

    def add_reference_axes(
        self,
        *,
        title: str = "Reference frame",
        display_rotate: bool = False,
        use_sampling_pose: bool = False,
    ) -> Self:
        """Add the candidate reference frame axes to the figure.

        Notes:
            Candidate generation applies the Aria rig→LUF convention fix (a 90° rotation
            about the local +Z/forward axis) to the **reference pose** before sampling.
            Applying the same correction again in plotting would double-rotate the
            reference axes. Therefore, ``display_rotate`` defaults to ``False`` for
            When gravity alignment is enabled, candidates are sampled around a
            gravity-aligned copy of the reference pose. In that case, plotting the
            sampling pose axes (``use_sampling_pose=True``) keeps the axes symmetric
            with the candidate cloud.
        """
        if self.candidate_results is None:
            return self
        pose = self.candidate_results.reference_pose
        title_use = title
        if use_sampling_pose:
            sampling_pose = getattr(self.candidate_results, "sampling_pose", None)
            if sampling_pose is not None:
                pose = sampling_pose
                if title == "Reference frame" and sampling_pose is not self.candidate_results.reference_pose:
                    title_use = "Sampling frame"
        return self.add_frame_axes(
            frame=pose,
            title=title_use,
            is_rotate_yaw_cw90=display_rotate,
        )

    def add_candidate_points(
        self,
        *,
        use_valid: bool = True,
        color: np.ndarray | str | None = None,
        colorbar_title: str | None = None,
        name: str = "Candidates",
        size: int = 3,
        opacity: float = 0.7,
        hovertext: list[str] | None = None,
        mark_reference: bool = False,
        reference_symbol: str = "diamond",
    ) -> Self:
        """Add candidate centers from the compact table or full sampled shell.

        ``color`` may be a scalar color or an ``Array[\"N\", numeric]`` aligned
        with the selected rows. Coordinates are world-frame metres.
        """
        pts = self._world_positions(use_valid=use_valid)
        marker = {"size": size, "opacity": opacity}
        if color is not None:
            if isinstance(color, np.ndarray):
                marker.update({"color": color, "colorscale": "Viridis"})
                if colorbar_title:
                    marker["colorbar"] = {"title": colorbar_title}
            else:
                marker.update({"color": color})
        self.fig.add_trace(
            go.Scatter3d(
                x=pts[:, 0],
                y=pts[:, 1],
                z=pts[:, 2],
                mode="markers",
                marker=marker,
                name=name,
                hovertext=hovertext,
                hoverinfo="text" if hovertext else "name",
            )
        )
        if mark_reference and self.candidate_results is not None:
            ref = self.candidate_results.reference_pose.t.detach().cpu().numpy()
            self.fig.add_trace(
                go.Scatter3d(
                    x=[ref[0]],
                    y=[ref[1]],
                    z=[ref[2]],
                    mode="markers",
                    marker={"color": "black", "size": 6, "symbol": reference_symbol},
                    name="Reference pose",
                )
            )
        return self

    def add_candidate_cloud(
        self,
        *,
        use_valid: bool = True,
        color: str | np.ndarray | None = "royalblue",
        name: str = "Candidates",
        size: int = 4,
        opacity: float = 0.7,
        mark_reference: bool = True,
    ) -> Self:
        """Add the default candidate-center cloud and optional reference marker."""
        return self.add_candidate_points(
            use_valid=use_valid,
            color=color,
            name=name,
            size=size,
            opacity=opacity,
            mark_reference=mark_reference,
        )

    def add_rejected_cloud(
        self,
        *,
        color: str = "crimson",
        name: str = "Rejected",
        size: int = 4,
        opacity: float = 0.8,
    ) -> Self:
        """Add world-frame centers rejected by any cumulative validity rule."""
        if self.candidate_results is None:
            return self
        mask = self._mask_valid_np()
        if mask.size == 0 or mask.all():
            return self
        pts = self._world_positions(use_valid=False)[~mask]
        return self.add_points(pts, name=name, color=color, size=size, opacity=opacity)

    def add_min_distance_overlay(self, distances: torch.Tensor, *, use_valid: bool = False) -> Self:
        """Color candidate centers by aligned point-to-mesh distance in metres."""
        dist_np = distances.detach().cpu().numpy().reshape(-1)
        mask = self._mask_valid_np()
        hover = [f"dist={d:.3f} m<br>valid={bool(v)}" for d, v in zip(dist_np.tolist(), mask.tolist(), strict=False)]
        return self.add_candidate_points(
            use_valid=use_valid,
            color=dist_np,
            colorbar_title="Min dist (m)",
            name="Candidates",
            hovertext=hover,
            opacity=0.8,
            size=4,
            mark_reference=True,
        )

    def add_path_collision_segments(self, collision_mask: torch.Tensor) -> Self:
        """Draw reference-to-candidate segments for full-shell collision rows."""
        ref = self._ref_center_np()
        centers = self._world_positions(use_valid=False)
        mask_np = collision_mask.detach().cpu().numpy().astype(bool)
        rej_centers = centers[mask_np]
        if rej_centers.size > 0:
            seg_pts = []
            for c in rej_centers:
                seg_pts.append(ref)
                seg_pts.append(c)
                seg_pts.append([np.nan, np.nan, np.nan])
            seg_pts = np.array(seg_pts)
            self.fig.add_trace(
                go.Scatter3d(
                    x=seg_pts[:, 0],
                    y=seg_pts[:, 1],
                    z=seg_pts[:, 2],
                    mode="lines",
                    line={"color": "crimson", "width": 4},
                    name="Rejected path",
                    hoverinfo="skip",
                )
            )
        self.fig.add_trace(
            go.Scatter3d(
                x=[ref[0]],
                y=[ref[1]],
                z=[ref[2]],
                mode="markers",
                marker={"color": "black", "size": 6, "symbol": "diamond"},
                name="Reference pose",
            )
        )
        return self

    def rule_rejection_bar(self) -> go.Figure:
        """Plot newly rejected row counts for each cumulative pruning mask."""
        masks = self.candidate_results.masks if self.candidate_results is not None else {}
        if not isinstance(masks, dict) or len(masks) == 0:
            fig = go.Figure()
            fig.update_layout(title="Rule rejections (no masks collected)")
            return fig
        prev = torch.ones_like(next(iter(masks.values())), dtype=torch.bool)
        names: list[str] = []
        counts: list[int] = []
        for name, mask in masks.items():
            rej = prev & (~mask)
            names.append(name)
            counts.append(int(rej.sum().item()))
            prev = mask
        fig = go.Figure(go.Bar(x=names, y=counts, marker_color="steelblue"))
        fig.update_layout(title="Rejections per rule", xaxis_title="Rule", yaxis_title="# rejected")
        return fig

    def add_candidate_frusta(
        self,
        *,
        scale: float = 1.0,
        color: str = "crimson",
        name: str = "Frustum",
        max_frustums: int | None = None,
        include_axes: bool = False,
        include_center: bool = False,
        display_rotate: bool = False,
    ) -> Self:
        """Overlay frusta using the attached candidate results.

        Notes:
            ``display_rotate`` is a legacy plotting option that applies the same Aria
            UI-style 90° local +Z rotation (``rotate_yaw_cw90``). Because candidate
            generation already applies this convention fix to the reference pose, the
            default is ``False`` to avoid a second roll offset (which becomes very
            apparent once roll jitter is enabled).
        """

        cand_results = self.candidate_results
        if cand_results is None:
            raise ValueError("Candidate results missing; call attach_candidate_results() first.")

        poses_world_cam = cand_results.poses_world_cam()
        if display_rotate:
            from aria_nbv.utils import rotate_yaw_cw90

            poses_world_cam = rotate_yaw_cw90(poses_world_cam)

        pose_list = self._pose_list_from_input(poses_world_cam)

        return self._add_frusta_for_poses(
            cams=cand_results.views,
            poses=pose_list,
            scale=scale,
            color=color,
            name=name,
            max_frustums=max_frustums,
            include_axes=include_axes,
            include_center=include_center,
        )


def _counterfactual_color(index: int) -> str:
    return COUNTERFACTUAL_COLORS[index % len(COUNTERFACTUAL_COLORS)]


def _trajectory_positions_np(trajectory: "CounterfactualTrajectory") -> np.ndarray:
    return trajectory.pose_chain_world().t.detach().cpu().numpy()


def _pretty_metric_label(name: str) -> str:
    if name == "cumulative_rri":
        return "Cumulative RRI"
    if name == "cumulative_score":
        return "Cumulative score"
    return name.replace("_", " ")


def _trajectory_metric_values(
    rollouts: "CounterfactualRolloutResult",
    *,
    color_metric: str,
) -> tuple[np.ndarray | None, str | None]:
    if color_metric == "auto":
        color_metric = "cumulative_score"

    if color_metric == "cumulative_score":
        values = np.array([float(trajectory.cumulative_score) for trajectory in rollouts.trajectories], dtype=float)
        return values, "Cumulative score"

    return None, None


def _trajectory_colors(
    rollouts: "CounterfactualRolloutResult",
    *,
    color_metric: str,
    colorscale: str,
) -> tuple[list[str], np.ndarray | None, str | None]:
    values, metric_label = _trajectory_metric_values(rollouts, color_metric=color_metric)
    if values is None:
        return [_counterfactual_color(index) for index, _ in enumerate(rollouts.trajectories)], None, None

    colors = [_counterfactual_color(index) for index, _ in enumerate(rollouts.trajectories)]
    finite_mask = np.isfinite(values)
    if not finite_mask.any():
        return colors, values, metric_label

    vmin = float(values[finite_mask].min())
    vmax = float(values[finite_mask].max())
    for idx, value in enumerate(values):
        if not np.isfinite(value):
            continue
        scale_pos = 0.5 if np.isclose(vmin, vmax) else float((value - vmin) / (vmax - vmin))
        colors[idx] = str(sample_colorscale(colorscale, [scale_pos])[0])
    return colors, values, metric_label


def _metric_color(value: float | None, finite_values: np.ndarray, *, default: str, colorscale: str) -> str:
    if value is None or not np.isfinite(value) or finite_values.size == 0:
        return default
    vmin = float(finite_values.min())
    vmax = float(finite_values.max())
    scale_pos = 0.5 if np.isclose(vmin, vmax) else float((float(value) - vmin) / (vmax - vmin))
    return str(sample_colorscale(colorscale, [scale_pos])[0])


def _valid_candidate_values(step: "CounterfactualStepResult", metric_name: str) -> np.ndarray | None:
    """Return one value per compact valid candidate for coloring."""

    candidates = step.candidates
    mask = candidates.mask_valid.detach().cpu().numpy().reshape(-1).astype(bool, copy=False)
    valid_count = int(mask.sum())
    if valid_count == 0:
        return None

    if metric_name == "selection_score":
        values = step.selection_scores
    elif metric_name == "selection_probability":
        values = step.selection_probabilities
    elif metric_name == "position_family":
        values = candidates.position_id
    else:
        return None
    if values is None:
        return None

    values_np = values.detach().cpu().numpy().reshape(-1).astype(float, copy=False)
    if values_np.shape[0] == mask.shape[0]:
        values_np = values_np[mask]
    if values_np.shape[0] != valid_count:
        return None
    return values_np


def _trajectory_name(
    trajectory: "CounterfactualTrajectory",
    *,
    traj_idx: int,
    score_label: str,
) -> str:
    return f"CF traj {traj_idx} ({score_label}={trajectory.cumulative_score:.3f})"


def _add_metric_colorbar(
    fig: go.Figure,
    *,
    metric_values: np.ndarray | None,
    metric_label: str | None,
    colorscale: str,
    anchor: np.ndarray,
) -> go.Figure:
    if metric_values is None or metric_label is None:
        return fig

    finite_mask = np.isfinite(metric_values)
    if not finite_mask.any():
        return fig

    finite_values = metric_values[finite_mask]
    anchor_xyz = np.broadcast_to(anchor.reshape(1, 3), (finite_values.shape[0], 3))
    fig.add_trace(
        go.Scatter3d(
            x=anchor_xyz[:, 0],
            y=anchor_xyz[:, 1],
            z=anchor_xyz[:, 2],
            mode="markers",
            marker={
                "size": 0.1,
                "opacity": 0.0,
                "color": finite_values,
                "colorscale": colorscale,
                "showscale": True,
                "colorbar": {"title": metric_label},
                "cmin": float(finite_values.min()),
                "cmax": float(finite_values.max()),
            },
            hoverinfo="skip",
            showlegend=False,
            name=metric_label,
        )
    )
    return fig


class CounterfactualPlotBuilder(CandidatePlotBuilder):
    """Snippet-aware plotting builder for multi-step counterfactual trajectories."""

    counterfactual_rollouts: CounterfactualRolloutResult | None = None

    @classmethod
    def from_rollouts(
        cls,
        snippet: EfmSnippetView,
        rollouts: "CounterfactualRolloutResult",
        *,
        title: str,
        height: int = 900,
    ) -> "CounterfactualPlotBuilder":
        """Create a snippet plot with multi-step rollout trajectories attached."""
        return cls.from_snippet(snippet, title=title, height=height).attach_counterfactual_rollouts(rollouts)

    def attach_counterfactual_rollouts(self, rollouts: "CounterfactualRolloutResult") -> Self:
        """Attach rollout trajectories for subsequent plotting calls."""

        self.counterfactual_rollouts = rollouts
        return self

    def add_actor_visible_target_obb(
        self,
        target: TargetDescriptor,
        *,
        color: str = "#ff2f74",
        name: str = "Active target / actor-visible",
        width: int = 7,
    ) -> Self:
        """Overlay the actor-visible target OBB used for target-conditioned rollout generation."""

        return self.add_oriented_box(
            pose_world_object=target.pose_world_object,
            extents=target.extents_m,
            name=name,
            color=color,
            width=width,
            opacity=0.95,
        )

    def add_counterfactual_paths(
        self,
        *,
        show_step_markers: bool = True,
        line_width: int = 5,
        root_color: str = "black",
        color_metric: str = "auto",
        colorscale: str = "Viridis",
        show_metric_colorbar: bool = True,
    ) -> Self:
        """Overlay rollout paths for all attached trajectories."""

        if self.counterfactual_rollouts is None:
            raise ValueError("Counterfactual rollouts missing; call attach_counterfactual_rollouts() first.")

        root = self.counterfactual_rollouts.root_pose_world.t.detach().cpu().numpy()
        self._update_scene_ranges(root)
        self.fig.add_trace(
            go.Scatter3d(
                x=[root[0]],
                y=[root[1]],
                z=[root[2]],
                mode="markers",
                marker={"size": 7, "color": root_color, "symbol": "diamond"},
                name="Counterfactual root",
            )
        )

        colors, metric_values, metric_label = _trajectory_colors(
            self.counterfactual_rollouts,
            color_metric=color_metric,
            colorscale=colorscale,
        )
        for traj_idx, trajectory in enumerate(self.counterfactual_rollouts.trajectories):
            pts = _trajectory_positions_np(trajectory)
            if pts.size == 0:
                continue
            self._update_scene_ranges(pts)
            color = colors[traj_idx]
            mode = "lines+markers" if show_step_markers else "lines"
            self.fig.add_trace(
                go.Scatter3d(
                    x=pts[:, 0],
                    y=pts[:, 1],
                    z=pts[:, 2],
                    mode=mode,
                    marker={"size": 4, "color": color},
                    line={"width": line_width, "color": color},
                    name=_trajectory_name(
                        trajectory,
                        traj_idx=traj_idx,
                        score_label=self.counterfactual_rollouts.score_label,
                    ),
                )
            )
        if show_metric_colorbar:
            self.fig = _add_metric_colorbar(
                self.fig,
                metric_values=metric_values,
                metric_label=metric_label,
                colorscale=colorscale,
                anchor=root,
            )
        return self

    def add_counterfactual_selected_frusta(
        self,
        *,
        scale: float = 0.6,
        include_axes: bool = False,
        include_center: bool = False,
        max_frustums_per_trajectory: int | None = None,
        display_rotate: bool = False,
    ) -> Self:
        """Overlay frusta for the selected poses in each attached trajectory."""

        if self.counterfactual_rollouts is None:
            raise ValueError("Counterfactual rollouts missing; call attach_counterfactual_rollouts() first.")

        for traj_idx, trajectory in enumerate(self.counterfactual_rollouts.trajectories):
            steps = trajectory.steps
            if max_frustums_per_trajectory is not None:
                steps = steps[:max_frustums_per_trajectory]
            if not steps:
                continue
            for step in steps:
                pose = step.selected_pose_world
                if display_rotate:
                    from aria_nbv.utils import rotate_yaw_cw90

                    pose = rotate_yaw_cw90(pose)
                self._add_frusta_for_poses(
                    cams=[step.selected_view],
                    poses=[pose],
                    scale=scale,
                    color=_counterfactual_color(traj_idx),
                    name=f"CF frusta {traj_idx} step {step.step_index + 1}",
                    max_frustums=None,
                    include_axes=include_axes,
                    include_center=include_center,
                )
        return self

    def add_counterfactual_step_shell(
        self,
        *,
        trajectory_index: int,
        step_index: int,
        show_history: bool = True,
        show_selected: bool = True,
        show_frusta: bool = True,
        frustum_scale: float = 0.5,
        max_frustums: int | None = 16,
        include_rejected: bool = False,
        candidate_color_metric: str = "selection_score",
    ) -> Self:
        """Plot one rollout step's candidate shell within the snippet scene."""

        if self.counterfactual_rollouts is None:
            raise ValueError("Counterfactual rollouts missing; call attach_counterfactual_rollouts() first.")

        trajectory = self.counterfactual_rollouts.trajectories[trajectory_index]
        step = trajectory.steps[step_index]

        if show_history:
            history = _trajectory_positions_np(trajectory)[: step_index + 1]
            if history.size > 0:
                self._update_scene_ranges(history)
                self.fig.add_trace(
                    go.Scatter3d(
                        x=history[:, 0],
                        y=history[:, 1],
                        z=history[:, 2],
                        mode="lines+markers",
                        marker={"size": 4, "color": "black"},
                        line={"width": 4, "color": "black"},
                        name="Rollout history",
                    )
                )

        self.attach_candidate_results(step.candidates)
        colorbar_title = _pretty_metric_label(candidate_color_metric)
        candidate_values = _valid_candidate_values(step, candidate_color_metric)
        if candidate_values is not None:
            self.add_candidate_points(
                use_valid=True,
                color=candidate_values,
                colorbar_title=colorbar_title,
                name=f"Step {step_index + 1} candidates",
                size=4,
                opacity=0.8,
                mark_reference=True,
            )
        elif step.selection_scores is not None:
            self.add_candidate_points(
                use_valid=True,
                color=step.selection_scores.detach().cpu().numpy(),
                colorbar_title=_pretty_metric_label(step.selection_score_label),
                name=f"Step {step_index + 1} candidates",
                size=4,
                opacity=0.8,
                mark_reference=True,
            )
        else:
            self.add_candidate_cloud(use_valid=True, name=f"Step {step_index + 1} candidates")
        if include_rejected:
            self.add_rejected_cloud()
        if show_frusta:
            metric_values = _valid_candidate_values(step, candidate_color_metric)
            if metric_values is not None and metric_values.size:
                poses = self._pose_list_from_input(step.candidates.poses_world_cam())
                indices = np.arange(len(poses))
                if max_frustums is not None and len(indices) > max_frustums:
                    indices = np.linspace(0, len(poses) - 1, num=max_frustums, dtype=int)
                finite_values = metric_values[np.isfinite(metric_values)]
                for local_idx in indices.tolist():
                    value = float(metric_values[local_idx]) if local_idx < metric_values.size else None
                    label = "n/a" if value is None else f"{value:.4f}"
                    self._add_frusta_for_poses(
                        cams=[step.candidates.views[int(local_idx)]],
                        poses=[poses[int(local_idx)]],
                        scale=frustum_scale,
                        color=_metric_color(value, finite_values, default="crimson", colorscale="Viridis"),
                        name=f"Step {step_index + 1} frustum {local_idx} {candidate_color_metric}={label}",
                        max_frustums=None,
                        include_axes=False,
                        include_center=False,
                    )
            else:
                self.add_candidate_frusta(
                    scale=frustum_scale,
                    color="crimson",
                    name=f"Step {step_index + 1} frusta",
                    max_frustums=max_frustums,
                    include_axes=False,
                    include_center=False,
                    display_rotate=False,
                )

        ref_pose = trajectory.reference_pose_world(step_index)
        self.add_frame_axes(frame=ref_pose, title="Rollout ref", is_rotate_yaw_cw90=False)
        if show_selected:
            self.add_points(
                step.selected_pose_world,
                name=f"Selected step {step_index + 1}",
                color="gold",
                size=7,
                symbol="diamond",
            )
        return self


def plot_counterfactual_paths_simple(
    rollouts: "CounterfactualRolloutResult",
    *,
    title: str = "Counterfactual pose rollouts",
    show_step_markers: bool = True,
    color_metric: str = "auto",
    colorscale: str = "Viridis",
    show_metric_colorbar: bool = True,
) -> go.Figure:
    """Plot rollout paths without requiring a snippet or mesh."""

    fig = go.Figure()
    root = rollouts.root_pose_world.t.detach().cpu().numpy()
    fig.add_trace(
        go.Scatter3d(
            x=[root[0]],
            y=[root[1]],
            z=[root[2]],
            mode="markers",
            marker={"size": 7, "color": "black", "symbol": "diamond"},
            name="Counterfactual root",
        )
    )
    colors, metric_values, metric_label = _trajectory_colors(
        rollouts,
        color_metric=color_metric,
        colorscale=colorscale,
    )
    for traj_idx, trajectory in enumerate(rollouts.trajectories):
        pts = _trajectory_positions_np(trajectory)
        if pts.size == 0:
            continue
        color = colors[traj_idx]
        fig.add_trace(
            go.Scatter3d(
                x=pts[:, 0],
                y=pts[:, 1],
                z=pts[:, 2],
                mode="lines+markers" if show_step_markers else "lines",
                marker={"size": 4, "color": color},
                line={"width": 5, "color": color},
                name=_trajectory_name(
                    trajectory,
                    traj_idx=traj_idx,
                    score_label=rollouts.score_label,
                ),
            )
        )
    if show_metric_colorbar:
        fig = _add_metric_colorbar(
            fig,
            metric_values=metric_values,
            metric_label=metric_label,
            colorscale=colorscale,
            anchor=root,
        )
    fig.update_layout(
        title=title,
        scene={
            "xaxis_title": "X (left)",
            "yaxis_title": "Y (up)",
            "zaxis_title": "Z (fwd)",
            "aspectmode": "data",
        },
    )
    return fig


def plot_counterfactual_step_simple(
    trajectory: "CounterfactualTrajectory",
    *,
    step_index: int,
    scale: float = 0.5,
    max_frustums: int | None = 12,
) -> go.Figure:
    """Plot one rollout step's candidate shell without requiring a snippet."""

    step = trajectory.steps[step_index]
    fig = plot_candidate_frusta_simple(step.candidates, scale=scale, max_frustums=max_frustums)

    history = _trajectory_positions_np(trajectory)[: step_index + 1]
    if history.size > 0:
        fig.add_trace(
            go.Scatter3d(
                x=history[:, 0],
                y=history[:, 1],
                z=history[:, 2],
                mode="lines+markers",
                marker={"size": 4, "color": "black"},
                line={"width": 4, "color": "black"},
                name="Rollout history",
            )
        )

    selected = step.selected_pose_world.t.detach().cpu().numpy()
    fig.add_trace(
        go.Scatter3d(
            x=[selected[0]],
            y=[selected[1]],
            z=[selected[2]],
            mode="markers",
            marker={"size": 7, "color": "gold", "symbol": "diamond"},
            name=f"Selected step {step_index + 1}",
        )
    )
    fig.update_layout(title=f"Counterfactual step {step_index + 1}")
    return fig


def plot_direction_polar(
    dirs: np.ndarray,
    *,
    title: str = "Direction distribution (az/elev)",
    bins: int = 40,
    fixed_ranges: bool = False,
) -> go.Figure:
    """Plot azimuth/elevation density of direction vectors."""
    elev = np.arcsin(dirs[:, 1])  # y is up in LUF
    az = np.arctan2(dirs[:, 0], dirs[:, 2])  # atan2(x, z) per our sampling
    elev_deg = np.degrees(elev)
    az_deg = np.degrees(az)
    h, xedges, yedges = np.histogram2d(az_deg, elev_deg, bins=bins)
    fig = go.Figure(
        data=go.Heatmap(
            x=xedges[:-1],
            y=yedges[:-1],
            z=h.T,
            colorscale="Viridis",
            colorbar_title="count",
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Azimuth (deg)",
        yaxis_title="Elevation (deg)",
        yaxis={"scaleanchor": None},
    )
    if fixed_ranges:
        fig.update_xaxes(range=[-180, 180])
        fig.update_yaxes(range=[-90, 90])
    return fig


def plot_direction_sphere(
    dirs: np.ndarray,
    *,
    title: str = "Directions on unit sphere",
    show_axes: bool = True,
) -> go.Figure:
    """3D scatter of directions on the unit sphere."""
    fig = go.Figure()

    if show_axes:
        fig = SnippetPlotBuilder.add_frame_axes_to_fig(
            fig=fig,
            cam_centers=np.zeros((1, 3)),
            cam_axes=np.eye(3),
            title="ref. frame",
            scale=1.0,
        )

    fig.add_trace(
        go.Scatter3d(
            x=dirs[:, 0],
            y=dirs[:, 1],
            z=dirs[:, 2],
            mode="markers",
            marker={"size": 2, "color": dirs[:, 1], "colorscale": "Turbo", "opacity": 0.7},
            name="dirs",
        )
    )

    fig.update_layout(
        title=title,
        scene={
            "xaxis_title": "X (left)",
            "yaxis_title": "Y (up)",
            "zaxis_title": "Z (fwd)",
            "xaxis": {"range": [-1.1, 1.1]},
            "yaxis": {"range": [-1.1, 1.1]},
            "zaxis": {"range": [-1.1, 1.1]},
            "aspectmode": "cube",
        },
    )
    return fig


def plot_position_polar(
    offsets: np.ndarray,
    *,
    title: str = "Offsets from reference pose (az/elev)",
    bins: int = 72,
    fixed_ranges: bool = True,
) -> go.Figure:
    """Plot reference-frame candidate offsets by azimuth and elevation.

    Args:
        offsets: LUF reference-frame offsets ``Array[\"N 3\", float]`` in metres.
        title: Figure title.
        bins: Bin count used independently along both angular axes.
        fixed_ranges: Clamp azimuth/elevation displays to their physical ranges.
    """
    # LUF: x=left, y=up, z=forward
    az = np.degrees(np.arctan2(offsets[:, 0], offsets[:, 2]))  # atan2(x, z)
    el = np.degrees(np.arctan2(offsets[:, 1], np.linalg.norm(offsets[:, [0, 2]], axis=1) + 1e-8))
    h, xedges, yedges = np.histogram2d(az, el, bins=bins)
    fig = go.Figure(go.Heatmap(x=xedges[:-1], y=yedges[:-1], z=h.T, colorscale="Viridis", colorbar_title="count"))
    fig.update_layout(title=title, xaxis_title="azimuth (deg)", yaxis_title="elevation (deg)")
    if fixed_ranges:
        fig.update_xaxes(range=[-180, 180])
        fig.update_yaxes(range=[-90, 90])
    return fig


def plot_position_sphere(
    offsets: np.ndarray,
    *,
    title: str = "Positions in rig frame",
    show_axes: bool = True,
    dirs: np.ndarray | None = None,
    dir_scale: float | None = None,
) -> go.Figure:
    """Plot LUF reference-frame position offsets and optional view directions.

    ``offsets`` and ``dirs`` have shape ``Array[\"N 3\", float]``. Offsets are
    measured in metres; directions are normalized before drawing.
    """
    offsets = np.asarray(offsets)
    fig = go.Figure(
        data=go.Scatter3d(
            x=offsets[:, 0],
            y=offsets[:, 1],
            z=offsets[:, 2],
            mode="markers",
            marker={"size": 2, "color": offsets[:, 1], "colorscale": "Turbo", "opacity": 0.7},
            name="positions",
        )
    )
    if show_axes:
        fig = SnippetPlotBuilder.add_frame_axes_to_fig(
            fig=fig, cam_centers=np.zeros((1, 3)), cam_axes=np.eye(3)[None, ...], scale=0.4
        )
    if dirs is not None:
        dirs = np.asarray(dirs)
        if dirs.shape[0] != offsets.shape[0]:
            n = min(dirs.shape[0], offsets.shape[0])
            console.warn(
                f"Direction count mismatch for position plot: offsets={offsets.shape[0]}, dirs={dirs.shape[0]}."
            )
            offsets_use = offsets[:n]
            dirs = dirs[:n]
        else:
            offsets_use = offsets
        norms = np.linalg.norm(dirs, axis=1, keepdims=True)
        dirs = dirs / np.clip(norms, 1e-8, None)
        if dir_scale is None:
            radii = np.linalg.norm(offsets_use, axis=1)
            median = float(np.median(radii)) if radii.size else 1.0
            if not np.isfinite(median) or median <= 0:
                median = 1.0
            dir_scale = 0.15 * median
        seg_start = offsets_use
        seg_ends = offsets_use + dirs * float(dir_scale)
        seg = np.stack([seg_start, seg_ends], axis=1)
        seg = np.concatenate([seg, np.full((seg.shape[0], 1, 3), np.nan, dtype=float)], axis=1).reshape(-1, 3)
        fig.add_trace(
            go.Scatter3d(
                x=seg[:, 0],
                y=seg[:, 1],
                z=seg[:, 2],
                mode="lines",
                line={"color": "firebrick", "width": 2},
                name="view dirs",
                opacity=0.7,
            )
        )
    fig.update_layout(
        title=title,
        scene={"xaxis_title": "X (left)", "yaxis_title": "Y (up)", "zaxis_title": "Z (fwd)"},
    )
    return fig


def plot_direction_marginals(dirs: torch.Tensor, bins: int = 60, *, fixed_ranges: bool = False) -> go.Figure:
    """Plot azimuth/elevation marginals for LUF unit directions ``Tensor[\"N 3\"]``."""
    elev = np.arcsin(dirs[:, 1])
    az = np.arctan2(dirs[:, 0], dirs[:, 2])

    fig = make_subplots(rows=1, cols=2, subplot_titles=("Azimuth", "Elevation"))
    fig.add_histogram(x=np.degrees(az), nbinsx=bins, row=1, col=1)
    fig.add_histogram(x=np.degrees(elev), nbinsx=bins, row=1, col=2)
    fig.update_xaxes(title="deg", row=1, col=1)
    fig.update_xaxes(title="deg", row=1, col=2)
    if fixed_ranges:
        fig.update_xaxes(range=[-180, 180], row=1, col=1)
        fig.update_xaxes(range=[-90, 90], row=1, col=2)
    return fig


def plot_radius_hist(
    offsets: np.ndarray,
    *,
    title: str = "Radius distribution",
    bins: int = 40,
) -> go.Figure:
    """Plot Euclidean radii of reference-frame offsets in metres."""
    r = np.linalg.norm(offsets, axis=1)
    fig = go.Figure(go.Histogram(x=r, nbinsx=bins))
    fig.update_layout(
        title=title,
        xaxis_title="radius (m)",
        yaxis_title="count",
    )
    return fig


def _normalise(v: torch.Tensor, *, eps: float = 1e-6) -> torch.Tensor:
    return v / v.norm(dim=-1, keepdim=True).clamp_min(eps)


def _roll_about_forward(
    *,
    forward: torch.Tensor,
    up_cam: torch.Tensor,
    up_ref: torch.Tensor,
    eps: float = 1e-6,
) -> torch.Tensor:
    """Compute signed roll (rad) of `up_cam` around `forward` relative to `up_ref`.

    The roll is defined by the "zero-roll" frame constructed from `(up_ref, forward)`:
    `left0 = normalize(up_ref × forward)` and `up0 = forward × left0`.

    Args:
        forward: ``Tensor["N 3"]`` unit (or unnormalised) forward vectors.
        up_cam: ``Tensor["N 3"]`` unit (or unnormalised) camera up vectors.
        up_ref: ``Tensor["3"]`` or ``Tensor["N 3"]`` reference up vector defining roll=0.
        eps: Stability constant for near-degenerate cross products.

    Returns:
        ``Tensor["N"]`` roll angles in radians in the range ``[-pi, pi]``.
    """

    forward = _normalise(forward, eps=eps)
    up_cam = _normalise(up_cam, eps=eps)

    if up_ref.ndim == 1:
        up_ref = up_ref.view(1, 3).expand_as(forward)
    else:
        while up_ref.ndim < forward.ndim:
            up_ref = up_ref.unsqueeze(0)
        up_ref = up_ref.expand_as(forward)
    up_ref = _normalise(up_ref, eps=eps)

    left0 = torch.cross(up_ref, forward, dim=-1)
    left0_norm = left0.norm(dim=-1, keepdim=True)
    degenerate = left0_norm.squeeze(-1) < eps
    if degenerate.any():
        alt = torch.tensor([1.0, 0.0, 0.0], device=forward.device, dtype=forward.dtype)
        alt = alt.view(1, 3).expand_as(forward)
        alt = alt - (alt * forward).sum(dim=-1, keepdim=True) * forward
        alt_norm = alt.norm(dim=-1, keepdim=True)
        second = alt_norm.squeeze(-1) < eps
        if second.any():
            alt2 = torch.tensor([0.0, 1.0, 0.0], device=forward.device, dtype=forward.dtype)
            alt2 = alt2.view(1, 3).expand_as(forward)
            alt2 = alt2 - (alt2 * forward).sum(dim=-1, keepdim=True) * forward
            alt[second] = alt2[second]
            alt_norm = alt.norm(dim=-1, keepdim=True)
        left0[degenerate] = alt[degenerate]
        left0_norm = left0.norm(dim=-1, keepdim=True)

    left0 = left0 / left0_norm.clamp_min(eps)
    up0 = _normalise(torch.cross(forward, left0, dim=-1), eps=eps)

    sin_term = (forward * torch.cross(up0, up_cam, dim=-1)).sum(dim=-1)
    cos_term = (up0 * up_cam).sum(dim=-1)
    return torch.atan2(sin_term, cos_term)


def plot_euler_world(
    candidates: CandidateSamplingResult, *, use_valid: bool = True, bins: int = 90, fixed_ranges: bool = True
) -> go.Figure:
    """Yaw/pitch/roll histograms in world frame for candidate cam poses.

    Notes:
        These angles are derived from the camera forward/up axes:
        - yaw: azimuth around world-up (world +Z), computed as ``atan2(fwd_x, fwd_y)`` (0 along +Y),
        - pitch: elevation above the world horizontal plane, computed as ``asin(fwd_z)``,
        - roll: twist around the forward axis relative to the roll-free frame induced by world-up.
    """

    poses = candidates.shell_poses
    if poses is None or poses._data is None:
        return go.Figure()
    mask = candidates.mask_valid if use_valid else torch.ones_like(candidates.mask_valid, dtype=torch.bool)
    poses_masked = PoseTW(poses._data[mask])
    r_wc = poses_masked.R
    fwd_w = r_wc[:, :, 2]
    up_w = r_wc[:, :, 1]
    yaw = torch.atan2(fwd_w[:, 0], fwd_w[:, 1])
    pitch = torch.asin(_normalise(fwd_w)[:, 2].clamp(-1.0, 1.0))
    from aria_nbv.utils.frames import world_up_tensor

    roll = _roll_about_forward(
        forward=fwd_w, up_cam=up_w, up_ref=world_up_tensor(device=fwd_w.device, dtype=fwd_w.dtype)
    )
    yaw, pitch, roll = [rad.rad2deg() for rad in (yaw, pitch, roll)]

    return _euler_histogram(
        yaw,
        pitch,
        roll,
        bins=bins,
        title="View yaw/pitch/roll (world frame, deg)",
        fixed_ranges=fixed_ranges,
    )


def plot_euler_reference(
    candidates: CandidateSamplingResult, *, use_valid: bool = True, bins: int = 90, fixed_ranges: bool = True
) -> go.Figure:
    """Yaw/pitch/roll of candidate cameras expressed in the reference rig frame.

    The reference frame is treated as LUF (x=left, y=up, z=fwd), matching the
    azimuth/elevation plots shown elsewhere in the diagnostics.
    """

    mask = candidates.mask_valid if use_valid else torch.ones_like(candidates.mask_valid, dtype=torch.bool)
    poses_world_cam = candidates.shell_poses[mask]
    poses_ref_cam = candidates.reference_pose.inverse().compose(poses_world_cam)
    r_rc = poses_ref_cam.R

    fwd_r = r_rc[:, :, 2]
    up_r = r_rc[:, :, 1]
    yaw = torch.atan2(fwd_r[:, 0], fwd_r[:, 2])
    pitch = torch.asin(_normalise(fwd_r)[:, 1].clamp(-1.0, 1.0))
    up_ref = torch.tensor([0.0, 1.0, 0.0], device=fwd_r.device, dtype=fwd_r.dtype)
    roll = _roll_about_forward(forward=fwd_r, up_cam=up_r, up_ref=up_ref)
    yaw, pitch, roll = [rad.rad2deg() for rad in (yaw, pitch, roll)]

    return _euler_histogram(
        yaw,
        pitch,
        roll,
        bins=bins,
        title="View yaw/pitch/roll (reference frame, deg)",
        fixed_ranges=fixed_ranges,
    )


def _euler_histogram(
    yaw_deg: torch.Tensor,
    pitch_deg: torch.Tensor,
    roll_deg: torch.Tensor,
    *,
    bins: int,
    title: str,
    fixed_ranges: bool,
) -> go.Figure:
    yaw_np = yaw_deg.detach().cpu().numpy().reshape(-1)
    pitch_np = pitch_deg.detach().cpu().numpy().reshape(-1)
    roll_np = roll_deg.detach().cpu().numpy().reshape(-1)

    fig = make_subplots(rows=1, cols=3, subplot_titles=("Yaw", "Pitch", "Roll"), horizontal_spacing=0.08)
    fig.add_histogram(x=yaw_np, nbinsx=bins, row=1, col=1)
    fig.add_histogram(x=pitch_np, nbinsx=bins, row=1, col=2)
    fig.add_histogram(x=roll_np, nbinsx=bins, row=1, col=3)
    if fixed_ranges:
        fig.update_xaxes(title_text="deg", range=[-180, 180], row=1, col=1)
        fig.update_xaxes(title_text="deg", range=[-90, 90], row=1, col=2)
        fig.update_xaxes(title_text="deg", range=[-180, 180], row=1, col=3)
    else:
        fig.update_xaxes(title_text="deg", row=1, col=1)
        fig.update_xaxes(title_text="deg", row=1, col=2)
        fig.update_xaxes(title_text="deg", row=1, col=3)
    fig.update_yaxes(title_text="count", row=1, col=1)
    fig.update_layout(title=title, height=320, margin={"l": 30, "r": 20, "t": 60, "b": 30}, showlegend=False)
    return fig


def plot_min_distance_to_mesh(
    *,
    snippet: EfmSnippetView,
    candidates: CandidateSamplingResult,
    distances: torch.Tensor,
) -> go.Figure:
    """Binary-coloured candidates: rejected (red, opaque) vs accepted (green, faint)."""

    dist_np = distances.detach().cpu().numpy().reshape(-1)
    mask_valid = candidates.mask_valid.detach().cpu().numpy().astype(bool)
    colors = ["rgba(0,200,0,0.2)" if v else "rgba(220,0,0,0.9)" for v in mask_valid.tolist()]
    hover = [f"dist={d:.3f} m<br>valid={bool(v)}" for d, v in zip(dist_np.tolist(), mask_valid.tolist(), strict=False)]

    builder = (
        CandidatePlotBuilder.from_snippet(snippet, title="Min distance to mesh")
        .attach_candidate_results(candidates)
        .add_mesh()
        .add_candidate_points(
            use_valid=False,
            color=np.array(colors),
            name="Candidates",
            opacity=1.0,
            size=4,
            hovertext=hover,
        )
        .add_reference_axes(display_rotate=False)
    )
    return builder.finalize()


def plot_path_collision_segments(
    *,
    snippet: EfmSnippetView,
    candidates: CandidateSamplingResult,
    collision_mask: torch.Tensor,
) -> go.Figure:
    """Plot segments from reference pose to candidates rejected by path-collision rule."""

    mask_np = collision_mask.detach().cpu().numpy().astype(bool)
    colors = ["rgba(0,200,0,0.2)" if not m else "rgba(220,0,0,0.9)" for m in mask_np.tolist()]

    builder = (
        CandidatePlotBuilder.from_snippet(snippet, title="Path collision segments")
        .attach_candidate_results(candidates)
        .add_mesh()
    )

    if mask_np.any():
        builder.add_path_collision_segments(collision_mask)

    builder.add_candidate_points(use_valid=False, color=np.array(colors), name="Candidates", opacity=1.0, size=4)
    builder.add_reference_axes(display_rotate=False)
    return builder.finalize()


def plot_rule_rejection_bar(candidates: CandidateSamplingResult) -> go.Figure:
    """Bar chart of rejection counts per rule using cumulative masks."""

    masks = candidates.masks
    if not isinstance(masks, dict) or len(masks) == 0:
        fig = go.Figure()
        fig.update_layout(title="Rule rejections (no masks collected)")
        return fig

    prev = torch.ones_like(next(iter(masks.values())), dtype=torch.bool)
    names: list[str] = []
    counts: list[int] = []
    for name, mask in masks.items():
        rej = prev & (~mask)
        names.append(name)
        counts.append(int(rej.sum().item()))
        prev = mask

    fig = go.Figure(go.Bar(x=names, y=counts, marker_color="steelblue"))
    fig.update_layout(title="Rejections per rule", xaxis_title="Rule", yaxis_title="# rejected")
    return fig


def plot_rule_masks(
    *,
    snippet: EfmSnippetView,
    shell_poses: torch.Tensor,
    masks: torch.Tensor,
    rule_names: list[str],
    sample_n: int = 500,
) -> go.Figure:
    """Visualise per-rule pruning on raw samples."""

    shell_np = shell_poses.detach().cpu().numpy()
    pts_all = shell_np[:, 9:12] if shell_np.shape[1] == 12 else shell_np
    # Align lengths defensively in case masks and shell_poses differ (e.g., legacy caches).
    max_len = min(sample_n, pts_all.shape[0], masks.shape[1])
    pts = pts_all[:max_len]
    builder = SnippetPlotBuilder.from_snippet(snippet, title="Rule-wise pruning").add_mesh()
    palette = ["#4caf50", "#f44336", "#2196f3", "#ff9800", "#9c27b0"]
    for ridx, name in enumerate(rule_names):
        if masks.shape[0] <= ridx:
            break
        valid = masks[ridx, :max_len].detach().cpu().numpy().astype(bool)
        color = palette[ridx % len(palette)]
        builder = builder.add_points(
            pts[valid],
            name=f"{name}: kept",
            color=color,
            size=3,
            opacity=0.65,
        )
    return builder.finalize()
