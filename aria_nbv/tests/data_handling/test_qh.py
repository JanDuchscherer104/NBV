"""Contracts for the framework-neutral finite-candidate Q_H data seam."""

# ruff: noqa: S101

from __future__ import annotations

import inspect
from dataclasses import fields, is_dataclass, replace
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
import torch
from efm3d.aria.pose import PoseTW
from torch.utils.data import Dataset, DistributedSampler

import aria_nbv.data_handling.qh as qh_data
from aria_nbv.data_handling.offline.actor import VinActorSample
from aria_nbv.data_handling.qh import (
    QhActorInputs,
    QhBatch,
    QhCorpus,
    QhDataset,
    QhDatasetConfig,
    QhSample,
    QhTransition,
    collate_qh_samples,
)
from aria_nbv.data_handling.raw.views import VinSnippetView
from aria_nbv.lightning.qh_datamodule import QhDataModule, QhDataModuleConfig
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
            candidate_position_id=np.arange(width, dtype=np.int32) % 6,
            actor_action_mask=np.asarray([True] * width),
            root_pose_world=np.asarray([1, 0, 0, 0, 1, 0, 0, 0, 1, 7, 8, 9], dtype=np.float32),
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
            history_position_id=np.arange(step, dtype=np.int32) % 6,
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
            snippet=VinSnippetView(
                points_world=torch.arange(12, dtype=torch.float32).reshape(3, 4),
                lengths=torch.tensor([3], dtype=torch.int64),
                t_world_rig=PoseTW(torch.arange(24, dtype=torch.float32).reshape(2, 12)),
            ),
        )

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


def test_dataset_config_factory_and_direct_injection_share_runtime_interface() -> None:
    """The config owns construction while the runtime accepts only adapters."""

    reader = _Reader((_stored_state(0, width=2, terminal=True),))
    source = _SparseActorSource()
    config = QhDatasetConfig.model_construct(
        rollout=SimpleNamespace(setup_target=lambda: reader),
        actor=SimpleNamespace(setup_target=lambda: source),
    )

    configured = config.setup_target()
    injected = QhDataset(rollout_reader=reader, actor_source=source)  # type: ignore[arg-type]

    assert type(configured) is type(injected) is QhDataset
    assert configured.rollout_reader is injected.rollout_reader is reader
    assert configured.actor_source is injected.actor_source is source
    parameters = inspect.signature(QhDataset).parameters
    assert tuple(parameters) == ("rollout_reader", "actor_source")
    assert all(parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in parameters.values())


def test_dataset_sparse_join_v0_ownership_and_exact_masks() -> None:
    dataset, source = _dataset()

    current = dataset[0]
    terminal = dataset[1]

    assert source.lookups == [41, 41, 41, 41]
    assert current.next_actor is not None
    assert current.transition.row_train_mask.item() is True
    assert terminal.next_actor is None
    assert terminal.transition.row_train_mask.item() is True
    assert not hasattr(current.current_actor, "target_center_world")
    assert current.current_actor.root_pose_world.tolist() == [
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        7.0,
        8.0,
        9.0,
    ]
    assert not hasattr(current.current_actor, "target_relative_pose_reference_object")
    assert not hasattr(current.current_actor, "q_train_mask")
    assert not hasattr(current.current_actor, "invalid_reason_bitset")
    assert not hasattr(current.current_actor, "one_step_target_root_gain")


def test_storage_target_center_does_not_cross_the_training_dto() -> None:
    state = _stored_state(0, width=2, terminal=True)
    perturbed = replace(
        state,
        actor=replace(state.actor, target_center_world=np.asarray([1e6, -1e6, 3e6], dtype=np.float32)),
    )
    source = _SparseActorSource()
    baseline = QhDataset(rollout_reader=_Reader((state,)), actor_source=source)[0].current_actor  # type: ignore[arg-type]
    changed = QhDataset(rollout_reader=_Reader((perturbed,)), actor_source=source)[0].current_actor  # type: ignore[arg-type]

    assert not hasattr(baseline, "target_center_world")
    assert not hasattr(changed, "target_center_world")
    assert torch.equal(changed.target_pose_world_object, baseline.target_pose_world_object)


def test_dataset_rejects_gt_descriptor_laundered_as_v1() -> None:
    source = _SparseActorSource()
    dataset = QhDataset(
        rollout_reader=_Reader((_stored_state(0, width=2, terminal=True, protocol="v1_observed"),)),  # type: ignore[arg-type]
        actor_source=source,  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match="v1_observed cannot use the Oracle GT"):
        dataset[0]
    assert source.lookups == [41]


