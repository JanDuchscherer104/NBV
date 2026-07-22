"""Tracer-bullet regressions for the Q_H Lightning review findings."""

# ruff: noqa: S101

from __future__ import annotations

import inspect
from copy import deepcopy
from dataclasses import replace
from typing import Any

import numpy as np
import pytest
import pytorch_lightning as pl
import torch
from lightning_fabric.utilities.exceptions import MisconfigurationException
from torch.optim.lr_scheduler import StepLR

from aria_nbv.data_handling.qh import QhBatch, QhCorpus, QhDataset
from aria_nbv.lightning.qh_datamodule import QhDataModule
from aria_nbv.lightning.qh_module import QhLightningModule
from tests.data_handling.test_qh import _dataset, _Reader, _SparseActorSource, _StaticDataset, _stored_state
from tests.lightning.test_qh_module import _module


def test_setup_none_admits_test_before_checking_scene_overlap() -> None:
    """``setup(None)`` must include test in the all-stage admission check."""

    dataset, _ = _dataset()
    sample = dataset[1]
    shared_train = _StaticDataset((sample,), "shared-scene")
    shared_test = _StaticDataset((sample,), "shared-scene")

    with pytest.raises(ValueError, match="train/test.*overlap scenes|overlap scenes.*train/test"):
        QhCorpus.admit(train=shared_train, test=shared_test)


