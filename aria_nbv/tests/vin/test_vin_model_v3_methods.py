import sys
import types
from pathlib import Path

import pytest
import torch
from pytorch3d.renderer.cameras import PerspectiveCameras  # type: ignore[import-untyped]

# Make vendored efm3d importable.
sys.path.append(str(Path(__file__).resolve().parents[3] / "external" / "efm3d"))

# Stub optional deps so vin imports without external packages.
if "coral_pytorch" not in sys.modules:
    coral_pytorch = types.ModuleType("coral_pytorch")
    layers = types.ModuleType("coral_pytorch.layers")
    losses = types.ModuleType("coral_pytorch.losses")

    class DummyCoralLayer(torch.nn.Module):  # pragma: no cover - import shim only
        def __init__(self, size_in: int, num_classes: int, **kwargs) -> None:
            super().__init__()
            out_dim = max(int(num_classes) - 1, 1)
            self.proj = torch.nn.Linear(int(size_in), out_dim, bias=True)

        def forward(self, x):  # pragma: no cover - import shim only
            return self.proj(x)

    def dummy_coral_loss(*args, **kwargs):  # pragma: no cover - import shim only
        raise RuntimeError("coral_pytorch is not installed")

    layers.CoralLayer = DummyCoralLayer
    losses.coral_loss = dummy_coral_loss
    coral_pytorch.layers = layers
    coral_pytorch.losses = losses
    sys.modules["coral_pytorch"] = coral_pytorch
    sys.modules["coral_pytorch.layers"] = layers
    sys.modules["coral_pytorch.losses"] = losses

if "power_spherical" not in sys.modules:
    power_spherical = types.ModuleType("power_spherical")

    class DummyPowerSpherical:  # pragma: no cover - import shim only
        pass

    power_spherical.HypersphericalUniform = DummyPowerSpherical
    power_spherical.PowerSpherical = DummyPowerSpherical
    sys.modules["power_spherical"] = power_spherical

if "e3nn" not in sys.modules:
    e3nn = types.ModuleType("e3nn")
    o3 = types.ModuleType("e3nn.o3")
    e3nn.o3 = o3
    sys.modules["e3nn"] = e3nn
    sys.modules["e3nn.o3"] = o3

if "seaborn" not in sys.modules:
    seaborn = types.ModuleType("seaborn")

    def _noop(*_args, **_kwargs):  # pragma: no cover - import shim only
        return None

    seaborn.set_theme = _noop
    seaborn.color_palette = lambda *args, **kwargs: []  # pragma: no cover - import shim only
    sys.modules["seaborn"] = seaborn

from efm3d.aria.aria_constants import (
    ARIA_POINTS_DIST_STD,
    ARIA_POINTS_INV_DIST_STD,
    ARIA_POINTS_TIME_NS,
    ARIA_POINTS_VOL_MAX,
    ARIA_POINTS_VOL_MIN,
    ARIA_POINTS_WORLD,
)
from efm3d.aria.pose import PoseTW

from aria_nbv.data_handling import is_vin_snippet_view_instance
from aria_nbv.data_handling.efm_views import EfmSnippetView, VinSnippetView
from aria_nbv.data_handling.vin_oracle_types import VinOracleBatch
from aria_nbv.vin.encoders import TrajectoryEncoderConfig
from aria_nbv.vin.geometry import pool_voxel_points
from aria_nbv.vin.geometry.semidense_projection import (
    SEMIDENSE_PROJ_DIM,
    encode_projection_summary,
    project_points_to_candidate_cameras,
    sample_semidense_points,
)
from aria_nbv.vin.geometry.semidense_schema import semidense_proj_feature_index
from aria_nbv.vin.models.scene_myopic import VinModelV3, VinModelV3Config
from aria_nbv.vin.scorer_context import apply_vin_scorer_film, compute_global_context, encode_pose_features
from aria_nbv.vin.types import EvlBackboneOutput


