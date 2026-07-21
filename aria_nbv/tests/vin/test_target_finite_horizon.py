"""Behavioral tests for the finite-horizon candidate-query scorer."""

# ruff: noqa: S101

from __future__ import annotations

from dataclasses import replace

import torch

from aria_nbv.lightning.qh_data import QhActorInputs
from aria_nbv.vin.models.target_finite_horizon import MultiStepCandidateScorerConfig


def _actor() -> QhActorInputs:
    return QhActorInputs(
        vin_blocks=(
            ("vin.points_world", torch.arange(48, dtype=torch.float32).reshape(2, 8, 3)),
            ("vin.lengths", torch.tensor([[6], [8]], dtype=torch.int64)),
            ("vin.t_world_rig", torch.arange(72, dtype=torch.float32).reshape(2, 3, 12)),
        ),
        vin_block_availability=(
            ("vin.points_world", torch.ones(2, dtype=torch.bool)),
            ("vin.lengths", torch.ones(2, dtype=torch.bool)),
            ("vin.t_world_rig", torch.ones(2, dtype=torch.bool)),
        ),
        target_center_world=torch.tensor([[1.0, 2.0, 3.0], [2.0, 3.0, 4.0]]),
        target_extents=torch.tensor([[0.4, 0.5, 0.6], [0.6, 0.7, 0.8]]),
        target_pose_world_object=torch.arange(24, dtype=torch.float32).reshape(2, 12),
        target_relative_pose_reference_object=torch.arange(24, 48, dtype=torch.float32).reshape(2, 12),
        target_sem_id=torch.tensor([4, 5]),
        target_inst_id=torch.tensor([44, 55]),
        candidate_row_id=torch.tensor([[10, 11, 12], [20, 21, -1]]),
        candidate_pose_world_cam=torch.arange(72, dtype=torch.float32).reshape(2, 3, 12),
        candidate_pose_relative_root=torch.arange(72, 144, dtype=torch.float32).reshape(2, 3, 12),
        candidate_position_id=torch.tensor([[0, 1, 2], [2, 3, -1]]),
        actor_action_mask=torch.tensor([[True, True, False], [True, True, False]]),
        history_candidate_row_id=torch.tensor([[7, 8], [9, -1]]),
        history_pose_world_cam=torch.arange(48, dtype=torch.float32).reshape(2, 2, 12),
        history_pose_relative_root=torch.arange(48, 96, dtype=torch.float32).reshape(2, 2, 12),
        history_position_id=torch.tensor([[0, 1], [2, -1]]),
        history_mask=torch.tensor([[True, True], [True, False]]),
        remaining_budget=torch.tensor([2, 1]),
    )


def _scorer():
    torch.manual_seed(7)
    scorer = MultiStepCandidateScorerConfig(candidate_token_dim=16, num_heads=4, dropout=0.0).setup_target()
    return scorer.eval()


def test_scorer_returns_finite_candidate_aligned_values() -> None:
    values = _scorer()(_actor())

    assert values.shape == (2, 3)
    assert values.dtype == torch.float32
    assert torch.isfinite(values).all()


def test_scorer_is_candidate_permutation_equivariant_and_row_id_independent() -> None:
    scorer = _scorer()
    actor = _actor()
    permutation = torch.tensor([2, 0, 1])
    permuted = replace(
        actor,
        candidate_row_id=actor.candidate_row_id[:, permutation] + 1000,
        candidate_pose_world_cam=actor.candidate_pose_world_cam[:, permutation],
        candidate_pose_relative_root=actor.candidate_pose_relative_root[:, permutation],
        candidate_position_id=actor.candidate_position_id[:, permutation],
        actor_action_mask=actor.actor_action_mask[:, permutation],
    )

    expected = scorer(actor)[:, permutation]
    actual = scorer(permuted)

    assert torch.allclose(actual, expected, atol=1e-6)


def test_invalid_candidate_features_cannot_change_valid_scores() -> None:
    scorer = _scorer()
    actor = _actor()
    changed = replace(
        actor,
        candidate_pose_world_cam=actor.candidate_pose_world_cam.clone(),
        candidate_pose_relative_root=actor.candidate_pose_relative_root.clone(),
    )
    changed.candidate_pose_world_cam[:, 2] = 1e6
    changed.candidate_pose_relative_root[:, 2] = -1e6

    before = scorer(actor)
    after = scorer(changed)

    assert torch.allclose(after[:, :2], before[:, :2], atol=1e-6)


def test_optional_block_availability_cannot_change_scores() -> None:
    scorer = _scorer()
    actor = _actor()
    changed = replace(
        actor,
        vin_block_availability=(
            *actor.vin_block_availability,
            ("vin.trajectory.time_ns", torch.tensor([True, False])),
        ),
    )

    assert torch.allclose(scorer(changed), scorer(actor), atol=1e-6)


def test_target_actor_history_and_budget_each_condition_scores() -> None:
    scorer = _scorer()
    actor = _actor()
    baseline = scorer(actor)
    target = torch.full_like(actor.target_center_world, 1000)
    points = dict(actor.vin_blocks)["vin.points_world"].clone()
    points[:, :, 0] *= 2
    history = actor.history_pose_relative_root.clone()
    history[:, :, 0] += 3
    variants = (
        replace(actor, target_center_world=target),
        replace(
            actor,
            vin_blocks=tuple(
                (name, points if name == "vin.points_world" else value) for name, value in actor.vin_blocks
            ),
        ),
        replace(actor, history_pose_relative_root=history),
        replace(actor, remaining_budget=actor.remaining_budget + 1),
    )

    for variant in variants:
        assert not torch.allclose(scorer(variant), baseline)


def test_shared_candidate_head_receives_gradients() -> None:
    scorer = _scorer().train()
    scorer(_actor()).sum().backward()

    assert all(parameter.grad is not None for parameter in scorer.value_head.parameters())
