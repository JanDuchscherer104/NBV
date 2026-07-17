"""Plotly diagnostics for legacy and experimental VIN encodings.

The active VIN v3 plotting helpers live in `aria_nbv.vin.diagnostics.plotting`.
This module contains app-facing figures for legacy shell/LFF experiments and
therefore remains under the canonical diagnostics package rather than
`aria_nbv.vin.experimental`.
"""

from __future__ import annotations

import math
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import matplotlib as mpl
import numpy as np
import plotly.graph_objects as go  # type: ignore[import-untyped]
import plotly.io as pio
import seaborn as sns
import torch
from e3nn import o3  # type: ignore[import-untyped]
from plotly import colors as plotly_colors  # type: ignore[import-untyped]
from plotly.subplots import make_subplots  # type: ignore[import-untyped]
from pytorch3d.renderer.cameras import (
    PerspectiveCameras,  # type: ignore[import-untyped]
)

from ...utils.reporting import _pretty_label
from ..geometry import build_frustum_points_world_p3d as _build_frustum_points_world_p3d
from ..types.diagnostics import VinForwardDiagnostics
from ._frustum_adapter import _camera_tw_from_p3d, _frustum_builder_stub, _pose_from_p3d_camera
from ._plot_primitives import (
    _histogram_bar,
    _histogram_edges,
    _line_trace,
    _scatter3d,
)

if TYPE_CHECKING:
    from ..encoders import LearnableFourierFeatures


@dataclass
class PlottingConfig:
    """Reusable Matplotlib, seaborn, and Plotly presentation settings."""

    style: str = "whitegrid"
    """Seaborn axes-style name passed to `seaborn.set_theme`."""

    palette: str | list[str] = "tab10"
    """Seaborn palette name or explicit color sequence."""

    font_family: str = "DejaVu Sans"
    """Matplotlib font-family name."""

    font_scale: float = 1.0
    """Multiplicative seaborn font scale."""

    title_size: int = 14
    """Matplotlib axes-title size in points."""

    label_size: int = 12
    """Matplotlib axes-label size in points."""

    tick_size: int = 10
    """Matplotlib tick-label size in points."""

    figure_dpi: int = 100
    """Default Matplotlib figure resolution in dots per inch."""

    context: str = "notebook"
    """Seaborn plotting-context name."""

    plotly_template: str = "plotly_white"
    """Plotly template name installed in `plotly.io.templates`."""

    plotly_colorway: list[str] | None = None
    """Optional Plotly categorical color sequence for the selected template."""

    seaborn_kwargs: dict[str, Any] = field(default_factory=dict)
    """Additional keyword arguments forwarded to `seaborn.set_theme`."""

    def apply_global(self) -> None:
        """Apply plotting style globally (no automatic restore)."""
        palette_colors = sns.color_palette(self.palette)
        sns.set_theme(
            style=self.style,
            palette=palette_colors,
            context=self.context,
            **self.seaborn_kwargs,
        )
        sns.set_theme(font_scale=self.font_scale)
        mpl.rcParams.update(
            {
                "axes.titlesize": self.title_size,
                "axes.labelsize": self.label_size,
                "xtick.labelsize": self.tick_size,
                "ytick.labelsize": self.tick_size,
                "figure.dpi": self.figure_dpi,
                "axes.prop_cycle": mpl.cycler(color=palette_colors),
                "font.family": [self.font_family],
            },
        )

        pio.templates.default = self.plotly_template
        if self.plotly_colorway is not None:
            pio.templates[self.plotly_template].layout.colorway = self.plotly_colorway

    @contextmanager
    def apply(self) -> Generator[None, None, None]:
        """Apply style within a context, restoring previous settings afterwards."""
        keys = [
            "axes.titlesize",
            "axes.labelsize",
            "xtick.labelsize",
            "ytick.labelsize",
            "figure.dpi",
        ]
        prev = {k: mpl.rcParams.get(k) for k in keys}
        prev_prop_cycle = mpl.rcParams.get("axes.prop_cycle")
        prev_font_family = mpl.rcParams.get("font.family")
        prev_plotly_template = pio.templates.default
        prev_plotly_colorway = getattr(
            pio.templates[prev_plotly_template].layout,
            "colorway",
            None,
        )
        target_plotly_colorway = getattr(
            pio.templates[self.plotly_template].layout,
            "colorway",
            None,
        )

        palette_colors = sns.color_palette(self.palette)
        sns.set_theme(
            style=self.style,
            palette=palette_colors,
            context=self.context,
            **self.seaborn_kwargs,
        )
        sns.set_theme(font_scale=self.font_scale)
        mpl.rcParams.update(
            {
                "axes.titlesize": self.title_size,
                "axes.labelsize": self.label_size,
                "xtick.labelsize": self.tick_size,
                "ytick.labelsize": self.tick_size,
                "figure.dpi": self.figure_dpi,
                "axes.prop_cycle": mpl.cycler(color=palette_colors),
                "font.family": [self.font_family],
            },
        )
        pio.templates.default = self.plotly_template
        if self.plotly_colorway is not None:
            pio.templates[self.plotly_template].layout.colorway = self.plotly_colorway
        try:
            yield
        finally:
            pio.templates.default = prev_plotly_template
            pio.templates[prev_plotly_template].layout.colorway = prev_plotly_colorway
            if self.plotly_colorway is not None:
                pio.templates[self.plotly_template].layout.colorway = target_plotly_colorway
            mpl.rcParams.update(prev)
            mpl.rcParams["axes.prop_cycle"] = prev_prop_cycle
            mpl.rcParams["font.family"] = prev_font_family


