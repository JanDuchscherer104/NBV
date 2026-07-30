# ruff: noqa: I001
"""Expose typed ASE/EFM views and immutable VIN offline-store entrypoints.

The package root exports the stable cross-module contracts for raw ASE/EFM
access: :class:`AseEfmDataset`, its config, and the zero-copy typed
:class:`EfmSnippetView` and :class:`VinSnippetView` views. It also exports the
:class:`VinOracleBatch` payload and read-side configuration for immutable
:class:`VinOfflineDataset` stores.

Specialized codecs, diagnostics, writers, adapters, and storage internals stay
owned by their leaf modules. Oracle sample generation and target selection are
pipeline concerns owned outside :mod:`aria_nbv.data_handling`; this package
neither constructs oracle labels nor chooses target entities.
"""

from __future__ import annotations

# Bind ASE/EFM views before VIN-store batches, whose VIN types import this root.
from .ase_efm.dataset import AseEfmDataset, AseEfmDatasetConfig
from .ase_efm.views import EfmSnippetView
from .vin_store.batch import VinOracleBatch
from .vin_store.dataset import VinOfflineDataset, VinOfflineDatasetConfig
from .vin_store.store import VinOfflineStoreConfig
from .vin_store.views import VinSnippetView

__all__ = [
    "AseEfmDataset",
    "AseEfmDatasetConfig",
    "EfmSnippetView",
    "VinSnippetView",
    "VinOracleBatch",
    "VinOfflineDataset",
    "VinOfflineDatasetConfig",
    "VinOfflineStoreConfig",
]
