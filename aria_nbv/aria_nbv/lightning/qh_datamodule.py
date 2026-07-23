"""Lightning loader adapter for an admitted framework-neutral ``Q_H`` corpus.

:class:`aria_nbv.data_handling.qh.QhCorpus` owns dataset construction and
all-stage admission. This module adds only deterministic PyTorch DataLoaders,
worker seeding, distributed training partitions, and exact evaluation loaders.
It deliberately does not interpret rollout storage, join actor evidence, or
materialize stage configs during the Lightning lifecycle.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Sized

import numpy as np
import pytorch_lightning as pl
import torch
from pydantic import Field
from torch.utils.data import DataLoader, DistributedSampler, Sampler, SequentialSampler

from ..data_handling.qh import (
    QhBatch,
    QhCorpus,
    QhDatasetConfig,
    QhStageDataset,
    collate_qh_samples,
)
from ..utils import Stage, TargetConfig


class QhDataModuleConfig(TargetConfig["QhDataModule"]):
    """Configure explicit Q_H stages and deterministic loader policy."""

    train: QhDatasetConfig
    """Training dataset factory; constructed and admitted before Lightning."""

    val: QhDatasetConfig | None = None
    """Optional scene-disjoint validation dataset factory."""

    test: QhDatasetConfig | None = None
    """Optional scene-disjoint held-out dataset factory."""

    batch_size: int = Field(default=1, ge=1)
    """Joined rollout states per DataLoader batch."""

    num_workers: int = Field(default=0, ge=0)
    """CPU worker count; worker processes never move tensors to CUDA."""

    pin_memory: bool = False
    """Ask PyTorch to call :meth:`aria_nbv.data_handling.qh.QhBatch.pin_memory`."""

    persistent_workers: bool = False
    """Keep workers alive between epochs when :attr:`num_workers` is positive."""

    @property
    def target_type(self) -> type[QhDataModule]:
        """Runtime adapter constructed by :meth:`setup_target`."""

        return QhDataModule

    def setup_target(self, *, seed: int) -> QhDataModule:
        """Construct every configured dataset and admit one runtime corpus.

        Args:
            seed: Experiment-owned seed shared by sampler, generator, and
                worker initialization. The deterministic datasets have no RNG.

        Returns:
            Thin :class:`QhDataModule` over an already admitted
            :class:`aria_nbv.data_handling.qh.QhCorpus`.
        """

        corpus = QhCorpus.admit(
            train=self.train.setup_target(),
            val=None if self.val is None else self.val.setup_target(),
            test=None if self.test is None else self.test.setup_target(),
        )
        return QhDataModule(
            corpus,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            pin_memory=self.pin_memory,
            persistent_workers=self.persistent_workers,
            seed=seed,
        )


class QhDataModule(pl.LightningDataModule):
    """Add loader policy to an admitted :class:`~aria_nbv.data_handling.qh.QhCorpus`.

    Training uses PyTorch's seeded
    [DistributedSampler](https://docs.pytorch.org/docs/2.4/data.html#torch.utils.data.distributed.DistributedSampler)
    and reports its global padding duplicates. Validation and test are exact,
    replicated sequential loaders. Trainer construction must set
    ``use_distributed_sampler=False`` so Lightning does not replace these
    explicit samplers.
    """

    def __init__(
        self,
        corpus: QhCorpus,
        *,
        batch_size: int = 1,
        num_workers: int = 0,
        pin_memory: bool = False,
        persistent_workers: bool = False,
        seed: int,
    ) -> None:
        super().__init__()
        if batch_size < 1 or num_workers < 0:
            raise ValueError("batch_size must be positive and num_workers non-negative.")
        self.corpus = corpus
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.pin_memory = pin_memory
        self.persistent_workers = persistent_workers and num_workers > 0
        self.seed = seed
        self._train_sampler: _AccountedDistributedSampler | None = None

    @property
    def training_horizon(self) -> int:
        """Return the horizon proven common during corpus admission."""

        return self.corpus.q_h_horizon

    @property
    def training_padding_rows(self) -> int:
        """Return the sampler's global padding-row count for the current epoch."""

        return 0 if self._train_sampler is None else self._train_sampler.padding_rows

    @property
    def training_padding_fraction(self) -> float:
        """Return padded rows divided by the sampler's global emitted rows."""

        if self._train_sampler is None or self._train_sampler.total_size == 0:
            return 0.0
        return self._train_sampler.padding_rows / self._train_sampler.total_size

    @property
    def training_duplicated_dataset_indices(self) -> tuple[int, ...]:
        """Return exact duplicated dataset indices for the current epoch."""

        return () if self._train_sampler is None else self._train_sampler.duplicated_dataset_indices

    def setup(self, stage: Stage | str | None = None) -> None:
        """Normalize the Lightning callback stage; corpus admission is already complete."""

        if stage == "predict":
            return
        if stage is not None:
            Stage.from_str(stage)

    def train_dataloader(self) -> DataLoader[QhBatch]:
        """Build the seeded, rank-partitioned training loader."""

        replicas, rank = self._distributed_context()
        sampler = self.prepare_training_sampler(num_replicas=replicas, rank=rank)
        return self._loader(self.corpus.train, sampler=sampler)

    def prepare_training_sampler(self, *, num_replicas: int, rank: int) -> _AccountedDistributedSampler:
        """Prepare rank-local sampling and global padding facts without row reads.

        This pre-loop hook constructs only PyTorch's index sampler over the
        already admitted training dataset. It does not iterate the dataset,
        start DataLoader workers, open Zarr state arrays, or materialize actor
        evidence. :meth:`train_dataloader` reuses the sampler when its
        distributed context matches the Trainer.
        """

        if (
            self._train_sampler is not None
            and self._train_sampler.num_replicas == num_replicas
            and self._train_sampler.rank == rank
        ):
            return self._train_sampler
        sampler = _AccountedDistributedSampler(
            self.corpus.train,
            num_replicas=num_replicas,
            rank=rank,
            shuffle=True,
            seed=self.seed,
            drop_last=False,
        )
        self._train_sampler = sampler
        return sampler

    def val_dataloader(self) -> DataLoader[QhBatch] | list[DataLoader[QhBatch]]:
        """Build a replicated exact validation loader when configured."""

        loader = self._eval_loader(self.corpus.val)
        return [] if loader is None else loader

    def test_dataloader(self) -> DataLoader[QhBatch] | list[DataLoader[QhBatch]]:
        """Build a replicated exact held-out loader when configured."""

        loader = self._eval_loader(self.corpus.test)
        return [] if loader is None else loader

    def _eval_loader(self, dataset: QhStageDataset | None) -> DataLoader[QhBatch] | None:
        if dataset is None:
            return None
        return self._loader(dataset, sampler=SequentialSampler(dataset))

    def _loader(self, dataset: QhStageDataset, *, sampler: Sampler[int]) -> DataLoader[QhBatch]:
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


def _seed_worker(worker_id: int) -> None:
    """Seed CPU worker RNGs from the experiment-owned DataLoader generator."""

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


__all__ = ["QhDataModule", "QhDataModuleConfig"]
