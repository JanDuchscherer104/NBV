"""Tests for rollout dataset writer lineage helpers."""

# ruff: noqa: S101

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import msgspec
import pytest
import torch
import zarr

import aria_nbv.oracle.pipelines.shards as shards_module
from aria_nbv.oracle.evidence import OracleEvidenceInvalidReason
from aria_nbv.oracle.pipelines.evaluated_rollout import OracleReplayInvalidityError
from aria_nbv.oracle.pipelines.rollout_dataset import (
    ExplicitRolloutTargetConfig,
    InsufficientRootSupportError,
    RolloutDatasetWriter,
    RolloutDatasetWriterConfig,
    RolloutDatasetWriterStats,
    SelectedDepthRetentionConfig,
    _explicit_target_result,
    _RolloutSourceLineageBuilder,
    _select_source_manifest_rows,
)
from aria_nbv.oracle.pipelines.shards import (
    plan_rollout_shards,
    plan_rollout_source_manifest,
    read_validated_completed_shard,
    run_rollout_shard,
    summarize_rollout_shard_campaign,
)
from aria_nbv.oracle.target_rri import TargetRriInvalidity
from aria_nbv.oracle.target_selection import (
    OracleTargetTask,
    TargetTaskIdentityStatus,
)
from aria_nbv.pose_generation import CandidateMixtureViewGeneratorConfig
from aria_nbv.rendering import CandidateDepthRendererConfig
from aria_nbv.rollouts.manifest import RolloutStoreManifestContext, manifest_sha256
from aria_nbv.rollouts.replay.engine import CounterfactualPoseGeneratorConfig
from aria_nbv.rollouts.replay.policy import RolloutPolicySpec, derive_selection_seed
from aria_nbv.rollouts.shard_manifest import (
    RolloutShardCampaignBinding,
    RolloutShardEntry,
    RolloutShardRow,
    RolloutSourceManifest,
    build_rollout_split_manifest_hash,
    canonical_rollout_shard_id,
    read_rollout_source_manifest,
    write_rollout_shard_manifest,
    write_rollout_source_manifest,
)
from aria_nbv.rollouts.zarr_store import RolloutZarrStoreReader, validate_rollout_zarr_store, write_rollout_zarr_store
from aria_nbv.targets import ObservedTargetDescriptor, TargetDescriptor
from aria_nbv.targets.protocol import TargetInputProtocol
from aria_nbv.utils.fingerprints import stable_config_hash, stable_msgspec_hash
from tests.rollout_fixtures import build_rollout_records


class _FakeManifest(msgspec.Struct):
    version: int = 7


def _target_descriptor() -> TargetDescriptor:
    return TargetDescriptor(
        sem_id=1,
        class_name="chair",
        pose_world_object=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
        extents_m=(1.0, 1.0, 1.0),
        relative_pose_reference_object=(
            1.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
        ),
    )


class _FakeSelectedDepthRenderer:
    def __init__(self, *, height: int, width: int) -> None:
        self.height = height
        self.width = width
        self.calls: list[tuple[object, list[int]]] = []

    def render_compact_indices(self, sample: object, candidates: object, compact_indices: list[int]):
        del sample
        self.calls.append((candidates, list(compact_indices)))
        shell_indices = candidates.candidate_shell_indices(device=torch.device("cpu"))
        selected_shell_index = shell_indices[int(compact_indices[0])]
        camera = SimpleNamespace(
            f=torch.tensor([[10.0, 11.0]], dtype=torch.float32),
            c=torch.tensor([[2.0, 3.0]], dtype=torch.float32),
            size=torch.tensor([[float(self.width), float(self.height)]], dtype=torch.float32),
        )
        return SimpleNamespace(
            depths=torch.ones((1, self.height, self.width), dtype=torch.float32),
            depths_valid_mask=torch.ones((1, self.height, self.width), dtype=torch.bool),
            candidate_indices=selected_shell_index.reshape(1),
            camera=camera,
        )


class _FakeSource:
    def __init__(self, dataset: _FakeDataset, *, store_dir: Path) -> None:
        self._dataset = dataset
        self.store = SimpleNamespace(store_dir=store_dir)

    def setup_target(self) -> "_FakeDataset":
        return self._dataset


class _FakeDataset:
    def __init__(self, records: list[Any], *, config_split: str = "train") -> None:
        self.manifest = _FakeManifest()
        self.config = SimpleNamespace(split=config_split)
        self._records = records
        self._record_by_pair = {(record.scene_id, record.snippet_id): record for record in records}

    def __len__(self) -> int:
        return len(self._records)


class _FakeRolloutConfig:
    def __init__(self, records: list[Any], *, store_dir: Path, source_split: str = "train") -> None:
        self.source = _FakeSource(_FakeDataset(records, config_split=source_split), store_dir=store_dir / "vin_offline")
        self.store = SimpleNamespace(store_dir=store_dir / "configured-rollouts.zarr")
        self.source_manifest_path: Path | None = None
        self.sample_keys: list[str] | None = None
        self._dump_token = "fake-rollout-config-v1"

    def model_dump_jsonable(self) -> dict[str, Any]:
        return {"dump_token": self._dump_token, "source_store": self.source.store.store_dir.as_posix()}

    def model_copy(self, *, deep: bool = False) -> "_FakeRolloutConfig":
        return deepcopy(self) if deep else self

    def setup_target(self) -> "_FakeShardWriter":
        return _FakeShardWriter(self)

    def selected_source_manifest_rows(self, manifest: RolloutSourceManifest) -> tuple[RolloutShardRow, ...]:
        return _select_source_manifest_rows(manifest, self.sample_keys)


class _FakeShardWriter:
    def __init__(self, config: _FakeRolloutConfig) -> None:
        self.config = config

    def run(self, *, invocation: object | None = None, shard_entry: RolloutShardEntry | None = None):
        del invocation
        if shard_entry is None:
            raise AssertionError("Shard writer tests must pass a shard entry.")
        records = build_rollout_records(horizon=1, num_samples=6, seed=33)[:1]
        records[0].lineage.source.source_offline_store_manifest_hash = shard_entry.source_manifest_hash
        records[0].lineage.source.source_cache_version = shard_entry.source_cache_version
        records[0].lineage.source.split_manifest_hash = shard_entry.split_manifest_hash
        return write_rollout_zarr_store(
            self.config.store.store_dir,
            records,
            source_offline_store_version=shard_entry.source_cache_version,
            split_manifest_hash=shard_entry.split_manifest_hash,
            manifest_context=RolloutStoreManifestContext(shard=shard_entry.to_jsonable()),
        )


