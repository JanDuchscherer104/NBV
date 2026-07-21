"""Contract tests for the dedicated finite-candidate Q_H data seam."""

# ruff: noqa: S101

from __future__ import annotations

import inspect
from dataclasses import fields, replace
from typing import Any

import numpy as np
import pytest
import pytorch_lightning as pl
import torch
from torch.utils.data import Dataset, DistributedSampler, SequentialSampler

import aria_nbv.lightning as lightning_root
from aria_nbv.data_handling.offline.actor import VinActorSample
from aria_nbv.lightning.qh_data import (
    QhBatch,
    QhDataModule,
    QhDataset,
    QhSample,
    QhSupervision,
    QhTransition,
    collate_qh_samples,
)
from aria_nbv.rollouts.qh_reader import (
    QhActorState as StoredActor,
)
from aria_nbv.rollouts.qh_reader import (
    QhLineage as StoredLineage,
)
from aria_nbv.rollouts.qh_reader import (
    QhRolloutState,
    QhSourceLineage,
    QhStateLocator,
)
from aria_nbv.rollouts.qh_reader import (
    QhSupervision as StoredSupervision,
)
from aria_nbv.rollouts.qh_reader import (
    QhTransition as StoredTransition,
)


def _lineage(step: int, *, protocol: str = "v0_gt_input", scene: str = "scene-a") -> StoredLineage:
    return StoredLineage(
        source_row_id=900,
        source_sample_index=41,
        source_sample_key=f"{scene}:snippet-a",
        source_shard_id="shard-sparse",
        source_shard_row=3,
        scene_id=scene,
        snippet_id="snippet-a",
        split="train",
        source_cache_version="7",
        source_offline_store_manifest_hash="source-hash",
        split_manifest_hash="split-hash",
        target_protocol_version=protocol,
        target_source="gt_obbs_oracle",
        schema_version="1",
        reason_code_version="1",
        return_semantics="cumulative_target_root_gain",
        td_semantics="selected_transition_only",
        reward_metric="target_root_gain",
        discount_gamma=0.9,
        horizon=2,
        rollout_row_id=0,
        rollout_id="rollout-a",
        chain_id=0,
        step_index=step,
        candidate_config_hash="candidate-hash",
        oracle_config_hash="oracle-hash",
        rollout_config_hash="rollout-hash",
    )


def _stored_state(step: int, *, width: int, terminal: bool, protocol: str = "v0_gt_input") -> QhRolloutState:
    ids = np.arange(step * 10, step * 10 + width, dtype=np.int64)
    poses = np.repeat(ids[:, None], 12, axis=1).astype(np.float32)
    history_ids = np.arange(step, dtype=np.int64) + 100
    history_poses = np.repeat(history_ids[:, None], 12, axis=1).astype(np.float32)
    selected = min(1, width - 1)
    next_state = None if terminal else QhStateLocator(0, step + 1)
    return QhRolloutState(
        locator=QhStateLocator(0, step),
        actor=StoredActor(
            candidate_row_id=ids,
            candidate_pose_world_cam=poses,
            candidate_pose_relative_root=poses + 0.5,
            candidate_position_id=ids + 200,
            actor_action_mask=np.asarray([True] * width),
            target_row_id=0,
            target_center_world=np.asarray([1.0, 2.0, 3.0], dtype=np.float32),
            target_extents=np.asarray([0.4, 0.5, 0.6], dtype=np.float32),
            target_pose_world_object=np.arange(12, dtype=np.float32),
            target_relative_pose_reference_object=np.arange(12, dtype=np.float32) + 10,
            target_sem_id=4,
            target_inst_id=44,
            history_candidate_row_id=history_ids,
            history_pose_world_cam=history_poses,
            history_pose_relative_root=history_poses + 0.25,
            history_position_id=history_ids + 200,
            remaining_budget=2 - step,
        ),
        supervision=StoredSupervision(
            q_train_mask=np.asarray([True] * width),
            invalid_reason_bitset=np.arange(width, dtype=np.uint32) + 10,
            one_step_target_rri=ids.astype(np.float32) + 0.1,
            one_step_target_root_gain=ids.astype(np.float32) + 0.2,
        ),
        transition=StoredTransition(
            selected_candidate_index=selected,
            selected_candidate_row_id=int(ids[selected]),
            reward=float(ids[selected]) + 0.2,
            reward_target_rri=float(ids[selected]) + 0.1,
            discount=0.0 if terminal else 0.9,
            terminal=terminal,
            next_state=next_state,
        ),
        lineage=_lineage(step, protocol=protocol),
    )


