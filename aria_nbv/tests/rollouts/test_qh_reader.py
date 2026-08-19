"""Contracts for the bounded, horizon-agnostic ``Q_H`` reader."""

# ruff: noqa: S101

from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pytest
import zarr

pytest.importorskip("efm3d")

from aria_nbv.rollouts.qh_reader import QhRolloutReader
from aria_nbv.rollouts.shard_manifest import build_rollout_split_manifest_hash
from aria_nbv.rollouts.zarr_store import (
    RolloutZarrStoreReader,
    RolloutZarrValidationResult,
    write_rollout_zarr_store,
)
from aria_nbv.targets.descriptor import TargetDescriptor
from aria_nbv.targets.selection import ObservedTargetDescriptor
from aria_nbv.utils import Stage
from aria_nbv.utils.fingerprints import stable_msgspec_hash
from tests.rollout_fixtures import build_rollout_records


def _campaign_split_hash(records: list[object]) -> str:
    """Return the canonical fixture hash for campaign-bound source rows."""

    sources = [record.lineage.source for record in records]
    first = sources[0]
    split_hash = build_rollout_split_manifest_hash(
        source_manifest_hash=first.source_offline_store_manifest_hash,
        split=first.split,
        records=[
            {
                "order": order,
                "sample_index": source.source_sample_index,
                "sample_key": source.source_sample_key,
                "scene_id": source.scene_id,
                "snippet_id": source.snippet_id,
                "split": source.split,
                "source_shard_id": source.source_shard_id,
                "source_shard_row": source.source_shard_row,
                "campaign_split": source.campaign_split,
            }
            for order, source in enumerate(sources)
        ],
    )
    for source in sources:
        source.split_manifest_hash = split_hash
    return split_hash


def _write_store(path: Path, *, horizon: int = 2, records: int = 1, source_row_id: int | None = None) -> Path:
    rollout_records = build_rollout_records(horizon=horizon, num_samples=6, seed=7)[:records]
    if source_row_id is not None:
        assert records == 1
        source = rollout_records[0].lineage.source
        source.source_row_id = source_row_id
        source.source_sample_index = source_row_id
        source.source_shard_row = source_row_id
    return write_rollout_zarr_store(
        path,
        rollout_records,
        discount_gamma=0.95,
        target_protocol_version="v0_gt_input",
        source_offline_store_version="7",
        split_manifest_hash="fixture-split-manifest",
    ).store_dir


def _write_v1_store(path: Path) -> Path:
    records = build_rollout_records(horizon=2, num_samples=6, seed=7)[:1]
    source = records[0].lineage.source
    target = records[0].lineage.target
    target.target_protocol_version = "v1_observed"
    target.target_source = "detected_obbs"
    target.descriptor_source = "detected_obbs"
    target.descriptor_provenance = "actor_visible_detector"
    actor = ObservedTargetDescriptor(
        sample_key=str(source.source_sample_key),
        source="detected_obbs",
        source_row=int(target.target_source_index),
        target_id=str(target.target_id),
        descriptor=TargetDescriptor(
            sem_id=int(target.target_sem_id),
            class_name=str(target.target_class_name),
            pose_world_object=tuple(target.target_pose_world_object),
            extents_m=tuple(target.target_extents),
            relative_pose_reference_object=tuple(target.target_relative_pose_reference_object),
        ),
        confidence=float(target.target_confidence),
        inst_id=int(target.target_inst_id),
    )
    target.descriptor_hash = actor.descriptor_hash
    target.target_invalid_reason_bitset = 1
    target.gt_match_status = "admitted"
    target.gt_match_iou = float(np.float32(0.7))
    target.explicit_target_hash = stable_msgspec_hash(
        {
            "sample_key": actor.sample_key,
            "target_id": actor.target_id,
            "detected_source_row": actor.source_row,
            "gt_match_row": target.matched_gt_target_row_id,
            "gt_match_id": target.matched_gt_target_id,
            "oriented_iou": target.gt_match_iou,
            "descriptor_hash": actor.descriptor_hash,
        }
    )
    return write_rollout_zarr_store(
        path,
        records,
        discount_gamma=0.95,
        target_protocol_version="v1_observed",
        source_offline_store_version="7",
        split_manifest_hash=_campaign_split_hash(records),
    ).store_dir


def test_reader_indexes_complete_chains_with_compact_keys(tmp_path: Path) -> None:
    reader = QhRolloutReader((_write_store(tmp_path / "rollouts.zarr", records=2),))
    first = reader[0]
    last = reader[-1]

    assert len(reader) == 2
    assert first.rollout_row_id != last.rollout_row_id
    assert first.store_index == last.store_index == 0
    assert first.source_ref in reader.source_refs
    with pytest.raises(IndexError, match="outside corpus length"):
        _ = reader[2]


