"""Oracle RRI package root exports.

The package-level convenience exports expose the raw ASE/EFM snippet surface
from ``aria_nbv.data_handling`` without importing the full legacy
``aria_nbv.data`` stack during package initialization.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

if importlib.util.find_spec("efm3d") is None:  # pragma: no cover - environment dependent
    vendor = Path(__file__).resolve().parents[1].parent / "external" / "efm3d"
    if vendor.exists():
        sys.path.append(str(vendor))
    else:  # pragma: no cover
        raise ModuleNotFoundError("efm3d not installed and vendor path missing")

from .data_handling import (
    AseEfmDataset,
    AseEfmDatasetConfig,
    EfmSnippetView,
)
from .data_handling.raw.views import (
    EfmCameraView,
    EfmGTView,
    EfmObbView,
    EfmPointsView,
    EfmTrajectoryView,
)

__all__ = [
    "AseEfmDataset",
    "AseEfmDatasetConfig",
    "EfmCameraView",
    "EfmGTView",
    "EfmObbView",
    "EfmPointsView",
    "EfmSnippetView",
    "EfmTrajectoryView",
]