def test_split_manifest_hash_tracks_source_rows_and_order() -> None:
    rows = [
        {
            "order": 0,
            "sample_index": 1,
            "sample_key": "a",
            "scene_id": "scene-a",
            "snippet_id": "snippet-a",
            "split": "train",
            "source_shard_id": "shard-0",
            "source_shard_row": 0,
        },
        {
            "order": 1,
            "sample_index": 2,
            "sample_key": "b",
            "scene_id": "scene-b",
            "snippet_id": "snippet-b",
            "split": "train",
            "source_shard_id": "shard-0",
            "source_shard_row": 1,
        },
    ]

    base = _RolloutSourceLineageBuilder.build_split_manifest_hash(
        source_manifest_hash="source", split="train", records=rows
    )
    reordered = _RolloutSourceLineageBuilder.build_split_manifest_hash(
        source_manifest_hash="source", split="train", records=list(reversed(rows))
    )
    changed_source = _RolloutSourceLineageBuilder.build_split_manifest_hash(
        source_manifest_hash="other", split="train", records=rows
    )

    assert base != reordered
    assert base != changed_source


def test_direct_v0_writer_keeps_physical_split_out_of_campaign_hash(tmp_path: Path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=51)[:1]
    source = records[0].lineage.source
    dataset_record = SimpleNamespace(
        sample_index=source.source_sample_index,
        sample_key=source.source_sample_key,
        scene_id=source.scene_id,
        snippet_id=source.snippet_id,
        split=source.split,
        shard_id=source.source_shard_id,
        row=source.source_shard_row,
    )
    dataset = _FakeDataset([dataset_record])
    lineage = _RolloutSourceLineageBuilder.from_dataset(dataset, max_samples=1, campaign_split=None)
    assert lineage.campaign_split is None
    source.campaign_split = None
    source.source_offline_store_manifest_hash = lineage.source_manifest_hash
    source.source_cache_version = lineage.source_cache_version
    source.split_manifest_hash = lineage.split_manifest_hash
    result = write_rollout_zarr_store(
        tmp_path / "direct-v0.zarr",
        records,
        source_offline_store_version=lineage.source_cache_version,
        split_manifest_hash=lineage.split_manifest_hash,
    )
    validation = validate_rollout_zarr_store(result.store_dir)
    assert validation.ok, validation.errors


@pytest.mark.parametrize("record_index", [0, 1])
def test_zarr_round_trip_persists_state_keyed_selection_seed(tmp_path: Path, record_index: int) -> None:
    record = build_rollout_records(horizon=2, num_samples=6, seed=51)[record_index]
    result = write_rollout_zarr_store(tmp_path / "selection-seed.zarr", [record])

    persisted = RolloutZarrStoreReader(result.store_dir).array("steps/selection_seed")
    trajectory = record.evaluated.result.trajectories[0]
    state_path: tuple[int, ...] = ()
    expected: list[int] = []
    for step in trajectory.steps:
        expected.append(derive_selection_seed(51, state_path))
        state_path += (step.selected_shell_index,)

    assert persisted.tolist() == expected


def test_campaign_split_is_serialized_and_bound_into_v3_source_hash() -> None:
    row = RolloutShardRow(
        order=0,
        sample_index=1,
        sample_key="sample",
        scene_id="scene",
        snippet_id="snippet",
        split="train",
        source_shard_id="shard-0",
        source_shard_row=0,
    )
    campaign_row = replace(row, campaign_split="pilot")
    assert row.hash_record() != campaign_row.hash_record()
    assert row.to_jsonable() != campaign_row.to_jsonable()
    assert _RolloutSourceLineageBuilder.build_split_manifest_hash(
        source_manifest_hash="source", split="train", records=[row.hash_record()]
    ) != _RolloutSourceLineageBuilder.build_split_manifest_hash(
        source_manifest_hash="source", split="train", records=[campaign_row.hash_record()]
    )


def test_v3_campaign_split_tampering_is_rejected_by_entry_hash() -> None:
    row = RolloutShardRow(
        order=0,
        sample_index=1,
        sample_key="sample",
        scene_id="scene",
        snippet_id="snippet",
        split="train",
        source_shard_id="shard-0",
        source_shard_row=0,
        campaign_split="train",
    )
    entry = RolloutShardEntry(
        shard_id="shard-000000",
        split="train",
        rows=(row,),
        writer_config_hash="writer",
        source_manifest_hash="source",
        source_cache_version="v1",
        split_manifest_hash=_RolloutSourceLineageBuilder.build_split_manifest_hash(
            source_manifest_hash="source", split="train", records=[row.hash_record()]
        ),
        source_store_dir="vin.zarr",
        campaign_split="train",
    )
    entry.validate()
    with pytest.raises(ValueError, match="campaign split|split_manifest_hash"):
        replace(entry, rows=(replace(row, campaign_split="test"),)).validate()


def test_v2_campaign_split_hashes_fail_closed() -> None:
    payload = {
        "manifest_version": "rollout-shard-manifest-v2",
        "shard_id": "shard-000000",
        "split": "train",
        "rows": [{"campaign_split": "pilot"}],
    }
    with pytest.raises(ValueError, match="incompatible; regenerate as v3"):
        RolloutShardEntry.from_jsonable(payload)


def test_selected_depth_renderer_config_sets_exact_size_atomically() -> None:
    base = CandidateDepthRendererConfig(output_width_px=None, output_height_px=None)

    cfg = SelectedDepthRetentionConfig(width_px=240, height_px=240).renderer_config(base)

    assert cfg.max_candidates_final == 1
    assert cfg.resolution_scale is None
    assert cfg.output_width_px == 240
    assert cfg.output_height_px == 240


def test_rollout_writer_encodes_oracle_task_into_frozen_target_lineage() -> None:
    task = OracleTargetTask(
        source_index=2,
        target_row_id=2,
        target_id="scene:snippet:gt_obbs_oracle:1:7:2",
        descriptor=TargetDescriptor(
            sem_id=1,
            class_name="chair",
            pose_world_object=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 2.0, 3.0),
            extents_m=(0.5, 0.5, 0.5),
            relative_pose_reference_object=(
                1.0,
                0.0,
                0.0,
                0.0,
                1.0,
                0.0,
                0.0,
                0.0,
                1.0,
                1.0,
                2.0,
                3.0,
            ),
        ),
        inst_id=7,
        confidence=0.9,
        identity_status=TargetTaskIdentityStatus.MATCHED.value,
        selected_rank=0,
        selection_probability=1.0,
    )
    writer = RolloutDatasetWriter.__new__(RolloutDatasetWriter)
    writer.config = SimpleNamespace(
        store=SimpleNamespace(target_protocol_version="v0_gt_input"),
        target_scorer=SimpleNamespace(target_crop_policy="gt-obb"),
        explicit_target=None,
    )

    lineage = writer._target_lineage(task, target_rank=0)

    assert lineage.target_row_id == 2
    assert lineage.target_source_index == 2
    assert lineage.matched_gt_target_row_id == 2
    assert lineage.matched_gt_target_id == task.target_id
    assert lineage.gt_match_status == "matched"
    assert lineage.target_projected_area_pixels == 0.0
    assert lineage.target_semidense_support_count == 0
    assert lineage.target_visibility_score == 0.0
    assert lineage.target_invalid_reason_bitset == 1


