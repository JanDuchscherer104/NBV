"""Two-rank CPU/Gloo worker used by the Q_H TorchRun smoke test."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import pytorch_lightning as pl
import torch
from pytorch_lightning.callbacks import ModelCheckpoint

from aria_nbv.data_handling.qh import QhCorpus
from aria_nbv.lightning.qh_datamodule import QhDataModule
from aria_nbv.lightning.qh_module import QhLightningModule, QhLightningModuleConfig
from aria_nbv.vin.models.target_finite_horizon import MultiStepCandidateScorerConfig
from tests.data_handling.test_qh import _dataset, _StaticDataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--scenario",
        choices=("standard", "global-empty", "local-empty"),
        default="standard",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    pl.seed_everything(123, workers=True)
    source, _ = _dataset()
    admitted = source[1]
    empty = replace(
        admitted,
        transition=replace(admitted.transition, row_train_mask=torch.tensor(False)),
    )
    if args.scenario == "standard":
        samples = (source[0], source[1], source[0], source[1])
        validation = _StaticDataset((source[1], source[1], source[1]), "val-scene")
        max_epochs = 2
    elif args.scenario == "global-empty":
        samples = (empty, empty)
        validation = None
        max_epochs = 1
    else:
        samples = (admitted, empty)
        validation = None
        max_epochs = 1
    data = QhDataModule(
        QhCorpus.admit(
            train=_StaticDataset(samples, "train-scene"),
            val=validation,
        ),
        batch_size=1,
        seed=43,
    )
    module = QhLightningModule(
        QhLightningModuleConfig(
            scorer=MultiStepCandidateScorerConfig(candidate_token_dim=16, num_heads=4),
            target_sync_interval=3,
        )
    )
    callbacks = []
    if args.scenario == "standard":
        callbacks.append(
            ModelCheckpoint(
                dirpath=args.output_dir / "checkpoints",
                filename="rank-zero-step={step}",
                every_n_train_steps=2,
                save_top_k=-1,
                save_on_train_epoch_end=False,
                auto_insert_metric_name=False,
            )
        )
    trainer = pl.Trainer(
        accelerator="cpu",
        devices=2,
        strategy="ddp",
        max_epochs=max_epochs,
        logger=False,
        callbacks=callbacks,
        enable_checkpointing=bool(callbacks),
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
        "optimizer_updates": int(module.optimizer_updates.item()),
        "target_syncs": int(module.target_syncs.item()),
        "training_row_count": int(module.training_row_count.item()),
        "validation_row_count": int(module.validation_row_count.item()),
        "validation_loss": float(trainer.callback_metrics.get("val/loss", torch.tensor(float("nan"))).item()),
    }
    (args.output_dir / f"rank-{trainer.global_rank}.json").write_text(json.dumps(payload, sort_keys=True))
    torch.save(module.state_dict(), args.output_dir / f"rank-{trainer.global_rank}-state.pt")
    if torch.distributed.is_initialized():
        torch.distributed.barrier()


if __name__ == "__main__":
    main()
