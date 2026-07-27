"""Two-rank CPU/Gloo worker used by the Q_H TorchRun smoke test."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import pytorch_lightning as pl
import torch
from pytorch_lightning.callbacks import ModelCheckpoint

from aria_nbv.lightning.qh_datamodule import QhDataModule
from aria_nbv.lightning.qh_module import QhLightningModule, QhLightningModuleConfig
from aria_nbv.vin.models.target_finite_horizon import MultiStepCandidateScorerConfig
from tests.data_handling.test_qh import _chain, _StaticDataset
from tests.lightning.test_qh_module import _TableScorer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--scenario",
        choices=("standard", "global-empty", "local-empty", "unequal"),
        default="standard",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    pl.seed_everything(123, workers=True)
    admitted = _chain(steps=2, width=2)
    empty = replace(
        admitted,
        supervision=replace(
            admitted.supervision,
            row_train_mask=torch.zeros_like(admitted.supervision.row_train_mask),
        ),
    )
    if args.scenario == "standard":
        samples = [_chain(steps=2, width=2, offset=offset) for offset in range(4)]
        validation = _StaticDataset(
            [_chain(steps=2, width=2, offset=10) for _ in range(3)],
            scene="val-scene",
        )
        max_epochs = 2
    elif args.scenario == "global-empty":
        samples = [empty, empty]
        validation = None
        max_epochs = 1
    elif args.scenario == "local-empty":
        samples = [admitted, empty]
        validation = None
        max_epochs = 1
    else:
        one_admitted = replace(
            _chain(steps=2, width=2),
            supervision=replace(
                admitted.supervision,
                row_train_mask=torch.tensor([True, False]),
            ),
        )
        samples = [one_admitted, _chain(steps=2, width=2, offset=10)]
        validation = None
        max_epochs = 1
    data = QhDataModule(
        train=_StaticDataset(samples, scene="train-scene"),
        val=validation,
        batch_size=1,
        seed=43,
    )
    module = QhLightningModule(
        QhLightningModuleConfig(
            scorer=MultiStepCandidateScorerConfig(candidate_token_dim=16, num_heads=4),
            lr_scheduler=None,
            target_sync_interval=3,
        ),
        scorer=_TableScorer() if args.scenario == "unequal" else None,
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
        use_distributed_sampler=True,
        deterministic=True,
    )
    trainer.fit(module, datamodule=data)

    sampler = trainer.train_dataloader.sampler
    payload = {
        "rank": trainer.global_rank,
        "world_size": trainer.world_size,
        "epoch": getattr(sampler, "epoch", 0),
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