def test_qh_batch_owns_pinning_and_nonblocking_transfer() -> None:
    """The top-level batch owns tensor pinning and transfer, not its lineage."""

    dataset, _ = _dataset()
    loader = QhDataModule(
        QhCorpus.admit(train=_StaticDataset((dataset[0],), "train-scene")),
        batch_size=1,
        seed=0,
    )
    batch = next(iter(loader.train_dataloader()))

    assert hasattr(QhBatch, "pin_memory")
    parameter = inspect.signature(QhBatch.to).parameters["non_blocking"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is True

    lineage = batch.lineage
    moved = batch.to("cpu", non_blocking=True)
    assert moved.lineage is lineage


def test_lightning_module_delegates_transfer_to_qh_batch() -> None:
    """Lightning's default transfer path must call the public batch ``to`` seam."""

    assert "transfer_batch_to_device" not in QhLightningModule.__dict__


def test_lightning_module_uses_the_data_owned_selected_row_predicate() -> None:
    """The fitted-Q layer must not copy the data-owned admission predicate."""

    source = inspect.getsource(QhLightningModule)
    fitted_source = inspect.getsource(QhLightningModule._fitted_q_components)

    assert fitted_source.count("batch.assert_selected_rows_consistent()") == 1
    assert "_validate_selected_rows" not in source
    assert "selected_candidate_row_id" not in fitted_source
    assert "torch.isfinite(batch.transition.reward)" not in fitted_source


def test_datamodule_does_not_read_private_trainer_accelerator_state() -> None:
    """Sampler ownership must use supported public configuration only."""

    source = inspect.getsource(QhDataModule)
    assert "_accelerator_connector" not in source


class _StepScheduledQhModule(QhLightningModule):
    """Test-only step scheduler exposing accidental optimizer advancement."""

    def configure_optimizers(self) -> dict[str, Any]:
        optimizer = super().configure_optimizers()
        return {
            "optimizer": optimizer,
            "lr_scheduler": {
                "scheduler": StepLR(optimizer, step_size=1, gamma=0.5),
                "interval": "step",
            },
        }


class _ClockSnapshot(pl.Callback):
    """Capture optimizer and scheduler state around one Trainer fit."""

    optimizer_before: dict[str, Any]
    scheduler_before: dict[str, Any]
    optimizer_after: dict[str, Any]
    scheduler_after: dict[str, Any]

    def on_train_start(self, trainer: pl.Trainer, pl_module: pl.LightningModule) -> None:
        del pl_module
        self.optimizer_before = deepcopy(trainer.optimizers[0].state_dict())
        self.scheduler_before = deepcopy(trainer.lr_scheduler_configs[0].scheduler.state_dict())

    def on_train_end(self, trainer: pl.Trainer, pl_module: pl.LightningModule) -> None:
        del pl_module
        self.optimizer_after = deepcopy(trainer.optimizers[0].state_dict())
        self.scheduler_after = deepcopy(trainer.lr_scheduler_configs[0].scheduler.state_dict())


def test_globally_empty_batch_does_not_advance_training_clocks() -> None:
    """A globally empty admitted batch is not an optimizer update."""

    dataset, _ = _dataset()
    sample = dataset[1]
    empty = replace(
        sample,
        transition=replace(sample.transition, row_train_mask=torch.tensor(False)),
    )
    data = QhDataModule(
        QhCorpus.admit(train=_StaticDataset((empty,), "train-scene")),
        batch_size=1,
        seed=0,
    )
    base = _module(sync_interval=1)
    module = _StepScheduledQhModule(base.config, scorer=base.online_scorer)
    online_before = deepcopy(module.online_scorer.state_dict())
    target_before = deepcopy(module.target_scorer.state_dict())
    clocks = _ClockSnapshot()
    trainer = pl.Trainer(
        accelerator="cpu",
        devices=1,
        max_epochs=1,
        limit_train_batches=1,
        num_sanity_val_steps=0,
        logger=False,
        callbacks=[clocks],
        enable_checkpointing=False,
        enable_model_summary=False,
        use_distributed_sampler=False,
    )

    trainer.fit(module, datamodule=data)

    assert trainer.global_step == 0
    assert module.optimizer_updates.item() == 0
    assert module.target_syncs.item() == 0
    assert clocks.optimizer_after == clocks.optimizer_before
    assert clocks.scheduler_after == clocks.scheduler_before
    assert all(torch.equal(value, online_before[name]) for name, value in module.online_scorer.state_dict().items())
    assert all(torch.equal(value, target_before[name]) for name, value in module.target_scorer.state_dict().items())


def test_dataset_actor_mask_exclusion_emits_diagnostic_row_without_training_update() -> None:
    """A selected action rejected by the actor mask must remain loadable but untrained."""

    state = _stored_state(0, width=2, terminal=True)
    selected = state.transition.selected_candidate_index
    actor_action_mask = np.array(state.actor.actor_action_mask, copy=True)
    actor_action_mask[selected] = False
    state = replace(state, actor=replace(state.actor, actor_action_mask=actor_action_mask))
    assert state.supervision.q_train_mask[selected]
    dataset = QhDataset(  # type: ignore[arg-type]
        rollout_reader=_Reader((state,)),
        actor_source=_SparseActorSource(),
    )

    sample = dataset[0]
    assert not sample.transition.row_train_mask.item()
    data = QhDataModule(
        QhCorpus.admit(train=_StaticDataset((sample,), "train-scene")),
        batch_size=1,
        seed=0,
    )
    module = _module(sync_interval=1)
    trainer = pl.Trainer(
        accelerator="cpu",
        devices=1,
        max_epochs=1,
        limit_train_batches=1,
        num_sanity_val_steps=0,
        logger=False,
        enable_checkpointing=False,
        enable_model_summary=False,
        use_distributed_sampler=False,
    )

    trainer.fit(module, datamodule=data)

    assert trainer.global_step == 0
    assert module.optimizer_updates.item() == 0
    assert module.target_syncs.item() == 0


def test_manual_optimization_rejects_gradient_accumulation() -> None:
    """Unsupported accumulation must fail publicly before the first batch."""

    dataset, _ = _dataset()
    data = QhDataModule(
        QhCorpus.admit(train=_StaticDataset((dataset[1],), "train-scene")),
        batch_size=1,
        seed=0,
    )
    trainer = pl.Trainer(
        accelerator="cpu",
        devices=1,
        max_epochs=1,
        accumulate_grad_batches=2,
        logger=False,
        enable_checkpointing=False,
        enable_model_summary=False,
        use_distributed_sampler=False,
    )

    with pytest.raises(MisconfigurationException, match="gradient accumulation.*manual optimization"):
        trainer.fit(_module(), datamodule=data)


def test_validate_and_test_share_the_public_evaluation_lifecycle() -> None:
    """Validation and held-out test expose the same aggregate metric contract."""

    dataset, _ = _dataset()
    data = QhDataModule(
        QhCorpus.admit(
            train=_StaticDataset((dataset[0],), "train-scene"),
            val=_StaticDataset((dataset[1],), "val-scene"),
            test=_StaticDataset((dataset[1],), "test-scene"),
        ),
        batch_size=1,
        seed=0,
    )
    module = _module(sync_interval=2)
    trainer = pl.Trainer(
        accelerator="cpu",
        devices=1,
        max_epochs=1,
        limit_train_batches=1,
        limit_val_batches=1,
        limit_test_batches=1,
        num_sanity_val_steps=0,
        logger=False,
        enable_checkpointing=False,
        enable_model_summary=False,
        use_distributed_sampler=False,
    )

    trainer.fit(module, datamodule=data)
    validation = trainer.validate(module, datamodule=data, verbose=False)[0]
    held_out = trainer.test(module, datamodule=data, verbose=False)[0]

    validation_metrics = {name.removeprefix("val/") for name in validation}
    test_metrics = {name.removeprefix("test/") for name in held_out}
    assert "loss" in validation_metrics
    assert test_metrics == validation_metrics
    assert {
        "loss",
        "td_abs_mean",
        "q_prediction_mean",
        "q_target_mean",
        "terminal_fraction",
        "bootstrap_fraction",
        "no_valid_next_fraction",
        "admitted_rows",
        "support_actions",
        "nonfinite_count",
        "target_age",
        "target_syncs",
    } <= validation_metrics
