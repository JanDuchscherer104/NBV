"""Contracts for configured target-frame S2 evidence acquisition."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

pytest.importorskip("efm3d")

from aria_nbv.rollouts.s2_analysis import S2AnalysisConfig, acquire_s2_store_evidence
from aria_nbv.rollouts.zarr_store import write_rollout_zarr_store
from tests.rollout_fixtures import build_rollout_records


def test_s2_acquisition_binds_config_store_identity_and_payload_digest(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=2, num_samples=6, seed=41)[:1],
    )
    config = S2AnalysisConfig(azimuth_bins=12, elevation_bins=6, projection_limit=32)

    first = acquire_s2_store_evidence(result.store_dir, slot=1, config=config)
    second = acquire_s2_store_evidence(result.store_dir, slot=1, config=config)

    assert first.path == result.store_dir.resolve()
    assert first.store_id == result.manifest_sha256
    assert first.config == config
    assert first.payload_sha256 == second.payload_sha256
    assert len(first.payload_sha256) == 64
    assert first.payload["azimuth_bins"] == 12
    assert first.payload["elevation_bins"] == 6
    assert first.payload["projection_limit"] == 32


@pytest.mark.parametrize(
    ("field", "value"),
    (("azimuth_bins", 7), ("elevation_bins", 3), ("projection_limit", 0)),
)
def test_s2_analysis_config_rejects_unsupported_domains(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        S2AnalysisConfig(**{field: value})
