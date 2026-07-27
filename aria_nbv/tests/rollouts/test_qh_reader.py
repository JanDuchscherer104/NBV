"""Contract tests for the lazy chain-native ``Q_H`` storage reader."""

# ruff: noqa: S101

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pytest
import zarr

pytest.importorskip("efm3d")

from aria_nbv.data_handling.qh import QhChainLineage
from aria_nbv.rollouts.qh_reader import QhRolloutReaderConfig
from aria_nbv.rollouts.zarr_store import write_rollout_zarr_store
from tests.rollout_fixtures import build_rollout_records


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


def test_reader_indexes_each_complete_chain_once(tmp_path: Path) -> None:
    reader = QhRolloutReaderConfig(store_dirs=(_write_store(tmp_path / "rollouts.zarr", records=2),)).setup_target()

    assert len(reader) == 2
    ids = [QhChainLineage(*reader[index].lineage).rollout_row_id for index in range(len(reader))]
    assert ids[0] != ids[1]
    assert QhChainLineage(*reader[-1].lineage).rollout_row_id == ids[-1]
    with pytest.raises(IndexError, match="outside corpus length"):
        _ = reader[2]


def test_reader_decodes_candidate_bearing_states_without_terminal_empty_row(tmp_path: Path) -> None:
    chain = QhRolloutReaderConfig(store_dirs=(_write_store(tmp_path / "rollouts.zarr"),)).setup_target()[0]
    lineage = QhChainLineage(*chain.lineage)

    assert lineage.horizon == 2
    assert len(chain.candidate_row_id) == 2
    assert chain.terminal.tolist() == [False, True]
    assert chain.discount.tolist() == pytest.approx([0.95, 0.0])
    assert chain.remaining_budget.tolist() == [2, 1]
    assert all(value.size > 0 for value in chain.candidate_row_id)
    assert all(value.shape[-1] == 12 for value in chain.candidate_pose_relative_root)


@pytest.mark.parametrize(
    ("array_path", "row", "value", "match"),
    [
        ("steps/step_index", 1, 0, "contiguous step indices"),
        ("q_h/td_next_step_row_id", 0, -1, "broken or crossing successor"),
        ("q_h/source_row_id", 1, 999, "mismatched source/target lineage"),
        ("steps/num_candidates", 1, 0, "empty candidate state"),
    ],
)
def test_reader_rejects_broken_chain_during_indexing(
    tmp_path: Path, array_path: str, row: int, value: int, match: str
) -> None:
    store = _write_store(tmp_path / "rollouts.zarr")
    zarr.open_group(store, mode="a")[array_path][row] = value
    with pytest.raises(ValueError, match=match):
        QhRolloutReaderConfig(store_dirs=(store,)).setup_target()


def test_reader_rejects_duplicate_and_unowned_rollout_chains(tmp_path: Path) -> None:
    duplicate = _write_store(tmp_path / "duplicate.zarr", records=2)
    root = zarr.open_group(duplicate, mode="a")
    root["rollouts/rollout_row_id"][1] = root["rollouts/rollout_row_id"][0]
    with pytest.raises(ValueError, match="duplicate.*rollout_row_id"):
        QhRolloutReaderConfig(store_dirs=(duplicate,)).setup_target()

    unowned = _write_store(tmp_path / "unowned.zarr", records=2)
    zarr.open_group(unowned, mode="a")["rollouts/rollout_row_id"][1] = 999
    with pytest.raises(ValueError, match="rollout_row_id=999.*unowned state rows"):
        QhRolloutReaderConfig(store_dirs=(unowned,)).setup_target()