def test_reader_normalizes_validation_campaign_split_without_changing_source_split(tmp_path: Path) -> None:
    records = build_rollout_records(horizon=2, num_samples=6, seed=7)[:1]
    records[0].lineage.source.campaign_split = "validation"
    store = write_rollout_zarr_store(
        tmp_path / "validation.zarr",
        records,
        discount_gamma=0.95,
        target_protocol_version="v0_gt_input",
        source_offline_store_version="7",
        split_manifest_hash=_campaign_split_hash(records),
    ).store_dir

    source = QhRolloutReader((store,)).source_refs[0]
    assert source.split is Stage.TRAIN
    assert source.campaign_split is Stage.VAL


def test_reader_campaign_split_isolates_three_way_corpus_and_hides_excluded_rows(tmp_path: Path) -> None:
    records = build_rollout_records(horizon=2, num_samples=6, seed=7)
    for record, campaign_split in zip(records, ("train", "validation", "test"), strict=True):
        record.lineage.source.campaign_split = campaign_split
        record.lineage.source.scene_id = f"scene-{campaign_split}"
    store = write_rollout_zarr_store(
        tmp_path / "three-way.zarr",
        records,
        discount_gamma=0.95,
        target_protocol_version="v0_gt_input",
        source_offline_store_version="7",
        split_manifest_hash=_campaign_split_hash(records),
    ).store_dir

    readers = {split: QhRolloutReader((store,), campaign_split=split) for split in (Stage.TRAIN, Stage.VAL, Stage.TEST)}
    assert [len(readers[split]) for split in (Stage.TRAIN, Stage.VAL, Stage.TEST)] == [1, 1, 1]
    assert [next(iter(readers[split].scenes)) for split in (Stage.TRAIN, Stage.VAL, Stage.TEST)] == [
        "scene-train",
        "scene-validation",
        "scene-test",
    ]
    assert all(len(reader.source_refs) == 1 for reader in readers.values())
    assert all(reader.provenance["stores"][0]["state_count"] == 2 for reader in readers.values())
    assert {readers[split][0].source_ref.source_sample_index for split in readers} == {0, 1, 2}


def test_reader_rejects_double_erased_campaign_identity(tmp_path: Path) -> None:
    records = build_rollout_records(horizon=2, num_samples=6, seed=7)[:1]
    records[0].lineage.source.campaign_split = "train"
    split_hash = _campaign_split_hash(records)
    store = write_rollout_zarr_store(
        tmp_path / "double-erased.zarr",
        records,
        discount_gamma=0.95,
        target_protocol_version="v0_gt_input",
        source_offline_store_version="7",
        split_manifest_hash=split_hash,
    ).store_dir
    root = zarr.open_group(store, mode="a")
    split_values = json.loads(bytes(np.asarray(root["dictionaries/split"])).decode("utf-8"))
    split_values.append("unknown")
    encoded = np.frombuffer(json.dumps(split_values).encode("utf-8"), dtype=np.uint8)
    root["dictionaries/split"].resize((encoded.size,))
    root["dictionaries/split"][:] = encoded
    root["sources/campaign_split_id"][:] = len(split_values) - 1
    root.attrs["campaign_split"] = "unknown"

    validation = RolloutZarrStoreReader(store).validate()
    assert not validation.ok
    assert any("campaign_split" in error for error in validation.errors)
    with pytest.raises(ValueError, match="canonical validation|campaign_split"):
        QhRolloutReader((store,))


def test_reader_campaign_filter_falls_back_to_legacy_physical_split(tmp_path: Path) -> None:
    records = build_rollout_records(horizon=2, num_samples=6, seed=7)[:1]
    records[0].lineage.source.split = "train"
    records[0].lineage.source.campaign_split = None
    store = write_rollout_zarr_store(
        tmp_path / "legacy-three-way.zarr",
        records,
        discount_gamma=0.95,
        target_protocol_version="v0_gt_input",
        source_offline_store_version="7",
        split_manifest_hash="fixture-split-manifest",
    ).store_dir

    assert [len(QhRolloutReader((store,), campaign_split=split)) for split in Stage] == [1, 0, 0]


def test_campaign_bound_store_rejects_all_unknown_campaign_assignments(tmp_path: Path) -> None:
    records = build_rollout_records(horizon=2, num_samples=6, seed=7)[:1]
    records[0].lineage.source.campaign_split = "train"
    store = write_rollout_zarr_store(
        tmp_path / "tampered.zarr",
        records,
        discount_gamma=0.95,
        target_protocol_version="v0_gt_input",
        source_offline_store_version="7",
        split_manifest_hash=_campaign_split_hash(records),
    ).store_dir
    root = zarr.open_group(store, mode="a")
    split_values = json.loads(bytes(np.asarray(root["dictionaries/split"])).decode("utf-8"))
    split_values.append("unknown")
    encoded = np.frombuffer(json.dumps(split_values).encode("utf-8"), dtype=np.uint8)
    root["dictionaries/split"].resize((encoded.size,))
    root["dictionaries/split"][:] = encoded
    unknown_id = len(split_values) - 1
    root["sources/campaign_split_id"][:] = unknown_id

    validation = RolloutZarrStoreReader(store).validate()
    assert not validation.ok
    assert any("unknown campaign split" in error for error in validation.errors)
    with pytest.raises(ValueError, match="canonical validation|unknown campaign split"):
        QhRolloutReader((store,))