def test_explicit_v1_target_setup_validates_hash_sample_and_identity() -> None:
    actor = ObservedTargetDescriptor(
        sample_key="scene/snippet/0",
        source="detected_obbs",
        source_row=3,
        target_id="scene/snippet/0:detected:3:7",
        descriptor=_target_descriptor(),
        confidence=0.9,
        inst_id=7,
    )
    hash_payload = {
        "sample_key": actor.sample_key,
        "target_id": actor.target_id,
        "detected_source_row": 3,
        "gt_match_row": 5,
        "gt_match_id": "gt-5",
        "oriented_iou": 0.6,
        "descriptor_hash": actor.descriptor_hash,
    }
    config = ExplicitRolloutTargetConfig(
        sample_key=actor.sample_key,
        actor_descriptor=actor,
        detected_source_row=3,
        gt_match_row=5,
        gt_match_id="gt-5",
        oriented_iou=0.6,
        target_id=actor.target_id,
        explicit_target_hash=stable_msgspec_hash(hash_payload),
    )

    runtime = config.setup_target()

    assert runtime.protocol is TargetInputProtocol.V1_OBSERVED
    assert runtime.explicit_target_hash == config.explicit_target_hash
    with pytest.raises(ValueError, match="sample/target identity mismatch"):
        ExplicitRolloutTargetConfig(
            **{**config.model_dump(), "sample_key": "other/sample"},
        )
    with pytest.raises(ValueError, match="explicit_target_hash"):
        ExplicitRolloutTargetConfig(
            **{**config.model_dump(), "explicit_target_hash": "tampered"},
        )


def test_explicit_v1_target_preserves_actor_descriptor_and_v1_lineage_fields() -> None:
    actor = ObservedTargetDescriptor(
        sample_key="scene/snippet/0",
        source="detected_obbs",
        source_row=0,
        target_id="scene/snippet/0:detected:0:7",
        descriptor=_target_descriptor(),
        confidence=0.9,
        inst_id=7,
    )
    payload = {
        "sample_key": actor.sample_key,
        "target_id": actor.target_id,
        "detected_source_row": 0,
        "gt_match_row": 7,
        "gt_match_id": "gt-7",
        "oriented_iou": 0.6,
        "descriptor_hash": actor.descriptor_hash,
    }
    explicit = ExplicitRolloutTargetConfig(
        sample_key=actor.sample_key,
        actor_descriptor=actor,
        detected_source_row=0,
        gt_match_row=7,
        gt_match_id="gt-7",
        oriented_iou=0.6,
        status="admitted",
        reason="admitted",
        target_id=actor.target_id,
        explicit_target_hash=stable_msgspec_hash(payload),
    ).setup_target()
    writer = RolloutDatasetWriter.__new__(RolloutDatasetWriter)
    writer.config = SimpleNamespace(
        store=SimpleNamespace(target_protocol_version=TargetInputProtocol.V1_OBSERVED),
        target_scorer=SimpleNamespace(target_crop_policy="gt-obb"),
        explicit_target=explicit,
    )

    task = _explicit_target_result(explicit).selected_rows[0]
    lineage = writer._target_lineage(task, target_rank=0)

    assert task.descriptor == actor.descriptor
    assert task.source_index == 7
    assert lineage.target_protocol_version == TargetInputProtocol.V1_OBSERVED
    assert lineage.target_source == actor.source
    assert lineage.target_source_index == 0
    assert lineage.descriptor_source == actor.source
    assert lineage.descriptor_provenance == "actor_visible_detector"
    assert lineage.descriptor_hash == actor.descriptor_hash
    assert lineage.explicit_target_hash == explicit.explicit_target_hash
    assert lineage.matched_gt_target_row_id == 7
    assert lineage.matched_gt_target_id == "gt-7"
    assert lineage.gt_match_iou == pytest.approx(0.6)
    assert lineage.gt_match_status == "admitted"


@pytest.mark.parametrize(
    ("status", "reason"),
    [("rejected", "wrong_class"), ("admitted", "wrong_class")],
)
def test_explicit_v1_target_rejects_non_admitted_status_or_reason(status: str, reason: str) -> None:
    actor = ObservedTargetDescriptor(
        sample_key="scene/snippet/0",
        source="detected_obbs",
        source_row=0,
        target_id="target-0",
        descriptor=_target_descriptor(),
        confidence=0.9,
        inst_id=1,
    )
    payload = {
        "sample_key": actor.sample_key,
        "target_id": actor.target_id,
        "detected_source_row": 0,
        "gt_match_row": 1,
        "gt_match_id": "gt-1",
        "oriented_iou": 0.7,
        "descriptor_hash": actor.descriptor_hash,
    }

    with pytest.raises(ValueError, match="admitted"):
        ExplicitRolloutTargetConfig(
            sample_key=actor.sample_key,
            actor_descriptor=actor,
            detected_source_row=0,
            gt_match_row=1,
            gt_match_id="gt-1",
            oriented_iou=0.7,
            status=status,
            reason=reason,
            target_id=actor.target_id,
            explicit_target_hash=stable_msgspec_hash(payload),
        )


def test_explicit_v1_target_rejects_conflicting_oracle_sampler() -> None:
    actor = ObservedTargetDescriptor(
        sample_key="scene/snippet/0",
        source="detected_obbs",
        source_row=0,
        target_id="target-0",
        descriptor=_target_descriptor(),
        confidence=0.9,
        inst_id=1,
    )
    payload = {
        "sample_key": actor.sample_key,
        "target_id": actor.target_id,
        "detected_source_row": 0,
        "gt_match_row": 1,
        "gt_match_id": "gt-1",
        "oriented_iou": 0.7,
        "descriptor_hash": actor.descriptor_hash,
    }
    explicit = ExplicitRolloutTargetConfig(
        sample_key=actor.sample_key,
        actor_descriptor=actor,
        detected_source_row=0,
        gt_match_row=1,
        gt_match_id="gt-1",
        oriented_iou=0.7,
        target_id=actor.target_id,
        explicit_target_hash=stable_msgspec_hash(payload),
    )

    with pytest.raises(ValueError, match="oracle_target_task_sampler"):
        RolloutDatasetWriterConfig(
            explicit_target=explicit,
            store={"target_protocol_version": "v1_observed"},
            oracle_target_task_sampler={"seed": 99},
        )


def test_writer_config_v0_dump_and_hash_omit_explicit_target_field() -> None:
    config = RolloutDatasetWriterConfig.model_validate(
        {"max_targets_per_sample": None, "store": {"target_protocol_version": "v0_gt_input"}}
    )
    payload = config.model_dump_jsonable()

    class _LegacyConfig:
        def model_dump_jsonable(self) -> dict[str, Any]:
            return payload

    assert "explicit_target" not in payload
    assert stable_config_hash(config) == stable_config_hash(_LegacyConfig())  # type: ignore[arg-type]


