"""Contracts for modular finite-horizon scene carriers."""

# ruff: noqa: S101

from __future__ import annotations

from dataclasses import replace

import pytest
import torch
from efm3d.aria.camera import CameraTW
from efm3d.aria.pose import PoseTW

import aria_nbv.vin.modules.qh_scene_encoders as scene_encoders
from aria_nbv.data_handling.qh_data import QhActorTensors
from aria_nbv.data_handling.qh_data.batching import move_qh_actor_tensors
from aria_nbv.vin.modules.qh_scene_encoders import (
    QhRootMomentsSceneEncoder,
    QhSelectedSurfacePointSceneEncoder,
    QhSelectedSurfacePointSceneEncoderConfig,
)
from tests.vin.test_target_finite_horizon import _actor, _cfplus_actor, _scorer


def _encoder() -> QhRootMomentsSceneEncoder:
    """Return the exact ``root_moments_v1`` carrier used by the scorer."""

    return QhRootMomentsSceneEncoder(scene_channels=("occ_pr", "occ_input", "free_input", "counts", "cent_pr"))


def _s1_encoder(
    *,
    pixel_stride: int = 1,
    view_chunk_size: int = 16,
    point_hidden_dim: int = 8,
) -> QhSelectedSurfacePointSceneEncoder:
    """Return a deterministic fixed-width S1 selected-surface encoder."""

    torch.manual_seed(5)
    encoder = QhSelectedSurfacePointSceneEncoderConfig(
        pixel_stride=pixel_stride,
        view_chunk_size=view_chunk_size,
        point_hidden_dim=point_hidden_dim,
        coordinate_scale_m=2.0,
    ).setup_target(
        scene_channels=("occ_pr", "occ_input", "free_input", "counts", "cent_pr"),
        dropout=0.0,
    )
    encoder.eval()
    return encoder


def _identity_current_pose(actor: QhActorTensors) -> PoseTW:
    """Return root-from-current identities over the actor B,S axes."""

    values = (
        PoseTW().tensor().to(device=actor.step_mask.device).reshape(1, 1, 12).expand(*actor.step_mask.shape, -1).clone()
    )
    return PoseTW(values)


def _expected_root_moments(actor: QhActorTensors) -> torch.Tensor:
    """Compute the versioned per-chain root-moments contract directly."""

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
    support = (valid_count.float() / lengths.unsqueeze(-1).clamp_min(1)).clamp(0.0, 1.0)
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
    assert torch.equal(encoded, _expected_root_moments(actor))


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


def test_qh_root_moments_and_scores_ignore_batch_point_padding() -> None:
    """Collation capacity cannot alter one chain's scene state or predictions."""

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
    original_features = _encoder()(actor)
    padded_features = _encoder()(padded)
    scorer = _scorer()
    original_scores = scorer(actor)
    padded_scores = scorer(padded)

    assert torch.equal(padded_features, original_features)
    assert torch.equal(padded_scores.conditional_q, original_scores.conditional_q)
    assert torch.equal(padded_scores.feasibility_logits, original_scores.feasibility_logits)


@pytest.mark.parametrize("scene_channels", [(), ("occ_pr", "occ_pr")])
def test_qh_root_moments_rejects_ambiguous_channel_layout(scene_channels) -> None:
    with pytest.raises(ValueError, match="scene_channels"):
        QhRootMomentsSceneEncoder(scene_channels=scene_channels)


def test_qh_s1_empty_valid_support_is_exactly_the_root_control() -> None:
    actor = _cfplus_actor()
    prefix = actor.selected_observation_prefix
    assert prefix is not None
    empty = replace(actor, selected_observation_prefix=replace(prefix, valid_mask=torch.zeros_like(prefix.valid_mask)))
    root = _encoder()(empty).unsqueeze(1).expand(-1, actor.step_mask.shape[1], -1)

    encoded = _s1_encoder()(empty, current_pose_relative_root=_identity_current_pose(empty))

    assert torch.equal(encoded[actor.step_mask], root[actor.step_mask])
    assert torch.equal(encoded[~actor.step_mask], torch.zeros_like(encoded[~actor.step_mask]))