DEFAULT_PLOT_CFG = PlottingConfig()


def _save_plotly_fig(fig: go.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(path, include_plotlyjs="cdn")


def _unit_dir_from_az_el(*, az: torch.Tensor, el: torch.Tensor) -> torch.Tensor:
    """Convert az/el (LUF: az=atan2(x,z), el=asin(y)) to unit vectors."""
    x = torch.cos(el) * torch.sin(az)
    y = torch.sin(el)
    z = torch.cos(el) * torch.cos(az)
    v = torch.stack([x, y, z], dim=-1)
    return v / (v.norm(dim=-1, keepdim=True).clamp_min(1e-8))


def _build_shell_descriptor_figure(
    *,
    u: torch.Tensor,
    f: torch.Tensor,
    r: torch.Tensor,
) -> go.Figure:
    """Build a 3D Plotly figure for one candidate shell descriptor."""
    if u.numel() == 0 or f.numel() == 0 or r.numel() == 0:
        return go.Figure()

    u0 = u[0].detach().cpu().numpy()
    f0 = f[0].detach().cpu().numpy()
    r0 = float(r[0].detach().cpu().item())
    t0 = u0 * r0

    axis_len = 1.2
    lim = 2.0

    fig = go.Figure()

    # Reference axes (LUF).
    axes = [
        (np.array([0.0, 0.0, 0.0]), np.array([axis_len, 0.0, 0.0]), "x (left)"),
        (np.array([0.0, 0.0, 0.0]), np.array([0.0, axis_len, 0.0]), "y (up)"),
        (np.array([0.0, 0.0, 0.0]), np.array([0.0, 0.0, axis_len]), "z (fwd)"),
    ]
    for start, end, label in axes:
        fig.add_trace(_line_trace(start, end, color="#285f82", name=label, width=6))
        fig.add_trace(
            go.Scatter3d(
                x=[end[0]],
                y=[end[1]],
                z=[end[2]],
                mode="text",
                text=[label],
                textposition="top center",
                showlegend=False,
            ),
        )

    fig.add_trace(
        go.Scatter3d(
            x=[t0[0]],
            y=[t0[1]],
            z=[t0[2]],
            mode="markers",
            marker={"size": 6, "color": "#fc5555"},
            name="candidate center",
        ),
    )
    fig.add_trace(_line_trace(np.zeros(3), t0, color="#fc5555", name="t = r·u", width=6))
    fig.add_trace(_line_trace(t0, t0 + u0, color="#285f82", name="u (pos dir)", width=6))
    fig.add_trace(_line_trace(t0, t0 + f0, color="#2a9d8f", name="f (forward)", width=6))

    fig.update_layout(
        title=_pretty_label("Shell descriptor (one candidate): t, r, u, f"),
        scene={
            "aspectmode": "data",
            "xaxis": {"title": _pretty_label("X (left)"), "range": [-lim, lim]},
            "yaxis": {"title": _pretty_label("Y (up)"), "range": [-lim, lim]},
            "zaxis": {"title": _pretty_label("Z (fwd)"), "range": [-lim, lim]},
        },
        legend={"orientation": "h", "y": -0.1},
        margin={"l": 0, "r": 0, "t": 50, "b": 0},
    )

    return fig


def build_lff_response_figures(
    pose_encoder: LearnableFourierFeatures,
    *,
    input_dim: int,
    input_range: tuple[float, float],
    num_samples: int = 200,
    max_features: int = 96,
) -> dict[str, go.Figure]:
    """Visualize LFF Fourier features and MLP output along one input dimension."""
    low, high = float(input_range[0]), float(input_range[1])
    xs = torch.linspace(low, high, steps=int(num_samples))
    x = torch.zeros((xs.numel(), pose_encoder.input_dim), dtype=torch.float32)
    x[:, input_dim] = xs

    with torch.no_grad():
        xwr = x @ pose_encoder.Wr.T
        fourier = torch.cat([torch.cos(xwr), torch.sin(xwr)], dim=-1) / math.sqrt(
            float(pose_encoder.fourier_dim),
        )
        fourier_plot = fourier[:, : int(max_features)]
        mlp_out = pose_encoder.mlp(fourier)
        mlp_plot = mlp_out[:, : int(max_features)]

    fourier_np = fourier_plot.detach().cpu().numpy().T
    mlp_np = mlp_plot.detach().cpu().numpy().T
    xs_np = xs.detach().cpu().numpy()

    fig_fourier = go.Figure(
        go.Heatmap(
            z=fourier_np,
            x=xs_np,
            colorscale="RdBu",
            colorbar={"title": _pretty_label("value")},
        ),
    )
    fig_fourier.update_layout(
        title=_pretty_label("LFF Fourier features (pre-MLP)"),
        xaxis_title=_pretty_label(f"input dim {input_dim}"),
        yaxis_title=_pretty_label("feature index"),
    )

    fig_mlp = go.Figure(
        go.Heatmap(
            z=mlp_np,
            x=xs_np,
            colorscale="RdBu",
            colorbar={"title": _pretty_label("value")},
        ),
    )
    fig_mlp.update_layout(
        title=_pretty_label("LFF output (post-MLP)"),
        xaxis_title=_pretty_label(f"input dim {input_dim}"),
        yaxis_title=_pretty_label("feature index"),
    )

    return {
        "lff_response_fourier": fig_fourier,
        "lff_response_mlp": fig_mlp,
    }


def build_frustum_samples_figure(
    debug: VinForwardDiagnostics,
    *,
    p3d_cameras: PerspectiveCameras,
    candidate_index: int,
    grid_size: int,
    depths_m: list[float],
) -> go.Figure:
    """Plot frustum sample points colored by token validity (world frame)."""
    points_world_flat = _build_frustum_points_world_p3d(
        p3d_cameras,
        grid_size=int(grid_size),
        depths_m=list(depths_m),
    )
    num_cams = int(points_world_flat.shape[0])

    token_valid = getattr(debug, "token_valid", None)
    if not isinstance(token_valid, torch.Tensor):
        return go.Figure()
    if token_valid.ndim == 3:
        token_valid = token_valid[0]
    if candidate_index >= token_valid.shape[0]:
        return go.Figure()

    if num_cams == 0:
        return go.Figure()
    cam_idx = min(max(int(candidate_index), 0), num_cams - 1)
    points = points_world_flat[cam_idx]

    valid = token_valid[candidate_index].reshape(-1).detach().cpu().numpy()
    points_np = points.detach().cpu().numpy()

    frustum_pose = _pose_from_p3d_camera(p3d_cameras, cam_idx)
    frustum_cam = _camera_tw_from_p3d(p3d_cameras, cam_idx)
    builder = _frustum_builder_stub(
        frustum_pose,
        title=_pretty_label("Frustum samples (world) colored by token validity"),
    )
    fig = builder.fig if builder is not None else go.Figure()
    if points_np.shape[0] > 0:
        fig.add_trace(
            _scatter3d(
                points_np[valid],
                name="valid",
                color="#2a9d8f",
                size=2,
                opacity=0.8,
            ),
        )
        fig.add_trace(
            _scatter3d(
                points_np[~valid],
                name="invalid",
                color="#e76f51",
                size=2,
                opacity=0.4,
            ),
        )
        if builder is not None:
            builder._update_scene_ranges(points_np)

    if builder is not None and frustum_cam is not None and frustum_pose is not None:
        frustum_scale = float(max(depths_m) if depths_m else 1.0)
        builder._add_frusta_for_poses(
            cams=frustum_cam,
            poses=frustum_pose,
            scale=frustum_scale,
            color="#ff4d4d",
            name="candidate frustum",
            max_frustums=None,
            include_axes=False,
            include_center=True,
        )

    fig.update_layout(
        title=_pretty_label("Frustum samples (world) colored by token validity"),
        scene=dict(aspectmode="data", **(builder.scene_ranges if builder is not None else {})),
        margin={"l": 0, "r": 0, "t": 40, "b": 0},
    )
    return fig


def build_alignment_figures(
    debug: VinForwardDiagnostics,
    *,
    log1p_counts: bool = False,
) -> dict[str, go.Figure]:
    """Plot alignment histograms between candidates and voxel frame."""
    figs: dict[str, go.Figure] = {}
    cand_forward = debug.candidate_forward_dir_rig.reshape(-1, 3)
    cand_center = debug.candidate_center_dir_rig.reshape(-1, 3)
    view_alignment = debug.view_alignment.reshape(-1).detach().cpu().numpy()

    edges = _histogram_edges([view_alignment], bins=60)
    fig_view = go.Figure(
        _histogram_bar(
            view_alignment,
            edges=edges,
            name="alignment",
            log1p_counts=log1p_counts,
        ),
    )
    fig_view.update_layout(
        title=_pretty_label("View alignment dot(f, -u)"),
        xaxis_title=_pretty_label("dot(f, -u)"),
        yaxis_title=_pretty_label("log1p(count)" if log1p_counts else "count"),
    )
    figs["view_alignment"] = fig_view

    if debug.voxel_forward_dir_rig is not None and debug.voxel_center_dir_rig is not None:
        voxel_forward = debug.voxel_forward_dir_rig.reshape(1, 3)
        voxel_center = debug.voxel_center_dir_rig.reshape(1, 3)
        dot_forward = (cand_forward * voxel_forward).sum(dim=-1).detach().cpu().numpy()
        dot_center = (cand_center * voxel_center).sum(dim=-1).detach().cpu().numpy()

        edges_fwd = _histogram_edges([dot_forward], bins=60)
        fig_fwd = go.Figure(
            _histogram_bar(
                dot_forward,
                edges=edges_fwd,
                name="dot",
                log1p_counts=log1p_counts,
            ),
        )
        fig_fwd.update_layout(
            title=_pretty_label("dot(candidate forward, voxel forward)"),
            xaxis_title=_pretty_label("dot"),
            yaxis_title=_pretty_label("log1p(count)" if log1p_counts else "count"),
        )
        figs["forward_vs_voxel"] = fig_fwd

        edges_center = _histogram_edges([dot_center], bins=60)
        fig_center = go.Figure(
            _histogram_bar(
                dot_center,
                edges=edges_center,
                name="dot",
                log1p_counts=log1p_counts,
            ),
        )
        fig_center.update_layout(
            title=_pretty_label("dot(candidate center dir, voxel center dir)"),
            xaxis_title=_pretty_label("dot"),
            yaxis_title=_pretty_label("log1p(count)" if log1p_counts else "count"),
        )
        figs["center_vs_voxel"] = fig_center

    return figs


def build_prediction_alignment_figure(
    debug: VinForwardDiagnostics,
    *,
    expected_normalized: np.ndarray,
) -> go.Figure:
    """Scatter of predicted score vs view alignment."""
    view_alignment = debug.view_alignment.reshape(-1).detach().cpu().numpy()
    fig = go.Figure(
        data=go.Scatter(
            x=view_alignment,
            y=expected_normalized,
            mode="markers",
            marker={"size": 5, "color": expected_normalized, "colorscale": "Viridis"},
        ),
    )
    fig.update_layout(
        title=_pretty_label("Predicted score vs view alignment"),
        xaxis_title=_pretty_label("dot(f, -u)"),
        yaxis_title=_pretty_label("expected normalized"),
    )
    return fig


def build_field_token_histograms(
    debug: VinForwardDiagnostics,
    *,
    channel_names: list[str],
    max_channels: int = 4,
    max_samples: int = 200_000,
    log1p_counts: bool = False,
) -> dict[str, go.Figure]:
    """Overlay histograms of field values and sampled token values."""
    field = debug.field
    tokens = debug.tokens
    if field.ndim != 5 or tokens.ndim != 4:
        return {}

    field = field[0]
    tokens = tokens[0]
    num_channels = min(max_channels, field.shape[0])

    figs: dict[str, go.Figure] = {}
    for i in range(num_channels):
        field_vals = field[i].reshape(-1)
        token_vals = tokens[..., i].reshape(-1)

        if field_vals.numel() > max_samples:
            idx = torch.randperm(field_vals.numel())[:max_samples]
            field_vals = field_vals[idx]
        if token_vals.numel() > max_samples:
            idx = torch.randperm(token_vals.numel())[:max_samples]
            token_vals = token_vals[idx]

        label = channel_names[i] if i < len(channel_names) else f"ch{i}"
        field_np = field_vals.detach().cpu().numpy()
        token_np = token_vals.detach().cpu().numpy()
        edges = _histogram_edges([field_np, token_np], bins=60)
        fig = go.Figure()
        fig.add_trace(
            _histogram_bar(
                field_np,
                edges=edges,
                name="field",
                log1p_counts=log1p_counts,
            ),
        )
        fig.add_trace(
            _histogram_bar(
                token_np,
                edges=edges,
                name="tokens",
                log1p_counts=log1p_counts,
            ),
        )
        fig.update_layout(
            barmode="overlay",
            title=_pretty_label(f"Field vs tokens: {label}"),
            xaxis_title=_pretty_label("value"),
            yaxis_title=_pretty_label("log1p(count)" if log1p_counts else "count"),
        )
        figs[label] = fig

    return figs


def _build_sh_components_figure(
    *,
    lmax: int,
    normalization: str,
    n_az: int = 220,
    n_el: int = 110,
) -> go.Figure:
    """Plot a few real SH components as Plotly heatmaps over az/el."""
    az = torch.linspace(-torch.pi, torch.pi, steps=int(n_az))
    el = torch.linspace(-0.5 * torch.pi, 0.5 * torch.pi, steps=int(n_el))
    az_grid, el_grid = torch.meshgrid(az, el, indexing="xy")
    dirs = _unit_dir_from_az_el(az=az_grid, el=el_grid)

    irreps = o3.Irreps.spherical_harmonics(int(lmax))
    y = o3.spherical_harmonics(
        irreps,
        dirs,
        normalize=True,
        normalization=str(normalization),
    )

    lm: list[tuple[int, int]] = []
    for degree in range(int(lmax) + 1):
        for order in range(-degree, degree + 1):
            lm.append((degree, order))

    wanted = [(0, 0), (1, -1), (1, 0), (1, 1)]
    idxs: list[int] = []
    titles: list[str] = []
    for degree, order in wanted:
        if (degree, order) not in lm:
            continue
        idx = lm.index((degree, order))
        idxs.append(idx)
        titles.append(f"Y(l={degree}, m={order}) component {idx}")

    if not idxs:
        return go.Figure()

    cols = 2
    rows = int(np.ceil(len(idxs) / cols))
    fig = make_subplots(
        rows=rows,
        cols=cols,
        subplot_titles=tuple(_pretty_label(title) for title in titles),
    )

    az_deg = np.degrees(az.detach().cpu().numpy())
    el_deg = np.degrees(el.detach().cpu().numpy())

    for i, idx in enumerate(idxs):
        r = i // cols + 1
        c = i % cols + 1
        comp = y[..., idx].detach().cpu().numpy().T
        fig.add_trace(
            go.Heatmap(
                x=az_deg,
                y=el_deg,
                z=comp,
                colorscale="RdBu",
                colorbar={"title": _pretty_label("value")},
            ),
            row=r,
            col=c,
        )
        fig.update_xaxes(title_text=_pretty_label("azimuth (deg)"), row=r, col=c)
        fig.update_yaxes(title_text=_pretty_label("elevation (deg)"), row=r, col=c)

    fig.update_layout(
        title=_pretty_label(
            f"Real spherical harmonics over directions on S^2 (lmax={lmax})",
        ),
        height=320 * rows,
    )
    return fig


def _build_radius_fourier_figure(
    *,
    r_min: float,
    r_max: float,
    freqs: Iterable[float],
    log1p_counts: bool = False,
) -> go.Figure:
    """Plot sin radius Fourier features for linear r (meters)."""
    r = torch.linspace(float(r_min), float(r_max), steps=500).view(-1, 1)
    r_np = r.squeeze(1).numpy()

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=tuple(_pretty_label(name) for name in ("radius r (meters)", "sin(2π ω r)")),
    )

    edges = _histogram_edges([r_np], bins=50)
    fig.add_trace(
        _histogram_bar(
            r_np,
            edges=edges,
            name="r",
            color="#285f82",
            log1p_counts=log1p_counts,
        ),
        row=1,
        col=1,
    )
    fig.update_xaxes(title_text=_pretty_label("r"), row=1, col=1)
    fig.update_yaxes(
        title_text=_pretty_label("log1p(count)" if log1p_counts else "count"),
        row=1,
        col=1,
    )

    freq_list = list(freqs)
    colors = plotly_colors.sample_colorscale(
        "Viridis",
        np.linspace(0.15, 0.85, len(freq_list)),
    )
    for color, w in zip(colors, freq_list, strict=True):
        y = torch.sin(2.0 * torch.pi * float(w) * r).squeeze(1).numpy()
        fig.add_trace(
            go.Scatter(
                x=r_np,
                y=y,
                mode="lines",
                line={"color": color},
                name=f"ω={w:g}",
            ),
            row=1,
            col=2,
        )

    fig.update_xaxes(title_text=_pretty_label("r (m)"), row=1, col=2)
    fig.update_yaxes(title_text=_pretty_label("value"), row=1, col=2)
    fig.update_layout(title=_pretty_label("1D Fourier features for radius (linear input)"))
    return fig