def test_writer_config_v1_dump_omits_explicit_target_but_accepts_explicit_target() -> None:
    actor = ObservedTargetDescriptor(
        sample_key="scene/snippet/0",
        source="detected_obbs",
        source_row=0,
        target_id="target-0",
        descriptor=_target_descriptor(),
        confidence=0.9,
        inst_id=1,
    )
    payload = {
        "sample_key": actor.sample_key,
        "target_id": actor.target_id,
        "detected_source_row": 0,
        "gt_match_row": 1,
        "gt_match_id": "gt-1",
        "oriented_iou": 0.7,
        "descriptor_hash": actor.descriptor_hash,
    }
    explicit = ExplicitRolloutTargetConfig(
        sample_key=actor.sample_key,
        actor_descriptor=actor,
        detected_source_row=0,
        gt_match_row=1,
        gt_match_id="gt-1",
        oriented_iou=0.7,
        target_id=actor.target_id,
        explicit_target_hash=stable_msgspec_hash(payload),
    )
    config = RolloutDatasetWriterConfig(
        explicit_target=explicit,
        store={"target_protocol_version": "v1_observed"},
    )

    assert "explicit_target" not in config.model_dump_jsonable()


def test_explicit_target_writer_path_does_not_construct_legacy_sampler(monkeypatch: pytest.MonkeyPatch) -> None:
    actor = ObservedTargetDescriptor(
        sample_key="scene/snippet/0",
        source="detected_obbs",
        source_row=0,
        target_id="target-0",
        descriptor=_target_descriptor(),
        confidence=0.9,
        inst_id=1,
    )
    payload = {
        "sample_key": actor.sample_key,
        "target_id": actor.target_id,
        "detected_source_row": 0,
        "gt_match_row": 1,
        "gt_match_id": "gt-1",
        "oriented_iou": 0.7,
        "descriptor_hash": actor.descriptor_hash,
    }
    explicit = ExplicitRolloutTargetConfig(
        sample_key=actor.sample_key,
        actor_descriptor=actor,
        detected_source_row=0,
        gt_match_row=1,
        gt_match_id="gt-1",
        oriented_iou=0.7,
        target_id=actor.target_id,
        explicit_target_hash=stable_msgspec_hash(payload),
    )
    config = _FakeRolloutConfig([], store_dir=Path("/tmp/unused"))
    config.explicit_target = explicit
    config.max_samples = None
    config.max_targets_per_sample = None
    writer = RolloutDatasetWriter.__new__(RolloutDatasetWriter)
    writer.config = config
    writer.stats = RolloutDatasetWriterStats()
    writer.console = SimpleNamespace(warn=lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "aria_nbv.oracle.pipelines.rollout_dataset.OracleTargetTaskSampler",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("legacy sampler constructed")),
    )
    # The explicit branch is selected before the source loop; an empty source
    # fails only because no records can be generated, never because sampling ran.
    with pytest.raises(RuntimeError, match="No rollout records"):
        writer.run()


def test_rollout_shard_campaign_binding_is_copied_and_required_for_resume(tmp_path: Path) -> None:
    config = _FakeRolloutConfig([_fake_record(0)], store_dir=tmp_path)
    base_entry = plan_rollout_shards(config, rows_per_shard=1)[0]
    binding = RolloutShardCampaignBinding("campaign", "plan", "work", "target", "profile", "explicit")
    entry = replace(base_entry, campaign_binding=binding)
    final_dir = tmp_path / "final" / entry.shard_id

    result = run_rollout_shard(
        config, shard_entry=entry, output_tmp=tmp_path / "tmp" / "unit.tmp", output_final=final_dir
    )
    owner = msgspec.json.decode(result.owner_path.read_bytes())
    success = msgspec.json.decode(result.success_path.read_bytes())
    expected = binding.to_jsonable()
    assert owner["campaign_binding"] == expected
    assert success["campaign_binding"] == expected
    manifest = msgspec.json.decode((result.final_dir / result.store_result.manifest_path.name).read_bytes())
    assert manifest["generation"]["shard"]["campaign_binding"] == expected
    assert run_rollout_shard(
        config, shard_entry=entry, output_tmp=tmp_path / "tmp" / "retry.tmp", output_final=final_dir
    ).skipped
    for field in ("campaign_id", "plan_hash", "work_unit_hash", "target_id", "profile_hash", "explicit_target_hash"):
        tampered = replace(binding, **{field: f"tampered-{field}"})
        with pytest.raises(RuntimeError, match="not a validated completed shard"):
            run_rollout_shard(
                config,
                shard_entry=replace(entry, campaign_binding=tampered),
                output_tmp=tmp_path / "tmp" / f"{field}.tmp",
                output_final=final_dir,
            )


def test_rollout_shard_campaign_binding_roundtrips_generation_revision_hash() -> None:
    binding = RolloutShardCampaignBinding("campaign", "plan", "work", "target", "profile", "explicit", "revision-a")
    assert RolloutShardCampaignBinding.from_jsonable(binding.to_jsonable()) == binding


def test_rollout_shard_insufficient_support_is_typed_and_leaves_no_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _FakeRolloutConfig([_fake_record(0)], store_dir=tmp_path)
    entry = plan_rollout_shards(config, rows_per_shard=1)[0]

    class _InsufficientWriter:
        def run(self, **_kwargs):
            raise InsufficientRootSupportError("insufficient_root_support:9<10")

    monkeypatch.setattr(config, "setup_target", lambda: _InsufficientWriter())
    tmp_dir = tmp_path / "tmp" / "unit.tmp"
    final_dir = tmp_path / "final" / entry.shard_id
    result = run_rollout_shard(config, shard_entry=entry, output_tmp=tmp_dir, output_final=final_dir)
    assert result.outcome == "insufficient_support"
    assert result.reason == "insufficient_root_support:9<10"
    assert not tmp_dir.exists()
    assert not final_dir.exists()
    assert not list(final_dir.parent.glob("_FAILED.*"))


