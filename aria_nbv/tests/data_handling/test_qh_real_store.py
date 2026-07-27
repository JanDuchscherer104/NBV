"""Read-only admission evidence for the incompatible June 2026 rollout store."""

# ruff: noqa: S101

from __future__ import annotations

import os
from pathlib import Path

import pytest
import zarr

from aria_nbv.data_handling.offline.store import VinOfflineStoreConfig
from aria_nbv.data_handling.qh import QhDatasetConfig
from aria_nbv.rollouts.qh_reader import QhRolloutReaderConfig

ROLLOUT_ENV = "ARIA_QH_REAL_ROLLOUT_STORE"
VIN_ENV = "ARIA_QH_REAL_VIN_STORE"


def _required_store(name: str) -> Path:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"Set {name} to run the immutable real-store admission check.")
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        pytest.fail(f"{name} does not identify an immutable store directory: {path}")
    return path


def test_real_v1_store_fails_before_actor_or_trainer_construction(
    monkeypatch: pytest.MonkeyPatch,
    record_property,
) -> None:
    """Reject ``v1_observed`` before loading VIN rows for the V0 ``Q_H`` task."""

    rollout_store = _required_store(ROLLOUT_ENV)
    vin_store = _required_store(VIN_ENV)
    actual_protocol = str(zarr.open_group(rollout_store, mode="r").attrs["target_protocol_version"])
    required_protocol = "v0_gt_input"
    rebuild_guidance = (
        "Rebuild the rollout corpus with target_protocol_version='v0_gt_input' "
        "and the canonical Oracle GT target descriptor before Q_H training."
    )
    record_property("rollout_store", str(rollout_store))
    record_property("vin_store", str(vin_store))
    record_property("actual_target_protocol", actual_protocol)
    record_property("required_target_protocol", required_protocol)
    record_property("rebuild_guidance", rebuild_guidance)
    assert actual_protocol == "v1_observed"
    assert actual_protocol != required_protocol

    def fail_actor_setup(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Protocol-incompatible rollout corpus reached VIN actor construction.")

    monkeypatch.setattr("aria_nbv.data_handling.qh.VinOfflineStoreReader", fail_actor_setup)
    config = QhDatasetConfig(
        rollout=QhRolloutReaderConfig(store_dirs=(rollout_store,)),
        actor=VinOfflineStoreConfig(store_dir=vin_store),
        split="train",
    )

    with pytest.raises(ValueError, match="v1_observed.*Oracle GT.*rebuild"):
        config.setup_target()
