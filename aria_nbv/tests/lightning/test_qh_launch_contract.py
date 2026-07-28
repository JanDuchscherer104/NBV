"""Fail-closed tests for the one-node LRZ Q_H launcher."""

# ruff: noqa: S101

from __future__ import annotations

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "templates" / "lrz" / "qh_training_one_node.sbatch"


def _run(
    script: Path,
    *,
    gpus: str | None = "2",
    nodes: str = "1",
    image: str | None = "registry.example/aria@sha256:tested",
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if gpus is None:
        env.pop("SLURM_GPUS_ON_NODE", None)
    else:
        env["SLURM_GPUS_ON_NODE"] = gpus
    env["SLURM_JOB_NUM_NODES"] = nodes
    if image is None:
        env.pop("LRZ_CONTAINER_IMAGE", None)
    else:
        env["LRZ_CONTAINER_IMAGE"] = image
    return subprocess.run(["bash", str(script)], env=env, capture_output=True, text=True, check=False)


def test_template_is_shell_valid_and_has_one_launcher_hierarchy() -> None:
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
    text = SCRIPT.read_text()

    assert "#SBATCH --nodes=1" in text
    assert "#SBATCH --ntasks-per-node=1" in text
    assert "#SBATCH --gres=gpu:2" in text
    assert text.count("srun --ntasks=1") == 1
    assert text.count("exec uv run --frozen --no-sync torchrun --standalone") == 1
    assert "command -v uv >/dev/null" in text
    assert "test -x .venv/bin/python" in text
    assert '--nproc_per_node="$GPUS_ON_NODE"' in text
    assert "--module aria_nbv.lightning.qh_cli" in text
    assert "export ARIA_DSS ARIA_REPO QH_CONFIG GPUS_ON_NODE LRZ_CONTAINER_IMAGE" in text
    assert "throughput/smoke launcher" in text
    assert "scene-disjoint validation/test" in text
    assert "Checkpoint and target-network sync cadences are bounded" in text
    config = (SCRIPT.parents[3] / ".configs/training/qh/train_qh_v0_lrz.template.toml").read_text()
    assert "checkpoint_every_n_train_steps = 100" in config
    assert "target_sync_interval = 100" in config


def test_local_smoke_syncs_the_target_within_one_bounded_update() -> None:
    smoke = (SCRIPT.parents[3] / ".configs/training/qh/train_qh_v0_smoke.toml").read_text()

    assert "target_sync_interval = 1" in smoke


def test_template_fails_before_launch_without_nonblank_container_image() -> None:
    for image in (None, "", "   "):
        completed = _run(SCRIPT, image=image)
        assert completed.returncode == 2
        assert "LRZ_CONTAINER_IMAGE" in completed.stderr


def test_template_fails_before_launch_without_positive_gpu_count() -> None:
    for value in (None, "0", "-1", "two"):
        completed = _run(SCRIPT, gpus=value)
        assert completed.returncode == 2
        assert "positive integer" in completed.stderr


def test_template_rejects_gpu_count_that_disagrees_with_trainer_config() -> None:
    completed = _run(SCRIPT, gpus="1")

    assert completed.returncode == 2
    assert "must equal trainer.devices=2" in completed.stderr


def test_template_rejects_multi_node_and_per_gpu_task_topology(tmp_path: Path) -> None:
    multi_node = _run(SCRIPT, nodes="2")
    assert multi_node.returncode == 2
    assert "exactly one LRZ node" in multi_node.stderr

    changed = tmp_path / "per-gpu.sbatch"
    changed.write_text(SCRIPT.read_text().replace("#SBATCH --ntasks-per-node=1", "#SBATCH --ntasks-per-node=2", 1))
    completed = _run(changed)
    assert completed.returncode == 2
    assert "one node and one launcher task" in completed.stderr


def test_template_rejects_changed_or_missing_gpu_directive(tmp_path: Path) -> None:
    for replacement in ("#SBATCH --gres=gpu:4", ""):
        changed = tmp_path / f"gres-{len(replacement)}.sbatch"
        changed.write_text(SCRIPT.read_text().replace("#SBATCH --gres=gpu:2", replacement, 1))

        completed = _run(changed)

        assert completed.returncode == 2
        assert "requires exactly #SBATCH --gres=gpu:2" in completed.stderr


def test_template_rejects_duplicate_srun_or_torchrun(tmp_path: Path) -> None:
    for name, extra, message in (
        ("extra-srun.sbatch", "\nsrun true\n", "exactly one srun"),
        ("extra-torchrun.sbatch", "\ntorchrun --help\n", "exactly one torchrun"),
    ):
        changed = tmp_path / name
        changed.write_text(SCRIPT.read_text() + extra)
        completed = _run(changed)
        assert completed.returncode == 2
        assert message in completed.stderr


def test_template_rejects_bypassing_prepared_project_environment(tmp_path: Path) -> None:
    changed = tmp_path / "bare-container-torchrun.sbatch"
    changed.write_text(
        SCRIPT.read_text()
        .replace("    command -v uv >/dev/null\n", "", 1)
        .replace("    test -x .venv/bin/python\n", "", 1)
        .replace("exec uv run --frozen --no-sync torchrun", "exec torchrun", 1)
    )

    completed = _run(changed)

    assert completed.returncode == 2
    assert "prepared frozen uv environment" in completed.stderr or "exactly one torchrun" in completed.stderr
