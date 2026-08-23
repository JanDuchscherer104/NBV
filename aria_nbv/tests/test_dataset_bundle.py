from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from aria_nbv.data_handling.vin_store.format import (
    VinOfflineBlockSpec,
    VinOfflineIndexRecord,
    VinOfflineManifest,
    VinOfflineMaterializedBlocks,
    VinOfflineShardSpec,
)
from aria_nbv.data_handling.vin_store.store import OFFLINE_DATASET_VERSION
from aria_nbv.dataset_bundle import (
    DatasetBundleSelection,
    build_dataset_bundle_summary,
    compute_dataset_bundle_deep_statistics,
    scan_root_gt_obb_target_opportunities,
)
from aria_nbv.rollouts.zarr_store import ROLLOUT_ZARR_SCHEMA_VERSION
from aria_nbv.utils.fingerprints import stable_msgspec_hash


def _write_root_store(root: Path) -> tuple[Path, str]:
    store = root / "vin"
    store.mkdir()
    manifest = VinOfflineManifest(
        version=OFFLINE_DATASET_VERSION,
        created_at="2026-07-21T00:00:00Z",
        source={},
        oracle={},
        vin={},
        materialized_blocks=VinOfflineMaterializedBlocks(
            backbone=False,
            depths=False,
            candidate_pcs=False,
            gt_obbs=True,
        ),
        stats={"num_samples": 2, "num_train": 1, "num_val": 1},
        provenance={},
        shards=[],
    )
    manifest.write(store / "manifest.json")
    records = [
        VinOfflineIndexRecord(0, "snippet-a", "scene-a", "snippet-a", "train", "shard-a", 0),
        VinOfflineIndexRecord(1, "snippet-b", "scene-b", "snippet-b", "val", "shard-b", 0),
    ]
    VinOfflineIndexRecord.write_many(store / "sample_index.jsonl", records)
    splits = store / "splits"
    splits.mkdir()
    np.save(splits / "train.npy", np.asarray([0], dtype=np.int64))
    np.save(splits / "val.npy", np.asarray([1], dtype=np.int64))
    return store, stable_msgspec_hash(manifest)


def _write_rollout_store(
    root: Path,
    *,
    name: str,
    source_hash: str,
    sample_index: int = 0,
    split: str = "train",
    counts: dict[str, int] | None = None,
) -> Path:
    store = root / name
    store.mkdir()
    payload = {
        "manifest_version": "rollout-store-manifest-v1",
        "schema_id": "aria_nbv.rollout_zarr_q_invalidity",
        "schema_version": ROLLOUT_ZARR_SCHEMA_VERSION,
        "root_attrs": {
            "schema_version": ROLLOUT_ZARR_SCHEMA_VERSION,
            "source_split": split,
            "split_manifest_hash": f"split-{name}",
            "q_h_horizon": 2,
        },
        "counts": counts or {"sources": 1, "targets": 2, "rollouts": 3, "steps": 6, "candidates": 24},
        "config_hashes": {
            "source_manifest": [source_hash],
            "split_manifest": [f"split-{name}"],
        },
        "generation": {"writer_config": {"profile": "pilot"}},
        "source_coverage": {
            "num_source_rows": 1,
            "scene_counts": {"scene-a": 1},
            "split_counts": {split: 1},
            "sources": [
                {
                    "source_row_id": 0,
                    "source_sample_index": sample_index,
                    "source_sample_key": "scene-a::snippet-a",
                    "scene_id": "scene-a",
                    "snippet_id": "snippet-a",
                    "split": split,
                    "source_shard_id": "shard-a",
                    "source_shard_row": 0,
                }
            ],
        },
    }
    (store / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    return store


def test_lightweight_bundle_aggregates_compatible_rollouts_without_duplicating_root(tmp_path: Path) -> None:
    root, source_hash = _write_root_store(tmp_path)
    first = _write_rollout_store(tmp_path, name="first.zarr", source_hash=source_hash)
    second = _write_rollout_store(
        tmp_path,
        name="second.zarr",
        source_hash=source_hash,
        counts={"sources": 1, "targets": 3, "rollouts": 4, "steps": 8, "candidates": 32},
    )

    evidence = build_dataset_bundle_summary(DatasetBundleSelection(root, (first, second)))

    assert evidence.verdict == "Incomplete"
    assert evidence.root["sample_count"] == 2
    assert evidence.aggregate["root_sample_count"] == 2
    assert evidence.aggregate["rollout_count"] == 7
    assert evidence.aggregate["step_count"] == 14
    assert evidence.aggregate["persisted_rollout_target_rows"] == 5
    assert evidence.aggregate["persisted_rollout_targets"] is None
    assert evidence.aggregate["root_target_opportunities"] is None
    assert evidence.aggregate["q_h_trainable_candidates"] is None
    assert all(row["included_in_training_totals"] for row in evidence.rollouts)
    json.dumps(evidence.to_jsonable(), sort_keys=True)


def test_incompatible_hash_and_split_rows_remain_visible_but_are_excluded(tmp_path: Path) -> None:
    root, source_hash = _write_root_store(tmp_path)
    compatible = _write_rollout_store(tmp_path, name="ok.zarr", source_hash=source_hash)
    wrong_hash = _write_rollout_store(tmp_path, name="wrong-hash.zarr", source_hash="other")
    wrong_split = _write_rollout_store(
        tmp_path,
        name="wrong-split.zarr",
        source_hash=source_hash,
        split="val",
    )

    evidence = build_dataset_bundle_summary(DatasetBundleSelection(root, (compatible, wrong_hash, wrong_split)))

    assert evidence.verdict == "Blocked"
    assert evidence.aggregate["rollout_count"] == 3
    excluded = [row for row in evidence.rollouts if not row["included_in_training_totals"]]
    assert {Path(str(row["path"])).name for row in excluded} == {"wrong-hash.zarr", "wrong-split.zarr"}
    assert any(finding.code == "source_manifest_hash_mismatch" for finding in evidence.findings)
    assert any(finding.code == "source_split_identity_mismatch" for finding in evidence.findings)


def test_blocked_root_excludes_every_rollout_from_training_totals_and_topology(tmp_path: Path) -> None:
    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="compatible.zarr", source_hash=source_hash)
    (root / "splits" / "train.npy").write_bytes(b"not-a-valid-npy")

    evidence = build_dataset_bundle_summary(DatasetBundleSelection(root, (rollout,)))

    assert evidence.verdict == "Blocked"
    assert evidence.rollouts[0]["included_in_training_totals"] is False
    assert evidence.aggregate["compatible_rollout_store_count"] == 0
    assert evidence.aggregate["rollout_count"] == 0
    assert evidence.topology["edges"][0]["resolution"] == "blocked"
    assert any(finding.code == "root_split_unreadable" for finding in evidence.findings)