def test_qh_s1_support_features_bind_sampled_capacity() -> None:
    actor = _cfplus_actor()
    encoder = _s1_encoder(pixel_stride=2)
    pooled_inputs: list[torch.Tensor] = []
    handle = encoder.point_update.register_forward_pre_hook(
        lambda _module, args: pooled_inputs.append(args[0].detach().clone())
    )

    encoder(actor, current_pose_relative_root=_identity_current_pose(actor))
    handle.remove()

    assert len(pooled_inputs) == 1
    diagnostics = pooled_inputs[0][:, -3:].reshape(*actor.step_mask.shape, 3)
    assert diagnostics[0, 0].tolist() == [0.0, 0.0, 0.0]
    assert diagnostics[0, 1].tolist() == [1.0, 1.0, 1.0]
    assert diagnostics[0, 2].tolist() == [1.0, 1.0, 1.0]


def test_qh_s1_support_features_separate_pixel_and_view_support() -> None:
    """Pixel density and observation coverage remain distinct estimands."""

    actor = _cfplus_actor()
    prefix = actor.selected_observation_prefix
    assert prefix is not None
    valid = prefix.valid_mask.clone()
    valid[0, 2, 0, 0] = False
    valid[0, 2, 1] = False
    changed = replace(actor, selected_observation_prefix=replace(prefix, valid_mask=valid))
    encoder = _s1_encoder(pixel_stride=1)
    pooled_inputs: list[torch.Tensor] = []
    handle = encoder.point_update.register_forward_pre_hook(
        lambda _module, args: pooled_inputs.append(args[0].detach().clone())
    )

    encoder(changed, current_pose_relative_root=_identity_current_pose(changed))
    handle.remove()

    diagnostics = pooled_inputs[0][:, -3:].reshape(*actor.step_mask.shape, 3)
    assert diagnostics[0, 2].tolist() == [1.0, 0.25, 0.5]


def test_qh_s1_global_replication_preserves_density_weighted_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replicating all points and sampled capacity leaves S1 unchanged."""

    actor = _cfplus_actor()
    encoder = _s1_encoder(pixel_stride=1, point_hidden_dim=3)
    encoder.point_encoder = torch.nn.Identity()
    pooled_inputs: list[torch.Tensor] = []

    def fake_backproject(depths, mask_valid, camera, pose_world_camera, *, stride):
        del mask_valid, camera, pose_world_camera, stride
        points = torch.tensor(
            [[0.25, 0.5, 1.0], [1.0, -0.5, 0.75]],
            dtype=torch.float32,
            device=depths.device,
        )
        return points.unsqueeze(0).expand(depths.shape[0], -1, -1).clone(), torch.full(
            (depths.shape[0],), 2, dtype=torch.int64, device=depths.device
        )

    monkeypatch.setattr(scene_encoders, "backproject_depths_camera_tw_batch", fake_backproject)
    handle = encoder.point_update.register_forward_pre_hook(
        lambda _module, args: pooled_inputs.append(args[0].detach().clone())
    )
    encoder(actor, current_pose_relative_root=_identity_current_pose(actor))
    handle.remove()

    pooled = pooled_inputs[0].reshape(*actor.step_mask.shape, -1)
    assert torch.equal(pooled[0, 1], pooled[0, 2])


def test_qh_s1_partial_duplication_changes_density_weighted_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Duplicating only one surface region changes its empirical measure."""

    actor = _cfplus_actor()
    prefix = actor.selected_observation_prefix
    assert prefix is not None
    encoder = _s1_encoder(pixel_stride=1)
    pooled_inputs: list[torch.Tensor] = []

    def fake_backproject(depths, mask_valid, camera, pose_world_camera, *, stride):
        del mask_valid, camera, pose_world_camera, stride
        values = depths[:, 0, 0].float()
        points = torch.stack((values, torch.zeros_like(values), torch.ones_like(values)), dim=-1).unsqueeze(1)
        return points, torch.ones(depths.shape[0], dtype=torch.int64, device=depths.device)

    monkeypatch.setattr(scene_encoders, "backproject_depths_camera_tw_batch", fake_backproject)
    handle = encoder.point_update.register_forward_pre_hook(
        lambda _module, args: pooled_inputs.append(args[0].detach().clone())
    )
    encoder(actor, current_pose_relative_root=_identity_current_pose(actor))
    duplicated_depth = prefix.depth_m.clone()
    duplicated_depth[0, 2, 1] = duplicated_depth[0, 2, 0]
    duplicated = replace(actor, selected_observation_prefix=replace(prefix, depth_m=duplicated_depth))
    encoder(duplicated, current_pose_relative_root=_identity_current_pose(duplicated))
    handle.remove()

    baseline = pooled_inputs[0].reshape(*actor.step_mask.shape, -1)[0, 2]
    duplicated_summary = pooled_inputs[1].reshape(*actor.step_mask.shape, -1)[0, 2]
    assert not torch.equal(duplicated_summary, baseline)