def _build_lff_weight_figures(
    *,
    pose_encoder: LearnableFourierFeatures,
) -> dict[str, go.Figure]:
    """Visualize Learnable Fourier Feature projection weights."""
    wr = pose_encoder.Wr.detach().cpu()
    wr_np = wr.numpy()
    fig_wr = go.Figure(
        go.Heatmap(
            z=wr_np,
            colorscale="RdBu",
            colorbar={"title": _pretty_label("value")},
        ),
    )
    fig_wr.update_layout(
        title=_pretty_label("LFF projection weights (Wr)"),
        xaxis_title=_pretty_label("input dim"),
        yaxis_title=_pretty_label("frequency index"),
    )

    norms = torch.linalg.vector_norm(wr, dim=0).numpy()
    fig_norm = go.Figure(
        go.Bar(
            x=list(range(len(norms))),
            y=norms,
        ),
    )
    fig_norm.update_layout(
        title=_pretty_label("LFF Wr column norms (per input dim)"),
        xaxis_title=_pretty_label("input dim"),
        yaxis_title=_pretty_label("norm"),
    )

    return {
        "lff_wr": fig_wr,
        "lff_wr_norms": fig_norm,
    }


def build_vin_encoding_figures(
    debug: VinForwardDiagnostics,
    *,
    lmax: int,
    sh_normalization: str,
    radius_freqs: Iterable[float],
    pose_encoder_lff: LearnableFourierFeatures | None = None,
    include_legacy_sh: bool = True,
    log1p_counts: bool = False,
) -> dict[str, go.Figure]:
    """Build Plotly figures from VIN forward diagnostics."""
    u = debug.candidate_center_dir_rig.reshape(-1, 3)
    f = debug.candidate_forward_dir_rig.reshape(-1, 3)
    r = debug.candidate_radius_m.reshape(-1, 1)

    r_min = float(r.min().item()) if r.numel() else 0.0
    r_max = float(r.max().item()) if r.numel() else 1.0
    if r_min == r_max:
        r_max = r_min + 1e-3

    figs: dict[str, go.Figure] = {}
    figs["shell_descriptor"] = _build_shell_descriptor_figure(u=u, f=f, r=r)
    if pose_encoder_lff is not None:
        figs.update(_build_lff_weight_figures(pose_encoder=pose_encoder_lff))
    if include_legacy_sh:
        figs["sh_components"] = _build_sh_components_figure(
            lmax=int(lmax),
            normalization=str(sh_normalization),
        )
        figs["radius_fourier_features"] = _build_radius_fourier_figure(
            r_min=r_min,
            r_max=r_max,
            freqs=radius_freqs,
            log1p_counts=log1p_counts,
        )
    return figs


