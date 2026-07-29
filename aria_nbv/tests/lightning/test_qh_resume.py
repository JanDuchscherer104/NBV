"""Full-state resume parity for fitted Q_H training."""

# ruff: noqa: S101

import pickle
from pathlib import Path

import pytest
import pytorch_lightning as pl
import torch
from pytorch_lightning.callbacks import ModelCheckpoint

from aria_nbv.lightning.optimizers import OneCycleSchedulerConfig
from aria_nbv.lightning.qh_datamodule import QhDataModule
from aria_nbv.lightning.qh_module import QhLightningModule, QhLightningModuleConfig
from aria_nbv.vin.models.target_finite_horizon import MultiStepCandidateScorerConfig
from tests.data_handling.test_qh import _chain, _StaticDataset


def _data() -> QhDataModule:
    samples = [_chain(steps=2, width=2, offset=offset) for offset in (0, 10, 20, 30)]
    return QhDataModule(
        train=_StaticDataset(samples, scene="train-scene"),
        batch_size=2,
        seed=29,
    )


class _RecordingQhModule(QhLightningModule):
    def __init__(self, config: QhLightningModuleConfig) -> None:
        super().__init__(config)
        self.sample_stream: list[tuple[int, ...]] = []

    def training_step(self, batch, batch_idx):
        self.sample_stream.append(tuple(value.rollout_row_id for value in batch.lineage))
        return super().training_step(batch, batch_idx)


def _module() -> _RecordingQhModule:
    return _RecordingQhModule(
        QhLightningModuleConfig(
            scorer=MultiStepCandidateScorerConfig(candidate_token_dim=16, num_heads=4),
            lr_scheduler=OneCycleSchedulerConfig(max_lr=1e-3, pct_start=0.5),
            target_sync_interval=3,
        )
    )


def _trainer(root: Path, *, max_steps: int, checkpoint_after_first_epoch: bool = False) -> pl.Trainer:
    callbacks = []
    if checkpoint_after_first_epoch:
        callbacks.append(
            ModelCheckpoint(
                dirpath=root / "checkpoints",
                filename="epoch={epoch}-step={step}",
                every_n_epochs=1,
                save_top_k=-1,
                save_on_train_epoch_end=True,
                auto_insert_metric_name=False,
            )
        )
    return pl.Trainer(
        accelerator="cpu",
        devices=1,
        max_steps=max_steps,
        max_epochs=max_steps + 1,
        default_root_dir=root,
        logger=False,
        enable_checkpointing=checkpoint_after_first_epoch,
        callbacks=callbacks,
        enable_model_summary=False,
        use_distributed_sampler=True,
        deterministic=True,
    )


def test_resume_matches_uninterrupted_online_target_and_sync_state(tmp_path: Path) -> None:
    pl.seed_everything(31, workers=True)
    reference = _module()
    reference_trainer = _trainer(tmp_path / "reference", max_steps=4, checkpoint_after_first_epoch=True)
    reference_trainer.fit(reference, datamodule=_data())
    checkpoint = tmp_path / "reference" / "checkpoints" / "epoch=0-step=2.ckpt"
    assert checkpoint.is_file()

    pl.seed_everything(999, workers=True)
    resumed = _module()
    resumed_trainer = _trainer(tmp_path / "resumed", max_steps=4)
    resumed_trainer.fit(resumed, datamodule=_data(), ckpt_path=checkpoint)

    assert reference_trainer.global_step == resumed_trainer.global_step == 4
    assert reference.optimizer_updates.item() == resumed.optimizer_updates.item() == 4
    assert reference.target_syncs.item() == resumed.target_syncs.item() == 1
    assert reference.sample_stream[:2] + resumed.sample_stream == reference.sample_stream
    for name, expected in reference.state_dict().items():
        actual = resumed.state_dict()[name]
        assert torch.allclose(actual, expected, atol=1e-5, rtol=1e-5), (
            name,
            (actual - expected).abs().max().item(),
        )
    reference_optimizer = reference_trainer.optimizers[0].state_dict()
    resumed_optimizer = resumed_trainer.optimizers[0].state_dict()
    assert reference_optimizer["param_groups"] == resumed_optimizer["param_groups"]
    assert reference_optimizer["state"].keys() == resumed_optimizer["state"].keys()
    for parameter_id, expected_state in reference_optimizer["state"].items():
        actual_state = resumed_optimizer["state"][parameter_id]
        for key, expected in expected_state.items():
            actual = actual_state[key]
            if torch.is_tensor(expected):
                assert torch.allclose(actual, expected, atol=1e-5, rtol=1e-5), (parameter_id, key)
            else:
                assert actual == expected
    reference_scheduler = reference_trainer.lr_scheduler_configs[0].scheduler
    resumed_scheduler = resumed_trainer.lr_scheduler_configs[0].scheduler
    assert reference_scheduler.state_dict() == resumed_scheduler.state_dict()
    assert reference_trainer.optimizers[0].param_groups[0]["lr"] == pytest.approx(
        resumed_trainer.optimizers[0].param_groups[0]["lr"]
    )


def test_corrupt_resume_checkpoint_fails_closed(tmp_path: Path) -> None:
    checkpoint = tmp_path / "corrupt.ckpt"
    checkpoint.write_bytes(b"not a Lightning checkpoint")

    with pytest.raises((pickle.UnpicklingError, RuntimeError, EOFError)):
        _trainer(tmp_path / "corrupt-run", max_steps=1).fit(
            _module(),
            datamodule=_data(),
            ckpt_path=checkpoint,
        )
