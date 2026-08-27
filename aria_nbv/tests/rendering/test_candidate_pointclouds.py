"""Tests for request-scoped candidate point-cloud geometry."""

from __future__ import annotations

from types import SimpleNamespace

import torch

import aria_nbv.rendering.candidate_pointclouds as candidate_pointclouds


def test_prepared_sample_geometry_reuses_collapse_and_static_bounds(monkeypatch) -> None:
    collapse_calls = 0

    def collapse_points() -> torch.Tensor:
        nonlocal collapse_calls
        collapse_calls += 1
        return torch.tensor([[3.0, 0.0, 0.0]], dtype=torch.float32)

    sample = SimpleNamespace(
        semidense=SimpleNamespace(collapse_points=collapse_points),
        get_occupancy_extend=lambda: torch.tensor([-1.0, 1.0, -1.0, 1.0, -1.0, 1.0]),
    )
    batch = SimpleNamespace(
        depths=torch.ones((1, 2, 2), dtype=torch.float32),
        depths_valid_mask=torch.ones((1, 2, 2), dtype=torch.bool),
        p3d_cameras=object(),
    )
    monkeypatch.setattr(
        candidate_pointclouds,
        "backproject_depths_p3d_batch",
        lambda **_kwargs: (
            torch.tensor([[[0.0, 4.0, 0.0]]], dtype=torch.float32),
            torch.tensor([1], dtype=torch.long),
        ),
    )

    prepared = candidate_pointclouds.prepare_sample_geometry(
        sample,
        device=torch.device("cpu"),
        dtype=torch.float32,
    )
    first = candidate_pointclouds.build_candidate_pointclouds(sample, batch, prepared_sample=prepared)
    second = candidate_pointclouds.build_candidate_pointclouds(sample, batch, prepared_sample=prepared)

    assert collapse_calls == 1
    assert first.semidense_points.data_ptr() == second.semidense_points.data_ptr()
    assert first.occupancy_bounds.tolist() == [-1.0, 3.0, -1.0, 4.0, -1.0, 1.0]
