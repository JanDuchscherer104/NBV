"""Regression tests for the canonical VIN campaign-store contract."""

from __future__ import annotations

import tomllib
from pathlib import Path

from aria_nbv.data_handling.vin_store.store import OFFLINE_DATASET_VERSION


def test_canonical_campaign_store_matches_reader_version() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    config = tomllib.loads(
        (repo_root / ".configs" / "build_rollouts_v1_cuda_campaign_writer.toml").read_text(encoding="utf-8")
    )
    expected = str(OFFLINE_DATASET_VERSION)
    assert config["store"]["source_offline_store_version"] == expected  # noqa: S101
    assert f"_v{expected}_" in config["source"]["store"]["store_dir"]  # noqa: S101