def test_dto_fields_and_collate_padding_alignment_and_to() -> None:
    dataset, _ = _dataset()
    first, second = dataset[0], dataset[1]
    permutation = torch.tensor([1, 0])
    first = replace(
        first,
        current_actor=replace(
            first.current_actor,
            candidate_row_id=first.current_actor.candidate_row_id[permutation],
            candidate_pose_relative_root=first.current_actor.candidate_pose_relative_root[permutation],
            candidate_position_id=first.current_actor.candidate_position_id[permutation],
            actor_action_mask=first.current_actor.actor_action_mask[permutation],
        ),
        transition=replace(first.transition, selected_candidate_index=torch.tensor(0)),
    )
    batch = collate_qh_samples([first, second])
    singleton = collate_qh_samples([first])

    assert {field.name for field in fields(QhSample)} == {
        "current_actor",
        "next_actor",
        "transition",
        "lineage",
    }
    assert {field.name for field in fields(QhTransition)} == {
        "selected_candidate_index",
        "selected_candidate_row_id",
        "reward",
        "discount",
        "terminal",
        "row_train_mask",
    }
    actor_fields = {field.name for field in fields(QhActorInputs)}
    assert "candidate_pose_world_cam" not in actor_fields
    assert "history_pose_world_cam" not in actor_fields
    assert "candidate_pose_world_cam" in {field.name for field in fields(StoredActor)}
    assert "history_pose_world_cam" in {field.name for field in fields(StoredActor)}
    assert "target_center_world" not in actor_fields
    assert "target_center_world" in {field.name for field in fields(StoredActor)}
    assert batch.current_actor.candidate_row_id.tolist() == [[1, 0, -1], [10, 11, 12]]
    assert batch.current_actor.candidate_position_id.tolist() == [[1, 0, -1], [0, 1, 2]]
    assert batch.current_actor.candidate_pose_relative_root[0, 0, 0].item() == 1.5
    assert not hasattr(batch, "supervision")
    assert batch.current_actor.actor_action_mask.tolist() == [[True, True, False], [True, True, True]]
    assert batch.current_actor.history_candidate_row_id.tolist() == [[-1], [100]]
    assert batch.current_actor.history_mask.tolist() == [[False], [True]]
    assert batch.next_actor_present.tolist() == [True, False]
    assert batch.next_actor is not None
    assert batch.next_actor.actor_action_mask.tolist() == [[True, True, True], [False, False, False]]
    assert singleton.current_actor.candidate_row_id.shape == (1, 2)
    assert batch.to("cpu").current_actor.candidate_row_id.device.type == "cpu"


def test_batch_selected_rows_consistency_accepts_admitted_rows() -> None:
    dataset, _ = _dataset()

    collate_qh_samples([dataset[0], dataset[1]]).assert_selected_rows_consistent()


@pytest.mark.parametrize(
    ("corruption", "message"),
    [
        ("index", "out-of-range"),
        ("row_id", "row-id"),
        ("actor_mask", "mask"),
        ("reward", "reward"),
        ("discount", "discount"),
    ],
)
def test_batch_selected_rows_consistency_rejects_each_conjunct(corruption: str, message: str) -> None:
    dataset, _ = _dataset()
    batch = collate_qh_samples([dataset[0], dataset[1]])
    transition = batch.transition
    actor = batch.current_actor
    if corruption == "index":
        selected = transition.selected_candidate_index.clone()
        selected[0] = actor.candidate_row_id.shape[1]
        transition = replace(transition, selected_candidate_index=selected)
    elif corruption == "row_id":
        row_id = transition.selected_candidate_row_id.clone()
        row_id[0] += 1000
        transition = replace(transition, selected_candidate_row_id=row_id)
    elif corruption == "actor_mask":
        actor_mask = actor.actor_action_mask.clone()
        actor_mask[0, transition.selected_candidate_index[0]] = False
        actor = replace(actor, actor_action_mask=actor_mask)
    elif corruption == "reward":
        reward = transition.reward.clone()
        reward[0] = torch.nan
        transition = replace(transition, reward=reward)
    else:
        discount = transition.discount.clone()
        discount[0] = torch.inf
        transition = replace(transition, discount=discount)

    with pytest.raises(ValueError, match=message):
        replace(batch, current_actor=actor, transition=transition).assert_selected_rows_consistent()


def test_batch_exposes_the_selected_row_assertion_as_one_data_owned_method() -> None:
    parameters = inspect.signature(QhBatch.assert_selected_rows_consistent).parameters

    assert tuple(parameters) == ("self",)
    assert not hasattr(qh_data, "assert_selected_rows_consistent")


