"""Cross-device determinism for seeded candidate-pose sampling."""

from __future__ import annotations

import pytest
import torch
from efm3d.aria.pose import PoseTW

from aria_nbv.pose_generation.candidate_generation import CandidateViewGeneratorConfig, _maybe_seed
from aria_nbv.pose_generation.orientations import OrientationBuilder
from aria_nbv.pose_generation.positional_sampling import PositionSampler
from aria_nbv.pose_generation.types import SamplingStrategy


def _accelerator() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    pytest.skip("cross-device RNG parity requires CUDA or MPS")


def _sample(
    device: torch.device,
    *,
    position_strategy: SamplingStrategy,
    view_strategy: SamplingStrategy | None,
) -> tuple[torch.Tensor, torch.Tensor]:
    bounded_jitter = view_strategy is None
    cfg = CandidateViewGeneratorConfig(
        device=device,
        num_samples=4,
        oversample_factor=1.0,
        min_radius=0.5,
        max_radius=0.8,
        sampling_strategy=position_strategy,
        view_sampling_strategy=view_strategy,
        view_max_azimuth_deg=10.0 if bounded_jitter else 0.0,
        view_max_elevation_deg=5.0 if bounded_jitter else 0.0,
        view_roll_jitter_deg=3.0,
        ensure_collision_free=False,
        ensure_free_space=False,
        min_distance_to_mesh=0.0,
        seed=7,
    )
    reference_pose = PoseTW.from_Rt(torch.eye(3, device=device), torch.zeros(3, device=device))
    with _maybe_seed(cfg.seed):
        _, offsets = PositionSampler(cfg).sample(reference_pose)
        _, view_delta = OrientationBuilder(cfg).build(reference_pose, offsets)

    assert view_delta is not None
    return offsets.cpu(), view_delta.tensor().cpu()


@pytest.mark.parametrize("position_strategy", list(SamplingStrategy))
@pytest.mark.parametrize("view_strategy", [None, *list(SamplingStrategy)])
def test_seeded_pose_samples_match_across_devices(
    monkeypatch: pytest.MonkeyPatch,
    position_strategy: SamplingStrategy,
    view_strategy: SamplingStrategy | None,
) -> None:
    monkeypatch.delenv("PYTORCH3D_BACKEND", raising=False)

    cpu_offsets, cpu_delta = _sample(
        torch.device("cpu"),
        position_strategy=position_strategy,
        view_strategy=view_strategy,
    )
    accelerator_offsets, accelerator_delta = _sample(
        _accelerator(),
        position_strategy=position_strategy,
        view_strategy=view_strategy,
    )

    assert torch.allclose(accelerator_offsets, cpu_offsets, atol=1e-6, rtol=1e-6)
    assert torch.allclose(accelerator_delta, cpu_delta, atol=1e-6, rtol=1e-6)