def test_reader_admits_trainable_v1_store_and_preserves_mask_identity(tmp_path: Path) -> None:
    store = _write_v1_store(tmp_path / "v1.zarr")
    reader = QhRolloutReader((store,))
    root = reader._stores[0]  # noqa: SLF001
    assert root.contract.target_protocol == "v1_observed"
    zarr_root = zarr.open_group(store, mode="r")
    actor = np.asarray(zarr_root["candidates/actor_action_mask"], dtype=np.bool_)
    oracle = np.asarray(zarr_root["candidates/oracle_label_mask"], dtype=np.bool_)
    q_train = np.asarray(zarr_root["candidates/q_train_mask"], dtype=np.bool_)
    assert q_train.any()
    assert np.array_equal(q_train, actor & oracle)


@pytest.mark.parametrize(
    ("field", "replacement"),
    (("descriptor_hash", "c" * 64), ("explicit_target_hash", "c" * 16)),
)
def test_reader_rejects_well_shaped_tampered_v1_target_hash(
    tmp_path: Path,
    field: str,
    replacement: str,
) -> None:
    store = _write_v1_store(tmp_path / "v1.zarr")
    root = zarr.open_group(store, mode="a")
    dictionary = root[f"dictionaries/{field}"]
    values = json.loads(np.asarray(dictionary, dtype=np.uint8).tobytes().decode("utf-8"))
    values[0] = replacement
    encoded = np.frombuffer(json.dumps(values, separators=(",", ":")).encode("utf-8"), dtype=np.uint8)
    dictionary.resize((encoded.size,))
    dictionary[:] = encoded

    validation = RolloutZarrStoreReader(store).validate()
    assert not validation.ok
    assert any("canonical target evidence" in error for error in validation.errors)
    with pytest.raises(ValueError, match="canonical validation"):
        QhRolloutReader((store,))


def test_reader_rejects_v1_store_with_fabricated_target_source(tmp_path: Path) -> None:
    store = _write_v1_store(tmp_path / "v1.zarr")
    root = zarr.open_group(store, mode="a")
    payload = np.frombuffer(b'["fabricated_actor"]', dtype=np.uint8)
    root["dictionaries/target_source"].resize((payload.size,))
    root["dictionaries/target_source"][:] = payload
    with pytest.raises(ValueError, match="actor-visible|canonical validation|target-source"):
        QhRolloutReader((store,))


def test_reader_rejects_v1_store_with_out_of_range_target_source_id(tmp_path: Path) -> None:
    store = _write_v1_store(tmp_path / "v1.zarr")
    root = zarr.open_group(store, mode="a")
    root["targets/target_source_id"][0] = 99

    with pytest.raises(ValueError, match="target_source_id|canonical validation"):
        QhRolloutReader((store,))


@pytest.mark.parametrize("horizon", (1, 2, 4))
def test_reader_admits_h1_h2_h4(tmp_path: Path, horizon: int) -> None:
    reader = QhRolloutReader((_write_store(tmp_path / f"h{horizon}.zarr", horizon=horizon),))
    chain = reader[0]

    assert len(chain.candidate_pose_relative_root) == horizon
    assert chain.horizon_remaining.tolist() == list(range(horizon, 0, -1))
    assert reader.max_horizon == horizon


def test_reader_composes_h2_and_h4_without_horizon_compatibility(tmp_path: Path) -> None:
    reader = QhRolloutReader(
        (
            _write_store(tmp_path / "h2.zarr", horizon=2),
            _write_store(tmp_path / "h4.zarr", horizon=4),
        )
    )

    assert [len(reader[index].candidate_pose_relative_root) for index in range(len(reader))] == [2, 4]
    assert reader.max_horizon == 4
    assert not hasattr(reader.contract, "horizon")
    assert not hasattr(reader.contract, "split_manifest_hash")


def test_reader_validates_each_store_exactly_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stores = (
        _write_store(tmp_path / "h1.zarr", horizon=1),
        _write_store(tmp_path / "h4.zarr", horizon=4),
    )
    calls: list[Path] = []
    original = RolloutZarrStoreReader.validate

    def recording_validate(reader: RolloutZarrStoreReader) -> RolloutZarrValidationResult:
        calls.append(reader.store_dir)
        return original(reader)

    monkeypatch.setattr(RolloutZarrStoreReader, "validate", recording_validate)
    reader = QhRolloutReader(stores)
    _ = reader[0]
    _ = reader[1]

    assert calls == [store.resolve() for store in stores]


