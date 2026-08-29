from __future__ import annotations

import json
import os
import signal
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest
import torch
from efm3d.aria.pose import PoseTW

import aria_nbv.dataset_bundle as dataset_bundle
from aria_nbv.data_handling.qh_data import QhActorTensors, QhChain, QhDatasetConfig
from aria_nbv.data_handling.qh_data.views import QhActorStateContract, QhChainKey, QhSupervision
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
    DatasetBundleGenerationChangedError,
    DatasetBundleSelection,
    DatasetBundleSummaryRequest,
    FrozenJsonArray,
    FrozenJsonObject,
    QhReadinessContract,
    assert_dataset_bundle_generation_current,
    build_dataset_bundle_summary,
    build_qh_corpus_readiness,
    capture_dataset_bundle_generation,
    compute_dataset_bundle_deep_statistics,
    inspect_dataset_bundle,
    preview_qh_batch,
    scan_root_gt_obb_target_opportunities,
)
from aria_nbv.rollouts.manifest import manifest_sha256
from aria_nbv.rollouts.qh_geometry import QhGeometryContract
from aria_nbv.rollouts.qh_reader import QhDataContract
from aria_nbv.rollouts.shard_manifest import RolloutShardEntry, RolloutShardRow, build_rollout_split_manifest_hash
from aria_nbv.rollouts.zarr_store import ROLLOUT_ZARR_SCHEMA_VERSION
from aria_nbv.utils import Stage
from aria_nbv.utils.fingerprints import stable_msgspec_hash


def test_dataset_bundle_generation_is_bounded_stable_and_population_order_independent(tmp_path: Path) -> None:
    root = tmp_path / "root"
    first = tmp_path / "first.zarr"
    second = tmp_path / "second.zarr"
    for store in (root, first, second):
        store.mkdir()
        (store / "manifest.json").write_text("{}", encoding="utf-8")
    payload = first / "candidates" / "target_rri" / "c" / "0"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"payload-chunk")

    _selection, baseline = capture_dataset_bundle_generation(root, (first, second))
    _selection, permuted = capture_dataset_bundle_generation(root, (second, first))
    payload.write_bytes(b"changed-payload-chunk")
    _selection, payload_changed = capture_dataset_bundle_generation(root, (first, second))

    assert baseline == permuted
    assert payload_changed == baseline
    assert all("candidates/" not in row[0] for entry in baseline.rollouts for row in entry.metadata)


