"""Cross-device determinism for VIN semidense-point sampling."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import torch

from aria_nbv.vin.geometry.semidense_projection import sample_semidense_points


def _accelerator() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    pytest.skip("cross-device RNG parity requires CUDA or MPS")


@pytest.mark.parametrize("batched", [False, True])
def test_seeded_semidense_sample_matches_across_devices(batched: bool) -> None:
    accelerator = _accelerator()
    points = torch.arange(80, dtype=torch.float32).reshape(16, 5)
    if batched:
        points = torch.stack((points, points + 100.0))
        lengths = torch.tensor([16, 13], dtype=torch.int64)
    else:
        lengths = torch.tensor([16], dtype=torch.int64)

    torch.manual_seed(17)
    expected = sample_semidense_points(
        SimpleNamespace(points_world=points, lengths=lengths),
        device=torch.device("cpu"),
        max_points=7,
    )
    torch.manual_seed(17)
    actual = sample_semidense_points(
        SimpleNamespace(points_world=points.to(accelerator), lengths=lengths.to(accelerator)),
        device=accelerator,
        max_points=7,
    )

    assert torch.allclose(actual.cpu(), expected, atol=0.0, rtol=0.0, equal_nan=True)
