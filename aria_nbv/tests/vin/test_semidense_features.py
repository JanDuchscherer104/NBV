import torch

from aria_nbv.data_handling.efm_views import EfmPointsView
from aria_nbv.vin.models import VinModelV2, VinModelV2Config


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
