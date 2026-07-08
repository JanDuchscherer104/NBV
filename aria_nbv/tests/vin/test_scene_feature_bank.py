"""Tests for actor-visible scene feature-bank helpers."""

# ruff: noqa: S101

from __future__ import annotations

import pytest
import torch
from efm3d.aria import CameraTW, PoseTW

from aria_nbv.vin.feature_bank import (
    PointFeatureBank,
    compress_point_features,
    pool_multiview_point_features,
    pool_point_query,
    sample_logged_image_features_at_world_points,
    validate_actor_feature_provenance,
)


def _identity_pose_batch(num_frames: int) -> PoseTW:
    rotations = torch.eye(3, dtype=torch.float32).reshape(1, 3, 3).repeat(num_frames, 1, 1)
    translations = torch.zeros((num_frames, 3), dtype=torch.float32)
    return PoseTW.from_Rt(rotations, translations)


def _translated_pose_batch(translations: torch.Tensor) -> PoseTW:
    rotations = (
        torch.eye(3, dtype=torch.float32).reshape(1, 1, 3, 3).repeat(translations.shape[0], translations.shape[1], 1, 1)
    )
    return PoseTW.from_Rt(rotations, translations.to(dtype=torch.float32))


def _camera_batch(num_frames: int, *, width: int = 4, height: int = 4) -> CameraTW:
    one = CameraTW.from_surreal(
        width=torch.tensor([float(width)]),
        height=torch.tensor([float(height)]),
        type_str="Pinhole",
        params=torch.tensor([[1.0, 1.0, (width - 1) / 2.0, (height - 1) / 2.0]], dtype=torch.float32),
        gain=torch.zeros(1),
        exposure_s=torch.zeros(1),
        valid_radius=torch.tensor([float(max(width, height))]),
        T_camera_rig=PoseTW.from_matrix3x4(torch.eye(3, 4, dtype=torch.float32).unsqueeze(0)),
    )
    return CameraTW(one.tensor().repeat(num_frames, 1))


def test_sample_logged_image_features_at_world_points_projects_logged_frames() -> None:
    feat2d = torch.arange(2 * 1 * 4 * 4, dtype=torch.float32).reshape(2, 1, 4, 4)
    points_world = torch.tensor([[0.0, 0.0, 1.0], [1.0, 0.0, 1.0]], dtype=torch.float32)

    bank = sample_logged_image_features_at_world_points(
        points_world=points_world,
        feat2d=feat2d,
        cameras=_camera_batch(2),
        t_world_camera=_identity_pose_batch(2),
        source_frame_indices=torch.tensor([10, 20]),
        warn=False,
    )

    assert isinstance(bank, PointFeatureBank)
    assert bank.points_world.shape == (1, 2, 3)
    assert bank.features.shape == (1, 2, 1)
    assert bank.per_frame_valid.shape == (1, 2, 2)
    assert bank.valid_mask.tolist() == [[True, True]]
    assert bank.valid_frame_count.tolist() == [[2, 2]]
    assert bank.source_frame_indices.tolist() == [[10, 20]]
    assert torch.allclose(bank.features.squeeze(-1), torch.tensor([[13.0, 14.0]]))


def test_sample_logged_image_features_at_world_points_uses_inverse_world_to_camera_pose() -> None:
    feat2d = torch.arange(2 * 1 * 1 * 4 * 4, dtype=torch.float32).reshape(2, 1, 1, 4, 4)
    points_world = torch.tensor([[[1.0, 0.0, 1.0]], [[2.0, 0.0, 1.0]]], dtype=torch.float32)
    t_world_camera = _translated_pose_batch(torch.tensor([[[1.0, 0.0, 0.0]], [[2.0, 0.0, 0.0]]], dtype=torch.float32))

    bank = sample_logged_image_features_at_world_points(
        points_world=points_world,
        feat2d=feat2d,
        cameras=_camera_batch(1),
        t_world_camera=t_world_camera,
        warn=False,
    )

    assert bank.valid_mask.tolist() == [[True], [True]]
    assert torch.allclose(bank.features.squeeze(-1), torch.tensor([[5.0], [21.0]]))


def test_sample_logged_image_features_at_world_points_records_compression_id() -> None:
    feat2d = torch.arange(2 * 2 * 4 * 4, dtype=torch.float32).reshape(2, 2, 4, 4)
    points_world = torch.tensor([[0.0, 0.0, 1.0]], dtype=torch.float32)

    bank = sample_logged_image_features_at_world_points(
        points_world=points_world,
        feat2d=feat2d,
        cameras=_camera_batch(2),
        t_world_camera=_identity_pose_batch(2),
        compression_output_dim=1,
        warn=False,
    )

    assert bank.features.shape == (1, 1, 1)
    assert bank.compression_id == "slice_1d"


def test_pool_multiview_point_features_empty_points() -> None:
    sampled = torch.zeros((1, 3, 0, 4), dtype=torch.float32)
    valid = torch.zeros((1, 3, 0), dtype=torch.bool)

    pooled = pool_multiview_point_features(sampled, valid)

    assert pooled.features.shape == (1, 0, 4)
    assert pooled.valid_mask.shape == (1, 0)
    assert pooled.valid_frame_count.shape == (1, 0)


