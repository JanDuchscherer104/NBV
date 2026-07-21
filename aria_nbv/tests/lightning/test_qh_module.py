"""Exact objective and lifecycle tests for the dedicated Q_H module."""

# ruff: noqa: S101

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest
import torch
from torch import nn

from aria_nbv.lightning.qh_data import QhBatch, QhSupervision, QhTransition
from aria_nbv.lightning.qh_module import QhLightningModule, QhLightningModuleConfig
from tests.vin.test_target_finite_horizon import _actor


class _TableScorer(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.current = nn.Parameter(torch.tensor([1.0, 2.0, 3.0]))
        self.next = nn.Parameter(torch.tensor([1.0, 3.0, 2.0]))

    def forward(self, actor):
        successor = actor.target_center_world[:, :1] > 5
        return torch.where(successor, self.next.unsqueeze(0), self.current.unsqueeze(0))


def _batch(*, bootstrap: bool = True) -> QhBatch:
    current = _actor()
    current = replace(
        current,
        target_center_world=torch.zeros_like(current.target_center_world),
        candidate_row_id=torch.tensor([[10, 11, 12], [20, 21, 22]]),
        actor_action_mask=torch.ones(2, 3, dtype=torch.bool),
    )
    successor = replace(
        current,
        target_center_world=torch.full_like(current.target_center_world, 10),
        actor_action_mask=torch.tensor([[bootstrap, bootstrap, bootstrap], [False, False, False]]),
    )
    return QhBatch(
        current_actor=current,
        next_actor=successor,
        next_actor_present=torch.tensor([True, True]),
        supervision=QhSupervision(
            q_train_mask=torch.ones(2, 3, dtype=torch.bool),
        ),
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


@pytest.mark.parametrize("field", ["index", "row_id", "actor_mask", "q_mask", "reward"])
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
    elif field == "q_mask":
        mask = batch.supervision.q_train_mask.clone()
        mask[0, 1] = False
        batch = replace(batch, supervision=replace(batch.supervision, q_train_mask=mask))
    else:
        batch = replace(batch, transition=replace(batch.transition, reward=torch.tensor([float("nan"), 2.0])))

    with pytest.raises(ValueError, match="selected Q_H row"):
        module.compute_fitted_q_loss(batch)


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
    assert all(torch.equal(value, module.target_scorer.state_dict()[name]) for name, value in original.items())

    module.record_optimizer_update()
    assert module.optimizer_updates.item() == 2
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

    assert logged[0][0] == "val/loss"
    assert logged[0][1].item() == pytest.approx(expected)
