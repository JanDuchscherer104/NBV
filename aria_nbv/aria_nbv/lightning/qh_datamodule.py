"""Stage admission and deterministic loaders for ``Q_H`` chain datasets.

Construction is a hard admission boundary: configured stages must be nonempty,
share one :class:`~aria_nbv.rollouts.qh_reader.QhDataContract`, and have
disjoint scene sets.  Once admitted, loaders preserve the dataset's padded
candidate width, seed each DataLoader's torch generator from the configured
module seed, and derive Python/NumPy worker seeds from each worker's
``torch.initial_seed()``.
"""

from __future__ import annotations

import random
from dataclasses import fields
from typing import Protocol, cast

import numpy as np
import pytorch_lightning as pl
import torch
from torch.utils.data import DataLoader, Dataset

from ..data_handling.qh_data import QhBatch, QhChain, collate_qh_chains
from ..data_handling.qh_data.views import QhActorStateContract, QhExperimentProfile, validate_experiment_profile
from ..rollouts.qh_reader import QhDataContract
from ..utils.fingerprints import stable_msgspec_hash


class _QhDataset(Protocol):
    @property
    def contract(self) -> QhDataContract: ...

    @property
    def actor_state_contract(self) -> QhActorStateContract: ...

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
        experiment_profile: QhExperimentProfile | None = None,
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
        self.experiment_profile = experiment_profile

        stages = {
            name: dataset for name, dataset in (("train", train), ("val", val), ("test", test)) if dataset is not None
        }
        empty = [name for name, dataset in stages.items() if len(dataset) == 0]
        if empty:
            raise ValueError(f"Q_H configured corpus stages must contain at least one chain: {empty}.")
        if any(dataset.contract != train.contract for dataset in stages.values()):
            raise ValueError("Q_H corpus stages have incompatible learning contracts.")
        self.learning_contract_hash = stable_msgspec_hash(train.contract)
        self.actor_state_contract_hash = stable_msgspec_hash(train.actor_state_contract)
        self.geometry_contract_hash = train.actor_state_contract.geometry_contract_hash
        if experiment_profile is not None:
            validate_experiment_profile(
                experiment_profile,
                root_evl_profile=train.actor_state_contract.root_evl_profile,
                selected_observation_protocol=train.actor_state_contract.selected_observation_protocol,
                target_protocol=train.contract.target_protocol,
                privileged=experiment_profile == "qh_cfplus_gt_depth_v1",
            )
            for name, dataset in stages.items():
                if dataset.actor_state_contract.experiment_profile != experiment_profile:
                    raise ValueError(
                        f"Q_H {name} stage has experiment profile "
                        f"{dataset.actor_state_contract.experiment_profile!r}, expected {experiment_profile!r}."
                    )
        for name, dataset in stages.items():
            if dataset.actor_state_contract == train.actor_state_contract:
                continue
            mismatches = [
                field.name
                for field in fields(QhActorStateContract)
                if getattr(dataset.actor_state_contract, field.name) != getattr(train.actor_state_contract, field.name)
            ]
            raise ValueError(f"Q_H {name} stage has incompatible actor-state contract fields: {', '.join(mismatches)}.")
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
    """Seed Python and NumPy from PyTorch's per-worker seed."""
    seed = torch.initial_seed() % (2**32)
    random.seed(seed)
    np.random.seed(seed)


__all__ = ["QhDataModule"]
