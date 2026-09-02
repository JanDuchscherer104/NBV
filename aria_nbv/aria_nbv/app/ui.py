"""Sidebar controls that construct typed NBV pipeline configurations.

The helpers provide dataset, candidate, renderer, and oracle settings while
keeping Streamlit widget state separate from compute and cache orchestration.
"""

from __future__ import annotations

import streamlit as st
import torch

from ..data_handling import AseEfmDatasetConfig
from ..oracle._scoring import PreparedRriScorerConfig
from ..pose_generation import CandidateViewGeneratorConfig, candidate_config_ui_bounds
from ..pose_generation.types import CollisionBackend, SamplingStrategy, ViewDirectionMode
from ..rendering import CandidateDepthRendererConfig, Pytorch3DDepthRendererConfig
from ..utils import Verbosity
from .panels.configuration import render_typed_config_fields


def dataset_config_ui(
    ui: st.delta_generator.DeltaGenerator, *, verbosity: Verbosity, is_debug: bool
) -> AseEfmDatasetConfig:
    """Render observed-snippet controls and return a fresh dataset config.

    Args:
        ui: Streamlit container that owns the widgets.
        verbosity: Project logging level copied into the dataset config.
        is_debug: Initial dataset-debug toggle.

    Returns:
        Dataset configuration for EFM evidence and attached evaluation assets.
    """

    ui.subheader("Dataset")
    mesh_ratio = ui.slider("mesh decimation ratio", 0.0, 1.0, 0.1, step=0.02)
    crop_enable = ui.checkbox("crop mesh", value=False)
    mesh_crop_margin = ui.slider("crop margin (m)", 0.0, 2.0, 0.5, step=0.05) if crop_enable else None
    mesh_keep_ratio = ui.slider("min keep ratio (after crop)", 0.0, 1.0, 0.7, step=0.05)
    require_mesh = ui.checkbox("require mesh", value=True)
    debug_flag = ui.checkbox("Debug (data)", value=is_debug)
    device_opts = ["cpu", "cuda"]
    default_device_idx = 1 if torch.cuda.is_available() else 0
    device_choice = ui.selectbox(
        "Dataset device",
        device_opts,
        index=default_device_idx,
        help="Move snippet tensors to this device immediately after loading.",
    )

    return AseEfmDatasetConfig(
        atek_variant="efm",
        mesh_simplify_ratio=mesh_ratio if mesh_ratio > 0 else None,
        crop_mesh=crop_enable,
        mesh_crop_margin_m=mesh_crop_margin,
        mesh_crop_min_keep_ratio=mesh_keep_ratio,
        require_mesh=require_mesh,
        batch_size=None,
        verbosity=verbosity,
        is_debug=debug_flag,
        device=device_choice,
    )