def _encode_projection_summary_for_model(
    model: VinModelV3,
    proj_data: dict[str, torch.Tensor] | None,
    *,
    batch_size: int,
    num_candidates: int,
    device: torch.device,
    dtype: torch.dtype,
) -> torch.Tensor:
    return encode_projection_summary(
        proj_data,
        batch_size=batch_size,
        num_candidates=num_candidates,
        device=device,
        dtype=dtype,
        grid_size=int(model.config.semidense_proj_grid_size),
        obs_count_max=int(model.config.semidense_obs_count_max),
        inv_dist_std_min=float(model.config.semidense_inv_dist_std_min),
        inv_dist_std_p95=float(model.config.semidense_inv_dist_std_p95),
    )


def _identity_pose(batch: int) -> PoseTW:
    device = torch.device("cpu")
    dtype = torch.float32
    rot = torch.eye(3, device=device, dtype=dtype).repeat(batch, 1, 1)
    trans = torch.zeros((batch, 3), device=device, dtype=dtype)
    return PoseTW.from_Rt(rot, trans)


def _make_backbone_out(*, batch: int, grid: int) -> EvlBackboneOutput:
    device = torch.device("cpu")
    dtype = torch.float32
    occ_pr = torch.rand(batch, 1, grid, grid, grid, device=device, dtype=dtype)
    cent_pr = torch.rand_like(occ_pr)
    occ_input = torch.rand_like(occ_pr)
    free_input = torch.rand_like(occ_pr)
    counts = torch.randint(0, 10, (batch, grid, grid, grid), device=device, dtype=torch.int64)
    pts_world = torch.zeros(batch, grid, grid, grid, 3, device=device, dtype=dtype)
    voxel_extent = torch.tensor([-1.0, 1.0, -1.0, 1.0, -1.0, 1.0], device=device, dtype=dtype).repeat(batch, 1)
    t_world_voxel = _identity_pose(batch)

    return EvlBackboneOutput(
        occ_pr=occ_pr,
        occ_input=occ_input,
        free_input=free_input,
        counts=counts,
        cent_pr=cent_pr,
        pts_world=pts_world,
        t_world_voxel=t_world_voxel,
        voxel_extent=voxel_extent,
    )


def _make_model() -> VinModelV3:
    config = VinModelV3Config(
        field_dim=4,
        field_gn_groups=2,
        global_pool_grid_size=2,
        semidense_proj_grid_size=4,
        semidense_proj_max_points=16,
        head_hidden_dim=8,
        head_num_layers=1,
        head_dropout=0.0,
        num_classes=5,
        use_voxel_valid_frac_gate=False,
        backbone=None,
    )
    return VinModelV3(config)


def _make_model_with_traj() -> VinModelV3:
    config = VinModelV3Config(
        field_dim=4,
        field_gn_groups=2,
        global_pool_grid_size=2,
        semidense_proj_grid_size=4,
        semidense_proj_max_points=16,
        head_hidden_dim=8,
        head_num_layers=1,
        head_dropout=0.0,
        num_classes=5,
        use_voxel_valid_frac_gate=False,
        backbone=None,
        use_traj_encoder=True,
        traj_encoder=TrajectoryEncoderConfig(),
    )
    return VinModelV3(config)


def _make_vin_snippet(*, num_points: int = 10) -> VinSnippetView:
    device = torch.device("cpu")
    dtype = torch.float32
    xyz = torch.randn((num_points, 3), device=device, dtype=dtype)
    xyz[:, 2] = xyz[:, 2].abs() + 1.0
    inv_sigma = torch.rand((num_points, 1), device=device, dtype=dtype)
    n_obs = torch.randint(1, 5, (num_points, 1), device=device, dtype=torch.int64).to(dtype=dtype)
    points_world = torch.cat([xyz, inv_sigma, n_obs], dim=-1)
    lengths = torch.tensor([points_world.shape[0]], device=device, dtype=torch.int64)
    t_world_rig = _identity_pose(2)
    return VinSnippetView(points_world=points_world, lengths=lengths, t_world_rig=t_world_rig)


