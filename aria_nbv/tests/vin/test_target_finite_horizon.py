"""Contracts for the production finite-horizon Q_H scorer."""

# ruff: noqa: S101

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import torch
from efm3d.aria.pose import PoseTW

from aria_nbv.data_handling.qh_data import QhActorTensors, collate_qh_chains
from aria_nbv.data_handling.qh_data.views import QhStaticContext
from aria_nbv.vin.models.target_finite_horizon import (
    TargetFiniteHorizonScorer,
    TargetFiniteHorizonScorerConfig,
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
        attention_heads=4,
        dropout=0.0,
        max_horizon=4,
    ).setup_target()
    scorer.eval()
    return scorer


def test_qh_scorer_output_matches_actor_candidate_axes_and_is_deterministic() -> None:
    actor = _actor()
    scorer = _scorer()

    first = scorer(actor)
    second = scorer(actor)

    assert first.shape == actor.action_mask.shape == (1, 3, 4)
    assert first.dtype == torch.float32
    assert torch.equal(first, second)
    assert torch.isfinite(first[actor.action_mask]).all()


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

    expected = scorer(actor)[:, :, permutation]
    actual = scorer(permuted)

    assert torch.allclose(actual, expected, atol=1e-6, rtol=1e-6)


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

    assert torch.allclose(changed[action_mask], baseline[action_mask], atol=1e-6, rtol=1e-6)
    assert torch.equal(changed[~action_mask], torch.zeros_like(changed[~action_mask]))


def test_qh_scorer_uses_target_history_and_budget_without_future_history() -> None:
    actor = _actor()
    scorer = _scorer()
    baseline = scorer(actor)

    target = actor.target_extents.clone()
    target[:, 0] += 0.75
    assert not torch.allclose(scorer(replace(actor, target_extents=target)), baseline)

    history = actor.history_pose_relative_root.tensor().clone()
    history[:, 2, 0, :] += 0.25
    assert not torch.allclose(
        scorer(replace(actor, history_pose_relative_root=PoseTW(history))),
        baseline,
    )

    future_history = actor.history_pose_relative_root.tensor().clone()
    future_history[:, 0, 2, :] += 10_000.0
    assert torch.allclose(
        scorer(replace(actor, history_pose_relative_root=PoseTW(future_history))),
        baseline,
        atol=1e-6,
        rtol=1e-6,
    )

    budget = actor.horizon_remaining.clone()
    budget[:, 0] -= 1
    assert not torch.allclose(scorer(replace(actor, horizon_remaining=budget)), baseline)


def test_qh_scorer_backward_updates_parameters_only() -> None:
    actor = _actor()
    scorer = _scorer()

    scorer(actor)[actor.action_mask].sum().backward()

    assert any(parameter.grad is not None and bool(parameter.grad.abs().sum() > 0) for parameter in scorer.parameters())
    assert actor.candidate_pose_relative_root.tensor().grad is None
    assert actor.static_context is not None
    assert actor.static_context.occ_pr is not None
    assert actor.static_context.occ_pr.grad is None


def test_qh_scorer_config_is_factory_and_rejects_profile_mismatch() -> None:
    config = TargetFiniteHorizonScorerConfig(hidden_dim=32, attention_heads=4, max_horizon=4)
    assert config.target_type is TargetFiniteHorizonScorer
    assert isinstance(config.setup_target(), TargetFiniteHorizonScorer)

    actor = replace(_actor(), static_context=None)
    try:
        config.setup_target()(actor)
    except ValueError as error:
        assert "EVL" in str(error)
    else:  # pragma: no cover - assertion branch
        raise AssertionError("scorer accepted an actor without required EVL context")


def test_qh_scorer_module_has_no_oracle_or_supervision_dependency() -> None:
    path = Path(__file__).resolve().parents[2] / "aria_nbv" / "vin" / "models" / "target_finite_horizon.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module is not None}
    assert not any("oracle" in module for module in imports)
    assert "QhSupervision" not in path.read_text(encoding="utf-8")
