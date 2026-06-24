import torch
from efm3d.aria.pose import PoseTW
from pytorch3d.renderer.cameras import PerspectiveCameras  # type: ignore[import-untyped]
from torch import nn

from aria_nbv.data_handling.efm_views import EfmPointsView
from aria_nbv.vin.geometry.semidense_schema import semidense_proj_feature_index
from aria_nbv.vin.models import VinModelV2, VinModelV2Config
from aria_nbv.vin.models._v2_semidense import (
    encode_semidense_projection_features_v2,
    prepare_semidense_frustum_tokens_v2,
    prepare_semidense_point_encoder_batch_v2,
    project_semidense_points_v2,
)


def test_collapse_points_obs_count() -> None:
    device = torch.device("cpu")
    points_world = torch.tensor(
        [
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
            [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
        ],
        device=device,
        dtype=torch.float32,
    )
    dist_std = torch.zeros((2, 2), device=device, dtype=torch.float32)
    inv_dist_std = torch.tensor([[1.0, 2.0], [3.0, 4.0]], device=device, dtype=torch.float32)
    time_ns = torch.tensor([0, 1], device=device, dtype=torch.int64)
    volume_min = torch.zeros(3, device=device, dtype=torch.float32)
    volume_max = torch.ones(3, device=device, dtype=torch.float32)
    lengths = torch.tensor([2, 2], device=device, dtype=torch.int64)

    view = EfmPointsView(
        points_world=points_world,
        dist_std=dist_std,
        inv_dist_std=inv_dist_std,
        time_ns=time_ns,
        volume_min=volume_min,
        volume_max=volume_max,
        lengths=lengths,
    )

    collapsed = view.collapse_points(include_inv_dist_std=True, include_obs_count=True)
    assert collapsed.shape[1] == 5

    xyz = collapsed[:, :3]
    inv_mean = collapsed[:, 3]
    obs_count = collapsed[:, 4]

    target = torch.tensor([0.0, 0.0, 0.0], device=device)
    match = (xyz == target).all(dim=1)
    assert match.sum().item() == 1
    idx = int(torch.nonzero(match, as_tuple=False)[0].item())
    assert torch.isclose(obs_count[idx], torch.tensor(2.0, device=device))
    assert torch.isclose(inv_mean[idx], torch.tensor(2.0, device=device))


def test_semidense_visibility_embedding_changes_output() -> None:
    device = torch.device("cpu")
    cfg = VinModelV2Config(
        point_encoder=None,
        traj_encoder=None,
        enable_semidense_frustum=True,
        semidense_visibility_embed=True,
        semidense_frustum_mask_invalid=False,
    )
    model = VinModelV2(cfg).to(device=device)
    model.eval()

    assert model.sem_frustum_vis_embed is not None
    with torch.no_grad():
        model.sem_frustum_vis_embed.weight[0].fill_(0.0)
        model.sem_frustum_vis_embed.weight[1].fill_(1.0)

    pose_enc = torch.zeros((1, 1, model.pose_encoder.out_dim), device=device, dtype=torch.float32)
    base_proj = {
        "x": torch.zeros((1, 2), device=device, dtype=torch.float32),
        "y": torch.zeros((1, 2), device=device, dtype=torch.float32),
        "z": torch.zeros((1, 2), device=device, dtype=torch.float32),
        "image_size": torch.tensor([[10.0, 10.0]], device=device, dtype=torch.float32),
        "inv_dist_std": torch.empty(0, device=device),
        "obs_count": torch.empty(0, device=device),
        "num_cams": torch.tensor(1, device=device),
    }

    proj_invalid = dict(base_proj)
    proj_invalid["valid"] = torch.zeros((1, 2), device=device, dtype=torch.bool)
    out_invalid = model._encode_semidense_frustum_context(
        proj_invalid,
        pose_enc,
        batch_size=1,
        num_candidates=1,
        device=device,
        dtype=torch.float32,
    )

    proj_valid = dict(base_proj)
    proj_valid["valid"] = torch.ones((1, 2), device=device, dtype=torch.bool)
    out_valid = model._encode_semidense_frustum_context(
        proj_valid,
        pose_enc,
        batch_size=1,
        num_candidates=1,
        device=device,
        dtype=torch.float32,
    )

    assert not torch.allclose(out_invalid, out_valid)


def test_prepare_semidense_frustum_tokens_v2_normalizes_and_flattens() -> None:
    """V2 frustum token prep should preserve legacy normalized screen/depth channels."""
    device = torch.device("cpu")
    proj = {
        "x": torch.tensor([[5.0, 0.0]], device=device, dtype=torch.float32),
        "y": torch.tensor([[2.5, 0.0]], device=device, dtype=torch.float32),
        "z": torch.tensor([[3.0, 0.0]], device=device, dtype=torch.float32),
        "valid": torch.tensor([[True, False]], device=device),
        "image_size": torch.tensor([[10.0, 20.0]], device=device, dtype=torch.float32),
        "inv_dist_std": torch.tensor([[0.25, 0.75]], device=device, dtype=torch.float32),
        "obs_count": torch.tensor([[4.0, 9.0]], device=device, dtype=torch.float32),
        "num_cams": torch.tensor(1, device=device),
    }

    tokens, valid, flat_tokens, flat_valid, valid_any = prepare_semidense_frustum_tokens_v2(
        proj,
        batch_size=1,
        num_candidates=1,
        device=device,
        dtype=torch.float32,
        max_points=1,
        normalize_obs_count=lambda obs: obs / 10.0,
    )

    assert tokens.shape == (1, 1, 1, 5)
    assert valid.shape == (1, 1, 1)
    assert flat_tokens.shape == (1, 1, 5)
    assert flat_valid.shape == (1, 1)
    assert valid_any.tolist() == [True]
    assert torch.allclose(
        flat_tokens[0, 0],
        torch.tensor([-0.5, -0.5, 3.0, 0.25, 0.4], dtype=torch.float32),
    )


def test_prepare_semidense_point_encoder_batch_v2_filters_pads_and_transforms() -> None:
    """Point prep should preserve V2 finite-selection and reference-rig semantics."""
    device = torch.device("cpu")
    reference = PoseTW.from_Rt(
        torch.eye(3, device=device, dtype=torch.float32).repeat(2, 1, 1),
        torch.tensor([[10.0, 0.0, 0.0], [0.0, 0.0, 0.0]], device=device),
    )
    points_world = torch.tensor(
        [
            [
                [11.0, 2.0, 3.0, 0.5, 3.0],
                [float("nan"), 0.0, 0.0, 7.0, 9.0],
                [12.0, 2.0, 3.0, 0.25, 8.0],
            ],
            [
                [float("nan"), 0.0, 0.0, 1.0, 1.0],
                [float("inf"), 0.0, 0.0, 1.0, 1.0],
                [0.0, float("nan"), 0.0, 1.0, 1.0],
            ],
        ],
        device=device,
        dtype=torch.float32,
    )

    pts_rig, has_points = prepare_semidense_point_encoder_batch_v2(
        points_world,
        pose_world_rig_ref=reference,
        batch_size=2,
        device=device,
        max_points=3,
        normalize_obs_count=lambda obs: obs / 10.0,
    )

    assert has_points.tolist() == [True, False]
    assert pts_rig.shape == (1, 3, 5)
    assert torch.allclose(
        pts_rig[0],
        torch.tensor(
            [
                [1.0, 2.0, 3.0, 0.5, 0.3],
                [2.0, 2.0, 3.0, 0.25, 0.8],
                [2.0, 2.0, 3.0, 0.25, 0.8],
            ],
            device=device,
        ),
    )


def test_v2_semidense_point_encoder_wrapper_scatters_valid_rows() -> None:
    """The V2 model should keep encoder ownership while delegating point prep."""
    device = torch.device("cpu")

    class SumPointEncoder(nn.Module):
        out_dim = 2

        def forward(self, points: torch.Tensor) -> torch.Tensor:
            return torch.stack([points[..., 0].sum(dim=1), points[..., 3].sum(dim=1)], dim=-1)

    model = VinModelV2(VinModelV2Config(point_encoder=None, traj_encoder=None)).to(device=device)
    model.point_encoder = SumPointEncoder()
    reference = PoseTW.from_Rt(
        torch.eye(3, device=device, dtype=torch.float32).repeat(2, 1, 1),
        torch.tensor([[10.0, 0.0, 0.0], [0.0, 0.0, 0.0]], device=device),
    )
    points_world = torch.tensor(
        [
            [[11.0, 0.0, 0.0, 0.5], [12.0, 0.0, 0.0, 1.5]],
            [[float("nan"), 0.0, 0.0, 5.0], [float("inf"), 0.0, 0.0, 5.0]],
        ],
        device=device,
        dtype=torch.float32,
    )

    feat = model._encode_semidense_features(
        points_world,
        pose_world_rig_ref=reference,
        batch_size=2,
        device=device,
        dtype=torch.float32,
    )

    assert feat is not None
    assert torch.allclose(feat[0], torch.tensor([3.0, 2.0], device=device))
    assert torch.count_nonzero(feat[1]) == 0


def test_v2_semidense_projection_keeps_permissive_missing_data_contract() -> None:
    device = torch.device("cpu")
    cameras_without_size = PerspectiveCameras(
        device=device,
        R=torch.eye(3, device=device).unsqueeze(0),
        T=torch.zeros((1, 3), device=device),
    )

    assert (
        project_semidense_points_v2(
            None,
            cameras_without_size,
            batch_size=1,
            num_candidates=1,
            device=device,
        )
        is None
    )
    assert (
        project_semidense_points_v2(
            torch.ones(1, 3, device=device),
            cameras_without_size,
            batch_size=1,
            num_candidates=1,
            device=device,
        )
        is None
    )

    zeros = encode_semidense_projection_features_v2(
        None,
        batch_size=1,
        num_candidates=2,
        device=device,
        dtype=torch.float32,
        grid_size=2,
    )
    assert zeros.shape == (1, 2, 5)
    assert torch.count_nonzero(zeros) == 0


def test_v2_semidense_summary_uses_raw_visibility_and_inv_distance_depth_weights() -> None:
    device = torch.device("cpu")
    proj_data = {
        "x": torch.tensor([[0.0, 5.0]], device=device),
        "y": torch.tensor([[0.0, 5.0]], device=device),
        "z": torch.tensor([[1.0, 3.0]], device=device),
        "finite": torch.ones((1, 2), device=device, dtype=torch.bool),
        "valid": torch.ones((1, 2), device=device, dtype=torch.bool),
        "image_size": torch.tensor([[10.0, 10.0]], device=device),
        "inv_dist_std": torch.tensor([[1.0, 3.0]], device=device),
        "obs_count": torch.tensor([[100.0, 1.0]], device=device),
        "num_cams": torch.tensor(1, device=device),
    }

    feats = encode_semidense_projection_features_v2(
        proj_data,
        batch_size=1,
        num_candidates=1,
        device=device,
        dtype=torch.float32,
        grid_size=2,
    )

    vis_idx = semidense_proj_feature_index("semidense_candidate_vis_frac")
    depth_idx = semidense_proj_feature_index("depth_mean")
    assert torch.isclose(feats[0, 0, vis_idx], torch.tensor(1.0, device=device))
    assert torch.isclose(feats[0, 0, depth_idx], torch.tensor(2.5, device=device))
