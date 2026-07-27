"""Behavioral tests for the finite-horizon candidate-query scorer."""

# ruff: noqa: S101

from __future__ import annotations

import inspect
import math
from dataclasses import dataclass, replace

import pytest
import torch
from efm3d.aria.pose import PoseTW

import aria_nbv.vin.models.target_finite_horizon as target_finite_horizon
from aria_nbv.data_handling.raw.views import VinSnippetView
from aria_nbv.vin.encoders.shell_descriptor import encode_shell_pose_descriptor
from aria_nbv.vin.models.target_finite_horizon import MultiStepCandidateScorerConfig


@dataclass(frozen=True)
class _ScorerActor:
    """Minimal structural actor carrier required by the scorer's public seam."""

    vin_snippet: VinSnippetView
    root_pose_world: torch.Tensor
    target_extents: torch.Tensor
    target_pose_world_object: torch.Tensor
    candidate_row_id: torch.Tensor
    candidate_pose_relative_root: torch.Tensor
    candidate_position_id: torch.Tensor
    actor_action_mask: torch.Tensor
    history_candidate_row_id: torch.Tensor
    history_pose_relative_root: torch.Tensor
    history_position_id: torch.Tensor
    history_mask: torch.Tensor
    remaining_budget: torch.Tensor


def _poses(translations: torch.Tensor) -> torch.Tensor:
    """Build identity-rotation ``T_parent_child`` poses from metric centers."""

    rotations = torch.eye(3, dtype=translations.dtype).expand(*translations.shape[:-1], 3, 3)
    return torch.cat((rotations.flatten(start_dim=-2), translations), dim=-1)


def _actor() -> _ScorerActor:
    root_translation = torch.tensor([[1.0, -2.0, 0.5], [-3.0, 4.0, 1.5]])
    rig_translation = torch.stack(
        (
            torch.stack(
                (
                    root_translation[0] - torch.tensor([1.0, 0.0, 0.0]),
                    root_translation[0] + torch.tensor([0.0, 4.0, 0.0]),
                    root_translation[0] + torch.tensor([0.0, 5.0, 0.0]),
                )
            ),
            torch.stack(
                (
                    root_translation[1] - torch.tensor([0.0, 1.0, 0.0]),
                    root_translation[1] + torch.tensor([4.0, 0.0, 0.0]),
                    root_translation[1] + torch.tensor([5.0, 0.0, 0.0]),
                )
            ),
        )
    )
    points_root = torch.arange(48, dtype=torch.float32).reshape(2, 8, 3) / 10.0
    points_world = points_root + root_translation.unsqueeze(1)
    candidate_center_root = torch.tensor(
        [
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 2.0, 0.0]],
            [[0.0, 0.0, 1.0], [1.0, 1.0, 0.0], [0.0, 0.0, 0.0]],
        ]
    )
    history_center_root = torch.tensor(
        [
            [[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0]],
            [[0.0, 0.0, -1.0], [0.0, 0.0, 0.0]],
        ]
    )
    target_center_root = torch.tensor([[2.0, 0.0, 1.0], [0.0, 3.0, 1.0]])
    return _ScorerActor(
        vin_snippet=VinSnippetView(
            points_world=points_world,
            lengths=torch.tensor([[6], [8]], dtype=torch.int64),
            t_world_rig=PoseTW(_poses(rig_translation)),
        ),
        root_pose_world=_poses(root_translation),
        target_extents=torch.tensor([[0.4, 0.5, 0.6], [0.6, 0.7, 0.8]]),
        target_pose_world_object=_poses(target_center_root + root_translation),
        candidate_row_id=torch.tensor([[10, 11, 12], [20, 21, -1]]),
        candidate_pose_relative_root=_poses(candidate_center_root),
        candidate_position_id=torch.tensor([[0, 1, 2], [2, 3, -1]]),
        actor_action_mask=torch.tensor([[True, True, False], [True, True, False]]),
        history_candidate_row_id=torch.tensor([[7, 8], [9, -1]]),
        history_pose_relative_root=_poses(history_center_root),
        history_position_id=torch.tensor([[0, 1], [2, -1]]),
        history_mask=torch.tensor([[True, True], [True, False]]),
        remaining_budget=torch.tensor([2, 1]),
    )


def _scorer():
    torch.manual_seed(7)
    scorer = MultiStepCandidateScorerConfig(candidate_token_dim=16, num_heads=4, dropout=0.0).setup_target()
    return scorer.eval()


