from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

import pytest

from aria_nbv.oracle.pipelines.root_selection import discover_ase_root_inventory, write_root_inventory


def _write_shard(path: Path, sample_keys: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w") as archive:
        for sample_key in sample_keys:
            payload = b"fixture"
            info = tarfile.TarInfo(f"{sample_key}.data.pth")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))


def _fixture_roots(tmp_path: Path) -> tuple[Path, Path]:
    efm_root = tmp_path / "ase_efm"
    mesh_root = tmp_path / "ase_meshes"
    mesh_root.mkdir()
    for scene_id in ("100", "200"):
        for shard_index in range(2):
            _write_shard(
                efm_root / scene_id / f"shards-{shard_index:04d}.tar",
                [
                    f"AriaSyntheticEnvironment_{scene_id}_AtekDataSample_{shard_index * 2:06d}",
                    f"AriaSyntheticEnvironment_{scene_id}_AtekDataSample_{shard_index * 2 + 1:06d}",
                ],
            )
        (mesh_root / f"scene_ply_{scene_id}.ply").write_text("ply\n", encoding="utf-8")
    return efm_root, mesh_root


def test_inventory_selects_one_deterministic_root_per_scene(tmp_path: Path) -> None:
    efm_root, mesh_root = _fixture_roots(tmp_path)

    first = discover_ase_root_inventory(
        ase_efm_dir=efm_root,
        ase_meshes_dir=mesh_root,
        seed=17,
        expected_scene_count=2,
    )
    second = discover_ase_root_inventory(
        ase_efm_dir=efm_root,
        ase_meshes_dir=mesh_root,
        seed=17,
        expected_scene_count=2,
    )

    assert [scene.scene_id for scene in first.scenes] == ["100", "200"]
    assert first.selected_sample_keys == second.selected_sample_keys
    assert len(set(first.selected_sample_keys)) == 2
    assert all(len(scene.candidates) == 2 for scene in first.scenes)


def test_inventory_writes_all_reserves_and_stable_hash(tmp_path: Path) -> None:
    efm_root, mesh_root = _fixture_roots(tmp_path)
    inventory = discover_ase_root_inventory(
        ase_efm_dir=efm_root,
        ase_meshes_dir=mesh_root,
        seed=23,
        expected_scene_count=2,
    )

    first_path = write_root_inventory(tmp_path / "inventory.json", inventory, repo_root=tmp_path)
    first_payload = first_path.read_bytes()
    second_path = write_root_inventory(tmp_path / "inventory.json", inventory, repo_root=tmp_path)

    assert second_path.read_bytes() == first_payload
    payload = json.loads(first_payload)
    assert payload["num_scenes"] == 2
    assert payload["num_candidates"] == 4
    assert all(len(scene["candidates"]) == 2 for scene in payload["scenes"])
    assert len(payload["inventory_hash"]) == 16


def test_inventory_fails_closed_on_missing_mesh(tmp_path: Path) -> None:
    efm_root, mesh_root = _fixture_roots(tmp_path)
    (mesh_root / "scene_ply_200.ply").unlink()

    with pytest.raises(ValueError, match="missing_mesh_scenes=\\['200'\\]"):
        discover_ase_root_inventory(
            ase_efm_dir=efm_root,
            ase_meshes_dir=mesh_root,
            seed=0,
            expected_scene_count=2,
        )
