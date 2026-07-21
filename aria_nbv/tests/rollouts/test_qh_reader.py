"""Contract tests for the lazy storage-only Q_H reader."""

# ruff: noqa: S101

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pytest
import zarr

pytest.importorskip("efm3d")

from aria_nbv.lightning.qh_data import QhDataset
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
    assert construction_matrix_reads == []

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


def test_qh_reader_rejects_corrupt_transition_linkage_when_row_is_read(tmp_path) -> None:
    store = _write_store(tmp_path / "rollouts.zarr")
    root = zarr.open_group(store, mode="a")
    root["q_h/td_next_step_row_id"][0] = -1

    reader = QhRolloutReaderConfig(store_dirs=(store,)).setup_target()

    with pytest.raises(ValueError, match="terminal/next linkage"):
        reader[0]


def test_qh_reader_resolves_sparse_source_ids_without_row_position_assumption(tmp_path) -> None:
    store = _write_store(tmp_path / "rollouts.zarr", source_row_id=10)

    reader = QhRolloutReaderConfig(store_dirs=(store,)).setup_target()
    state = reader[0]

    assert state.lineage.source_row_id == 10
    assert state.lineage.source_sample_index == 10
    assert state.lineage.source_shard_row == 10
