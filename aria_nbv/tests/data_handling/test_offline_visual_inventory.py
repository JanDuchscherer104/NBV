"""Tests for immutable VIN offline visual-inventory diagnostics."""

from __future__ import annotations

import pytest
import torch

from aria_nbv.data_handling import VinOfflineDatasetConfig
from aria_nbv.data_handling.vin_store.inventory import (
    OfflineVisualInventory,
    OfflineVisualInventoryError,
    collect_offline_visual_inventory,
)
from tests.data_handling.test_vin_offline_store import _write_test_store


def test_collect_offline_visual_inventory_success_and_metadata(tmp_path) -> None:
    """Inventory should expose required metadata, masks, deltas, and optional warnings."""

    store_cfg = _write_test_store(tmp_path, include_backbone=True)
    dataset = VinOfflineDatasetConfig(store=store_cfg, return_format="sample", split="all").setup_target()
    sample = dataset[0]

    inventory = collect_offline_visual_inventory(sample)

    assert isinstance(inventory, OfflineVisualInventory)  # noqa: S101
    assert inventory.ok  # noqa: S101
    assert inventory.sample_key == "sample-0"  # noqa: S101
    assert inventory.sample_index == 0  # noqa: S101
    assert inventory.split == "train"  # noqa: S101
    assert inventory.scene_id == "scene-a"  # noqa: S101
    assert inventory.snippet_id == "snippet-000"  # noqa: S101
    assert inventory.candidate_count == 2  # noqa: S101
    assert inventory.candidate_width == 4  # noqa: S101
    assert inventory.candidate_valid_mask is not None  # noqa: S101
    assert inventory.candidate_valid_mask.tolist() == [True, True, False, False]  # noqa: S101
    assert inventory.accuracy_delta is not None  # noqa: S101
    assert inventory.completeness_delta is not None  # noqa: S101
    assert torch.allclose(inventory.accuracy_delta[:2], torch.full((2,), 0.05))  # noqa: S101
    assert torch.allclose(inventory.completeness_delta[:2], torch.full((2,), 0.05))  # noqa: S101
    assert inventory.has_depths  # noqa: S101
    assert inventory.has_backbone_voxel_extent  # noqa: S101
    assert inventory.has_backbone_points  # noqa: S101
    assert not inventory.has_candidates  # noqa: S101
    assert any("candidate-sampling" in warning for warning in inventory.warnings)  # noqa: S101
    assert inventory.metadata["vin_snippet.valid_semidense_points"] == 2  # noqa: S101


def test_collect_offline_visual_inventory_missing_required_fails(tmp_path) -> None:
    """Strict mode should fail with actionable field names for required data."""

    store_cfg = _write_test_store(tmp_path)
    dataset = VinOfflineDatasetConfig(store=store_cfg, return_format="sample", split="all").setup_target()
    sample = dataset[0]
    sample.oracle.rri = None  # type: ignore[assignment]

    with pytest.raises(OfflineVisualInventoryError) as exc_info:
        collect_offline_visual_inventory(sample)

    assert "sample.oracle.rri" in str(exc_info.value)  # noqa: S101

    inventory = collect_offline_visual_inventory(sample, strict=False)
    assert not inventory.ok  # noqa: S101
    assert any("sample.oracle.rri" in error for error in inventory.errors)  # noqa: S101


def test_collect_offline_visual_inventory_optional_warnings(tmp_path) -> None:
    """Missing optional visual payloads should be warnings, not required failures."""

    store_cfg = _write_test_store(tmp_path, include_backbone=False)
    dataset = VinOfflineDatasetConfig(store=store_cfg, return_format="sample", split="all").setup_target()
    sample = dataset[0]

    inventory = collect_offline_visual_inventory(sample)

    assert inventory.ok  # noqa: S101
    assert not inventory.has_candidate_pcs  # noqa: S101
    assert not inventory.has_backbone_voxel_extent  # noqa: S101
    assert any("candidate point clouds" in warning for warning in inventory.warnings)  # noqa: S101
    assert any("backbone output" in warning for warning in inventory.warnings)  # noqa: S101
