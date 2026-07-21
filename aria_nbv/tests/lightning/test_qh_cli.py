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


def test_cli_loads_toml_and_applies_explicit_resume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "qh.toml"
    resume = tmp_path / "resume.ckpt"
    config_path.write_text(
        """
[trainer]
use_distributed_sampler = false
use_wandb = false
[data]
[data.train.rollout]
store_dirs = ["/tmp/rollouts"]
[data.train.actor.store]
store_dir = "/tmp/vin"
"""
    )
    captured: dict[str, object] = {}

    def _run(config: QhExperimentConfig) -> None:
        captured["config"] = config

    monkeypatch.setattr(QhExperimentConfig, "run", _run)

    qh_cli.main(["--config-path", str(config_path), "--resume", str(resume)])

    loaded = captured["config"]
    assert isinstance(loaded, QhExperimentConfig)
    assert loaded.resume_checkpoint == resume
