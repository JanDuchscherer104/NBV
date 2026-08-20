from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch
from efm3d.aria.pose import PoseTW

from aria_nbv.data_handling.qh_data import QhActorTensors, QhChain, QhDatasetConfig
from aria_nbv.data_handling.qh_data.views import QhChainKey, QhSupervision
from aria_nbv.data_handling.vin_store.format import (
    VinOfflineBlockSpec,
    VinOfflineIndexRecord,
    VinOfflineManifest,
    VinOfflineMaterializedBlocks,
    VinOfflineShardSpec,
)
from aria_nbv.data_handling.vin_store.store import OFFLINE_DATASET_VERSION
from aria_nbv.data_handling.vin_store.views import VinSnippetView
from aria_nbv.dataset_bundle import (
    DatasetBundleSelection,
    build_dataset_bundle_summary,
    build_qh_corpus_readiness,
    compute_dataset_bundle_deep_statistics,
    preview_qh_batch,
    scan_root_gt_obb_target_opportunities,
)
from aria_nbv.rollouts.qh_reader import QhDataContract
from aria_nbv.rollouts.zarr_store import ROLLOUT_ZARR_SCHEMA_VERSION
from aria_nbv.utils import Stage
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
        stats={"num_samples": 2, "num_train": 1, "num_val": 1, "storage_bytes": 200},
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
        "storage_bytes": 600,
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


_QH_CONTRACT = QhDataContract(
    schema_version=ROLLOUT_ZARR_SCHEMA_VERSION,
    target_protocol="v0_gt_input",
    reward_metric="target-root-gain",
    return_semantics="finite-horizon",
    td_semantics="fitted-q",
    discount_gamma=0.95,
    reason_code_version="reasons-v1",
    actor_store_version=str(OFFLINE_DATASET_VERSION),
)


def _qh_chain(*, scene: str, steps: int, width: int, offset: int) -> QhChain:
    identity = PoseTW().tensor()
    candidate_poses = torch.stack([identity] * (steps * width)).reshape(steps, width, 12)
    step_mask = torch.ones(steps, dtype=torch.bool)
    candidate_mask = torch.ones(steps, width, dtype=torch.bool)
    history_mask = torch.arange(steps)[:, None] > torch.arange(steps)
    return QhChain(
        actor=QhActorTensors(
            vin_snippet=VinSnippetView(
                points_world=torch.zeros(2, 3),
                lengths=torch.tensor([2]),
                t_world_rig=PoseTW(torch.stack([identity])),
                t_world_snippet=PoseTW(torch.stack([identity])),
            ),
            root_pose_world=identity,
            target_pose_relative_root=identity,
            target_extents=torch.ones(3),
            candidate_pose_relative_root=candidate_poses,
            candidate_mask=candidate_mask,
            action_mask=candidate_mask,
            history_pose_relative_root=torch.zeros(steps, steps, 12),
            history_mask=history_mask,
            horizon_remaining=torch.arange(steps, 0, -1),
            step_mask=step_mask,
        ),
        supervision=QhSupervision(
            label_mask=candidate_mask,
            candidate_reward=torch.ones(steps, width),
            selected_index=torch.zeros(steps, dtype=torch.int64),
            discount=torch.cat((torch.full((max(steps - 1, 0),), 0.95), torch.zeros(1))),
            terminal=torch.arange(steps) == steps - 1,
        ),
        key=QhChainKey(offset, offset, offset, scene, offset),
    )


class _QhStageDataset:
    def __init__(
        self,
        stage: Stage,
        chains: tuple[QhChain, ...],
        *,
        contract: QhDataContract = _QH_CONTRACT,
    ) -> None:
        self.stage = stage
        self.chains = chains
        self.contract = contract
        self.scenes = frozenset(chain.key.scene_id for chain in chains)
        self.max_horizon = max((chain.num_steps for chain in chains), default=0)
        self.provenance = {"stage": stage, "stores": ["fixture.zarr"]}

    def __len__(self) -> int:
        return len(self.chains)

    def __getitem__(self, index: int) -> QhChain:
        return self.chains[index]


def _patch_qh_stages(
    monkeypatch,
    stages: dict[Stage, _QhStageDataset],
    captured: list[QhDatasetConfig] | None = None,
) -> None:
    def _setup(config: QhDatasetConfig) -> _QhStageDataset:
        if captured is not None:
            captured.append(config)
        assert config.split is not None
        return stages[config.split]

    monkeypatch.setattr(QhDatasetConfig, "setup_target", _setup)


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


def test_qh_readiness_constructs_real_datamodule_and_normalizes_storage(monkeypatch, tmp_path: Path) -> None:
    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="qh.zarr", source_hash=source_hash)
    stages = {
        Stage.TRAIN: _QhStageDataset(
            Stage.TRAIN,
            (
                _qh_chain(scene="scene-train", steps=1, width=2, offset=0),
                _qh_chain(scene="scene-train", steps=2, width=2, offset=1),
            ),
        ),
        Stage.VAL: _QhStageDataset(
            Stage.VAL,
            (_qh_chain(scene="scene-val", steps=1, width=2, offset=2),),
        ),
        Stage.TEST: _QhStageDataset(
            Stage.TEST,
            (_qh_chain(scene="scene-test", steps=1, width=2, offset=3),),
        ),
    }
    captured: list[QhDatasetConfig] = []
    _patch_qh_stages(monkeypatch, stages, captured)

    readiness = build_qh_corpus_readiness(
        DatasetBundleSelection(root, (rollout,)),
        batch_size=2,
        seed=17,
    )

    assert readiness.verdict == "Ready"
    assert readiness.scene_disjoint is True
    assert [row.stage for row in readiness.stages] == [Stage.TRAIN, Stage.VAL, Stage.TEST]
    assert [row.chain_count for row in readiness.stages] == [2, 1, 1]
    assert [row.state_count for row in readiness.stages] == [3, 1, 1]
    assert [row.trainable_candidate_count for row in readiness.stages] == [6, 2, 2]
    assert readiness.loader_settings == {
        "batch_size": 2,
        "num_workers": 0,
        "pin_memory": False,
        "persistent_workers": False,
        "seed": 17,
    }
    assert readiness.contract is not None and readiness.contract["target_protocol"] == "v0_gt_input"
    assert [metric.value for metric in readiness.storage] == [100.0, 150.0, 120.0, 60.0]
    assert [config.split for config in captured] == [Stage.TRAIN, Stage.VAL, Stage.TEST]
    assert all(config.actor.store_dir == root for config in captured)
    json.dumps(readiness.to_jsonable(), sort_keys=True)


