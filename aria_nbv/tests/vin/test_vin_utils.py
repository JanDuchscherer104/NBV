"""Tests for VIN diagnostics helpers."""

# ruff: noqa: S101

from __future__ import annotations

from pathlib import Path

from aria_nbv.app.panels.vin_utils import _build_experiment_config
from aria_nbv.data_handling.offline.source import VinOfflineSourceConfig
from aria_nbv.oracle.pipelines.online_vin import VinOracleOnlineDatasetConfig
from aria_nbv.utils import Stage


def test_build_experiment_config_defaults_to_online_source() -> None:
    cfg = _build_experiment_config(toml_path=None, stage=Stage.TRAIN)

    assert cfg.run_mode == "summarize_vin"
    assert cfg.stage is Stage.TRAIN
    assert cfg.trainer_config.use_wandb is False
    assert cfg.datamodule_config.num_workers == 0
    assert cfg.datamodule_config.batch_size is None
    assert isinstance(cfg.datamodule_config.source, VinOracleOnlineDatasetConfig)


def test_build_experiment_config_preserves_toml_source() -> None:
    toml_path = Path(__file__).resolve().parents[3] / ".configs" / "offline_only.toml"
    cfg = _build_experiment_config(toml_path=str(toml_path), stage=Stage.VAL)

    assert cfg.run_mode == "summarize_vin"
    assert cfg.stage is Stage.VAL
    assert cfg.trainer_config.use_wandb is False
    assert isinstance(cfg.datamodule_config.source, VinOfflineSourceConfig)
    assert cfg.module_config.vin.apply_cw90_correction is False