class _Reader:
    def __init__(self, states: tuple[QhRolloutState, ...]) -> None:
        self.states = states
        lineages = tuple(state.lineage for state in states)
        self.source_lineage = tuple(
            dict.fromkeys(
                QhSourceLineage(
                    source_row_id=lineage.source_row_id,
                    source_sample_index=lineage.source_sample_index,
                    source_sample_key=lineage.source_sample_key,
                    source_shard_id=lineage.source_shard_id,
                    source_shard_row=lineage.source_shard_row,
                    scene_id=lineage.scene_id,
                    snippet_id=lineage.snippet_id,
                    split=lineage.split,
                    source_cache_version=lineage.source_cache_version,
                    source_offline_store_manifest_hash=lineage.source_offline_store_manifest_hash,
                    split_manifest_hash=lineage.split_manifest_hash,
                )
                for lineage in lineages
            )
        )
        self.scene_ids = frozenset(lineage.scene_id for lineage in lineages)

    @property
    def q_h_horizon(self) -> int:
        return max(state.lineage.horizon for state in self.states)

    def __len__(self) -> int:
        return len(self.states)

    def __getitem__(self, index: int) -> QhRolloutState:
        return self.states[index]

    def read(self, locator: QhStateLocator) -> QhRolloutState:
        return self.states[locator.state_row]


class _SparseActorSource:
    def __init__(self) -> None:
        self.lookups: list[int] = []
        self.source_offline_store_version = "7"
        self.source_offline_store_manifest_hash = "source-hash"
        arrays = (
            ("vin.points_world", np.arange(12, dtype=np.float32).reshape(3, 4)),
            ("vin.lengths", np.asarray([3], dtype=np.int64)),
            ("vin.t_world_rig", np.arange(24, dtype=np.float32).reshape(2, 12)),
        )
        self.sample = VinActorSample(
            sample_index=41,
            sample_key="scene-a:snippet-a",
            scene_id="scene-a",
            snippet_id="snippet-a",
            split="train",
            source_shard_id="shard-sparse",
            source_shard_row=3,
            source_offline_store_version="7",
            source_offline_store_manifest_hash="source-hash",
            blocks=arrays,
            availability=tuple((name, True) for name, _ in arrays),
        )
        self.requested_blocks = tuple(name for name, _ in arrays)

    def index_for_sample(self, sample_index: int) -> int:
        self.lookups.append(sample_index)
        if sample_index != 41:
            raise KeyError(sample_index)
        return 0

    def validate_lineage(self, index: int, **expected: Any) -> None:
        assert index == 0
        assert expected["source_sample_index"] == 41
        assert expected["source_shard_row"] == 3
        assert expected["scene_id"] == "scene-a"

    def __getitem__(self, index: int) -> VinActorSample:
        assert index == 0
        return self.sample


def _dataset() -> tuple[QhDataset, _SparseActorSource]:
    source = _SparseActorSource()
    dataset = QhDataset(
        rollout_reader=_Reader(
            (
                _stored_state(0, width=2, terminal=False),
                _stored_state(1, width=3, terminal=True),
            )
        ),  # type: ignore[arg-type]
        actor_source=source,  # type: ignore[arg-type]
    )
    return dataset, source


