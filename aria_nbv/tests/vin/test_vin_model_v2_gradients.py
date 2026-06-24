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

from efm3d.aria.pose import PoseTW

from aria_nbv.data_handling import VinOracleBatch
from aria_nbv.vin.backbones import EvlBackboneConfig
from aria_nbv.vin.diagnostics import summarize_vin_v2
from aria_nbv.vin.models import SEMIDENSE_PROJ_DIM, VinModelV2, VinModelV2Config
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


def test_vin_model_v2_gradients(monkeypatch) -> None:
    config = VinModelV2Config()
    monkeypatch.setattr(EvlBackboneConfig, "setup_target", lambda self: DummyBackbone())
    model = VinModelV2(config)

    batch = 1
    num_candidates = 3
    grid = 2
    backbone_out = _make_backbone_out(batch=batch, grid=grid)
    reference_pose, candidate_poses = _make_poses(batch=batch, num_candidates=num_candidates)

    cameras = PerspectiveCameras(device=torch.device("cpu"))
    pred = model.forward(
        efm={},
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


def test_semidense_projection_features_shape() -> None:
    model = VinModelV2(VinModelV2Config(point_encoder=None, traj_encoder=None))
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
    proj_data = model._project_semidense_points(
        points_world,
        cameras,
        batch_size=1,
        num_candidates=1,
        device=device,
    )
    proj_feat = model._encode_semidense_projection_features(
        proj_data,
        batch_size=1,
        num_candidates=1,
        device=device,
        dtype=torch.float32,
    )
    assert proj_feat.shape == (1, 1, SEMIDENSE_PROJ_DIM)
    assert (proj_feat[..., 0] >= 0.0).all()


def test_vin_model_v2_cached_batch_summary() -> None:
    model = VinModelV2(VinModelV2Config(point_encoder=None, traj_encoder=None))
    device = torch.device("cpu")
    num_candidates = 2
    backbone_out = _make_backbone_out(batch=1, grid=2)
    reference_pose, candidate_poses = _make_poses(batch=1, num_candidates=num_candidates)
    cameras = PerspectiveCameras(
        device=device,
        R=torch.eye(3, device=device).unsqueeze(0).repeat(num_candidates, 1, 1),
        T=torch.zeros((num_candidates, 3), device=device),
        focal_length=torch.tensor([[50.0, 50.0]], device=device).repeat(num_candidates, 1),
        principal_point=torch.tensor([[50.0, 50.0]], device=device).repeat(num_candidates, 1),
        image_size=torch.tensor([[100.0, 100.0]], device=device).repeat(num_candidates, 1),
        in_ndc=False,
    )
    zeros = torch.zeros(num_candidates, dtype=torch.float32, device=device)
    batch = VinOracleBatch(
        efm_snippet_view=None,
        candidate_poses_world_cam=candidate_poses,
        reference_pose_world_rig=reference_pose,
        rri=zeros,
        pm_dist_before=zeros,
        pm_dist_after=zeros,
        pm_acc_before=zeros,
        pm_comp_before=zeros,
        pm_acc_after=zeros,
        pm_comp_after=zeros,
        scene_id="scene",
        snippet_id="snippet",
        p3d_cameras=cameras,
        candidate_count=torch.tensor(num_candidates),
        backbone_out=backbone_out,
    )

    summary = model.summarize_vin(batch, include_torchsummary=False)
    direct_summary = summarize_vin_v2(model, batch, include_torchsummary=False)

    for text in (summary, direct_summary):
        assert "VIN v2 summary" in text
        assert "cached batch" in text
        assert "Trainable VIN params" in text