def test_batch_owns_recursive_pin_and_non_blocking_transfer(monkeypatch: pytest.MonkeyPatch) -> None:
    dataset, _ = _dataset()
    batch = collate_qh_samples([dataset[0], dataset[1]])
    expected_tensor_ids = _tensor_ids(batch) - _tensor_ids(batch.lineage)
    pinned: list[int] = []
    transferred: list[tuple[int, bool]] = []
    original_to = torch.Tensor.to

    def pin_memory(tensor: torch.Tensor) -> torch.Tensor:
        pinned.append(id(tensor))
        return tensor

    def to(tensor: torch.Tensor, *args: Any, **kwargs: Any) -> torch.Tensor:
        transferred.append((id(tensor), kwargs["non_blocking"]))
        return original_to(tensor, *args, **kwargs)

    monkeypatch.setattr(torch.Tensor, "pin_memory", pin_memory)
    monkeypatch.setattr(torch.Tensor, "to", to)

    pinned_batch = batch.pin_memory()
    moved_batch = batch.to("cpu", non_blocking=False)

    assert set(pinned) == expected_tensor_ids
    assert {tensor_id for tensor_id, _flag in transferred} == expected_tensor_ids
    assert {flag for _tensor_id, flag in transferred} == {False}
    assert pinned_batch.lineage is batch.lineage
    assert moved_batch.lineage is batch.lineage


def _tensor_ids(value: object) -> set[int]:
    if isinstance(value, torch.Tensor):
        return {id(value)}
    if isinstance(value, PoseTW):
        return {id(value.tensor())}
    if isinstance(value, tuple):
        return set().union(*(_tensor_ids(item) for item in value), set())
    if is_dataclass(value):
        return set().union(*(_tensor_ids(getattr(value, field.name)) for field in fields(value)), set())
    return set()


def test_typed_vin_snippets_pad_points_and_trajectory_independently() -> None:
    dataset, _ = _dataset()
    first, second = dataset[0], dataset[1]
    first = replace(
        first,
        current_actor=replace(
            first.current_actor,
            vin_snippet=VinSnippetView(
                points_world=first.current_actor.vin_snippet.points_world[:2],
                lengths=torch.tensor([2]),
                t_world_rig=PoseTW(first.current_actor.vin_snippet.t_world_rig.tensor()[:1]),
            ),
        ),
    )
    snippet = collate_qh_samples([first, second]).current_actor.vin_snippet

    assert snippet.points_world.shape == (2, 3, 4)
    assert torch.isnan(snippet.points_world[0, 2]).all()
    assert snippet.lengths.tolist() == [[2], [3]]
    assert snippet.t_world_rig.tensor().shape == (2, 2, 12)
    assert snippet.t_world_rig.tensor()[0, 1].eq(0).all()


class _StaticDataset(Dataset[QhSample]):
    def __init__(self, samples: tuple[QhSample, ...], scene: str) -> None:
        self.samples = samples
        self.scene_ids = frozenset({scene})
        self.q_h_horizon = max(sample.lineage.current.horizon for sample in samples)
        self.provenance = {"kind": "static-test", "scene": scene, "rows": len(samples)}

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> QhSample:
        return self.samples[index % len(self.samples)]


class _EmptyDataset(Dataset[QhSample]):
    scene_ids = frozenset({"empty-scene"})
    q_h_horizon = 2

    def __len__(self) -> int:
        return 0

    def __getitem__(self, index: int) -> QhSample:
        raise IndexError(index)


def _data_module(
    train: _StaticDataset | QhDataset,
    *,
    val: _StaticDataset | QhDataset | None = None,
    test: _StaticDataset | QhDataset | None = None,
    **kwargs: Any,
) -> QhDataModule:
    return QhDataModule(QhCorpus.admit(train=train, val=val, test=test), seed=kwargs.pop("seed", 0), **kwargs)


