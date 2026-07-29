"""CLI tests for the dedicated Q_H training entry point."""

# ruff: noqa: S101

from pathlib import Path

import pytest

from aria_nbv.lightning import qh_cli
from aria_nbv.lightning.qh_experiment import QhExperimentConfig


def test_help_is_available() -> None:
    with pytest.raises(SystemExit) as error:
        qh_cli.main(["--help"])

    assert error.value.code == 0


def test_cli_loads_toml_and_applies_explicit_checkpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "qh.toml"
    resume = tmp_path / "resume.ckpt"
    config_path.write_text(
        """
[trainer_config]
use_distributed_sampler = true
gradient_clip_val = 0
use_wandb = false
[datamodule_config]
[datamodule_config.train.rollout]
store_dirs = ["/tmp/rollouts"]
[datamodule_config.train.actor]
store_dir = "/tmp/vin"
"""
    )
    captured: dict[str, object] = {}

    def _run(config: QhExperimentConfig) -> None:
        captured["config"] = config

    monkeypatch.setattr(QhExperimentConfig, "setup_target_and_run", _run)

    qh_cli.main(["--config-path", str(config_path), "--ckpt-path", str(resume)])

    loaded = captured["config"]
    assert isinstance(loaded, QhExperimentConfig)
    assert loaded.ckpt_path == resume
