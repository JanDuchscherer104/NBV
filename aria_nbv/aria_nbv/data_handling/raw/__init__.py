"""Raw ASE/EFM data interfaces used by ``aria_nbv.data_handling``.

This module provides the stable raw snippet layer for the data-handling package.
It keeps the existing raw dataset and typed view implementations intact while
presenting a single import surface for:

- the iterable raw ASE/EFM dataset,
- typed raw and VIN snippet views, and
- the worker-local snippet loader used for live snippet attachment.
"""

from __future__ import annotations

from .dataset import AseEfmDataset, AseEfmDatasetConfig, infer_semidense_bounds
from .loader import EfmSnippetLoader
from .views import (
    EfmCameraView,
    EfmGTView,
    EfmObbView,
    EfmPointsView,
    EfmSnippetView,
    EfmTrajectoryView,
    VinSnippetView,
    is_efm_snippet_view_instance,
    is_vin_snippet_view_instance,
)

__all__ = [
    "AseEfmDataset",
    "AseEfmDatasetConfig",
    "EfmCameraView",
    "EfmGTView",
    "EfmObbView",
    "EfmPointsView",
    "EfmSnippetLoader",
    "EfmSnippetView",
    "EfmTrajectoryView",
    "VinSnippetView",
    "infer_semidense_bounds",
    "is_efm_snippet_view_instance",
    "is_vin_snippet_view_instance",
]
