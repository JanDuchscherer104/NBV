"""Contracts for the production finite-horizon Q_H scorer."""

# ruff: noqa: S101

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest
import torch
from efm3d.aria.pose import PoseTW

from aria_nbv.data_handling.qh_data import QhActorTensors, collate_qh_chains
from aria_nbv.data_handling.qh_data.views import QhStaticContext
from aria_nbv.utils.fingerprints import stable_config_hash
from aria_nbv.vin.models.target_finite_horizon import (
    TargetFiniteHorizonScorer,
    TargetFiniteHorizonScorerConfig,
)
from aria_nbv.vin.modules.qh_history_encoders import (
    QhCausalTransformerHistoryEncoderConfig,
    QhMeanPoolHistoryEncoderConfig,
)
from aria_nbv.vin.modules.qh_state_fusion import (
    QhCrossAttentionStateFusionConfig,
    QhIndependentMlpStateFusionConfig,
)
from aria_nbv.vin.modules.qh_value_decoders import (
    QhCoralValueDecoderConfig,
    QhPredeclaredPhysicalCoralSupport,
)
from tests.data_handling.test_qh import _chain, _snippet


def _actor(*, steps: int = 3, width: int = 4) -> QhActorTensors:
    chain = _chain(steps=steps, width=width)
    context = QhStaticContext(
        vin_snippet=_snippet(steps),
        t_world_voxel=PoseTW(),
        voxel_extent=torch.tensor([-1.0, 1.0, -1.0, 1.0, -1.0, 1.0]),
        occ_pr=torch.linspace(0.1, 0.8, 8).reshape(1, 2, 2, 2),
        occ_input=torch.linspace(0.2, 0.9, 8).reshape(1, 2, 2, 2),
        free_input=torch.linspace(0.9, 0.2, 8).reshape(1, 2, 2, 2),
        counts=torch.arange(8, dtype=torch.int64).reshape(2, 2, 2),
        cent_pr=torch.linspace(0.3, 1.0, 8).reshape(1, 2, 2, 2),
        pts_world=torch.arange(24, dtype=torch.float32).reshape(8, 3) / 10.0,
        evl_presence=torch.ones(8, dtype=torch.bool),
    )
    chain = replace(chain, actor=replace(chain.actor, static_context=context))
    return collate_qh_chains([chain]).actor


def _scorer() -> TargetFiniteHorizonScorer:
    torch.manual_seed(11)
    scorer = TargetFiniteHorizonScorerConfig(
        hidden_dim=32,
        dropout=0.0,
        max_horizon=4,
    ).setup_target()
    scorer.eval()
    return scorer


def _coral_scorer() -> TargetFiniteHorizonScorer:
    """Return a deterministic scorer with a three-class ordinal value head."""

    torch.manual_seed(11)
    scorer = TargetFiniteHorizonScorerConfig(
        hidden_dim=32,
        dropout=0.0,
        max_horizon=4,
        value_decoder=QhCoralValueDecoderConfig(
            support=QhPredeclaredPhysicalCoralSupport.create(
                source_population_digest="population-v1",
                ordered_input_digest="physical-rule-inputs-v1",
                physical_rule="symmetric-root-gain-support-v1",
                bin_edges=(-0.5, 0.5),
                bin_values=(-1.0, 0.0, 1.0),
            ),
            preinit_bias=False,
        ),
    ).setup_target()
    scorer.eval()
    return scorer


def _ordered_history_scorer() -> TargetFiniteHorizonScorer:
    """Return a deterministic A1 scorer whose only new factor is H1 history."""

    torch.manual_seed(11)
    scorer = TargetFiniteHorizonScorerConfig(
        hidden_dim=32,
        dropout=0.0,
        max_horizon=4,
        history_encoder=QhCausalTransformerHistoryEncoderConfig(attention_heads=4),
    ).setup_target()
    scorer.eval()
    return scorer


def test_qh_scorer_output_matches_actor_candidate_axes_and_is_deterministic() -> None:
    actor = _actor()
    scorer = _scorer()

    first = scorer(actor)
    second = scorer(actor)

    assert first.conditional_q.shape == actor.action_mask.shape == (1, 3, 4)
    assert first.conditional_q.dtype == torch.float32
    assert torch.equal(first.conditional_q, second.conditional_q)
    assert torch.isfinite(first.conditional_q[actor.action_mask]).all()


