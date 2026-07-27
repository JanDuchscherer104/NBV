"""Public contract tests for complete-chain ``Q_H`` data batches."""

# ruff: noqa: S101

from __future__ import annotations

from dataclasses import astuple, dataclass, fields
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
import torch
from efm3d.aria.pose import PoseTW
from torch.utils.data import DataLoader, RandomSampler

import aria_nbv.data_handling.qh as qh
from aria_nbv.data_handling.offline.format import VinOfflineIndexRecord
from aria_nbv.data_handling.qh import (
    QhChainLineage,
    QhDataset,
    QhInputs,
    QhRolloutChain,
    QhSupervision,
    collate_qh_samples,
)
from aria_nbv.data_handling.raw.views import VinSnippetView
from aria_nbv.lightning.qh_datamodule import QhDataModule, distributed_padding_rows
from aria_nbv.utils import Stage
from aria_nbv.utils.fingerprints import stable_msgspec_hash

LINEAGE_FIELDS = [
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


def _lineage(*, horizon: int = 2, rollout_row_id: int = 0, manifest_hash: str = "manifest") -> QhChainLineage:
    return QhChainLineage(
        0,
        0,
        "sample-0",
        "shard-0",
        0,
        "scene-0",
        "snippet-0",
        Stage.TRAIN,
        "7",
        manifest_hash,
        "split-hash",
        "mesh-v1",
        0,
        1,
        2,
        "v0_gt_input",
        "gt_obbs_oracle",
        "crop-v1",
        "8",
        "reason-v1",
        "discounted_target_root_gain",
        "selected_transition_double_q",
        "target_root_gain",
        0.95,
        horizon,
        rollout_row_id,
        f"rollout-{rollout_row_id}",
        rollout_row_id,
        10,
        1,
        2,
        "greedy",
        1,
        -1,
        0.0,
        7,
        "horizon",
        "candidate-hash",
        "oracle-hash",
        "rollout-hash",
        "",
        "",
        "",
    )


def _snippet(points: int = 2) -> VinSnippetView:
    return VinSnippetView(
        points_world=torch.arange(points * 3, dtype=torch.float32).reshape(points, 3),
        lengths=torch.tensor([points], dtype=torch.int64),
        t_world_rig=PoseTW(torch.zeros(1, 12)),
    )


def _chain(*, steps: int, width: int, offset: int = 0) -> QhRolloutChain:
    ids = torch.arange(offset, offset + steps * width, dtype=torch.int64).reshape(steps, width)
    poses = torch.arange(steps * width * 12, dtype=torch.float32).reshape(steps, width, 12) + offset
    positions = torch.arange(width, dtype=torch.int64).repeat(steps, 1)
    selected = torch.arange(steps, dtype=torch.int64).remainder(width)
    selected_pose = poses.gather(1, selected[:, None, None].expand(steps, 1, 12)).squeeze(1)
    selected_position = positions.gather(1, selected[:, None]).squeeze(1)
    previous_pose = torch.zeros(steps, 12)
    previous_position = torch.full((steps,), -1, dtype=torch.int64)
    previous_mask = torch.zeros(steps, dtype=torch.bool)
    if steps > 1:
        previous_pose[1:] = selected_pose[:-1]
        previous_position[1:] = selected_position[:-1]
        previous_mask[1:] = True
    terminal = torch.zeros(steps, dtype=torch.bool)
    terminal[-1] = True
    discount = torch.full((steps,), 0.95)
    discount[-1] = 0
    return QhRolloutChain(
        inputs=QhInputs(
            vin_snippet=_snippet(points=steps),
            root_pose_world=torch.zeros(12),
            target_extents=torch.ones(3),
            target_pose_world_object=torch.zeros(12),
            candidate_pose_relative_root=poses,
            candidate_position_id=positions,
            actor_action_mask=torch.ones(steps, width, dtype=torch.bool),
            previous_selected_pose_relative_root=previous_pose,
            previous_selected_position_id=previous_position,
            previous_selected_mask=previous_mask,
            remaining_budget=torch.arange(steps, 0, -1),
            step_mask=torch.ones(steps, dtype=torch.bool),
        ),
        supervision=QhSupervision(
            candidate_row_id=ids,
            q_train_mask=torch.ones(steps, width, dtype=torch.bool),
            invalid_reason_bitset=torch.zeros(steps, width, dtype=torch.int64),
            one_step_target_rri=ids.float() / 10,
            one_step_target_root_gain=ids.float() / 5,
            selected_candidate_index=selected,
            discount=discount,
            terminal=terminal,
            row_train_mask=torch.ones(steps, dtype=torch.bool),
        ),
        lineage=_lineage(horizon=steps, rollout_row_id=offset),
    )


def test_public_qh_dtos_are_exactly_five_and_lineage_has_43_cpu_scalars() -> None:
    assert qh.__all__ == ["QhRolloutChain", "QhChainLineage", "QhInputs", "QhSupervision", "QhBatch"]
    assert [field.name for field in fields(QhChainLineage)] == LINEAGE_FIELDS
    lineage = _lineage()
    assert len(fields(lineage)) == 43
    assert not hasattr(lineage, "to")
    assert not hasattr(lineage, "pin_memory")
    assert all(not isinstance(value, torch.Tensor) for value in astuple(lineage))


def test_actor_inputs_and_supervision_are_structurally_separate() -> None:
    input_fields = {field.name for field in fields(QhInputs)}
    banned = {
        "candidate_row_id",
        "q_train_mask",
        "invalid_reason_bitset",
        "one_step_target_rri",
        "one_step_target_root_gain",
        "selected_candidate_index",
        "reward",
        "rollout_row_id",
    }
    assert input_fields.isdisjoint(banned)
    assert [field.name for field in fields(QhSupervision)] == [
        "candidate_row_id",
        "q_train_mask",
        "invalid_reason_bitset",
        "one_step_target_rri",
        "one_step_target_root_gain",
        "selected_candidate_index",
        "discount",
        "terminal",
        "row_train_mask",
    ]


def test_selected_facts_are_gathered_from_dense_supervision() -> None:
    supervision = _chain(steps=3, width=3).supervision
    expected = torch.tensor([0, 4, 8])
    assert torch.equal(supervision.selected_candidate_row_id, expected)
    assert torch.equal(supervision.selected_reward, expected.float() / 5)
    assert torch.equal(supervision.selected_rri, expected.float() / 10)


def test_collate_pads_time_and_candidates_and_preserves_causal_history() -> None:
    first = _chain(steps=2, width=3)
    second = _chain(steps=3, width=2, offset=100)
    batch = collate_qh_samples([first, second])

    assert batch.inputs.candidate_pose_relative_root.shape == (2, 3, 3, 12)
    assert batch.supervision.candidate_row_id.shape == (2, 3, 3)
    assert batch.inputs.step_mask.tolist() == [[True, True, False], [True, True, True]]
    assert not batch.inputs.actor_action_mask[0, 2].any()
    assert not batch.supervision.q_train_mask[0, 2].any()
    assert not batch.supervision.row_train_mask[0, 2]
    assert batch.supervision.candidate_row_id[0, 2].eq(-1).all()
    assert batch.inputs.candidate_position_id[1, :, 2].eq(-1).all()
    assert torch.equal(
        batch.inputs.previous_selected_pose_relative_root[1, 1:],
        second.inputs.candidate_pose_relative_root[torch.arange(2), second.supervision.selected_candidate_index[:-1]],
    )
    assert batch.inputs.previous_selected_position_id[0, 0] == -1
    assert not batch.inputs.previous_selected_mask[:, 0].any()
    batch.assert_selected_rows_consistent()


def test_padding_numeric_values_are_inert_under_explicit_masks() -> None:
    batch = collate_qh_samples([_chain(steps=1, width=1), _chain(steps=2, width=2, offset=10)])
    valid = batch.inputs.step_mask.unsqueeze(-1) & batch.inputs.actor_action_mask
    baseline = batch.inputs.candidate_pose_relative_root[valid].sum()
    changed = batch.inputs.candidate_pose_relative_root.clone()
    changed[~valid] = 1e9
    assert changed[valid].sum() == baseline
    assert not batch.supervision.row_train_mask[~batch.inputs.step_mask].any()


def test_batch_transfer_visits_each_tensor_once_and_keeps_lineage_cpu_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch = collate_qh_samples([_chain(steps=2, width=2)])
    lineage = batch.lineage
    calls: list[int] = []
    original = torch.Tensor.to

    def recording_to(value: torch.Tensor, *args: Any, **kwargs: Any) -> torch.Tensor:
        calls.append(id(value))
        return original(value, *args, **kwargs)

    monkeypatch.setattr(torch.Tensor, "to", recording_to)
    moved = batch.to("cpu")
    assert moved.lineage is lineage
    assert len(calls) == len(set(calls))
    assert len(calls) == 23


@dataclass
class _Manifest:
    version: int = 7


class _ActorReader:
    def __init__(self, manifest: _Manifest, record: VinOfflineIndexRecord) -> None:
        self.manifest = manifest
        self.record = record
        self.config = SimpleNamespace(store_dir=Path("/tmp/vin"))
        self.reads = 0

    def get_split_records(self, _split: Stage | None) -> list[VinOfflineIndexRecord]:
        return [self.record]

    def read_actor_snippet(self, record: VinOfflineIndexRecord, *, device: str = "cpu") -> VinSnippetView:
        assert record is self.record
        assert device == "cpu"
        self.reads += 1
        return _snippet()


class _RolloutReader:
    def __init__(self, stored: SimpleNamespace, source: SimpleNamespace) -> None:
        self.stored = stored
        self.source_lineage = (source,)
        self.scene_ids = frozenset({source.scene_id})
        self.q_h_horizon = 2
        self.provenance = {"stores": []}

    def __len__(self) -> int:
        return 1

    def __getitem__(self, index: int) -> SimpleNamespace:
        assert index in (0, -1)
        return self.stored


def test_dataset_item_is_one_chain_and_reads_one_actor_snippet() -> None:
    manifest = _Manifest()
    manifest_hash = stable_msgspec_hash(manifest)
    lineage = _lineage(manifest_hash=manifest_hash)
    source = SimpleNamespace(**{name: getattr(lineage, name) for name in LINEAGE_FIELDS[:11]})
    stored = SimpleNamespace(
        root_pose_world=np.zeros(12, dtype=np.float32),
        target_extents=np.ones(3, dtype=np.float32),
        target_pose_world_object=np.zeros(12, dtype=np.float32),
        candidate_pose_relative_root=(np.zeros((2, 12), dtype=np.float32), np.ones((1, 12), dtype=np.float32)),
        candidate_position_id=(np.array([0, 1], dtype=np.int32), np.array([2], dtype=np.int32)),
        actor_action_mask=(np.array([True, True]), np.array([True])),
        remaining_budget=np.array([2, 1], dtype=np.int64),
        candidate_row_id=(np.array([0, 1], dtype=np.int64), np.array([2], dtype=np.int64)),
        q_train_mask=(np.array([True, True]), np.array([True])),
        invalid_reason_bitset=(np.zeros(2, dtype=np.uint32), np.zeros(1, dtype=np.uint32)),
        one_step_target_rri=(np.array([0.1, 0.2], dtype=np.float32), np.array([0.3], dtype=np.float32)),
        one_step_target_root_gain=(np.array([0.4, 0.5], dtype=np.float32), np.array([0.6], dtype=np.float32)),
        selected_candidate_index=np.array([1, 0], dtype=np.int64),
        discount=np.array([0.95, 0], dtype=np.float32),
        terminal=np.array([False, True]),
        lineage=astuple(lineage),
    )
    record = VinOfflineIndexRecord(0, "sample-0", "scene-0", "snippet-0", "train", "shard-0", 0)
    actor = _ActorReader(manifest, record)
    dataset = QhDataset(rollout_reader=_RolloutReader(stored, source), actor_reader=actor)  # type: ignore[arg-type]

    chain = dataset[0]
    assert len(dataset) == 1
    assert actor.reads == 1
    assert chain.inputs.candidate_pose_relative_root.shape == (2, 2, 12)
    assert chain.inputs.previous_selected_position_id.tolist() == [-1, 1]
    assert chain.supervision.selected_candidate_row_id.tolist() == [1, 2]
    assert chain.supervision.row_train_mask.tolist() == [True, True]


def test_chain_dataset_collates_with_multiple_workers() -> None:
    samples = [_chain(steps=2, width=2, offset=index * 10) for index in range(4)]
    loader = DataLoader(samples, batch_size=2, num_workers=2, collate_fn=collate_qh_samples)
    batches = list(loader)
    assert [batch.inputs.step_mask.sum().item() for batch in batches] == [4, 4]
    assert [lineage.rollout_row_id for batch in batches for lineage in batch.lineage] == [0, 10, 20, 30]


class _StaticDataset(torch.utils.data.Dataset[QhRolloutChain]):
    def __init__(self, samples: list[QhRolloutChain], *, scene: str, horizon: int = 2) -> None:
        self.samples = samples
        self.scene_ids = frozenset({scene})
        self.q_h_horizon = horizon
        self.provenance = {"scene": scene}

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> QhRolloutChain:
        return self.samples[index]


def test_datamodule_uses_chain_datasets_and_lightning_default_sampler() -> None:
    train = _StaticDataset([_chain(steps=2, width=2) for _ in range(3)], scene="train")
    data = QhDataModule(train=train, batch_size=2, seed=7)
    loader = data.train_dataloader()

    assert data.training_horizon == 2
    assert isinstance(loader.sampler, RandomSampler)
    assert distributed_padding_rows(train, world_size=2) == 1
    assert next(iter(loader)).inputs.step_mask.shape == (2, 2)


def test_datamodule_rejects_empty_overlap_and_horizon_mismatch() -> None:
    chain = _chain(steps=2, width=2)
    train = _StaticDataset([chain], scene="shared")
    with pytest.raises(ValueError, match="at least one chain"):
        QhDataModule(train=_StaticDataset([], scene="train"), seed=7)
    with pytest.raises(ValueError, match="overlap scenes"):
        QhDataModule(train=train, val=_StaticDataset([chain], scene="shared"), seed=7)
    with pytest.raises(ValueError, match="equal positive"):
        QhDataModule(train=train, val=_StaticDataset([chain], scene="val", horizon=3), seed=7)


def test_experiment_uses_chain_stages_and_lightning_sampler_defaults() -> None:
    package_root = Path(qh.__file__).parents[1]
    source = (package_root / "lightning" / "qh_experiment.py").read_text(encoding="utf-8")
    assert "data.corpus" not in source
    assert "prepare_training_sampler" not in source
    assert "dataset_for_stage" in source
    for name in ("train_qh_v0_smoke.toml", "train_qh_v0_lrz.template.toml"):
        config = (package_root.parents[1] / ".configs" / name).read_text(encoding="utf-8")
        assert "use_distributed_sampler = true" in config
