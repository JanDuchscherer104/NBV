"""Symmetry and causality contracts for the temporal field transformer."""

from __future__ import annotations

import pytest
import torch
from torch import nn

from aria_nbv.vin.models.temporal_field_transformer import (
    TemporalFieldTransformer,
    TemporalFieldTransformerConfig,
    hierarchical_temporal_coral_loss,
)
from aria_nbv.vin.types.temporal_field import TemporalFieldBatch


def _poses(translations: torch.Tensor) -> torch.Tensor:
    batch, count, _ = translations.shape
    poses = torch.zeros((batch, count, 3, 4), dtype=translations.dtype)
    poses[..., :3] = torch.eye(3, dtype=translations.dtype)
    poses[..., 3] = translations
    return poses


def _global_transform(poses: torch.Tensor) -> torch.Tensor:
    rotation = torch.tensor([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    translation = torch.tensor([7.0, -3.0, 2.0])
    transformed = poses.clone()
    transformed[..., :3] = rotation @ poses[..., :3]
    transformed[..., 3] = torch.einsum("ij,...j->...i", rotation, poses[..., 3]) + translation
    return transformed


def _batch() -> TemporalFieldBatch:
    return TemporalFieldBatch(
        features=torch.tensor([[[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]]]),
        t_world_field=_poses(torch.tensor([[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 1.0, 0.0]]])),
        time_s=torch.tensor([[0.0, 1.0, 2.0]]),
        valid=torch.ones((1, 3), dtype=torch.bool),
    )


def _targets() -> torch.Tensor:
    return _poses(torch.tensor([[[0.5, 0.5, 0.0], [2.0, -0.5, 0.0], [-1.0, 1.0, 0.0]]]))


def _candidates() -> torch.Tensor:
    return _poses(torch.tensor([[[0.0, -1.0, 0.0], [3.0, 0.0, 0.0], [1.0, 2.0, 0.0]]]))


def _target_features() -> torch.Tensor:
    return torch.tensor([[[1.0, 1.0, 1.0, 0.0], [2.0, 1.0, 1.0, 0.0], [1.0, 2.0, 1.0, 1.0]]])


def _model(*, num_layers: int = 2) -> TemporalFieldTransformer:
    torch.manual_seed(7)
    model = TemporalFieldTransformer(
        TemporalFieldTransformerConfig(
            field_feature_dim=2,
            d_model=16,
            num_heads=4,
            num_layers=num_layers,
            num_classes=5,
            dropout=0.0,
        ),
    )
    return model.eval()


def test_target_and_candidate_permutation_equivariance() -> None:
    """Reordering either query axis must only reorder the matching output axis."""

    target_order = torch.tensor([2, 0, 1])
    candidate_order = torch.tensor([1, 2, 0])
    query_time = torch.tensor([[2.0, 1.0, 3.0]])
    model = _model()

    logits = model(
        _batch(), _targets(), _candidates(), target_features=_target_features(), query_time_s=query_time
    )
    permuted = model(
        _batch(),
        _targets()[:, target_order],
        _candidates()[:, candidate_order],
        target_features=_target_features()[:, target_order],
        query_time_s=query_time[:, candidate_order],
    )

    assert torch.allclose(permuted, logits[:, target_order][:, :, candidate_order], atol=1e-6)


def test_target_and_candidate_subset_consistency() -> None:
    """Removing unrelated target/candidate queries must not change retained scores."""

    target_index = torch.tensor([0, 2])
    candidate_index = torch.tensor([2, 0])
    query_time = torch.tensor([[2.0, 1.0, 3.0]])
    model = _model()

    logits = model(
        _batch(), _targets(), _candidates(), target_features=_target_features(), query_time_s=query_time
    )
    subset = model(
        _batch(),
        _targets()[:, target_index],
        _candidates()[:, candidate_index],
        target_features=_target_features()[:, target_index],
        query_time_s=query_time[:, candidate_index],
    )

    expected = logits[:, target_index][:, :, candidate_index]
    assert torch.allclose(subset, expected, atol=1e-6)


def test_global_se3_invariance() -> None:
    """A shared world-frame change must not alter scalar RRI logits."""

    fields = _batch()
    model = _model()
    transformed_fields = TemporalFieldBatch(
        features=fields.features,
        t_world_field=_global_transform(fields.t_world_field),
        time_s=fields.time_s,
        valid=fields.valid,
    )

    logits = model(fields, _targets(), _candidates(), target_features=_target_features())
    transformed = model(
        transformed_fields,
        _global_transform(_targets()),
        _global_transform(_candidates()),
        target_features=_target_features(),
    )

    assert torch.allclose(transformed, logits, atol=1e-5)


def test_field_order_invariance_and_masking() -> None:
    """Tile storage order and padded tile contents must not change predictions."""

    fields = _batch()
    order = torch.tensor([2, 0, 1])
    reordered = TemporalFieldBatch(
        features=fields.features[:, order],
        t_world_field=fields.t_world_field[:, order],
        time_s=fields.time_s[:, order],
        valid=fields.valid[:, order],
    )
    padded = TemporalFieldBatch(
        features=torch.cat((fields.features, torch.full((1, 1, 2), 1.0e6)), dim=1),
        t_world_field=torch.cat((fields.t_world_field, _poses(torch.tensor([[[9.0, 9.0, 9.0]]]))), dim=1),
        time_s=torch.cat((fields.time_s, torch.tensor([[1.0e6]])), dim=1),
        valid=torch.tensor([[True, True, True, False]]),
    )
    model = _model()

    logits = model(fields, _targets(), _candidates(), target_features=_target_features())
    assert torch.allclose(
        model(reordered, _targets(), _candidates(), target_features=_target_features()), logits, atol=1e-6
    )
    assert torch.allclose(
        model(padded, _targets(), _candidates(), target_features=_target_features()), logits, atol=1e-6
    )


def test_time_origin_is_a_gauge_choice() -> None:
    """Shifting field and query timestamps together must not alter predictions."""

    fields = _batch()
    shifted = TemporalFieldBatch(
        features=fields.features,
        t_world_field=fields.t_world_field,
        time_s=fields.time_s + 100.0,
        valid=fields.valid,
    )
    query_time = torch.tensor([[1.0, 2.0, 3.0]])
    model = _model()

    assert torch.allclose(
        model(fields, _targets(), _candidates(), target_features=_target_features(), query_time_s=query_time),
        model(
            shifted,
            _targets(),
            _candidates(),
            target_features=_target_features(),
            query_time_s=query_time + 100.0,
        ),
        atol=1e-6,
    )


def test_candidate_query_time_masks_future_fields() -> None:
    """Each candidate query must ignore EFM predictions made after its query time."""

    fields = _batch()
    changed_future = TemporalFieldBatch(
        features=fields.features.clone(),
        t_world_field=fields.t_world_field.clone(),
        time_s=fields.time_s,
        valid=fields.valid,
    )
    changed_future.features[:, 2] = 1.0e6
    changed_future.t_world_field[:, 2, :, 3] = 1.0e6
    query_time = torch.tensor([[1.0, 3.0, 1.0]])
    model = _model()

    logits = model(
        fields, _targets(), _candidates(), target_features=_target_features(), query_time_s=query_time
    )
    changed = model(
        changed_future,
        _targets(),
        _candidates(),
        target_features=_target_features(),
        query_time_s=query_time,
    )

    assert torch.allclose(changed[:, :, [0, 2]], logits[:, :, [0, 2]], atol=1e-6)


def test_all_masked_history_is_finite() -> None:
    """The pair query token should make cold-start inference well-defined."""

    fields = TemporalFieldBatch(
        features=torch.zeros((1, 2, 2)),
        t_world_field=_poses(torch.zeros((1, 2, 3))),
        time_s=torch.zeros((1, 2)),
        valid=torch.zeros((1, 2), dtype=torch.bool),
    )
    model = _model()

    logits = model(fields, _targets(), _candidates(), target_features=_target_features())

    assert torch.isfinite(logits).all()


def test_output_shape_finite_gradients_and_tied_refinement() -> None:
    """The compact model should train directly and own only one repeated block."""

    fields = _batch()
    fields.features.requires_grad_(True)
    model = _model(num_layers=3).train()

    logits = model(fields, _targets(), _candidates(), target_features=_target_features())
    logits.square().mean().backward()

    refiners = [module for module in model.modules() if isinstance(module, nn.TransformerEncoderLayer)]
    assert logits.shape == (1, 3, 3, 4)
    assert len(refiners) == 1
    assert fields.features.grad is not None
    assert torch.isfinite(fields.features.grad).all()


def test_vin_batch_adapter_consumes_stored_temporal_fields() -> None:
    """The actual training-batch seam should route history and candidates."""

    class CandidatePoses:
        matrix3x4 = _candidates()

    class Batch:
        temporal_fields = _batch()
        candidate_poses_world_cam = CandidatePoses()

    model = _model()

    direct = model(_batch(), _targets(), _candidates(), target_features=_target_features())
    adapted = model.forward_vin_batch(Batch(), _targets(), _target_features())  # type: ignore[arg-type]

    assert torch.equal(adapted, direct)


def test_config_derives_exact_feature_dimension_from_manifest() -> None:
    config = TemporalFieldTransformerConfig.from_manifest(
        {"backbone_history_feature_dim": 64},
        d_model=16,
        num_heads=4,
        num_classes=5,
    )

    assert config.field_feature_dim == 64


def test_target_features_condition_only_their_own_query_rows() -> None:
    model = _model()
    changed_features = _target_features().clone()
    changed_features[:, 1] += 10.0

    baseline = model(_batch(), _targets(), _candidates(), target_features=_target_features())
    changed = model(_batch(), _targets(), _candidates(), target_features=changed_features)

    assert torch.equal(changed[:, 0], baseline[:, 0])
    assert not torch.equal(changed[:, 1], baseline[:, 1])
    assert torch.equal(changed[:, 2], baseline[:, 2])


def test_batch_adapter_applies_hard_pair_mask_and_hierarchical_loss() -> None:
    class CandidatePoses:
        matrix3x4 = _candidates()

    class Batch:
        temporal_fields = _batch()
        candidate_poses_world_cam = CandidatePoses()

    pair_valid = torch.tensor([[[True, False, True], [False, False, True], [True, True, True]]])
    model = _model()
    logits = model.forward_vin_batch(  # type: ignore[arg-type]
        Batch(),
        _targets(),
        _target_features(),
        pair_valid=pair_valid,
    )
    labels = torch.zeros(pair_valid.shape, dtype=torch.long)
    loss = hierarchical_temporal_coral_loss(logits, labels, pair_valid, num_classes=5)

    assert torch.equal(logits[~pair_valid], torch.zeros_like(logits[~pair_valid]))
    assert torch.isfinite(loss)


def test_grouped_rollout_adapter_rejects_wrong_source_snippet() -> None:
    class Batch:
        temporal_fields = _batch()
        scene_id = "scene"
        snippet_id = "history-snippet"

    class Rollout:
        scene_id = "scene"
        snippet_id = "label-snippet"
        targets_world_query = _targets()
        target_features = _target_features()
        candidates_world_camera = _candidates()
        pair_valid = torch.ones((1, 3, 3), dtype=torch.bool)

    with pytest.raises(ValueError, match="same single source snippet"):
        _model().forward_grouped_rollout(Batch(), Rollout())  # type: ignore[arg-type]


def test_grouped_rollout_adapter_rejects_wrong_split_context() -> None:
    class Batch:
        temporal_fields = _batch()
        scene_id = "scene"
        snippet_id = "history-snippet"
        split = "train"

    class Rollout:
        scene_id = "scene"
        snippet_id = "history-snippet"
        split = "val"
        targets_world_query = _targets()
        target_features = _target_features()
        candidates_world_camera = _candidates()
        pair_valid = torch.ones((1, 3, 3), dtype=torch.bool)

    with pytest.raises(ValueError, match="same single source snippet"):
        _model().forward_grouped_rollout(Batch(), Rollout())  # type: ignore[arg-type]


def test_hierarchical_loss_ignores_scenes_without_labels() -> None:
    logits = torch.randn((1, 2, 3, 4))
    labels = torch.zeros((1, 2, 3), dtype=torch.long)
    valid = torch.tensor([[[True, False, True], [False, False, True]]])
    expected = hierarchical_temporal_coral_loss(logits, labels, valid, num_classes=5)

    batched_logits = torch.cat((logits, torch.full_like(logits, 1.0e6)))
    batched_labels = torch.cat((labels, torch.full_like(labels, 4)))
    batched_valid = torch.cat((valid, torch.zeros_like(valid)))
    actual = hierarchical_temporal_coral_loss(batched_logits, batched_labels, batched_valid, num_classes=5)

    assert torch.equal(actual, expected)