def _target_pose_relative_root(actor: _ScorerActor) -> torch.Tensor:
    return (PoseTW(actor.root_pose_world).inverse() @ PoseTW(actor.target_pose_world_object)).tensor()


def _left_multiply_world_pose(pose: torch.Tensor, rotation: torch.Tensor, translation: torch.Tensor) -> torch.Tensor:
    """Apply one world-frame rigid transform to flattened world-from poses."""

    pose_rotation = pose[..., :9].reshape(*pose.shape[:-1], 3, 3)
    pose_translation = pose[..., 9:12]
    transformed_rotation = torch.einsum("ij,...jk->...ik", rotation, pose_rotation)
    transformed_translation = torch.einsum("ij,...j->...i", rotation, pose_translation) + translation
    return torch.cat((transformed_rotation.flatten(start_dim=-2), transformed_translation), dim=-1)


def _apply_common_world_transform(actor: _ScorerActor) -> _ScorerActor:
    """Transform every world-frame actor fact while preserving local facts."""

    yaw = math.pi / 3
    rotation = torch.tensor(
        [
            [math.cos(yaw), -math.sin(yaw), 0.0],
            [math.sin(yaw), math.cos(yaw), 0.0],
            [0.0, 0.0, 1.0],
        ],
    )
    translation = torch.tensor([13.0, -7.0, 2.5])
    points = actor.vin_snippet.points_world
    xyz = torch.einsum("ij,...j->...i", rotation, points[..., :3]) + translation
    return replace(
        actor,
        vin_snippet=VinSnippetView(
            points_world=torch.cat((xyz, points[..., 3:]), dim=-1),
            lengths=actor.vin_snippet.lengths,
            t_world_rig=PoseTW(
                _left_multiply_world_pose(actor.vin_snippet.t_world_rig.tensor(), rotation, translation)
            ),
        ),
        root_pose_world=_left_multiply_world_pose(actor.root_pose_world, rotation, translation),
        target_pose_world_object=_left_multiply_world_pose(
            actor.target_pose_world_object,
            rotation,
            translation,
        ),
    )


def test_scorer_returns_finite_candidate_aligned_values() -> None:
    values = _scorer()(_actor())

    assert values.shape == (2, 3)
    assert values.dtype == torch.float32
    assert torch.isfinite(values).all()


def test_scorer_is_invariant_to_a_common_world_frame_transform() -> None:
    """Changing the arbitrary world gauge must not change learned values."""

    scorer = _scorer()
    actor = _actor()

    assert torch.allclose(scorer(_apply_common_world_transform(actor)), scorer(actor), atol=1e-5, rtol=1e-5)


def test_scorer_does_not_choose_a_rig_timestamp_as_the_reference_frame() -> None:
    """Changing audit-only rig history must not move learned scene features."""

    scorer = _scorer()
    actor = _actor()
    changed = replace(
        actor,
        vin_snippet=VinSnippetView(
            points_world=actor.vin_snippet.points_world,
            lengths=actor.vin_snippet.lengths,
            t_world_rig=PoseTW(_poses(torch.full((2, 3, 3), 10_000.0))),
        ),
    )

    assert torch.allclose(scorer(changed), scorer(actor), atol=1e-6)


def test_scorer_is_candidate_permutation_equivariant_and_row_id_independent() -> None:
    scorer = _scorer()
    actor = _actor()
    permutation = torch.tensor([2, 0, 1])
    permuted = replace(
        actor,
        candidate_row_id=actor.candidate_row_id[:, permutation] + 1000,
        candidate_pose_relative_root=actor.candidate_pose_relative_root[:, permutation],
        candidate_position_id=actor.candidate_position_id[:, permutation],
        actor_action_mask=actor.actor_action_mask[:, permutation],
    )

    expected = scorer(actor)[:, permutation]
    actual = scorer(permuted)

    assert torch.allclose(actual, expected, atol=1e-6)


def test_scorer_candidate_subset_preserves_retained_query_values() -> None:
    """Prototype 150e0d28: removed candidate queries cannot perturb retained values."""

    scorer = _scorer()
    actor = _actor()
    retained = torch.tensor([1, 0])
    subset = replace(
        actor,
        candidate_row_id=actor.candidate_row_id[:, retained],
        candidate_pose_relative_root=actor.candidate_pose_relative_root[:, retained],
        candidate_position_id=actor.candidate_position_id[:, retained],
        actor_action_mask=actor.actor_action_mask[:, retained],
    )

    assert torch.allclose(scorer(subset), scorer(actor)[:, retained], atol=1e-6)