def test_qh_s1_stride_is_representation_identity() -> None:
    """Changing the deterministic pixel lattice changes the point-set input."""

    actor = _cfplus_actor()
    pooled_inputs: list[torch.Tensor] = []
    encoders = (_s1_encoder(pixel_stride=1), _s1_encoder(pixel_stride=2))
    handles = [
        encoder.point_update.register_forward_pre_hook(
            lambda _module, args: pooled_inputs.append(args[0].detach().clone())
        )
        for encoder in encoders
    ]

    for encoder in encoders:
        encoder(actor, current_pose_relative_root=_identity_current_pose(actor))
    for handle in handles:
        handle.remove()

    first = pooled_inputs[0].reshape(*actor.step_mask.shape, -1)[0, 2]
    second = pooled_inputs[1].reshape(*actor.step_mask.shape, -1)[0, 2]
    assert not torch.equal(second, first)


def test_qh_s1_point_pool_is_permutation_invariant(monkeypatch: pytest.MonkeyPatch) -> None:
    actor = _cfplus_actor()
    encoder = _s1_encoder()
    reverse = False

    def fake_backproject(depths, mask_valid, camera, pose_world_camera, *, stride):
        del mask_valid, camera, pose_world_camera, stride
        points = torch.tensor(
            [[0.25, 0.5, 1.0], [1.0, -0.5, 0.75], [-0.25, 0.0, 1.5]],
            dtype=torch.float32,
            device=depths.device,
        )
        if reverse:
            points = points.flip(0)
        return points.unsqueeze(0).expand(depths.shape[0], -1, -1).clone(), torch.full(
            (depths.shape[0],),
            points.shape[0],
            dtype=torch.int64,
            device=depths.device,
        )

    monkeypatch.setattr(scene_encoders, "backproject_depths_camera_tw_batch", fake_backproject)
    first = encoder(actor, current_pose_relative_root=_identity_current_pose(actor))
    reverse = True
    second = encoder(actor, current_pose_relative_root=_identity_current_pose(actor))

    torch.testing.assert_close(second, first, rtol=0.0, atol=1e-7)


def test_qh_s1_applies_root_to_current_transform_once(monkeypatch: pytest.MonkeyPatch) -> None:
    actor = _cfplus_actor()
    encoder = _s1_encoder()
    point_inputs: list[torch.Tensor] = []

    def fake_backproject(depths, mask_valid, camera, pose_world_camera, *, stride):
        del mask_valid, camera, pose_world_camera, stride
        points = torch.tensor([[[1.0, 0.0, 0.0]]], dtype=torch.float32, device=depths.device)
        return points.expand(depths.shape[0], -1, -1).clone(), torch.ones(
            depths.shape[0], dtype=torch.int64, device=depths.device
        )

    monkeypatch.setattr(scene_encoders, "backproject_depths_camera_tw_batch", fake_backproject)
    handle = encoder.point_encoder.register_forward_pre_hook(
        lambda _module, args: point_inputs.append(args[0].detach().clone())
    )
    encoder(actor, current_pose_relative_root=_identity_current_pose(actor))
    translated = _identity_current_pose(actor).tensor().clone()
    translated[:, 1:, -3] = 1.0
    encoder(actor, current_pose_relative_root=PoseTW(translated))
    handle.remove()

    assert torch.equal(point_inputs[0][..., 0], torch.full_like(point_inputs[0][..., 0], 0.5))
    assert torch.equal(point_inputs[1][..., 0], torch.zeros_like(point_inputs[1][..., 0]))


