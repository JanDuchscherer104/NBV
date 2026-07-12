# ruff: noqa: I001
"""Canonical data contracts for ASE/EFM snippets and derived NBV stores.

:mod:`aria_nbv.data_handling` owns the typed boundary between upstream ASE/ATEK/EFM
payloads and the training/evaluation objects consumed by ARIA-NBV. The public
surface exposes:

- :class:`EfmSnippetView` and stream-specific views for camera images, calibration,
  trajectory poses, semidense points, OBBs, GT annotations, and optional meshes;
- :class:`VinSnippetView` and :class:`VinOracleBatch` for VIN-style one-step RRI scoring;
- strict immutable VIN offline-store readers/writers.

The central safety contract is actor/oracle separation. Observed EVL/MPS/OBB
evidence is actor-visible; ASE meshes, GT OBBs, target crops, and oracle labels
are supervision/evaluation assets. Invalid samples, targets, or candidates must
be represented with masks and reason codes rather than low RRI values.
"""

from __future__ import annotations

# Import order is intentional: raw view exports must be bound before dependent
# modules that may indirectly import them back from ``aria_nbv.data_handling``.
from .raw import (
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
from .offline.dataset import VinOfflineDataset, VinOfflineDatasetConfig, VinOfflineSample
from .offline.diagnostics import (
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
from .offline.format import VinOfflineIndexRecord, VinOfflineManifest, VinOfflineMaterializedBlocks
from .offline.store import OFFLINE_DATASET_VERSION, VinOfflineStoreConfig
from .offline.inventory import (
    OfflineVisualInventory,
    OfflineVisualInventoryError,
    collect_offline_visual_inventory,
)
from .offline.writer import (
    VinOfflineWriter,
    VinOfflineWriterConfig,
    flush_prepared_samples_to_shard,
    prepare_vin_offline_sample,
)
from .mesh_cache import MeshProcessSpec, ProcessedMesh, load_or_process_mesh
from .offline.adapter import DEFAULT_VIN_SNIPPET_PAD_POINTS, build_vin_snippet_view, empty_vin_snippet
from .offline.batch import CompactObbBlock, CompactTrajectoryBlock, VinOracleBatch, VinOracleDatasetBase

__all__ = [
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
    "ProcessedMesh",
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
    "VinOfflineStoreConfig",
    "VinOfflineWriter",
    "VinOfflineWriterConfig",
    "VinOracleBatch",
    "VinOracleDatasetBase",
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