def candidate_config_ui(
    default: CandidateViewGeneratorConfig,
    ui: st.delta_generator.DeltaGenerator,
    *,
    is_debug: bool = False,
    verbosity: Verbosity,
) -> CandidateViewGeneratorConfig:
    """Render finite-candidate controls and return a validated config copy.

    Distances are entered in metres, angles in degrees, and any target point is
    interpreted in the world frame as actor-visible conditioning.

    Args:
        default: Existing generator configuration used to seed every widget.
        ui: Streamlit container that owns the widgets.
        is_debug: Initial candidate-debug toggle.
        verbosity: Project logging level copied into the result.

    Returns:
        Validated candidate-generator configuration.
    """

    expander = ui.expander("Candidate Generator", expanded=False)
    schema_driven = expander.checkbox(
        "Schema-driven Pydantic controls",
        value=True,
        key="candidate_config_schema_driven",
        help="Use field metadata from CandidateViewGeneratorConfig: enums and Literals use select boxes, bounds are enforced, and the result is revalidated.",
    )
    if schema_driven:
        debug_flag = expander.checkbox("Debug (candidates)", value=is_debug, key="candidate_config_debug")
        updated = render_typed_config_fields(
            default,
            ui=expander,
            key_prefix="candidate_config",
            excluded_paths=frozenset({"is_debug", "verbosity"}),
            choices={"device": ("auto", "cpu", "cuda")},
            bounds=candidate_config_ui_bounds(),
        )
        return updated.model_copy(update={"is_debug": debug_flag, "verbosity": verbosity})

    num_samples_default = default.num_samples
    debug_flag = expander.checkbox("Debug (candidates)", value=is_debug)

    seed_enabled_default = default.seed is not None
    seed_enabled = expander.checkbox(
        "Deterministic seed",
        value=seed_enabled_default,
        help="When enabled, candidate sampling is reproducible across reruns. Disable for stochastic sampling.",
    )
    seed_value_default = int(default.seed) if default.seed is not None else 0
    seed_value = expander.number_input(
        "seed",
        min_value=0,
        value=int(seed_value_default),
        step=1,
        disabled=not seed_enabled,
        help="Seed used for candidate sampling and view-direction jitter.",
    )
    seed = int(seed_value) if seed_enabled else None

    device_mode = expander.selectbox(
        "Generator device",
        ["cpu", "cuda"],
        index=1 if torch.cuda.is_available() else 0,
        help="Device to run candidate sampling on.",
    )

    sampling_opts = list(SamplingStrategy)
    sampling_choice = expander.selectbox(
        "sampling_strategy",
        options=sampling_opts,
        index=sampling_opts.index(default.sampling_strategy),
        format_func=lambda s: s.name.lower(),
    )

    collision_opts = list(CollisionBackend)
    collision_choice = expander.selectbox(
        "collision_backend",
        options=collision_opts,
        index=collision_opts.index(default.collision_backend),
        format_func=lambda c: c.value,
        help="PyTorch3D for GPU, pyembree/trimesh for CPU.",
    )

    num_samples = expander.slider("num_samples", 2, 512, num_samples_default, step=2)
    oversample = expander.slider("oversample_factor", 1.0, 4.0, float(default.oversample_factor), step=0.25)
    min_radius = expander.slider("min_radius (m)", 0.1, 2.0, float(default.min_radius), step=0.05)
    max_radius = expander.slider("max_radius (m)", 0.2, 3.0, float(default.max_radius), step=0.05)
    min_elev = expander.slider("min_elev_deg", -90.0, 0.0, float(default.min_elev_deg), step=1.0)
    max_elev = expander.slider("max_elev_deg", 0.0, 90.0, float(default.max_elev_deg), step=1.0)
    delta_az = expander.slider(
        "delta_azimuth_deg",
        min_value=0.0,
        max_value=360.0,
        value=float(default.delta_azimuth_deg),
        step=5.0,
        help="Yaw span around the last forward direction; 360=full sphere, 90=±45°, 0=planar slice.",
    )
    kappa = expander.slider("orientation kappa (PowerSpherical)", 0.0, 16.0, float(default.kappa), step=0.5)
    align_to_gravity = expander.checkbox(
        "align_to_gravity",
        value=bool(default.align_to_gravity),
        help="Sample in a gravity-aligned reference frame (drops pitch/roll, keeps yaw) to avoid tilted shells.",
    )

    view_mode = expander.selectbox(
        "view_direction_mode",
        options=list(ViewDirectionMode),
        index=list(ViewDirectionMode).index(default.view_direction_mode),
        format_func=lambda m: m.value,
        help="Base orientation: rig-forward, radial away/towards, or target point.",
    )

    view_sampling_opts = [None] + list(SamplingStrategy)
    view_sampling_choice = expander.selectbox(
        "view_sampling_strategy",
        options=view_sampling_opts,
        index=view_sampling_opts.index(default.view_sampling_strategy),
        format_func=lambda s: "none" if s is None else s.value,
        help=(
            "Optional legacy view-direction sampler. If view_max_azimuth_deg/view_max_elevation_deg > 0, we use "
            "bounded box jitter regardless of this setting; if both caps are 0, this controls whether view "
            "directions are random (uniform sphere / PowerSpherical) or deterministic (none)."
        ),
    )

    view_kappa = expander.slider(
        "view_kappa (PowerSpherical)",
        0.0,
        16.0,
        float(default.view_kappa if default.view_kappa is not None else default.kappa),
        step=0.5,
    )

    view_max_azimuth_deg = expander.slider(
        "view_max_azimuth_deg",
        0.0,
        90.0,
        float(default.view_max_azimuth_deg)
        if default.view_max_azimuth_deg is not None
        else float(default.view_max_angle_deg),
        step=1.0,
    )
    view_max_elevation_deg = expander.slider(
        "view_max_elevation_deg",
        0.0,
        90.0,
        float(default.view_max_elevation_deg)
        if default.view_max_elevation_deg is not None
        else float(default.view_max_angle_deg),
        step=1.0,
    )
    view_roll = expander.slider(
        "view_roll_jitter_deg",
        0.0,
        90.0,
        float(default.view_roll_jitter_deg),
        step=1.0,
        help="Random roll around sampled forward; 0 disables roll jitter.",
    )

    ref_frame_default = default.reference_frame_index if default.reference_frame_index is not None else -1
    ref_frame_idx_input = expander.number_input(
        "reference_frame_index (camera frame; -1 = final)",
        value=int(ref_frame_default),
        step=1,
        format="%d",
        help="Optional camera frame index used as reference pose; -1 uses the final pose.",
    )
    reference_frame_index = int(ref_frame_idx_input)
    if reference_frame_index < 0:
        reference_frame_index = None

    target_point_world = default.view_target_point_world
    if view_mode is ViewDirectionMode.TARGET_POINT:
        tp_x = expander.number_input(
            "target_point_world.x", value=float(target_point_world[0]) if target_point_world is not None else 0.0
        )
        tp_y = expander.number_input(
            "target_point_world.y", value=float(target_point_world[1]) if target_point_world is not None else 0.0
        )
        tp_z = expander.number_input(
            "target_point_world.z", value=float(target_point_world[2]) if target_point_world is not None else 0.0
        )
        target_point_world = torch.tensor([tp_x, tp_y, tp_z], dtype=torch.float32)
    else:
        target_point_world = None

    ensure_collision_free = expander.checkbox("ensure_collision_free", value=default.ensure_collision_free)
    ensure_free_space = expander.checkbox("ensure_free_space", value=default.ensure_free_space)
    min_distance = expander.slider("min_distance_to_mesh (m)", 0.0, 2.0, float(default.min_distance_to_mesh), step=0.01)

    collect_rule_masks = expander.checkbox("collect_rule_masks", value=default.collect_rule_masks)
    collect_debug_stats = expander.checkbox("collect_debug_stats", value=default.collect_debug_stats)

    updated = default.model_copy(
        update={
            "seed": seed,
            "num_samples": int(num_samples),
            "oversample_factor": float(oversample),
            "align_to_gravity": bool(align_to_gravity),
            "min_radius": float(min_radius),
            "max_radius": float(max_radius),
            "min_elev_deg": float(min_elev),
            "max_elev_deg": float(max_elev),
            "delta_azimuth_deg": float(delta_az),
            "sampling_strategy": sampling_choice,
            "kappa": float(kappa),
            "view_direction_mode": view_mode,
            "view_sampling_strategy": view_sampling_choice,
            "view_kappa": float(view_kappa),
            "view_max_azimuth_deg": float(view_max_azimuth_deg),
            "view_max_elevation_deg": float(view_max_elevation_deg),
            "view_roll_jitter_deg": float(view_roll),
            "view_target_point_world": target_point_world,
            "min_distance_to_mesh": float(min_distance),
            "ensure_collision_free": ensure_collision_free,
            "collision_backend": collision_choice,
            "ensure_free_space": ensure_free_space,
            "device": device_mode,
            "is_debug": debug_flag,
            "verbosity": verbosity,
            "reference_frame_index": reference_frame_index,
            "collect_rule_masks": collect_rule_masks,
            "collect_debug_stats": collect_debug_stats,
        }
    )
    return CandidateViewGeneratorConfig.model_validate(updated.model_dump())


