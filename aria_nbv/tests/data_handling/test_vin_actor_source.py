"""Actor-only projection tests for immutable VIN offline stores."""

from __future__ import annotations

import pickle
from dataclasses import FrozenInstanceError
from typing import TYPE_CHECKING

import numpy as np
import pytest
from pydantic import ValidationError

from aria_nbv.data_handling.offline.actor import VinActorSourceConfig
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
    assert tuple(name for name, _value in sample.blocks) == (*CORE_BLOCKS, *TRAJECTORY_BLOCKS)
    assert dict(sample.availability) == dict.fromkeys((*CORE_BLOCKS, *TRAJECTORY_BLOCKS), True)
    assert reads == [*CORE_BLOCKS, *TRAJECTORY_BLOCKS]
    assert sample.block("vin.points_world").shape == (4, 4)
    assert sample.block("oracle.rri") is None
    with pytest.raises(FrozenInstanceError):
        sample.sample_key = "mutated"  # type: ignore[misc]
    with pytest.raises(ValueError, match="read-only"):
        sample.block("vin.points_world")[0, 0] = -1.0


def test_missing_optional_blocks_are_explicitly_unavailable(tmp_path: Path) -> None:
    """Optional actor evidence is absent, never synthesized as zero arrays."""

    store, _ = _write_actor_store(tmp_path / "store", trajectory=False)
    sample = VinActorSourceConfig(store=store).setup_target()[0]

    assert sample.block("vin.trajectory.time_ns") is None
    assert sample.block("vin.trajectory.gravity_in_world") is None
    assert dict(sample.availability) == {
        **dict.fromkeys(CORE_BLOCKS, True),
        **dict.fromkeys(TRAJECTORY_BLOCKS, False),
    }


def test_sparse_sample_index_has_explicit_lookup(tmp_path: Path) -> None:
    """Rollout joins resolve immutable sample ids without row-position assumptions."""

    store, _ = _write_actor_store(tmp_path / "store")
    source = VinActorSourceConfig(store=store).setup_target()

    assert source.index_for_sample(7) == 0
    with pytest.raises(KeyError, match="sample_index=0.*Rebuild"):
        source.index_for_sample(0)


def test_missing_required_actor_block_fails_during_setup(tmp_path: Path) -> None:
    """Required ablations fail before DataLoader workers start."""

    store, _ = _write_actor_store(tmp_path / "store", backbone=False)
    config = VinActorSourceConfig(store=store, required_blocks=("backbone.occ_pr",))

    with pytest.raises(ValueError, match="backbone.occ_pr.*Rebuild"):
        config.setup_target()


def test_explicit_optional_backbone_and_detection_blocks_are_projected(tmp_path: Path) -> None:
    """Explicit actor-visible ablations remain independent of the base profile."""

    store, _ = _write_actor_store(tmp_path / "store", backbone=True, detected_obbs=True)
    source = VinActorSourceConfig(
        store=store,
        optional_blocks=("backbone.occ_pr", "detected.obbs", "detected.obb_probs"),
    ).setup_target()
    sample = source[0]

    assert sample.block("backbone.occ_pr").shape == (1, 2, 2, 2)
    assert sample.block("detected.obbs").shape == (2, 34)
    assert sample.block("detected.obb_probs").shape == (2, 3)
    assert all(dict(sample.availability).values())


@pytest.mark.parametrize(
    "block_name",
    [
        "oracle.rri",
        "gt.obbs",
        "oracle.depths",
        "oracle.candidate_pcs",
        "selected_depth/raster",
        "target.crop",
        "candidate.pose",
    ],
)
def test_config_rejects_non_actor_blocks(block_name: str, tmp_path: Path) -> None:
    """The config allowlist must make privileged reads unrepresentable."""

    store, _ = _write_actor_store(tmp_path / "store")
    with pytest.raises(ValidationError, match="actor-visible"):
        VinActorSourceConfig(store=store, optional_blocks=(block_name,))


@pytest.mark.parametrize(
    "block_name",
    [
        "backbone.selected_depth",
        "backbone.oracle_depths",
        "backbone.gt_mesh",
    ],
)
def test_config_rejects_unknown_backbone_arrays_even_when_persisted(block_name: str, tmp_path: Path) -> None:
    """Only writer-owned actor-visible backbone names cross the source seam."""

    store, _ = _write_actor_store(tmp_path / "store", extra_numeric_blocks=(block_name,))
    reader = VinOfflineStoreReader(store)
    assert block_name in reader.manifest.shards[0].blocks

    with pytest.raises(ValidationError, match="actor-visible"):
        VinActorSourceConfig(store=store, optional_blocks=(block_name,))


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
    assert restored[0].block("vin.lengths").tolist() == [3]


def test_actor_source_stays_off_the_data_handling_root(tmp_path: Path) -> None:
    """The new leaf is intentionally not a root-package export."""

    store, _ = _write_actor_store(tmp_path / "store")
    source = VinActorSourceConfig(store=store).setup_target()

    import aria_nbv.data_handling as data_handling

    assert source.config.profile == "minimal_pose_target_v0"
    assert "VinActorSource" not in data_handling.__all__
    assert "VinActorSourceConfig" not in data_handling.__all__
