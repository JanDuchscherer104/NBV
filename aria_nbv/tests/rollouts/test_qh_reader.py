"""Contracts for the bounded, horizon-agnostic ``Q_H`` reader."""

# ruff: noqa: S101

from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pytest
import torch
import zarr
from efm3d.aria.pose import PoseTW

pytest.importorskip("efm3d")

from aria_nbv.data_handling.qh_data.batching import collate_qh_chains
from aria_nbv.data_handling.qh_data.materialization import _tensor_chain
from aria_nbv.data_handling.vin_store.views import VinSnippetView
from aria_nbv.rollouts.inspection import q_h_evidence_rows
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


def _write_store(
    path: Path,
    *,
    horizon: int = 2,
    records: int = 1,
    source_row_id: int | None = None,
    selected_depth_enabled: bool = True,
) -> Path:
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
        selected_depth_enabled=selected_depth_enabled,
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


def _write_packed_early_terminal_store(path: Path) -> Path:
    records = build_rollout_records(horizon=4, num_samples=60, seed=7)[:3]
    factual_lengths = (3, 1, 2)
    for record, factual_length in zip(records, factual_lengths, strict=True):
        trajectory = record.evaluated.result.trajectories[0]
        trajectory.steps[:] = trajectory.steps[:factual_length]
        trajectory.terminated_early = True
        record.evaluated.steps = {
            key: value for key, value in record.evaluated.steps.items() if key[1] < factual_length
        }
    return write_rollout_zarr_store(
        path,
        records,
        discount_gamma=0.95,
        target_protocol_version="v0_gt_input",
        source_offline_store_version="7",
        split_manifest_hash="fixture-split-manifest",
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


def test_reader_reads_selected_cf_gt_depth_only_when_explicitly_requested(tmp_path: Path) -> None:
    """Rich Q_H reads retain selected mesh-depth evidence with its alignment metadata."""

    store = _write_store(tmp_path / "rollouts.zarr")
    chain = QhRolloutReader((store,), include_selected_depth=True)[0]

    assert chain.selected_depth_renderer == "Pytorch3DDepthRenderer"
    assert chain.selected_depth_m is not None
    assert chain.selected_depth_valid_mask is not None
    assert chain.selected_depth_focal_px is not None
    assert chain.selected_depth_principal_point_px is not None
    assert chain.selected_depth_image_size_hw is not None
    assert chain.selected_depth_m.shape[0] == len(chain.candidate_pose_relative_root)
    assert chain.selected_depth_m.dtype == np.float16
    assert chain.selected_depth_valid_mask.dtype == np.bool_
    assert len(chain.one_step_target_rri) == len(chain.candidate_pose_relative_root)
    for values, mask in zip(chain.one_step_target_rri, chain.label_mask, strict=True):
        assert np.isfinite(values[mask]).all()


def test_reader_preserves_renderer_metadata_without_loading_selected_depth(tmp_path: Path) -> None:
    enabled = QhRolloutReader((_write_store(tmp_path / "enabled.zarr"),))[0]
    disabled = QhRolloutReader((_write_store(tmp_path / "disabled.zarr", selected_depth_enabled=False),))[0]

    assert enabled.selected_depth_renderer == "Pytorch3DDepthRenderer"
    assert enabled.selected_depth_m is None
    assert disabled.selected_depth_renderer is None
    assert disabled.selected_depth_m is None


def test_reader_contract_records_selected_depth_geometry(tmp_path: Path) -> None:
    contract = QhRolloutReader((_write_store(tmp_path / "rollouts.zarr"),), include_selected_depth=True).contract

    assert contract.selected_depth_enabled
    assert contract.selected_depth_role == "selected_successor_state_history"
    assert contract.selected_depth_renderer == "Pytorch3DDepthRenderer"
    assert contract.selected_depth_image_size_hw == (240, 240)
    assert contract.selected_depth_dtype == "float16"
    assert contract.selected_depth_units == "m"
    assert contract.selected_depth_znear_m == pytest.approx(1e-3)
    assert contract.selected_depth_zfar_m == pytest.approx(20.0)
    assert contract.selected_depth_projection_model == "linear_pinhole_screen"
    assert contract.selected_depth_value_semantics == "camera_z_m"
    assert contract.selected_depth_pixel_convention == "half_pixel_centers_in_ndc_false"
    assert contract.selected_depth_camera_axes == "left_up_forward"
    assert contract.selected_depth_pose_convention == "root_from_camera"


def test_reader_round_trips_non_square_off_axis_selected_calibration(tmp_path: Path) -> None:
    records = build_rollout_records(horizon=2, num_samples=6, seed=7)[:1]
    for step in records[0].evaluated.result.trajectories[0].steps:
        evidence = records[0].evaluated.step(0, step.step_index).evaluation.evidence
        evidence.selected_depth_m = np.full((3, 5), 2.0, dtype=np.float32)
        evidence.selected_depth_valid_mask = np.ones((3, 5), dtype=np.bool_)
        evidence.selected_depth_focal_px = (7.0, 8.0)
        evidence.selected_depth_principal_point_px = (1.25, 0.75)
        evidence.selected_depth_image_size_hw = (3, 5)
    store = write_rollout_zarr_store(
        tmp_path / "off-axis.zarr",
        records,
        selected_depth_width_px=5,
        selected_depth_height_px=3,
    ).store_dir

    chain = QhRolloutReader((store,), include_selected_depth=True)[0]

    assert chain.selected_depth_m is not None and chain.selected_depth_m.shape == (2, 3, 5)
    assert chain.selected_depth_focal_px is not None
    assert chain.selected_depth_principal_point_px is not None
    assert chain.selected_depth_image_size_hw is not None
    assert chain.selected_depth_focal_px.tolist() == [[7.0, 8.0], [7.0, 8.0]]
    assert chain.selected_depth_principal_point_px.tolist() == [[1.25, 0.75], [1.25, 0.75]]
    assert chain.selected_depth_image_size_hw.tolist() == [[3, 5], [3, 5]]


def test_reader_rejects_non_cf_gt_selected_depth_provenance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A rich reader must not relabel an unknown selected-depth renderer as CF-GT."""

    store = _write_store(tmp_path / "rollouts.zarr")
    validation = RolloutZarrStoreReader(store).validate()
    root = zarr.open_group(store, mode="a")
    root.attrs["selected_depth_renderer"] = "UnknownDepthRenderer"
    monkeypatch.setattr(RolloutZarrStoreReader, "validate", lambda _self: validation)

    with pytest.raises(ValueError, match="CF-GT depth requires"):
        QhRolloutReader((store,), include_selected_depth=True)


@pytest.mark.parametrize(
    ("attribute", "value", "field"),
    (
        ("selected_depth_role", "other-role", "selected_depth_role"),
        ("selected_depth_renderer", "other-renderer", "selected_depth_renderer"),
        ("selected_depth_width_px", 320, "selected_depth_image_size_hw"),
        ("selected_depth_dtype", "float32", "selected_depth_dtype"),
        ("selected_depth_units", "mm", "selected_depth_units"),
        ("selected_depth_znear_m", 0.1, "selected_depth_znear_m"),
        ("selected_depth_zfar_m", 10.0, "selected_depth_zfar_m"),
        ("selected_depth_source_resolution", "resampled", "selected_depth_source_resolution"),
    ),
)
def test_reader_rejects_mixed_selected_depth_contracts_during_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    attribute: str,
    value: str | int | float,
    field: str,
) -> None:
    first = _write_store(tmp_path / "first.zarr")
    second = _write_store(tmp_path / "second.zarr")
    validations = {
        first.resolve(): RolloutZarrStoreReader(first).validate(),
        second.resolve(): RolloutZarrStoreReader(second).validate(),
    }
    zarr.open_group(second, mode="a").attrs[attribute] = value
    monkeypatch.setattr(
        RolloutZarrStoreReader,
        "validate",
        lambda reader: validations[reader.store_dir],
    )

    with pytest.raises(ValueError, match=f"incompatible {field}"):
        QhRolloutReader((first, second), include_selected_depth=True)


def test_lean_reader_ignores_unconsumed_selected_depth_geometry(tmp_path: Path) -> None:
    first = _write_store(tmp_path / "first.zarr")
    second = _write_store(tmp_path / "second.zarr", selected_depth_enabled=False)

    reader = QhRolloutReader((first, second))

    assert len(reader) == 2
    assert not reader.contract.selected_depth_enabled


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


def test_q_h_evidence_is_metadata_first_and_deep_counts_are_explicit(tmp_path: Path, monkeypatch) -> None:
    store = _write_v1_store(tmp_path / "v1.zarr")
    reader = RolloutZarrStoreReader(store)
    validation = reader.validate()
    assert validation.ok
    monkeypatch.setattr(reader, "validate", lambda: pytest.fail("accepted validation should be reused"))

    shallow = q_h_evidence_rows(reader, validation_result=validation)[0]
    assert shallow["available"] is True
    assert shallow["deep_count"] is False
    assert shallow["actor_valid_count"] is None
    assert shallow["oracle_valid_count"] is None
    assert shallow["trainable_count"] is None
    assert shallow["counted_state_rows"] is None
    assert shallow["truncated"] is None
    assert shallow["count_reason"] == "metadata does not prove mask counts; request deep_count"

    deep = q_h_evidence_rows(reader, deep_count=True, validation_result=validation)[0]
    root = zarr.open_group(store, mode="r")
    candidate_ids = np.asarray(root["q_h/candidate_row_id"], dtype=np.int64)
    valid = np.asarray(root["q_h/valid_action_mask"], dtype=np.bool_)
    trainable = np.asarray(root["q_h/q_train_mask"], dtype=np.bool_)
    factual_ids = np.asarray(root["candidates/candidate_row_id"], dtype=np.int64)
    factual_oracle = np.asarray(root["candidates/oracle_label_mask"], dtype=np.bool_)
    oracle_by_id = dict(zip(factual_ids.tolist(), factual_oracle.tolist(), strict=True))
    expected_oracle = sum(oracle_by_id.get(int(candidate_id), False) for candidate_id in candidate_ids.reshape(-1))
    assert deep["actor_valid_count"] == int(valid.sum())
    assert deep["oracle_valid_count"] == expected_oracle
    assert deep["trainable_count"] == int(trainable.sum())
    assert deep["padding_count"] == int((candidate_ids < 0).sum())
    assert deep["counted_state_rows"] == int(candidate_ids.shape[0])
    assert deep["total_state_rows"] == int(candidate_ids.shape[0])
    assert deep["truncated"] is False
    assert deep["count_reason"] == "explicit complete current-store mask projection"


def test_q_h_deep_count_uses_bounded_candidate_slices(tmp_path: Path, monkeypatch) -> None:
    store = _write_v1_store(tmp_path / "v1.zarr")
    reader = RolloutZarrStoreReader(store)
    validation = reader.validate()

    def reject_full_array(*_args, **_kwargs):
        raise AssertionError("Q_H deep count must not convert a whole Zarr array")

    monkeypatch.setattr(zarr.Array, "__array__", reject_full_array, raising=False)
    original_array = reader.array
    slice_keys: list[object] = []

    class SliceOnlyArray:
        def __init__(self, array):
            self._array = array

        @property
        def shape(self):
            return self._array.shape

        def __getitem__(self, key):
            if not isinstance(key, slice):
                raise AssertionError(f"whole-array or fancy indexing is not allowed: {key!r}")
            slice_keys.append(key)
            return self._array[key]

    def array(path: str):
        if path in {"candidates/candidate_row_id", "candidates/oracle_label_mask"}:
            return SliceOnlyArray(reader.root[path])
        return original_array(path)

    monkeypatch.setattr(reader, "array", array)
    row = q_h_evidence_rows(
        reader,
        deep_count=True,
        chunk_size=2,
        state_row_limit=1,
        validation_result=validation,
    )[0]
    assert row["deep_count"] is True
    assert row["count_reason"] == "explicit bounded-prefix current-store mask projection"
    assert row["counted_state_rows"] == 1
    assert row["total_state_rows"] == int(reader.root["q_h/candidate_row_id"].shape[0])
    assert row["truncated"] is True
    assert slice_keys
    assert all(isinstance(key, slice) for key in slice_keys)


def test_q_h_deep_count_supports_bounded_cancellation(tmp_path: Path) -> None:
    store = _write_v1_store(tmp_path / "v1.zarr")
    reader = RolloutZarrStoreReader(store)
    validation = reader.validate()
    progress: list[tuple[int, int]] = []

    row = q_h_evidence_rows(
        reader,
        deep_count=True,
        chunk_size=1,
        progress_callback=lambda completed, total: progress.append((completed, total)) or False,
        validation_result=validation,
    )[0]
    assert progress == [(1, int(reader.root["q_h/candidate_row_id"].shape[0]))]
    assert row["count_reason"] == "cancelled during bounded current-store mask projection"
    assert row["counted_state_rows"] == 1
    assert row["truncated"] is True


def test_q_h_deep_count_fails_closed_for_unsorted_factual_ids(tmp_path: Path, monkeypatch) -> None:
    store = _write_v1_store(tmp_path / "v1.zarr")
    reader = RolloutZarrStoreReader(store)
    validation = reader.validate()
    original_array = reader.array
    factual_ids = np.asarray(original_array("candidates/candidate_row_id"), dtype=np.int64)

    def array(path: str):
        if path == "candidates/candidate_row_id":
            return factual_ids[::-1]
        return original_array(path)

    monkeypatch.setattr(reader, "array", array)
    row = q_h_evidence_rows(reader, deep_count=True, validation_result=validation)[0]
    assert row["available"] is False
    assert "must be monotonic" in row["blocking_reason"]


def test_q_h_evidence_blocks_invalid_store_before_projection(tmp_path: Path) -> None:
    store = _write_v1_store(tmp_path / "v1.zarr")
    root = zarr.open_group(store, mode="a")
    root["targets/target_source_id"][0] = 99
    reader = RolloutZarrStoreReader(store)

    row = q_h_evidence_rows(reader, deep_count=True)[0]

    assert row["available"] is False
    assert row["deep_count"] is True
    assert row["blocking_reason"]


def test_reader_indexes_packed_early_terminal_chains_by_factual_steps(tmp_path: Path) -> None:
    reader = QhRolloutReader((_write_packed_early_terminal_store(tmp_path / "early.zarr"),))

    chains = [reader[index] for index in range(len(reader))]
    assert len(reader) == 3
    assert [len(chain.candidate_pose_relative_root) for chain in chains] == [3, 1, 2]
    assert [chain.rollout_row_id for chain in chains] == [0, 1, 2]
    assert [chain.horizon_remaining.tolist() for chain in chains] == [[4, 3, 2], [4], [4, 3]]
    assert reader.max_horizon == 3


def test_reader_materialization_preserves_n60_identity_across_packed_chains(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _write_packed_early_terminal_store(tmp_path / "early-n60.zarr")
    validation = RolloutZarrStoreReader(store).validate()
    root = zarr.open_group(store, mode="a")
    q_h = root["q_h"]
    candidate_rows = np.asarray(q_h["candidate_row_id"], dtype=np.int64)
    selected = np.asarray([0, 11, 12, 59, 0, 11], dtype=np.int64)
    q_h["selected_candidate_index"][:] = selected
    selected_rows = candidate_rows[np.arange(selected.size), selected]
    root["steps/selected_candidate_row_id"][:] = selected_rows
    q_h["td_selected_candidate_row_id"][:] = selected_rows
    monkeypatch.setattr(RolloutZarrStoreReader, "validate", lambda _self: validation)

    reader = QhRolloutReader((store,))
    chains = [
        _tensor_chain(
            reader[index],
            VinSnippetView(
                points_world=torch.zeros(2, 3),
                lengths=torch.tensor([2]),
                t_world_rig=PoseTW(torch.stack([PoseTW().tensor()])),
                t_world_snippet=PoseTW(torch.stack([PoseTW().tensor()])),
            ),
        )
        for index in range(len(reader))
    ]
    assert [len(chain.supervision.selected_index) for chain in chains] == [3, 1, 2]
    for chain in chains:
        for step, index in enumerate(chain.supervision.selected_index.tolist()):
            if step + 1 < len(chain.supervision.selected_index):
                assert torch.equal(
                    chain.actor.history_pose_relative_root.tensor()[step + 1, step],
                    chain.actor.candidate_pose_relative_root.tensor()[step, index],
                )
    selected_59 = [
        chain.actor.candidate_pose_relative_root.tensor()[step, index]
        for chain in chains
        for step, index in enumerate(chain.supervision.selected_index.tolist())
        if index == 59
    ]
    assert len(selected_59) == 1
    chain_with_59 = next(chain for chain in chains if 59 in chain.supervision.selected_index.tolist())
    assert not torch.equal(selected_59[0], chain_with_59.actor.candidate_pose_relative_root.tensor()[0, 11])
    batch = collate_qh_chains(chains)
    monkeypatch.setattr(torch.Tensor, "pin_memory", lambda value: value)
    transferred = batch.pin_memory().to("cpu")
    assert transferred.actor.step_mask.tolist() == [[True, True, True], [True, False, False], [True, True, False]]
    assert transferred.keys[0].rollout_row_id != transferred.keys[1].rollout_row_id


@pytest.mark.parametrize(
    "step_rollout_ids",
    (
        (99, 0, 0, 1, 2, 2),  # missing first rollout run
        (0, 0, 1, 0, 2, 2),  # interleaved first rollout run
        (0, 0, 0, 1, 2, 99),  # orphaned final step
    ),
)
def test_reader_rejects_invalid_factual_rollout_partition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    step_rollout_ids: tuple[int, ...],
) -> None:
    store = _write_packed_early_terminal_store(tmp_path / "early.zarr")
    validation = RolloutZarrStoreReader(store).validate()
    zarr.open_group(store, mode="a")["steps/rollout_row_id"][:] = np.asarray(step_rollout_ids, dtype=np.int64)
    monkeypatch.setattr(RolloutZarrStoreReader, "validate", lambda _self: validation)

    with pytest.raises(ValueError, match="ordered factual step run|non-contiguous factual|orphaned factual steps"):
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
    reader = QhRolloutReader((_write_store(tmp_path / "rollouts.zarr"),), include_selected_depth=True)
    reads: list[tuple[str, object]] = []
    original = zarr.Array.__getitem__

    def recording_getitem(array: zarr.Array, selection: object) -> object:
        reads.append((str(array.path), selection))
        return original(array, selection)

    monkeypatch.setattr(zarr.Array, "__getitem__", recording_getitem)
    chain = reader[0]

    assert len(chain.candidate_pose_relative_root) == 2
    payload_reads = [
        (path, selection) for path, selection in reads if path.startswith(("q_h/", "candidates/", "selected_depth/"))
    ]
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