def _make_cameras(num_cams: int) -> PerspectiveCameras:
    device = torch.device("cpu")
    dtype = torch.float32
    rot = torch.eye(3, device=device, dtype=dtype).expand(num_cams, 3, 3).contiguous()
    trans = torch.zeros((num_cams, 3), device=device, dtype=dtype)
    return PerspectiveCameras(
        device=device,
        R=rot,
        T=trans,
        focal_length=torch.tensor([[40.0, 40.0]], device=device, dtype=dtype).expand(num_cams, -1),
        principal_point=torch.tensor([[32.0, 32.0]], device=device, dtype=dtype).expand(num_cams, -1),
        image_size=torch.tensor([[64.0, 64.0]], device=device, dtype=dtype).expand(num_cams, -1),
        in_ndc=False,
    )


def _make_indexed_cameras(*, num_cams: int, offset: float = 0.0) -> PerspectiveCameras:
    device = torch.device("cpu")
    dtype = torch.float32
    rot = torch.eye(3, device=device, dtype=dtype).expand(num_cams, 3, 3).contiguous()
    trans = torch.zeros((num_cams, 3), device=device, dtype=dtype)
    trans[:, 0] = torch.arange(num_cams, device=device, dtype=dtype) + float(offset)
    return PerspectiveCameras(
        device=device,
        R=rot,
        T=trans,
        focal_length=torch.tensor([[40.0, 40.0]], device=device, dtype=dtype).expand(num_cams, -1),
        principal_point=torch.tensor([[32.0, 32.0]], device=device, dtype=dtype).expand(num_cams, -1),
        image_size=torch.tensor([[64.0, 64.0]], device=device, dtype=dtype).expand(num_cams, -1),
        in_ndc=False,
    )


def _make_candidate_poses(*, num_candidates: int, offset: float = 0.0) -> PoseTW:
    device = torch.device("cpu")
    dtype = torch.float32
    rot = torch.eye(3, device=device, dtype=dtype).expand(num_candidates, 3, 3).contiguous()
    trans = torch.zeros((num_candidates, 3), device=device, dtype=dtype)
    trans[:, 0] = torch.linspace(0.0, 0.2, num_candidates, device=device, dtype=dtype) + float(offset)
    return PoseTW.from_Rt(rot, trans)


def test_pose_encoder_lff_property() -> None:
    model = _make_model()
    assert model.pose_encoder_lff is not None


def test_ensure_vin_snippet_from_vin() -> None:
    model = _make_model()
    snippet = _make_vin_snippet()
    ensured = model._ensure_vin_snippet(snippet, device=torch.device("cpu"))
    assert is_vin_snippet_view_instance(ensured)


def test_ensure_vin_snippet_from_efm() -> None:
    model = _make_model()
    efm = {
        "__key__": "AriaSyntheticEnvironment_000000_AtekDataSample_000000",
        ARIA_POINTS_WORLD: torch.randn((2, 4, 3)),
        ARIA_POINTS_DIST_STD: torch.ones((2, 4), dtype=torch.float32),
        ARIA_POINTS_INV_DIST_STD: torch.ones((2, 4), dtype=torch.float32),
        ARIA_POINTS_TIME_NS: torch.zeros((2, 4), dtype=torch.int64),
        ARIA_POINTS_VOL_MIN: torch.tensor([-1.0, -1.0, -1.0], dtype=torch.float32),
        ARIA_POINTS_VOL_MAX: torch.tensor([1.0, 1.0, 1.0], dtype=torch.float32),
    }
    snippet = EfmSnippetView.from_cache_efm(efm)
    ensured = model._ensure_vin_snippet(snippet, device=torch.device("cpu"))
    assert is_vin_snippet_view_instance(ensured)
    assert ensured.points_world.shape[-1] == 5


def test_encode_pose_features_shapes() -> None:
    model = _make_model()
    reference_pose = _identity_pose(1)
    candidates = _make_candidate_poses(num_candidates=3)
    features = encode_pose_features(
        pose_encoder=model.pose_encoder,
        pose_world_cam=candidates.unsqueeze(0),
        pose_world_rig_ref=reference_pose,
    )
    assert features.pose_enc.shape[:2] == (1, 3)
    assert features.pose_vec.shape[:2] == (1, 3)
    assert features.candidate_center_rig_m.shape == (1, 3, 3)


