"""External TorchRun smoke tests for exact two-rank Q_H transactions."""

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

from aria_nbv.data_handling.qh import QhChain
from aria_nbv.lightning.qh_datamodule import QhDataModule
from aria_nbv.lightning.qh_module import QhLightningModule, QhLightningModuleConfig
from tests.data_handling.test_qh import _chain
from tests.lightning.test_qh_fast_dev_run import _trainer
from tests.lightning.test_qh_module import _ChainDataset, _TableScorer


def _run_torchrun(output_dir: Path, scenario: str) -> list[dict[str, object]]:
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


def _fit_control(chains: list[QhChain], *, batch_size: int) -> dict[str, torch.Tensor]:
    pl.seed_everything(123, workers=True)
    module = QhLightningModule(
        QhLightningModuleConfig(lr_scheduler=None, target_sync_interval=3),
        scorer=_TableScorer(),
    )
    data = QhDataModule(
        train=_ChainDataset(chains),
        batch_size=batch_size,
        seed=43,
    )
    trainer = _trainer(
        fast_dev_run=False,
        max_epochs=1,
        deterministic=True,
    )
    trainer.fit(module, datamodule=data)
    return module.state_dict()


def test_two_process_global_empty_batch_is_complete_noop(tmp_path: Path) -> None:
    payloads = _run_torchrun(tmp_path, "global-empty")

    assert {payload["global_step"] for payload in payloads} == {0}
    assert {payload["optimizer_updates"] for payload in payloads} == {0}
    assert {payload["training_row_count"] for payload in payloads} == {0}
    assert {payload["online_scorer_calls"] for payload in payloads} == {0}
    assert {payload["target_scorer_calls"] for payload in payloads} == {0}
    assert {payload["log_calls"] for payload in payloads} == {0}
    assert {payload["state_unchanged"] for payload in payloads} == {True}


def test_two_process_local_empty_rank_matches_single_rank_update(tmp_path: Path) -> None:
    payloads = _run_torchrun(tmp_path, "local-empty")

    one_fields = ("global_step", "optimizer_updates", "online_scorer_calls", "target_scorer_calls")
    assert all({payload[field] for payload in payloads} == {1} for field in one_fields)
    assert sorted(payload["training_row_count"] for payload in payloads) == [0, 2]
    rank_states = [torch.load(tmp_path / f"rank-{rank}-state.pt", weights_only=True) for rank in range(2)]
    for name in rank_states[0]:
        assert torch.equal(rank_states[0][name], rank_states[1][name])

    for name, expected in _fit_control([_chain(steps=2, width=2)], batch_size=1).items():
        assert torch.allclose(rank_states[0][name], expected, atol=1e-6, rtol=1e-6), name


def test_two_process_unsupported_backup_metrics_are_global(tmp_path: Path) -> None:
    payloads = _run_torchrun(tmp_path, "unsupported-metric")

    assert {payload["unsupported_backup_rows"] for payload in payloads} == {1.0}
    assert all(float(payload["unsupported_backup_fraction"]) == pytest.approx(1.0 / 3.0) for payload in payloads)


@pytest.mark.parametrize("scenario", ["distributed-val", "distributed-test"])
def test_two_process_evaluation_fails_before_scorer_or_logging(tmp_path: Path, scenario: str) -> None:
    payloads = _run_torchrun(tmp_path, scenario)

    assert {payload["world_size"] for payload in payloads} == {2}
    assert all("single-device" in str(payload["error"]) for payload in payloads)
    assert all(
        {payload[field] for payload in payloads} == {0}
        for field in ("online_scorer_calls", "target_scorer_calls", "log_calls")
    )


def test_two_process_unequal_counts_match_exact_global_mean_update(tmp_path: Path) -> None:
    payloads = _run_torchrun(tmp_path, "unequal")

    assert sorted(payload["training_row_count"] for payload in payloads) == [1, 2]
    rank_states = [torch.load(tmp_path / f"rank-{rank}-state.pt", weights_only=True) for rank in range(2)]
    for name in rank_states[0]:
        assert torch.equal(rank_states[0][name], rank_states[1][name])

    one_admitted = _chain(steps=2, width=2)
    labels = one_admitted.supervision.label_mask.clone()
    labels[1, one_admitted.supervision.selected_index[1]] = False
    one_admitted = replace(one_admitted, supervision=replace(one_admitted.supervision, label_mask=labels))
    control_state = _fit_control([one_admitted, _chain(steps=2, width=2, offset=10)], batch_size=2)
    for name, expected in control_state.items():
        assert torch.allclose(rank_states[0][name], expected, atol=1e-6, rtol=1e-6), name
