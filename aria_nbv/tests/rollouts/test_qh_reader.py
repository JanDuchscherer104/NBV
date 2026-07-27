"""Contract tests for the lazy storage-only Q_H reader."""

# ruff: noqa: S101

from __future__ import annotations

import pickle
from dataclasses import fields
from pathlib import Path

import numpy as np
import pytest
import zarr

pytest.importorskip("efm3d")

from aria_nbv.data_handling.qh import QhDataset
from aria_nbv.rollouts.qh_reader import QhRolloutReader, QhRolloutReaderConfig, QhStateLocator
from aria_nbv.rollouts.zarr_store import RolloutZarrStoreReader, write_rollout_zarr_store
from tests.rollout_fixtures import build_rollout_records


def _write_store(
    path: Path,
    *,
    horizon: int = 2,
    records: int = 1,
    discount_gamma: float = 0.95,
    source_row_id: int | None = None,
    source_manifest_hash: str | None = None,
    source_split_manifest_hash: str | None = None,
    lineage_target_protocol: str | None = None,
    lineage_reason_code_version: str | None = None,
    candidate_config_hash: str | None = None,
    oracle_config_hash: str | None = None,
    rollout_config_hash: str | None = None,
) -> Path:
    rollout_records = build_rollout_records(horizon=horizon, num_samples=6, seed=7)[:records]
    for record in rollout_records:
        if source_manifest_hash is not None:
            record.lineage.source.source_offline_store_manifest_hash = source_manifest_hash
        if source_split_manifest_hash is not None:
            record.lineage.source.split_manifest_hash = source_split_manifest_hash
        if lineage_target_protocol is not None:
            record.lineage.target.target_protocol_version = lineage_target_protocol
        if lineage_reason_code_version is not None:
            record.lineage.policy.reason_code_version = lineage_reason_code_version
        if candidate_config_hash is not None:
            record.lineage.policy.candidate_config_hash = candidate_config_hash
        if oracle_config_hash is not None:
            record.lineage.policy.oracle_config_hash = oracle_config_hash
        if rollout_config_hash is not None:
            record.lineage.policy.rollout_config_hash = rollout_config_hash
    if source_row_id is not None:
        assert records == 1
        rollout_records[0].lineage.source.source_row_id = source_row_id
        rollout_records[0].lineage.source.source_sample_index = source_row_id
        rollout_records[0].lineage.source.source_shard_row = source_row_id
    result = write_rollout_zarr_store(
        path,
        rollout_records,
        discount_gamma=discount_gamma,
        target_protocol_version="v0_gt_input",
        source_offline_store_version="7",
        split_manifest_hash="fixture-split-manifest",
    )
    return result.store_dir


