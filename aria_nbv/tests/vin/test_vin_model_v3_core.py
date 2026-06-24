import sys
import types
from pathlib import Path

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

from efm3d.aria.pose import PoseTW

from aria_nbv.data_handling.efm_views import VinSnippetView
from aria_nbv.vin.backbones import EvlBackboneConfig
from aria_nbv.vin.geometry.semidense_projection import (
    SEMIDENSE_PROJ_DIM,
    encode_projection_summary,
    project_points_to_candidate_cameras,
)
from aria_nbv.vin.models.v3 import VinModelV3, VinModelV3Config
from aria_nbv.vin.types import EvlBackboneOutput


class DummyBackbone:
    def __init__(self) -> None:
        self.device = torch.device("cpu")

    def forward(self, efm):  # pragma: no cover - not used in tests
        raise RuntimeError("Dummy backbone should not be called")


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
    t_world_voxel = PoseTW.from_Rt(torch.eye(3, device=device, dtype=dtype).repeat(batch, 1, 1), torch.zeros(batch, 3))

    return EvlBackboneOutput(
        occ_feat=None,
        obb_feat=None,
        occ_pr=occ_pr,
        occ_input=occ_input,
        free_input=free_input,
        counts=counts,
        counts_m=None,
        cent_pr=cent_pr,
        pts_world=pts_world,
        t_world_voxel=t_world_voxel,
        voxel_extent=voxel_extent,
    )


def _make_poses(*, batch: int, num_candidates: int) -> tuple[PoseTW, PoseTW]:
    device = torch.device("cpu")
    dtype = torch.float32
    rot = torch.eye(3, device=device, dtype=dtype)
    t_ref = torch.zeros(3, device=device, dtype=dtype)
    reference = PoseTW.from_Rt(rot, t_ref)
    ts = torch.linspace(0.0, 0.2, num_candidates, device=device, dtype=dtype)
    t_cand = torch.stack([ts, torch.zeros_like(ts), torch.zeros_like(ts)], dim=-1)
    rot_cand = rot.expand(num_candidates, 3, 3)
    candidates = PoseTW.from_Rt(rot_cand, t_cand)
    return reference, candidates


def _make_vin_snippet(num_points: int = 8) -> VinSnippetView:
    device = torch.device("cpu")
    dtype = torch.float32
    xyz = torch.randn((num_points, 3), device=device, dtype=dtype)
    xyz[:, 2] = xyz[:, 2].abs() + 1.0
    inv_sigma = torch.rand((num_points, 1), device=device, dtype=dtype)
    n_obs = torch.randint(1, 5, (num_points, 1), device=device, dtype=torch.int64).to(dtype=dtype)
    points_world = torch.cat([xyz, inv_sigma, n_obs], dim=-1)
    lengths = torch.tensor([points_world.shape[0]], device=device, dtype=torch.int64)
    t_world_rig = PoseTW.from_Rt(torch.eye(3, device=device, dtype=dtype).unsqueeze(0), torch.zeros((1, 3)))
    return VinSnippetView(points_world=points_world, lengths=lengths, t_world_rig=t_world_rig)


def test_vin_model_v3_gradients(monkeypatch) -> None:
    config = VinModelV3Config()
    monkeypatch.setattr(EvlBackboneConfig, "setup_target", lambda self: DummyBackbone())
    model = VinModelV3(config)

    batch = 1
    num_candidates = 3
    grid = 2
    backbone_out = _make_backbone_out(batch=batch, grid=grid)
    reference_pose, candidate_poses = _make_poses(batch=batch, num_candidates=num_candidates)
    snippet = _make_vin_snippet()

    poses_cw = candidate_poses.inverse()
    rotations = poses_cw.R.transpose(-1, -2).contiguous()
    translations = poses_cw.t
    cameras = PerspectiveCameras(
        device=torch.device("cpu"),
        R=rotations,
        T=translations,
        focal_length=torch.tensor([[40.0, 40.0]], dtype=torch.float32).expand(num_candidates, -1),
        principal_point=torch.tensor([[32.0, 32.0]], dtype=torch.float32).expand(num_candidates, -1),
        image_size=torch.tensor([[64.0, 64.0]], dtype=torch.float32).expand(num_candidates, -1),
        in_ndc=False,
    )
    pred = model.forward(
        efm=snippet,
        candidate_poses_world_cam=candidate_poses,
        reference_pose_world_rig=reference_pose,
        p3d_cameras=cameras,
        backbone_out=backbone_out,
    )

    loss = pred.logits.sum() + pred.expected_normalized.sum()
    loss.backward()

    pose_encoder_params = list(model.pose_encoder.parameters())
    assert pose_encoder_params, "Pose encoder has no parameters."

    grad_params = {
        "pose_encoder": pose_encoder_params[0],
        "field_proj": next(model.field_proj.parameters()),
        "global_pooler": next(model.global_pooler.parameters()),
        "head_mlp": next(model.head_mlp.parameters()),
        "head_coral": next(model.head_coral.parameters()),
    }
    pose_scale_log = getattr(model.pose_encoder, "pose_scale_log", None)
    if pose_scale_log is not None:
        grad_params["pose_scale_log"] = pose_scale_log

    for name, param in grad_params.items():
        assert param.grad is not None, f"Missing grad for {name}"
        assert torch.isfinite(param.grad).all(), f"Non-finite grad for {name}"


def test_v3_shared_head_preserves_checkpoint_keys() -> None:
    """V3 should keep the public head_mlp/head_coral state-dict surface."""
    model = VinModelV3(VinModelV3Config())
    keys = set(model.state_dict())

    assert any(key.startswith("head_mlp.") for key in keys)
    assert any(key.startswith("head_coral.") for key in keys)
    assert any(key.startswith("voxel_proj_film.") for key in keys)
    assert any(key.startswith("voxel_proj_film_norm.") for key in keys)
    assert not any(key.startswith("scorer_head.") for key in keys)
    assert not any(key.startswith("film.") for key in keys)


def test_semidense_projection_features_shape_v3() -> None:
    model = VinModelV3(VinModelV3Config())
    device = torch.device("cpu")
    points_world = torch.tensor(
        [
            [-0.5, -0.5, 2.0],
            [0.5, -0.5, 2.0],
            [-0.5, 0.5, 2.0],
            [0.5, 0.5, 2.0],
        ],
        device=device,
        dtype=torch.float32,
    )
    cameras = PerspectiveCameras(
        device=device,
        R=torch.eye(3, device=device).unsqueeze(0),
        T=torch.zeros((1, 3), device=device),
        focal_length=torch.tensor([[50.0, 50.0]], device=device),
        principal_point=torch.tensor([[50.0, 50.0]], device=device),
        image_size=torch.tensor([[100.0, 100.0]], device=device),
        in_ndc=False,
    )
    proj_data = project_points_to_candidate_cameras(
        points_world,
        cameras,
        batch_size=1,
        num_candidates=1,
        device=device,
    )
    proj_feat = encode_projection_summary(
        proj_data,
        batch_size=1,
        num_candidates=1,
        device=device,
        dtype=torch.float32,
        grid_size=int(model.config.semidense_proj_grid_size),
        obs_count_max=int(model.config.semidense_obs_count_max),
        inv_dist_std_min=float(model.config.semidense_inv_dist_std_min),
        inv_dist_std_p95=float(model.config.semidense_inv_dist_std_p95),
    )
    assert proj_feat.shape == (1, 1, SEMIDENSE_PROJ_DIM)
    assert (proj_feat[..., 0] >= 0.0).all()