def test_qh_scorer_returns_conditional_q_and_feasibility_logits() -> None:
    actor = _actor()
    output = _scorer()(actor)

    assert hasattr(output, "conditional_q")
    assert hasattr(output, "feasibility_logits")
    assert output.conditional_q.shape == actor.action_mask.shape
    assert output.feasibility_logits.shape == actor.action_mask.shape
    assert output.conditional_q.dtype is torch.float32
    assert output.feasibility_logits.dtype is torch.float32
    assert output.value_auxiliary is None


def test_qh_coral_scorer_preserves_scalar_contract_and_attaches_thresholds() -> None:
    actor = _actor()
    output = _coral_scorer()(actor)
    materialized = actor.candidate_mask & actor.step_mask.unsqueeze(-1)

    assert output.value_auxiliary is not None
    assert output.conditional_q.shape == actor.action_mask.shape
    assert output.value_auxiliary.logits.shape == (*actor.action_mask.shape, 2)
    assert output.value_auxiliary.logits.dtype is torch.float32
    assert output.value_auxiliary.bin_edges.tolist() == [-0.5, 0.5]
    assert output.value_auxiliary.bin_values.tolist() == [-1.0, 0.0, 1.0]
    assert torch.isfinite(output.value_auxiliary.logits[materialized]).all()
    assert torch.equal(
        output.value_auxiliary.logits[~materialized],
        torch.zeros_like(output.value_auxiliary.logits[~materialized]),
    )
    assert bool((output.conditional_q[materialized] >= -1.0).all())
    assert bool((output.conditional_q[materialized] <= 1.0).all())


def test_qh_scorer_explicit_remaining_horizon_matches_default_query() -> None:
    actor = _actor()
    scorer = _scorer()
    explicit = actor.horizon_remaining

    default = scorer(actor)
    queried = scorer(actor, requested_horizon=explicit)

    assert torch.equal(default.conditional_q, queried.conditional_q)
    assert torch.equal(default.feasibility_logits, queried.feasibility_logits)


def test_qh_scorer_accepts_bounded_off_diagonal_horizon_query() -> None:
    actor = _actor()
    scorer = _scorer()
    shorter = actor.horizon_remaining.clone()
    shorter[:, 0] = 1

    output = scorer(actor, requested_horizon=shorter)

    assert output.conditional_q.shape == actor.action_mask.shape
    assert torch.isfinite(output.conditional_q[actor.candidate_mask]).all()
    assert torch.equal(output.feasibility_logits, scorer(actor).feasibility_logits)


@pytest.mark.parametrize("invalid_horizon", [-1, 0, 5])
def test_qh_scorer_rejects_requested_horizon_outside_supported_range(invalid_horizon: int) -> None:
    actor = _actor()
    with pytest.raises(ValueError, match="horizon"):
        _scorer()(actor, requested_horizon=torch.full(actor.action_mask.shape[:2], invalid_horizon))


def test_qh_scorer_rejects_requested_horizon_above_factual_budget_without_clamping() -> None:
    actor = _actor()
    horizon = actor.horizon_remaining.clone()
    horizon[:, -1] = 2

    with pytest.raises(ValueError, match="factual horizon_remaining"):
        _scorer()(actor, requested_horizon=horizon)


def test_qh_scorer_rejects_requested_horizon_shape_and_dtype_drift() -> None:
    actor = _actor()
    scorer = _scorer()

    with pytest.raises(ValueError, match="shape"):
        scorer(actor, requested_horizon=actor.horizon_remaining.unsqueeze(-1))
    with pytest.raises(ValueError, match="int64"):
        scorer(actor, requested_horizon=actor.horizon_remaining.float())


def test_qh_scorer_raw_outputs_are_independent_of_action_mask() -> None:
    actor = _actor()
    scorer = _scorer()
    changed_mask = actor.action_mask.clone()
    changed_mask[..., 0] = ~changed_mask[..., 0]

    baseline = scorer(actor)
    changed = scorer(replace(actor, action_mask=changed_mask))

    assert torch.equal(changed.conditional_q, baseline.conditional_q)
    assert torch.equal(changed.feasibility_logits, baseline.feasibility_logits)