def test_dataset_bundle_generation_digest_uses_versioned_canonical_preimage(tmp_path: Path) -> None:
    root = tmp_path / "root"
    rollout = tmp_path / "rollout.zarr"
    root.mkdir()
    rollout.mkdir()

    _selection, generation = capture_dataset_bundle_generation(root, (rollout,))
    payload = {
        "root": dataset_bundle._generation_entry_json(generation.root),
        "rollouts": [dataset_bundle._generation_entry_json(entry) for entry in generation.rollouts],
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    assert generation.identity_version == "dataset-bundle-generation-v1"
    assert "generation_digest" not in canonical_json
    assert (
        generation.generation_digest == sha256(f"{generation.identity_version}\n{canonical_json}".encode()).hexdigest()
    )


def test_dataset_bundle_generation_parses_authority_fields_into_digest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    rollout = tmp_path / "rollout.zarr"
    root.mkdir()
    rollout.mkdir()
    (root / "manifest.json").write_text('{"version":10}', encoding="utf-8")
    (rollout / "manifest.json").write_text(
        '{"manifest_version":"rollout-store-manifest-v1","schema_version":"0.1-draft"}',
        encoding="utf-8",
    )
    for name in ("_SUCCESS.json", "_owner.json"):
        (rollout / name).write_text(
            json.dumps({"rollout_store_content_sha256": "a" * 64}),
            encoding="utf-8",
        )
    monkeypatch.setattr(dataset_bundle, "_bounded_metadata_fingerprints", lambda _root: ())

    _selection, baseline = capture_dataset_bundle_generation(root, (rollout,))
    root_fields = {(field.relative_name, field.field_name): field for field in baseline.root.authoritative_fields}
    rollout_fields = {
        (field.relative_name, field.field_name): field for field in baseline.rollouts[0].authoritative_fields
    }

    assert root_fields[("manifest.json", "version")].value == 10
    assert rollout_fields[("manifest.json", "manifest_version")].value == "rollout-store-manifest-v1"
    assert rollout_fields[("manifest.json", "schema_version")].value == "0.1-draft"
    assert rollout_fields[("_owner.json", "rollout_store_content_sha256")].value == "a" * 64
    assert rollout_fields[("_SUCCESS.json", "rollout_store_content_sha256")].value == "a" * 64

    (root / "manifest.json").write_text('{"version":11}', encoding="utf-8")
    _selection, root_version_changed = capture_dataset_bundle_generation(root, (rollout,))
    assert root_version_changed.generation_digest != baseline.generation_digest

    (root / "manifest.json").write_text('{"version":10}', encoding="utf-8")
    (rollout / "_owner.json").write_text(
        json.dumps({"rollout_store_content_sha256": "b" * 64}),
        encoding="utf-8",
    )
    _selection, seal_changed = capture_dataset_bundle_generation(root, (rollout,))
    assert seal_changed.generation_digest != baseline.generation_digest


def test_dataset_bundle_generation_missing_and_invalid_authority_is_deterministic(tmp_path: Path) -> None:
    root = tmp_path / "root"
    rollout = tmp_path / "rollout.zarr"
    root.mkdir()
    rollout.mkdir()

    _selection, first = capture_dataset_bundle_generation(root, (rollout,))
    _selection, repeated = capture_dataset_bundle_generation(root, (rollout,))

    assert repeated == first
    assert {field.status for field in first.root.authoritative_fields} == {"missing_file"}
    assert {field.status for field in first.rollouts[0].authoritative_fields} == {"missing_file"}

    (root / "manifest.json").write_text("not-json", encoding="utf-8")
    (rollout / "manifest.json").write_text('{"manifest_version":7}', encoding="utf-8")
    _selection, invalid = capture_dataset_bundle_generation(root, (rollout,))

    assert invalid.root.authoritative_fields[0].status == "invalid_json"
    rollout_fields = {field.field_name: field for field in invalid.rollouts[0].authoritative_fields}
    assert rollout_fields["manifest_version"].status == "invalid_type"
    assert rollout_fields["schema_version"].status == "missing_field"
    assert invalid.generation_digest != first.generation_digest


def test_dataset_bundle_generation_unreadable_authority_is_deterministic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    manifest = root / "manifest.json"
    manifest.write_text('{"version":10}', encoding="utf-8")
    original_open = os.open

    def _unreadable(path: os.PathLike[str] | str, *args: Any, **kwargs: Any) -> int:
        if Path(path) == manifest:
            raise OSError("permission denied")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", _unreadable)

    _selection, first = capture_dataset_bundle_generation(root, ())
    _selection, repeated = capture_dataset_bundle_generation(root, ())

    assert repeated == first
    assert first.root.authoritative_fields[0].status == "unreadable"


@pytest.mark.parametrize("entry_kind", ["fifo", "directory", "device"])
def test_bounded_json_read_rejects_non_regular_entries_without_blocking(
    entry_kind: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    manifest = root / "manifest.json"
    if entry_kind == "fifo":
        os.mkfifo(manifest)
    elif entry_kind == "directory":
        manifest.mkdir()
    else:
        manifest.symlink_to(os.devnull)
    original_open = os.open

    def _checked_open(path: os.PathLike[str] | str, flags: int, *args: Any, **kwargs: Any) -> int:
        if Path(path) == manifest:
            assert flags & os.O_NONBLOCK
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", _checked_open)

    _selection, first = capture_dataset_bundle_generation(root, ())
    _selection, repeated = capture_dataset_bundle_generation(root, ())

    assert repeated == first
    assert first.root.authoritative_fields[0].status == "unreadable"


def test_metadata_symlink_target_identity_rejects_special_files_nonblocking(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = tmp_path / "metadata.fifo"
    os.mkfifo(target)
    manifest = root / "manifest.json"
    manifest.symlink_to(target)
    original_open = os.open

    def _checked_open(path: os.PathLike[str] | str, flags: int, *args: Any, **kwargs: Any) -> int:
        if Path(path) == manifest:
            assert flags & os.O_NONBLOCK
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", _checked_open)

    metadata = dataset_bundle._bounded_metadata_fingerprints(root)

    assert metadata[0][-3:] == (None, None, None)


def test_metadata_symlink_target_replacement_changes_generation_identity(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = tmp_path / "target.json"
    target.write_text('{"version": 10}', encoding="utf-8")
    (root / "manifest.json").symlink_to(target)

    _selection, first = capture_dataset_bundle_generation(root, ())
    replacement = tmp_path / "replacement.json"
    replacement.write_text('{"version": 11}', encoding="utf-8")
    replacement.replace(target)
    _selection, replaced = capture_dataset_bundle_generation(root, ())

    assert replaced.generation_digest != first.generation_digest


def test_bounded_json_read_accepts_symlink_to_regular_file(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text('{"version": 10}', encoding="utf-8")
    alias = tmp_path / "manifest.json"
    alias.symlink_to(target)

    status, payload = dataset_bundle._read_bounded_json_object(alias)

    assert status == "present"
    assert payload == {"version": 10}


def test_dataset_bundle_generation_oversized_authority_is_deterministic(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    manifest = root / "manifest.json"
    manifest.write_bytes(b"{" + b" " * dataset_bundle._MAX_SMALL_SIDECAR_JSON_BYTES + b"}")

    _selection, first = capture_dataset_bundle_generation(root, ())
    _selection, repeated = capture_dataset_bundle_generation(root, ())

    assert repeated == first
    assert first.root.authoritative_fields[0].status == "oversized"


def test_dataset_bundle_generation_detects_same_path_atomic_replacement(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    before_stat = root.stat()
    _selection, before = capture_dataset_bundle_generation(root, ())
    replacement = tmp_path / "replacement"
    replacement.mkdir()
    root.rmdir()
    os.replace(replacement, root)
    os.utime(root, ns=(before_stat.st_atime_ns, before_stat.st_mtime_ns))

    _selection, after = capture_dataset_bundle_generation(root, ())

    assert after.generation_digest != before.generation_digest
    with pytest.raises(DatasetBundleGenerationChangedError) as exc_info:
        assert_dataset_bundle_generation_current(before)
    assert exc_info.value.expected == before
    assert exc_info.value.observed == after
    message = str(exc_info.value)
    assert f"expected_identity_version={before.identity_version}" in message
    assert f"expected_generation_digest={before.generation_digest}" in message
    assert f"observed_identity_version={after.identity_version}" in message
    assert f"observed_generation_digest={after.generation_digest}" in message
    assert f"expected_selected={root.as_posix()}" in message
    assert f"expected_canonical={root.as_posix()}" in message
    assert f"observed_selected={root.as_posix()}" in message
    assert f"observed_canonical={root.as_posix()}" in message
    assert "manifest.json" not in message


def test_dataset_bundle_generation_preserves_alias_text_and_broken_status(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    alias = tmp_path / "root-alias"
    alias.symlink_to("target", target_is_directory=True)
    selection, direct = capture_dataset_bundle_generation(alias, ())
    alias.unlink()
    alias.symlink_to("./target", target_is_directory=True)
    relinked_selection, relinked = capture_dataset_bundle_generation(alias, ())

    assert selection.root_store == target.resolve()
    assert relinked_selection.root_store == selection.root_store
    assert direct.root.symlink_target == "target"
    assert relinked.root.symlink_target == "./target"
    assert relinked.generation_digest != direct.generation_digest

    alias.unlink()
    alias.symlink_to("missing-target", target_is_directory=True)
    _selection, broken = capture_dataset_bundle_generation(alias, ())
    alias.unlink()
    _selection, missing = capture_dataset_bundle_generation(alias, ())
    assert broken.root.entry_status == "broken_alias"
    assert missing.root.entry_status == "missing"
    assert broken.generation_digest != missing.generation_digest


def test_dataset_bundle_generation_alias_retarget_to_root_raises_typed_change(tmp_path: Path) -> None:
    root = tmp_path / "root"
    rollout = tmp_path / "rollout"
    root.mkdir()
    rollout.mkdir()
    root_alias = tmp_path / "root-alias"
    rollout_alias = tmp_path / "rollout-alias"
    root_alias.symlink_to(root, target_is_directory=True)
    rollout_alias.symlink_to(rollout, target_is_directory=True)
    _selection, generation = capture_dataset_bundle_generation(root_alias, (rollout_alias,))
    rollout_alias.unlink()
    rollout_alias.symlink_to(root, target_is_directory=True)

    with pytest.raises(DatasetBundleGenerationChangedError):
        assert_dataset_bundle_generation_current(generation)


def test_dataset_bundle_request_rejects_selection_generation_mismatch(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    selection, generation = capture_dataset_bundle_generation(first, ())

    with pytest.raises(ValueError, match="does not match"):
        inspect_dataset_bundle(
            DatasetBundleSummaryRequest(
                selection=replace(selection, root_store=second),
                generation=generation,
            )
        )


def test_dataset_bundle_inspection_rejects_stale_generation_before_domain_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, _source_hash = _write_root_store(tmp_path)
    selection, generation = capture_dataset_bundle_generation(root, ())
    manifest = root / "manifest.json"
    manifest.write_bytes(manifest.read_bytes() + b"\n")

    def _unexpected(_request: DatasetBundleSummaryRequest) -> Any:
        pytest.fail("bundle summary domain function ran for a stale generation")

    monkeypatch.setattr(dataset_bundle, "_build_dataset_bundle_summary_unchecked", _unexpected)

    with pytest.raises(DatasetBundleGenerationChangedError):
        inspect_dataset_bundle(DatasetBundleSummaryRequest(selection=selection, generation=generation))


def test_dataset_bundle_acquisition_rejects_mid_read_generation_change(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, _source_hash = _write_root_store(tmp_path)
    selection, generation = capture_dataset_bundle_generation(root, ())
    original = dataset_bundle._build_dataset_bundle_summary_unchecked

    def _mutating_build(request: DatasetBundleSummaryRequest) -> dataset_bundle.DatasetBundleEvidence:
        evidence = original(request)
        manifest = root / "manifest.json"
        manifest.write_bytes(manifest.read_bytes() + b"\n")
        return evidence

    monkeypatch.setattr(dataset_bundle, "_build_dataset_bundle_summary_unchecked", _mutating_build)

    with pytest.raises(DatasetBundleGenerationChangedError):
        inspect_dataset_bundle(DatasetBundleSummaryRequest(selection=selection, generation=generation))


def test_qh_readiness_requires_an_explicit_named_contract(tmp_path: Path) -> None:
    """Diagnostic defaults cannot silently become Q_H readiness evidence."""

    selection = DatasetBundleSelection(tmp_path / "missing-root", (tmp_path / "rollouts",))
    with pytest.raises(TypeError, match="contract"):
        build_qh_corpus_readiness(selection)  # type: ignore[call-arg]


_QH_CONTRACT = QhDataContract(
    schema_version=ROLLOUT_ZARR_SCHEMA_VERSION,
    target_protocol="v1_observed",
    reward_metric="target-root-gain",
    return_semantics="finite-horizon",
    td_semantics="fitted-q",
    discount_gamma=0.95,
    reason_code_version="reasons-v1",
    actor_store_version=str(OFFLINE_DATASET_VERSION),
)
_QH_READINESS_CONTRACT = QhReadinessContract("qh_cf0_v1", "evl_v1", "none", "legacy_selected_rows_v1")


def _qh_chain(*, scene: str, steps: int, width: int, offset: int) -> QhChain:
    identity = PoseTW().tensor()
    candidate_poses = torch.stack([identity] * (steps * width)).reshape(steps, width, 12)
    candidate_mask = torch.ones(steps, width, dtype=torch.bool)
    return QhChain(
        actor=QhActorTensors(
            vin_snippet=VinSnippetView(
                points_world=torch.zeros(2, 3),
                lengths=torch.tensor([2]),
                t_world_rig=PoseTW(torch.stack([identity])),
                t_world_snippet=PoseTW(torch.stack([identity])),
            ),
            root_pose_world=PoseTW(identity),
            target_pose_relative_root=PoseTW(identity),
            target_extents=torch.ones(3),
            candidate_pose_relative_root=PoseTW(candidate_poses),
            candidate_mask=candidate_mask,
            action_mask=candidate_mask,
            history_pose_relative_root=PoseTW(torch.zeros(steps, steps, 12)),
            history_mask=torch.arange(steps)[:, None] > torch.arange(steps),
            horizon_remaining=torch.arange(steps, 0, -1),
            step_mask=torch.ones(steps, dtype=torch.bool),
        ),
        supervision=QhSupervision(
            label_mask=candidate_mask,
            candidate_reward=torch.ones(steps, width),
            one_step_target_rri=torch.ones(steps, width),
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
        configured_max_horizon: int | None = None,
    ):
        self.stage = stage
        self.chains = chains
        self.contract = contract
        self.scenes = frozenset(chain.key.scene_id for chain in chains)
        self.max_horizon = (
            max((chain.num_steps for chain in chains), default=0)
            if configured_max_horizon is None
            else configured_max_horizon
        )
        self.provenance = {"stage": stage.value, "stores": ["fixture.zarr"]}
        self.actor_state_contract = QhActorStateContract("evl_v1", "none", "actor-manifest", (), "qh_cf0_v1")

    def __len__(self) -> int:
        return len(self.chains)

    def __getitem__(self, index: int) -> QhChain:
        return self.chains[index]


def _patch_qh_stages(
    monkeypatch: pytest.MonkeyPatch, stages: dict[Stage, _QhStageDataset], captured: list[QhDatasetConfig] | None = None
) -> None:
    def setup(config: QhDatasetConfig) -> _QhStageDataset:
        if captured is not None:
            captured.append(config)
        assert config.split is not None
        return stages[config.split]

    monkeypatch.setattr(QhDatasetConfig, "setup_target", setup)


def test_qh_readiness_constructs_real_datamodule_and_binds_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="qh.zarr", source_hash=source_hash)
    stages = {
        Stage.TRAIN: _QhStageDataset(Stage.TRAIN, (_qh_chain(scene="train", steps=2, width=2, offset=0),)),
        Stage.VAL: _QhStageDataset(Stage.VAL, (_qh_chain(scene="val", steps=2, width=2, offset=1),)),
        Stage.TEST: _QhStageDataset(Stage.TEST, (_qh_chain(scene="test", steps=2, width=2, offset=2),)),
    }
    captured: list[QhDatasetConfig] = []
    _patch_qh_stages(monkeypatch, stages, captured)
    readiness = build_qh_corpus_readiness(
        DatasetBundleSelection(root, (rollout,)), contract=_QH_READINESS_CONTRACT, batch_size=2, seed=17
    )
    assert readiness.verdict == "Ready"
    assert readiness.actor_contract is not None
    assert readiness.actor_contract["experiment_profile"] == "qh_cf0_v1"
    assert [config.experiment_profile for config in captured] == ["qh_cf0_v1"] * 3


def test_qh_readiness_and_preview_forward_dense_objective_profile_and_reject_incompatible_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Both public Q_H paths retain the named objective at DataModule admission."""

    from aria_nbv.lightning import qh_datamodule

    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="qh-dense-contract.zarr", source_hash=source_hash)
    stages = {
        Stage.TRAIN: _QhStageDataset(Stage.TRAIN, (_qh_chain(scene="train", steps=1, width=1, offset=0),)),
        Stage.VAL: _QhStageDataset(Stage.VAL, ()),
        Stage.TEST: _QhStageDataset(Stage.TEST, ()),
    }
    _patch_qh_stages(monkeypatch, stages)
    captured_profiles: list[str] = []
    real_data_module = qh_datamodule.QhDataModule

    def capture_data_module(**kwargs: Any) -> Any:
        captured_profiles.append(kwargs["objective_profile"])
        return real_data_module(**kwargs)

    monkeypatch.setattr(qh_datamodule, "QhDataModule", capture_data_module)
    contract = replace(_QH_READINESS_CONTRACT, objective_profile="qh_dense_valid_fitted_q_v1")
    selection = DatasetBundleSelection(root, (rollout,))

    readiness = build_qh_corpus_readiness(selection, contract=contract)

    assert readiness.verdict == "Blocked"
    assert readiness.loader_settings["objective_profile"] == "qh_dense_valid_fitted_q_v1"
    assert readiness.to_jsonable()["loader_settings"]["objective_profile"] == "qh_dense_valid_fitted_q_v1"
    assert "dense-valid Q_H objective requires" in readiness.blockers[0]
    with pytest.raises(ValueError, match="dense-valid Q_H objective requires"):
        preview_qh_batch(selection, contract=contract)
    assert captured_profiles == ["qh_dense_valid_fitted_q_v1", "qh_dense_valid_fitted_q_v1"]


def test_qh_readiness_reports_realized_maximum_for_early_terminated_chains(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Readiness must report observed chain lengths, not configured horizon."""

    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="qh.zarr", source_hash=source_hash)
    stages = {
        Stage.TRAIN: _QhStageDataset(
            Stage.TRAIN,
            (
                _qh_chain(scene="train-a", steps=2, width=1, offset=0),
                _qh_chain(scene="train-b", steps=3, width=1, offset=1),
            ),
            configured_max_horizon=8,
        ),
        Stage.VAL: _QhStageDataset(Stage.VAL, ()),
        Stage.TEST: _QhStageDataset(Stage.TEST, ()),
    }
    _patch_qh_stages(monkeypatch, stages)

    readiness = build_qh_corpus_readiness(DatasetBundleSelection(root, (rollout,)), contract=_QH_READINESS_CONTRACT)

    assert readiness.verdict == "Ready"
    assert readiness.stages[0].max_horizon == 3


def test_qh_readiness_json_export_plainifies_cfplus_geometry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """CF+ geometry dataclasses must not leak into download JSON."""

    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="qh.zarr", source_hash=source_hash)
    geometry = QhGeometryContract(
        projection_model="pinhole",
        linearization="z",
        camera_pose="camera_from_root",
        depth_semantics="metric_z",
        focal_px=(120.0, 120.0),
        principal_point_px=(120.0, 120.0),
        image_size_hw=(240, 240),
        camera_axes="x-right,y-down,z-forward",
        camera_forward="+z",
        camera_handedness="right",
        pixel_convention="pixel-center",
        in_ndc=False,
        znear_m=0.1,
        zfar_m=20.0,
        invalid_fill_value=0.0,
        dtype="float16",
        renderer="pytorch3d",
        source_role="selected_action",
        selected_identity="selected_depth.step_row_id",
    )
    contract = replace(_QH_CONTRACT, selected_depth_geometry=geometry)
    stages = {
        stage: _QhStageDataset(
            stage,
            (_qh_chain(scene=stage.value, steps=1, width=1, offset=index),),
            contract=contract,
        )
        for index, stage in enumerate((Stage.TRAIN, Stage.VAL, Stage.TEST))
    }
    _patch_qh_stages(monkeypatch, stages)

    readiness = build_qh_corpus_readiness(DatasetBundleSelection(root, (rollout,)), contract=_QH_READINESS_CONTRACT)

    payload = readiness.to_jsonable()
    json.dumps(payload, sort_keys=True)
    assert payload["contract"]["selected_depth_geometry"]["image_size_hw"] == [240, 240]


def test_qh_batch_preview_is_seeded_and_reports_real_padding(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="qh.zarr", source_hash=source_hash)
    stages = {
        Stage.TRAIN: _QhStageDataset(
            Stage.TRAIN,
            (
                _qh_chain(scene="train", steps=1, width=2, offset=0),
                _qh_chain(scene="train", steps=2, width=1, offset=1),
            ),
        ),
        Stage.VAL: _QhStageDataset(Stage.VAL, (_qh_chain(scene="val", steps=2, width=1, offset=2),)),
        Stage.TEST: _QhStageDataset(Stage.TEST, (_qh_chain(scene="test", steps=2, width=1, offset=3),)),
    }
    _patch_qh_stages(monkeypatch, stages)
    selection = DatasetBundleSelection(root, (rollout,))
    first = preview_qh_batch(
        selection, contract=_QH_READINESS_CONTRACT, stage=Stage.TRAIN, chain_index=1, batch_size=2, seed=11
    )
    second = preview_qh_batch(
        selection, contract=_QH_READINESS_CONTRACT, stage="train", chain_index=1, batch_size=2, seed=11
    )
    assert first == second
    assert first.selected_chain_steps == 2
    assert first.step_padding_count == 1
    assert first.candidate_padding_count == 4


def test_qh_readiness_fails_closed_for_empty_train_overlap_and_contract_mismatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="qh.zarr", source_hash=source_hash)
    selection = DatasetBundleSelection(root, (rollout,))
    empty = {
        Stage.TRAIN: _QhStageDataset(Stage.TRAIN, ()),
        Stage.VAL: _QhStageDataset(Stage.VAL, (_qh_chain(scene="val", steps=1, width=1, offset=0),)),
        Stage.TEST: _QhStageDataset(Stage.TEST, ()),
    }
    _patch_qh_stages(monkeypatch, empty)
    assert "training stage" in build_qh_corpus_readiness(selection, contract=_QH_READINESS_CONTRACT).blockers[0]
    overlap = {
        Stage.TRAIN: _QhStageDataset(Stage.TRAIN, (_qh_chain(scene="shared", steps=1, width=1, offset=0),)),
        Stage.VAL: _QhStageDataset(Stage.VAL, (_qh_chain(scene="shared", steps=1, width=1, offset=1),)),
        Stage.TEST: _QhStageDataset(Stage.TEST, ()),
    }
    _patch_qh_stages(monkeypatch, overlap)
    assert "overlap scenes" in build_qh_corpus_readiness(selection, contract=_QH_READINESS_CONTRACT).blockers[0]
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
    assert (
        "incompatible learning semantics"
        in build_qh_corpus_readiness(selection, contract=_QH_READINESS_CONTRACT).blockers[0]
    )


def test_qh_readiness_rejects_bundle_binding_before_dataset_construction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root, _source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="tampered.zarr", source_hash="wrong-root")
    called = False

    def unexpected(_config: QhDatasetConfig) -> None:
        nonlocal called
        called = True
        raise AssertionError("dataset construction must not run")

    monkeypatch.setattr(QhDatasetConfig, "setup_target", unexpected)
    readiness = build_qh_corpus_readiness(DatasetBundleSelection(root, (rollout,)), contract=_QH_READINESS_CONTRACT)
    assert readiness.verdict == "Blocked"
    assert not called
    assert any("manifest hash" in blocker for blocker in readiness.blockers)


def test_qh_readiness_rejects_incomplete_promotion_evidence_before_dataset_construction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A promotion marker without its paired typed evidence is never admitted."""

    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="tampered-promoted.zarr", source_hash=source_hash)
    (rollout / "_SUCCESS.json").write_text("{}", encoding="utf-8")
    called = False

    def unexpected(_config: QhDatasetConfig) -> None:
        nonlocal called
        called = True
        raise AssertionError("dataset construction must not run")

    monkeypatch.setattr(QhDatasetConfig, "setup_target", unexpected)
    readiness = build_qh_corpus_readiness(DatasetBundleSelection(root, (rollout,)), contract=_QH_READINESS_CONTRACT)

    assert readiness.verdict == "Blocked"
    assert not called
    assert any("trust" in blocker or "promotion" in blocker for blocker in readiness.blockers)


def test_qh_preview_rejects_incomplete_promotion_evidence_before_dataset_construction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The direct preview API shares readiness's fail-closed promotion gate."""

    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="tampered-preview.zarr", source_hash=source_hash)
    (rollout / "_SUCCESS.json").write_text("{}", encoding="utf-8")
    called = False

    def unexpected(_config: QhDatasetConfig) -> None:
        nonlocal called
        called = True
        raise AssertionError("dataset construction must not run")

    monkeypatch.setattr(QhDatasetConfig, "setup_target", unexpected)
    with pytest.raises(ValueError, match="trust|promotion"):
        preview_qh_batch(DatasetBundleSelection(root, (rollout,)), contract=_QH_READINESS_CONTRACT)

    assert not called


def test_qh_readiness_rejects_two_broken_promotion_marker_aliases_before_dataset_construction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Broken marker aliases cannot masquerade as an unpromoted V0 store."""

    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="broken-marker.zarr", source_hash=source_hash)
    for marker in ("_SUCCESS.json", "_owner.json"):
        (rollout / marker).symlink_to(tmp_path / f"missing-{marker}")
    monkeypatch.setattr(
        dataset_bundle, "_build_qh_data_module", lambda *_args, **_kwargs: pytest.fail("unexpected construction")
    )

    readiness = build_qh_corpus_readiness(DatasetBundleSelection(root, (rollout,)), contract=_QH_READINESS_CONTRACT)

    assert readiness.verdict == "Blocked"


def test_qh_preview_rejects_two_broken_promotion_marker_aliases_before_dataset_construction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Preview applies the same marker gate before Q_H construction."""

    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="broken-preview-marker.zarr", source_hash=source_hash)
    for marker in ("_SUCCESS.json", "_owner.json"):
        (rollout / marker).symlink_to(tmp_path / f"missing-{marker}")
    monkeypatch.setattr(
        dataset_bundle, "_build_qh_data_module", lambda *_args, **_kwargs: pytest.fail("unexpected construction")
    )

    with pytest.raises(ValueError, match="promotion"):
        preview_qh_batch(DatasetBundleSelection(root, (rollout,)), contract=_QH_READINESS_CONTRACT)


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


@pytest.mark.parametrize("fifo_entry", ["vin_manifest", "vin_sample_index", "rollout_manifest"])
def test_public_bundle_summary_reports_fifo_metadata_as_blocked_visible_evidence(
    fifo_entry: str, tmp_path: Path
) -> None:
    """Public bundle inspection must reject FIFO metadata without blocking."""

    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="fifo.zarr", source_hash=source_hash)
    if fifo_entry == "vin_manifest":
        fifo_path = root / "manifest.json"
        expected_code = "root_store_unreadable"
    elif fifo_entry == "vin_sample_index":
        fifo_path = root / "sample_index.jsonl"
        expected_code = "root_store_unreadable"
    else:
        fifo_path = rollout / "manifest.json"
        expected_code = "rollout_store_unreadable"
    fifo_path.unlink()
    os.mkfifo(fifo_path)

    previous_handler = signal.getsignal(signal.SIGALRM)

    def _deadline(_signum: int, _frame: object) -> None:
        raise TimeoutError("FIFO public summary exceeded its two-second deadline")

    signal.signal(signal.SIGALRM, _deadline)
    signal.setitimer(signal.ITIMER_REAL, 2)
    try:
        evidence = build_dataset_bundle_summary(DatasetBundleSelection(root, (rollout,)))
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)

    assert evidence.verdict == "Blocked"
    assert any(finding.code == expected_code for finding in evidence.findings)
    if fifo_entry == "rollout_manifest":
        assert evidence.rollouts[0]["included_in_training_totals"] is False
        assert evidence.rollouts[0]["path"] == rollout.as_posix()


def test_lightweight_summary_accepts_large_regular_production_payloads(tmp_path: Path) -> None:
    """Production payloads scale past the retired 16 MiB summary cap."""

    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="large-summary.zarr", source_hash=source_hash)
    padding = b"\n" * (16 * dataset_bundle._MAX_SMALL_SIDECAR_JSON_BYTES + 1)
    root_manifest_path = root / "manifest.json"
    root_manifest_path.write_bytes(root_manifest_path.read_bytes() + padding)
    index_path = root / "sample_index.jsonl"
    index_path.write_bytes(index_path.read_bytes() + padding)
    split_path = root / "splits" / "train.npy"
    split_path.write_bytes(split_path.read_bytes() + b"\0" * len(padding))
    manifest_path = rollout / "manifest.json"
    manifest_path.write_bytes(manifest_path.read_bytes() + padding)

    evidence = build_dataset_bundle_summary(DatasetBundleSelection(root, (rollout,)))

    assert evidence.root["sample_count"] == 2
    assert evidence.root["split_counts"].to_jsonable() == {"train": 1, "val": 1}
    assert evidence.rollouts[0]["included_in_training_totals"] is True
    assert evidence.aggregate["rollout_count"] == 3


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


def test_dataset_bundle_evidence_is_deeply_immutable_with_export_parity(tmp_path: Path) -> None:
    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="frozen.zarr", source_hash=source_hash)

    evidence = build_dataset_bundle_summary(DatasetBundleSelection(root, (rollout,)))
    exported = evidence.to_jsonable()

    assert isinstance(evidence.root, FrozenJsonObject)
    assert isinstance(evidence.root["split_counts"], FrozenJsonObject)
    assert isinstance(evidence.rollouts[0]["counts"], FrozenJsonObject)
    assert isinstance(evidence.topology["nodes"], FrozenJsonArray)
    with pytest.raises(TypeError):
        evidence.root["sample_count"] = 99  # type: ignore[index]
    with pytest.raises(TypeError):
        evidence.root["split_counts"]["train"] = 99  # type: ignore[index]
    exported["root"]["sample_count"] = 99
    assert evidence.to_jsonable()["root"]["sample_count"] == 2
    assert json.loads(json.dumps(evidence.to_jsonable(), sort_keys=True)) == evidence.to_jsonable()
    assert evidence.to_jsonable()["generation"]["generation_digest"] == evidence.generation.generation_digest


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


