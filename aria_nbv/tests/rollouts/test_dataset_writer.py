"""Tests for rollout dataset writer lineage helpers."""

# ruff: noqa: S101

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import msgspec
import pytest
import torch

from aria_nbv.oracle.evidence import OracleEvidenceInvalidReason
from aria_nbv.oracle.pipelines.rollout_dataset import (
    RolloutDatasetWriter,
    RolloutDatasetWriterConfig,
    RolloutDatasetWriterStats,
    SelectedDepthRetentionConfig,
    _RolloutSourceLineageBuilder,
    _TargetRriInvalidityError,
)
from aria_nbv.oracle.pipelines.shards import plan_rollout_shards, run_rollout_shard, summarize_rollout_shard_campaign
from aria_nbv.oracle.target_rri import TargetRriInvalidity
from aria_nbv.oracle.target_selection import (
    ORACLE_TARGET_TASK_SOURCE,
    OracleTargetTaskRow,
    TargetTaskIdentityStatus,
    target_candidate_row_from_task,
)
from aria_nbv.pose_generation import CandidateMixtureViewGeneratorConfig
from aria_nbv.rendering import CandidateDepthRendererConfig
from aria_nbv.rollouts.manifest import RolloutStoreManifestContext
from aria_nbv.rollouts.replay.engine import CounterfactualPoseGeneratorConfig
from aria_nbv.rollouts.replay.policy import RolloutPolicySpec
from aria_nbv.rollouts.shard_manifest import RolloutShardEntry, canonical_rollout_shard_id, write_rollout_shard_manifest
from aria_nbv.rollouts.zarr_store import write_rollout_zarr_store
from aria_nbv.targets import TargetDescriptor
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
        self._dump_token = "fake-rollout-config-v1"

    def model_dump_jsonable(self) -> dict[str, Any]:
        return {"dump_token": self._dump_token, "source_store": self.source.store.store_dir.as_posix()}

    def model_copy(self, *, deep: bool = False) -> "_FakeRolloutConfig":
        return deepcopy(self) if deep else self

    def setup_target(self) -> "_FakeShardWriter":
        return _FakeShardWriter(self)


class _FakeShardWriter:
    def __init__(self, config: _FakeRolloutConfig) -> None:
        self.config = config

    def run(self, *, invocation: object | None = None, shard_entry: RolloutShardEntry | None = None):
        del invocation
        if shard_entry is None:
            raise AssertionError("Shard writer tests must pass a shard entry.")
        records = build_rollout_records(horizon=1, num_samples=6, seed=33)[:1]
        records[0].lineage.source_offline_store_manifest_hash = shard_entry.source_manifest_hash
        records[0].lineage.source_cache_version = shard_entry.source_cache_version
        records[0].lineage.split_manifest_hash = shard_entry.split_manifest_hash
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


def test_selected_depth_renderer_config_sets_exact_size_atomically() -> None:
    base = CandidateDepthRendererConfig(output_width_px=None, output_height_px=None)

    cfg = SelectedDepthRetentionConfig(width_px=240, height_px=240).renderer_config(base)

    assert cfg.max_candidates_final == 1
    assert cfg.resolution_scale is None
    assert cfg.output_width_px == 240
    assert cfg.output_height_px == 240


def test_rollout_writer_oracle_target_task_adapter_marks_identity_valid_gt_label() -> None:
    row = OracleTargetTaskRow(
        scene_id="scene",
        snippet_id="snippet",
        source=ORACLE_TARGET_TASK_SOURCE,
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
        projected_area_pixels=0.0,
        projected_area_fraction=0.0,
        semidense_support_count=0,
        evl_support_count=0,
        effective_support_count=0.0,
        identity_iou=None,
        identity_second_iou=None,
        identity_ambiguity_gap=None,
        identity_status=TargetTaskIdentityStatus.MATCHED.value,
        identity_valid=True,
        selected_rank=0,
        selection_probability=1.0,
    )

    target = target_candidate_row_from_task(row)

    assert target.gt_label_valid
    assert target.gt_match_status == "matched"
    assert target.visibility_score == 0.0
    assert target.support_score == 0.0
    assert target.deficit_score == 0.0
    assert math.isnan(target.score)
    assert target.gt_target_row_id == 2
    assert target.gt_match_iou is None
    assert target.gt_match_score is None
    assert math.isnan(target.score)
    assert target.source == ORACLE_TARGET_TASK_SOURCE
    assert target.invalid_reason_bitset == 1


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
            raise _TargetRriInvalidityError(invalidity)

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
    monkeypatch.setattr(
        "aria_nbv.oracle.pipelines.rollout_dataset.target_descriptor_from_candidate_row",
        lambda _target: _target_descriptor(),
    )
    monkeypatch.setattr(CounterfactualPoseGeneratorConfig, "setup_target", lambda self: _Replay())

    records = writer._rollout_target(
        sample=SimpleNamespace(efm_snippet_view=object(), scene_id="scene", snippet_id="snippet"),
        target=SimpleNamespace(target_id="target"),
        target_rank=0,
        source_lineage=object(),
    )

    assert records == []
    assert writer.stats.rollout_invalid_skips == 1
    assert writer.stats.skipped_reasons == {"oracle_greedy:root_depth_missing": 1}


def test_rollout_writer_selected_depth_render_is_once_per_materialized_step() -> None:
    records = build_rollout_records(horizon=2, num_samples=6, seed=35)[:1]
    for trajectory in records[0].result.trajectories:
        for step in trajectory.steps:
            step.selected_depth_m = None
            step.selected_depth_valid_mask = None
    fake_renderer = _FakeSelectedDepthRenderer(height=4, width=5)
    writer = RolloutDatasetWriter.__new__(RolloutDatasetWriter)
    writer.config = SimpleNamespace(selected_depth=SimpleNamespace(height_px=4, width_px=5))

    writer._attach_selected_depths(
        result=records[0].result,
        sample=SimpleNamespace(efm_snippet_view=object()),
        renderer=fake_renderer,
    )

    materialized_steps = [step for trajectory in records[0].result.trajectories for step in trajectory.steps]
    assert len(fake_renderer.calls) == len(materialized_steps)
    for step in materialized_steps:
        assert step.selected_depth_m.shape == (4, 5)
        assert step.selected_depth_valid_mask.shape == (4, 5)
        assert step.selected_depth_image_size_hw == (4, 5)


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

    with pytest.raises(RuntimeError, match="Temporary rollout shard path already exists"):
        run_rollout_shard(config, shard_entry=entry, output_tmp=stale_tmp, output_final=tmp_path / "new-final")
    with pytest.raises(RuntimeError, match="Final rollout shard path exists"):
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
    (final_root / "_FAILED.shard-000001.2026-05-15T00-00-00Z.json").write_text(
        '{"error": "synthetic failure"}',
        encoding="utf-8",
    )
    (final_root / "shard-000002").mkdir(parents=True)

    campaign = summarize_rollout_shard_campaign(manifest_path, final_root=final_root)
    by_id = {shard.shard_id: shard for shard in campaign.shards}

    assert campaign.counts == {"succeeded": 1, "failed": 1, "incomplete": 1, "missing": 1}
    assert by_id["shard-000000"].status == "succeeded"
    assert by_id["shard-000001"].status == "failed"
    assert by_id["shard-000001"].failed_markers
    assert by_id["shard-000002"].status == "incomplete"
    assert by_id["shard-000003"].status == "missing"


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