def test_qh_coral_thresholds_are_independent_of_action_mask() -> None:
    actor = _actor()
    scorer = _coral_scorer()
    changed_mask = actor.action_mask.clone()
    changed_mask[..., 0] = ~changed_mask[..., 0]

    baseline = scorer(actor)
    changed = scorer(replace(actor, action_mask=changed_mask))

    assert baseline.value_auxiliary is not None
    assert changed.value_auxiliary is not None
    assert torch.equal(changed.conditional_q, baseline.conditional_q)
    assert torch.equal(changed.value_auxiliary.logits, baseline.value_auxiliary.logits)


def test_qh_scorer_materialized_candidate_rows_are_finite_when_not_action_selectable() -> None:
    actor = _actor()
    action_mask = actor.action_mask.clone()
    action_mask[..., 0] = False
    output = _scorer()(replace(actor, action_mask=action_mask))

    materialized = actor.candidate_mask & actor.step_mask.unsqueeze(-1)
    assert torch.isfinite(output.conditional_q[materialized]).all()
    assert torch.isfinite(output.feasibility_logits[materialized]).all()


def test_qh_scorer_materialized_invalid_candidate_is_isolated_from_other_rows() -> None:
    actor = _actor()
    scorer = _scorer()
    action_mask = actor.action_mask.clone()
    action_mask[..., -1] = False
    invalid = replace(actor, action_mask=action_mask)
    baseline = scorer(invalid)
    poses = actor.candidate_pose_relative_root.tensor().clone()
    poses[..., -1, 9:12] += 1000.0
    changed = scorer(replace(invalid, candidate_pose_relative_root=PoseTW(poses)))

    assert torch.allclose(changed.conditional_q[..., :-1], baseline.conditional_q[..., :-1], atol=1e-6, rtol=1e-6)
    assert torch.allclose(
        changed.feasibility_logits[..., :-1],
        baseline.feasibility_logits[..., :-1],
        atol=1e-6,
        rtol=1e-6,
    )


def test_qh_scorer_candidate_permutation_preserves_both_output_heads() -> None:
    actor = _actor()
    scorer = _scorer()
    permutation = torch.tensor([2, 0, 3, 1])
    permuted = replace(
        actor,
        candidate_pose_relative_root=PoseTW(actor.candidate_pose_relative_root.tensor()[:, :, permutation]),
        candidate_mask=actor.candidate_mask[:, :, permutation],
        action_mask=actor.action_mask[:, :, permutation],
    )

    expected = scorer(actor)
    actual = scorer(permuted)

    assert torch.allclose(actual.conditional_q, expected.conditional_q[:, :, permutation], atol=1e-6, rtol=1e-6)
    assert torch.allclose(
        actual.feasibility_logits,
        expected.feasibility_logits[:, :, permutation],
        atol=1e-6,
        rtol=1e-6,
    )


def test_qh_ordered_history_preserves_candidate_permutation_equivariance() -> None:
    actor = _actor(steps=4)
    scorer = _ordered_history_scorer()
    permutation = torch.tensor([2, 0, 3, 1])
    permuted = replace(
        actor,
        candidate_pose_relative_root=PoseTW(actor.candidate_pose_relative_root.tensor()[:, :, permutation]),
        candidate_mask=actor.candidate_mask[:, :, permutation],
        action_mask=actor.action_mask[:, :, permutation],
    )

    expected = scorer(actor)
    actual = scorer(permuted)

    assert torch.allclose(actual.conditional_q, expected.conditional_q[:, :, permutation], atol=1e-6, rtol=1e-6)
    assert torch.allclose(
        actual.feasibility_logits,
        expected.feasibility_logits[:, :, permutation],
        atol=1e-6,
        rtol=1e-6,
    )


def test_qh_coral_scorer_candidate_permutation_preserves_thresholds() -> None:
    actor = _actor()
    scorer = _coral_scorer()
    permutation = torch.tensor([2, 0, 3, 1])
    permuted = replace(
        actor,
        candidate_pose_relative_root=PoseTW(actor.candidate_pose_relative_root.tensor()[:, :, permutation]),
        candidate_mask=actor.candidate_mask[:, :, permutation],
        action_mask=actor.action_mask[:, :, permutation],
    )

    expected = scorer(actor)
    actual = scorer(permuted)

    assert expected.value_auxiliary is not None
    assert actual.value_auxiliary is not None
    assert torch.allclose(
        actual.value_auxiliary.logits,
        expected.value_auxiliary.logits[:, :, permutation],
        atol=1e-6,
        rtol=1e-6,
    )