def test_invalid_promoted_store_remains_visible_but_is_excluded(tmp_path: Path) -> None:
    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="invalid-promotion.zarr", source_hash=source_hash)
    (rollout / "_SUCCESS.json").symlink_to(tmp_path / "missing-success.json")

    evidence = build_dataset_bundle_summary(DatasetBundleSelection(root, (rollout,)))

    assert len(evidence.rollouts) == 1
    assert evidence.rollouts[0]["included_in_training_totals"] is False
    assert evidence.aggregate["compatible_rollout_store_count"] == 0
    assert any(finding.code == "rollout_promotion_invalid" for finding in evidence.findings)


def test_malformed_promotion_marker_pair_is_visible_but_excluded(tmp_path: Path) -> None:
    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="malformed-promotion.zarr", source_hash=source_hash)
    for name in ("_SUCCESS.json", "_owner.json"):
        (rollout / name).write_text("{}", encoding="utf-8")

    evidence = build_dataset_bundle_summary(DatasetBundleSelection(root, (rollout,)))

    assert evidence.rollouts[0]["included_in_training_totals"] is False
    assert evidence.aggregate["compatible_rollout_store_count"] == 0
    assert any(finding.code == "rollout_promotion_invalid" for finding in evidence.findings)


@pytest.mark.parametrize("present_marker", [None, "_SUCCESS.json", "_owner.json"])
def test_typed_shard_advertisement_requires_both_promotion_markers(
    present_marker: str | None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Typed shard ownership is promotion advertisement even without a sidecar."""

    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="advertised.zarr", source_hash=source_hash)
    manifest_path = rollout / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["generation"]["shard"] = {"shard_id": "advertised"}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    if present_marker is not None:
        (rollout / present_marker).write_text("{}", encoding="utf-8")

    evidence = build_dataset_bundle_summary(DatasetBundleSelection(root, (rollout,)))

    assert evidence.rollouts[0]["included_in_training_totals"] is False
    assert any(finding.code == "rollout_promotion_invalid" for finding in evidence.findings)
    monkeypatch.setattr(
        dataset_bundle,
        "_build_qh_data_module",
        lambda *_args, **_kwargs: pytest.fail("promotion rejection must precede Q_H construction"),
    )
    readiness = build_qh_corpus_readiness(DatasetBundleSelection(root, (rollout,)), contract=_QH_READINESS_CONTRACT)
    assert readiness.verdict == "Blocked"
    assert any("promotion" in blocker.lower() for blocker in readiness.blockers)


def test_oversized_promotion_marker_is_bounded_visible_and_excluded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="oversized-promotion.zarr", source_hash=source_hash)
    (rollout / "_SUCCESS.json").write_bytes(b"{" + b" " * dataset_bundle._MAX_SMALL_SIDECAR_JSON_BYTES + b"}")
    (rollout / "_owner.json").write_text("{}", encoding="utf-8")
    original_read_text = Path.read_text

    def bounded_only(path: Path, *args: Any, **kwargs: Any) -> str:
        if path.name in {"_SUCCESS.json", "_owner.json"}:
            pytest.fail("promotion markers must not use unbounded read_text")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", bounded_only)

    evidence = build_dataset_bundle_summary(DatasetBundleSelection(root, (rollout,)))

    assert evidence.rollouts[0]["included_in_training_totals"] is False
    assert evidence.aggregate["compatible_rollout_store_count"] == 0
    finding = next(finding for finding in evidence.findings if finding.code == "rollout_promotion_invalid")
    assert "_SUCCESS.json is oversized" in finding.message


def test_public_bundle_summary_rejects_fifo_promotion_marker_without_blocking(tmp_path: Path) -> None:
    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="fifo-marker.zarr", source_hash=source_hash)
    marker = rollout / "_SUCCESS.json"
    os.mkfifo(marker)
    previous_handler = signal.getsignal(signal.SIGALRM)

    def _deadline(_signum: int, _frame: object) -> None:
        raise TimeoutError("FIFO promotion marker summary exceeded its two-second deadline")

    signal.signal(signal.SIGALRM, _deadline)
    signal.setitimer(signal.ITIMER_REAL, 2)
    try:
        evidence = build_dataset_bundle_summary(DatasetBundleSelection(root, (rollout,)))
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)

    assert evidence.rollouts[0]["included_in_training_totals"] is False
    assert evidence.aggregate["compatible_rollout_store_count"] == 0
    assert any(finding.code == "rollout_promotion_invalid" for finding in evidence.findings)


def test_typed_promotion_marker_pair_remains_eligible_without_deep_validation(tmp_path: Path) -> None:
    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="promoted.zarr", source_hash=source_hash)
    manifest_path = rollout / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    row = RolloutShardRow(0, 0, "sample-0", "scene-0", "snippet-0", "train", "source-0", 0)
    shard_entry = RolloutShardEntry(
        shard_id="shard-000000",
        split="train",
        rows=(row,),
        writer_config_hash="c" * 64,
        source_manifest_hash=source_hash,
        source_cache_version=str(OFFLINE_DATASET_VERSION),
        split_manifest_hash=build_rollout_split_manifest_hash(
            source_manifest_hash=source_hash,
            split="train",
            records=[row.hash_record()],
        ),
        source_store_dir="root",
        generation_revision_hash="d" * 64,
    )
    shard_entry.validate()
    shard = shard_entry.to_jsonable()
    manifest["generation"]["shard"] = shard
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    manifest_hash = manifest_sha256(manifest)
    owner = {
        "sidecar_kind": "rollout_shard_owner",
        "shard_id": shard_entry.shard_id,
        "writer_config_hash": shard_entry.writer_config_hash,
        "source_manifest_hash": shard_entry.source_manifest_hash,
        "split_manifest_hash": shard_entry.split_manifest_hash,
        "generation_revision_hash": shard_entry.generation_revision_hash,
        "source_cache_version": shard_entry.source_cache_version,
        "split": shard_entry.split,
        "num_source_rows": len(shard_entry.rows),
        "campaign_binding": None,
        "rollout_manifest_sha256": manifest_hash,
        "rollout_store_content_sha256": "a" * 64,
    }
    success = {
        "sidecar_kind": "rollout_shard_success",
        **{key: owner[key] for key in owner if key not in {"sidecar_kind"}},
        "owner_sha256": manifest_sha256(owner),
    }
    (rollout / "_owner.json").write_text(json.dumps(owner), encoding="utf-8")
    (rollout / "_SUCCESS.json").write_text(json.dumps(success), encoding="utf-8")

    evidence = build_dataset_bundle_summary(DatasetBundleSelection(root, (rollout,)))

    assert evidence.rollouts[0]["included_in_training_totals"] is True, [
        finding.to_jsonable() for finding in evidence.findings
    ]
    assert not any(finding.code == "rollout_promotion_invalid" for finding in evidence.findings)

    manifest["generation"]["shard"]["shard_id"] = None
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    owner["shard_id"] = None
    owner["rollout_manifest_sha256"] = manifest_sha256(manifest)
    success.update({key: owner[key] for key in owner if key != "sidecar_kind"})
    success["owner_sha256"] = manifest_sha256(owner)
    (rollout / "_owner.json").write_text(json.dumps(owner), encoding="utf-8")
    (rollout / "_SUCCESS.json").write_text(json.dumps(success), encoding="utf-8")

    malformed = build_dataset_bundle_summary(DatasetBundleSelection(root, (rollout,)))

    assert malformed.rollouts[0]["included_in_training_totals"] is False
    assert any(finding.code == "rollout_promotion_invalid" for finding in malformed.findings)


def test_blocked_root_excludes_every_rollout_from_training_totals_and_topology(tmp_path: Path) -> None:
    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="compatible.zarr", source_hash=source_hash)
    (root / "splits" / "train.npy").write_bytes(b"not-a-valid-npy")

    evidence = build_dataset_bundle_summary(DatasetBundleSelection(root, (rollout,)))

    assert evidence.verdict == "Blocked"
    assert evidence.rollouts[0]["included_in_training_totals"] is False
    assert evidence.aggregate["compatible_rollout_store_count"] == 0
    assert evidence.aggregate["rollout_count"] == 0
    assert evidence.topology.to_jsonable()["edges"][0]["resolution"] == "blocked"
    assert any(finding.code == "root_split_unreadable" for finding in evidence.findings)


def test_required_validation_controls_ready_verdict(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
    assert tuple(row.to_jsonable() for row in evidence.coral_artifacts) == (
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


def test_deep_statistics_reports_trainable_coverage_without_mutating_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="deep.zarr", source_hash=source_hash)

    class _Reader:
        def __init__(self, _path: Path) -> None:
            pass

        def array(self, path: str) -> np.ndarray:
            arrays: dict[str, np.ndarray] = {
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


def test_deep_statistics_excludes_promoted_content_trust_failure_before_array_access(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, name="content-mismatch.zarr", source_hash=source_hash)
    manifest_path = rollout / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    row = RolloutShardRow(0, 0, "sample-0", "scene-0", "snippet-0", "train", "source-0", 0)
    entry = RolloutShardEntry(
        shard_id="shard-000000",
        split="train",
        rows=(row,),
        writer_config_hash="c" * 64,
        source_manifest_hash=source_hash,
        source_cache_version=str(OFFLINE_DATASET_VERSION),
        split_manifest_hash=build_rollout_split_manifest_hash(
            source_manifest_hash=source_hash, split="train", records=[row.hash_record()]
        ),
        source_store_dir="root",
        generation_revision_hash="d" * 64,
    )
    manifest["generation"]["shard"] = entry.to_jsonable()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    owner = {
        "sidecar_kind": "rollout_shard_owner",
        "shard_id": entry.shard_id,
        "writer_config_hash": entry.writer_config_hash,
        "source_manifest_hash": entry.source_manifest_hash,
        "split_manifest_hash": entry.split_manifest_hash,
        "generation_revision_hash": entry.generation_revision_hash,
        "source_cache_version": entry.source_cache_version,
        "split": entry.split,
        "num_source_rows": len(entry.rows),
        "campaign_binding": None,
        "rollout_manifest_sha256": manifest_sha256(manifest),
        "rollout_store_content_sha256": "a" * 64,
    }
    success = {
        "sidecar_kind": "rollout_shard_success",
        **{key: value for key, value in owner.items() if key != "sidecar_kind"},
        "owner_sha256": manifest_sha256(owner),
    }
    (rollout / "_owner.json").write_text(json.dumps(owner), encoding="utf-8")
    (rollout / "_SUCCESS.json").write_text(json.dumps(success), encoding="utf-8")
    original_array = dataset_bundle.RolloutZarrStoreReader.array

    def _unexpected_array(self: Any, path: str) -> Any:
        pytest.fail(f"content-untrusted promoted store opened candidate array {path}")

    monkeypatch.setattr(
        dataset_bundle,
        "_rollout_promotion_blocker",
        lambda path: (
            "Promoted rollout content-mismatch.zarr is not trusted: canonical store content mismatch."
            if path == rollout
            else None
        ),
    )
    monkeypatch.setattr(dataset_bundle.RolloutZarrStoreReader, "array", _unexpected_array)
    deep = compute_dataset_bundle_deep_statistics(DatasetBundleSelection(root, (rollout,)))
    monkeypatch.setattr(dataset_bundle.RolloutZarrStoreReader, "array", original_array)

    assert deep["stores"][0]["path"] == rollout.as_posix()
    assert deep["stores"][0]["included"] is False
    assert "canonical store content mismatch" in str(deep["stores"][0]["reason"])
    assert deep["aggregate"]["eligible_rollout_store_count"] == 0
    assert deep["aggregate"]["scanned_rollout_store_count"] == 0


def test_root_gt_obb_scan_counts_only_finite_non_padding_rows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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

    valid: np.ndarray = np.zeros((34,), dtype=np.float32)
    valid[:6] = [0, 2, 0, 1, 0, 3]
    valid[18:30] = [1, 0, 0, 0, 1, 0, 0, 0, 1, 10, 20, 30]
    padded: np.ndarray = np.full((34,), -1.0, dtype=np.float32)
    nonfinite = valid.copy()
    nonfinite[0] = np.nan
    finite_nonpositive_geometry = valid.copy()
    finite_nonpositive_geometry[1] = 0.0

    class _Reader:
        def __init__(self, _config: Any) -> None:
            pass

        def read_numeric_block(self, record: VinOfflineIndexRecord, _name: str) -> np.ndarray:
            return cast(
                np.ndarray,
                np.stack(
                    [
                        valid if record.sample_index == 0 else finite_nonpositive_geometry,
                        padded if record.sample_index == 0 else nonfinite,
                    ]
                ),
            )

        def read_optional_record(self, _record: VinOfflineIndexRecord, _name: str) -> Any | None:
            return None

    monkeypatch.setattr("aria_nbv.dataset_bundle.VinOfflineStoreReader", _Reader)
    scan = scan_root_gt_obb_target_opportunities(root)

    assert scan["available"] is True
    assert scan["target_opportunity_count"] == 2
    assert scan["scene_counts"] == {"scene-a": 1, "scene-b": 1}
    assert scan["split_counts"] == {"train": 1, "val": 1}
    assert scan["semantic_role"] == "gt_obb_label_evaluation_target_opportunities"
    assert scan["per_sample"][1]["gt_obb_target_opportunities"] == 1


def test_root_gt_obb_scan_does_not_mask_unexpected_reader_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root, _source_hash = _write_root_store(tmp_path)
    manifest = VinOfflineManifest.read(root / "manifest.json")
    block = VinOfflineBlockSpec.for_zarr_array(
        name="gt.obbs",
        array_path="gt/obbs",
        dtype="float32",
        shape=[1, 1, 34],
    )
    manifest.shards = [
        VinOfflineShardSpec("shard-a", "shards/shard-a", 0, 1, {"gt.obbs": block}),
        VinOfflineShardSpec("shard-b", "shards/shard-b", 1, 1, {"gt.obbs": block}),
    ]
    manifest.write(root / "manifest.json")

    class _BrokenReader:
        def __init__(self, _config: Any) -> None:
            pass

        def read_numeric_block(self, _record: VinOfflineIndexRecord, _name: str) -> np.ndarray:
            raise RuntimeError("unexpected implementation failure")

    monkeypatch.setattr("aria_nbv.dataset_bundle.VinOfflineStoreReader", _BrokenReader)

    with pytest.raises(RuntimeError, match="unexpected implementation failure"):
        scan_root_gt_obb_target_opportunities(root)


def test_root_gt_obb_scan_does_not_fall_back_when_blocks_are_absent(tmp_path: Path) -> None:
    root, _source_hash = _write_root_store(tmp_path)

    scan = scan_root_gt_obb_target_opportunities(root)

    assert scan["available"] is False
    assert scan["target_opportunity_count"] is None
    assert scan["reason"] == "gt_obb_block_missing:shard-a,shard-b"
