"""Actor-only projection tests for immutable VIN offline stores."""

from __future__ import annotations

import pickle
from dataclasses import FrozenInstanceError, fields
from typing import TYPE_CHECKING

import numpy as np
import pytest

from aria_nbv.data_handling.offline.actor import VinActorSample, VinActorSourceConfig
from aria_nbv.data_handling.offline.format import (
    VinOfflineIndexRecord,
    VinOfflineManifest,
    VinOfflineMaterializedBlocks,
    VinOfflineShardSpec,
)
from aria_nbv.data_handling.offline.store import (
    OFFLINE_DATASET_VERSION,
    VinOfflineShardWriter,
    VinOfflineStoreConfig,
    VinOfflineStoreReader,
)
from aria_nbv.utils.fingerprints import stable_msgspec_hash

if TYPE_CHECKING:
    from pathlib import Path


CORE_BLOCKS = (
    "vin.points_world",
    "vin.lengths",
    "vin.t_world_rig",
)
TRAJECTORY_BLOCKS = (
    "vin.trajectory.time_ns",
    "vin.trajectory.gravity_in_world",
)


def test_actor_sample_owns_one_typed_snippet_instead_of_parallel_block_bags() -> None:
    """Q_H actor evidence should reuse the canonical typed VIN snippet view."""

    field_names = {field.name for field in fields(VinActorSample)}

    assert "snippet" in field_names
    assert "blocks" not in field_names
    assert "availability" not in field_names


def _write_actor_store(
    root: Path,
    *,
    trajectory: bool = True,
    backbone: bool = False,
    detected_obbs: bool = False,
    extra_numeric_blocks: tuple[str, ...] = (),
    sample_key: str = "scene-a:snippet-000",
    snippet_id: str = "snippet-000",
) -> tuple[VinOfflineStoreConfig, str]:
    """Write one immutable row with selected actor and forbidden sentinel blocks."""

    store = VinOfflineStoreConfig(store_dir=root)
    shard_dir = store.shards_dir / "shard-000000"
    shard_dir.mkdir(parents=True)
    writer = VinOfflineShardWriter(shard_dir)
    arrays = {
        "vin.points_world": np.arange(16, dtype=np.float32).reshape(1, 4, 4),
        "vin.lengths": np.asarray([[3]], dtype=np.int64),
        "vin.t_world_rig": np.arange(24, dtype=np.float32).reshape(1, 2, 12),
        "oracle.rri": np.full((1, 3), 9001.0, dtype=np.float32),
        "gt.obbs": np.full((1, 2, 34), 9002.0, dtype=np.float32),
        "oracle.depths": np.full((1, 3, 2, 2), 9003.0, dtype=np.float32),
    }
    if trajectory:
        arrays.update(
            {
                "vin.trajectory.time_ns": np.asarray([[100, 200]], dtype=np.int64),
                "vin.trajectory.gravity_in_world": np.asarray([[0.0, 0.0, -9.81]], dtype=np.float32),
            }
        )
    if backbone:
        arrays["backbone.occ_pr"] = np.ones((1, 1, 2, 2, 2), dtype=np.float32)
    if detected_obbs:
        arrays["detected.obbs"] = np.ones((1, 2, 34), dtype=np.float32)
        arrays["detected.obb_probs"] = np.full((1, 2, 3), 1.0 / 3.0, dtype=np.float32)
    for name in extra_numeric_blocks:
        arrays[name] = np.full((1, 2), 9006.0, dtype=np.float32)

    blocks = {name: writer.write_numeric_block(name, value) for name, value in arrays.items()}
    shard = writer.write_record_block("oracle.candidate_pcs", [{"sentinel": 9004}])
    blocks[shard.name] = shard
    manifest = VinOfflineManifest(
        version=OFFLINE_DATASET_VERSION,
        created_at="2026-07-19T00:00:00Z",
        source={"dataset_config": {"scene_ids": ["scene-a"]}},
        oracle={"sentinel": 9005},
        vin={"pad_points": 4},
        materialized_blocks=VinOfflineMaterializedBlocks(
            backbone=backbone,
            depths=True,
            candidate_pcs=True,
            gt_obbs=True,
            detected_obbs=detected_obbs,
            trajectory=trajectory,
        ),
        shards=[
            VinOfflineShardSpec(
                shard_id="shard-000000",
                relative_dir="shards/shard-000000",
                row_start=0,
                num_rows=1,
                blocks=blocks,
            )
        ],
    )
    root.mkdir(parents=True, exist_ok=True)
    manifest.write(store.manifest_path)
    record = VinOfflineIndexRecord(
        sample_index=7,
        sample_key=sample_key,
        scene_id="scene-a",
        snippet_id=snippet_id,
        split="train",
        shard_id="shard-000000",
        row=0,
    )
    VinOfflineIndexRecord.write_many(store.sample_index_path, [record])
    store.write_split_indices(
        {
            "all": np.asarray([7], dtype=np.int64),
            "train": np.asarray([7], dtype=np.int64),
            "val": np.asarray([], dtype=np.int64),
        }
    )
    return store, stable_msgspec_hash(manifest)