@pytest.mark.parametrize(("valid_count", "expected_calls", "raises"), [(9, 1, True), (10, 7, False)])
def test_rollout_target_probe_is_disposable_and_recipes_regenerate(
    monkeypatch: pytest.MonkeyPatch, valid_count: int, expected_calls: int, raises: bool
) -> None:
    import aria_nbv.oracle.pipelines.rollout_dataset as rollout_module

    class _Scorer:
        invalidity = None

    class _Candidates:
        def __init__(self) -> None:
            self.mask_valid = torch.tensor([True] * valid_count + [False] * (12 - valid_count))

    class _Step:
        candidates = _Candidates()

    class _Trajectory:
        steps = (_Step(),)

    class _Result:
        trajectories = (_Trajectory(),)
        mask_valid = torch.ones(10 if not raises else 9, dtype=torch.bool)

    calls = 0

    class _Generator:
        def generate_from_typed_sample(self, *_args, **_kwargs):
            nonlocal calls
            calls += 1
            return _Result()

    recipes = [
        SimpleNamespace(
            name=f"recipe-{i}",
            policy=RolloutPolicySpec(horizon=1, branch_factor=1, selection_policy="random_valid", seed=i),
        )
        for i in range(6)
    ]
    config = SimpleNamespace(
        min_valid_root_candidates=10,
        target_scorer=SimpleNamespace(setup_target=lambda **_kwargs: _Scorer()),
        selected_depth=SimpleNamespace(enabled=False),
        store=SimpleNamespace(target_eval_crops_enabled=False),
        candidate_mixture=CandidateMixtureViewGeneratorConfig(),
        recipes=recipes,
        log_timing=False,
        verbosity=1,
        is_debug=False,
    )
    writer = RolloutDatasetWriter.__new__(RolloutDatasetWriter)
    writer.config = config
    writer.stats = RolloutDatasetWriterStats()
    writer.console = SimpleNamespace(warn=lambda *_args, **_kwargs: None)
    monkeypatch.setattr(CounterfactualPoseGeneratorConfig, "setup_target", lambda self: _Generator())
    monkeypatch.setattr(CandidateMixtureViewGeneratorConfig, "setup_target", lambda self: _Generator())
    monkeypatch.setattr(
        rollout_module,
        "OracleReplayAdapter",
        lambda _scorer: SimpleNamespace(materialize=lambda result, **_kwargs: result),
    )
    monkeypatch.setattr(writer, "_target_lineage", lambda *_args, **_kwargs: SimpleNamespace())

    def call():
        return writer._rollout_target(
            sample=SimpleNamespace(
                efm_snippet_view=object(),
                scene_id="scene",
                snippet_id="snippet",
                sample_index=0,
                sample_key="sample",
                split="train",
                source_shard_id="s",
                source_shard_row=0,
            ),
            target=SimpleNamespace(target_id="target", descriptor=_target_descriptor()),
            target_rank=0,
            source_lineage=SimpleNamespace(
                config_hash=lambda *_args: "hash",
                mesh_version=lambda *_args: "mesh",
                source_manifest_hash="source",
                source_cache_version="cache",
                split_manifest_hash="split",
            ),
        )

    if raises:
        with pytest.raises(rollout_module.InsufficientRootSupportError):
            call()
    else:
        call()
    assert calls == expected_calls


def test_campaign_writer_rejects_partial_multi_recipe_target_before_store() -> None:
    writer = RolloutDatasetWriter.__new__(RolloutDatasetWriter)
    writer.config = SimpleNamespace(recipes=[object(), object(), object(), object()])
    entry = SimpleNamespace(campaign_binding=object())

    with pytest.raises(RuntimeError, match="one validated record per configured recipe"):
        writer._require_campaign_recipe_completeness([object()], entry)

    writer._require_campaign_recipe_completeness([object(), object(), object(), object()], entry)


def test_rollout_shard_without_campaign_binding_preserves_legacy_evidence(tmp_path: Path) -> None:
    config = _FakeRolloutConfig([_fake_record(0)], store_dir=tmp_path)
    entry = plan_rollout_shards(config, rows_per_shard=1)[0]
    result = run_rollout_shard(
        config,
        shard_entry=entry,
        output_tmp=tmp_path / "tmp" / "unit.tmp",
        output_final=tmp_path / "final" / entry.shard_id,
    )

    owner = msgspec.json.decode(result.owner_path.read_bytes())
    success = msgspec.json.decode(result.success_path.read_bytes())
    assert owner["campaign_binding"] is None
    assert success["campaign_binding"] is None


def test_rollout_shard_historical_evidence_without_binding_key_is_not_current(tmp_path: Path) -> None:
    config = _FakeRolloutConfig([_fake_record(0)], store_dir=tmp_path)
    entry = plan_rollout_shards(config, rows_per_shard=1)[0]
    final_dir = tmp_path / "final" / entry.shard_id
    result = run_rollout_shard(
        config,
        shard_entry=entry,
        output_tmp=tmp_path / "tmp" / "unit.tmp",
        output_final=final_dir,
    )

    current_manifest = msgspec.json.decode((result.final_dir / result.store_result.manifest_path.name).read_bytes())
    assert current_manifest["generation"]["shard"].get("campaign_binding") in (None,)

    for sidecar in (result.owner_path, result.success_path):
        payload = msgspec.json.decode(sidecar.read_bytes())
        payload.pop("campaign_binding", None)
        sidecar.write_bytes(msgspec.json.encode(payload))
    manifest_path = final_dir / result.store_result.manifest_path.name
    manifest = msgspec.json.decode(manifest_path.read_bytes())
    manifest["generation"]["shard"].pop("campaign_binding", None)
    manifest["generation"]["shard"]["generation_revision_hash"] = "stale-generation-revision"
    manifest_path.write_bytes(msgspec.json.encode(manifest))
    manifest_digest = manifest_sha256(manifest)
    zarr.open_group(final_dir, mode="r+").attrs["manifest_sha256"] = manifest_digest
    owner = msgspec.json.decode(result.owner_path.read_bytes())
    owner["rollout_manifest_sha256"] = manifest_digest
    result.owner_path.write_bytes(msgspec.json.encode(owner))
    success = msgspec.json.decode(result.success_path.read_bytes())
    success["rollout_manifest_sha256"] = manifest_digest
    success["owner_sha256"] = manifest_sha256(owner)
    result.success_path.write_bytes(msgspec.json.encode(success))

    with pytest.raises(RuntimeError, match="not a validated completed shard"):
        run_rollout_shard(
            config,
            shard_entry=entry,
            output_tmp=tmp_path / "tmp" / "retry.tmp",
            output_final=final_dir,
        )


def test_rollout_writer_config_allows_unbounded_targets_per_sample() -> None:
    config = RolloutDatasetWriterConfig.model_validate({"max_targets_per_sample": None})

    assert config.max_targets_per_sample is None
    with pytest.raises(ValueError, match="max_targets_per_sample"):
        RolloutDatasetWriterConfig.model_validate({"max_targets_per_sample": 0})