def test_qh_s1_projection_opens_before_upstream_point_path_receives_gradients() -> None:
    """Identity start delays only the point MLP, not the residual projection."""

    actor = _cfplus_actor()
    # Force repeated differentiable accumulator updates across chunks.
    encoder = _s1_encoder(view_chunk_size=1)
    encoder.train()
    optimizer = torch.optim.SGD(encoder.parameters(), lr=0.1)

    encoder(actor, current_pose_relative_root=_identity_current_pose(actor)).sum().backward()

    first_gradients = dict(encoder.named_parameters())
    projection_gradient = first_gradients["point_update.weight"].grad
    assert projection_gradient is not None
    assert torch.isfinite(projection_gradient).all()
    assert bool(projection_gradient.abs().sum().gt(0))
    for name, parameter in first_gradients.items():
        if name.startswith("point_encoder."):
            assert parameter.grad is not None
            assert torch.count_nonzero(parameter.grad) == 0

    optimizer.step()
    optimizer.zero_grad(set_to_none=True)
    assert torch.count_nonzero(encoder.point_update.weight) > 0

    encoder(actor, current_pose_relative_root=_identity_current_pose(actor)).sum().backward()

    gradients = [parameter.grad for parameter in encoder.parameters()]
    assert gradients
    assert all(gradient is not None and torch.isfinite(gradient).all() for gradient in gradients)
    assert all(bool(gradient.abs().sum().gt(0)) for gradient in gradients if gradient is not None)


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA autocast requires a GPU")
@pytest.mark.parametrize("dtype", [torch.float16, torch.bfloat16])
def test_qh_s1_cuda_autocast_preserves_float32_reductions_and_gradients(dtype: torch.dtype) -> None:
    if dtype is torch.bfloat16 and not torch.cuda.is_bf16_supported():
        pytest.skip("CUDA device does not support bfloat16")
    actor = move_qh_actor_tensors(_cfplus_actor(), "cuda", non_blocking=False)
    encoder = _s1_encoder(view_chunk_size=1).cuda().train()

    with torch.autocast(device_type="cuda", dtype=dtype):
        encoded = encoder(actor, current_pose_relative_root=_identity_current_pose(actor))
        loss = encoded.square().mean()
    loss.backward()

    assert encoded.dtype is torch.float32
    gradients = [parameter.grad for parameter in encoder.parameters()]
    assert all(gradient is not None and torch.isfinite(gradient).all() for gradient in gradients)


@pytest.mark.parametrize("field", ["depth", "camera", "pose"])
def test_qh_s1_rejects_malformed_active_geometry_before_backprojection(field: str) -> None:
    actor = _cfplus_actor()
    prefix = actor.selected_observation_prefix
    assert prefix is not None
    if field == "depth":
        depth = prefix.depth_m.clone()
        depth[0, 1, 0, 0, 0] = torch.nan
        changed = replace(prefix, depth_m=depth)
        expected = "finite positive metres"
    elif field == "camera":
        camera = prefix.camera.tensor().clone()
        camera[0, 1, 0, 2] = 0.0
        changed = replace(prefix, camera=CameraTW(camera))
        expected = "positive pinhole intrinsics"
    else:
        pose = prefix.camera_pose_relative_root.tensor().clone()
        pose[0, 1, 0, :9] = 0.0
        changed = replace(prefix, camera_pose_relative_root=PoseTW(pose))
        expected = "proper rigid transforms"

    with pytest.raises(ValueError, match=expected):
        _s1_encoder()(
            replace(actor, selected_observation_prefix=changed),
            current_pose_relative_root=_identity_current_pose(actor),
        )
