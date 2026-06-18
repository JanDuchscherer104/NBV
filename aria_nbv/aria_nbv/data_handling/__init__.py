# ruff: noqa: I001
"""Canonical data contracts for ASE/EFM snippets and derived NBV stores.

`aria_nbv.data_handling` owns the typed boundary between upstream ASE/ATEK/EFM
payloads and the training/evaluation objects consumed by ARIA-NBV. The public
surface exposes:

- `EfmSnippetView` and stream-specific views for camera images, calibration,
  trajectory poses, semidense points, OBBs, GT annotations, and optional meshes;
- `VinSnippetView` and `VinOracleBatch` for VIN-style one-step RRI scoring;
- strict immutable VIN offline-store readers/writers;
- oracle target-task sampling for rollout/data-generation labels;
- actor-visible target selection for diagnostics and deployable-policy studies.

The central safety contract is actor/oracle separation. Observed EVL/MPS/OBB
evidence is actor-visible; ASE meshes, GT OBBs, target crops, and oracle labels
are supervision/evaluation assets. Invalid samples, targets, or candidates must
be represented with masks and reason codes rather than low RRI values.
"""

from __future__ import annotations

# Import order is intentional: raw view exports must be bound before dependent
# modules that may indirectly import them back from ``aria_nbv.data_handling``.
from ._raw import (
    AseEfmDataset,
    AseEfmDatasetConfig,
    EfmCameraView,
    EfmGTView,
    EfmObbView,
    EfmPointsView,
    EfmSnippetView,
    EfmTrajectoryView,
    VinSnippetView,
    infer_semidense_bounds,
    is_efm_snippet_view_instance,
    is_vin_snippet_view_instance,
)
from .mesh_cache import MeshProcessSpec, ProcessedMesh, load_or_process_mesh
from .vin_adapter import DEFAULT_VIN_SNIPPET_PAD_POINTS, build_vin_snippet_view, empty_vin_snippet
from .vin_oracle_types import CompactObbBlock, CompactTrajectoryBlock, VinOracleBatch, VinOracleDatasetBase
from ._offline_dataset import VinOfflineDataset, VinOfflineDatasetConfig, VinOfflineSample
from ._offline_diagnostics import (
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
from ._offline_format import VinOfflineIndexRecord, VinOfflineManifest, VinOfflineMaterializedBlocks
from ._offline_store import OFFLINE_DATASET_VERSION, VinOfflineStoreConfig
from ._offline_visual_inventory import (
    OfflineVisualInventory,
    OfflineVisualInventoryError,
    collect_offline_visual_inventory,
)
from ._offline_writer import (
    VinOfflineWriter,
    VinOfflineWriterConfig,
    flush_prepared_samples_to_shard,
    prepare_vin_offline_sample,
)
from ._target_selection import (
    ORACLE_TARGET_TASK_SOURCE,
    TARGET_INVALID_REASON_CODES,
    TARGET_INVALID_REASON_VERSION,
    ActorVisibleTargetSelector,
    OracleTargetTaskRow,
    OracleTargetTaskSampler,
    OracleTargetTaskSamplerConfig,
    OracleTargetTaskSamplingResult,
    OracleTargetTaskSweepCell,
    TargetCandidateRow,
    TargetSelectionPolicy,
    TargetSelectionResult,
    TargetSelectorConfig,
    TargetSourceMode,
    TargetTaskIdentityStatus,
    target_gt_obb_world,
)
from ._vin_sources import (
    VinDatasetSourceConfig,
    VinOfflineSourceConfig,
    VinOracleOnlineDataset,
    VinOracleOnlineDatasetConfig,
)


__all__ = [
    "ActorVisibleTargetSelector",
    "AseEfmDataset",
    "AseEfmDatasetConfig",
    "CompactObbBlock",
    "CompactTrajectoryBlock",
    "DEFAULT_VIN_SNIPPET_PAD_POINTS",
    "EfmCameraView",
    "EfmGTView",
    "EfmObbView",
    "EfmPointsView",
    "EfmSnippetView",
    "EfmTrajectoryView",
    "MeshProcessSpec",
    "NumericSummary",
    "OFFLINE_DATASET_VERSION",
    "OfflineVisualInventory",
    "OfflineVisualInventoryError",
    "ORACLE_TARGET_TASK_SOURCE",
    "OracleTargetTaskRow",
    "OracleTargetTaskSampler",
    "OracleTargetTaskSamplerConfig",
    "OracleTargetTaskSamplingResult",
    "OracleTargetTaskSweepCell",
    "ProcessedMesh",
    "TARGET_INVALID_REASON_CODES",
    "TARGET_INVALID_REASON_VERSION",
    "TargetCandidateRow",
    "TargetSelectionPolicy",
    "TargetSelectionResult",
    "TargetSelectorConfig",
    "TargetSourceMode",
    "TargetTaskIdentityStatus",
    "target_gt_obb_world",
    "VinDatasetSourceConfig",
    "VinOfflineDataset",
    "VinOfflineBackboneDiagnostic",
    "VinOfflineBlockDiagnostic",
    "VinOfflineCoverageSceneDiagnostic",
    "VinOfflineCoverageStats",
    "VinOfflineDatasetConfig",
    "VinOfflineDatasetStats",
    "VinOfflineIndexRecord",
    "VinOfflineManifest",
    "VinOfflineMaterializedBlocks",
    "VinOfflineMemoryDiagnostic",
    "VinOfflineSample",
    "VinOfflineSampleDiagnostic",
    "VinOfflineSourceConfig",
    "VinOfflineStoreConfig",
    "VinOfflineWriter",
    "VinOfflineWriterConfig",
    "VinOracleBatch",
    "VinOracleDatasetBase",
    "VinOracleOnlineDataset",
    "VinOracleOnlineDatasetConfig",
    "VinSnippetView",
    "build_vin_snippet_view",
    "collect_vin_offline_dataset_coverage",
    "collect_vin_offline_dataset_stats",
    "collect_offline_visual_inventory",
    "empty_vin_snippet",
    "flush_prepared_samples_to_shard",
    "infer_semidense_bounds",
    "is_efm_snippet_view_instance",
    "is_vin_snippet_view_instance",
    "load_or_process_mesh",
    "prepare_vin_offline_sample",
]
