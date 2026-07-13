"""LightningDataModule for VIN training with online or immutable offline labels.

The training data-flow mirrors `aria_nbv/scripts/train_vin.py`:

EFM snippet → candidate generation → depth rendering → backprojection → oracle RRI → VIN (CORAL).

This module keeps the expensive oracle labeler in the data pipeline by default,
but can switch to immutable VIN offline stores for fast parallel reading.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated, TypeAlias

import pytorch_lightning as pl
from pydantic import Field, model_validator
from torch.utils.data import DataLoader, Dataset, IterableDataset

from ..configs import PathConfig
from ..data_handling import (
    AseEfmDatasetConfig,
    VinOracleBatch,
)
from ..data_handling.offline.batch import VinOracleDatasetBase
from ..data_handling.offline.source import VinOfflineSourceConfig
from ..oracle.pipelines.online_vin import VinOracleOnlineDataset, VinOracleOnlineDatasetConfig
from ..utils import Console, Stage, TargetConfig, Verbosity

VinDatasetSourceConfig: TypeAlias = Annotated[
    VinOracleOnlineDatasetConfig | VinOfflineSourceConfig,
    Field(discriminator="kind"),
]
"""Split-aware VIN dataset-source union composed by Lightning."""


def _default_source() -> VinDatasetSourceConfig:
    return VinOracleOnlineDatasetConfig(
        dataset=AseEfmDatasetConfig(
            load_meshes=True,
            require_mesh=True,
            batch_size=1,
            verbosity=Verbosity.QUIET,
            is_debug=False,
            wds_shuffle=True,
        )
    )


class VinDataModuleConfig(TargetConfig["VinDataModule"]):
    """Configuration for `VinDataModule`."""

    @property
    def target_type(self) -> type["VinDataModule"]:
        return VinDataModule

    paths: PathConfig = Field(default_factory=PathConfig)
    """Project path resolver."""

    source: VinDatasetSourceConfig = Field(default_factory=_default_source)
    """Config-as-factory dataset source."""

    shuffle: bool = True
    """Whether to shuffle the train dataset at each epoch (only applies to offline stores)."""

    shuffle_candidates: bool = True
    """Whether to shuffle candidate views and corresponding labels with each sample (offline stores only)."""

    num_workers: int = 16
    """Number of DataLoader worker processes (use >0 for offline stores; keep 0 for online labeler)."""
    batch_size: int | None = None
    """Optional DataLoader batch size (offline-store only; requires custom collation)."""

    persistent_workers: bool = False
    """Whether to keep DataLoader workers alive between epochs (ignored when num_workers=0)."""

    verbosity: Verbosity = Verbosity.NORMAL
    """Verbosity level for dataset/labeler diagnostics."""

    is_debug: bool = False
    """Enable debug defaults (forces num_workers=0, lowers verbosity)."""

    use_train_as_val: bool = False
    """Use the train dataset instance for validation/testing (applies to online datasets)."""

    @model_validator(mode="after")
    def _check_compatibility(self) -> VinDataModuleConfig:
        if self.source is None:
            raise ValueError("source must be set.")

        if self.batch_size is not None:
            if self.batch_size <= 0:
                raise ValueError("batch_size must be >= 1 when provided.")
            if not self.source.is_map_style:
                raise ValueError(
                    "batch_size can only be used with map-style datasets.",
                )

        if self.num_workers > 0 and isinstance(self.source, VinOracleOnlineDatasetConfig):
            if "num_workers" not in self.model_fields_set:
                self.num_workers = 0
            else:
                raise ValueError(
                    "OracleRriLabeler is not multiprocess-safe; set num_workers=0 for online datasets.",
                )
        return self


class VinDataModule(pl.LightningDataModule):
    """LightningDataModule that yields online or offline oracle-labelled VIN batches."""

    _train_source: VinOracleDatasetBase | None
    """Optional config-selected dataset for training."""

    _val_source: VinOracleDatasetBase | None
    """Optional config-selected dataset for validation/testing."""

    def __init__(self, config: VinDataModuleConfig):
        super().__init__()
        self.config = config
        self.save_hyperparameters(config.model_dump_jsonable())

        self._train_source: VinOracleDatasetBase | None = None
        self._val_source: VinOracleDatasetBase | None = None

    @dataclass(slots=True)
    class _StagePlan:
        dataset: Dataset[VinOracleBatch] | IterableDataset[VinOracleBatch]
        is_map_style: bool
        allow_shuffle: bool
        use_batching: bool

    class _ShuffleCandidatesMapDataset(Dataset[VinOracleBatch]):
        """Map-style dataset wrapper that shuffles candidates per sample."""

        def __init__(self, base: Dataset[VinOracleBatch]) -> None:
            self._base = base

        def __len__(self) -> int:  # type: ignore[override]
            return len(self._base)

        def __getitem__(self, idx: int) -> VinOracleBatch:  # type: ignore[override]
            sample = self._base[idx]
            if not isinstance(sample, VinOracleBatch):
                raise TypeError("ShuffleCandidatesMapDataset expects VinOracleBatch samples.")
            return sample.shuffle_candidates()

    class _ShuffleCandidatesIterableDataset(IterableDataset[VinOracleBatch]):
        """Iterable dataset wrapper that shuffles candidates per sample."""

        def __init__(self, base: IterableDataset[VinOracleBatch]) -> None:
            super().__init__()
            self._base = base

        def __iter__(self) -> Iterator[VinOracleBatch]:  # type: ignore[override]
            for sample in self._base:
                if not isinstance(sample, VinOracleBatch):
                    raise TypeError("ShuffleCandidatesIterableDataset expects VinOracleBatch samples.")
                yield sample.shuffle_candidates()

    def _resolve_map_style(self, dataset: object) -> bool:
        return bool(getattr(dataset, "is_map_style", isinstance(dataset, Dataset)))

    def _build_stage_plan(
        self,
        stage: Stage,
    ) -> _StagePlan:
        self.setup(stage=stage)
        if stage is Stage.TRAIN:
            if self._train_source is None:
                raise RuntimeError("Missing train dataset. Did setup() run?")
            is_map_style = self._resolve_map_style(self._train_source)
            use_batching = is_map_style and self.config.batch_size is not None
            return self._StagePlan(
                dataset=self._train_source,
                is_map_style=is_map_style,
                allow_shuffle=is_map_style and self.config.shuffle,
                use_batching=use_batching,
            )

        if self._val_source is None:
            raise RuntimeError("Missing val dataset. Did setup() run?")
        is_map_style = self._resolve_map_style(self._val_source)
        use_batching = is_map_style and self.config.batch_size is not None
        return self._StagePlan(
            dataset=self._val_source,
            is_map_style=is_map_style,
            allow_shuffle=False,
            use_batching=use_batching,
        )

    # --------------------------------------------------------------------- setup
    def setup(self, stage: Stage | str | None = None) -> None:
        console = Console.with_prefix(self.__class__.__name__, "setup")
        requested = Stage.from_str(stage) if stage is not None else None
        if requested is None or requested is Stage.TRAIN:
            if self._train_source is None:
                self._train_source = self.config.source.setup_target(split=Stage.TRAIN)
                console.log("Initialized train dataset.")
                console.plog(
                    self._describe_dataset(self._train_source, stage=Stage.TRAIN),
                )
        if requested is None or requested in (Stage.VAL, Stage.TEST):
            if self._val_source is None and self.config.use_train_as_val:
                if self._train_source is None:
                    self._train_source = self.config.source.setup_target(split=Stage.TRAIN)
                    console.log("Initialized train dataset.")
                    console.plog(
                        self._describe_dataset(self._train_source, stage=Stage.TRAIN),
                    )
                self._val_source = self._train_source
                console.log("Using train dataset for validation/testing.")
                console.plog(
                    self._describe_dataset(self._val_source, stage=Stage.VAL),
                )
            elif self._val_source is None:
                self._val_source = self.config.source.setup_target(split=Stage.VAL)
                console.log("Initialized val dataset.")
                console.plog(
                    self._describe_dataset(self._val_source, stage=Stage.VAL),
                )

    # ------------------------------------------------------------------ loaders
    def train_dataloader(self) -> DataLoader:
        plan = self._build_stage_plan(Stage.TRAIN)
        dataset = plan.dataset
        if plan.is_map_style and self.config.shuffle_candidates:
            if isinstance(dataset, Dataset):
                dataset = self._ShuffleCandidatesMapDataset(dataset)
            elif isinstance(dataset, IterableDataset):
                dataset = self._ShuffleCandidatesIterableDataset(dataset)
        return DataLoader(
            dataset,
            batch_size=self.config.batch_size if plan.use_batching else None,
            shuffle=self.config.shuffle if plan.allow_shuffle else False,
            num_workers=self.config.num_workers,
            persistent_workers=self.config.persistent_workers if self.config.num_workers > 0 else False,
            collate_fn=VinOracleBatch.collate if plan.use_batching else None,
        )

    def val_dataloader(self) -> DataLoader:
        plan = self._build_stage_plan(Stage.VAL)
        return DataLoader(
            plan.dataset,
            batch_size=self.config.batch_size if plan.use_batching else None,
            num_workers=self.config.num_workers,
            persistent_workers=self.config.persistent_workers if self.config.num_workers > 0 else False,
            collate_fn=VinOracleBatch.collate if plan.use_batching else None,
        )

    def test_dataloader(self) -> DataLoader:
        return self.val_dataloader()

    # ------------------------------------------------------------------ helpers
    def iter_oracle_batches(self, *, stage: Stage) -> Iterator[VinOracleBatch]:
        """Iterate oracle batches without going through a DataLoader."""
        plan = self._build_stage_plan(stage)
        return iter(plan.dataset)

    def _describe_dataset(self, dataset: VinOracleDatasetBase, *, stage: Stage) -> dict[str, object]:
        from ..data_handling.offline.dataset import VinOfflineDatasetConfig

        summary: dict[str, object] = {
            "stage": stage.value,
            "dataset_type": dataset.__class__.__name__,
        }

        cfg = getattr(dataset, "config", None)
        if isinstance(cfg, VinOfflineDatasetConfig):
            summary.update(
                {
                    "store_dir": str(cfg.store.store_dir),
                    "split": cfg.split,
                    "return_format": cfg.return_format,
                    "include_efm_snippet": cfg.include_efm_snippet,
                    "include_gt_mesh": cfg.include_gt_mesh,
                    "load_backbone": cfg.load_backbone,
                    "load_candidates": cfg.load_candidates,
                    "load_depths": cfg.load_depths,
                    "load_candidate_pcs": cfg.load_candidate_pcs,
                    "limit": cfg.limit,
                }
            )
            return summary

        if isinstance(dataset, VinOracleOnlineDataset):
            base = getattr(dataset, "_base", None)
            base_cfg = getattr(base, "config", None)
            if base_cfg is not None:
                summary.update(
                    {
                        "atek_variant": getattr(base_cfg, "atek_variant", None),
                        "scene_ids": getattr(base_cfg, "scene_ids", None),
                        "snippet_ids": getattr(base_cfg, "snippet_ids", None),
                        "tar_url_count": len(getattr(base_cfg, "tar_urls", []) or []),
                        "wds_shuffle": getattr(base_cfg, "wds_shuffle", None),
                        "wds_repeat": getattr(base_cfg, "wds_repeat", None),
                        "load_meshes": getattr(base_cfg, "load_meshes", None),
                        "require_mesh": getattr(base_cfg, "require_mesh", None),
                        "device": getattr(base_cfg, "device", None),
                    }
                )
        return summary


__all__ = ["VinDataModule", "VinDataModuleConfig", "VinDatasetSourceConfig", "VinOracleBatch"]
