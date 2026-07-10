"""Tests for ASE downloader list-mode stats and config filtering."""

from __future__ import annotations

import json
import tarfile
from io import BytesIO
from typing import TYPE_CHECKING

from aria_nbv.data_handling.atek_downloads.download_stats import (
    compute_downloaded_atek_stats,
    count_snippets_in_tar,
)
from aria_nbv.data_handling.atek_downloads.metadata import ASEMetadata

if TYPE_CHECKING:
    from pathlib import Path


def _write_mesh_urls(path: Path, scene_ids: list[str]) -> None:
    payload = [
        {
            "filename": f"scene_ply_{scene_id}.zip",
            "cdn": f"https://example.com/{scene_id}.zip",
            "sha": "dummy",
        }
        for scene_id in scene_ids
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_atek_urls(
    path: Path,
    cfg_to_scene_shards: dict[str, dict[str, int]],
) -> None:
    configs = {}
    for cfg_name, scene_to_count in cfg_to_scene_shards.items():
        wds_file_urls = {}
        for scene_id, shard_count in scene_to_count.items():
            wds_file_urls[scene_id] = {
                f"shards-{idx:04d}_tar": {
                    "filename": (f"AriaSyntheticEnvironment_1_0_ATEK_{cfg_name}_{scene_id}_shards-{idx:04d}.tar"),
                    "sha1sum": "dummy",
                    "file_size_bytes": 1,
                    "download_url": "https://example.com/file.tar",
                }
                for idx in range(shard_count)
            }
        configs[cfg_name] = {"wds_file_urls": wds_file_urls}

    payload = {
        "raw_dataset_name": "ASE",
        "raw_dataset_release_version": "dummy",
        "atek_data_for_all_configs": configs,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_tar_safe(path: Path, *, snippet_count: int) -> None:
    """Write a small WebDataset-style tar with ``snippet_count`` samples."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w") as tf:
        for idx in range(snippet_count):
            name = f"AriaSyntheticEnvironment_00000_AtekDataSample_{idx:06d}.sequence_name.txt"
            data = b"00000\n"
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, fileobj=BytesIO(data))


def test_get_scenes_with_meshes_respects_config(tmp_path: Path) -> None:
    """Return GT-mesh scenes for the requested ATEK config."""
    mesh_path = tmp_path / "mesh.json"
    atek_path = tmp_path / "atek.json"

    _write_mesh_urls(mesh_path, ["1"])
    _write_atek_urls(
        atek_path,
        {
            "efm": {"1": 1},
            "cubercnn_eval": {"1": 2},
        },
    )

    meta = ASEMetadata(
        url_dir=tmp_path,
        mesh_json_filename="mesh.json",
        atek_json_filename="atek.json",
    )

    # No config -> max shards across configs (cubercnn_eval wins).
    expected_max_shards = 2
    scenes = meta.get_scenes_with_meshes()
    assert len(scenes) == 1  # noqa: S101
    assert scenes[0].shard_count == expected_max_shards  # noqa: S101
    assert scenes[0].atek_config == "cubercnn_eval"  # noqa: S101

    # Config -> config-specific shards.
    expected_efm_shards = 1
    scenes_efm = meta.get_scenes_with_meshes(config="efm")
    assert len(scenes_efm) == 1  # noqa: S101
    assert scenes_efm[0].shard_count == expected_efm_shards  # noqa: S101
    assert scenes_efm[0].atek_config == "efm"  # noqa: S101


def test_count_snippets_in_tar_counts_sequence_name_files(tmp_path: Path) -> None:
    """Count snippets in a shard tar via ``*.sequence_name.txt`` members."""
    tar_path = tmp_path / "shards-0000.tar"
    expected = 3
    _write_tar_safe(tar_path, snippet_count=expected)
    assert count_snippets_in_tar(tar_path) == expected  # noqa: S101


def test_compute_downloaded_atek_stats_counts_downloaded_shards_and_snippets(
    tmp_path: Path,
) -> None:
    """Report expected vs downloaded shard and snippet counts."""
    mesh_path = tmp_path / "mesh.json"
    atek_path = tmp_path / "atek.json"
    data_root = tmp_path / ".data"
    data_root.mkdir()

    _write_mesh_urls(mesh_path, ["1"])
    _write_atek_urls(
        atek_path,
        {
            "efm": {"1": 2},
            "efm_eval": {"1": 2},
        },
    )
    meta = ASEMetadata(
        url_dir=tmp_path,
        mesh_json_filename="mesh.json",
        atek_json_filename="atek.json",
    )

    # Download only one of the two expected shards for efm, with 5 snippets.
    downloaded_snippets = 5
    _write_tar_safe(
        data_root / "ase_efm" / "1" / "shards-0000.tar",
        snippet_count=downloaded_snippets,
    )

    stats = compute_downloaded_atek_stats(
        metadata=meta,
        data_root=data_root,
        config_name="efm",
        snippet_sample_size=10,
    )
    expected_shards = 2
    downloaded_shards = 1
    downloaded_scenes = 1
    assert stats.expected_shards == expected_shards  # noqa: S101
    assert stats.downloaded_shards == downloaded_shards  # noqa: S101
    assert stats.downloaded_snippets == downloaded_snippets  # noqa: S101
    assert stats.downloaded_scenes == downloaded_scenes  # noqa: S101