def test_qh_reader_prefix_indexing_and_eager_parity(tmp_path) -> None:
    first = _write_store(tmp_path / "first.zarr")
    second = _write_store(tmp_path / "second.zarr")
    eager_first = RolloutZarrStoreReader(first).q_h_view()
    eager_second = RolloutZarrStoreReader(second).q_h_view()

    reader = QhRolloutReaderConfig(store_dirs=(first, second)).setup_target()

    assert len(reader) == 4
    assert [reader.locator(index) for index in range(len(reader))] == [
        QhStateLocator(0, 0),
        QhStateLocator(0, 1),
        QhStateLocator(1, 0),
        QhStateLocator(1, 1),
    ]
    for index, eager in ((0, eager_first), (1, eager_first), (2, eager_second), (3, eager_second)):
        state = reader[index]
        row = state.locator.state_row
        width = state.actor.candidate_row_id.shape[0]
        assert np.array_equal(state.actor.candidate_row_id, eager["candidate_row_id"][row, :width])
        rollout_row_id = state.lineage.rollout_row_id
        assert np.array_equal(
            state.actor.root_pose_world,
            RolloutZarrStoreReader((first, second)[index // 2]).array("rollouts/root_pose_world")[rollout_row_id],
        )
        assert np.array_equal(state.actor.actor_action_mask, eager["valid_action_mask"][row, :width])
        assert np.array_equal(state.supervision.q_train_mask, eager["q_train_mask"][row, :width])
        assert np.array_equal(
            state.supervision.invalid_reason_bitset,
            eager["invalid_reason_bitset"][row, :width],
        )
        assert np.allclose(
            state.supervision.one_step_target_root_gain,
            eager["one_step_target_root_gain"][row, :width],
            equal_nan=True,
        )
        assert state.transition.selected_candidate_index == int(eager["selected_candidate_index"][row])
        assert state.transition.selected_candidate_row_id == int(eager["td_selected_candidate_row_id"][row])
        assert state.transition.reward == pytest.approx(float(eager["td_reward"][row]))


def test_qh_reader_transition_history_and_terminal_contract(tmp_path) -> None:
    reader = QhRolloutReaderConfig(store_dirs=(_write_store(tmp_path / "rollouts.zarr"),)).setup_target()

    current = reader[0]
    terminal = reader[1]

    assert current.transition.next_state == QhStateLocator(0, 1)
    assert current.transition.terminal is False
    assert current.transition.discount == pytest.approx(0.95)
    assert current.actor.remaining_budget == 2
    assert current.actor.history_candidate_row_id.shape == (0,)

    assert terminal.transition.next_state is None
    assert terminal.transition.terminal is True
    assert terminal.transition.discount == 0.0
    assert terminal.actor.remaining_budget == 1
    assert terminal.actor.history_candidate_row_id.tolist() == [current.transition.selected_candidate_row_id]
    selected = current.transition.selected_candidate_index
    assert np.array_equal(
        terminal.actor.history_pose_world_cam[0],
        current.actor.candidate_pose_world_cam[selected],
    )
    assert terminal.lineage.source_row_id == current.lineage.source_row_id
    assert terminal.lineage.target_protocol_version == "v0_gt_input"
    assert terminal.lineage.target_source == "gt_obbs_oracle"


def test_qh_reader_provenance_uses_only_preflighted_metadata(tmp_path, monkeypatch) -> None:
    store = _write_store(tmp_path / "rollouts.zarr")
    reader = QhRolloutReaderConfig(store_dirs=(store,)).setup_target()
    monkeypatch.setattr(reader, "_root", lambda *_args: pytest.fail("provenance reopened Zarr"))

    provenance = reader.provenance

    assert provenance["stores"][0]["path"] == str(store)
    assert provenance["stores"][0]["manifest_sha256"]
    assert provenance["compatibility"]["schema_version"]
    assert provenance["compatibility"]["target_protocol_version"] == "v0_gt_input"


def test_qh_reader_uses_no_eager_or_oracle_audit_read_path(tmp_path, monkeypatch) -> None:
    store = _write_store(tmp_path / "rollouts.zarr", records=2)

    monkeypatch.setattr(
        RolloutZarrStoreReader,
        "validate",
        lambda *args, **kwargs: pytest.fail("production Q_H reader called generic validation"),
    )
    monkeypatch.setattr(
        RolloutZarrStoreReader,
        "q_h_view",
        lambda *args, **kwargs: pytest.fail("production Q_H reader called eager q_h_view"),
    )
    monkeypatch.setattr(
        RolloutZarrStoreReader,
        "array",
        lambda *args, **kwargs: pytest.fail("production Q_H reader called eager array"),
    )
    touched: list[str] = []
    reads: list[tuple[str, object]] = []
    original_getitem = zarr.Group.__getitem__
    original_array_getitem = zarr.Array.__getitem__

    def recording_getitem(group, key):
        touched.append(str(key))
        return original_getitem(group, key)

    def recording_array_getitem(array, selection):
        reads.append((str(array.path), selection))
        return original_array_getitem(array, selection)

    monkeypatch.setattr(zarr.Group, "__getitem__", recording_getitem)
    monkeypatch.setattr(zarr.Array, "__getitem__", recording_array_getitem)

    matrix_paths = {
        f"q_h/{name}"
        for name in (
            "candidate_row_id",
            "valid_action_mask",
            "q_train_mask",
            "position_id",
            "one_step_target_rri",
            "one_step_target_root_gain",
            "invalid_reason_bitset",
        )
    }

    def is_whole_matrix_row(selection: object) -> bool:
        if isinstance(selection, (int, np.integer)):
            return True
        if not isinstance(selection, tuple):
            return selection is Ellipsis or selection == slice(None)
        if len(selection) < 2:
            return True
        column = selection[1]
        return column is Ellipsis or column == slice(None)

    reader = QhRolloutReaderConfig(store_dirs=(store,)).setup_target()

    construction_matrix_reads = [(path, selection) for path, selection in reads if path in matrix_paths]
    assert construction_matrix_reads
    assert {path for path, _ in construction_matrix_reads} == matrix_paths
    assert all(
        isinstance(selection, tuple)
        and len(selection) == 2
        and isinstance(selection[0], (int, np.integer))
        and isinstance(selection[1], slice)
        and selection[1].stop is not None
        for _, selection in construction_matrix_reads
    )
    state_axis_reads = [
        (path, selection) for path, selection in reads if path.startswith("steps/") or path.startswith("q_h/")
    ]
    assert state_axis_reads
    assert all(
        isinstance(selection, (int, np.integer))
        or (isinstance(selection, tuple) and isinstance(selection[0], (int, np.integer)))
        for _, selection in state_axis_reads
    )

    reads.clear()
    state = reader[0]

    assert state.actor.candidate_row_id.size > 0
    assert not any(
        audit_name in key
        for key in touched
        for audit_name in ("selected_depth", "candidate_diagnostics", "target_eval_crops")
    )
    state_matrix_reads = [(path, selection) for path, selection in reads if path in matrix_paths]
    assert {path for path, _ in state_matrix_reads} == matrix_paths
    assert all(is_whole_matrix_row(selection) for _, selection in state_matrix_reads)


def test_qh_reader_pickle_drops_and_reopens_handles(tmp_path) -> None:
    reader = QhRolloutReaderConfig(store_dirs=(_write_store(tmp_path / "rollouts.zarr"),)).setup_target()
    expected = reader[0]
    assert reader._roots  # noqa: SLF001

    restored = pickle.loads(pickle.dumps(reader))

    assert restored._roots == {}  # noqa: SLF001
    actual = restored[0]
    assert restored._roots  # noqa: SLF001
    assert np.array_equal(actual.actor.candidate_row_id, expected.actor.candidate_row_id)


def test_qh_reader_scene_metadata_never_reads_state_payloads(tmp_path, monkeypatch) -> None:
    store = _write_store(tmp_path / "rollouts.zarr")
    reader = QhRolloutReaderConfig(store_dirs=(store,)).setup_target()
    reads: list[tuple[str, object]] = []
    original_array_getitem = zarr.Array.__getitem__

    def recording_array_getitem(array, selection):
        reads.append((str(array.path), selection))
        return original_array_getitem(array, selection)

    monkeypatch.setattr(zarr.Array, "__getitem__", recording_array_getitem)
    monkeypatch.setattr(
        QhRolloutReader,
        "__getitem__",
        lambda *_args, **_kwargs: pytest.fail("scene metadata materialized a Q_H state"),
    )

    assert reader.scene_ids == frozenset({"fixture_box"})
    assert reads == []


def test_qh_reader_rejects_corrupt_v0_descriptor_when_row_is_read(tmp_path) -> None:
    store = _write_store(tmp_path / "rollouts.zarr")
    root = zarr.open_group(store, mode="a")
    root["targets/target_relative_pose_reference_object"][0, 0] = np.nan

    reader = QhRolloutReaderConfig(store_dirs=(store,)).setup_target()

    with pytest.raises(ValueError, match="incomplete canonical V0 descriptor"):
        reader[0]


def test_qh_reader_rejects_corrupt_persisted_rollout_root(tmp_path) -> None:
    store = _write_store(tmp_path / "rollouts.zarr")
    root = zarr.open_group(store, mode="a")
    root["rollouts/root_pose_world"][0, 0] = np.nan

    reader = QhRolloutReaderConfig(store_dirs=(store,)).setup_target()

    with pytest.raises(ValueError, match="rollout root pose"):
        reader[0]


def test_qh_reader_rejects_heterogeneous_store_metadata(tmp_path) -> None:
    first = _write_store(tmp_path / "first.zarr", discount_gamma=0.95)
    second = _write_store(tmp_path / "second.zarr", discount_gamma=0.5)

    with pytest.raises(ValueError, match="heterogeneous.*discount_gamma"):
        QhRolloutReaderConfig(store_dirs=(first, second)).setup_target()


def test_qh_reader_accepts_rollout_horizons_up_to_padded_maximum(tmp_path) -> None:
    records = (
        build_rollout_records(horizon=1, num_samples=6, seed=7)[0],
        build_rollout_records(horizon=2, num_samples=6, seed=7)[1],
    )
    result = write_rollout_zarr_store(
        tmp_path / "mixed.zarr",
        records,
        discount_gamma=0.95,
        target_protocol_version="v0_gt_input",
        source_offline_store_version="7",
        split_manifest_hash="fixture-split-manifest",
    )

    reader = QhRolloutReaderConfig(store_dirs=(result.store_dir,)).setup_target()

    assert len(reader) == 3
    assert [reader[index].lineage.horizon for index in range(len(reader))] == [1, 2, 2]
    assert reader.q_h_horizon == 2


@pytest.mark.parametrize("config_field", ["candidate_config_hash", "oracle_config_hash", "rollout_config_hash"])
def test_qh_reader_rejects_cross_store_lineage_config_mismatch(tmp_path, config_field) -> None:
    first = _write_store(tmp_path / "first.zarr", **{config_field: "config-A"})
    second = _write_store(tmp_path / "second.zarr", **{config_field: "config-B"})

    with pytest.raises(ValueError, match=rf"heterogeneous.*{config_field}es"):
        QhRolloutReaderConfig(store_dirs=(first, second)).setup_target()


def test_qh_dataset_rejects_later_store_source_manifest_before_item_read(tmp_path, monkeypatch) -> None:
    first = _write_store(tmp_path / "first.zarr", source_manifest_hash="source-A")
    second = _write_store(tmp_path / "second.zarr", source_manifest_hash="source-B")
    reader = QhRolloutReaderConfig(store_dirs=(first, second)).setup_target()

    class ActorSource:
        requested_blocks: tuple[str, ...] = ()

        def index_for_sample(self, sample_index: int) -> int:
            assert sample_index == 0
            return 0

        def validate_lineage(self, _index: int, **expected) -> None:
            actual = expected["source_offline_store_manifest_hash"]
            if actual != "source-A":
                raise ValueError(f"source_offline_store_manifest_hash mismatch: {actual}")

        def __getitem__(self, _index: int):
            pytest.fail("source payload read during corpus admission")

    monkeypatch.setattr(
        QhRolloutReader,
        "__getitem__",
        lambda *_args, **_kwargs: pytest.fail("rollout payload read during corpus admission"),
    )

    with pytest.raises(ValueError, match="source_offline_store_manifest_hash.*source-B"):
        QhDataset(rollout_reader=reader, actor_source=ActorSource())  # type: ignore[arg-type]


def test_qh_reader_rejects_source_split_hash_that_differs_from_root(tmp_path) -> None:
    store = _write_store(
        tmp_path / "rollouts.zarr",
        source_split_manifest_hash="different-source-split",
    )

    with pytest.raises(ValueError, match="source rows.*root split_manifest_hash"):
        QhRolloutReaderConfig(store_dirs=(store,)).setup_target()


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("lineage_target_protocol", "v1_observed", "target_protocol_version_id.*root target_protocol_version"),
        ("lineage_reason_code_version", "different-reasons", "reason_code_version_id.*root reason_code_version"),
    ],
)
def test_qh_reader_rejects_lineage_versions_that_differ_from_root(tmp_path, field, value, match) -> None:
    store = _write_store(tmp_path / "rollouts.zarr", **{field: value})

    with pytest.raises(ValueError, match=match):
        QhRolloutReaderConfig(store_dirs=(store,)).setup_target()