def build_candidate_encoding_figures(
    debug: VinForwardDiagnostics,
    *,
    lmax: int,
    sh_normalization: str,
    radius_freqs: Iterable[float],
    pose_encoder_lff: LearnableFourierFeatures | None = None,
    include_legacy_sh: bool = True,
    max_candidates: int = 512,
    max_sh_components: int = 64,
    max_pose_dims: int = 128,
) -> dict[str, go.Figure]:
    """Build Plotly figures for actual candidate encodings."""
    u = debug.candidate_center_dir_rig.reshape(-1, 3)
    f = debug.candidate_forward_dir_rig.reshape(-1, 3)
    r = debug.candidate_radius_m.reshape(-1, 1)
    pose_enc = debug.pose_enc.reshape(-1, debug.pose_enc.shape[-1])

    n = int(u.shape[0])
    if n == 0:
        return {}

    if n > max_candidates:
        idx = torch.randperm(n, device=u.device)[:max_candidates]
        u = u[idx]
        f = f[idx]
        r = r[idx]
        pose_enc = pose_enc[idx]

    figs: dict[str, go.Figure] = {}

    if include_legacy_sh:
        irreps = o3.Irreps.spherical_harmonics(int(lmax))
        u_sh = o3.spherical_harmonics(
            irreps,
            u.to(torch.float32),
            normalize=True,
            normalization=str(sh_normalization),
        )
        f_sh = o3.spherical_harmonics(
            irreps,
            f.to(torch.float32),
            normalize=True,
            normalization=str(sh_normalization),
        )

        if u_sh.shape[1] > max_sh_components:
            u_sh = u_sh[:, :max_sh_components]
            f_sh = f_sh[:, :max_sh_components]

        u_np = u_sh.detach().cpu().numpy()
        f_np = f_sh.detach().cpu().numpy()

        figs["sh_components_u"] = go.Figure(
            go.Heatmap(
                z=u_np,
                colorscale="RdBu",
                colorbar={"title": _pretty_label("value")},
            ),
        )
        figs["sh_components_u"].update_layout(
            title=_pretty_label("SH components for candidate center directions (u)"),
            xaxis_title=_pretty_label("component index"),
            yaxis_title=_pretty_label("candidate index"),
        )

        figs["sh_components_f"] = go.Figure(
            go.Heatmap(
                z=f_np,
                colorscale="RdBu",
                colorbar={"title": _pretty_label("value")},
            ),
        )
        figs["sh_components_f"].update_layout(
            title=_pretty_label("SH components for candidate forward directions (f)"),
            xaxis_title=_pretty_label("component index"),
            yaxis_title=_pretty_label("candidate index"),
        )

        freq_list = list(radius_freqs)
        if freq_list:
            r_f32 = r.to(torch.float32)
            feats: list[torch.Tensor] = []
            for w in freq_list:
                omega = 2.0 * torch.pi * float(w)
                feats.append(torch.sin(omega * r_f32))
                feats.append(torch.cos(omega * r_f32))
            r_feat = torch.cat(feats, dim=-1)
            r_np = r_feat.detach().cpu().numpy()
            figs["radius_fourier_samples"] = go.Figure(
                go.Heatmap(
                    z=r_np,
                    colorscale="RdBu",
                    colorbar={"title": _pretty_label("value")},
                ),
            )
            figs["radius_fourier_samples"].update_layout(
                title=_pretty_label("Radius Fourier features for candidates (sin/cos)"),
                xaxis_title=_pretty_label("feature index"),
                yaxis_title=_pretty_label("candidate index"),
            )

    if pose_encoder_lff is not None:
        pose_vec = getattr(debug, "pose_vec", None)
        if pose_vec is None:
            view_alignment = debug.view_alignment.reshape(-1, 1)
            pose_vec = torch.cat([u, f, r, view_alignment], dim=-1)
        else:
            pose_vec = pose_vec.reshape(-1, pose_vec.shape[-1])
        xwr = pose_vec @ pose_encoder_lff.Wr.T
        fourier = torch.cat([torch.cos(xwr), torch.sin(xwr)], dim=-1) / math.sqrt(
            float(pose_encoder_lff.fourier_dim),
        )
        if fourier.shape[1] > max_pose_dims:
            fourier = fourier[:, :max_pose_dims]
        fourier_np = fourier.detach().cpu().numpy()
        figs["lff_fourier_features"] = go.Figure(
            go.Heatmap(
                z=fourier_np,
                colorscale="RdBu",
                colorbar={"title": _pretty_label("value")},
            ),
        )
        figs["lff_fourier_features"].update_layout(
            title=_pretty_label("LFF Fourier features (pre-MLP)"),
            xaxis_title=_pretty_label("feature index"),
            yaxis_title=_pretty_label("candidate index"),
        )

    if pose_enc.shape[1] > max_pose_dims:
        pose_enc = pose_enc[:, :max_pose_dims]
    enc_np = pose_enc.detach().cpu().numpy()
    figs["pose_encoding"] = go.Figure(
        go.Heatmap(
            z=enc_np,
            colorscale="RdBu",
            colorbar={"title": _pretty_label("value")},
        ),
    )
    figs["pose_encoding"].update_layout(
        title=_pretty_label("Pose encoder output (candidate embeddings)"),
        xaxis_title=_pretty_label("embedding dim"),
        yaxis_title=_pretty_label("candidate index"),
    )

    return figs


