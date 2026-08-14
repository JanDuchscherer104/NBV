"""Stage admission and deterministic loaders for ``Q_H`` chain datasets.

Construction is a hard admission boundary: configured stages must be nonempty,
share one :class:`~aria_nbv.rollouts.qh_reader.QhDataContract`, and have
disjoint scene sets.  Once admitted, loaders preserve the dataset's padded
candidate width and derive worker seeds from the Lightning base seed.
"""

from __future__ import annotations

import random
from typing import Protocol, cast

import numpy as np
import pytorch_lightning as pl
import torch
from torch.utils.data import DataLoader, Dataset

from ..data_handling.qh_data import QhBatch, QhChain, collate_qh_chains
from ..rollouts.qh_reader import QhDataContract


class _QhDataset(Protocol):
    @property
    def contract(self) -> QhDataContract: ...

    @property
    def scenes(self) -> frozenset[str]: ...

    @property
    def max_horizon(self) -> int: ...

    @property
    def provenance(self) -> dict[str, object]: ...

    def __len__(self) -> int: ...

    def __getitem__(self, index: int) -> QhChain: ...


class QhDataModule(pl.LightningDataModule):
    """Admit compatible stage datasets and build their DataLoaders."""

    def __init__(
        self,
        *,
        train: _QhDataset,
        val: _QhDataset | None = None,
        test: _QhDataset | None = None,
        batch_size: int = 1,
        num_workers: int = 0,
        pin_memory: bool = False,
        persistent_workers: bool = False,
        seed: int,
    ) -> None:
        super().__init__()
        self.train_dataset = train
        self.val_dataset = val
        self.test_dataset = test
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.pin_memory = pin_memory
        self.persistent_workers = persistent_workers and num_workers > 0
        self.seed = seed

        stages = {
            name: dataset for name, dataset in (("train", train), ("val", val), ("test", test)) if dataset is not None
        }
        empty = [name for name, dataset in stages.items() if len(dataset) == 0]
        if empty:
            raise ValueError(f"Q_H configured corpus stages must contain at least one chain: {empty}.")
        if any(dataset.contract != train.contract for dataset in stages.values()):
            raise ValueError("Q_H corpus stages have incompatible learning contracts.")
        names = tuple(stages)
        for index, left in enumerate(names):
            for right in names[index + 1 :]:
                overlap = stages[left].scenes & stages[right].scenes
                if overlap:
                    raise ValueError(f"Q_H {left}/{right} datasets overlap scenes {sorted(overlap)}.")

    def train_dataloader(self) -> DataLoader[QhBatch]:
        """Build the deterministically shuffled training loader."""
        return self._loader(self.train_dataset, shuffle=True)

    def val_dataloader(self) -> DataLoader[QhBatch] | list[DataLoader[QhBatch]]:
        """Build the sequential validation loader when configured."""
        return [] if self.val_dataset is None else self._loader(self.val_dataset, shuffle=False)

    def test_dataloader(self) -> DataLoader[QhBatch] | list[DataLoader[QhBatch]]:
        """Build the sequential test loader when configured."""
        return [] if self.test_dataset is None else self._loader(self.test_dataset, shuffle=False)

    def _loader(self, dataset: _QhDataset, *, shuffle: bool) -> DataLoader[QhBatch]:
        loader = DataLoader(
            cast(Dataset[QhChain], dataset),
            batch_size=self.batch_size,
            shuffle=shuffle,
            num_workers=self.num_workers,
            pin_memory=self.pin_memory,
            persistent_workers=self.persistent_workers,
            collate_fn=collate_qh_chains,
            worker_init_fn=_seed_worker,
            generator=torch.Generator().manual_seed(self.seed),
        )
        return cast(DataLoader[QhBatch], loader)


def _seed_worker(_worker_id: int) -> None:
    seed = torch.initial_seed() % (2**32)
    random.seed(seed)
    np.random.seed(seed)


__all__ = ["QhDataModule"]