def test_build_field_bundle_requires_fields() -> None:
    model = _make_model()
    backbone_out = _make_backbone_out(batch=1, grid=2)
    bundle = model._build_field_bundle(backbone_out)
    assert bundle.field.ndim == 5
    assert "counts_norm" in bundle.aux

    missing = EvlBackboneOutput(
        occ_pr=None,
        occ_input=backbone_out.occ_input,
        free_input=backbone_out.free_input,
        counts=backbone_out.counts,
        cent_pr=backbone_out.cent_pr,
        pts_world=backbone_out.pts_world,
        t_world_voxel=backbone_out.t_world_voxel,
        voxel_extent=backbone_out.voxel_extent,
    )
    with pytest.raises(RuntimeError):
        model._build_field_bundle(missing)


def test_compute_global_context_shapes() -> None:
    model = _make_model()
    backbone_out = _make_backbone_out(batch=1, grid=2)
    bundle = model._build_field_bundle(backbone_out)
    candidates = _make_candidate_poses(num_candidates=2).unsqueeze(0)
    reference_pose = _identity_pose(1)
    pose_feats = encode_pose_features(
        pose_encoder=model.pose_encoder,
        pose_world_cam=candidates,
        pose_world_rig_ref=reference_pose,
    )
    ctx = compute_global_context(
        global_pooler=model.global_pooler,
        field=bundle.field,
        pose_enc=pose_feats.pose_enc,
        pts_world=backbone_out.pts_world,
        t_world_voxel=backbone_out.t_world_voxel,
        pose_world_rig_ref=reference_pose,
        voxel_extent=backbone_out.voxel_extent,
    )
    assert ctx.pos_grid.shape[1] == 3
    assert ctx.global_feat.shape[:2] == (1, 2)


def test_pool_voxel_points_handles_flat_and_grid() -> None:
    grid = 3
    pts_world = torch.zeros((1, grid, grid, grid, 3), dtype=torch.float32)
    tokens_grid = pool_voxel_points(pts_world, grid_shape=(grid, grid, grid), pool_grid=2)
    assert tokens_grid.shape == (1, 8, 3)

    flat = pts_world.reshape(1, -1, 3)
    tokens_flat = pool_voxel_points(flat, grid_shape=(grid, grid, grid), pool_grid=2)
    assert tokens_flat.shape == (1, 8, 3)


def test_apply_film_modulates() -> None:
    global_feat = torch.ones((1, 1, 4), dtype=torch.float32)
    proj_feat = torch.zeros((1, 1, SEMIDENSE_PROJ_DIM), dtype=torch.float32)
    film = torch.nn.Linear(SEMIDENSE_PROJ_DIM, 8, bias=True)
    with torch.no_grad():
        film.weight.zero_()
        film.bias.copy_(torch.tensor([0.1, 0.1, 0.1, 0.1, 0.5, 0.5, 0.5, 0.5]))
    out = apply_vin_scorer_film(global_feat, proj_feat, film=film, norm=None)
    assert out.shape == global_feat.shape
    assert not torch.allclose(out, global_feat)


def test_sample_semidense_points_vin_view() -> None:
    model = _make_model()
    snippet = _make_vin_snippet(num_points=8)
    points = sample_semidense_points(
        snippet,
        device=torch.device("cpu"),
        max_points=int(model.config.semidense_proj_max_points),
    )
    assert points is not None
    assert points.shape[-1] == 5
    assert points.dtype == torch.float32


def test_sample_semidense_points_accepts_optional_obs_count() -> None:
    model = _make_model()
    snippet = _make_vin_snippet(num_points=8)
    four_channel_points = snippet.points_world[:, :4]
    four_channel_snippet = VinSnippetView(
        points_world=four_channel_points,
        lengths=snippet.lengths,
        t_world_rig=snippet.t_world_rig,
    )
    sampled = sample_semidense_points(
        four_channel_snippet,
        device=torch.device("cpu"),
        max_points=int(model.config.semidense_proj_max_points),
    )
    assert sampled is not None
    assert sampled.shape == four_channel_points.shape
    assert sampled.dtype == torch.float32
    assert torch.isfinite(sampled).all()


