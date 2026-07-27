"""Real Trainer and installed-CLI smoke tests for the dedicated Q_H stack."""

# ruff: noqa: S101

from pathlib import Path

import pytest
import pytorch_lightning as pl

from aria_nbv.lightning import qh_cli
from aria_nbv.lightning.qh_datamodule import QhDataModule, QhDataModuleConfig
from aria_nbv.lightning.qh_module import QhLightningModule, QhLightningModuleConfig
from aria_nbv.vin.models.target_finite_horizon import MultiStepCandidateScorerConfig
from tests.data_handling.test_qh import _chain, _StaticDataset


def test_cpu_fast_dev_run_executes_real_qh_batch() -> None:
    train = _StaticDataset(
        [_chain(steps=2, width=2), _chain(steps=2, width=2, offset=10)],
        scene="train-scene",
    )
    data = QhDataModule(train=train, batch_size=2, seed=17)
    module = QhLightningModule(
        QhLightningModuleConfig(
            scorer=MultiStepCandidateScorerConfig(candidate_token_dim=16, num_heads=4),
            target_sync_interval=2,
        )
    )
    trainer = pl.Trainer(
        accelerator="cpu",
        devices=1,
        fast_dev_run=True,
        logger=False,
        enable_checkpointing=False,
        enable_model_summary=False,
        use_distributed_sampler=True,
    )

    trainer.fit(module, datamodule=data)

    assert trainer.global_step == 1
    assert module.optimizer_updates.item() == 1


def test_cli_executes_real_fast_dev_fit_through_experiment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise strict TOML -> CLI -> experiment -> real Lightning fit."""

    data = QhDataModule(
        train=_StaticDataset(
            [_chain(steps=2, width=2), _chain(steps=2, width=2, offset=10)],
            scene="train-scene",
        ),
        batch_size=2,
        seed=17,
    )
    monkeypatch.setattr(QhDataModuleConfig, "setup_target", lambda self, *, seed: data)
    config_path = tmp_path / "qh-fast-dev.toml"
    config_path.write_text(
        f"""
seed = 17
stage = "train"
out_dir = "{tmp_path / "run"}"

[trainer_config]
accelerator = "cpu"
devices = 1
fast_dev_run = true
use_distributed_sampler = true
gradient_clip_val = 0
accumulate_grad_batches = 1
use_wandb = false
enable_model_summary = false

[trainer_config.callbacks]
use_model_checkpoint = false
use_lr_monitor = false

[datamodule_config]
batch_size = 2
[datamodule_config.train.rollout]
store_dirs = ["{tmp_path / "unused-rollouts"}"]
[datamodule_config.train.actor]
store_dir = "{tmp_path / "unused-vin"}"

[module_config]
target_sync_interval = 2
[module_config.scorer]
candidate_token_dim = 16
num_heads = 4
"""
    )

    qh_cli.main(["--config-path", str(config_path)])

    assert (tmp_path / "run" / "run_manifest.json").is_file()