def plot_vin_encodings_from_debug(
    debug: VinForwardDiagnostics,
    *,
    out_dir: Path,
    lmax: int,
    sh_normalization: str,
    radius_freqs: Iterable[float],
    file_stem_prefix: str,
    pose_encoder_lff: LearnableFourierFeatures | None = None,
    include_legacy_sh: bool = True,
) -> dict[str, Path]:
    """Generate VIN encoding plots using Plotly and persist them as HTML.

    Args:
        debug: Diagnostics from `VinModel.forward_with_debug`.
        out_dir: Output directory for saved figures.
        lmax: Maximum SH degree to visualize (legacy plots only).
        sh_normalization: Spherical harmonics normalization mode (legacy plots only).
        radius_freqs: Frequencies for the legacy radius Fourier feature plot.
        file_stem_prefix: Prefix used for output filenames.
        pose_encoder_lff: Optional LFF encoder used for weight visualizations.
        include_legacy_sh: Whether to include legacy SH/Fourier plots.

    Returns:
        Mapping of figure labels to saved HTML paths.
    """
    build_vin_encoding_figures(
        debug,
        lmax=lmax,
        sh_normalization=sh_normalization,
        radius_freqs=radius_freqs,
        pose_encoder_lff=pose_encoder_lff,
        include_legacy_sh=include_legacy_sh,
    )


__all__ = [
    "DEFAULT_PLOT_CFG",
    "PlottingConfig",
    "build_alignment_figures",
    "build_candidate_encoding_figures",
    "build_field_token_histograms",
    "build_frustum_samples_figure",
    "build_lff_response_figures",
    "build_prediction_alignment_figure",
    "build_vin_encoding_figures",
    "plot_vin_encodings_from_debug",
]