def test_sample_semidense_points_vin_batch() -> None:
    model = _make_model()
    snippet = _make_vin_snippet(num_points=16)
    points = snippet.points_world.unsqueeze(0).expand(2, -1, -1)
    lengths = torch.tensor([16, 16], dtype=torch.int64)
    batch_snippet = VinSnippetView(points_world=points, lengths=lengths, t_world_rig=snippet.t_world_rig)
    sampled = sample_semidense_points(
        batch_snippet,
        device=torch.device("cpu"),
        max_points=int(model.config.semidense_proj_max_points),
    )
    assert sampled is not None
    assert sampled.shape[0] == 2
    assert sampled.shape[-1] == 5


def test_sample_semidense_points_invalid_channels() -> None:
    model = _make_model()
    snippet = _make_vin_snippet(num_points=4)
    bad_points = snippet.points_world[:, :3]
    bad_snippet = VinSnippetView(points_world=bad_points, lengths=snippet.lengths, t_world_rig=snippet.t_world_rig)
    with pytest.raises(ValueError, match="at least 4 channels"):
        sample_semidense_points(
            bad_snippet,
            device=torch.device("cpu"),
            max_points=int(model.config.semidense_proj_max_points),
        )


def test_encode_traj_features_vin_snippet() -> None:
    model = _make_model_with_traj()
    snippet = _make_vin_snippet()
    traj_feat, traj_pose_vec, traj_pose_enc = model._encode_traj_features(
        snippet,
        pose_world_rig_ref=_identity_pose(1),
        batch_size=1,
        device=torch.device("cpu"),
        dtype=torch.float32,
    )
    assert traj_feat is not None
    assert traj_feat.shape[0] == 1
    assert traj_pose_vec is not None
    assert traj_pose_vec.shape[0] == 1
    assert traj_pose_enc is not None
    assert traj_pose_enc.shape[0] == 1


def test_project_semidense_points_shapes() -> None:
    snippet = _make_vin_snippet(num_points=5)
    cameras = _make_cameras(2)
    proj = project_points_to_candidate_cameras(
        snippet.points_world,
        cameras,
        batch_size=1,
        num_candidates=2,
        device=torch.device("cpu"),
    )
    assert proj is not None
    assert proj["x"].shape[0] == 2
    assert proj["valid"].shape == proj["x"].shape


def test_project_semidense_points_errors() -> None:
    snippet = _make_vin_snippet(num_points=5)
    cameras = PerspectiveCameras(device=torch.device("cpu"))
    with pytest.raises(RuntimeError):
        project_points_to_candidate_cameras(
            snippet.points_world,
            cameras,
            batch_size=1,
            num_candidates=1,
            device=torch.device("cpu"),
        )

    cameras = _make_cameras(1)
    with pytest.raises(ValueError):
        project_points_to_candidate_cameras(
            snippet.points_world,
            cameras,
            batch_size=1,
            num_candidates=2,
            device=torch.device("cpu"),
        )


def test_encode_semidense_projection_features() -> None:
    model = _make_model()
    snippet = _make_vin_snippet(num_points=4)
    cameras = _make_cameras(1)
    proj = project_points_to_candidate_cameras(
        snippet.points_world,
        cameras,
        batch_size=1,
        num_candidates=1,
        device=torch.device("cpu"),
    )
    feats = _encode_projection_summary_for_model(
        model,
        proj,
        batch_size=1,
        num_candidates=1,
        device=torch.device("cpu"),
        dtype=torch.float32,
    )
    assert feats.shape == (1, 1, SEMIDENSE_PROJ_DIM)
    assert torch.isfinite(feats).all()

    with pytest.raises(RuntimeError):
        _encode_projection_summary_for_model(
            model,
            None,
            batch_size=1,
            num_candidates=1,
            device=torch.device("cpu"),
            dtype=torch.float32,
        )