def test_dataset_sparse_join_v0_ownership_and_exact_masks() -> None:
    dataset, source = _dataset()

    current = dataset[0]
    terminal = dataset[1]

    assert source.lookups == [41, 41, 41, 41]
    assert current.next_actor is not None
    assert current.transition.row_train_mask.item() is True
    assert terminal.next_actor is None
    assert terminal.transition.row_train_mask.item() is True
    assert current.current_actor.target_center_world.tolist() == [1.0, 2.0, 3.0]
    assert not hasattr(current.current_actor, "q_train_mask")
    assert not hasattr(current.current_actor, "invalid_reason_bitset")
    assert not hasattr(current.current_actor, "one_step_target_root_gain")


def test_dataset_rejects_gt_descriptor_laundered_as_v1() -> None:
    source = _SparseActorSource()
    dataset = QhDataset(
        rollout_reader=_Reader((_stored_state(0, width=2, terminal=True, protocol="v1_observed"),)),  # type: ignore[arg-type]
        actor_source=source,  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match="v1_observed cannot use the Oracle GT"):
        dataset[0]
    assert source.lookups == [41]


@pytest.mark.parametrize("failure", ["unknown", "available_without_payload"])
def test_dataset_rejects_actor_block_contract_injection(failure: str) -> None:
    source = _SparseActorSource()
    if failure == "unknown":
        source.sample = replace(
            source.sample,
            blocks=(*source.sample.blocks, ("oracle.label", np.asarray([9.0], dtype=np.float32))),
            availability=(*source.sample.availability, ("oracle.label", True)),
        )
        source.requested_blocks = (*source.requested_blocks, "oracle.label")
        match = "non-actor numeric blocks"
    else:
        source.sample = replace(
            source.sample,
            availability=(*source.sample.availability, ("vin.trajectory.time_ns", True)),
        )
        source.requested_blocks = (*source.requested_blocks, "vin.trajectory.time_ns")
        match = "availability=True"
    dataset = QhDataset(
        rollout_reader=_Reader((_stored_state(0, width=2, terminal=True),)),  # type: ignore[arg-type]
        actor_source=source,  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match=match):
        dataset[0]


def test_dto_fields_and_collate_padding_alignment_and_to() -> None:
    dataset, _ = _dataset()
    first, second = dataset[0], dataset[1]
    permutation = torch.tensor([1, 0])
    first = replace(
        first,
        current_actor=replace(
            first.current_actor,
            candidate_row_id=first.current_actor.candidate_row_id[permutation],
            candidate_pose_world_cam=first.current_actor.candidate_pose_world_cam[permutation],
            candidate_pose_relative_root=first.current_actor.candidate_pose_relative_root[permutation],
            candidate_position_id=first.current_actor.candidate_position_id[permutation],
            actor_action_mask=first.current_actor.actor_action_mask[permutation],
        ),
        supervision=replace(
            first.supervision,
            q_train_mask=first.supervision.q_train_mask[permutation],
        ),
        transition=replace(first.transition, selected_candidate_index=torch.tensor(0)),
    )
    batch = collate_qh_samples([first, second])
    singleton = collate_qh_samples([first])

    assert {field.name for field in fields(QhSample)} == {
        "current_actor",
        "next_actor",
        "supervision",
        "transition",
        "lineage",
    }
    assert {field.name for field in fields(QhSupervision)} == {"q_train_mask"}
    assert {field.name for field in fields(QhTransition)} == {
        "selected_candidate_index",
        "selected_candidate_row_id",
        "reward",
        "discount",
        "terminal",
        "row_train_mask",
    }
    assert batch.current_actor.candidate_row_id.tolist() == [[1, 0, -1], [10, 11, 12]]
    assert batch.current_actor.candidate_position_id.tolist() == [[201, 200, -1], [210, 211, 212]]
    assert batch.current_actor.candidate_pose_world_cam[0, 0, 0].item() == 1.0
    assert batch.supervision.q_train_mask.tolist() == [[True, True, False], [True, True, True]]
    assert batch.current_actor.actor_action_mask.tolist() == [[True, True, False], [True, True, True]]
    assert batch.current_actor.history_candidate_row_id.tolist() == [[-1], [100]]
    assert batch.current_actor.history_mask.tolist() == [[False], [True]]
    assert batch.next_actor_present.tolist() == [True, False]
    assert batch.next_actor is not None
    assert batch.next_actor.actor_action_mask.tolist() == [[True, True, True], [False, False, False]]
    assert singleton.current_actor.candidate_row_id.shape == (1, 2)
    assert batch.to("cpu").current_actor.candidate_row_id.device.type == "cpu"


