"""Deprecated legacy data package.

Canonical raw snippet, cache, and VIN batch contracts live in
``aria_nbv.data_handling``. This package now retains only residual utilities
that have not moved yet; mirrored compatibility re-exports were removed.
"""

from .downloader import ASEDownloader, ASEDownloaderConfig
from .metadata import ASEMetadata, SceneMetadata

__all__ = [
    "ASEDownloader",
    "ASEDownloaderConfig",
    "ASEMetadata",
    "SceneMetadata",
]
