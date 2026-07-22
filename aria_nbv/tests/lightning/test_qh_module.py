"""Exact objective and lifecycle tests for the dedicated Q_H module."""

# ruff: noqa: S101

from __future__ import annotations

import warnings
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from typing import get_type_hints

import pytest
import torch
from pydantic import ValidationError
from torch import nn

from aria_nbv.data_handling.qh import QhActorInputs, QhBatch, QhTransition
from aria_nbv.lightning.qh_module import QhLightningModule, QhLightningModuleConfig
from tests.vin.test_target_finite_horizon import _actor


class _TableScorer(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.current = nn.Parameter(torch.tensor([1.0, 2.0, 3.0]))
        self.next = nn.Parameter(torch.tensor([1.0, 3.0, 2.0]))

    def forward(self, actor):
        successor = actor.target_pose_world_object[:, 9:10] > 5
        return torch.where(successor, self.next.unsqueeze(0), self.current.unsqueeze(0))


def _batch(*, bootstrap: bool = True) -> QhBatch:
    current = _actor()
    current = replace(
        current,
        target_pose_world_object=torch.zeros_like(current.target_pose_world_object),
        candidate_row_id=torch.tensor([[10, 11, 12], [20, 21, 22]]),
        actor_action_mask=torch.ones(2, 3, dtype=torch.bool),
    )
    successor = replace(
        current,
        target_pose_world_object=torch.full_like(current.target_pose_world_object, 10),
        actor_action_mask=torch.tensor([[bootstrap, bootstrap, bootstrap], [False, False, False]]),
    )
    return QhBatch(
        current_actor=current,
        next_actor=successor,
        next_actor_present=torch.tensor([True, True]),
        transition=QhTransition(
            selected_candidate_index=torch.tensor([1, 0]),
            selected_candidate_row_id=torch.tensor([11, 20]),
            reward=torch.tensor([0.5, 2.0]),
            discount=torch.tensor([0.9, 0.9]),
            terminal=torch.tensor([False, not bootstrap]),
            row_train_mask=torch.tensor([True, True]),
        ),
        lineage=(),
    )


def _module(sync_interval: int = 2) -> QhLightningModule:
    return QhLightningModule(
        QhLightningModuleConfig(target_sync_interval=sync_interval, huber_delta=1.0),
        scorer=_TableScorer(),
    )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), "inf"])
def test_huber_delta_rejects_nonfinite_values(value: float | str) -> None:
    with pytest.raises(ValidationError) as error:
        QhLightningModuleConfig(huber_delta=value)

    assert error.value.errors()[0]["loc"] == ("huber_delta",)


def test_forward_accepts_the_concrete_actor_input_contract() -> None:
    assert get_type_hints(QhLightningModule.forward)["actor"] is QhActorInputs


def test_exact_double_q_target_and_huber_loss() -> None:
    module = _module()
    module.target_scorer.next.data.copy_(torch.tensor([10.0, 20.0, 30.0]))

    loss, targets, admitted = module.compute_fitted_q_loss(_batch())

    assert admitted.tolist() == [True, True]
    assert targets.tolist() == pytest.approx([18.5, 2.0])
    assert loss.item() == pytest.approx(8.25)


def test_terminal_and_no_valid_next_rows_do_not_bootstrap() -> None:
    module = _module()
    batch = _batch(bootstrap=False)

    _loss, targets, _admitted = module.compute_fitted_q_loss(batch)

    assert targets.tolist() == pytest.approx(batch.transition.reward.tolist())


@pytest.mark.parametrize("field", ["index", "row_id", "actor_mask", "reward"])
def test_trainable_selected_rows_fail_closed(field: str) -> None:
    module = _module()
    batch = _batch()
    if field == "index":
        batch = replace(batch, transition=replace(batch.transition, selected_candidate_index=torch.tensor([9, 0])))
    elif field == "row_id":
        batch = replace(batch, transition=replace(batch.transition, selected_candidate_row_id=torch.tensor([999, 20])))
    elif field == "actor_mask":
        mask = batch.current_actor.actor_action_mask.clone()
        mask[0, 1] = False
        batch = replace(batch, current_actor=replace(batch.current_actor, actor_action_mask=mask))
    else:
        batch = replace(batch, transition=replace(batch.transition, reward=torch.tensor([float("nan"), 2.0])))

    with pytest.raises(ValueError, match="selected Q_H row"):
        module.compute_fitted_q_loss(batch)


def test_row_train_mask_is_the_canonical_selected_transition_admission() -> None:
    """Malformed excluded rows must not create a second model-layer policy."""

    module = _module()
    batch = _batch()
    batch = replace(
        batch,
        transition=replace(
            batch.transition,
            selected_candidate_index=torch.tensor([99, 0]),
            selected_candidate_row_id=torch.tensor([999, 20]),
            reward=torch.tensor([float("nan"), 2.0]),
            row_train_mask=torch.tensor([False, True]),
        ),
    )

    loss, _targets, admitted = module.compute_fitted_q_loss(batch)

    assert admitted.tolist() == [False, True]
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
        "val/no_valid_next_fraction": 0.5,
        "val/admitted_rows": 2.0,
        "val/support_actions": 6.0,
        "val/nonfinite_count": 0.0,
        "val/target_age": 0.0,
        "val/target_syncs": 0.0,
    }
    assert set(logged) == set(expected)
    for name, value in expected.items():
        assert logged[name].item() == pytest.approx(value)


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


def test_empty_local_admission_still_participates_in_distributed_count(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _module()
    batch = _batch()
    batch = replace(
        batch,
        transition=replace(batch.transition, row_train_mask=torch.zeros(2, dtype=torch.bool)),
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
