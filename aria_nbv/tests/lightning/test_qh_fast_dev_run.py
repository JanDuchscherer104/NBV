"""Real Trainer smoke for the dedicated Q_H stack."""

# ruff: noqa: S101

import pytorch_lightning as pl

from aria_nbv.lightning.qh_data import QhDataModule
from aria_nbv.lightning.qh_module import QhLightningModule, QhLightningModuleConfig
from aria_nbv.vin.models.target_finite_horizon import MultiStepCandidateScorerConfig
from tests.lightning.test_qh_data import _dataset, _StaticDataset


def test_cpu_fast_dev_run_executes_real_qh_batch() -> None:
    source, _ = _dataset()
    train = _StaticDataset((source[0], source[1]), "train-scene")
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
        use_distributed_sampler=False,
    )

    trainer.fit(module, datamodule=data)

    assert trainer.global_step == 1
    assert module.optimizer_updates.item() == 1