def test_encode_semidense_grid_features() -> None:
    model = _make_model()
    snippet = _make_vin_snippet(num_points=6)
    cameras = _make_cameras(1)
    proj = project_points_to_candidate_cameras(
        snippet.points_world,
        cameras,
        batch_size=1,
        num_candidates=1,
        device=torch.device("cpu"),
    )
    feats = model._encode_semidense_grid_features(
        proj,
        batch_size=1,
        num_candidates=1,
        device=torch.device("cpu"),
        dtype=torch.float32,
    )
    assert feats.shape == (1, 1, model.config.semidense_cnn_out_dim)
    assert torch.isfinite(feats).all()


def test_semidense_proj_feature_index_uses_canonical_names_only() -> None:
    assert semidense_proj_feature_index("semidense_candidate_vis_frac") >= 0
    with pytest.raises(ValueError):
        semidense_proj_feature_index("valid_frac")
    with pytest.raises(ValueError):
        semidense_proj_feature_index("semidense_valid_frac")
    with pytest.raises(ValueError):
        semidense_proj_feature_index("unknown_feature")


def test_forward_impl_requires_cw90_tag() -> None:
    model = _make_model()
    model.config.apply_cw90_correction = True
    snippet = _make_vin_snippet()
    backbone_out = _make_backbone_out(batch=1, grid=2)
    candidates = _make_candidate_poses(num_candidates=2)
    reference_pose = _identity_pose(1)
    cameras = _make_cameras(2)

    with pytest.raises(RuntimeError):
        model._forward_impl(
            snippet,
            candidate_poses_world_cam=candidates,
            reference_pose_world_rig=reference_pose,
            p3d_cameras=cameras,
            return_debug=False,
            backbone_out=backbone_out,
        )


def test_forward_and_debug_paths() -> None:
    model = _make_model()
    snippet = _make_vin_snippet()
    backbone_out = _make_backbone_out(batch=1, grid=2)
    candidates = _make_candidate_poses(num_candidates=2)
    reference_pose = _identity_pose(1)
    cameras = _make_cameras(2)

    pred = model.forward(
        snippet,
        candidate_poses_world_cam=candidates,
        reference_pose_world_rig=reference_pose,
        p3d_cameras=cameras,
        backbone_out=backbone_out,
    )
    assert pred.logits.shape[:2] == (1, 2)

    pred_debug, debug = model.forward_with_debug(
        snippet,
        candidate_poses_world_cam=candidates,
        reference_pose_world_rig=reference_pose,
        p3d_cameras=cameras,
        backbone_out=backbone_out,
    )
    assert debug is not None
    assert debug.semidense_proj is not None
    assert pred_debug.logits.shape == pred.logits.shape


def test_forward_with_traj_context() -> None:
    model = _make_model_with_traj()
    snippet = _make_vin_snippet()
    backbone_out = _make_backbone_out(batch=1, grid=2)
    candidates = _make_candidate_poses(num_candidates=2)
    reference_pose = _identity_pose(1)
    cameras = _make_cameras(2)

    pred_debug, debug = model.forward_with_debug(
        snippet,
        candidate_poses_world_cam=candidates,
        reference_pose_world_rig=reference_pose,
        p3d_cameras=cameras,
        backbone_out=backbone_out,
    )
    assert pred_debug.logits.shape[:2] == (1, 2)
    assert debug.traj_ctx is not None
    assert debug.traj_feat is not None


def test_init_bin_values_and_summary() -> None:
    model = _make_model()
    values = torch.tensor([0.0, 0.5, 1.0, 1.5, 2.0], dtype=torch.float32)
    model.init_bin_values(values, overwrite=True)
    assert model.head_coral.has_bin_values

    snippet = _make_vin_snippet(num_points=6)
    backbone_out = _make_backbone_out(batch=1, grid=2)
    candidates = _make_candidate_poses(num_candidates=2)
    reference_pose = _identity_pose(1)
    cameras = _make_cameras(2)
    batch = VinOracleBatch(
        efm_snippet_view=snippet,
        candidate_poses_world_cam=candidates,
        reference_pose_world_rig=reference_pose,
        rri=torch.zeros(2, dtype=torch.float32),
        pm_dist_before=torch.zeros(2, dtype=torch.float32),
        pm_dist_after=torch.zeros(2, dtype=torch.float32),
        pm_acc_before=torch.zeros(2, dtype=torch.float32),
        pm_comp_before=torch.zeros(2, dtype=torch.float32),
        pm_acc_after=torch.zeros(2, dtype=torch.float32),
        pm_comp_after=torch.zeros(2, dtype=torch.float32),
        p3d_cameras=cameras,
        scene_id="scene",
        snippet_id="snippet",
        backbone_out=backbone_out,
    )
    summary = model.summarize_vin(batch, include_torchsummary=False)
    assert "VIN v3 summary" in summary