def renderer_config_ui(
    default: CandidateDepthRendererConfig,
    ui: st.delta_generator.DeltaGenerator,
    *,
    is_debug: bool = False,
    verbosity: Verbosity,
) -> CandidateDepthRendererConfig:
    """Render oracle depth controls and return an updated renderer config.

    Args:
        default: Existing renderer configuration used for defaults.
        ui: Streamlit container that owns the widgets.
        is_debug: Initial renderer-debug toggle.
        verbosity: Project logging level copied into the result.

    Returns:
        Renderer configuration for mesh-derived oracle/evaluation depths.
    """

    ui.subheader("Depth Renderer")

    max_candidates_default = default.max_candidates_final if default.max_candidates_final is not None else 4
    max_candidates = ui.slider("max_candidates", 1, 48, max_candidates_default)
    res_scale = ui.slider(
        "Render resolution scale (xH, xW)",
        0.1,
        4.0,
        1.0,
        step=0.05,
        help="Scales both height and width before rendering; >1 upsamples, <1 downsamples.",
    )
    renderer_device_options = ["cpu", "cuda"]
    default_device = str(getattr(default.renderer, "device", "cuda" if torch.cuda.is_available() else "cpu"))
    default_device_idx = renderer_device_options.index(default_device if default_device in ("cpu", "cuda") else "cuda")
    renderer_device_sel = ui.selectbox("renderer device", renderer_device_options, index=default_device_idx)
    debug_flag = ui.checkbox("Debug (renderer)", value=is_debug)
    renderer_cfg = Pytorch3DDepthRendererConfig(
        device=renderer_device_sel,
        is_debug=debug_flag,
        verbosity=verbosity,
    )
    return default.model_copy(
        update={
            "max_candidates_final": int(max_candidates),
            "renderer": renderer_cfg,
            "is_debug": debug_flag,
            "resolution_scale": float(res_scale),
            "verbosity": verbosity,
        }
    )


def oracle_config_ui(
    default: PreparedRriScorerConfig,
    ui: st.delta_generator.DeltaGenerator,
) -> PreparedRriScorerConfig:
    """Render the oracle-RRI section and return its unchanged configuration.

    The current panel exposes no mutable oracle settings; it preserves a typed
    extension point without leaking mesh-derived labels into actor controls.
    """

    ui.subheader("Oracle RRI")
    return default


__all__ = [
    "candidate_config_ui",
    "dataset_config_ui",
    "oracle_config_ui",
    "renderer_config_ui",
]