def test_rollout_writer_records_typed_root_evidence_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    invalidity = TargetRriInvalidity(
        reason=OracleEvidenceInvalidReason.ROOT_DEPTH_MISSING,
        message="root depth is unavailable",
    )

    class _Scorer:
        invalidity = None

    class _Replay:
        def generate_from_typed_sample(self, *_args, **_kwargs):
            raise OracleReplayInvalidityError(invalidity)

    recipe = SimpleNamespace(
        name="oracle_greedy",
        policy=RolloutPolicySpec(
            horizon=1,
            branch_factor=1,
            selection_policy="oracle_greedy",
            seed=0,
        ),
    )
    writer = RolloutDatasetWriter.__new__(RolloutDatasetWriter)
    writer.config = SimpleNamespace(
        target_scorer=SimpleNamespace(setup_target=lambda **_kwargs: _Scorer()),
        selected_depth=SimpleNamespace(enabled=False),
        candidate_mixture=CandidateMixtureViewGeneratorConfig(),
        recipes=[recipe],
        log_timing=False,
        verbosity=1,
        is_debug=False,
    )
    writer.stats = RolloutDatasetWriterStats()
    writer.console = SimpleNamespace(warn=lambda *_args, **_kwargs: None)
    monkeypatch.setattr(CounterfactualPoseGeneratorConfig, "setup_target", lambda self: _Replay())

    records = writer._rollout_target(
        sample=SimpleNamespace(efm_snippet_view=object(), scene_id="scene", snippet_id="snippet"),
        target=SimpleNamespace(target_id="target", descriptor=_target_descriptor()),
        target_rank=0,
        source_lineage=object(),
    )

    assert records == []
    assert writer.stats.rollout_invalid_skips == 1
    assert writer.stats.skipped_reasons == {"oracle_greedy:root_depth_missing": 1}


def test_rollout_writer_selected_depth_render_is_once_per_materialized_step() -> None:
    records = build_rollout_records(horizon=2, num_samples=6, seed=35)[:1]
    for chain_id, trajectory in enumerate(records[0].evaluated.result.trajectories):
        for step in trajectory.steps:
            evaluated_step = records[0].evaluated.step(chain_id, step.step_index)
            evaluated_step.evaluation.evidence.selected_depth_m = None
            evaluated_step.evaluation.evidence.selected_depth_valid_mask = None
    fake_renderer = _FakeSelectedDepthRenderer(height=4, width=5)
    writer = RolloutDatasetWriter.__new__(RolloutDatasetWriter)
    writer.config = SimpleNamespace(selected_depth=SimpleNamespace(height_px=4, width_px=5))

    writer._attach_selected_depths(
        evaluated=records[0].evaluated,
        sample=SimpleNamespace(efm_snippet_view=object()),
        renderer=fake_renderer,
    )

    materialized_steps = list(records[0].evaluated.steps.values())
    assert len(fake_renderer.calls) == len(materialized_steps)
    for step in materialized_steps:
        assert step.evaluation.evidence.selected_depth_m.shape == (4, 5)
        assert step.evaluation.evidence.selected_depth_valid_mask.shape == (4, 5)
        assert step.evaluation.evidence.selected_depth_image_size_hw == (4, 5)


def test_rollout_shard_manifest_planning_is_deterministic_and_order_sensitive(tmp_path: Path) -> None:
    records = [_fake_record(index) for index in range(4)]
    config = _FakeRolloutConfig(records, store_dir=tmp_path)

    first = plan_rollout_shards(config, rows_per_shard=2)
    second = plan_rollout_shards(config, rows_per_shard=2)
    reversed_entries = plan_rollout_shards(
        _FakeRolloutConfig(list(reversed(records)), store_dir=tmp_path), rows_per_shard=2
    )

    assert [entry.to_jsonable() for entry in first] == [entry.to_jsonable() for entry in second]
    assert [entry.shard_id for entry in first] == ["shard-000000", "shard-000001"]
    assert first[0].split_manifest_hash != reversed_entries[0].split_manifest_hash
    assert first[0].rows[0].source_shard_id == "vin-shard-000000"
    assert first[0].rows[0].source_shard_row == 0


def test_rollout_shard_id_canonicalization_accepts_padded_and_unpadded_forms() -> None:
    assert canonical_rollout_shard_id(7) == "shard-000007"
    assert canonical_rollout_shard_id("7") == "shard-000007"
    assert canonical_rollout_shard_id("shard-7") == "shard-000007"
    assert canonical_rollout_shard_id("shard-000007") == "shard-000007"


def test_rollout_shard_mode_rejects_manifest_source_row_mismatch(tmp_path: Path) -> None:
    records = [_fake_record(0)]
    config = _FakeRolloutConfig(records, store_dir=tmp_path)
    entry = plan_rollout_shards(config, rows_per_shard=1)[0]
    bad_entry = replace(entry, rows=(replace(entry.rows[0], scene_id="other-scene"),))
    writer = RolloutDatasetWriter.__new__(RolloutDatasetWriter)

    with pytest.raises(ValueError, match="does not match"):
        writer._apply_shard_manifest(config.source.setup_target(), bad_entry)


def test_rollout_shard_lineage_uses_row_split_when_source_config_exposes_all(tmp_path: Path) -> None:
    records = [_fake_record(0)]
    config = _FakeRolloutConfig(records, store_dir=tmp_path, source_split="all")
    entry = plan_rollout_shards(config, rows_per_shard=1)[0]
    dataset = config.source.setup_target()
    writer = RolloutDatasetWriter.__new__(RolloutDatasetWriter)

    writer._apply_shard_manifest(dataset, entry)
    source_lineage = _RolloutSourceLineageBuilder.from_dataset(dataset, max_samples=len(dataset))

    RolloutDatasetWriter._validate_shard_lineage(source_lineage, entry)


def test_rollout_shard_atomic_promotion_writes_markers_and_skips_completed(tmp_path: Path) -> None:
    records = [_fake_record(0)]
    config = _FakeRolloutConfig(records, store_dir=tmp_path)
    entry = plan_rollout_shards(config, rows_per_shard=1)[0]
    tmp_dir = tmp_path / "tmp" / "shard-000000.tmp"
    final_dir = tmp_path / "final" / "shard-000000"

    result = run_rollout_shard(config, shard_entry=entry, output_tmp=tmp_dir, output_final=final_dir)
    skipped = run_rollout_shard(config, shard_entry=entry, output_tmp=tmp_path / "other.tmp", output_final=final_dir)

    assert not result.skipped
    assert result.success_path.exists()
    assert result.owner_path.exists()
    assert not tmp_dir.exists()
    assert skipped.skipped

    alternate_row = replace(entry.rows[0], campaign_split="validation")
    alternate_entry = replace(
        entry,
        rows=(alternate_row,),
        campaign_split="validation",
        split_manifest_hash=build_rollout_split_manifest_hash(
            source_manifest_hash=entry.source_manifest_hash,
            split=entry.split,
            records=[alternate_row.hash_record()],
        ),
    )
    assert (
        read_validated_completed_shard(
            final_dir,
            shard_entry=alternate_entry,
            writer_config_hash=alternate_entry.writer_config_hash,
        )
        is None
    )


