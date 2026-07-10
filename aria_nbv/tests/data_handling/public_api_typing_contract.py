"""Mypy contract for typed ``aria_nbv.data_handling`` root exports.

This module is intentionally not named ``test_*`` because it is a static typing
contract, not a runtime pytest case. Run it with:

```
uv run mypy tests/data_handling/public_api_typing_contract.py
```
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

from aria_nbv.data_handling import (
    DEFAULT_VIN_SNIPPET_PAD_POINTS,
    OFFLINE_DATASET_VERSION,
    CompactObbBlock,
    CompactTrajectoryBlock,
    MeshProcessSpec,
    NumericSummary,
    OfflineVisualInventory,
    OfflineVisualInventoryError,
    ProcessedMesh,
    VinDatasetSourceConfig,
    VinOfflineBackboneDiagnostic,
    VinOfflineBlockDiagnostic,
    VinOfflineCoverageSceneDiagnostic,
    VinOfflineCoverageStats,
    VinOfflineDataset,
    VinOfflineDatasetConfig,
    VinOfflineDatasetStats,
    VinOfflineIndexRecord,
    VinOfflineManifest,
    VinOfflineMaterializedBlocks,
    VinOfflineMemoryDiagnostic,
    VinOfflineSample,
    VinOfflineSampleDiagnostic,
    VinOfflineSourceConfig,
    VinOfflineStoreConfig,
    VinOfflineWriter,
    VinOfflineWriterConfig,
    VinOracleBatch,
    VinOracleDatasetBase,
    VinOracleOnlineDataset,
    VinOracleOnlineDatasetConfig,
    VinSnippetView,
    build_vin_snippet_view,
    collect_offline_visual_inventory,
    collect_vin_offline_dataset_coverage,
    collect_vin_offline_dataset_stats,
    empty_vin_snippet,
    flush_prepared_samples_to_shard,
    load_or_process_mesh,
    prepare_vin_offline_sample,
)

RootExportClasses: TypeAlias = tuple[
    type[CompactObbBlock],
    type[CompactTrajectoryBlock],
    type[MeshProcessSpec],
    type[NumericSummary],
    type[OfflineVisualInventory],
    type[OfflineVisualInventoryError],
    type[ProcessedMesh],
    type[VinOfflineBackboneDiagnostic],
    type[VinOfflineBlockDiagnostic],
    type[VinOfflineCoverageSceneDiagnostic],
    type[VinOfflineCoverageStats],
    type[VinOfflineDataset],
    type[VinOfflineDatasetConfig],
    type[VinOfflineDatasetStats],
    type[VinOfflineIndexRecord],
    type[VinOfflineManifest],
    type[VinOfflineMaterializedBlocks],
    type[VinOfflineMemoryDiagnostic],
    type[VinOfflineSample],
    type[VinOfflineSampleDiagnostic],
    type[VinOfflineSourceConfig],
    type[VinOfflineStoreConfig],
    type[VinOfflineWriter],
    type[VinOfflineWriterConfig],
    type[VinOracleBatch],
    type[VinOracleDatasetBase],
    type[VinOracleOnlineDataset],
    type[VinOracleOnlineDatasetConfig],
]

ROOT_EXPORT_CLASSES: RootExportClasses = (
    CompactObbBlock,
    CompactTrajectoryBlock,
    MeshProcessSpec,
    NumericSummary,
    OfflineVisualInventory,
    OfflineVisualInventoryError,
    ProcessedMesh,
    VinOfflineBackboneDiagnostic,
    VinOfflineBlockDiagnostic,
    VinOfflineCoverageSceneDiagnostic,
    VinOfflineCoverageStats,
    VinOfflineDataset,
    VinOfflineDatasetConfig,
    VinOfflineDatasetStats,
    VinOfflineIndexRecord,
    VinOfflineManifest,
    VinOfflineMaterializedBlocks,
    VinOfflineMemoryDiagnostic,
    VinOfflineSample,
    VinOfflineSampleDiagnostic,
    VinOfflineSourceConfig,
    VinOfflineStoreConfig,
    VinOfflineWriter,
    VinOfflineWriterConfig,
    VinOracleBatch,
    VinOracleDatasetBase,
    VinOracleOnlineDataset,
    VinOracleOnlineDatasetConfig,
)

DEFAULT_PAD_POINTS: int = DEFAULT_VIN_SNIPPET_PAD_POINTS
DATASET_VERSION: int = OFFLINE_DATASET_VERSION

BUILD_VIN_SNIPPET: Callable[..., VinSnippetView] = build_vin_snippet_view
EMPTY_VIN_SNIPPET: Callable[..., VinSnippetView] = empty_vin_snippet
LOAD_MESH: Callable[..., ProcessedMesh] = load_or_process_mesh
COLLECT_INVENTORY: Callable[..., OfflineVisualInventory] = collect_offline_visual_inventory
COLLECT_COVERAGE: Callable[..., VinOfflineCoverageStats] = collect_vin_offline_dataset_coverage
COLLECT_STATS: Callable[..., VinOfflineDatasetStats] = collect_vin_offline_dataset_stats
FLUSH_SHARD: Callable[..., object] = flush_prepared_samples_to_shard
PREPARE_SAMPLE: Callable[..., object] = prepare_vin_offline_sample


def accepts_source_config(config: VinDatasetSourceConfig) -> VinDatasetSourceConfig:
    """Require the package-root source-config alias to be valid as a type."""
    return config