def test_pool_multiview_point_features_all_invalid_returns_zero_descriptors() -> None:
    sampled = torch.ones((1, 2, 3, 2), dtype=torch.float32)
    valid = torch.zeros((1, 2, 3), dtype=torch.bool)

    pooled = pool_multiview_point_features(sampled, valid)

    assert torch.equal(pooled.features, torch.zeros_like(pooled.features))
    assert pooled.valid_mask.tolist() == [[False, False, False]]
    assert pooled.valid_frame_count.tolist() == [[0, 0, 0]]
    assert torch.equal(pooled.weight_sum, torch.zeros_like(pooled.weight_sum))


def test_pool_multiview_point_features_mixed_valid_weighted_mean() -> None:
    sampled = torch.tensor(
        [
            [
                [[1.0, 10.0], [2.0, 20.0]],
                [[3.0, 30.0], [4.0, 40.0]],
                [[5.0, 50.0], [6.0, 60.0]],
            ]
        ],
        dtype=torch.float32,
    )
    valid = torch.tensor([[[True, True], [False, True], [True, False]]])
    weights = torch.tensor([[1.0, 2.0, 3.0]], dtype=torch.float32)

    pooled = pool_multiview_point_features(sampled, valid, point_weights=weights)

    expected = torch.tensor([[[4.0, 40.0], [10.0 / 3.0, 100.0 / 3.0]]], dtype=torch.float32)
    assert torch.allclose(pooled.features, expected)
    assert pooled.valid_frame_count.tolist() == [[2, 2]]
    assert torch.allclose(pooled.weight_sum, torch.tensor([[4.0, 3.0]]))


def test_pool_multiview_point_features_frame_order_invariant() -> None:
    sampled = torch.randn((1, 4, 3, 5), generator=torch.Generator().manual_seed(7))
    valid = torch.tensor([[[True, False, True], [True, True, False], [False, True, True], [True, False, False]]])
    weights = torch.tensor([[1.0, 2.0, 3.0, 4.0]], dtype=torch.float32)

    pooled = pool_multiview_point_features(sampled, valid, point_weights=weights)
    perm = torch.tensor([2, 0, 3, 1])
    pooled_perm = pool_multiview_point_features(
        sampled[:, perm],
        valid[:, perm],
        point_weights=weights[:, perm],
    )

    assert torch.allclose(pooled.features, pooled_perm.features)
    assert torch.equal(pooled.valid_frame_count, pooled_perm.valid_frame_count)


def test_pool_point_query_is_permutation_invariant_over_points() -> None:
    features = torch.tensor(
        [[[1.0, 4.0], [2.0, 3.0], [10.0, -1.0], [3.0, 2.0]]],
        dtype=torch.float32,
    )
    mask = torch.tensor([[True, True, False, True]])

    pooled = pool_point_query(features, mask)
    perm = torch.tensor([3, 0, 2, 1])
    pooled_perm = pool_point_query(features[:, perm], mask[:, perm])

    assert torch.allclose(pooled.mean, pooled_perm.mean)
    assert torch.allclose(pooled.maximum, pooled_perm.maximum)
    assert torch.allclose(pooled.std, pooled_perm.std)
    assert torch.equal(pooled.count, pooled_perm.count)
    assert pooled.count.tolist() == [3]


def test_pool_point_query_empty_support() -> None:
    features = torch.zeros((2, 0, 3), dtype=torch.float32)
    mask = torch.zeros((2, 0), dtype=torch.bool)

    pooled = pool_point_query(features, mask)

    assert pooled.mean.shape == (2, 3)
    assert pooled.maximum.shape == (2, 3)
    assert pooled.std.shape == (2, 3)
    assert pooled.count.tolist() == [0, 0]
    assert pooled.valid_mask.tolist() == [False, False]


def test_validate_actor_feature_provenance_rejects_oracle_sources() -> None:
    validate_actor_feature_provenance(feature_source="efm3d_feat2d_upsampled")
    validate_actor_feature_provenance(feature_source="cubercnn_roi")
    with pytest.raises(ValueError, match="not an actor-visible"):
        validate_actor_feature_provenance(feature_source="gt_mesh")
    with pytest.raises(ValueError, match="not an actor-visible"):
        validate_actor_feature_provenance(feature_source="unvisited_candidate_roi")
    with pytest.raises(ValueError, match="not an approved"):
        validate_actor_feature_provenance(feature_source="some_new_descriptor")
    with pytest.raises(ValueError, match="source_role"):
        validate_actor_feature_provenance(feature_source="efm3d_feat2d_upsampled", source_role="oracle")


def test_point_feature_bank_constructor_rejects_gt_crop() -> None:
    with pytest.raises(ValueError, match="not an actor-visible"):
        PointFeatureBank(
            points_world=torch.zeros((1, 1, 3)),
            features=torch.zeros((1, 1, 2)),
            valid_mask=torch.ones((1, 1), dtype=torch.bool),
            valid_frame_count=torch.ones((1, 1), dtype=torch.int64),
            weight_sum=torch.ones((1, 1)),
            per_frame_valid=torch.ones((1, 1, 1), dtype=torch.bool),
            source_frame_indices=torch.zeros((1, 1), dtype=torch.int64),
            feature_source="gt_obb_crop",
        )


def test_compress_point_features_projection_and_slice() -> None:
    features = torch.tensor([[[1.0, 2.0, 3.0]]])
    projection = torch.tensor([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])

    assert torch.allclose(compress_point_features(features, projection=projection), torch.tensor([[[4.0, 5.0]]]))
    assert torch.equal(compress_point_features(features, output_dim=2), features[..., :2])