def test_efm_snippet_semidense_path() -> None:
    model = _make_model()
    device = torch.device("cpu")
    points_world = torch.randn((2, 4, 3), device=device, dtype=torch.float32)
    points_world[..., 2] = points_world[..., 2].abs() + 1.0
    efm = {
        "__key__": "AriaSyntheticEnvironment_000000_AtekDataSample_000000",
        ARIA_POINTS_WORLD: points_world,
        ARIA_POINTS_DIST_STD: torch.ones((2, 4), device=device, dtype=torch.float32),
        ARIA_POINTS_INV_DIST_STD: torch.ones((2, 4), device=device, dtype=torch.float32),
        ARIA_POINTS_TIME_NS: torch.zeros((2, 4), device=device, dtype=torch.int64),
        ARIA_POINTS_VOL_MIN: torch.tensor([-1.0, -1.0, -1.0], device=device, dtype=torch.float32),
        ARIA_POINTS_VOL_MAX: torch.tensor([1.0, 1.0, 1.0], device=device, dtype=torch.float32),
    }
    snippet = EfmSnippetView.from_cache_efm(efm)
    vin_snippet = model._ensure_vin_snippet(snippet, device=device)
    sampled = sample_semidense_points(
        vin_snippet,
        device=device,
        max_points=int(model.config.semidense_proj_max_points),
    )
    assert sampled is not None
    assert sampled.shape[-1] == 5


def test_ensure_vin_snippet_rejects_non_dict() -> None:
    model = _make_model()
    with pytest.raises(TypeError):
        model._ensure_vin_snippet("bad", device=torch.device("cpu"))  # type: ignore[arg-type]


def test_vin_oracle_batch_shuffle_candidates_unbatched() -> None:
    num = 4
    candidates = _make_candidate_poses(num_candidates=num)
    reference_pose = _identity_pose(1)
    rri = torch.arange(num, dtype=torch.float32)
    pm_dist_before = rri + 10.0
    pm_dist_after = rri + 20.0
    pm_acc_before = rri + 30.0
    pm_comp_before = rri + 40.0
    pm_acc_after = rri + 50.0
    pm_comp_after = rri + 60.0
    cameras = _make_indexed_cameras(num_cams=num)

    batch = VinOracleBatch(
        efm_snippet_view=None,
        candidate_poses_world_cam=candidates,
        reference_pose_world_rig=reference_pose,
        rri=rri,
        pm_dist_before=pm_dist_before,
        pm_dist_after=pm_dist_after,
        pm_acc_before=pm_acc_before,
        pm_comp_before=pm_comp_before,
        pm_acc_after=pm_acc_after,
        pm_comp_after=pm_comp_after,
        p3d_cameras=cameras,
        scene_id="scene",
        snippet_id="snippet",
        backbone_out=None,
    )

    perm_gen = torch.Generator().manual_seed(42)
    expected_perm = torch.randperm(num, generator=perm_gen)
    shuffled = batch.shuffle_candidates(generator=torch.Generator().manual_seed(42))

    assert torch.equal(shuffled.rri, rri[expected_perm])
    assert torch.equal(shuffled.pm_dist_before, pm_dist_before[expected_perm])
    assert torch.equal(shuffled.pm_dist_after, pm_dist_after[expected_perm])
    assert torch.equal(shuffled.pm_acc_before, pm_acc_before[expected_perm])
    assert torch.equal(shuffled.pm_comp_before, pm_comp_before[expected_perm])
    assert torch.equal(shuffled.pm_acc_after, pm_acc_after[expected_perm])
    assert torch.equal(shuffled.pm_comp_after, pm_comp_after[expected_perm])
    assert torch.equal(
        shuffled.candidate_poses_world_cam.tensor(),
        candidates.tensor()[expected_perm],
    )
    assert torch.equal(shuffled.p3d_cameras.T, cameras.T[expected_perm])
    assert torch.equal(shuffled.reference_pose_world_rig.tensor(), reference_pose.tensor())


