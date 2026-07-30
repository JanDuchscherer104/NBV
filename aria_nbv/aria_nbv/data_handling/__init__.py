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

# Bind raw views before offline batches, whose VIN types import this root.
from .raw.dataset import AseEfmDataset, AseEfmDatasetConfig
from .raw.views import EfmSnippetView, VinSnippetView
from .offline.batch import VinOracleBatch
from .offline.dataset import VinOfflineDataset, VinOfflineDatasetConfig
from .offline.store import VinOfflineStoreConfig

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