def test_required_validation_controls_ready_verdict(monkeypatch, tmp_path: Path) -> None:
    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="ready.zarr", source_hash=source_hash)

    class _Reader:
        def __init__(self, _path: Path) -> None:
            pass

        def validate(self) -> SimpleNamespace:
            return SimpleNamespace(ok=True, errors=())

    monkeypatch.setattr("aria_nbv.dataset_bundle.RolloutZarrStoreReader", _Reader)
    evidence = build_dataset_bundle_summary(
        DatasetBundleSelection(root, (rollout,)),
        validate_rollouts=True,
    )

    assert evidence.verdict == "Ready"
    assert evidence.rollouts[0]["validation_status"] == "ok"


def test_coral_catalog_is_non_blocking_and_labels_missing_provenance(tmp_path: Path) -> None:
    root, _source_hash = _write_root_store(tmp_path)
    artifact = tmp_path / "rri_binner.json"
    artifact.write_text(json.dumps({"num_classes": 3, "edges": [-0.1, 0.2]}), encoding="utf-8")

    evidence = build_dataset_bundle_summary(
        DatasetBundleSelection(root, ()),
        coral_artifact_roots=(tmp_path,),
    )

    assert evidence.verdict == "Incomplete"
    assert any(finding.code == "no_rollout_supervision_selected" for finding in evidence.findings)
    assert evidence.coral_artifacts == (
        {
            "path": artifact.resolve().as_posix(),
            "num_classes": 3,
            "edge_count": 2,
            "class_counts": None,
            "fit_data_path": None,
            "fit_data_available": False,
            "provenance": "unavailable",
            "config_references": [],
            "size_bytes": artifact.stat().st_size,
            "mtime_unix": artifact.stat().st_mtime,
        },
    )