def test_qh_reader_rejects_corrupt_transition_linkage_during_indexing(tmp_path) -> None:
    store = _write_store(tmp_path / "rollouts.zarr")
    root = zarr.open_group(store, mode="a")
    root["q_h/td_next_step_row_id"][0] = -1

    with pytest.raises(ValueError, match="broken or crossing successor"):
        QhRolloutReaderConfig(store_dirs=(store,)).setup_target()


def test_qh_reader_indexes_and_decodes_complete_chains_once(tmp_path) -> None:
    reader = QhRolloutReaderConfig(store_dirs=(_write_store(tmp_path / "rollouts.zarr", records=2),)).setup_target()

    assert len(reader) == 4  # Legacy transition surface until G004.
    assert reader.chain_count == 2
    first = reader.read_chain(0)
    second = reader.read_chain(1)

    assert first.lineage.rollout_row_id != second.lineage.rollout_row_id
    assert first.lineage.source_row_id != second.lineage.source_row_id
    assert len(first.state.candidate_pose_relative_root) == first.lineage.horizon == 2
    assert len(first.supervision.candidate_row_id) == 2
    assert first.transition.terminal.tolist() == [False, True]
    assert first.transition.discount.tolist() == pytest.approx([0.95, 0.0])
    assert first.state.remaining_budget.tolist() == [2, 1]
    assert all(candidate_ids.size > 0 for candidate_ids in first.supervision.candidate_row_id)