def test_qh_scorer_duplicate_candidate_has_identical_independent_outputs() -> None:
    actor = _actor()
    scorer = _scorer()
    poses = actor.candidate_pose_relative_root.tensor().clone()
    poses[..., 1, :] = poses[..., 0, :]

    output = scorer(replace(actor, candidate_pose_relative_root=PoseTW(poses)))

    assert torch.equal(output.conditional_q[..., 0], output.conditional_q[..., 1])
    assert torch.equal(output.feasibility_logits[..., 0], output.feasibility_logits[..., 1])


def test_qh_scorer_is_candidate_permutation_equivariant() -> None:
    actor = _actor()
    scorer = _scorer()
    permutation = torch.tensor([2, 0, 3, 1])
    permuted = replace(
        actor,
        candidate_pose_relative_root=PoseTW(actor.candidate_pose_relative_root.tensor()[:, :, permutation]),
        candidate_mask=actor.candidate_mask[:, :, permutation],
        action_mask=actor.action_mask[:, :, permutation],
    )

    expected = scorer(actor).conditional_q[:, :, permutation]
    actual = scorer(permuted).conditional_q

    assert torch.allclose(actual, expected, atol=1e-6, rtol=1e-6)


def test_qh_a0_identical_feature_control_preserves_public_candidate_invariants() -> None:
    actor = _actor()
    torch.manual_seed(11)
    scorer = TargetFiniteHorizonScorerConfig(
        hidden_dim=32,
        dropout=0.0,
        max_horizon=4,
        state_fusion=QhIndependentMlpStateFusionConfig(),
    ).setup_target()
    scorer.eval()
    permutation = torch.tensor([2, 0, 3, 1])
    permuted = replace(
        actor,
        candidate_pose_relative_root=PoseTW(actor.candidate_pose_relative_root.tensor()[:, :, permutation]),
        candidate_mask=actor.candidate_mask[:, :, permutation],
        action_mask=actor.action_mask[:, :, permutation],
    )
    changed_action_mask = actor.action_mask.clone()
    changed_action_mask[..., 0] = ~changed_action_mask[..., 0]

    expected = scorer(actor)
    actual = scorer(permuted)
    mask_changed = scorer(replace(actor, action_mask=changed_action_mask))
    candidate_mask = actor.candidate_mask.clone()
    candidate_mask[..., -1] = False
    valid_mask = actor.action_mask.clone()
    valid_mask[..., -1] = False
    masked = replace(actor, candidate_mask=candidate_mask, action_mask=valid_mask)
    mutated_pose = actor.candidate_pose_relative_root.tensor().clone()
    mutated_pose[..., -1, :] = 1.0e6
    invalid_changed = scorer(replace(masked, candidate_pose_relative_root=PoseTW(mutated_pose)))
    invalid_baseline = scorer(masked)

    assert torch.allclose(actual.conditional_q, expected.conditional_q[:, :, permutation], atol=1e-6, rtol=1e-6)
    assert torch.allclose(
        actual.feasibility_logits,
        expected.feasibility_logits[:, :, permutation],
        atol=1e-6,
        rtol=1e-6,
    )
    assert torch.equal(mask_changed.conditional_q, expected.conditional_q)
    assert torch.equal(mask_changed.feasibility_logits, expected.feasibility_logits)
    assert torch.allclose(
        invalid_changed.conditional_q[candidate_mask],
        invalid_baseline.conditional_q[candidate_mask],
        atol=1e-6,
        rtol=1e-6,
    )
    assert torch.allclose(
        invalid_changed.feasibility_logits[candidate_mask],
        invalid_baseline.feasibility_logits[candidate_mask],
        atol=1e-6,
        rtol=1e-6,
    )
    assert torch.equal(
        invalid_changed.conditional_q[~candidate_mask],
        torch.zeros_like(invalid_changed.conditional_q[~candidate_mask]),
    )
    assert torch.equal(
        invalid_changed.feasibility_logits[~candidate_mask],
        torch.zeros_like(invalid_changed.feasibility_logits[~candidate_mask]),
    )


