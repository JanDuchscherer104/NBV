"""External TorchRun attachment smoke for one-node Q_H DDP."""

# ruff: noqa: S101

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def test_two_process_cpu_gloo_training_is_rank_disjoint_and_single_writer(tmp_path: Path) -> None:
    package_root = Path(__file__).resolve().parents[2]
    torchrun = Path(os.environ.get("VIRTUAL_ENV", "/home/jd/repos/ARIA-NBV/aria_nbv/.venv")) / "bin" / "torchrun"
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
            str(tmp_path),
        ],
        cwd=package_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payloads = [json.loads((tmp_path / f"rank-{rank}.json").read_text()) for rank in range(2)]
    assert {payload["world_size"] for payload in payloads} == {2}
    assert {payload["epoch"] for payload in payloads} == {1}
    assert {payload["global_step"] for payload in payloads} == {4}
    assert {payload["validation_row_count"] for payload in payloads} == {1}
    assert set(payloads[0]["indices"]).isdisjoint(payloads[1]["indices"])
    assert sorted(payloads[0]["indices"] + payloads[1]["indices"]) == [0, 1, 2, 3]
    assert len(list((tmp_path / "checkpoints").glob("*.ckpt"))) == 2