def test_qh_reader_chain_lineage_is_exact_and_ordered(tmp_path) -> None:
    reader = QhRolloutReaderConfig(store_dirs=(_write_store(tmp_path / "rollouts.zarr"),)).setup_target()
    lineage = reader.read_chain(0).lineage

    assert [field.name for field in fields(lineage)] == [
        "source_row_id",
        "source_sample_index",
        "source_sample_key",
        "source_shard_id",
        "source_shard_row",
        "scene_id",
        "snippet_id",
        "split",
        "source_cache_version",
        "source_offline_store_manifest_hash",
        "split_manifest_hash",
        "mesh_version",
        "target_row_id",
        "target_sem_id",
        "target_inst_id",
        "target_protocol_version",
        "target_source",
        "target_crop_policy",
        "schema_version",
        "reason_code_version",
        "return_semantics",
        "td_semantics",
        "reward_metric",
        "discount_gamma",
        "horizon",
        "rollout_row_id",
        "rollout_id",
        "chain_id",
        "root_time_ns",
        "root_trajectory_index",
        "root_frame_index",
        "policy",
        "branch_factor",
        "beam_width",
        "temperature",
        "random_seed",
        "termination_reason",
        "candidate_config_hash",
        "oracle_config_hash",
        "rollout_config_hash",
        "model_checkpoint_hash",
        "branch_schedule_id",
        "selection_rng_state_hash",
    ]
    assert lineage.target_protocol_version == "v0_gt_input"
    assert lineage.target_source == "gt_obbs_oracle"
    assert lineage.horizon == 2


