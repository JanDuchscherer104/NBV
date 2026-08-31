"""Mypy contract for stable root exports and specialized leaf contracts.

Run with ``uv run mypy tests/data_handling/public_api_typing_contract.py``.
"""

from __future__ import annotations

from collections.abc import Callable

from aria_nbv.data_handling import (
    AseEfmDataset,
    AseEfmDatasetConfig,
    EfmSnippetView,
    VinOfflineDataset,
    VinOfflineDatasetConfig,
    VinOfflineStoreConfig,
    VinOracleBatch,
    VinSnippetView,
)
from aria_nbv.data_handling.mesh_cache import MeshProcessSpec, ProcessedMesh, load_or_process_mesh
from aria_nbv.data_handling.vin_store.adapter import (
    DEFAULT_VIN_SNIPPET_PAD_POINTS,
    build_vin_snippet_view,
    empty_vin_snippet,
)
from aria_nbv.data_handling.vin_store.batch import CompactObbBlock, CompactTrajectoryBlock, VinOracleDatasetBase
from aria_nbv.data_handling.vin_store.diagnostics import (
    NumericSummary,
    VinOfflineBackboneDiagnostic,
    VinOfflineBlockDiagnostic,
    VinOfflineCoverageSceneDiagnostic,
    VinOfflineCoverageStats,
    VinOfflineDatasetStats,
    VinOfflineMemoryDiagnostic,
    VinOfflineSampleDiagnostic,
    collect_vin_offline_dataset_coverage,
    collect_vin_offline_dataset_stats,
)
from aria_nbv.data_handling.vin_store.format import (
    VinOfflineIndexRecord,
    VinOfflineManifest,
    VinOfflineMaterializedBlocks,
)
from aria_nbv.data_handling.vin_store.inventory import (
    OfflineVisualInventory,
    OfflineVisualInventoryError,
    collect_offline_visual_inventory,
)
from aria_nbv.data_handling.vin_store.source import VinOfflineSourceConfig
from aria_nbv.data_handling.vin_store.store import OFFLINE_DATASET_VERSION
from aria_nbv.data_handling.vin_store.writer import flush_prepared_samples_to_shard, prepare_vin_offline_sample
from aria_nbv.geometry import TargetRelativeFrame, TargetRelativeFrameDegeneracyError, TargetRelativeFrameError
from aria_nbv.lightning.lit_datamodule import VinDatasetSourceConfig
from aria_nbv.oracle.pipelines.online_vin import VinOracleOnlineDataset, VinOracleOnlineDatasetConfig
from aria_nbv.pose_generation import (
    ActorTargetContext,
    AdmissionEvidence,
    CandidateConditioning,
    CandidateGenerator,
    CandidateProgram,
    CandidateRequest,
    CandidateSet,
    CandidateTable,
    PreparedCandidateScene,
    ProgramCandidateGenerator,
)

ROOT_EXPORT_CLASSES = (
    AseEfmDataset,
    AseEfmDatasetConfig,
    EfmSnippetView,
    VinSnippetView,
    VinOracleBatch,
    VinOfflineDataset,
    VinOfflineDatasetConfig,
    VinOfflineStoreConfig,
)

LEAF_CONTRACT_CLASSES = (
    ActorTargetContext,
    AdmissionEvidence,
    CandidateConditioning,
    CandidateProgram,
    CandidateRequest,
    CandidateSet,
    CandidateTable,
    CompactObbBlock,
    CompactTrajectoryBlock,
    MeshProcessSpec,
    NumericSummary,
    OfflineVisualInventory,
    OfflineVisualInventoryError,
    ProcessedMesh,
    PreparedCandidateScene,
    ProgramCandidateGenerator,
    TargetRelativeFrame,
    TargetRelativeFrameDegeneracyError,
    TargetRelativeFrameError,
    VinOfflineBackboneDiagnostic,
    VinOfflineBlockDiagnostic,
    VinOfflineCoverageSceneDiagnostic,
    VinOfflineCoverageStats,
    VinOfflineDatasetStats,
    VinOfflineIndexRecord,
    VinOfflineManifest,
    VinOfflineMaterializedBlocks,
    VinOfflineMemoryDiagnostic,
    VinOfflineSampleDiagnostic,
    VinOracleDatasetBase,
)

GENERATOR_FACTORY: Callable[[], CandidateGenerator] = ProgramCandidateGenerator

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
    """Require the Lightning-owned source-config alias to remain valid."""
    return config


SOURCE_CONFIG_CLASSES = (VinOfflineSourceConfig, VinOracleOnlineDataset, VinOracleOnlineDatasetConfig)