def test_qh_scorer_invalid_rows_are_isolated() -> None:
    actor = _actor()
    scorer = _scorer()
    action_mask = actor.action_mask.clone()
    action_mask[..., -1] = False
    candidate_mask = actor.candidate_mask.clone()
    candidate_mask[..., -1] = False
    masked = replace(actor, action_mask=action_mask, candidate_mask=candidate_mask)
    mutated_pose = actor.candidate_pose_relative_root.tensor().clone()
    mutated_pose[..., -1, :] = 1.0e6
    mutated = replace(masked, candidate_pose_relative_root=PoseTW(mutated_pose))

    baseline = scorer(masked)
    changed = scorer(mutated)

    assert torch.allclose(
        changed.conditional_q[candidate_mask],
        baseline.conditional_q[candidate_mask],
        atol=1e-6,
        rtol=1e-6,
    )
    assert torch.equal(
        changed.conditional_q[~candidate_mask],
        torch.zeros_like(changed.conditional_q[~candidate_mask]),
    )


def test_qh_scorer_sanitizes_inactive_nonfinite_pose_rows() -> None:
    actor = _actor()
    scorer = _scorer()
    baseline = scorer(actor)
    candidate = actor.candidate_pose_relative_root.tensor().clone()
    candidate[~actor.candidate_mask] = float("nan")
    history = actor.history_pose_relative_root.tensor().clone()
    history[~actor.history_mask] = float("inf")

    actual = scorer(
        replace(
            actor,
            candidate_pose_relative_root=PoseTW(candidate),
            history_pose_relative_root=PoseTW(history),
        )
    )
    assert torch.allclose(actual.conditional_q, baseline.conditional_q, atol=1e-6, rtol=1e-6)
    assert torch.allclose(actual.feasibility_logits, baseline.feasibility_logits, atol=1e-6, rtol=1e-6)
    assert torch.isfinite(actual.conditional_q).all()
    assert torch.isfinite(actual.feasibility_logits).all()


def test_qh_scorer_rejects_nonfinite_active_pose_rows() -> None:
    actor = _actor()
    scorer = _scorer()
    candidate = actor.candidate_pose_relative_root.tensor().clone()
    first = tuple(int(value) for value in torch.nonzero(actor.action_mask, as_tuple=False)[0])
    candidate[first] = float("nan")
    with pytest.raises(ValueError, match="active candidate poses"):
        scorer(replace(actor, candidate_pose_relative_root=PoseTW(candidate)))

    target = actor.target_pose_relative_root.tensor().clone()
    target[..., 0] = float("inf")
    with pytest.raises(ValueError, match="active target poses"):
        scorer(replace(actor, target_pose_relative_root=PoseTW(target)))

    root = actor.root_pose_world.tensor().clone()
    root[..., 0] = float("nan")
    with pytest.raises(ValueError, match="active root poses"):
        scorer(replace(actor, root_pose_world=PoseTW(root)))

    extents = actor.target_extents.clone()
    extents[..., 0] = float("inf")
    with pytest.raises(ValueError, match="active target extents"):
        scorer(replace(actor, target_extents=extents))


def test_qh_scene_summary_is_root_frame_invariant_and_tracks_raw_support() -> None:
    actor = _actor()
    scorer = _scorer()
    points = actor.vin_snippet.points_world.clone()
    root = actor.root_pose_world.tensor().clone()
    root[0, -3:] = torch.tensor([2.0, -1.0, 0.5])
    shifted = replace(
        actor,
        root_pose_world=PoseTW(root),
        vin_snippet=replace(actor.vin_snippet, points_world=points + root[:, -3:]),
    )
    assert torch.allclose(scorer._scene_summary(actor), scorer._scene_summary(shifted))

    empty = replace(actor, vin_snippet=replace(actor.vin_snippet, lengths=torch.tensor([0])))
    zero = replace(actor, vin_snippet=replace(actor.vin_snippet, points_world=torch.zeros_like(points)))
    empty_summary = scorer._scene_summary(empty)
    zero_summary = scorer._scene_summary(zero)
    assert empty_summary[0, -2:].tolist() == [0.0, 0.0]
    assert zero_summary[0, -2:].tolist() == [1.0, 1.0]


def test_qh_scene_summary_rejects_out_of_range_point_lengths() -> None:
    actor = _actor()
    scorer = _scorer()
    invalid = replace(actor, vin_snippet=replace(actor.vin_snippet, lengths=torch.tensor([99])))
    with pytest.raises(ValueError, match=r"lengths must be in \[0,"):
        scorer._scene_summary(invalid)