def test_optional_actor_blocks_use_dtype_safe_unavailable_sentinels() -> None:
    dataset, _ = _dataset()
    present, absent = dataset[0], dataset[1]
    optional = (
        ("vin.trajectory.gravity_in_world", torch.tensor([1.0, 2.0, 3.0])),
        ("vin.trajectory.time_ns", torch.tensor([10, 20], dtype=torch.int64)),
        ("backbone.occ_input", torch.tensor([True, False])),
    )
    present = replace(
        present,
        current_actor=replace(
            present.current_actor,
            vin_blocks=(*present.current_actor.vin_blocks, *optional),
            vin_block_availability=(
                *present.current_actor.vin_block_availability,
                *((name, torch.tensor(True)) for name, _ in optional),
            ),
        ),
    )
    absent = replace(
        absent,
        current_actor=replace(
            absent.current_actor,
            vin_block_availability=(
                *absent.current_actor.vin_block_availability,
                *((name, torch.tensor(False)) for name, _ in optional),
            ),
        ),
    )

    blocks = dict(collate_qh_samples([present, absent]).current_actor.vin_blocks)

    assert torch.isnan(blocks["vin.trajectory.gravity_in_world"][1]).all()
    assert blocks["vin.trajectory.time_ns"][1].tolist() == [-1, -1]
    assert blocks["backbone.occ_input"][1].tolist() == [False, False]


class _StaticDataset(Dataset[QhSample]):
    def __init__(self, samples: tuple[QhSample, ...], scene: str) -> None:
        self.samples = samples
        self.scene_ids = frozenset({scene})
        self.q_h_horizon = max(sample.lineage.current.horizon for sample in samples)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> QhSample:
        return self.samples[index % len(self.samples)]


@pytest.mark.parametrize(("workers", "persistent"), [(0, False), (2, True)])
def test_datamodule_workers_and_persistence(workers: int, persistent: bool) -> None:
    dataset, _ = _dataset()
    stage = _StaticDataset((dataset[0], dataset[1]), "train-scene")
    module = QhDataModule(
        train=stage,
        batch_size=2,
        num_workers=workers,
        persistent_workers=persistent,
        seed=11,
    )

    loader = module.train_dataloader()
    batch = next(iter(loader))

    assert isinstance(batch, QhBatch)
    assert loader.persistent_workers is persistent
    assert loader.num_workers == workers


def test_datamodule_exposes_training_corpus_horizon_only_after_fit_setup() -> None:
    dataset, _ = _dataset()
    stage = _StaticDataset((dataset[0], dataset[1]), "train-scene")
    module = QhDataModule(train=stage)

    with pytest.raises(RuntimeError, match=r'setup\("fit"\)'):
        _ = module.training_horizon

    module.setup("fit")

    assert module.training_horizon == 2