def test_deep_statistics_reports_trainable_coverage_without_mutating_summary(monkeypatch, tmp_path: Path) -> None:
    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="deep.zarr", source_hash=source_hash)

    class _Reader:
        def __init__(self, _path: Path) -> None:
            pass

        def array(self, path: str) -> np.ndarray:
            arrays = {
                "candidates/q_train_mask": np.asarray([True, False, True]),
                "candidates/target_rri": np.asarray([0.2, np.nan, -0.1], dtype=np.float32),
                "candidates/target_root_gain": np.asarray([0.3, np.nan, -0.2], dtype=np.float32),
                "steps/num_valid_candidates": np.asarray([2, 1]),
                "rollouts/horizon": np.asarray([2]),
                "rollouts/source_row_id": np.asarray([0]),
                "rollouts/target_row_id": np.asarray([0]),
                "sources/source_row_id": np.asarray([0]),
                "sources/sample_index": np.asarray([0]),
                "targets/target_row_id": np.asarray([0]),
                "targets/target_id": np.asarray([0]),
                "dictionaries/target": np.frombuffer(json.dumps(["target-a"]).encode("utf-8"), dtype=np.uint8),
            }
            return arrays[path]

    monkeypatch.setattr("aria_nbv.dataset_bundle.RolloutZarrStoreReader", _Reader)
    deep = compute_dataset_bundle_deep_statistics(DatasetBundleSelection(root, (rollout,)))

    assert deep["aggregate"]["q_h_trainable_candidates"] == 2
    assert deep["aggregate"]["finite_target_rri_candidates"] == 2
    assert deep["aggregate"]["persisted_rollout_unique_target_tasks"] == 1
    assert deep["aggregate"]["deep_rollout_scan_status"] == "available"
    assert deep["aggregate"]["root_gt_obb_target_opportunities"] is None
    assert deep["stores"][0]["target_rri"]["minimum"] < 0
    json.dumps(deep, sort_keys=True)


def test_deep_statistics_preserves_unavailable_status_when_selected_store_scan_fails(tmp_path: Path) -> None:
    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="manifest-only.zarr", source_hash=source_hash)

    deep = compute_dataset_bundle_deep_statistics(DatasetBundleSelection(root, (rollout,)))

    assert deep["aggregate"]["deep_rollout_scan_status"] == "unavailable"
    assert deep["aggregate"]["eligible_rollout_store_count"] == 1
    assert deep["aggregate"]["scanned_rollout_store_count"] == 0
    assert deep["aggregate"]["failed_rollout_store_count"] == 1
    assert deep["aggregate"]["persisted_rollout_unique_target_tasks"] is None
    assert deep["aggregate"]["q_h_trainable_candidates"] is None
    assert deep["aggregate"]["finite_target_rri_candidates"] is None


def test_root_gt_obb_scan_counts_only_finite_non_padding_rows(monkeypatch, tmp_path: Path) -> None:
    root, _source_hash = _write_root_store(tmp_path)
    manifest = VinOfflineManifest.read(root / "manifest.json")
    block = VinOfflineBlockSpec.for_zarr_array(
        name="gt.obbs",
        array_path="gt/obbs",
        dtype="float32",
        shape=[1, 2, 34],
    )
    manifest.shards = [
        VinOfflineShardSpec("shard-a", "shards/shard-a", 0, 1, {"gt.obbs": block}),
        VinOfflineShardSpec("shard-b", "shards/shard-b", 1, 1, {"gt.obbs": block}),
    ]
    manifest.write(root / "manifest.json")

    valid = np.zeros((34,), dtype=np.float32)
    valid[:6] = [0, 2, 0, 1, 0, 3]
    valid[18:30] = [1, 0, 0, 0, 1, 0, 0, 0, 1, 10, 20, 30]
    padded = np.full((34,), -1.0, dtype=np.float32)
    nonfinite = valid.copy()
    nonfinite[0] = np.nan

    class _Reader:
        def __init__(self, _config: object) -> None:
            pass

        def read_numeric_block(self, record: VinOfflineIndexRecord, _name: str) -> np.ndarray:
            return np.stack([valid, padded if record.sample_index == 0 else nonfinite])

        def read_optional_record(self, _record: VinOfflineIndexRecord, _name: str) -> object | None:
            return None

    monkeypatch.setattr("aria_nbv.data_handling.vin_store.target_inventory.VinOfflineStoreReader", _Reader)
    scan = scan_root_gt_obb_target_opportunities(root)

    assert scan["available"] is True
    assert scan["target_opportunity_count"] == 2
    assert scan["scene_counts"] == {"scene-a": 1, "scene-b": 1}
    assert scan["split_counts"] == {"train": 1, "val": 1}
    assert scan["semantic_role"] == "gt_obb_label_evaluation_target_opportunities"


def test_root_gt_obb_scan_does_not_fall_back_when_blocks_are_absent(tmp_path: Path) -> None:
    root, _source_hash = _write_root_store(tmp_path)

    scan = scan_root_gt_obb_target_opportunities(root)

    assert scan["available"] is False
    assert scan["target_opportunity_count"] is None
    assert scan["reason"] == "gt_obb_block_missing:shard-a,shard-b"