def test_reader_rejects_failed_canonical_validation_before_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _write_store(tmp_path / "rollouts.zarr")
    errors = [f"validation error {index}" for index in range(6)]
    result = RolloutZarrValidationResult(store, 0, 0, 0, errors)
    monkeypatch.setattr(RolloutZarrStoreReader, "validate", lambda _self: result)

    with pytest.raises(ValueError) as raised:
        QhRolloutReader((store,))

    message = str(raised.value)
    assert str(store) in message
    assert "6 error(s)" in message
    assert all(error in message for error in errors[:5])
    assert errors[5] not in message


def test_reader_rejects_conflicting_duplicate_source_identity(tmp_path: Path) -> None:
    first = _write_store(tmp_path / "first.zarr")
    second = _write_store(tmp_path / "second.zarr")
    zarr.open_group(second, mode="a")["sources/source_shard_row"][0] = 99

    with pytest.raises(ValueError, match="conflicting source identity.*sample_index=0"):
        QhRolloutReader((first, second))


def test_reader_rejects_mismatched_source_split_manifest_hash(tmp_path: Path) -> None:
    store = _write_store(tmp_path / "rollouts.zarr")
    zarr.open_group(store, mode="a").attrs["split_manifest_hash"] = "wrong-split-manifest"

    with pytest.raises(ValueError, match="split_manifest_hash"):
        QhRolloutReader((store,))


@pytest.mark.parametrize(
    ("array_path", "row", "value"),
    [
        ("steps/step_index", 1, 0),
        ("q_h/td_next_step_row_id", 0, -1),
        ("q_h/source_row_id", 1, 999),
        ("steps/num_candidates", 1, 0),
    ],
)
def test_reader_rejects_broken_canonical_chain(tmp_path: Path, array_path: str, row: int, value: int) -> None:
    store = _write_store(tmp_path / "rollouts.zarr")
    zarr.open_group(store, mode="a")[array_path][row] = value
    with pytest.raises(ValueError, match="canonical validation|empty candidate state"):
        QhRolloutReader((store,))


def test_reader_uses_bounded_payload_slices(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reader = QhRolloutReader((_write_store(tmp_path / "rollouts.zarr"),))
    reads: list[tuple[str, object]] = []
    original = zarr.Array.__getitem__

    def recording_getitem(array: zarr.Array, selection: object) -> object:
        reads.append((str(array.path), selection))
        return original(array, selection)

    monkeypatch.setattr(zarr.Array, "__getitem__", recording_getitem)
    chain = reader[0]

    assert len(chain.candidate_pose_relative_root) == 2
    payload_reads = [(path, selection) for path, selection in reads if path.startswith(("q_h/", "candidates/"))]
    assert payload_reads
    assert all(selection != slice(None) for _, selection in payload_reads)


def test_reader_pickle_reopens_worker_handles(tmp_path: Path) -> None:
    reader = QhRolloutReader((_write_store(tmp_path / "rollouts.zarr"),))
    expected = reader[0].candidate_reward[0].copy()
    restored = pickle.loads(pickle.dumps(reader))
    assert restored._roots == {}  # noqa: SLF001
    assert np.array_equal(restored[0].candidate_reward[0], expected)


def test_reader_resolves_sparse_persisted_ids(tmp_path: Path) -> None:
    store = _write_store(tmp_path / "rollouts.zarr", source_row_id=10)
    root = zarr.open_group(store, mode="a")
    step_ids = np.asarray([10, 20], dtype=np.int64)
    root["steps/step_row_id"][:] = step_ids
    root["q_h/state_step_row_id"][:] = step_ids
    root["q_h/td_next_step_row_id"][:] = np.asarray([20, -1], dtype=np.int64)
    root["selected_depth/step_row_id"][:] = step_ids
    for row, step_id in enumerate(step_ids.tolist()):
        candidate_rows = np.flatnonzero(np.asarray(root["candidates/step_row_id"]) == row)
        root["candidates/step_row_id"][candidate_rows] = step_id
    root["rollouts/rollout_row_id"][0] = 50
    root["lineage/rollout_row_id"][0] = 50
    root["steps/rollout_row_id"][:] = 50
    root["targets/target_row_id"][0] = 30
    root["rollouts/target_row_id"][0] = 30
    root["q_h/target_row_id"][:] = 30

    chain = QhRolloutReader((store,))[0]
    assert (chain.rollout_row_id, chain.target_row_id, chain.source_ref.source_sample_index) == (50, 30, 10)
