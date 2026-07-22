"""Full-state resume parity for fitted Q_H training."""

# ruff: noqa: S101

import pickle
from pathlib import Path

import pytest
import pytorch_lightning as pl
import torch
from pytorch_lightning.callbacks import ModelCheckpoint

from aria_nbv.data_handling.qh import QhCorpus
from aria_nbv.lightning.qh_datamodule import QhDataModule
from aria_nbv.lightning.qh_module import QhLightningModule, QhLightningModuleConfig
from aria_nbv.vin.models.target_finite_horizon import MultiStepCandidateScorerConfig
from tests.data_handling.test_qh import _dataset, _StaticDataset


def _data() -> QhDataModule:
    source, _ = _dataset()
    samples = (source[0], source[1], source[0], source[1])
    return QhDataModule(
        QhCorpus.admit(train=_StaticDataset(samples, "train-scene")),
        batch_size=2,
        seed=29,
    )


def _module() -> QhLightningModule:
    return QhLightningModule(
        QhLightningModuleConfig(
            scorer=MultiStepCandidateScorerConfig(candidate_token_dim=16, num_heads=4),
            target_sync_interval=3,
        )
    )


def _trainer(root: Path, *, max_steps: int, checkpoint_every_two_steps: bool = False) -> pl.Trainer:
    callbacks = []
    if checkpoint_every_two_steps:
        callbacks.append(
            ModelCheckpoint(
                dirpath=root / "checkpoints",
                filename="step={step}",
                every_n_train_steps=2,
                save_top_k=-1,
                save_on_train_epoch_end=False,
                auto_insert_metric_name=False,
            )
        )
    return pl.Trainer(
        accelerator="cpu",
        devices=1,
        max_steps=max_steps,
        max_epochs=4,
        default_root_dir=root,
        logger=False,
        enable_checkpointing=checkpoint_every_two_steps,
        callbacks=callbacks,
        enable_model_summary=False,
        use_distributed_sampler=False,
        deterministic=True,
    )


def test_resume_matches_uninterrupted_online_target_and_sync_state(tmp_path: Path) -> None:
    pl.seed_everything(31, workers=True)
    reference = _module()
    reference_trainer = _trainer(tmp_path / "reference", max_steps=4, checkpoint_every_two_steps=True)
    reference_trainer.fit(reference, datamodule=_data())
    checkpoint = tmp_path / "reference" / "checkpoints" / "step=2.ckpt"
    assert checkpoint.is_file()

    pl.seed_everything(999, workers=True)
    resumed = _module()
    resumed_trainer = _trainer(tmp_path / "resumed", max_steps=4)
    resumed_trainer.fit(resumed, datamodule=_data(), ckpt_path=checkpoint)

    assert reference_trainer.global_step == resumed_trainer.global_step == 4
    assert reference.optimizer_updates.item() == resumed.optimizer_updates.item() == 4
    assert reference.target_syncs.item() == resumed.target_syncs.item() == 1
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


def test_corrupt_resume_checkpoint_fails_closed(tmp_path: Path) -> None:
    checkpoint = tmp_path / "corrupt.ckpt"
    checkpoint.write_bytes(b"not a Lightning checkpoint")

    with pytest.raises((pickle.UnpicklingError, RuntimeError, EOFError)):
        _trainer(tmp_path / "corrupt-run", max_steps=1).fit(
            _module(),
            datamodule=_data(),
            ckpt_path=checkpoint,
        )