def test_vin_oracle_batch_shuffle_candidates_batched() -> None:
    num = 3
    batch_a = VinOracleBatch(
        efm_snippet_view=None,
        candidate_poses_world_cam=_make_candidate_poses(num_candidates=num, offset=0.0),
        reference_pose_world_rig=_identity_pose(1),
        rri=torch.arange(num, dtype=torch.float32) + 100.0,
        pm_dist_before=torch.arange(num, dtype=torch.float32) + 110.0,
        pm_dist_after=torch.arange(num, dtype=torch.float32) + 120.0,
        pm_acc_before=torch.arange(num, dtype=torch.float32) + 130.0,
        pm_comp_before=torch.arange(num, dtype=torch.float32) + 140.0,
        pm_acc_after=torch.arange(num, dtype=torch.float32) + 150.0,
        pm_comp_after=torch.arange(num, dtype=torch.float32) + 160.0,
        p3d_cameras=_make_indexed_cameras(num_cams=num, offset=0.0),
        scene_id="scene_a",
        snippet_id="snippet_a",
        backbone_out=None,
    )
    batch_b = VinOracleBatch(
        efm_snippet_view=None,
        candidate_poses_world_cam=_make_candidate_poses(num_candidates=num, offset=10.0),
        reference_pose_world_rig=_identity_pose(1),
        rri=torch.arange(num, dtype=torch.float32) + 200.0,
        pm_dist_before=torch.arange(num, dtype=torch.float32) + 210.0,
        pm_dist_after=torch.arange(num, dtype=torch.float32) + 220.0,
        pm_acc_before=torch.arange(num, dtype=torch.float32) + 230.0,
        pm_comp_before=torch.arange(num, dtype=torch.float32) + 240.0,
        pm_acc_after=torch.arange(num, dtype=torch.float32) + 250.0,
        pm_comp_after=torch.arange(num, dtype=torch.float32) + 260.0,
        p3d_cameras=_make_indexed_cameras(num_cams=num, offset=10.0),
        scene_id="scene_b",
        snippet_id="snippet_b",
        backbone_out=None,
    )
    batch = VinOracleBatch.collate([batch_a, batch_b])

    perm_gen = torch.Generator().manual_seed(7)
    expected_perm = torch.stack([torch.randperm(num, generator=perm_gen) for _ in range(2)])
    shuffled = batch.shuffle_candidates(generator=torch.Generator().manual_seed(7))

    for field_name in (
        "rri",
        "pm_dist_before",
        "pm_dist_after",
        "pm_acc_before",
        "pm_comp_before",
        "pm_acc_after",
        "pm_comp_after",
    ):
        values = getattr(batch, field_name)
        expected_values = torch.gather(values, dim=1, index=expected_perm)
        assert torch.equal(getattr(shuffled, field_name), expected_values)

    poses = batch.candidate_poses_world_cam.tensor()
    pose_index = expected_perm.view(2, num, 1).expand_as(poses)
    expected_poses = torch.gather(poses, dim=1, index=pose_index)
    assert torch.equal(shuffled.candidate_poses_world_cam.tensor(), expected_poses)

    for field_name in ("R", "T", "focal_length", "principal_point", "image_size"):
        values = getattr(batch.p3d_cameras, field_name).reshape(
            2, num, *getattr(batch.p3d_cameras, field_name).shape[1:]
        )
        index = expected_perm.view(2, num, *([1] * (values.ndim - 2))).expand_as(values)
        expected_values = torch.gather(values, dim=1, index=index).reshape_as(
            getattr(shuffled.p3d_cameras, field_name),
        )
        assert torch.equal(getattr(shuffled.p3d_cameras, field_name), expected_values)