def test_qh_batch_preview_is_seeded_and_reports_real_padding(monkeypatch, tmp_path: Path) -> None:
    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="qh.zarr", source_hash=source_hash)
    stages = {
        Stage.TRAIN: _QhStageDataset(
            Stage.TRAIN,
            (
                _qh_chain(scene="scene-train", steps=1, width=2, offset=0),
                _qh_chain(scene="scene-train", steps=2, width=1, offset=1),
            ),
        ),
        Stage.VAL: _QhStageDataset(Stage.VAL, ()),
        Stage.TEST: _QhStageDataset(Stage.TEST, ()),
    }
    _patch_qh_stages(monkeypatch, stages)
    selection = DatasetBundleSelection(root, (rollout,))

    first = preview_qh_batch(selection, stage=Stage.TRAIN, chain_index=1, batch_size=2, seed=11)
    second = preview_qh_batch(selection, stage="train", chain_index=1, batch_size=2, seed=11)

    assert first == second
    assert first.selected_chain_steps == 2
    assert first.shapes["candidate_pose_relative_root"] == (2, 2, 2, 12)
    assert first.shapes["label_mask"] == (2, 2, 2)
    assert sorted(first.batch_step_counts) == [1, 2]
    assert first.step_padding_count == 1
    assert first.candidate_padding_count == 4
    assert first.action_count == first.trainable_candidate_count == 4
    json.dumps(first.to_jsonable(), sort_keys=True)


def test_qh_readiness_fails_closed_for_empty_train_overlap_and_contract_mismatch(monkeypatch, tmp_path: Path) -> None:
    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="qh.zarr", source_hash=source_hash)
    selection = DatasetBundleSelection(root, (rollout,))

    empty_train = {
        Stage.TRAIN: _QhStageDataset(Stage.TRAIN, ()),
        Stage.VAL: _QhStageDataset(Stage.VAL, (_qh_chain(scene="scene-val", steps=1, width=1, offset=0),)),
        Stage.TEST: _QhStageDataset(Stage.TEST, ()),
    }
    _patch_qh_stages(monkeypatch, empty_train)
    empty = build_qh_corpus_readiness(selection)
    assert empty.verdict == "Blocked"
    assert "training stage" in empty.blockers[0]

    overlap = {
        Stage.TRAIN: _QhStageDataset(Stage.TRAIN, (_qh_chain(scene="shared", steps=1, width=1, offset=0),)),
        Stage.VAL: _QhStageDataset(Stage.VAL, (_qh_chain(scene="shared", steps=1, width=1, offset=1),)),
        Stage.TEST: _QhStageDataset(Stage.TEST, ()),
    }
    _patch_qh_stages(monkeypatch, overlap)
    overlapping = build_qh_corpus_readiness(selection)
    assert overlapping.verdict == "Blocked"
    assert "overlap scenes" in overlapping.blockers[0]

    mismatch = {
        Stage.TRAIN: _QhStageDataset(Stage.TRAIN, (_qh_chain(scene="train", steps=1, width=1, offset=0),)),
        Stage.VAL: _QhStageDataset(
            Stage.VAL,
            (_qh_chain(scene="val", steps=1, width=1, offset=1),),
            contract=replace(_QH_CONTRACT, reward_metric="scene-rri"),
        ),
        Stage.TEST: _QhStageDataset(Stage.TEST, ()),
    }
    _patch_qh_stages(monkeypatch, mismatch)
    incompatible = build_qh_corpus_readiness(selection)
    assert incompatible.verdict == "Blocked"
    assert "incompatible learning contracts" in incompatible.blockers[0]


def test_qh_readiness_rejects_bundle_binding_before_dataset_construction(monkeypatch, tmp_path: Path) -> None:
    root, _source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="tampered.zarr", source_hash="wrong-root")
    called = False

    def _unexpected_setup(_config: QhDatasetConfig):
        nonlocal called
        called = True
        raise AssertionError("dataset construction must not run")

    monkeypatch.setattr(QhDatasetConfig, "setup_target", _unexpected_setup)
    readiness = build_qh_corpus_readiness(DatasetBundleSelection(root, (rollout,)))

    assert readiness.verdict == "Blocked"
    assert not called
    assert any("manifest hash" in blocker for blocker in readiness.blockers)


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
    padded = np.full((34,), -1.0, dtype=np.float32)
    nonfinite = valid.copy()
    nonfinite[0] = np.nan

    class _Reader:
        def __init__(self, _config: object) -> None:
            pass

        def read_numeric_block(self, record: VinOfflineIndexRecord, _name: str) -> np.ndarray:
            return np.stack([valid, padded if record.sample_index == 0 else nonfinite])

    monkeypatch.setattr("aria_nbv.dataset_bundle.VinOfflineStoreReader", _Reader)
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
