"""ASE mesh and ATEK shard acquisition utilities.

This package provides manifest parsing plus checksum-aware acquisition of ATEK
WebDataset shards and ASE ground-truth meshes. Downloaded shards are the
tensorized VRS/MPS provenance consumed by :class:`AseEfmDataset`; meshes remain
oracle supervision and evaluation assets rather than actor-visible inputs.
"""

from .downloader import ASEDownloader, ASEDownloaderConfig
from .metadata import ASEMetadata, SceneMetadata

__all__ = [
    "ASEDownloader",
    "ASEDownloaderConfig",
    "ASEMetadata",
    "SceneMetadata",
]