def test_read_validated_completed_shard_rejects_tampered_success_binding(tmp_path: Path) -> None:
    config = _FakeRolloutConfig([_fake_record(0)], store_dir=tmp_path)
    entry = plan_rollout_shards(config, rows_per_shard=1)[0]
    final_dir = tmp_path / "final" / entry.shard_id
    run_rollout_shard(config, shard_entry=entry, output_tmp=tmp_path / "tmp", output_final=final_dir)
    assert (
        read_validated_completed_shard(final_dir, shard_entry=entry, writer_config_hash=entry.writer_config_hash)
        is not None
    )
    success_path = final_dir / "_SUCCESS.json"
    payload = json.loads(success_path.read_text(encoding="utf-8"))
    payload["split_manifest_hash"] = "tampered"
    success_path.write_text(json.dumps(payload), encoding="utf-8")
    assert (
        read_validated_completed_shard(final_dir, shard_entry=entry, writer_config_hash=entry.writer_config_hash)
        is None
    )


def test_rollout_shard_timeout_delegates_atomic_quarantine_and_allows_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _FakeRolloutConfig([_fake_record(0)], store_dir=tmp_path)
    entry = plan_rollout_shards(config, rows_per_shard=1)[0]
    tmp_dir = tmp_path / "tmp" / "shard-000000.tmp"
    final_dir = tmp_path / "final" / entry.shard_id
    calls: list[tuple[Path, Path, str]] = []
    original_quarantine = shards_module.quarantine_rollout_staging
    original_run = _FakeShardWriter.run

    def recording_quarantine(path: Path, quarantine_root: Path, *, reason: str = "timed_out") -> Path | None:
        calls.append((path, quarantine_root, reason))
        return original_quarantine(path, quarantine_root, reason=reason)

    monkeypatch.setattr(shards_module, "quarantine_rollout_staging", recording_quarantine)

    def timeout_run(self: _FakeShardWriter, **_kwargs: object) -> None:
        self.config.store.store_dir.mkdir(parents=True)
        raise TimeoutError("synthetic timeout")

    monkeypatch.setattr(_FakeShardWriter, "run", timeout_run)

    with pytest.raises(TimeoutError, match="synthetic timeout"):
        run_rollout_shard(config, shard_entry=entry, output_tmp=tmp_dir, output_final=final_dir)

    assert calls == [(tmp_dir, tmp_dir.parent / "quarantine", "timed_out")]
    quarantined = list((tmp_dir.parent / "quarantine").glob(f"{tmp_dir.name}.timed_out-*"))
    assert len(quarantined) == 1
    assert not tmp_dir.exists()
    assert not final_dir.exists()

    monkeypatch.setattr(_FakeShardWriter, "run", original_run)
    restarted = run_rollout_shard(
        config,
        shard_entry=entry,
        output_tmp=tmp_path / "tmp" / "restart.tmp",
        output_final=final_dir,
    )
    assert restarted.skipped is False
    assert final_dir.exists()


def test_rollout_shard_resume_rejects_tampered_owner_sidecar(tmp_path: Path) -> None:
    records = [_fake_record(0)]
    config = _FakeRolloutConfig(records, store_dir=tmp_path)
    entry = plan_rollout_shards(config, rows_per_shard=1)[0]
    final_dir = tmp_path / "final" / "shard-000000"

    result = run_rollout_shard(
        config,
        shard_entry=entry,
        output_tmp=tmp_path / "tmp" / "shard-000000.tmp",
        output_final=final_dir,
    )
    owner_payload = msgspec.json.decode(result.owner_path.read_bytes())
    owner_payload["num_source_rows"] = 999
    result.owner_path.write_bytes(msgspec.json.encode(owner_payload))

    with pytest.raises(RuntimeError, match="not a validated completed shard"):
        run_rollout_shard(
            config,
            shard_entry=entry,
            output_tmp=tmp_path / "tmp" / "retry.tmp",
            output_final=final_dir,
        )


def test_rollout_shard_atomic_promotion_rejects_stale_paths(tmp_path: Path) -> None:
    records = [_fake_record(0)]
    config = _FakeRolloutConfig(records, store_dir=tmp_path)
    entry = plan_rollout_shards(config, rows_per_shard=1)[0]
    stale_tmp = tmp_path / "tmp" / "shard-000000.tmp"
    stale_tmp.mkdir(parents=True)
    partial_final = tmp_path / "final" / "shard-000000"
    partial_final.mkdir(parents=True)

    with pytest.raises(
        shards_module.RolloutShardOwnershipConflictError, match="Temporary rollout shard path already exists"
    ):
        run_rollout_shard(config, shard_entry=entry, output_tmp=stale_tmp, output_final=tmp_path / "new-final")
    with pytest.raises(shards_module.RolloutShardOwnershipConflictError, match="Final rollout shard path exists"):
        run_rollout_shard(config, shard_entry=entry, output_tmp=tmp_path / "fresh.tmp", output_final=partial_final)


def test_rollout_shard_campaign_status_reports_retry_classes(tmp_path: Path) -> None:
    records = [_fake_record(index) for index in range(4)]
    config = _FakeRolloutConfig(records, store_dir=tmp_path)
    entries = plan_rollout_shards(config, rows_per_shard=1)
    manifest_path = tmp_path / "rollout_shards.jsonl"
    final_root = tmp_path / "final"
    write_rollout_shard_manifest(manifest_path, entries)

    run_rollout_shard(
        config,
        shard_entry=entries[0],
        output_tmp=tmp_path / "tmp" / "shard-000000.tmp",
        output_final=final_root / "shard-000000",
    )
    (final_root / "_FAILED.shard-000001.foreign.json").write_text(
        json.dumps({"sidecar_kind": "rollout_shard_failure", "shard_id": entries[1].shard_id}),
        encoding="utf-8",
    )
    (final_root / "_FAILED.shard-000001.2026-05-15T00-00-00Z.json").write_text(
        json.dumps(
            {
                "sidecar_kind": "rollout_shard_failure",
                "shard_id": entries[1].shard_id,
                "writer_config_hash": entries[1].writer_config_hash,
                "source_manifest_hash": entries[1].source_manifest_hash,
                "split_manifest_hash": entries[1].split_manifest_hash,
                "generation_revision_hash": entries[1].generation_revision_hash,
                "campaign_binding": None,
                "error": "synthetic failure",
            }
        ),
        encoding="utf-8",
    )
    (final_root / "shard-000002").mkdir(parents=True)

    campaign = summarize_rollout_shard_campaign(manifest_path, final_root=final_root)
    by_id = {shard.shard_id: shard for shard in campaign.shards}

    assert campaign.counts == {"succeeded": 1, "failed": 1, "incomplete": 1, "missing": 1}
    assert by_id["shard-000000"].status == "succeeded"
    assert by_id["shard-000001"].status == "failed"
    assert by_id["shard-000001"].failed_markers
    assert len(by_id["shard-000001"].failed_markers) == 1
    assert by_id["shard-000002"].status == "incomplete"
    assert by_id["shard-000003"].status == "missing"


