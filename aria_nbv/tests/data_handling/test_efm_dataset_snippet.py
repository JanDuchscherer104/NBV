"""Integration checks for scene/snippet lookup in the main data-handling dataset."""

from __future__ import annotations

import tarfile
from pathlib import Path

import pytest


def _scene_shards(scene_id: str) -> tuple[Path, list[Path]]:
    repo_root = Path(__file__).resolve().parents[2]
    scene_dir = repo_root / ".data" / "ase_efm" / scene_id
    if not scene_dir.exists():
        pytest.skip("Missing ASE scene directory for snippet lookup test")
    tar_paths = sorted(scene_dir.glob("*.tar"))
    if not tar_paths:
        pytest.skip("Missing ASE tar shards for snippet lookup test")
    return scene_dir, tar_paths


def _first_sample_key(tar_path: Path) -> str:
    with tarfile.open(tar_path, "r") as tar:
        for member in tar:
            return member.name.split(".", 1)[0]
    message = f"No members found in {tar_path}"
    raise RuntimeError(message)


def test_ase_efm_snippet_lookup() -> None:
    """Resolve a sample key + shard ID to the correct tar and sample."""
    scene_id = "81286"
    _, tar_paths = _scene_shards(scene_id)
    tar_path = tar_paths[0]
    sample_key = _first_sample_key(tar_path)

    from aria_nbv.data_handling.ase_efm.dataset import AseEfmDatasetConfig

    ds = AseEfmDatasetConfig(
        scene_ids=[scene_id],
        snippet_ids=[sample_key],
        batch_size=1,
        load_meshes=False,
        device="cpu",
        wds_shuffle=False,
    ).setup_target()
    sample = next(iter(ds))

    assert sample.scene_id == scene_id  # noqa: S101
    assert sample.snippet_id == sample_key  # noqa: S101
    assert Path(sample.efm["__url__"]).name == tar_path.name  # noqa: S101

    shard_id = tar_path.stem
    ds_shard = AseEfmDatasetConfig(
        scene_ids=[scene_id],
        snippet_ids=[shard_id],
        batch_size=1,
        load_meshes=False,
        device="cpu",
        wds_shuffle=False,
    ).setup_target()
    sample_shard = next(iter(ds_shard))

    assert Path(sample_shard.efm["__url__"]).stem == shard_id  # noqa: S101