def test_minimal_profile_reads_only_actor_visible_blocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The pilot-like profile must not touch persisted Oracle sentinels."""

    store, _ = _write_actor_store(tmp_path / "store")
    source = VinActorSourceConfig(store=store, split="train").setup_target()
    reads: list[str] = []
    original = VinOfflineStoreReader.read_numeric_block

    def _record_read(self: VinOfflineStoreReader, record: VinOfflineIndexRecord, block_name: str) -> np.ndarray:
        reads.append(block_name)
        return original(self, record, block_name)

    monkeypatch.setattr(VinOfflineStoreReader, "read_numeric_block", _record_read)
    sample = source[0]

    assert len(source) == 1
    assert sample.sample_index == 7
    assert sample.sample_key == "scene-a:snippet-000"
    assert reads == [*CORE_BLOCKS]
    assert sample.snippet.points_world.shape == (4, 4)
    assert sample.snippet.lengths.tolist() == [3]
    assert sample.snippet.t_world_rig.tensor().shape == (2, 12)
    with pytest.raises(FrozenInstanceError):
        sample.sample_key = "mutated"  # type: ignore[misc]


def test_optional_persisted_blocks_do_not_cross_the_typed_actor_seam(tmp_path: Path) -> None:
    """The V0 actor source reads exactly the typed snippet evidence."""

    store, _ = _write_actor_store(tmp_path / "store", trajectory=True, backbone=True, detected_obbs=True)
    sample = VinActorSourceConfig(store=store).setup_target()[0]

    assert {field.name for field in fields(VinActorSample)} == {
        "sample_index",
        "sample_key",
        "scene_id",
        "snippet_id",
        "split",
        "source_shard_id",
        "source_shard_row",
        "source_offline_store_version",
        "source_offline_store_manifest_hash",
        "snippet",
    }
    assert not hasattr(sample, "blocks")
    assert not hasattr(sample, "availability")


def test_sparse_sample_index_has_explicit_lookup(tmp_path: Path) -> None:
    """Rollout joins resolve immutable sample ids without row-position assumptions."""

    store, _ = _write_actor_store(tmp_path / "store")
    source = VinActorSourceConfig(store=store).setup_target()

    assert source.index_for_sample(7) == 0
    with pytest.raises(KeyError, match="sample_index=0.*Rebuild"):
        source.index_for_sample(0)


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("source_sample_index", 8),
        ("source_sample_key", "other"),
        ("source_shard_id", "shard-999999"),
        ("source_shard_row", 3),
        ("source_offline_store_version", "999"),
        ("source_offline_store_manifest_hash", "wrong-hash"),
    ],
)
def test_lineage_mismatch_has_rebuild_guidance(field: str, bad_value: object, tmp_path: Path) -> None:
    """Every immutable join key must fail with actionable corpus guidance."""

    store, manifest_hash = _write_actor_store(tmp_path / "store")
    source = VinActorSourceConfig(store=store).setup_target()
    expected: dict[str, object] = {
        "source_sample_index": 7,
        "source_sample_key": "scene-a:snippet-000",
        "source_shard_id": "shard-000000",
        "source_shard_row": 0,
        "source_offline_store_version": str(OFFLINE_DATASET_VERSION),
        "source_offline_store_manifest_hash": manifest_hash,
    }
    expected[field] = bad_value

    with pytest.raises(ValueError, match=rf"{field}.*Rebuild"):
        source.validate_lineage(0, **expected)  # type: ignore[arg-type]


def test_lineage_accepts_equivalent_raw_and_compact_ase_atek_ids(tmp_path: Path) -> None:
    """Identifier spelling differences must not break an otherwise exact join."""

    store, manifest_hash = _write_actor_store(
        tmp_path / "store",
        sample_key="ASE_81286_Atek_000000",
        snippet_id="ASE_81286_Atek_000000",
    )
    source = VinActorSourceConfig(store=store).setup_target()

    source.validate_lineage(
        0,
        source_sample_index=7,
        source_sample_key="AriaSyntheticEnvironment_81286_AtekDataSample_000000",
        source_shard_id="shard-000000",
        source_shard_row=0,
        source_offline_store_version=str(OFFLINE_DATASET_VERSION),
        source_offline_store_manifest_hash=manifest_hash,
        snippet_id="AriaSyntheticEnvironment_81286_AtekDataSample_000000",
    )


def test_pickle_drops_worker_local_reader_and_reopens_lazily(tmp_path: Path) -> None:
    """Spawned workers must not inherit open Zarr reader state."""

    store, _ = _write_actor_store(tmp_path / "store")
    source = VinActorSourceConfig(store=store).setup_target()
    source[0]
    assert source._reader is not None

    restored = pickle.loads(pickle.dumps(source))

    assert restored._reader is None
    assert restored[0].snippet.lengths.tolist() == [3]


def test_actor_source_stays_off_the_data_handling_root(tmp_path: Path) -> None:
    """The new leaf is intentionally not a root-package export."""

    store, _ = _write_actor_store(tmp_path / "store")
    source = VinActorSourceConfig(store=store).setup_target()

    import aria_nbv.data_handling as data_handling

    assert source.config.profile == "minimal_pose_target_v0"
    assert "VinActorSource" not in data_handling.__all__
    assert "VinActorSourceConfig" not in data_handling.__all__
