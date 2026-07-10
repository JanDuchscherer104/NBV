import torch
from efm3d.aria.aria_constants import ARIA_POINTS_VOL_MAX, ARIA_POINTS_VOL_MIN, ARIA_POINTS_WORLD

from aria_nbv.data_handling.raw.dataset import infer_semidense_bounds


def test_infer_bounds_prefers_volume_keys():
    efm = {
        ARIA_POINTS_VOL_MIN: torch.tensor([0.0, 0.0, 0.0]),
        ARIA_POINTS_VOL_MAX: torch.tensor([1.0, 1.0, 1.0]),
        ARIA_POINTS_WORLD: torch.zeros((1, 2, 3)),
    }

    bounds = infer_semidense_bounds(efm)
    assert bounds is not None
    lo, hi = bounds
    assert torch.allclose(lo, torch.tensor([0.0, 0.0, 0.0]))
    assert torch.allclose(hi, torch.tensor([0.0, 0.0, 0.0]))


def test_infer_bounds_falls_back_to_points_and_lengths():
    points = torch.tensor(
        [
            [
                [0.0, 0.0, 0.0],
                [1.0, 2.0, 3.0],
                [float("nan"), float("nan"), float("nan")],
                [10.0, 10.0, 10.0],
            ]
        ]
    )
    lengths = torch.tensor([2])
    efm = {ARIA_POINTS_WORLD: points, "msdpd#points_world_lengths": lengths}

    bounds = infer_semidense_bounds(efm)
    assert bounds is not None
    lo, hi = bounds
    assert torch.allclose(lo, torch.tensor([0.0, 0.0, 0.0]))
    assert torch.allclose(hi, torch.tensor([1.0, 2.0, 3.0]))
