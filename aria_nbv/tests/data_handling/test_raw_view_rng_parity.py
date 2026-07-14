"""Cross-device determinism for semidense raw-view subsampling."""

from __future__ import annotations

import pytest
import torch

from aria_nbv.data_handling.raw.views import EfmPointsView, _cpu_randperm


def _accelerator() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    pytest.skip("cross-device RNG parity requires CUDA or MPS")


def _points_view(device: torch.device) -> EfmPointsView:
    frame0 = torch.arange(18, dtype=torch.float32).reshape(6, 3)
    frame1 = torch.arange(18, 36, dtype=torch.float32).reshape(6, 3)
    frame1[0] = frame0[0]
    points = torch.stack((frame0, frame1)).to(device)
    shape = points.shape[:2]
    return EfmPointsView(
        points_world=points,
        dist_std=torch.ones(shape, device=device),
        inv_dist_std=torch.arange(12, dtype=torch.float32, device=device).reshape(shape),
        time_ns=torch.arange(2, dtype=torch.int64, device=device),
        volume_min=torch.zeros(3, device=device),
        volume_max=torch.ones(3, device=device),
        lengths=torch.tensor([6, 6], dtype=torch.int64, device=device),
    )


def test_local_seed_zero_permutation_ignores_process_rng_and_device() -> None:
    accelerator = _accelerator()

    expected = _cpu_randperm(12, torch.device("cpu"))
    torch.manual_seed(11)
    torch.rand(17)
    actual = _cpu_randperm(12, accelerator)

    assert torch.equal(actual.cpu(), expected)


@pytest.mark.parametrize(
    ("include_inv_dist_std", "include_obs_count"),
    [(False, False), (True, False), (False, True), (True, True)],
)
def test_deterministic_collapse_points_matches_across_devices(
    include_inv_dist_std: bool,
    include_obs_count: bool,
) -> None:
    accelerator = _accelerator()
    if accelerator.type == "mps" and (include_obs_count or not include_inv_dist_std):
        pytest.skip("torch.unique(dim=0) is not implemented on MPS")

    expected = _points_view(torch.device("cpu")).collapse_points(
        max_points=5,
        include_inv_dist_std=include_inv_dist_std,
        include_obs_count=include_obs_count,
    )
    torch.rand(17)
    actual = _points_view(accelerator).collapse_points(
        max_points=5,
        include_inv_dist_std=include_inv_dist_std,
        include_obs_count=include_obs_count,
    )

    assert torch.equal(actual.cpu(), expected)


def test_deterministic_last_frame_points_matches_across_devices() -> None:
    accelerator = _accelerator()

    expected = _points_view(torch.device("cpu")).last_frame_points_np(max_points=3)
    torch.rand(17)
    actual = _points_view(accelerator).last_frame_points_np(max_points=3)

    assert (actual == expected).all()
