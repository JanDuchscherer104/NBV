"""Exact objective and lifecycle tests for the dedicated Q_H module."""

# ruff: noqa: S101

from __future__ import annotations

import ast
import inspect
import warnings
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest
import torch
from pydantic import ValidationError
from torch import nn

from aria_nbv.data_handling.qh import QhBatch, collate_qh_samples
from aria_nbv.lightning.optimizers import OneCycleSchedulerConfig
from aria_nbv.lightning.qh_module import (
    QhLightningModule,
    QhLightningModuleConfig,
    _flatten_qh_scorer_inputs,
)
from tests.data_handling.test_qh import _chain


class _TableScorer(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.current = nn.Parameter(torch.tensor([1.0, 2.0, 3.0]))
        self.next = nn.Parameter(torch.tensor([1.0, 3.0, 2.0]))
        self.calls = 0

    def forward(self, actor):
        self.calls += 1
        successor = actor.remaining_budget.unsqueeze(1) == 1
        width = actor.candidate_pose_relative_root.shape[1]
        return torch.where(successor, self.next[:width].unsqueeze(0), self.current[:width].unsqueeze(0))


def _batch(*, bootstrap: bool = True) -> QhBatch:
    chain = _chain(steps=2, width=3)
    supervision = replace(
        chain.supervision,
        one_step_target_root_gain=torch.tensor([[0.0, 0.5, 0.0], [2.0, 0.0, 0.0]]),
        selected_candidate_index=torch.tensor([1, 0]),
        discount=torch.tensor([0.9, 0.9]),
        terminal=torch.tensor([not bootstrap, not bootstrap]),
        row_train_mask=torch.tensor([True, True]),
    )
    return collate_qh_samples([replace(chain, supervision=supervision)])


def _module(sync_interval: int = 2) -> QhLightningModule:
    return QhLightningModule(
        QhLightningModuleConfig(target_sync_interval=sync_interval, huber_delta=1.0, lr_scheduler=None),
        scorer=_TableScorer(),
    )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), "inf"])
def test_huber_delta_rejects_nonfinite_values(value: float | str) -> None:
    with pytest.raises(ValidationError) as error:
        QhLightningModuleConfig(huber_delta=value)

    assert error.value.errors()[0]["loc"] == ("huber_delta",)


def test_forward_flattens_and_scatters_every_valid_chain_state_once() -> None:
    module = _module()
    batch = _batch()

    values = module(batch)

    assert values.shape == (1, 2, 3)
    assert values.tolist() == [[[1.0, 2.0, 3.0], [1.0, 3.0, 2.0]]]
    assert module.online_scorer.calls == 1


def test_flatten_gathers_causal_history_for_variable_length_chains_without_step_loop() -> None:
    batch = collate_qh_samples([_chain(steps=3, width=2), _chain(steps=2, width=2, offset=10)])

    flattened, valid = _flatten_qh_scorer_inputs(batch)

    assert valid.tolist() == [True, True, True, True, True, False]
    assert flattened.history_mask.tolist() == [
        [False, False, False],
        [True, False, False],
        [True, True, False],
        [False, False, False],
        [True, False, False],
    ]
    assert flattened.history_candidate_row_id.tolist() == [
        [-1, -1, -1],
        [0, -1, -1],
        [0, 3, -1],
        [-1, -1, -1],
        [10, -1, -1],
    ]
    tree = ast.parse(inspect.getsource(_flatten_qh_scorer_inputs))
    assert not any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(tree))


def test_forward_scatter_keeps_padded_states_zero() -> None:
    module = _module()
    batch = collate_qh_samples([_chain(steps=1, width=3), _chain(steps=2, width=3, offset=10)])

    values = module(batch)

    assert values.shape == (2, 2, 3)
    assert values[0, 1].eq(0).all()
    assert module.online_scorer.calls == 1


def test_exact_double_q_target_and_huber_loss() -> None:
    module = _module()
    module.target_scorer.next.data.copy_(torch.tensor([10.0, 20.0, 30.0]))

    loss, targets, admitted = module.compute_fitted_q_loss(_batch())

    assert admitted.tolist() == [[True, True]]
    assert torch.allclose(targets, torch.tensor([[18.5, 2.0]]))
    assert loss.item() == pytest.approx(8.25)
    assert module.online_scorer.calls == 1
    assert module.target_scorer.calls == 1


def test_terminal_and_no_valid_next_rows_do_not_bootstrap() -> None:
    module = _module()
    batch = _batch(bootstrap=False)

    _loss, targets, _admitted = module.compute_fitted_q_loss(batch)

    assert torch.equal(targets, batch.supervision.selected_reward)


def test_nonterminal_transition_with_no_valid_successor_action_does_not_bootstrap() -> None:
    module = _module()
    batch = _batch()
    action_mask = batch.inputs.actor_action_mask.clone()
    action_mask[:, 1] = False
    row_mask = batch.supervision.row_train_mask.clone()
    row_mask[:, 1] = False
    batch = replace(
        batch,
        inputs=replace(batch.inputs, actor_action_mask=action_mask),
        supervision=replace(batch.supervision, row_train_mask=row_mask),
    )

    _loss, targets, admitted = module.compute_fitted_q_loss(batch)

    assert admitted.tolist() == [[True, False]]
    assert targets[0, 0] == batch.supervision.selected_reward[0, 0]