def test_qh_candidate_relative_transforms_compose_in_the_declared_direction() -> None:
    actor = _actor()
    scorer = _scorer()
    batch_size, steps, width = actor.action_mask.shape
    rotation = torch.eye(3).expand(batch_size, steps, width, 3, 3).clone()
    candidate_translation = torch.zeros(batch_size, steps, width, 3)
    candidate_translation[:, 1, 0, 0] = 5.0
    candidates = PoseTW.from_Rt(rotation, candidate_translation)
    history_rotation = torch.eye(3).expand(batch_size, steps, steps, 3, 3).clone()
    history_translation = torch.zeros(batch_size, steps, steps, 3)
    history_translation[:, 1, 0, 0] = 2.0
    history = PoseTW.from_Rt(history_rotation, history_translation)
    target = PoseTW.from_Rt(torch.eye(3).expand(batch_size, 3, 3).clone(), torch.tensor([[9.0, 0.0, 0.0]]))
    actor = replace(
        actor,
        candidate_pose_relative_root=candidates,
        history_pose_relative_root=history,
        target_pose_relative_root=target,
    )

    current = scorer._current_pose_relative_root(actor, history)
    current_from_candidate = scorer._expand_pose(current.inverse(), width) @ candidates
    candidate_from_target = candidates.inverse() @ scorer._expand_pose(target, steps, width)

    assert torch.equal(current_from_candidate.t[0, 1, 0], torch.tensor([3.0, 0.0, 0.0]))
    assert torch.equal(candidate_from_target.t[0, 1, 0], torch.tensor([4.0, 0.0, 0.0]))


def test_qh_scorer_uses_target_history_and_budget_without_future_history() -> None:
    actor = _actor()
    scorer = _scorer()
    baseline = scorer(actor).conditional_q

    target = actor.target_extents.clone()
    target[:, 0] += 0.75
    assert not torch.allclose(scorer(replace(actor, target_extents=target)).conditional_q, baseline)

    history = actor.history_pose_relative_root.tensor().clone()
    history[:, 2, 0, :] += 0.25
    assert not torch.allclose(
        scorer(replace(actor, history_pose_relative_root=PoseTW(history))).conditional_q,
        baseline,
    )

    future_history = actor.history_pose_relative_root.tensor().clone()
    future_history[:, 0, 2, :] += 10_000.0
    assert torch.allclose(
        scorer(replace(actor, history_pose_relative_root=PoseTW(future_history))).conditional_q,
        baseline,
        atol=1e-6,
        rtol=1e-6,
    )

    budget = actor.horizon_remaining.clone()
    budget[:, 0] -= 1
    assert not torch.allclose(scorer(replace(actor, horizon_remaining=budget)).conditional_q, baseline)


def test_qh_feasibility_is_independent_of_target_budget_and_requested_horizon() -> None:
    actor = _actor()
    scorer = _scorer()
    baseline = scorer(actor).feasibility_logits
    target = actor.target_extents + 0.75
    budget = actor.horizon_remaining.clone()
    budget[:, 0] -= 1
    requested_horizon = budget.clone()
    requested_horizon[:, 0] = 1

    changed = scorer(
        replace(actor, target_extents=target, horizon_remaining=budget),
        requested_horizon=requested_horizon,
    ).feasibility_logits

    assert torch.equal(changed, baseline)


def test_qh_ordered_history_is_sensitive_only_to_noncurrent_prefix_order() -> None:
    actor = _actor(steps=4)
    history = actor.history_pose_relative_root.tensor().clone()
    history[:, 3, [0, 1]] = history[:, 3, [1, 0]]
    permuted = replace(actor, history_pose_relative_root=PoseTW(history))

    torch.manual_seed(11)
    mean_scorer = TargetFiniteHorizonScorerConfig(
        hidden_dim=32,
        dropout=0.0,
        max_horizon=4,
        history_encoder=QhMeanPoolHistoryEncoderConfig(),
    ).setup_target()
    mean_scorer.eval()
    ordered_scorer = _ordered_history_scorer()

    assert torch.allclose(
        mean_scorer(actor).conditional_q,
        mean_scorer(permuted).conditional_q,
        atol=1e-6,
        rtol=1e-6,
    )
    assert not torch.allclose(
        ordered_scorer(actor).conditional_q[:, 3],
        ordered_scorer(permuted).conditional_q[:, 3],
    )