def test_target_change_is_isolated_to_its_own_batched_query() -> None:
    """Prototype ef4aed9f: target-conditioned queries cannot cross batch items."""

    scorer = _scorer()
    actor = _actor()
    target_pose = actor.target_pose_world_object.clone()
    target_pose[1, 9:12] += torch.tensor([8.0, -3.0, 2.0])

    baseline = scorer(actor)
    changed = scorer(replace(actor, target_pose_world_object=target_pose))

    assert torch.equal(changed[0], baseline[0])


def test_invalid_candidate_features_cannot_change_valid_scores() -> None:
    scorer = _scorer()
    actor = _actor()
    changed = replace(
        actor,
        candidate_pose_relative_root=actor.candidate_pose_relative_root.clone(),
        candidate_position_id=actor.candidate_position_id.clone(),
    )
    changed.candidate_pose_relative_root[:, 2] = -1e6
    changed.candidate_position_id[:, 2] = 1_000_000

    before = scorer(actor)
    after = scorer(changed)

    assert torch.allclose(after[:, :2], before[:, :2], atol=1e-6)


def test_target_actor_history_and_budget_each_condition_scores() -> None:
    scorer = _scorer()
    actor = _actor()
    baseline = scorer(actor)
    target_pose = actor.target_pose_world_object.clone()
    target_pose[:, 9:12] += torch.tensor([4.0, -2.0, 1.0])
    points = actor.vin_snippet.points_world.clone()
    points[:, :, 0] *= 2
    history = actor.history_pose_relative_root.clone()
    history[:, :, 9] += 3
    variants = (
        replace(actor, target_pose_world_object=target_pose),
        replace(
            actor,
            vin_snippet=VinSnippetView(
                points_world=points,
                lengths=actor.vin_snippet.lengths,
                t_world_rig=actor.vin_snippet.t_world_rig,
            ),
        ),
        replace(actor, history_pose_relative_root=history),
        replace(actor, remaining_budget=actor.remaining_budget + 1),
    )

    for variant in variants:
        assert not torch.allclose(scorer(variant), baseline)


def test_candidate_target_relations_use_camera_from_root_and_positive_z() -> None:
    """Derived relations must bind transform direction, units, and optical axis."""

    actor = _actor()

    centers, ranges, optical_cosines = target_finite_horizon._candidate_target_relations(
        actor.candidate_pose_relative_root,
        _target_pose_relative_root(actor),
        actor.actor_action_mask,
    )

    assert centers.shape == (2, 3, 3)
    assert ranges.shape == (2, 3, 1)
    assert optical_cosines.shape == (2, 3, 1)
    assert torch.allclose(centers[0, 0], torch.tensor([2.0, 0.0, 1.0]))
    assert torch.allclose(ranges[0, 0], torch.tensor([math.sqrt(5.0)]))
    descriptor = encode_shell_pose_descriptor(PoseTW(actor.candidate_pose_relative_root))
    target_center_root = PoseTW(_target_pose_relative_root(actor)).t.unsqueeze(1)
    expected_cosines = (descriptor.forward_dir * (target_center_root - descriptor.center_m)).sum(
        dim=-1, keepdim=True
    ) / ranges.clamp_min(1e-8)
    assert torch.allclose(optical_cosines[0, 0], expected_cosines[0, 0])
    assert torch.allclose(centers[0, 1], torch.tensor([1.0, 0.0, 1.0]))
    assert torch.allclose(ranges[0, 1], torch.tensor([math.sqrt(2.0)]))
    assert torch.allclose(optical_cosines[0, 1], expected_cosines[0, 1])
    assert torch.equal(centers[:, 2], torch.zeros_like(centers[:, 2]))
    assert torch.equal(ranges[:, 2], torch.zeros_like(ranges[:, 2]))
    assert torch.equal(optical_cosines[:, 2], torch.zeros_like(optical_cosines[:, 2]))


def test_candidate_target_relations_invert_nonidentity_candidate_rotation() -> None:
    """A rotated camera must use ``T_cam_root``, not ``T_root_cam``."""

    actor = _actor()
    candidate_poses = actor.candidate_pose_relative_root.clone()
    candidate_poses[0, 0, :9] = torch.tensor(
        [
            [0.0, 0.0, 1.0],
            [0.0, 1.0, 0.0],
            [-1.0, 0.0, 0.0],
        ]
    ).flatten()

    centers, ranges, optical_cosines = target_finite_horizon._candidate_target_relations(
        candidate_poses,
        _target_pose_relative_root(actor),
        actor.actor_action_mask,
    )

    assert torch.allclose(centers[0, 0], torch.tensor([-1.0, 0.0, 2.0]))
    assert torch.allclose(ranges[0, 0], torch.tensor([math.sqrt(5.0)]))
    descriptor = encode_shell_pose_descriptor(PoseTW(candidate_poses))
    target_center_root = PoseTW(_target_pose_relative_root(actor)).t.unsqueeze(1)
    expected = (descriptor.forward_dir * (target_center_root - descriptor.center_m)).sum(
        dim=-1, keepdim=True
    ) / ranges.clamp_min(1e-8)
    assert torch.allclose(optical_cosines[0, 0], expected[0, 0])