@pytest.mark.parametrize(("workers", "persistent"), [(0, False), (2, True)])
def test_datamodule_workers_and_persistence(workers: int, persistent: bool) -> None:
    dataset, _ = _dataset()
    stage = _StaticDataset((dataset[0], dataset[1]), "train-scene")
    module = _data_module(
        stage,
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


def test_datamodule_exposes_pre_admitted_training_corpus_horizon() -> None:
    dataset, _ = _dataset()
    stage = _StaticDataset((dataset[0], dataset[1]), "train-scene")
    module = _data_module(stage)

    assert module.training_horizon == 2


@pytest.mark.parametrize("stage_name", ["val", "test"])
def test_corpus_requires_admission_and_rejects_empty_configured_stage(stage_name: str) -> None:
    dataset, _ = _dataset()
    train = _StaticDataset((dataset[0],), "train-scene")

    with pytest.raises(TypeError, match="QhCorpus.admit"):
        QhCorpus(train=train)  # type: ignore[call-arg]
    with pytest.raises(ValueError, match=f"configured corpus stages.*{stage_name}"):
        QhCorpus.admit(train=train, **{stage_name: _EmptyDataset()})  # type: ignore[arg-type]


def test_corpus_rejects_mismatched_stage_horizons_and_training_supervision_dto_is_absent() -> None:
    dataset, _ = _dataset()
    train = _StaticDataset((dataset[0],), "train-scene")
    val = _StaticDataset((dataset[0],), "val-scene")
    val.q_h_horizon = 3

    with pytest.raises(ValueError, match="stage horizons disagree"):
        QhCorpus.admit(train=train, val=val)

    assert not hasattr(qh_data, "QhSupervision")


def test_datamodule_config_constructs_every_stage_before_admission(monkeypatch: pytest.MonkeyPatch) -> None:
    dataset, _ = _dataset()
    configs = tuple(QhDatasetConfig.model_construct() for _ in range(3))
    stages = (
        _StaticDataset((dataset[0],), "train-scene"),
        _StaticDataset((dataset[0],), "val-scene"),
        _StaticDataset((dataset[0],), "test-scene"),
    )
    by_config = dict(zip(map(id, configs), stages, strict=True))
    constructed: list[int] = []

    def setup_target(config: QhDatasetConfig) -> _StaticDataset:
        constructed.append(id(config))
        return by_config[id(config)]

    monkeypatch.setattr(QhDatasetConfig, "setup_target", setup_target)
    module = QhDataModuleConfig(train=configs[0], val=configs[1], test=configs[2]).setup_target(seed=31)

    assert constructed == list(map(id, configs))
    assert module.corpus.train is stages[0]
    assert module.corpus.val is stages[1]
    assert module.corpus.test is stages[2]
    assert module.seed == 31


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

    module = _data_module(
        stage,
        val=_StaticDataset(samples, "scene-b"),
        batch_size=2,
        seed=17,
    )
    module._distributed_context = lambda: (2, 0)  # type: ignore[method-assign]
    prepared = module.prepare_training_sampler(num_replicas=2, rank=0)
    assert module.training_padding_rows == 1
    assert module.training_padding_fraction == pytest.approx(1 / 6)
    loader = module.train_dataloader()
    assert loader.sampler is prepared
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


def test_prepare_training_sampler_computes_padding_without_materializing_rows() -> None:
    class _MetadataOnlyDataset(Dataset[QhSample]):
        scene_ids = frozenset({"metadata-only"})
        q_h_horizon = 2
        provenance = {"kind": "metadata-only"}

        def __len__(self) -> int:
            return 5

        def __getitem__(self, index: int) -> QhSample:
            pytest.fail(f"sampler preparation materialized row {index}")

    module = QhDataModule(QhCorpus.admit(train=_MetadataOnlyDataset()), seed=17)

    sampler = module.prepare_training_sampler(num_replicas=2, rank=0)

    assert sampler.num_samples == 3
    assert module.training_padding_rows == 1
    assert module.training_padding_fraction == pytest.approx(1 / 6)


def test_validation_order_matches_multiworker_persistent_epoch_two() -> None:
    def collect(workers: int) -> list[list[int]]:
        dataset, _ = _dataset()
        train = _StaticDataset((dataset[0],), "train-scene")
        module = _data_module(
            train,
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


def test_corpus_rejects_scene_overlap_and_datamodule_stays_loader_only() -> None:
    dataset, _ = _dataset()
    sample = dataset[1]
    train = _StaticDataset((sample,), "same-scene")
    val = _StaticDataset((sample,), "same-scene")

    with pytest.raises(ValueError, match="overlap scenes"):
        QhCorpus.admit(train=train, val=val)

    assert "cuda" not in inspect.getsource(QhDataModule).lower()


def test_datamodule_scene_check_uses_compact_reader_metadata() -> None:
    source = _SparseActorSource()

    class MetadataOnlyReader(_Reader):
        def __getitem__(self, _index: int) -> QhRolloutState:
            pytest.fail("QhCorpus.admit materialized a rollout item")

    dataset = QhDataset(
        rollout_reader=MetadataOnlyReader((_stored_state(0, width=2, terminal=True),)),  # type: ignore[arg-type]
        actor_source=source,  # type: ignore[arg-type]
    )

    QhCorpus.admit(train=dataset)

    assert dataset.scene_ids == frozenset({"scene-a"})
    assert source.lookups == [41]