@pytest.mark.parametrize(
    ("array_path", "row", "value", "match"),
    [
        ("steps/step_index", 1, 0, "contiguous step indices"),
        ("q_h/td_next_step_row_id", 0, -1, "broken or crossing successor"),
        ("q_h/source_row_id", 1, 999, "mismatched source/target lineage"),
        ("steps/num_candidates", 1, 0, "empty candidate state"),
    ],
)
def test_qh_reader_rejects_broken_chain_during_indexing(tmp_path, array_path, row, value, match) -> None:
    store = _write_store(tmp_path / "rollouts.zarr")
    zarr.open_group(store, mode="a")[array_path][row] = value

    with pytest.raises(ValueError, match=match):
        QhRolloutReaderConfig(store_dirs=(store,)).setup_target()


def test_qh_reader_rejects_duplicate_and_empty_rollout_chains(tmp_path) -> None:
    duplicate = _write_store(tmp_path / "duplicate.zarr", records=2)
    duplicate_root = zarr.open_group(duplicate, mode="a")
    duplicate_root["rollouts/rollout_row_id"][1] = duplicate_root["rollouts/rollout_row_id"][0]
    with pytest.raises(ValueError, match="duplicate.*rollout_row_id"):
        QhRolloutReaderConfig(store_dirs=(duplicate,)).setup_target()

    empty = _write_store(tmp_path / "empty.zarr", records=2)
    empty_root = zarr.open_group(empty, mode="a")
    empty_root["rollouts/rollout_row_id"][1] = 999
    with pytest.raises(ValueError, match="rollout_row_id=999.*unowned state rows"):
        QhRolloutReaderConfig(store_dirs=(empty,)).setup_target()


