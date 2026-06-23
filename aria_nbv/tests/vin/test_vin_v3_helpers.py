"""Unit tests for VIN v3 helpers (voxel sampling + position grids)."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import torch

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

from aria_nbv.vin.geometry import pos_grid_from_pts_world, sample_voxel_field
from aria_nbv.vin.model_v3 import VinModelV3, VinModelV3Config
from aria_nbv.vin.types import EvlBackboneOutput


def _identity_pose(batch: int) -> PoseTW:
    rot = torch.eye(3, dtype=torch.float32).view(1, 3, 3).expand(batch, 3, 3)
    trans = torch.zeros((batch, 3), dtype=torch.float32)
    return PoseTW.from_Rt(rot, trans)


def _make_backbone_out(*, batch: int, grid: int) -> EvlBackboneOutput:
    device = torch.device("cpu")
    dtype = torch.float32
    occ_pr = torch.rand(batch, 1, grid, grid, grid, device=device, dtype=dtype)
    cent_pr = torch.rand_like(occ_pr)
    occ_input = torch.rand_like(occ_pr)
    free_input = torch.rand_like(occ_pr)
    counts = torch.zeros((batch, grid, grid, grid), device=device, dtype=torch.int64)
    pts_world = torch.zeros(batch, grid, grid, grid, 3, device=device, dtype=dtype)
    voxel_extent = torch.tensor([-2.0, 2.0, 0.0, 4.0, -2.0, 2.0], device=device, dtype=dtype).repeat(batch, 1)
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


def test_build_field_bundle_shapes_and_prior() -> None:
    model = VinModelV3(VinModelV3Config(field_dim=8, field_gn_groups=2))
    out = _make_backbone_out(batch=2, grid=4)
    bundle = model._build_field_bundle(out)
    assert bundle.field.shape[:2] == (2, model.config.field_dim)

    # counts are zero -> unknown=1 everywhere -> new_surface_prior == occ_pr
    occ_pr = out.occ_pr.squeeze(1)
    new_surface = bundle.aux["new_surface_prior"].squeeze(1)
    assert torch.allclose(new_surface, occ_pr, atol=1e-6)


def test_pos_grid_from_pts_world_shape() -> None:
    batch, grid = 1, 4
    pts_world = torch.zeros(batch, grid, grid, grid, 3, dtype=torch.float32)
    pos_grid = pos_grid_from_pts_world(
        pts_world,
        t_world_voxel=_identity_pose(batch),
        pose_world_rig_ref=_identity_pose(batch),
        voxel_extent=torch.tensor([-1.0, 1.0, -1.0, 1.0, -1.0, 1.0], dtype=torch.float32),
        grid_shape=(grid, grid, grid),
    )
    assert pos_grid.shape == (batch, 3, grid, grid, grid)


def test_sample_voxel_field_validity_mask() -> None:
    b, c, d, h, w = 1, 4, 6, 6, 6
    field = torch.randn((b, c, d, h, w), dtype=torch.float32)
    t_world_voxel = _identity_pose(b)
    voxel_extent = torch.tensor([0.0, 6.0, 0.0, 6.0, 0.0, 6.0], dtype=torch.float32)

    # Candidate 0: inside, Candidate 1: outside.
    points_world = torch.tensor(
        [
            [
                [[3.0, 3.0, 3.0], [4.0, 3.0, 3.0]],
                [[30.0, 30.0, 30.0], [40.0, 30.0, 30.0]],
            ]
        ],
        dtype=torch.float32,
    )

    tokens, valid = sample_voxel_field(
        field,
        points_world=points_world,
        t_world_voxel=t_world_voxel,
        voxel_extent=voxel_extent,
    )
    assert tokens.shape == (1, 2, 2, c)
    assert valid.shape == (1, 2, 2)
    assert valid[0, 0].any().item() is True
    assert valid[0, 1].any().item() is False
    assert torch.isfinite(tokens).all()
