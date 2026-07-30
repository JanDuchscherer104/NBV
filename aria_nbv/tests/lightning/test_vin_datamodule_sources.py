"""Contracts for Lightning-owned VIN dataset-source composition."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from aria_nbv.data_handling.vin_store.source import VinOfflineSourceConfig
from aria_nbv.lightning.lit_datamodule import VinDataModuleConfig
from aria_nbv.oracle.pipelines.online_vin import VinOracleOnlineDatasetConfig


def _config_path(name: str) -> Path:
    return Path(__file__).resolve().parents[3] / ".configs" / name


def test_online_source_defaults_to_single_process_loading() -> None:
    config = VinDataModuleConfig()

    assert isinstance(config.source, VinOracleOnlineDatasetConfig)
    assert config.num_workers == 0


def test_online_source_rejects_explicit_worker_processes() -> None:
    with pytest.raises(ValueError, match="num_workers=0"):
        VinDataModuleConfig(source=VinOracleOnlineDatasetConfig(), num_workers=1)


@pytest.mark.parametrize(
    ("filename", "expected_type"),
    [
        ("online_only.toml", VinOracleOnlineDatasetConfig),
        ("offline_only.toml", VinOfflineSourceConfig),
    ],
)
def test_canonical_source_discriminators_parse(filename: str, expected_type: type[object]) -> None:
    with _config_path(filename).open("rb") as handle:
        payload = tomllib.load(handle)["datamodule_config"]
    config = VinDataModuleConfig.model_validate(payload)

    assert isinstance(config.source, expected_type)
