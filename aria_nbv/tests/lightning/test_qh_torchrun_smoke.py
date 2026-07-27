"""External TorchRun attachment smoke for one-node Q_H DDP."""

# ruff: noqa: S101

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
import pytorch_lightning as pl
import torch

from aria_nbv.lightning.qh_datamodule import QhDataModule
from aria_nbv.lightning.qh_module import QhLightningModule, QhLightningModuleConfig
from aria_nbv.vin.models.target_finite_horizon import MultiStepCandidateScorerConfig
from tests.data_handling.test_qh import _chain, _StaticDataset
from tests.lightning.test_qh_module import _TableScorer


def _run_torchrun(output_dir: Path, scenario: str = "standard") -> list[dict[str, object]]:
    package_root = Path(__file__).resolve().parents[2]
    torchrun = Path(sys.executable).with_name("torchrun")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(package_root)
    completed = subprocess.run(
        [
            str(torchrun),
            "--standalone",
            "--nproc_per_node=2",
            "--module",
            "tests.lightning.qh_torchrun_worker",
            "--output-dir",
            str(output_dir),
            "--scenario",
            scenario,
        ],
        cwd=package_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return [json.loads((output_dir / f"rank-{rank}.json").read_text()) for rank in range(2)]


def _module() -> QhLightningModule:
    return QhLightningModule(
        QhLightningModuleConfig(
            scorer=MultiStepCandidateScorerConfig(candidate_token_dim=16, num_heads=4),
            lr_scheduler=None,
            target_sync_interval=3,
        )
    )


def _table_module() -> QhLightningModule:
    return QhLightningModule(
        QhLightningModuleConfig(lr_scheduler=None, target_sync_interval=3),
        scorer=_TableScorer(),
    )


def test_two_process_cpu_gloo_training_is_rank_disjoint_and_single_writer(tmp_path: Path) -> None:
    payloads = _run_torchrun(tmp_path)
    assert {payload["world_size"] for payload in payloads} == {2}
    assert {payload["epoch"] for payload in payloads} == {1}
    assert {payload["global_step"] for payload in payloads} == {4}
    assert {payload["validation_row_count"] for payload in payloads} == {4}
    assert {payload["validation_admitted_rows"] for payload in payloads} == {8}
    assert payloads[0]["validation_loss"] == pytest.approx(payloads[1]["validation_loss"])
    assert set(payloads[0]["indices"]).isdisjoint(payloads[1]["indices"])
    assert sorted(payloads[0]["indices"] + payloads[1]["indices"]) == [0, 1, 2, 3]
    assert len(list((tmp_path / "checkpoints").glob("*.ckpt"))) == 2

    module = _module()
    module.load_state_dict(torch.load(tmp_path / "rank-0-state.pt", weights_only=True))
    data = QhDataModule(
        train=_StaticDataset([_chain(steps=2, width=2)], scene="train-scene"),
        val=_StaticDataset(
            [_chain(steps=2, width=2, offset=10) for _ in range(3)],
            scene="val-scene",
        ),
        batch_size=1,
        seed=43,
    )
    trainer = pl.Trainer(
        accelerator="cpu",
        devices=1,
        logger=False,
        enable_checkpointing=False,
        enable_model_summary=False,
        use_distributed_sampler=True,
    )
    single_rank_loss = trainer.validate(module, datamodule=data, verbose=False)[0]["val/loss"]
    assert payloads[0]["validation_loss"] == pytest.approx(single_rank_loss)


def test_two_process_global_empty_batch_is_a_complete_noop(tmp_path: Path) -> None:
    payloads = _run_torchrun(tmp_path, "global-empty")

    assert {payload["global_step"] for payload in payloads} == {0}
    assert {payload["optimizer_updates"] for payload in payloads} == {0}
    assert {payload["target_syncs"] for payload in payloads} == {0}
    assert {payload["training_row_count"] for payload in payloads} == {0}


def test_two_process_local_empty_rank_matches_single_rank_admitted_update(tmp_path: Path) -> None:
    payloads = _run_torchrun(tmp_path, "local-empty")

    assert {payload["global_step"] for payload in payloads} == {1}
    assert {payload["optimizer_updates"] for payload in payloads} == {1}
    assert sorted(payload["training_row_count"] for payload in payloads) == [0, 2]
    rank_states = [torch.load(tmp_path / f"rank-{rank}-state.pt", weights_only=True) for rank in range(2)]
    for name in rank_states[0]:
        assert torch.equal(rank_states[0][name], rank_states[1][name])

    pl.seed_everything(123, workers=True)
    control = _module()
    data = QhDataModule(
        train=_StaticDataset([_chain(steps=2, width=2)], scene="train-scene"),
        batch_size=1,
        seed=43,
    )
    trainer = pl.Trainer(
        accelerator="cpu",
        devices=1,
        max_epochs=1,
        logger=False,
        enable_checkpointing=False,
        enable_model_summary=False,
        use_distributed_sampler=True,
        deterministic=True,
    )
    trainer.fit(control, datamodule=data)
    for name, expected in control.state_dict().items():
        assert torch.allclose(rank_states[0][name], expected, atol=1e-6, rtol=1e-6), name


def test_two_process_unequal_transition_counts_match_exact_global_mean_update(tmp_path: Path) -> None:
    payloads = _run_torchrun(tmp_path, "unequal")

    assert sorted(payload["training_row_count"] for payload in payloads) == [1, 2]
    rank_states = [torch.load(tmp_path / f"rank-{rank}-state.pt", weights_only=True) for rank in range(2)]
    for name in rank_states[0]:
        assert torch.equal(rank_states[0][name], rank_states[1][name])

    one_admitted = _chain(steps=2, width=2)
    one_admitted = replace(
        one_admitted,
        supervision=replace(one_admitted.supervision, row_train_mask=torch.tensor([True, False])),
    )
    pl.seed_everything(123, workers=True)
    control = _table_module()
    data = QhDataModule(
        train=_StaticDataset([one_admitted, _chain(steps=2, width=2, offset=10)], scene="train-scene"),
        batch_size=2,
        seed=43,
    )
    trainer = pl.Trainer(
        accelerator="cpu",
        devices=1,
        max_epochs=1,
        logger=False,
        enable_checkpointing=False,
        enable_model_summary=False,
        use_distributed_sampler=True,
        deterministic=True,
    )
    trainer.fit(control, datamodule=data)
    for name, expected in control.state_dict().items():
        assert torch.allclose(rank_states[0][name], expected, atol=1e-6, rtol=1e-6), name
