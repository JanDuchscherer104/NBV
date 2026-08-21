"""Direct-Trainer regressions for the retained Q_H training transaction."""

# ruff: noqa: S101

from copy import deepcopy
from dataclasses import replace
from typing import Any

import pytest
import pytorch_lightning as pl
import torch
from lightning_fabric.utilities.exceptions import MisconfigurationException

from aria_nbv.lightning.qh_datamodule import QhDataModule
from aria_nbv.lightning.qh_module import QhLightningModule, QhLightningModuleConfig
from tests.data_handling.test_qh import _chain
from tests.lightning.test_qh_module import _CF0_ACTOR_HASH, _ChainDataset, _TableScorer


def _trainer(*, devices: int = 1, fast_dev_run: bool = True, **kwargs: Any) -> pl.Trainer:
    return pl.Trainer(
        accelerator="cpu",
        devices=devices,
        fast_dev_run=fast_dev_run,
        logger=False,
        enable_checkpointing=False,
        enable_model_summary=False,
        use_distributed_sampler=True,
        **kwargs,
    )


@pytest.mark.parametrize("horizons", [(1,), (4,), (1, 3, 4)], ids=["h1", "h4", "mixed"])
def test_fast_dev_run_executes_exactly_one_injected_scorer_transaction(
    horizons: tuple[int, ...],
) -> None:
    data = QhDataModule(
        train=_ChainDataset(
            [_chain(steps=horizon, width=3, offset=index * 100) for index, horizon in enumerate(horizons)]
        ),
        batch_size=len(horizons),
        seed=17,
        experiment_profile="qh_cf0_v1",
    )
    module = QhLightningModule(
        QhLightningModuleConfig(
            target_sync_interval=1,
            actor_state_contract_hash=_CF0_ACTOR_HASH,
            learning_contract_hash=data.learning_contract_hash,
        ),
        scorer=_TableScorer(),
    )
    trainer = _trainer()

    trainer.fit(module, datamodule=data)

    assert trainer.global_step == 1
    assert module.optimizer_updates.item() == 1
    assert module.online_scorer.calls == 1
    assert module.target_scorer.calls == 1
    assert trainer.lr_scheduler_configs[0].scheduler.last_epoch == 1
    assert all(
        torch.equal(value, module.target_scorer.state_dict()[name])
        for name, value in module.online_scorer.state_dict().items()
    )


def test_fast_dev_run_global_empty_batch_is_exact_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    sample = _chain(steps=2, width=3)
    sample = replace(
        sample,
        supervision=replace(sample.supervision, label_mask=torch.zeros_like(sample.supervision.label_mask)),
    )
    data = QhDataModule(
        train=_ChainDataset([sample]),
        batch_size=1,
        seed=17,
        experiment_profile="qh_cf0_v1",
    )
    module = QhLightningModule(
        QhLightningModuleConfig(
            target_sync_interval=1,
            actor_state_contract_hash=_CF0_ACTOR_HASH,
            learning_contract_hash=data.learning_contract_hash,
        ),
        scorer=_TableScorer(),
    )
    initial_state = deepcopy(module.state_dict())
    logged: list[str] = []

    class _CaptureSchedulerState(pl.Callback):
        def __init__(self) -> None:
            self.before: dict[str, Any] | None = None

        def on_train_start(self, trainer: pl.Trainer, pl_module: pl.LightningModule) -> None:
            del pl_module
            self.before = deepcopy(trainer.lr_scheduler_configs[0].scheduler.state_dict())

    capture = _CaptureSchedulerState()

    monkeypatch.setattr(module, "log", lambda name, value, **kwargs: logged.append(name))
    trainer = _trainer(callbacks=[capture])

    trainer.fit(module, datamodule=data)

    assert trainer.global_step == 0
    assert module.online_scorer.calls == 0
    assert module.target_scorer.calls == 0
    assert module.optimizer_updates.item() == 0
    assert module.training_loss_sum.item() == 0.0
    assert module.training_row_count.item() == 0
    assert logged == []
    assert capture.before == trainer.lr_scheduler_configs[0].scheduler.state_dict()
    assert all(torch.equal(value, module.state_dict()[name]) for name, value in initial_state.items())


def test_trainer_rejects_gradient_accumulation_before_scorer_execution() -> None:
    data = QhDataModule(
        train=_ChainDataset([_chain(steps=2, width=3)]),
        batch_size=1,
        seed=17,
        experiment_profile="qh_cf0_v1",
    )
    module = QhLightningModule(
        QhLightningModuleConfig(
            lr_scheduler=None,
            actor_state_contract_hash=_CF0_ACTOR_HASH,
            learning_contract_hash=data.learning_contract_hash,
        ),
        scorer=_TableScorer(),
    )
    initial_state = deepcopy(module.state_dict())
    trainer = _trainer(accumulate_grad_batches=2)

    with pytest.raises(
        (ValueError, MisconfigurationException),
        match="(Q_H.*accumulate_grad_batches=1|gradient accumulation.*not supported.*manual optimization)",
    ):
        trainer.fit(module, datamodule=data)

    assert module.online_scorer.calls == 0
    assert module.target_scorer.calls == 0
    assert module.optimizer_updates.item() == 0
    assert trainer.global_step == 0
    assert all(torch.equal(value, module.state_dict()[name]) for name, value in initial_state.items())