@pytest.mark.parametrize("field", ["index", "row_id", "actor_mask", "reward"])
def test_trainable_selected_rows_fail_closed(field: str) -> None:
    module = _module()
    batch = _batch()
    if field == "index":
        batch = replace(
            batch,
            supervision=replace(batch.supervision, selected_candidate_index=torch.tensor([[9, 0]])),
        )
    elif field == "row_id":
        row_ids = batch.supervision.candidate_row_id.clone()
        row_ids[0, 0, 1] = -1
        batch = replace(batch, supervision=replace(batch.supervision, candidate_row_id=row_ids))
    elif field == "actor_mask":
        mask = batch.inputs.actor_action_mask.clone()
        mask[0, 0, 1] = False
        batch = replace(batch, inputs=replace(batch.inputs, actor_action_mask=mask))
    else:
        reward = batch.supervision.one_step_target_root_gain.clone()
        reward[0, 0, 1] = float("nan")
        batch = replace(batch, supervision=replace(batch.supervision, one_step_target_root_gain=reward))

    with pytest.raises(ValueError, match="selected Q_H row"):
        module.compute_fitted_q_loss(batch)


def test_row_train_mask_is_the_canonical_selected_transition_admission() -> None:
    """Malformed excluded rows must not create a second model-layer policy."""

    module = _module()
    batch = _batch()
    reward = batch.supervision.one_step_target_root_gain.clone()
    reward[0, 0, 0] = float("nan")
    batch = replace(
        batch,
        supervision=replace(
            batch.supervision,
            selected_candidate_index=torch.tensor([[0, 0]]),
            one_step_target_root_gain=reward,
            row_train_mask=torch.tensor([[False, True]]),
        ),
    )

    loss, _targets, admitted = module.compute_fitted_q_loss(batch)

    assert admitted.tolist() == [[False, True]]
    assert torch.isfinite(loss)


def test_stage_diagnostics_are_interpretable_and_share_one_key_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    module.target_scorer.next.data.copy_(torch.tensor([10.0, 20.0, 30.0]))
    logged: dict[str, torch.Tensor] = {}
    monkeypatch.setattr(module, "log", lambda name, value, **kwargs: logged.__setitem__(name, value))

    module.on_validation_epoch_start()
    module.validation_step(_batch(), 0)
    module.on_validation_epoch_end()

    expected = {
        "val/loss": 8.25,
        "val/td_abs_mean": 8.75,
        "val/q_prediction_mean": 1.5,
        "val/q_prediction_std": 0.5,
        "val/q_prediction_min": 1.0,
        "val/q_prediction_max": 2.0,
        "val/q_target_mean": 10.25,
        "val/q_target_std": 8.25,
        "val/q_target_min": 2.0,
        "val/q_target_max": 18.5,
        "val/terminal_fraction": 0.0,
        "val/bootstrap_fraction": 0.5,
        "val/no_valid_next_fraction": 0.0,
        "val/admitted_rows": 2.0,
        "val/support_actions": 3.0,
        "val/nonfinite_count": 0.0,
        "val/target_age": 0.0,
        "val/target_syncs": 0.0,
    }
    assert set(logged) == set(expected)
    for name, value in expected.items():
        assert logged[name].item() == pytest.approx(value)


def test_training_step_logs_stage_qualified_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _module()
    optimizer = torch.optim.SGD(module.online_scorer.parameters(), lr=0.01)
    logged: set[str] = set()
    monkeypatch.setattr(module, "optimizers", lambda: optimizer)
    monkeypatch.setattr(module, "manual_backward", lambda loss: loss.backward())
    monkeypatch.setattr(module, "_step_learning_rate_schedulers", lambda: None)
    monkeypatch.setattr(module, "log", lambda name, value, **kwargs: logged.add(name))

    loss = module.training_step(_batch(), 0)

    assert loss is not None
    assert "train/td_abs_mean" in logged