def test_qh_reader_chain_reads_bound_state_and_candidate_slices(tmp_path, monkeypatch) -> None:
    store = _write_store(tmp_path / "rollouts.zarr")
    reader = QhRolloutReaderConfig(store_dirs=(store,)).setup_target()
    reads: list[tuple[str, object]] = []
    original = zarr.Array.__getitem__

    def recording_getitem(array, selection):
        reads.append((str(array.path), selection))
        return original(array, selection)

    monkeypatch.setattr(zarr.Array, "__getitem__", recording_getitem)
    chain = reader.read_chain(0)

    assert len(chain.supervision.candidate_row_id) == 2
    matrix_reads = [(path, selection) for path, selection in reads if path.startswith("q_h/")]
    assert matrix_reads
    assert all(selection != slice(None) for _, selection in matrix_reads)
    candidate_reads = [(path, selection) for path, selection in reads if path.startswith("candidates/")]
    assert candidate_reads
    assert all(selection != slice(None) for _, selection in candidate_reads)


def test_qh_reader_rejects_candidate_misalignment_during_indexing(tmp_path) -> None:
    store = _write_store(tmp_path / "rollouts.zarr")
    root = zarr.open_group(store, mode="a")
    root["q_h/candidate_row_id"][0, 0] = 1

    with pytest.raises(ValueError, match="candidate ids are not a contiguous full-shell slice"):
        QhRolloutReaderConfig(store_dirs=(store,)).setup_target()


def test_qh_reader_rejects_corrupt_padded_candidate_tail(tmp_path) -> None:
    store = _write_store(tmp_path / "rollouts.zarr")
    root = zarr.open_group(store, mode="a")
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
    corruptions = (
        ("candidate_row_id", 999, "non-sentinel actor fields"),
        ("valid_action_mask", True, "non-sentinel actor fields"),
        ("q_train_mask", True, "non-sentinel actor fields"),
        ("position_id", 0, "non-sentinel actor fields"),
        ("invalid_reason_bitset", 1, "non-zero invalid reasons"),
        ("one_step_target_rri", 0.0, "finite supervision"),
        ("one_step_target_root_gain", 0.0, "finite supervision"),
    )
    for field, value, match in corruptions:
        array = root[f"q_h/{field}"]
        original = array[0, width]
        array[0, width] = value
        with pytest.raises(ValueError, match=match):
            QhRolloutReaderConfig(store_dirs=(store,)).setup_target()
        array[0, width] = original


