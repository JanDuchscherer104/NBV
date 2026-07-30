"""Two-rank CPU/Gloo worker for exact Q_H transaction regressions."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import pytorch_lightning as pl
import torch

from aria_nbv.data_handling.qh import collate_qh_chains
from aria_nbv.lightning.qh_datamodule import QhDataModule
from aria_nbv.lightning.qh_module import QhLightningModule, QhLightningModuleConfig
from tests.data_handling.test_qh import _chain
from tests.lightning.test_qh_fast_dev_run import _trainer
from tests.lightning.test_qh_module import _ChainDataset, _TableScorer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    scenarios = ("global-empty", "local-empty", "unequal", "distributed-val", "distributed-test")
    parser.add_argument("--scenario", choices=scenarios, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    pl.seed_everything(123, workers=True)

    if args.scenario in {"distributed-val", "distributed-test"}:
        torch.distributed.init_process_group("gloo")
        module = QhLightningModule(QhLightningModuleConfig(lr_scheduler=None), scorer=_TableScorer())
        log_calls = 0

        def _log(*args, **kwargs) -> None:
            nonlocal log_calls
            del args, kwargs
            log_calls += 1

        module.log = _log
        error: str | None = None
        try:
            step = module.validation_step if args.scenario == "distributed-val" else module.test_step
            step(collate_qh_chains([_chain(steps=2, width=3)]), 0)
        except ValueError as exc:
            error = str(exc)
        rank = torch.distributed.get_rank()
        payload = {
            "rank": rank,
            "world_size": torch.distributed.get_world_size(),
            "error": error,
            "online_scorer_calls": module.online_scorer.calls,
            "target_scorer_calls": module.target_scorer.calls,
            "log_calls": log_calls,
        }
        (args.output_dir / f"rank-{rank}.json").write_text(json.dumps(payload, sort_keys=True))
        torch.distributed.barrier()
        torch.distributed.destroy_process_group()
        return

    admitted = _chain(steps=2, width=2)
    empty = replace(
        admitted,
        supervision=replace(admitted.supervision, label_mask=torch.zeros_like(admitted.supervision.label_mask)),
    )
    if args.scenario == "global-empty":
        samples = [empty, empty]
    elif args.scenario == "local-empty":
        samples = [admitted, empty]
    else:
        one_admitted = _chain(steps=2, width=2)
        labels = one_admitted.supervision.label_mask.clone()
        labels[1, one_admitted.supervision.selected_index[1]] = False
        one_admitted = replace(one_admitted, supervision=replace(one_admitted.supervision, label_mask=labels))
        samples = [one_admitted, _chain(steps=2, width=2, offset=10)]

    data = QhDataModule(
        train=_ChainDataset(samples),
        batch_size=1,
        seed=43,
    )
    module = QhLightningModule(
        QhLightningModuleConfig(lr_scheduler=None, target_sync_interval=3),
        scorer=_TableScorer(),
    )
    initial_state = {name: value.detach().clone() for name, value in module.state_dict().items()}
    log_calls = 0
    original_log = module.log

    def _log(*args, **kwargs) -> None:
        nonlocal log_calls
        log_calls += 1
        original_log(*args, **kwargs)

    if args.scenario == "global-empty":
        module.log = _log
    trainer = _trainer(
        devices=2,
        strategy="ddp",
        fast_dev_run=False,
        max_epochs=1,
        deterministic=True,
    )
    trainer.fit(module, datamodule=data)

    payload = {
        "world_size": trainer.world_size,
        "global_step": trainer.global_step,
        "optimizer_updates": int(module.optimizer_updates.item()),
        "training_row_count": int(module.training_row_count.item()),
        "online_scorer_calls": module.online_scorer.calls,
        "target_scorer_calls": module.target_scorer.calls,
        "log_calls": log_calls,
        "state_unchanged": all(torch.equal(value, module.state_dict()[name]) for name, value in initial_state.items()),
    }
    (args.output_dir / f"rank-{trainer.global_rank}.json").write_text(json.dumps(payload, sort_keys=True))
    torch.save(module.state_dict(), args.output_dir / f"rank-{trainer.global_rank}-state.pt")
    if torch.distributed.is_initialized():
        torch.distributed.barrier()


if __name__ == "__main__":
    main()
