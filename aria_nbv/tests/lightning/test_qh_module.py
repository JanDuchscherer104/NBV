"""Objective, masking, and transaction tests for the retained Q_H module."""

# ruff: noqa: S101

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest
import torch
from pydantic import ValidationError
from torch import nn
from torch.utils.data import Dataset

from aria_nbv.data_handling.qh import QhActorTensors, QhBatch, QhChain, collate_qh_chains
from aria_nbv.lightning.qh_module import QhLightningModule, QhLightningModuleConfig
from aria_nbv.rollouts.qh_reader import QhDataContract
from tests.data_handling.test_qh import _chain


class _TableScorer(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.current = nn.Parameter(torch.tensor([1.0, 2.0, 3.0, 4.0]))
        self.next = nn.Parameter(torch.tensor([1.0, 3.0, 2.0, 4.0]))
        self.calls = 0

    def forward(self, actor: QhActorTensors) -> torch.Tensor:
        self.calls += 1
        width = actor.action_mask.shape[-1]
        current = self.current[:width].view(1, 1, width)
        successor = self.next[:width].view(1, 1, width)
        return torch.where(actor.horizon_remaining.unsqueeze(-1).eq(1), successor, current).expand(
            *actor.action_mask.shape
        )


class _BadShapeScorer(nn.Module):
    def forward(self, actor: QhActorTensors) -> torch.Tensor:
        return torch.zeros((*actor.action_mask.shape[:2], actor.action_mask.shape[-1] + 1))


_CONTRACT = QhDataContract("qh-v1", "v0", "reward", "return", "td", 0.95, "reasons-v1", "vin-v1")


class _ChainDataset(Dataset[QhChain]):
    def __init__(self, chains: list[QhChain], *, scene: str = "train-scene") -> None:
        self.chains = chains
        self.scenes = frozenset({scene})
        self.max_horizon = max(chain.num_steps for chain in chains)
        self.contract = _CONTRACT
        self.provenance: dict[str, object] = {"scene": scene}

    def __len__(self) -> int:
        return len(self.chains)

    def __getitem__(self, index: int) -> QhChain:
        return self.chains[index]


def _batch(*, bootstrap: bool = True) -> QhBatch:
    chain = _chain(steps=2, width=3)
    supervision = replace(
        chain.supervision,
        candidate_reward=torch.tensor([[0.0, 0.5, 0.0], [2.0, 0.0, 0.0]]),
        selected_index=torch.tensor([1, 0]),
        discount=torch.tensor([0.9, 0.0]),
        terminal=torch.tensor([not bootstrap, True]),
    )
    return collate_qh_chains([replace(chain, supervision=supervision)])


def _module(sync_interval: int = 2) -> QhLightningModule:
    return QhLightningModule(
        QhLightningModuleConfig(target_sync_interval=sync_interval, lr_scheduler=None),
        scorer=_TableScorer(),
    )


def _install_manual_step(module: QhLightningModule, monkeypatch: pytest.MonkeyPatch, *, lr: float = 0.1) -> None:
    optimizer = torch.optim.SGD(module.online_scorer.parameters(), lr=lr)
    monkeypatch.setattr(module, "optimizers", lambda: optimizer)
    monkeypatch.setattr(module, "manual_backward", lambda loss: loss.backward())
    monkeypatch.setattr(module, "_step_learning_rate_schedulers", lambda: None)
    monkeypatch.setattr(module, "log", lambda *args, **kwargs: None)


def test_scorer_is_required_and_not_part_of_config() -> None:
    with pytest.raises(TypeError, match="scorer"):
        QhLightningModule(QhLightningModuleConfig(lr_scheduler=None))  # type: ignore[call-arg]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), "inf"])
def test_huber_delta_rejects_nonfinite_values(value: float | str) -> None:
    with pytest.raises(ValidationError) as error:
        QhLightningModuleConfig(huber_delta=value)

    assert error.value.errors()[0]["loc"] == ("huber_delta",)


def test_forward_consumes_actor_tensors_and_requires_exact_batch_shape() -> None:
    batch = collate_qh_chains([_chain(steps=1, width=3), _chain(steps=2, width=3, offset=10)])
    module = _module()

    values = module(batch.actor)

    assert values.shape == (2, 2, 3)
    assert module.online_scorer.calls == 1
    with pytest.raises(ValueError, match=r"must return shape \(2, 2, 3\)"):
        QhLightningModule(module.config, scorer=_BadShapeScorer())(batch.actor)


def test_exact_double_q_target_and_huber_loss() -> None:
    module = _module()
    module.target_scorer.next.data.copy_(torch.tensor([10.0, 20.0, 30.0, 40.0]))

    loss, targets, admitted = module.compute_fitted_q_loss(_batch())

    assert admitted.tolist() == [[True, True]]
    assert torch.allclose(targets, torch.tensor([[18.5, 2.0]]))
    assert loss.item() == pytest.approx(8.25)


def test_terminal_rows_do_not_bootstrap() -> None:
    batch = _batch(bootstrap=False)

    _loss, targets, _admitted = _module().compute_fitted_q_loss(batch)

    selected_reward = batch.supervision.candidate_reward.gather(
        -1, batch.supervision.selected_index.unsqueeze(-1)
    ).squeeze(-1)
    assert torch.equal(targets, selected_reward)


def test_bootstrap_argmax_uses_shifted_action_and_label_support() -> None:
    module = _module()
    module.online_scorer.next.data.copy_(torch.tensor([5.0, 1_000_000.0, 7.0, 0.0]))
    module.target_scorer.next.data.copy_(torch.tensor([10.0, 1_000_000.0, 30.0, 0.0]))
    batch = _batch()
    labels = batch.supervision.label_mask.clone()
    labels[:, 1] = torch.tensor([True, False, True])
    batch = replace(batch, supervision=replace(batch.supervision, label_mask=labels))

    _loss, targets, admitted = module.compute_fitted_q_loss(batch)

    assert admitted.tolist() == [[True, True]]
    assert targets[0, 0].item() == pytest.approx(0.5 + 0.9 * 30.0)


def test_nonterminal_row_without_joint_successor_support_does_not_bootstrap() -> None:
    module = _module()
    module.target_scorer.next.data.copy_(torch.tensor([1_000_000.0, 20.0, 30.0, 0.0]))
    batch = _batch()
    labels = batch.supervision.label_mask.clone()
    labels[:, 1] = False
    batch = replace(batch, supervision=replace(batch.supervision, label_mask=labels))

    _loss, targets, admitted = module.compute_fitted_q_loss(batch)

    assert admitted.tolist() == [[True, False]]
    assert targets[0, 0] == 0.5


@pytest.mark.parametrize("sync_interval", [1, 2])
def test_target_sync_copies_post_update_online_weights(sync_interval: int, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _module(sync_interval)
    _install_manual_step(module, monkeypatch)
    initial_target = deepcopy(module.target_scorer.state_dict())

    for update in range(sync_interval):
        module.training_step(_batch(), update)
        if update + 1 < sync_interval:
            assert all(
                torch.equal(value, module.target_scorer.state_dict()[name]) for name, value in initial_target.items()
            )

    assert module.optimizer_updates.item() == sync_interval
    online_state = module.online_scorer.state_dict()
    target_state = module.target_scorer.state_dict()
    assert any(not torch.equal(value, initial_target[name]) for name, value in online_state.items())
    assert all(torch.equal(value, target_state[name]) for name, value in online_state.items())


def test_single_device_validation_logs_exact_weighted_loss_and_only_infrastructure_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    module.target_scorer.next.data.copy_(torch.tensor([10.0, 20.0, 30.0, 40.0]))
    logged: dict[str, torch.Tensor] = {}
    monkeypatch.setattr(module, "log", lambda name, value, **kwargs: logged.__setitem__(name, value.detach()))

    module.on_validation_epoch_start()
    module.validation_step(_batch(), 0)
    module.on_validation_epoch_end()

    assert logged["val/loss"].item() == pytest.approx(8.25)
    assert logged["val/admitted_rows"].item() == 2
    assert set(logged) == {
        "val/loss",
        "val/admitted_rows",
        "val/bootstrap_fraction",
        "val/terminal_fraction",
        "val/no_successor_fraction",
        "val/nonfinite_valid_values",
    }


def test_target_is_independent_frozen_forced_to_eval_and_excluded_from_optimizer() -> None:
    module = _module()

    assert module.target_scorer is not module.online_scorer
    assert all(not parameter.requires_grad for parameter in module.target_scorer.parameters())
    module.train()
    assert module.online_scorer.training is True
    assert module.target_scorer.training is False
    optimizer = module.configure_optimizers()
    assert isinstance(optimizer, torch.optim.Optimizer)
    optimized = {id(parameter) for group in optimizer.param_groups for parameter in group["params"]}

    assert optimized == {id(parameter) for parameter in module.online_scorer.parameters()}
    assert optimized.isdisjoint({id(parameter) for parameter in module.target_scorer.parameters()})
