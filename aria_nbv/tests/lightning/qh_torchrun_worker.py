"""Two-rank CPU/Gloo worker used by the Q_H TorchRun smoke test."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytorch_lightning as pl
import torch
from pytorch_lightning.callbacks import ModelCheckpoint

from aria_nbv.lightning.qh_data import QhDataModule
from aria_nbv.lightning.qh_module import QhLightningModule, QhLightningModuleConfig
from aria_nbv.vin.models.target_finite_horizon import MultiStepCandidateScorerConfig
from tests.lightning.test_qh_data import _dataset, _StaticDataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    source, _ = _dataset()
    samples = (source[0], source[1], source[0], source[1])
    data = QhDataModule(
        train=_StaticDataset(samples, "train-scene"),
        val=_StaticDataset((source[1],), "val-scene"),
        batch_size=1,
        seed=43,
    )
    module = QhLightningModule(
        QhLightningModuleConfig(
            scorer=MultiStepCandidateScorerConfig(candidate_token_dim=16, num_heads=4),
            target_sync_interval=3,
        )
    )
    callback = ModelCheckpoint(
        dirpath=args.output_dir / "checkpoints",
        filename="rank-zero-step={step}",
        every_n_train_steps=2,
        save_top_k=-1,
        save_on_train_epoch_end=False,
        auto_insert_metric_name=False,
    )
    trainer = pl.Trainer(
        accelerator="cpu",
        devices=2,
        strategy="ddp",
        max_epochs=2,
        logger=False,
        callbacks=[callback],
        enable_model_summary=False,
        use_distributed_sampler=False,
        deterministic=True,
    )
    trainer.fit(module, datamodule=data)

    sampler = data._train_sampler
    if sampler is None:
        raise RuntimeError("Q_H training sampler was not constructed.")
    payload = {
        "rank": trainer.global_rank,
        "world_size": trainer.world_size,
        "epoch": sampler.epoch,
        "indices": list(sampler),
        "global_step": trainer.global_step,
        "validation_row_count": int(module.validation_row_count.item()),
    }
    (args.output_dir / f"rank-{trainer.global_rank}.json").write_text(json.dumps(payload, sort_keys=True))
    if torch.distributed.is_initialized():
        torch.distributed.barrier()


if __name__ == "__main__":
    main()