def test_qh_reader_trims_every_chain_candidate_field_to_active_width(tmp_path) -> None:
    store = _write_store(tmp_path / "rollouts.zarr")
    root = zarr.open_group(store, mode="a")
    active_width = int(root["q_h"].attrs["max_candidates"])
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
        array.resize((state_count, active_width + 1))
        array[:, active_width] = sentinel
    root["q_h"].attrs["max_candidates"] = active_width + 1

    chain = QhRolloutReaderConfig(store_dirs=(store,)).setup_target().read_chain(0)

    for step_index, candidate_ids in enumerate(chain.supervision.candidate_row_id):
        width = candidate_ids.size
        assert width == active_width
        assert chain.state.candidate_pose_relative_root[step_index].shape[0] == width
        assert chain.state.candidate_position_id[step_index].shape[0] == width
        assert chain.state.actor_action_mask[step_index].shape[0] == width
        assert chain.supervision.q_train_mask[step_index].shape[0] == width
        assert chain.supervision.invalid_reason_bitset[step_index].shape[0] == width
        assert chain.supervision.one_step_target_rri[step_index].shape[0] == width
        assert chain.supervision.one_step_target_root_gain[step_index].shape[0] == width


def test_qh_reader_resolves_all_sparse_persisted_ids(tmp_path) -> None:
    store = _write_store(tmp_path / "rollouts.zarr", source_row_id=10)
    root = zarr.open_group(store, mode="a")

    step_ids = np.asarray([10, 20], dtype=np.int64)
    root["steps/step_row_id"][:] = step_ids
    root["q_h/state_step_row_id"][:] = step_ids
    root["q_h/td_next_step_row_id"][:] = np.asarray([20, -1], dtype=np.int64)
    for row, step_id in enumerate(step_ids.tolist()):
        start = int(np.flatnonzero(np.asarray(root["candidates/step_row_id"]) == row)[0])
        stop = start + int(root["steps/num_candidates"][row])
        root["candidates/step_row_id"][start:stop] = step_id

    candidate_ids = np.asarray(root["candidates/candidate_row_id"], dtype=np.int64) + 100
    root["candidates/candidate_row_id"][:] = candidate_ids
    padded_ids = np.asarray(root["q_h/candidate_row_id"], dtype=np.int64)
    padded_ids[padded_ids >= 0] += 100
    root["q_h/candidate_row_id"][:] = padded_ids
    root["steps/selected_candidate_row_id"][:] = (
        np.asarray(root["steps/selected_candidate_row_id"], dtype=np.int64) + 100
    )
    root["q_h/td_selected_candidate_row_id"][:] = (
        np.asarray(root["q_h/td_selected_candidate_row_id"], dtype=np.int64) + 100
    )

    root["rollouts/rollout_row_id"][0] = 50
    root["lineage/rollout_row_id"][0] = 50
    root["steps/rollout_row_id"][:] = 50
    root["targets/target_row_id"][0] = 30
    root["rollouts/target_row_id"][0] = 30
    root["q_h/target_row_id"][:] = 30

    reader = QhRolloutReaderConfig(store_dirs=(store,)).setup_target()
    chain = reader.read_chain(0)
    current = reader[0]
    successor = reader.read(current.transition.next_state)

    assert chain.lineage.rollout_row_id == 50
    assert chain.lineage.target_row_id == 30
    assert chain.lineage.source_row_id == 10
    assert chain.lineage.source_sample_index == 10
    assert chain.lineage.source_shard_row == 10
    assert chain.supervision.candidate_row_id[0][0] == 100
    assert current.transition.next_state == QhStateLocator(0, 1)
    assert successor.lineage.step_index == 1
    assert successor.actor.history_candidate_row_id.tolist() == [current.transition.selected_candidate_row_id]