def test_horizon_two_history_is_an_unordered_set() -> None:
    """The V0 H=2 baseline must be truthful about its set-valued history."""

    scorer = _scorer()
    actor = _actor()
    permutation = torch.tensor([1, 0])
    permuted = replace(
        actor,
        history_candidate_row_id=actor.history_candidate_row_id[:, permutation],
        history_pose_relative_root=actor.history_pose_relative_root[:, permutation],
        history_position_id=actor.history_position_id[:, permutation],
        history_mask=actor.history_mask[:, permutation],
    )

    assert torch.allclose(scorer(permuted), scorer(actor), atol=1e-6)


def test_horizon_two_scorer_docs_describe_history_as_unordered() -> None:
    """Public docs must not claim temporal order the model cannot represent."""

    documentation = inspect.getdoc(target_finite_horizon.MultiStepCandidateScorer) or ""

    assert "ordered" not in documentation.lower()
    assert "unordered" in documentation.lower() or "set-valued" in documentation.lower()


def test_valid_nonfinite_actor_feature_fails_closed() -> None:
    """A NaN under a true action mask must not be laundered into a score."""

    actor = _actor()
    candidate_pose = actor.candidate_pose_relative_root.clone()
    candidate_pose[0, 0, 0] = torch.nan

    with torch.no_grad(), pytest.raises(ValueError, match="finite|non-finite"):
        _scorer()(replace(actor, candidate_pose_relative_root=candidate_pose))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "candidate_pose_relative_root",
            _actor().candidate_pose_relative_root[..., :11],
            "candidate_pose_relative_root",
        ),
        ("history_pose_relative_root", _actor().history_pose_relative_root[..., :11], "history_pose_relative_root"),
    ],
)
def test_actor_pose_shape_validation_is_owned_by_relative_root_tensors(
    field: str,
    value: torch.Tensor,
    message: str,
) -> None:
    with torch.no_grad(), pytest.raises(ValueError, match=message):
        _scorer()(replace(_actor(), **{field: value}))


def test_nonfinite_scorer_output_fails_closed() -> None:
    """A numerically invalid learned output must not reach action selection."""

    scorer = _scorer()
    with torch.no_grad():
        scorer.value_head.weight.fill_(torch.inf)

    with torch.no_grad(), pytest.raises(ValueError, match="non-finite"):
        scorer(_actor())


def test_position_family_encoding_is_nominal_not_periodic() -> None:
    """Unordered family labels must not acquire circular numeric geometry."""

    source = inspect.getsource(target_finite_horizon)

    assert "_periodic_id" not in source
    assert "torch.sin" not in source
    assert "torch.cos" not in source
    assert _scorer().position_family_embedding.padding_idx == 6


def test_zero_dropout_scorer_selection_is_deterministic_in_train_mode() -> None:
    """The fitted-Q baseline's zero-dropout scorer has stable action selection."""

    torch.manual_seed(17)
    scorer = MultiStepCandidateScorerConfig(candidate_token_dim=16, num_heads=4, dropout=0.0).setup_target()
    scorer.train()
    actor = _actor()

    first = scorer(actor).argmax(dim=1)
    second = scorer(actor).argmax(dim=1)

    assert torch.equal(first, second)


def test_nonzero_dropout_is_rejected() -> None:
    """The deterministic fitted-Q baseline admits no stochastic scorer path."""

    with pytest.raises(ValueError, match="dropout"):
        MultiStepCandidateScorerConfig(dropout=0.1)


@pytest.mark.parametrize("horizon", [1, 3])
def test_non_v0_horizon_is_rejected(horizon: int) -> None:
    """The unordered-history baseline is admitted only for the frozen H=2 task."""

    with pytest.raises(ValueError, match="horizon"):
        MultiStepCandidateScorerConfig(horizon=horizon)


def test_shared_candidate_head_receives_gradients() -> None:
    scorer = _scorer().train()
    scorer(_actor()).sum().backward()

    assert all(parameter.grad is not None for parameter in scorer.value_head.parameters())