def test_reader_uses_bounded_state_and_candidate_slices(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reader = QhRolloutReaderConfig(store_dirs=(_write_store(tmp_path / "rollouts.zarr"),)).setup_target()
    reads: list[tuple[str, object]] = []
    original = zarr.Array.__getitem__

    def recording_getitem(array: zarr.Array, selection: object) -> object:
        reads.append((str(array.path), selection))
        return original(array, selection)

    monkeypatch.setattr(zarr.Array, "__getitem__", recording_getitem)
    chain = reader[0]

    assert len(chain.candidate_row_id) == 2
    payload_reads = [(path, selection) for path, selection in reads if path.startswith(("q_h/", "candidates/"))]
    assert payload_reads
    assert all(selection != slice(None) for _, selection in payload_reads)


def test_reader_pickle_drops_and_reopens_worker_handles(tmp_path: Path) -> None:
    reader = QhRolloutReaderConfig(store_dirs=(_write_store(tmp_path / "rollouts.zarr"),)).setup_target()
    expected = reader[0].candidate_row_id[0].copy()
    restored = pickle.loads(pickle.dumps(reader))
    assert restored._roots == {}  # noqa: SLF001
    assert np.array_equal(restored[0].candidate_row_id[0], expected)


def test_reader_rejects_candidate_misalignment_and_corrupt_padding(tmp_path: Path) -> None:
    misaligned = _write_store(tmp_path / "misaligned.zarr")
    zarr.open_group(misaligned, mode="a")["q_h/candidate_row_id"][0, 0] = 1
    with pytest.raises(ValueError, match="contiguous full-shell slice"):
        QhRolloutReaderConfig(store_dirs=(misaligned,)).setup_target()

    padded = _write_store(tmp_path / "padded.zarr")
    root = zarr.open_group(padded, mode="a")
    width = int(root["q_h"].attrs["max_candidates"])
    state_count = int(root["q_h/state_step_row_id"].shape[0])
    sentinels = {
        "candidate_row_id": -1,
        "valid_action_mask": False,
        "q_train_mask": False,
        "position_id": -1,
        "invalid_reason_bitset": 0,
        "one_step_target_rri": np.nan,
        "one_step_target_root_gain": np.nan,
    }
    for field, sentinel in sentinels.items():
        array = root[f"q_h/{field}"]
        array.resize((state_count, width + 1))
        array[:, width] = sentinel
    root["q_h"].attrs["max_candidates"] = width + 1
    root["q_h/invalid_reason_bitset"][0, width] = 1
    with pytest.raises(ValueError, match="non-zero invalid reasons"):
        QhRolloutReaderConfig(store_dirs=(padded,)).setup_target()


def test_reader_resolves_sparse_persisted_ids(tmp_path: Path) -> None:
    store = _write_store(tmp_path / "rollouts.zarr", source_row_id=10)
    root = zarr.open_group(store, mode="a")
    step_ids = np.asarray([10, 20], dtype=np.int64)
    root["steps/step_row_id"][:] = step_ids
    root["q_h/state_step_row_id"][:] = step_ids
    root["q_h/td_next_step_row_id"][:] = np.asarray([20, -1], dtype=np.int64)
    for row, step_id in enumerate(step_ids.tolist()):
        candidate_rows = np.flatnonzero(np.asarray(root["candidates/step_row_id"]) == row)
        root["candidates/step_row_id"][candidate_rows] = step_id
    candidate_ids = np.asarray(root["candidates/candidate_row_id"], dtype=np.int64) + 100
    root["candidates/candidate_row_id"][:] = candidate_ids
    padded_ids = np.asarray(root["q_h/candidate_row_id"], dtype=np.int64)
    padded_ids[padded_ids >= 0] += 100
    root["q_h/candidate_row_id"][:] = padded_ids
    root["steps/selected_candidate_row_id"][:] = np.asarray(root["steps/selected_candidate_row_id"]) + 100
    root["q_h/td_selected_candidate_row_id"][:] = np.asarray(root["q_h/td_selected_candidate_row_id"]) + 100
    root["rollouts/rollout_row_id"][0] = 50
    root["lineage/rollout_row_id"][0] = 50
    root["steps/rollout_row_id"][:] = 50
    root["targets/target_row_id"][0] = 30
    root["rollouts/target_row_id"][0] = 30
    root["q_h/target_row_id"][:] = 30

    chain = QhRolloutReaderConfig(store_dirs=(store,)).setup_target()[0]
    lineage = QhChainLineage(*chain.lineage)
    assert (lineage.rollout_row_id, lineage.target_row_id, lineage.source_row_id) == (50, 30, 10)
    assert chain.candidate_row_id[0][0] == 100
