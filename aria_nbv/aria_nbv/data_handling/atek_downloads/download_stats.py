"""Helpers for reporting local download coverage and snippet counts for ATEK shards."""

from __future__ import annotations

import tarfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .metadata import ASEMetadata, SceneMetadata


@dataclass(frozen=True)
class DownloadedAtekStats:
    """Summary of available vs downloaded ATEK data for a given config."""

    config_name: str
    """ATEK config name (e.g., ``"efm"``)."""

    expected_scenes: int
    """Number of GT-mesh scenes expected for this config."""

    expected_shards: int
    """Total number of shards expected across GT-mesh scenes for this config."""

    downloaded_scenes: int
    """Number of GT-mesh scenes present on disk (at least one shard downloaded)."""

    downloaded_shards: int
    """Number of shard tar files found on disk across GT-mesh scenes."""

    downloaded_snippets: int
    """Estimated or exact number of snippet samples in downloaded shard tar files."""

    snippets_per_shard: int | None
    """If constant, the inferred number of snippets per shard."""

    snippet_count_is_estimate: bool
    """Whether ``downloaded_snippets`` was inferred from a sampled constant."""


def count_snippets_in_tar(path: Path) -> int:
    """Count snippet samples in a shard tar.

    We define one snippet as one WebDataset "sample key". In ASE ATEK shards, each
    snippet includes a ``*.sequence_name.txt`` file, so we count these entries.

    Args:
        path: Path to a ``.tar`` shard.

    Returns:
        Number of snippets in this shard.
    """
    count = 0
    with tarfile.open(path, "r") as tf:
        for member in tf:
            if member.name.endswith(".sequence_name.txt"):
                count += 1
    return count


def _iter_downloaded_shard_tars(data_dir: Path, scenes: Iterable[SceneMetadata]) -> list[Path]:
    tar_paths: list[Path] = []
    for scene in scenes:
        scene_dir = data_dir / scene.scene_id
        if not scene_dir.is_dir():
            continue
        tar_paths.extend(sorted(scene_dir.glob("shards-*.tar")))
    return tar_paths


def _estimate_snippet_count_from_shards(tar_paths: list[Path], sample_size: int) -> tuple[int, int | None, bool]:
    if not tar_paths:
        return 0, None, False

    sample = tar_paths[: min(sample_size, len(tar_paths))]
    sample_counts = {count_snippets_in_tar(p) for p in sample}
    if len(sample_counts) == 1:
        snippets_per_shard = next(iter(sample_counts))
        snippet_count_is_estimate = len(sample) < len(tar_paths)
        return snippets_per_shard * len(tar_paths), snippets_per_shard, snippet_count_is_estimate

    total = sum(count_snippets_in_tar(p) for p in tar_paths)
    return total, None, False


def compute_downloaded_atek_stats(
    *,
    metadata: ASEMetadata,
    data_root: Path,
    config_name: str,
    snippet_sample_size: int = 10,
) -> DownloadedAtekStats:
    """Compute local download coverage for an ATEK config.

    Args:
        metadata: Parsed ASE metadata (meshes + ATEK shard manifests).
        data_root: Project data root directory (e.g., ``.data``).
        config_name: ATEK config name (e.g., ``"efm"``).
        snippet_sample_size: Number of shard tars to sample to infer a constant
            snippet-per-shard count. If the sample is not constant, the function
            falls back to an exact scan of all shard tars.

    Returns:
        Download stats for GT-mesh scenes under ``config_name``.
    """
    scenes = metadata.get_scenes_with_meshes(config=config_name)
    expected_shards = sum(scene.shard_count for scene in scenes)

    data_dir = (data_root / f"ase_{config_name}").resolve()
    tar_paths = _iter_downloaded_shard_tars(data_dir, scenes) if data_dir.is_dir() else []

    downloaded_shards = len(tar_paths)
    downloaded_scenes = len({p.parent.name for p in tar_paths})
    downloaded_snippets, snippets_per_shard, snippet_count_is_estimate = _estimate_snippet_count_from_shards(
        tar_paths,
        sample_size=snippet_sample_size,
    )

    return DownloadedAtekStats(
        config_name=config_name,
        expected_scenes=len(scenes),
        expected_shards=expected_shards,
        downloaded_scenes=downloaded_scenes,
        downloaded_shards=downloaded_shards,
        downloaded_snippets=downloaded_snippets,
        snippets_per_shard=snippets_per_shard,
        snippet_count_is_estimate=snippet_count_is_estimate,
    )


__all__ = [
    "DownloadedAtekStats",
    "compute_downloaded_atek_stats",
    "count_snippets_in_tar",
]