def test_qh_scorer_rejects_incomplete_realized_history_prefix() -> None:
    actor = _actor(steps=4)
    history_mask = actor.history_mask.clone()
    history_mask[:, 3, 1] = False

    with pytest.raises(ValueError, match="complete strictly causal prefix"):
        _ordered_history_scorer()(replace(actor, history_mask=history_mask))


def test_qh_scorer_backward_updates_parameters_only() -> None:
    actor = _actor()
    scorer = _scorer()

    scorer(actor).conditional_q[actor.action_mask].sum().backward()

    assert any(parameter.grad is not None and bool(parameter.grad.abs().sum() > 0) for parameter in scorer.parameters())
    assert actor.candidate_pose_relative_root.tensor().grad is None
    assert actor.static_context is not None
    assert actor.static_context.occ_pr is not None
    assert actor.static_context.occ_pr.grad is None


def test_qh_scorer_config_is_factory_and_rejects_profile_mismatch() -> None:
    config = TargetFiniteHorizonScorerConfig(hidden_dim=32, max_horizon=4)

    assert config.model_dump()["horizon_query_semantics"] == "bounded_scalar_v1"
    assert config.target_type is TargetFiniteHorizonScorer
    assert isinstance(config.setup_target(), TargetFiniteHorizonScorer)

    actor = replace(_actor(), static_context=None)
    try:
        config.setup_target()(actor)
    except ValueError as error:
        assert "EVL" in str(error)
    else:  # pragma: no cover - assertion branch
        raise AssertionError("scorer accepted an actor without required EVL context")


@pytest.mark.parametrize(
    ("state_fusion", "history_encoder"),
    [
        (QhIndependentMlpStateFusionConfig(), None),
        (QhCrossAttentionStateFusionConfig(attention_heads=2), QhMeanPoolHistoryEncoderConfig()),
        (
            QhCrossAttentionStateFusionConfig(attention_heads=2),
            QhCausalTransformerHistoryEncoderConfig(attention_heads=2),
        ),
    ],
)
def test_qh_scorer_config_round_trips_discriminated_modules(state_fusion, history_encoder) -> None:
    config = TargetFiniteHorizonScorerConfig(
        hidden_dim=32,
        max_horizon=4,
        state_fusion=state_fusion,
        history_encoder=history_encoder,
    )

    restored = TargetFiniteHorizonScorerConfig.model_validate(config.model_dump_jsonable())

    assert restored == config
    assert type(restored.state_fusion) is type(state_fusion)
    assert type(restored.history_encoder) is type(history_encoder)


def test_qh_default_history_preserves_legacy_state_and_explicit_identity() -> None:
    default_config = TargetFiniteHorizonScorerConfig(hidden_dim=32, dropout=0.0, max_horizon=4)
    explicit_config = TargetFiniteHorizonScorerConfig(
        hidden_dim=32,
        dropout=0.0,
        max_horizon=4,
        history_encoder=QhMeanPoolHistoryEncoderConfig(),
    )
    assert "history_encoder" not in default_config.model_dump_jsonable()
    assert explicit_config.model_dump_jsonable()["history_encoder"]["kind"] == "mean_pool_v1"
    assert stable_config_hash(default_config) != stable_config_hash(explicit_config)

    torch.manual_seed(17)
    default = default_config.setup_target()
    torch.manual_seed(17)
    explicit = explicit_config.setup_target()
    assert default.state_dict().keys() == explicit.state_dict().keys()
    assert not any(key.startswith("history_encoder.") for key in default.state_dict())
    assert all(torch.equal(default.state_dict()[key], explicit.state_dict()[key]) for key in default.state_dict())
    actor = _actor(steps=4)
    default.eval()
    explicit.eval()
    assert torch.equal(default(actor).conditional_q, explicit(actor).conditional_q)


def test_qh_scorer_config_rejects_incompatible_attention_width() -> None:
    with pytest.raises(ValueError, match="divisible"):
        TargetFiniteHorizonScorerConfig(
            hidden_dim=31,
            state_fusion=QhCrossAttentionStateFusionConfig(attention_heads=4),
        )


def test_qh_scorer_module_has_no_oracle_or_supervision_dependency() -> None:
    path = Path(__file__).resolve().parents[2] / "aria_nbv" / "vin" / "models" / "target_finite_horizon.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module is not None}
    assert not any("oracle" in module for module in imports)
    assert "QhSupervision" not in path.read_text(encoding="utf-8")