@pytest.mark.parametrize(
    ("updates", "expected_age", "expected_syncs"),
    [(1, 1.0, 0.0), (2, 0.0, 1.0)],
)
def test_target_diagnostics_follow_completed_optimizer_updates(
    updates: int,
    expected_age: float,
    expected_syncs: float,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module(sync_interval=2)
    for _ in range(updates):
        module.record_optimizer_update()
    logged: dict[str, torch.Tensor] = {}
    monkeypatch.setattr(module, "log", lambda name, value, **kwargs: logged.__setitem__(name, value))

    module.validation_step(_batch(), 0)

    assert logged["val/target_age"].item() == expected_age
    assert logged["val/target_syncs"].item() == expected_syncs


@pytest.mark.parametrize(
    ("estimated_steps", "warns"),
    [(1, True), (2, False), (20, False), (float("inf"), False)],
)
def test_fit_start_warns_only_when_target_sync_is_unreachable(
    estimated_steps: int,
    warns: bool,
) -> None:
    module = _module(sync_interval=2)
    module.trainer = SimpleNamespace(
        lr_scheduler_configs=[],
        estimated_stepping_batches=estimated_steps,
        global_step=0,
    )

    if warns:
        with pytest.warns(UserWarning, match="requires 2 remaining optimizer updates.*1 estimated updates remaining"):
            module.on_fit_start()
    else:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            module.on_fit_start()
        assert not captured


def test_fit_start_uses_resume_counter_for_next_sync_reachability() -> None:
    module = _module(sync_interval=100)
    module.optimizer_updates.fill_(99)
    module.trainer = SimpleNamespace(
        lr_scheduler_configs=[],
        estimated_stepping_batches=100,
        global_step=99,
    )

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        module.on_fit_start()
    module.record_optimizer_update()

    assert not captured
    assert module.optimizer_updates.item() == 100
    assert module.target_syncs.item() == 1


def test_fit_start_warns_when_resume_capacity_cannot_reach_next_sync() -> None:
    module = _module(sync_interval=101)
    module.optimizer_updates.fill_(99)
    module.trainer = SimpleNamespace(
        lr_scheduler_configs=[],
        estimated_stepping_batches=100,
        global_step=99,
    )

    with pytest.warns(
        UserWarning,
        match="requires 2 remaining optimizer updates.*1 estimated updates remaining.*global_step=99",
    ):
        module.on_fit_start()


def test_target_is_independent_frozen_and_forced_to_eval() -> None:
    module = _module()

    assert module.target_scorer is not module.online_scorer
    assert all(not parameter.requires_grad for parameter in module.target_scorer.parameters())
    assert all(
        torch.equal(left, right)
        for left, right in zip(module.online_scorer.parameters(), module.target_scorer.parameters(), strict=True)
    )
    module.train()
    assert module.online_scorer.training is True
    assert module.target_scorer.training is False


def test_target_hard_sync_uses_optimizer_update_counter() -> None:
    module = _module(sync_interval=2)
    original = deepcopy(module.target_scorer.state_dict())
    module.online_scorer.current.data.add_(5)

    module.record_optimizer_update()
    assert module.optimizer_updates.item() == 1
    assert module.target_syncs.item() == 0
    assert all(torch.equal(value, module.target_scorer.state_dict()[name]) for name, value in original.items())

    module.record_optimizer_update()
    assert module.optimizer_updates.item() == 2
    assert module.target_syncs.item() == 1
    assert all(
        torch.equal(value, module.target_scorer.state_dict()[name])
        for name, value in module.online_scorer.state_dict().items()
    )


def test_optimizer_excludes_target_parameters() -> None:
    module = _module()
    optimizer = module.configure_optimizers()
    optimized = {id(parameter) for group in optimizer.param_groups for parameter in group["params"]}

    assert optimized == {id(parameter) for parameter in module.online_scorer.parameters()}
    assert optimized.isdisjoint({id(parameter) for parameter in module.target_scorer.parameters()})


def test_configure_optimizers_builds_repo_standard_stateful_step_scheduler() -> None:
    module = QhLightningModule(
        QhLightningModuleConfig(
            lr_scheduler=OneCycleSchedulerConfig(max_lr=1e-3),
            target_sync_interval=2,
        ),
        scorer=_TableScorer(),
    )
    module.trainer = SimpleNamespace(estimated_stepping_batches=4)

    configured = module.configure_optimizers()

    assert isinstance(configured, dict)
    assert configured["lr_scheduler"]["interval"] == "step"
    assert configured["lr_scheduler"]["scheduler"].total_steps == 4


def test_empty_local_admission_still_participates_in_distributed_count(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _module()
    batch = _batch()
    batch = replace(
        batch,
        supervision=replace(batch.supervision, row_train_mask=torch.zeros(1, 2, dtype=torch.bool)),
    )
    calls: list[torch.Tensor] = []

    monkeypatch.setattr(torch.distributed, "is_available", lambda: True)
    monkeypatch.setattr(torch.distributed, "is_initialized", lambda: True)
    monkeypatch.setattr(torch.distributed, "get_world_size", lambda: 2)

    def _all_reduce(value: torch.Tensor, op) -> None:
        del op
        calls.append(value)
        value.add_(1)

    monkeypatch.setattr(torch.distributed, "all_reduce", _all_reduce)

    loss, _targets, admitted = module.compute_fitted_q_loss(batch)

    assert calls
    assert not admitted.any()
    assert loss.item() == 0.0
    assert loss.requires_grad


def test_validation_uses_no_distributed_collectives(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _module()
    logged: list[tuple[str, torch.Tensor]] = []
    expected = module.compute_fitted_q_loss(_batch())[0].item()

    monkeypatch.setattr(module, "log", lambda name, value, **kwargs: logged.append((name, value)))
    monkeypatch.setattr(
        torch.distributed,
        "all_reduce",
        lambda *args, **kwargs: pytest.fail("replicated validation must not reduce across ranks"),
    )

    module.on_validation_epoch_start()
    module.validation_step(_batch(), 0)
    module.on_validation_epoch_end()

    logged_by_name = dict(logged)
    assert logged_by_name["val/loss"].item() == pytest.approx(expected)
