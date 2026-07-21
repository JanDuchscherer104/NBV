"""Contracts for the factorized scene-bundle RRI baseline."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
import torch

from aria_nbv.learning import (
    ActorSceneBundle,
    FactorizedRriModel,
    FactorizedRriTransformer,
    SceneBundleSupervision,
    hierarchical_masked_loss,
)


def _poses(translations: torch.Tensor) -> torch.Tensor:
    batch, count, _ = translations.shape
    poses = torch.zeros((batch, count, 3, 4), dtype=translations.dtype)
    poses[..., :3] = torch.eye(3, dtype=translations.dtype)
    poses[..., 3] = translations
    return poses


def _bundle() -> ActorSceneBundle:
    return ActorSceneBundle(
        scene_features=torch.tensor([[[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]]]),
        t_world_scene=_poses(torch.tensor([[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0]]])),
        scene_time_s=torch.tensor([[0.0, 1.0, 2.0]]),
        scene_valid=torch.tensor([[True, True, True]]),
        target_features=torch.tensor([[[1.0, 0.5], [0.5, 1.0]]]),
        t_world_target=_poses(torch.tensor([[[0.5, 0.5, 0.0], [1.5, 0.5, 0.0]]])),
        target_valid=torch.tensor([[True, True]]),
        candidate_features=torch.tensor([[[1.0], [0.5], [0.0]]]),
        t_world_candidate=_poses(torch.tensor([[[0.0, 2.0, 0.0], [2.0, 0.0, 0.0], [2.0, 2.0, 0.0]]])),
        candidate_time_s=torch.tensor([[3.0, 3.5, 4.0]]),
        candidate_valid=torch.tensor([[True, True, True]]),
        pair_valid=torch.ones((1, 2, 3), dtype=torch.bool),
    )


def _model(*, refinement_steps: int = 1) -> FactorizedRriModel:
    torch.manual_seed(11)
    return FactorizedRriModel(
        scene_feature_dim=2,
        target_feature_dim=2,
        candidate_feature_dim=1,
        hidden_dim=16,
        scene_refinement_steps=refinement_steps,
    ).eval()


def _transformer(*, refinement_steps: int = 1) -> FactorizedRriTransformer:
    torch.manual_seed(11)
    return FactorizedRriTransformer(
        scene_feature_dim=2,
        target_feature_dim=2,
        candidate_feature_dim=1,
        hidden_dim=16,
        num_heads=4,
        scene_refinement_steps=refinement_steps,
    ).eval()


def _global_transform(poses: torch.Tensor) -> torch.Tensor:
    rotation = torch.tensor([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    translation = torch.tensor([7.0, -3.0, 2.0])
    transformed = poses.clone()
    transformed[..., :3] = rotation @ poses[..., :3]
    transformed[..., 3] = torch.einsum("ij,...j->...i", rotation, poses[..., 3]) + translation
    return transformed


def _replace(bundle: ActorSceneBundle, **updates: torch.Tensor) -> ActorSceneBundle:
    values = {name: getattr(bundle, name) for name in bundle.__dataclass_fields__}
    values.update(updates)
    return ActorSceneBundle(**values)


def test_bundle_validation_and_actor_oracle_firewall() -> None:
    """Actor inputs stay immutable, shaped, and free of oracle labels."""

    bundle = _bundle()
    supervision = SceneBundleSupervision(
        utility=torch.zeros((1, 2, 3)),
        label_valid=torch.ones((1, 2, 3), dtype=torch.bool),
    )

    assert not hasattr(bundle, "utility")
    assert supervision.utility.shape == bundle.pair_valid.shape
    with pytest.raises(FrozenInstanceError):
        bundle.scene_features = torch.zeros_like(bundle.scene_features)  # type: ignore[misc]
    with pytest.raises(ValueError, match="pair_valid"):
        _replace(bundle, pair_valid=torch.ones((1, 2, 2), dtype=torch.bool))
    with pytest.raises(TypeError, match="bool"):
        SceneBundleSupervision(torch.zeros((1, 2, 3)), torch.ones((1, 2, 3)))
    with pytest.raises(ValueError, match="invalid target or candidate"):
        _replace(bundle, candidate_valid=torch.tensor([[True, False, True]]))


def test_forward_is_finite_trainable_and_encodes_scene_once() -> None:
    """One scene encoding should serve the full target-candidate product."""

    bundle = _bundle()
    bundle.scene_features.requires_grad_(True)
    model = _model().train()
    calls: list[tuple[int, ...]] = []
    hook = model.scene_encoder.register_forward_hook(lambda _module, inputs, _output: calls.append(inputs[0].shape))

    prediction = model(bundle)
    prediction.square().mean().backward()
    hook.remove()

    assert prediction.shape == (1, 2, 3)
    assert torch.isfinite(prediction).all()
    assert calls == [(1, 3, 15)]
    assert bundle.scene_features.grad is not None
    assert torch.isfinite(bundle.scene_features.grad).all()


def test_shared_global_se3_transform_leaves_scalar_predictions_unchanged() -> None:
    """Only local relative transforms may influence scalar utility."""

    bundle = _bundle()
    transformed = _replace(
        bundle,
        t_world_scene=_global_transform(bundle.t_world_scene),
        t_world_target=_global_transform(bundle.t_world_target),
        t_world_candidate=_global_transform(bundle.t_world_candidate),
    )
    model = _model()

    assert torch.allclose(model(bundle), model(transformed), atol=1e-5)


def test_target_and_candidate_subsets_are_consistent() -> None:
    """Unrelated target or candidate rows must not change absolute scores."""

    bundle = _bundle()
    model = _model()
    full = model(bundle)
    target_index = torch.tensor([1])
    candidate_index = torch.tensor([2, 0])
    subset = _replace(
        bundle,
        target_features=bundle.target_features[:, target_index],
        t_world_target=bundle.t_world_target[:, target_index],
        target_valid=bundle.target_valid[:, target_index],
        candidate_features=bundle.candidate_features[:, candidate_index],
        t_world_candidate=bundle.t_world_candidate[:, candidate_index],
        candidate_time_s=bundle.candidate_time_s[:, candidate_index],
        candidate_valid=bundle.candidate_valid[:, candidate_index],
        pair_valid=bundle.pair_valid[:, target_index][:, :, candidate_index],
    )

    assert torch.allclose(model(subset), full[:, target_index][:, :, candidate_index], atol=1e-6)


def test_candidate_permutation_is_exactly_equivariant() -> None:
    """Candidate order may only permute the corresponding prediction axis."""

    bundle = _bundle()
    permutation = torch.tensor([2, 0, 1])
    permuted = _replace(
        bundle,
        candidate_features=bundle.candidate_features[:, permutation],
        t_world_candidate=bundle.t_world_candidate[:, permutation],
        candidate_time_s=bundle.candidate_time_s[:, permutation],
        candidate_valid=bundle.candidate_valid[:, permutation],
        pair_valid=bundle.pair_valid[:, :, permutation],
    )
    model = _model()

    assert torch.allclose(model(permuted), model(bundle)[:, :, permutation], atol=1e-6)


def test_scene_refinement_reuses_one_parameter_set() -> None:
    """Extra refinement steps reuse weights instead of deepening the model."""

    one_step = _model(refinement_steps=1)
    three_steps = _model(refinement_steps=3)

    assert sum(parameter.numel() for parameter in one_step.parameters()) == sum(
        parameter.numel() for parameter in three_steps.parameters()
    )
    assert one_step.scene_refinement_steps == 1


def test_factorized_transformer_preserves_absolute_utility_symmetries() -> None:
    """Pair cross-attention stays invariant, equivariant, and subset-consistent."""

    bundle = _bundle()
    model = _transformer()
    full = model(bundle)
    permutation = torch.tensor([2, 0, 1])
    permuted = _replace(
        bundle,
        candidate_features=bundle.candidate_features[:, permutation],
        t_world_candidate=bundle.t_world_candidate[:, permutation],
        candidate_time_s=bundle.candidate_time_s[:, permutation],
        candidate_valid=bundle.candidate_valid[:, permutation],
        pair_valid=bundle.pair_valid[:, :, permutation],
    )
    transformed = _replace(
        bundle,
        t_world_scene=_global_transform(bundle.t_world_scene),
        t_world_target=_global_transform(bundle.t_world_target),
        t_world_candidate=_global_transform(bundle.t_world_candidate),
    )
    subset = _replace(
        bundle,
        target_features=bundle.target_features[:, 1:2],
        t_world_target=bundle.t_world_target[:, 1:2],
        target_valid=bundle.target_valid[:, 1:2],
        candidate_features=bundle.candidate_features[:, 2:3],
        t_world_candidate=bundle.t_world_candidate[:, 2:3],
        candidate_time_s=bundle.candidate_time_s[:, 2:3],
        candidate_valid=bundle.candidate_valid[:, 2:3],
        pair_valid=bundle.pair_valid[:, 1:2, 2:3],
    )

    assert torch.allclose(model(permuted), full[:, :, permutation], atol=1e-6)
    assert torch.allclose(model(transformed), full, atol=1e-5)
    assert torch.allclose(model(subset), full[:, 1:2, 2:3], atol=1e-6)


def test_transformer_refinement_is_weight_tied() -> None:
    one_step = _transformer(refinement_steps=1)
    three_steps = _transformer(refinement_steps=3)

    assert sum(parameter.numel() for parameter in one_step.parameters()) == sum(
        parameter.numel() for parameter in three_steps.parameters()
    )


def test_hierarchical_masked_loss_reduces_candidate_target_scene() -> None:
    """Large scenes and targets must not dominate the batch objective."""

    prediction = torch.tensor(
        [
            [[1.0, 3.0, 999.0], [5.0, 999.0, 999.0]],
            [[2.0, 999.0, 999.0], [999.0, 999.0, 999.0]],
        ],
        requires_grad=True,
    )
    supervision = SceneBundleSupervision(
        utility=torch.zeros_like(prediction),
        label_valid=torch.tensor(
            [
                [[True, True, False], [True, False, False]],
                [[True, False, False], [False, False, False]],
            ]
        ),
    )
    pair_valid = torch.tensor(
        [
            [[True, True, False], [True, False, False]],
            [[True, False, False], [False, False, False]],
        ]
    )

    mse = hierarchical_masked_loss(prediction, supervision, pair_valid=pair_valid, loss="mse")
    mae = hierarchical_masked_loss(prediction, supervision, pair_valid=pair_valid, loss="mae")
    mse.backward()

    assert torch.allclose(mse, torch.tensor(9.5))
    assert torch.allclose(mae, torch.tensor(2.75))
    assert prediction.grad is not None
    assert prediction.grad[0, 0, 2] == 0.0


def test_loss_uses_both_actor_and_oracle_masks() -> None:
    """Neither actor-invalid pairs nor unavailable labels enter training."""

    prediction = torch.tensor([[[1.0, 1.0e6, 1.0e6]]])
    supervision = SceneBundleSupervision(
        utility=torch.zeros_like(prediction),
        label_valid=torch.tensor([[[True, True, False]]]),
    )
    pair_valid = torch.tensor([[[True, False, True]]])

    assert hierarchical_masked_loss(prediction, supervision, pair_valid=pair_valid) == 1.0
    with pytest.raises(ValueError, match="at least one"):
        hierarchical_masked_loss(prediction, supervision, pair_valid=torch.zeros_like(pair_valid))
