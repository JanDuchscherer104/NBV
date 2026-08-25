"""Contracts for modular finite-horizon scene carriers."""

# ruff: noqa: S101

from __future__ import annotations

from dataclasses import replace

import pytest
import torch
from efm3d.aria.pose import PoseTW

from aria_nbv.data_handling.qh_data import QhActorTensors
from aria_nbv.vin.modules.qh_scene_encoders import QhRootMomentsSceneEncoder
from tests.vin.test_target_finite_horizon import _actor


def _encoder() -> QhRootMomentsSceneEncoder:
    """Return the exact ``root_moments_v1`` carrier used by the scorer."""

    return QhRootMomentsSceneEncoder(scene_channels=("occ_pr", "occ_input", "free_input", "counts", "cent_pr"))


def _legacy_root_moments(actor: QhActorTensors) -> torch.Tensor:
    """Reproduce the pre-extraction inline control for parity evidence."""

    context = actor.static_context
    assert context is not None
    pooled = []
    for name in ("occ_pr", "occ_input", "free_input", "counts", "cent_pr"):
        value = getattr(context, name).detach().float().reshape(actor.step_mask.shape[0], -1)
        pooled.append(
            torch.stack(
                (
                    value.mean(dim=-1),
                    value.std(dim=-1, unbiased=False),
                    value.amin(dim=-1),
                    value.amax(dim=-1),
                ),
                dim=-1,
            )
        )
    points = actor.vin_snippet.points_world.detach().float()[..., :3]
    lengths = actor.vin_snippet.lengths.reshape(points.shape[0], -1)[:, 0].long()
    point_mask = torch.arange(points.shape[1], device=points.device).unsqueeze(0) < lengths.unsqueeze(1)
    point_mask &= torch.isfinite(points).all(dim=-1)
    points_root = actor.root_pose_world.inverse().transform(points)
    safe_points = torch.where(point_mask.unsqueeze(-1), points_root, torch.zeros_like(points_root))
    valid_count = point_mask.sum(dim=1, keepdim=True)
    count = valid_count.clamp_min(1)
    mean = safe_points.sum(dim=1) / count
    centered = torch.where(point_mask.unsqueeze(-1), points_root - mean.unsqueeze(1), torch.zeros_like(points_root))
    std = (centered.square().sum(dim=1) / count).sqrt()
    support = (valid_count.float() / max(points.shape[1], 1)).clamp(0.0, 1.0)
    present = valid_count.gt(0).float()
    return torch.cat((*pooled, mean, std, present, support), dim=-1)


def test_qh_root_moments_is_parameter_free_with_exact_control_width() -> None:
    actor = _actor()
    encoder = _encoder()

    encoded = encoder(actor)

    assert encoder.output_dim == 28
    assert not encoder.state_dict()
    assert encoded.shape == (1, 28)
    assert encoded.dtype is torch.float32
    assert torch.equal(encoded, _legacy_root_moments(actor))


def test_qh_root_moments_is_root_frame_invariant_and_tracks_raw_support() -> None:
    actor = _actor()
    encoder = _encoder()
    points = actor.vin_snippet.points_world.clone()
    root = actor.root_pose_world.tensor().clone()
    root[0, -3:] = torch.tensor([2.0, -1.0, 0.5])
    shifted = replace(
        actor,
        root_pose_world=PoseTW(root),
        vin_snippet=replace(actor.vin_snippet, points_world=points + root[:, -3:]),
    )
    assert torch.allclose(encoder(actor), encoder(shifted))

    empty = replace(actor, vin_snippet=replace(actor.vin_snippet, lengths=torch.tensor([0])))
    zero = replace(actor, vin_snippet=replace(actor.vin_snippet, points_world=torch.zeros_like(points)))
    empty_features = encoder(empty)
    zero_features = encoder(zero)
    assert empty_features[0, -2:].tolist() == [0.0, 0.0]
    assert zero_features[0, -2:].tolist() == [1.0, 1.0]


def test_qh_root_moments_rejects_out_of_range_point_lengths() -> None:
    actor = _actor()
    invalid = replace(actor, vin_snippet=replace(actor.vin_snippet, lengths=torch.tensor([99])))

    with pytest.raises(ValueError, match=r"lengths must be in \[0,"):
        _encoder()(invalid)


def test_qh_root_moments_support_retains_batch_padded_capacity_semantics() -> None:
    """Make the inherited batch-dependent denominator explicit and auditable."""

    actor = _actor()
    points = actor.vin_snippet.points_world
    padded_points = torch.full(
        (points.shape[0], points.shape[1] + 3, points.shape[2]),
        float("nan"),
        dtype=points.dtype,
        device=points.device,
    )
    padded_points[:, : points.shape[1]] = points
    padded = replace(actor, vin_snippet=replace(actor.vin_snippet, points_world=padded_points))
    length = int(actor.vin_snippet.lengths.reshape(-1)[0])

    original_support = _encoder()(actor)[0, -1]
    padded_support = _encoder()(padded)[0, -1]

    assert original_support.item() == pytest.approx(length / points.shape[1])
    assert padded_support.item() == pytest.approx(length / padded_points.shape[1])
    assert padded_support < original_support


@pytest.mark.parametrize("scene_channels", [(), ("occ_pr", "occ_pr")])
def test_qh_root_moments_rejects_ambiguous_channel_layout(scene_channels) -> None:
    with pytest.raises(ValueError, match="scene_channels"):
        QhRootMomentsSceneEncoder(scene_channels=scene_channels)