def test_distributed_train_padding_and_replicated_exact_eval() -> None:
    dataset, _ = _dataset()
    samples = tuple(dataset[index % 2] for index in range(5))
    stage = _StaticDataset(samples, "scene-a")
    train_samplers = [
        DistributedSampler(stage, num_replicas=2, rank=rank, shuffle=True, seed=17, drop_last=False)
        for rank in range(2)
    ]
    first = [list(sampler) for sampler in train_samplers]
    second = [list(sampler) for sampler in train_samplers]

    assert first == second
    assert sum(map(len, first)) == 6
    assert len([index for indices in first for index in indices]) - len(stage) == 1

    module = QhDataModule(
        train=stage,
        val=_StaticDataset(samples, "scene-b"),
        batch_size=2,
        seed=17,
    )
    module._distributed_context = lambda: (2, 0)  # type: ignore[method-assign]
    loader = module.train_dataloader()
    assert list(module.val_dataloader().sampler) == list(range(len(stage)))
    reported: list[tuple[int, ...]] = []
    for epoch in range(3):
        assert isinstance(loader.sampler, DistributedSampler)
        loader.sampler.set_epoch(epoch)
        partitions = []
        for rank in range(2):
            sampler = DistributedSampler(stage, num_replicas=2, rank=rank, shuffle=True, seed=17, drop_last=False)
            sampler.set_epoch(epoch)
            partitions.append(list(sampler))
        counts: dict[int, int] = {}
        for indices in partitions:
            for index in indices:
                counts[index] = counts.get(index, 0) + 1
        expected_duplicates = tuple(index for index, count in sorted(counts.items()) for _ in range(count - 1))
        assert module.training_padding_rows == 1
        assert module.training_duplicated_dataset_indices == expected_duplicates
        reported.append(module.training_duplicated_dataset_indices)
    assert len(set(reported)) > 1


def test_attached_trainer_enforces_sampler_ownership() -> None:
    dataset, _ = _dataset()
    train = _StaticDataset((dataset[0],), "train-scene")
    val = _StaticDataset((dataset[1],), "val-scene")

    rejected = QhDataModule(train=train, val=val)
    rejected.trainer = pl.Trainer(
        accelerator="cpu",
        devices=1,
        logger=False,
        enable_checkpointing=False,
        enable_model_summary=False,
        use_distributed_sampler=True,
    )
    with pytest.raises(RuntimeError, match=r"TrainerFactoryConfig\(use_distributed_sampler=False\)"):
        rejected.setup()

    accepted = QhDataModule(train=train, val=val)
    accepted.trainer = pl.Trainer(
        accelerator="cpu",
        devices=1,
        logger=False,
        enable_checkpointing=False,
        enable_model_summary=False,
        use_distributed_sampler=False,
    )
    accepted.setup()

    assert isinstance(accepted.train_dataloader().sampler, DistributedSampler)
    assert isinstance(accepted.val_dataloader().sampler, SequentialSampler)


def test_validation_order_matches_multiworker_persistent_epoch_two() -> None:
    def collect(workers: int) -> list[list[int]]:
        dataset, _ = _dataset()
        train = _StaticDataset((dataset[0],), "train-scene")
        module = QhDataModule(
            train=train,
            val=dataset,
            batch_size=1,
            num_workers=workers,
            persistent_workers=workers > 0,
            seed=23,
        )
        loader = module.val_dataloader()
        assert loader is not None
        epochs = [[batch.lineage[0].current.step_index for batch in loader] for _epoch in range(2)]
        if workers > 0:
            assert loader.persistent_workers is True
        return epochs

    single_process = collect(0)
    multi_process = collect(2)

    assert single_process == [[0, 1], [0, 1]]
    assert multi_process == single_process


def test_datamodule_rejects_scene_overlap_and_module_stays_leaf_only() -> None:
    dataset, _ = _dataset()
    sample = dataset[1]
    train = _StaticDataset((sample,), "same-scene")
    val = _StaticDataset((sample,), "same-scene")

    with pytest.raises(ValueError, match="overlap scenes"):
        QhDataModule(train=train, val=val).setup()

    assert not hasattr(lightning_root, "QhDataset")
    assert "cuda" not in inspect.getsource(QhDataModule).lower()


def test_datamodule_scene_check_uses_compact_reader_metadata() -> None:
    source = _SparseActorSource()

    class MetadataOnlyReader(_Reader):
        def __getitem__(self, _index: int) -> QhRolloutState:
            pytest.fail("QhDataModule.setup materialized a rollout item")

    dataset = QhDataset(
        rollout_reader=MetadataOnlyReader((_stored_state(0, width=2, terminal=True),)),  # type: ignore[arg-type]
        actor_source=source,  # type: ignore[arg-type]
    )

    QhDataModule(train=dataset).setup("fit")

    assert dataset.scene_ids == frozenset({"scene-a"})
    assert source.lookups == [41]
