"""Chain-native :class:`QhDataset` loaders with deterministic, resumable shuffling.
Lightning replaces samplers; metrics include padding duplicates rather than a deduplicated corpus.
"""

from __future__ import annotations

import random
from collections.abc import Sized

import numpy as np
import pytorch_lightning as pl
import torch
from pydantic import Field
from torch.utils.data import DataLoader, Dataset, RandomSampler

from ..data_handling.qh import QhBatch, QhDatasetConfig, QhRolloutChain, collate_qh_samples
from ..utils import Stage, TargetConfig

_LearningContract = tuple[tuple[tuple[str, object], ...], ...]


class QhDataModuleConfig(TargetConfig["QhDataModule"]):
    """Configure explicit chain datasets and deterministic loader policy."""

    train: QhDatasetConfig
    """Required training chain dataset factory."""
    val: QhDatasetConfig | None = None
    """Optional scene-disjoint validation dataset factory."""
    test: QhDatasetConfig | None = None
    """Optional scene-disjoint held-out dataset factory."""
    batch_size: int = Field(default=1, ge=1)
    """Complete rollout chains per loader batch."""
    num_workers: int = Field(default=0, ge=0)
    """CPU worker count."""
    pin_memory: bool = False
    """Ask PyTorch to call :meth:`QhBatch.pin_memory`."""
    persistent_workers: bool = False
    """Keep workers alive between epochs when worker count is positive."""

    @property
    def target_type(self) -> type[QhDataModule]:
        """Runtime adapter constructed by :meth:`setup_target`."""

        return QhDataModule

    def setup_target(self, *, seed: int) -> QhDataModule:
        """Construct and admit every configured chain dataset."""

        return QhDataModule(
            train=self.train.setup_target(),
            val=None if self.val is None else self.val.setup_target(),
            test=None if self.test is None else self.test.setup_target(),
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            pin_memory=self.pin_memory,
            persistent_workers=self.persistent_workers,
            seed=seed,
        )


class QhDataModule(pl.LightningDataModule):
    """Build stage loaders without interpreting storage or training labels.

    :class:`QhDataset` owns admission and :func:`collate_qh_samples` owns padding;
    ``use_distributed_sampler=True`` lets Lightning partition every stage.
    """

    def __init__(
        self,
        *,
        train: Dataset[QhRolloutChain],
        val: Dataset[QhRolloutChain] | None = None,
        test: Dataset[QhRolloutChain] | None = None,
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
        self._train_generator = torch.Generator().manual_seed(seed)
        self._learning_contract = _validate_stages(train=train, val=val, test=test)

    @property
    def training_horizon(self) -> int:
        """Return the horizon proven common across configured stages."""
        return int(self.train_dataset.q_h_horizon)

    @property
    def provenance(self) -> dict[str, object]:
        """Return compact preflighted provenance for every configured stage."""
        return {
            name: None if dataset is None else dataset.provenance
            for name, dataset in (
                ("train", self.train_dataset),
                ("val", self.val_dataset),
                ("test", self.test_dataset),
            )
        }

    @property
    def learning_contract(self) -> dict[str, object]:
        """Return stage-invariant corpus semantics used by checkpoints."""
        return dict(zip(("rollout", "actor"), map(dict, self._learning_contract), strict=True))

    def dataset_for_stage(self, stage: Stage | str) -> Dataset[QhRolloutChain] | None:
        """Return the configured dataset for one lifecycle stage."""
        resolved = Stage.from_str(stage)
        return {
            Stage.TRAIN: self.train_dataset,
            Stage.VAL: self.val_dataset,
            Stage.TEST: self.test_dataset,
        }[resolved]

    def setup(self, stage: Stage | str | None = None) -> None:
        """Validate Lightning stage text; datasets are already admitted."""
        if stage not in (None, "predict"):
            Stage.from_str(stage)

    def state_dict(self) -> dict[str, torch.Tensor]:
        """Persist the shuffled training stream at epoch boundaries."""
        return {"train_generator_state": self._train_generator.get_state()}

    def load_state_dict(self, state_dict: dict[str, torch.Tensor]) -> None:
        """Restore the shuffled training stream from a Lightning checkpoint."""
        self._train_generator.set_state(state_dict["train_generator_state"])

    def train_dataloader(self) -> DataLoader[QhBatch]:
        """Build a shuffled loader eligible for Lightning sampler replacement."""
        return self._loader(self.train_dataset, shuffle=True)

    def val_dataloader(self) -> DataLoader[QhBatch] | list[DataLoader[QhBatch]]:
        """Build a sequential validation loader eligible for sampler replacement."""
        return [] if self.val_dataset is None else self._loader(self.val_dataset, shuffle=False)

    def test_dataloader(self) -> DataLoader[QhBatch] | list[DataLoader[QhBatch]]:
        """Build a sequential held-out loader eligible for sampler replacement."""
        return [] if self.test_dataset is None else self._loader(self.test_dataset, shuffle=False)

    def _loader(self, dataset: Dataset[QhRolloutChain], *, shuffle: bool) -> DataLoader[QhBatch]:
        return DataLoader(
            dataset,
            batch_size=self.batch_size,
            sampler=RandomSampler(dataset, generator=self._train_generator) if shuffle else None,
            num_workers=self.num_workers,
            pin_memory=self.pin_memory,
            persistent_workers=self.persistent_workers,
            collate_fn=collate_qh_samples,
            worker_init_fn=_seed_worker,
            generator=torch.Generator().manual_seed(self.seed),
        )


def _validate_stages(**stages: Dataset[QhRolloutChain] | None) -> _LearningContract:
    configured = {name: value for name, value in stages.items() if value is not None}
    if len(contracts := {_learning_contract(value.provenance) for value in configured.values()}) != 1:
        raise ValueError("Q_H corpus stages have incompatible learning contracts.")
    empty = [name for name, value in configured.items() if len(value) < 1]
    if empty:
        raise ValueError(f"Q_H configured corpus stages must contain at least one chain: {empty}.")
    horizons = {name: int(value.q_h_horizon) for name, value in configured.items()}
    if any(value < 1 for value in horizons.values()) or len(set(horizons.values())) != 1:
        raise ValueError(f"Q_H corpus stage horizons must be equal positive integers: {horizons}.")
    names = tuple(configured)
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            overlap = configured[left].scene_ids & configured[right].scene_ids
            if overlap:
                raise ValueError(f"Q_H {left}/{right} datasets overlap scenes {sorted(overlap)}.")
    return contracts.pop()


def _learning_contract(provenance: dict[str, object]) -> _LearningContract:
    rollout = provenance["rollout"]["compatibility"]  # type: ignore[index]
    actor = provenance["actor"]  # type: ignore[assignment]
    return (
        tuple(sorted((name, value) for name, value in rollout.items() if name != "source_split")),
        (("manifest_hash", actor["manifest_hash"]), ("store_version", actor["store_version"])),
    )


def distributed_padding_rows(dataset: Sized, *, world_size: int) -> int:
    """Return the duplicate rows Lightning's default sampler must pad globally."""

    if world_size < 1:
        raise ValueError("world_size must be positive.")
    return (-len(dataset)) % world_size


def _seed_worker(worker_id: int) -> None:
    del worker_id
    seed = torch.initial_seed() % (2**32)
    random.seed(seed)
    np.random.seed(seed)


__all__ = ["QhDataModule", "QhDataModuleConfig"]
