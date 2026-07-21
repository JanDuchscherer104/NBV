"""Typed actor-only data seam for finite-candidate ``Q_H`` training.

The module composes one lazy rollout state with one immutable VIN actor row.
It owns protocol-aware descriptor selection, exact lineage validation, tensor
conversion, deterministic padding, and distributed loader semantics. Rollout
storage interpretation remains in :mod:`aria_nbv.rollouts.qh_reader`; VIN
source projection remains in :mod:`aria_nbv.data_handling.offline.actor`.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Sized
from dataclasses import dataclass, replace
from functools import cached_property
from typing import TypeAlias

import numpy as np
import pytorch_lightning as pl
import torch
from torch import Tensor
from torch.utils.data import DataLoader, Dataset, DistributedSampler, Sampler, SequentialSampler

from ..data_handling.offline.actor import (
    ACTOR_VISIBLE_NUMERIC_BLOCKS,
    VinActorSample,
    VinActorSource,
    VinActorSourceConfig,
)
from ..rollouts import qh_reader as rollout_qh
from ..targets.protocol import TargetDescriptorProvenance, TargetInputProtocol, validate_target_protocol_admission
from ..utils import TargetConfig


@dataclass(frozen=True, slots=True)
class QhActorInputs:
    """Actor-visible tensors for one state or a padded batch of states.

    Candidate and history axes are compact for a sample and right-padded for a
    batch. Only `actor_action_mask` and `history_mask` define usable rows;
    padded ids are ``-1``. No Oracle label, invalid reason, selection
    diagnostic, or selected-depth raster crosses this interface.
    """

    vin_blocks: tuple[tuple[str, Tensor], ...]
    """Named VIN actor tensors in deterministic source-profile order.

    Core batched blocks are ``vin.points_world``
    ``Tensor["B P C_p", float32]`` in world metres, ``vin.lengths``
    ``Tensor["B 1", int64]``, and ``vin.t_world_rig``
    ``Tensor["B T 12", float32]`` world-from-rig poses. Optional block shapes
    follow their immutable VIN store schema.
    """

    vin_block_availability: tuple[tuple[str, Tensor], ...]
    """Named ``Tensor["", bool]`` or ``Tensor["B", bool]`` block-presence flags."""

    target_center_world: Tensor
    """``Tensor["3", float32]`` or ``Tensor["B 3", float32]`` V0 center in world metres."""

    target_extents: Tensor
    """``Tensor["3", float32]`` or ``Tensor["B 3", float32]`` V0 OBB extents in metres."""

    target_pose_world_object: Tensor
    """``Tensor["12", float32]`` or ``Tensor["B 12", float32]`` V0 object pose in world frame."""

    target_relative_pose_reference_object: Tensor
    """``Tensor["12", float32]`` or ``Tensor["B 12", float32]`` V0 target pose relative to root."""

    target_sem_id: Tensor
    """Scalar or ``Tensor["B", int64]`` semantic target ids."""

    target_inst_id: Tensor
    """Scalar or ``Tensor["B", int64]`` instance target ids."""

    candidate_row_id: Tensor
    """``Tensor["N_q", int64]`` or ``Tensor["B N_q", int64]`` stable ids; padding is ``-1``."""

    candidate_pose_world_cam: Tensor
    """``Tensor["N_q 12", float32]`` or ``Tensor["B N_q 12", float32]`` world-from-camera poses."""

    candidate_pose_relative_root: Tensor
    """``Tensor["N_q 12", float32]`` or ``Tensor["B N_q 12", float32]`` root-from-camera poses."""

    candidate_position_id: Tensor
    """``Tensor["N_q", int64]`` or ``Tensor["B N_q", int64]`` position-family ids; padding is ``-1``."""

    actor_action_mask: Tensor
    """``Tensor["N_q", bool]`` or ``Tensor["B N_q", bool]`` hard action mask; padding is false."""

    history_candidate_row_id: Tensor
    """``Tensor["H_t", int64]`` or ``Tensor["B H_t", int64]`` prior candidate ids; padding is ``-1``."""

    history_pose_world_cam: Tensor
    """``Tensor["H_t 12", float32]`` or ``Tensor["B H_t 12", float32]`` prior world-from-camera poses."""

    history_pose_relative_root: Tensor
    """``Tensor["H_t 12", float32]`` or ``Tensor["B H_t 12", float32]`` prior root-from-camera poses."""

    history_position_id: Tensor
    """``Tensor["H_t", int64]`` or ``Tensor["B H_t", int64]`` prior position-family ids; padding is ``-1``."""

    history_mask: Tensor
    """``Tensor["H_t", bool]`` or ``Tensor["B H_t", bool]`` history-presence mask; padding is false."""

    remaining_budget: Tensor
    """``Tensor["", int64]`` or ``Tensor["B", int64]`` remaining acquisition count."""

    def to(self, device: str | torch.device) -> QhActorInputs:
        """Return the same actor view with every tensor moved to `device`."""

        return replace(
            self,
            vin_blocks=tuple((name, value.to(device)) for name, value in self.vin_blocks),
            vin_block_availability=tuple((name, value.to(device)) for name, value in self.vin_block_availability),
            target_center_world=self.target_center_world.to(device),
            target_extents=self.target_extents.to(device),
            target_pose_world_object=self.target_pose_world_object.to(device),
            target_relative_pose_reference_object=self.target_relative_pose_reference_object.to(device),
            target_sem_id=self.target_sem_id.to(device),
            target_inst_id=self.target_inst_id.to(device),
            candidate_row_id=self.candidate_row_id.to(device),
            candidate_pose_world_cam=self.candidate_pose_world_cam.to(device),
            candidate_pose_relative_root=self.candidate_pose_relative_root.to(device),
            candidate_position_id=self.candidate_position_id.to(device),
            actor_action_mask=self.actor_action_mask.to(device),
            history_candidate_row_id=self.history_candidate_row_id.to(device),
            history_pose_world_cam=self.history_pose_world_cam.to(device),
            history_pose_relative_root=self.history_pose_relative_root.to(device),
            history_position_id=self.history_position_id.to(device),
            history_mask=self.history_mask.to(device),
            remaining_budget=self.remaining_budget.to(device),
        )


@dataclass(frozen=True, slots=True)
class QhSupervision:
    """Candidate-aligned hard training admission kept outside actor inputs."""

    q_train_mask: Tensor
    """``Tensor["N_q", bool]`` or ``Tensor["B N_q", bool]`` hard training mask; padding is false."""

    def to(self, device: str | torch.device) -> QhSupervision:
        """Move all supervision tensors to `device`."""

        return replace(
            self,
            q_train_mask=self.q_train_mask.to(device),
        )


@dataclass(frozen=True, slots=True)
class QhTransition:
    """Selected-transition tensors and the exact row-level training gate."""

    selected_candidate_index: Tensor
    """``Tensor["", int64]`` or ``Tensor["B", int64]`` selected full-shell indices."""

    selected_candidate_row_id: Tensor
    """``Tensor["", int64]`` or ``Tensor["B", int64]`` selected stable candidate ids."""

    reward: Tensor
    """``Tensor["", float32]`` or ``Tensor["B", float32]`` selected target-root-gain rewards."""

    discount: Tensor
    """``Tensor["", float32]`` or ``Tensor["B", float32]`` gamma-or-zero TD discounts."""

    terminal: Tensor
    """``Tensor["", bool]`` or ``Tensor["B", bool]`` terminal flags."""

    row_train_mask: Tensor
    """``Tensor["", bool]`` or ``Tensor["B", bool]`` exact fitted-Q admission gate."""

    def to(self, device: str | torch.device) -> QhTransition:
        """Move all selected-transition tensors to `device`."""

        return replace(
            self,
            selected_candidate_index=self.selected_candidate_index.to(device),
            selected_candidate_row_id=self.selected_candidate_row_id.to(device),
            reward=self.reward.to(device),
            discount=self.discount.to(device),
            terminal=self.terminal.to(device),
            row_train_mask=self.row_train_mask.to(device),
        )


@dataclass(frozen=True, slots=True)
class QhLineage:
    """Audit-only current and optional next rollout provenance."""

    current: rollout_qh.QhLineage
    """Exact persisted lineage for the current rollout state."""

    next: rollout_qh.QhLineage | None
    """Exact persisted lineage for the admitted successor, when present."""


@dataclass(frozen=True, slots=True)
class QhSample:
    """One transition-complete, actor-safe finite-candidate training sample."""

    current_actor: QhActorInputs
    """Current model input view."""

    next_actor: QhActorInputs | None
    """Admitted successor model input, absent exactly for terminal rows."""

    supervision: QhSupervision
    """Current candidate-aligned labels and masks."""

    transition: QhTransition
    """Selected transition and row-level training gate."""

    lineage: QhLineage
    """Audit provenance excluded from model calls."""


@dataclass(frozen=True, slots=True)
class QhBatch:
    """Padded transition batch with explicit mixed-terminal presence masks."""

    current_actor: QhActorInputs
    """Padded current actor views."""

    next_actor: QhActorInputs | None
    """Padded successor actor views, absent only when the whole batch is terminal."""

    next_actor_present: Tensor
    """``Tensor["B", bool]`` identifying rows represented in `next_actor`."""

    supervision: QhSupervision
    """Padded current supervision."""

    transition: QhTransition
    """Batched selected-transition facts and row masks."""

    lineage: tuple[QhLineage, ...]
    """Per-row audit provenance, never passed to the model."""

    def to(self, device: str | torch.device) -> QhBatch:
        """Return a device-moved batch while retaining CPU audit lineage."""

        return replace(
            self,
            current_actor=self.current_actor.to(device),
            next_actor=None if self.next_actor is None else self.next_actor.to(device),
            next_actor_present=self.next_actor_present.to(device),
            supervision=self.supervision.to(device),
            transition=self.transition.to(device),
        )


class QhDatasetConfig(TargetConfig["QhDataset"]):
    """Configure the lazy rollout reader and immutable VIN actor source."""

    rollout: rollout_qh.QhRolloutReaderConfig
    """Homogeneous V0 rollout corpus configuration."""

    actor: VinActorSourceConfig
    """Actor-only immutable VIN source configuration."""

    @property
    def target_type(self) -> type[QhDataset]:
        """Runtime dataset constructed by :meth:`setup_target`."""

        return QhDataset


class QhDataset(Dataset[QhSample]):
    """Join rollout transitions and immutable actor evidence by exact lineage.

    :class:`aria_nbv.rollouts.qh_reader.QhRolloutReader` supplies current and
    successor rollout facts; :class:`aria_nbv.data_handling.offline.actor.VinActorSource`
    supplies actor-visible observation blocks. Construction validates every
    compact source join before :meth:`__getitem__` can materialize a sample.
    Oracle diagnostics stay outside :class:`QhActorInputs`; only the minimal
    :class:`QhSupervision.q_train_mask` crosses the training seam.
    """

    def __init__(
        self,
        config: QhDatasetConfig | None = None,
        *,
        rollout_reader: rollout_qh.QhRolloutReader | None = None,
        actor_source: VinActorSource | None = None,
    ) -> None:
        """Construct from a config or explicit adapters for focused tests.

        Exactly one construction form must be used. Dependencies are accepted
        rather than created when explicit adapters are supplied, keeping the
        dataset interface directly testable.
        """

        if config is not None:
            if rollout_reader is not None or actor_source is not None:
                raise ValueError("QhDataset accepts either config or explicit adapters, not both.")
            rollout_reader = config.rollout.setup_target()
            actor_source = config.actor.setup_target()
        if rollout_reader is None or actor_source is None:
            raise ValueError("QhDataset requires both a rollout reader and VIN actor source.")
        self.rollout_reader = rollout_reader
        self.actor_source = actor_source
        self._validate_source_lineage()

    def __len__(self) -> int:
        """Return the validated rollout-state count."""

        return len(self.rollout_reader)

    def __getitem__(self, index: int) -> QhSample:
        """Join one selected transition and optional successor to actor evidence.

        The returned :class:`QhSample` preserves exact candidate-row alignment.
        ``row_train_mask`` is true only when the selected index is in range,
        its candidate is admitted by ``q_train_mask``, and reward/discount are
        finite.
        """

        current = self.rollout_reader[index]
        current_actor = self._compose_actor(current)
        next_state = None
        next_actor = None
        if current.transition.next_state is not None:
            next_state = self.rollout_reader.read(current.transition.next_state)
            self._validate_transition_link(current, next_state)
            next_actor = self._compose_actor(next_state)

        selected = current.transition.selected_candidate_index
        selected_index_valid = 0 <= selected < current.supervision.q_train_mask.shape[0]
        row_train = bool(
            selected_index_valid
            and current.supervision.q_train_mask[selected]
            and np.isfinite(current.transition.reward)
            and np.isfinite(current.transition.discount)
        )
        return QhSample(
            current_actor=current_actor,
            next_actor=next_actor,
            supervision=_tensor_supervision(current),
            transition=QhTransition(
                selected_candidate_index=torch.tensor(selected, dtype=torch.int64),
                selected_candidate_row_id=torch.tensor(
                    current.transition.selected_candidate_row_id,
                    dtype=torch.int64,
                ),
                reward=torch.tensor(current.transition.reward, dtype=torch.float32),
                discount=torch.tensor(current.transition.discount, dtype=torch.float32),
                terminal=torch.tensor(current.transition.terminal, dtype=torch.bool),
                row_train_mask=torch.tensor(row_train, dtype=torch.bool),
            ),
            lineage=QhLineage(current=current.lineage, next=None if next_state is None else next_state.lineage),
        )

    @cached_property
    def scene_ids(self) -> frozenset[str]:
        """Return scene ids for split-disjointness checks before loader creation."""

        return self.rollout_reader.scene_ids

    @property
    def q_h_horizon(self) -> int:
        """Return :attr:`QhRolloutReader.q_h_horizon` without reading samples."""

        return self.rollout_reader.q_h_horizon

    def _validate_source_lineage(self) -> None:
        """Validate every compact rollout/source join before any batch can load."""

        for lineage in self.rollout_reader.source_lineage:
            self._actor_source_index(lineage)

    def _compose_actor(self, state: rollout_qh.QhRolloutState) -> QhActorInputs:
        lineage = state.lineage
        protocol = validate_target_protocol_admission(
            lineage.target_protocol_version,
            target_source=lineage.target_source,
            descriptor_source=lineage.target_source,
            descriptor_provenance=TargetDescriptorProvenance.ORACLE_GT,
        )
        if protocol is not TargetInputProtocol.V0_GT_INPUT:
            raise ValueError("QhDataset currently materializes only v0_gt_input target descriptors.")

        source_index = self._actor_source_index(lineage)
        return _tensor_actor(
            self.actor_source[source_index],
            state.actor,
            requested_blocks=self.actor_source.requested_blocks,
        )

    def _actor_source_index(self, lineage: rollout_qh.QhLineage | rollout_qh.QhSourceLineage) -> int:
        """Resolve and validate one compact rollout-to-source join."""

        source_index = self.actor_source.index_for_sample(lineage.source_sample_index)
        self.actor_source.validate_lineage(
            source_index,
            source_sample_index=lineage.source_sample_index,
            source_sample_key=lineage.source_sample_key,
            source_shard_id=lineage.source_shard_id,
            source_shard_row=lineage.source_shard_row,
            source_offline_store_version=lineage.source_cache_version,
            source_offline_store_manifest_hash=lineage.source_offline_store_manifest_hash,
            scene_id=lineage.scene_id,
            snippet_id=lineage.snippet_id,
            split=lineage.split,
        )
        return source_index

    @staticmethod
    def _validate_transition_link(
        current: rollout_qh.QhRolloutState,
        next_state: rollout_qh.QhRolloutState,
    ) -> None:
        expected = current.transition.next_state
        if expected != next_state.locator:
            raise ValueError("Q_H successor locator changed during dataset composition.")
        if (
            next_state.lineage.rollout_row_id != current.lineage.rollout_row_id
            or next_state.lineage.step_index != current.lineage.step_index + 1
            or next_state.lineage.source_sample_index != current.lineage.source_sample_index
        ):
            raise ValueError("Q_H successor crosses rollout, step, or source lineage.")


def collate_qh_samples(samples: list[QhSample]) -> QhBatch:
    """Collate transition samples with deterministic right padding.

    Candidate and history ids use ``-1`` sentinels, pose/features use zeros,
    and all associated masks use false. Mixed terminal batches receive an
    empty padded successor row plus ``next_actor_present=False``; an all-terminal
    batch keeps ``next_actor=None``. This is the ``collate_fn`` used by
    :class:`QhDataModule` and PyTorch's
    [DataLoader](https://docs.pytorch.org/docs/stable/data.html#torch.utils.data.DataLoader).

    Args:
        samples: Non-empty list of transition-complete :class:`QhSample` rows.

    Returns:
        :class:`QhBatch` with batch axis ``B=len(samples)`` and independently
        padded current/successor candidate and history axes.
    """

    if not samples:
        raise ValueError("Cannot collate an empty Q_H sample list.")
    current_actor = _collate_actor([sample.current_actor for sample in samples])
    next_present = torch.tensor([sample.next_actor is not None for sample in samples], dtype=torch.bool)
    next_actor = None
    if bool(next_present.any()):
        exemplar = next(sample.next_actor for sample in samples if sample.next_actor is not None)
        assert exemplar is not None
        next_actor = _collate_actor(
            [sample.next_actor if sample.next_actor is not None else _empty_actor_like(exemplar) for sample in samples]
        )

    supervision = QhSupervision(
        q_train_mask=_pad_first_axis([sample.supervision.q_train_mask for sample in samples], False),
    )
    transition = QhTransition(
        selected_candidate_index=torch.stack([sample.transition.selected_candidate_index for sample in samples]),
        selected_candidate_row_id=torch.stack([sample.transition.selected_candidate_row_id for sample in samples]),
        reward=torch.stack([sample.transition.reward for sample in samples]),
        discount=torch.stack([sample.transition.discount for sample in samples]),
        terminal=torch.stack([sample.transition.terminal for sample in samples]),
        row_train_mask=torch.stack([sample.transition.row_train_mask for sample in samples]),
    )
    return QhBatch(
        current_actor=current_actor,
        next_actor=next_actor,
        next_actor_present=next_present,
        supervision=supervision,
        transition=transition,
        lineage=tuple(sample.lineage for sample in samples),
    )


class _AccountedDistributedSampler(DistributedSampler):
    """Expose exact global padding duplicates for the sampler's current epoch."""

    @property
    def padding_rows(self) -> int:
        """Return the number of extra rows added across all rank partitions."""

        return self.total_size - len(self.dataset)

    @property
    def duplicated_dataset_indices(self) -> tuple[int, ...]:
        """Return each extra padded dataset index for the current epoch."""

        partitions = _distributed_training_partitions(
            self.dataset,
            num_replicas=self.num_replicas,
            seed=self.seed,
            epoch=self.epoch,
        )
        counts = Counter(index for partition in partitions for index in partition)
        duplicates = tuple(index for index, count in sorted(counts.items()) for _ in range(count - 1))
        if len(duplicates) != self.padding_rows:
            raise RuntimeError("DistributedSampler padding accounting diverged from its global rank partitions.")
        return duplicates


QhDatasetLike: TypeAlias = Dataset[QhSample] | QhDatasetConfig
"""Accepted explicit dataset or config input for one data-module stage."""


class QhDataModuleConfig(TargetConfig["QhDataModule"]):
    """Configure explicit Q_H stage datasets and deterministic loader policy."""

    train: QhDatasetConfig
    """Training corpus config."""

    val: QhDatasetConfig | None = None
    """Optional scene-disjoint validation corpus config."""

    test: QhDatasetConfig | None = None
    """Optional scene-disjoint test corpus config."""

    batch_size: int = 1
    """Positive state rows per batch."""

    num_workers: int = 0
    """CPU DataLoader worker count; workers never move tensors to CUDA."""

    pin_memory: bool = False
    """Pin collated CPU tensors for asynchronous accelerator transfer."""

    persistent_workers: bool = False
    """Keep workers alive between epochs; ignored when `num_workers` is zero."""

    seed: int = 0
    """Sampler, generator, and worker seed."""

    @property
    def target_type(self) -> type[QhDataModule]:
        """Runtime data module constructed by :meth:`setup_target`."""

        return QhDataModule


class QhDataModule(pl.LightningDataModule):
    """Own scene-disjoint datasets and distributed sampling for fitted ``Q_H``.

    Training uses a seeded PyTorch
    [DistributedSampler](https://docs.pytorch.org/docs/stable/data.html#torch.utils.data.distributed.DistributedSampler)
    with
    explicit duplicate accounting. Validation and test use replicated
    sequential loaders so :class:`QhLightningModule` can compute exact local
    sums without per-batch collectives. Lightning sampler replacement must be
    disabled, as required by :class:`QhExperimentConfig`; see the official
    [LightningDataModule lifecycle](https://lightning.ai/docs/pytorch/stable/data/datamodule.html).
    """

    def __init__(
        self,
        config: QhDataModuleConfig | None = None,
        *,
        train: QhDatasetLike | None = None,
        val: QhDatasetLike | None = None,
        test: QhDatasetLike | None = None,
        batch_size: int = 1,
        num_workers: int = 0,
        pin_memory: bool = False,
        persistent_workers: bool = False,
        seed: int = 0,
    ) -> None:
        """Accept one config or explicit per-stage configs/datasets.

        Explicit datasets provide a focused test seam. Config inputs are
        materialized lazily by :meth:`setup`, before worker processes open
        their own Zarr readers.
        """

        super().__init__()
        if config is not None:
            if train is not None or val is not None or test is not None:
                raise ValueError("QhDataModule accepts either config or explicit stage inputs, not both.")
            train, val, test = config.train, config.val, config.test
            batch_size = config.batch_size
            num_workers = config.num_workers
            pin_memory = config.pin_memory
            persistent_workers = config.persistent_workers
            seed = config.seed
        if train is None:
            raise ValueError("QhDataModule requires an explicit training dataset or config.")
        if batch_size < 1 or num_workers < 0:
            raise ValueError("batch_size must be positive and num_workers non-negative.")
        self._stage_inputs = {"train": train, "val": val, "test": test}
        self._datasets: dict[str, Dataset[QhSample]] = {}
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.pin_memory = pin_memory
        self.persistent_workers = persistent_workers and num_workers > 0
        self.seed = seed
        self._train_sampler: _AccountedDistributedSampler | None = None

    @property
    def training_padding_rows(self) -> int:
        """Return the current training sampler's global padding-row count."""

        return 0 if self._train_sampler is None else self._train_sampler.padding_rows

    @property
    def training_duplicated_dataset_indices(self) -> tuple[int, ...]:
        """Return exact duplicated row ids for the training sampler's current epoch."""

        return () if self._train_sampler is None else self._train_sampler.duplicated_dataset_indices

    @property
    def training_horizon(self) -> int:
        """Return the admitted training corpus maximum after :meth:`setup`.

        The training dataset must expose the narrow read-only
        :attr:`QhDataset.q_h_horizon` contract. Configured datasets gain that
        contract when ``setup("fit")`` materializes them; explicit test
        datasets may implement the same attribute directly.
        """

        dataset = self._datasets.get("train")
        if dataset is None:
            raise RuntimeError('Q_H training horizon is available only after setup("fit").')
        horizon = getattr(dataset, "q_h_horizon", None)
        if not isinstance(horizon, int) or isinstance(horizon, bool) or horizon < 1:
            raise TypeError("Q_H training dataset must expose a positive integer q_h_horizon.")
        return horizon

    def setup(self, stage: str | None = None) -> None:
        """Materialize the requested stages and enforce scene-disjoint splits.

        Args:
            stage: Lightning stage name (``"fit"``, ``"validate"``,
                ``"test"``, or ``None`` for every configured stage).
        """

        self._assert_sampler_policy()
        requested = _requested_stages(stage)
        for name in requested:
            source = self._stage_inputs[name]
            if source is not None and name not in self._datasets:
                self._datasets[name] = source.setup_target() if isinstance(source, QhDatasetConfig) else source
        self._assert_scene_disjoint()

    def train_dataloader(self) -> DataLoader[QhBatch]:
        """Build the seeded distributed training loader.

        The sampler pads global rank partitions instead of dropping rows;
        :attr:`training_padding_rows` and
        :attr:`training_duplicated_dataset_indices` expose those duplicates.
        """

        self.setup("fit")
        dataset = self._datasets["train"]
        replicas, rank = self._distributed_context()
        sampler = _AccountedDistributedSampler(
            dataset,
            num_replicas=replicas,
            rank=rank,
            shuffle=True,
            seed=self.seed,
            drop_last=False,
        )
        self._train_sampler = sampler
        return self._loader(dataset, sampler=sampler)

    def val_dataloader(self) -> DataLoader[QhBatch] | list[DataLoader[QhBatch]]:
        """Build a replicated exact validation loader for DDP-safe evaluation."""

        self.setup("validate")
        loader = self._eval_loader("val")
        return [] if loader is None else loader

    def test_dataloader(self) -> DataLoader[QhBatch] | list[DataLoader[QhBatch]]:
        """Build a replicated exact test loader for DDP-safe evaluation."""

        self.setup("test")
        loader = self._eval_loader("test")
        return [] if loader is None else loader

    def _eval_loader(self, stage: str) -> DataLoader[QhBatch] | None:
        dataset = self._datasets.get(stage)
        if dataset is None:
            return None
        return self._loader(dataset, sampler=SequentialSampler(dataset))

    def _loader(self, dataset: Dataset[QhSample], *, sampler: Sampler[int]) -> DataLoader[QhBatch]:
        generator = torch.Generator().manual_seed(self.seed)
        return DataLoader(
            dataset,
            batch_size=self.batch_size,
            sampler=sampler,
            num_workers=self.num_workers,
            pin_memory=self.pin_memory,
            persistent_workers=self.persistent_workers,
            collate_fn=collate_qh_samples,
            worker_init_fn=_seed_worker,
            generator=generator,
        )

    def _distributed_context(self) -> tuple[int, int]:
        trainer = getattr(self, "trainer", None)
        if trainer is not None:
            return int(trainer.world_size), int(trainer.global_rank)
        if torch.distributed.is_available() and torch.distributed.is_initialized():
            return torch.distributed.get_world_size(), torch.distributed.get_rank()
        return 1, 0

    def _assert_sampler_policy(self) -> None:
        trainer = getattr(self, "trainer", None)
        if trainer is None:
            return
        connector = getattr(trainer, "_accelerator_connector", None)
        if connector is None or connector.use_distributed_sampler is not False:
            raise RuntimeError(
                "QhDataModule owns padded training and replicated exact-eval loaders. Construct the Trainer with "
                "TrainerFactoryConfig(use_distributed_sampler=False)."
            )

    def _assert_scene_disjoint(self) -> None:
        scenes = {name: _dataset_scene_ids(dataset) for name, dataset in self._datasets.items()}
        names = tuple(scenes)
        for index, left in enumerate(names):
            for right in names[index + 1 :]:
                overlap = scenes[left] & scenes[right]
                if overlap:
                    raise ValueError(
                        f"Q_H {left}/{right} datasets overlap scenes {sorted(overlap)}; use scene-level splits."
                    )


def _tensor_actor(
    source: VinActorSample,
    state: rollout_qh.QhActorState,
    *,
    requested_blocks: tuple[str, ...],
) -> QhActorInputs:
    _validate_actor_sample(source, requested_blocks=requested_blocks)
    blocks = tuple((name, _from_numpy(value)) for name, value in source.blocks)
    availability = tuple((name, torch.tensor(present, dtype=torch.bool)) for name, present in source.availability)
    history_count = int(state.history_candidate_row_id.shape[0])
    return QhActorInputs(
        vin_blocks=blocks,
        vin_block_availability=availability,
        target_center_world=_from_numpy(state.target_center_world, torch.float32),
        target_extents=_from_numpy(state.target_extents, torch.float32),
        target_pose_world_object=_from_numpy(state.target_pose_world_object, torch.float32),
        target_relative_pose_reference_object=_from_numpy(
            state.target_relative_pose_reference_object,
            torch.float32,
        ),
        target_sem_id=torch.tensor(state.target_sem_id, dtype=torch.int64),
        target_inst_id=torch.tensor(state.target_inst_id, dtype=torch.int64),
        candidate_row_id=_from_numpy(state.candidate_row_id, torch.int64),
        candidate_pose_world_cam=_from_numpy(state.candidate_pose_world_cam, torch.float32),
        candidate_pose_relative_root=_from_numpy(state.candidate_pose_relative_root, torch.float32),
        candidate_position_id=_from_numpy(state.candidate_position_id, torch.int64),
        actor_action_mask=_from_numpy(state.actor_action_mask, torch.bool),
        history_candidate_row_id=_from_numpy(state.history_candidate_row_id, torch.int64),
        history_pose_world_cam=_from_numpy(state.history_pose_world_cam, torch.float32),
        history_pose_relative_root=_from_numpy(state.history_pose_relative_root, torch.float32),
        history_position_id=_from_numpy(state.history_position_id, torch.int64),
        history_mask=torch.ones(history_count, dtype=torch.bool),
        remaining_budget=torch.tensor(state.remaining_budget, dtype=torch.int64),
    )


def _tensor_supervision(state: rollout_qh.QhRolloutState) -> QhSupervision:
    return QhSupervision(
        q_train_mask=_from_numpy(state.supervision.q_train_mask, torch.bool),
    )


def _validate_actor_sample(source: VinActorSample, *, requested_blocks: tuple[str, ...]) -> None:
    availability_names = tuple(name for name, _ in source.availability)
    block_names = tuple(name for name, _ in source.blocks)
    if len(availability_names) != len(set(availability_names)):
        raise ValueError("VIN actor availability names must be unique.")
    if availability_names != requested_blocks:
        raise ValueError(
            "VIN actor sample availability does not match the exact requested profile; rebuild the actor source."
        )
    if len(block_names) != len(set(block_names)):
        raise ValueError("VIN actor block names must be unique.")
    unknown = (set(availability_names) | set(block_names)) - ACTOR_VISIBLE_NUMERIC_BLOCKS
    if unknown:
        raise ValueError(f"VIN actor sample contains non-actor numeric blocks: {sorted(unknown)}.")
    present = {name for name, available in source.availability if available}
    if set(block_names) != present:
        raise ValueError(
            "VIN actor block payloads must exist exactly for availability=True entries; rebuild the actor source."
        )
    for name, value in source.blocks:
        if not (np.issubdtype(value.dtype, np.number) or np.issubdtype(value.dtype, np.bool_)):
            raise ValueError(f"VIN actor block {name!r} is not numeric.")


def _from_numpy(value: np.ndarray, dtype: torch.dtype | None = None) -> Tensor:
    tensor = torch.from_numpy(np.array(value, copy=True))
    return tensor if dtype is None else tensor.to(dtype=dtype)


def _collate_actor(actors: list[QhActorInputs]) -> QhActorInputs:
    availability_names = tuple(name for name, _ in actors[0].vin_block_availability)
    if any(tuple(name for name, _ in actor.vin_block_availability) != availability_names for actor in actors[1:]):
        raise ValueError("Q_H actor block profiles changed within one batch.")
    availability = tuple(
        (
            name,
            torch.stack([dict(actor.vin_block_availability)[name] for actor in actors]),
        )
        for name in availability_names
    )
    block_maps = [dict(actor.vin_blocks) for actor in actors]
    blocks: list[tuple[str, Tensor]] = []
    for name in availability_names:
        exemplar = next((mapping[name] for mapping in block_maps if name in mapping), None)
        if exemplar is None:
            continue
        values = [mapping.get(name, _unavailable_like(exemplar)) for mapping in block_maps]
        blocks.append((name, _pad_nd(values, 0)))
    return QhActorInputs(
        vin_blocks=tuple(blocks),
        vin_block_availability=availability,
        target_center_world=torch.stack([actor.target_center_world for actor in actors]),
        target_extents=torch.stack([actor.target_extents for actor in actors]),
        target_pose_world_object=torch.stack([actor.target_pose_world_object for actor in actors]),
        target_relative_pose_reference_object=torch.stack(
            [actor.target_relative_pose_reference_object for actor in actors]
        ),
        target_sem_id=torch.stack([actor.target_sem_id for actor in actors]),
        target_inst_id=torch.stack([actor.target_inst_id for actor in actors]),
        candidate_row_id=_pad_first_axis([actor.candidate_row_id for actor in actors], -1),
        candidate_pose_world_cam=_pad_first_axis([actor.candidate_pose_world_cam for actor in actors], 0),
        candidate_pose_relative_root=_pad_first_axis(
            [actor.candidate_pose_relative_root for actor in actors],
            0,
        ),
        candidate_position_id=_pad_first_axis([actor.candidate_position_id for actor in actors], -1),
        actor_action_mask=_pad_first_axis([actor.actor_action_mask for actor in actors], False),
        history_candidate_row_id=_pad_first_axis([actor.history_candidate_row_id for actor in actors], -1),
        history_pose_world_cam=_pad_first_axis([actor.history_pose_world_cam for actor in actors], 0),
        history_pose_relative_root=_pad_first_axis(
            [actor.history_pose_relative_root for actor in actors],
            0,
        ),
        history_position_id=_pad_first_axis([actor.history_position_id for actor in actors], -1),
        history_mask=_pad_first_axis([actor.history_mask for actor in actors], False),
        remaining_budget=torch.stack([actor.remaining_budget for actor in actors]),
    )


def _empty_actor_like(actor: QhActorInputs) -> QhActorInputs:
    def empty(value: Tensor) -> Tensor:
        return value.new_empty((0, *value.shape[1:]))

    return replace(
        actor,
        vin_blocks=tuple((name, _unavailable_like(value)) for name, value in actor.vin_blocks),
        vin_block_availability=tuple(
            (name, torch.tensor(False, dtype=torch.bool)) for name, _ in actor.vin_block_availability
        ),
        target_center_world=torch.zeros_like(actor.target_center_world),
        target_extents=torch.zeros_like(actor.target_extents),
        target_pose_world_object=torch.zeros_like(actor.target_pose_world_object),
        target_relative_pose_reference_object=torch.zeros_like(actor.target_relative_pose_reference_object),
        target_sem_id=torch.tensor(-1, dtype=torch.int64),
        target_inst_id=torch.tensor(-1, dtype=torch.int64),
        candidate_row_id=empty(actor.candidate_row_id),
        candidate_pose_world_cam=empty(actor.candidate_pose_world_cam),
        candidate_pose_relative_root=empty(actor.candidate_pose_relative_root),
        candidate_position_id=empty(actor.candidate_position_id),
        actor_action_mask=empty(actor.actor_action_mask),
        history_candidate_row_id=empty(actor.history_candidate_row_id),
        history_pose_world_cam=empty(actor.history_pose_world_cam),
        history_pose_relative_root=empty(actor.history_pose_relative_root),
        history_position_id=empty(actor.history_position_id),
        history_mask=empty(actor.history_mask),
        remaining_budget=torch.tensor(0, dtype=torch.int64),
    )


def _unavailable_like(exemplar: Tensor) -> Tensor:
    if exemplar.dtype == torch.bool:
        return torch.zeros_like(exemplar)
    if exemplar.is_floating_point() or exemplar.is_complex():
        return torch.full_like(exemplar, float("nan"))
    return torch.full_like(exemplar, -1)


def _pad_first_axis(values: list[Tensor], fill: int | float | bool) -> Tensor:
    return _pad_nd(values, fill, only_first=True)


def _pad_nd(values: list[Tensor], fill: int | float | bool, *, only_first: bool = False) -> Tensor:
    if not values:
        raise ValueError("Cannot pad an empty tensor list.")
    ndim = values[0].ndim
    if any(value.ndim != ndim for value in values):
        raise ValueError("Q_H tensors with different ranks cannot share one padded field.")
    maxima = [max(value.shape[axis] for value in values) for axis in range(ndim)]
    if only_first:
        expected_tail = values[0].shape[1:]
        if any(value.shape[1:] != expected_tail for value in values[1:]):
            raise ValueError("Only the leading Q_H candidate/history axis may vary.")
        maxima[1:] = expected_tail
    output = torch.full((len(values), *maxima), fill, dtype=values[0].dtype)
    for row, value in enumerate(values):
        selection = (row, *(slice(0, size) for size in value.shape))
        output[selection] = value
    return output


def _seed_worker(worker_id: int) -> None:
    """Seed CPU-only worker RNGs from the DataLoader generator."""

    del worker_id
    seed = torch.initial_seed() % (2**32)
    random.seed(seed)
    np.random.seed(seed)


def _distributed_training_partitions(
    dataset: Sized,
    *,
    num_replicas: int,
    seed: int,
    epoch: int,
) -> tuple[tuple[int, ...], ...]:
    partitions: list[tuple[int, ...]] = []
    for rank in range(num_replicas):
        sampler = DistributedSampler(
            dataset,
            num_replicas=num_replicas,
            rank=rank,
            shuffle=True,
            seed=seed,
            drop_last=False,
        )
        sampler.set_epoch(epoch)
        partitions.append(tuple(sampler))
    return tuple(partitions)


def _requested_stages(stage: str | None) -> tuple[str, ...]:
    if stage in {None, "fit"}:
        return ("train", "val")
    if stage in {"validate", "val"}:
        return ("val",)
    if stage in {"test"}:
        return ("test",)
    if stage in {"predict"}:
        return ()
    raise ValueError(f"Unknown Lightning stage {stage!r}.")


def _dataset_scene_ids(dataset: Dataset[QhSample]) -> frozenset[str]:
    declared = getattr(dataset, "scene_ids", None)
    if declared is not None:
        return frozenset(declared)
    return frozenset(dataset[index].lineage.current.scene_id for index in range(len(dataset)))


__all__ = [
    "QhActorInputs",
    "QhBatch",
    "QhDataModule",
    "QhDataModuleConfig",
    "QhDataset",
    "QhDatasetConfig",
    "QhLineage",
    "QhSample",
    "QhSupervision",
    "QhTransition",
    "collate_qh_samples",
]