def test_failure_sidecar_binds_campaign_and_excludes_tampered_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _FakeRolloutConfig([_fake_record(0)], store_dir=tmp_path)
    base_entry = plan_rollout_shards(config, rows_per_shard=1)[0]
    binding = RolloutShardCampaignBinding("campaign", "plan", "work", "target", "profile", "explicit")
    entry = replace(base_entry, campaign_binding=binding)
    final_root = tmp_path / "final"

    class _FailingWriter:
        def run(self, **_kwargs: object) -> None:
            raise RuntimeError("synthetic failure")

    monkeypatch.setattr(config, "setup_target", lambda: _FailingWriter())
    with pytest.raises(RuntimeError, match="synthetic failure"):
        run_rollout_shard(
            config,
            shard_entry=entry,
            output_tmp=tmp_path / "tmp" / "unit.tmp",
            output_final=final_root / entry.shard_id,
        )

    marker = next(final_root.glob(f"_FAILED.{entry.shard_id}.*.json"))
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert payload["campaign_binding"] == binding.to_jsonable()

    tampered = dict(payload)
    tampered["campaign_binding"] = {**binding.to_jsonable(), "work_unit_hash": "tampered"}
    (final_root / f"_FAILED.{entry.shard_id}.tampered.json").write_text(json.dumps(tampered), encoding="utf-8")
    manifest_path = tmp_path / "rollout_shards.jsonl"
    write_rollout_shard_manifest(manifest_path, [entry])
    campaign = summarize_rollout_shard_campaign(manifest_path, final_root=final_root)
    status = campaign.shards[0]
    assert status.status == "failed"
    assert status.failed_markers == (marker,)


def test_rollout_source_manifest_is_profile_independent_and_roundtrips(tmp_path: Path) -> None:
    records = [_fake_record(index) for index in range(3)]
    config = _FakeRolloutConfig(records, store_dir=tmp_path)

    manifest = plan_rollout_source_manifest(config.source)
    output_path = tmp_path / "source-manifest.json"
    write_rollout_source_manifest(output_path, manifest)
    restored = read_rollout_source_manifest(output_path)

    assert restored == manifest
    assert restored.source_store_dir == config.source.store.store_dir.name
    assert not Path(restored.source_store_dir).is_absolute()
    assert [row.sample_key for row in restored.rows] == [record.sample_key for record in records]
    assert restored.split_manifest_hash == _RolloutSourceLineageBuilder.build_split_manifest_hash(
        source_manifest_hash=restored.source_manifest_hash,
        split="train",
        records=[row.hash_record() for row in restored.rows],
    )
    assert "writer_config_hash" not in restored.to_jsonable()


def test_rollout_source_manifest_rejects_duplicate_source_rows(tmp_path: Path) -> None:
    records = [_fake_record(0), _fake_record(0)]
    config = _FakeRolloutConfig(records, store_dir=tmp_path)

    with pytest.raises(ValueError, match="duplicate source-row identities"):
        plan_rollout_source_manifest(config.source)


def test_rollout_writer_applies_reviewed_source_manifest_order(tmp_path: Path) -> None:
    records = [_fake_record(index) for index in range(3)]
    config = _FakeRolloutConfig(records, store_dir=tmp_path)
    manifest = plan_rollout_source_manifest(config.source)
    dataset = config.source.setup_target()
    dataset._records = list(reversed(dataset._records))

    RolloutDatasetWriter._apply_source_manifest(dataset, manifest)

    assert [record.sample_key for record in dataset._records] == [row.sample_key for row in manifest.rows]


def test_rollout_writer_applies_exact_source_subset_order_and_validates_lineage(tmp_path: Path) -> None:
    records = [_fake_record(index) for index in range(3)]
    config = _FakeRolloutConfig(records, store_dir=tmp_path)
    manifest = plan_rollout_source_manifest(config.source)
    sample_keys = [records[2].sample_key, records[0].sample_key]
    dataset = config.source.setup_target()

    RolloutDatasetWriter._apply_source_manifest(dataset, manifest, sample_keys=sample_keys)
    lineage = _RolloutSourceLineageBuilder.from_dataset(dataset, max_samples=len(dataset))
    selected_rows = _select_source_manifest_rows(manifest, sample_keys)
    expected_subset_hash = _RolloutSourceLineageBuilder.build_split_manifest_hash(
        source_manifest_hash=manifest.source_manifest_hash,
        split=manifest.split,
        records=[{**row.hash_record(), "order": order} for order, row in enumerate(selected_rows)],
    )

    assert [record.sample_key for record in dataset._records] == sample_keys
    assert lineage.split_manifest_hash == expected_subset_hash
    RolloutDatasetWriter._validate_source_manifest_lineage(
        lineage,
        manifest,
        expected_split_manifest_hash=lineage.split_manifest_hash,
    )
    with pytest.raises(ValueError, match="ordered source rows"):
        RolloutDatasetWriter._validate_source_manifest_lineage(
            lineage,
            manifest,
            expected_split_manifest_hash=manifest.split_manifest_hash,
        )


def test_rollout_shard_mode_uses_planned_subset_rows_and_validates_shard_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = [_fake_record(index) for index in range(3)]
    config = _FakeRolloutConfig(records, store_dir=tmp_path)
    manifest = plan_rollout_source_manifest(config.source)
    manifest_path = tmp_path / "source-manifest.json"
    write_rollout_source_manifest(manifest_path, manifest)
    config.source_manifest_path = manifest_path
    config.sample_keys = [records[2].sample_key, records[0].sample_key]
    entries = plan_rollout_shards(config, rows_per_shard=1)

    assert [entry.rows[0].sample_key for entry in entries] == config.sample_keys

    config.oracle_target_task_sampler = object()
    monkeypatch.setattr(
        "aria_nbv.oracle.pipelines.rollout_dataset.OracleTargetTaskSampler",
        lambda _config: object(),
    )
    validated: list[tuple[_RolloutSourceLineageBuilder, RolloutShardEntry]] = []

    class _ValidationReachedError(RuntimeError):
        pass

    validate_shard_lineage = RolloutDatasetWriter._validate_shard_lineage

    def _capture_validation(
        lineage: _RolloutSourceLineageBuilder,
        shard_entry: RolloutShardEntry,
    ) -> None:
        validated.append((lineage, shard_entry))
        validate_shard_lineage(lineage, shard_entry)
        raise _ValidationReachedError

    monkeypatch.setattr(RolloutDatasetWriter, "_validate_shard_lineage", staticmethod(_capture_validation))
    writer = RolloutDatasetWriter.__new__(RolloutDatasetWriter)
    writer.config = config

    with pytest.raises(_ValidationReachedError):
        writer.run(shard_entry=entries[0])

    assert len(validated) == 1
    assert validated[0][0].split_manifest_hash == entries[0].split_manifest_hash


def _fake_record(index: int) -> SimpleNamespace:
    return SimpleNamespace(
        sample_index=index,
        sample_key=f"scene-a:snippet-{index:03d}",
        scene_id="scene-a",
        snippet_id=f"snippet-{index:03d}",
        split="train",
        shard_id="vin-shard-000000",
        row=index,
    )
