"""Provide stage-aware VIN datasets and candidate-table collation to Lightning.

The training data-flow mirrors `aria_nbv/scripts/train_vin.py`:

EFM snippet → candidate generation → depth rendering → backprojection → oracle RRI → VIN (CORAL).

This module owns dataset construction, stage reuse, candidate shuffling, and
``VinOracleBatch.collate`` selection. It keeps the expensive oracle labeler in
the data pipeline by default, but can switch to immutable VIN offline stores
for fast parallel reading. It does not own scorer inputs or losses; those
boundaries belong to :mod:`aria_nbv.lightning._candidate_scorer_batch` and
:mod:`aria_nbv.lightning.lit_module`.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import pytorch_lightning as pl
from pydantic import Field, model_validator
from torch.utils.data import DataLoader, Dataset, IterableDataset

from ..configs import PathConfig
from ..data_handling import (
    AseEfmDatasetConfig,
    VinDatasetSourceConfig,
    VinOracleBatch,
    VinOracleDatasetBase,
    VinOracleOnlineDatasetConfig,
)
from ..utils import Console, Stage, TargetConfig, Verbosity


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
    """Configure stage datasets and candidate-table collation.

    Online sources yield one oracle-labelled snippet at a time and therefore
    require ``num_workers=0``. Map-style offline sources may collate a batch of
    size ``B``; candidate rows are right-padded to ``N_q`` and accompanied by
    per-sample `candidate_count` values used to construct the hard prefix mask.
    """

    @property
    def target_type(self) -> type["VinDataModule"]:
        """Return the :class:`VinDataModule` factory target."""

        return VinDataModule

    paths: PathConfig = Field(default_factory=PathConfig)
    """Project path resolver used by nested dataset/store configurations."""

    source: VinDatasetSourceConfig = Field(default_factory=_default_source)
    """Config-as-factory source for online labels or an immutable offline store."""

    shuffle: bool = True
    """Shuffle map-style training samples each epoch; ignored for iterable sources."""

    shuffle_candidates: bool = True
    """Permute compact valid candidate rows and aligned labels per training sample.

    For a collated table, only each row's valid prefix is permuted; right-padding
    stays outside :meth:`VinOracleBatch.candidate_valid_mask`.
    """

    num_workers: int = 16
    """DataLoader worker count; must be zero for the non-multiprocess-safe online labeler."""

    batch_size: int | None = None
    """Optional offline batch size ``B`` using :meth:`VinOracleBatch.collate`.

    ``None`` preserves single-sample candidate poses ``PoseTW["N_q 12"]`` and
    RRI labels ``Tensor["N_q", float32]``. A positive value produces
    ``PoseTW["B N_q 12"]`` and ``Tensor["B N_q", float32]`` tables padded to
    the largest compact valid count in the batch.
    """

    persistent_workers: bool = False
    """Keep worker processes between epochs; forced off when `num_workers` is zero."""

    verbosity: Verbosity = Verbosity.NORMAL
    """Dataset and oracle-labeler diagnostic verbosity."""

    is_debug: bool = False
    """Serialized compatibility flag; worker and trainer debug policy is configured elsewhere."""

    use_train_as_val: bool = False
    """Reuse the exact train dataset instance for validation and testing.

    This is intended for online diagnostics where a separate validation source
    is unavailable, not for held-out performance reporting.
    """

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
    """Own stage datasets and loaders for oracle-labelled VIN batches.

    Lightning may call :meth:`setup` more than once. Dataset instances are
    therefore initialized lazily and retained by stage. Scorer-device transfer
    remains the module's responsibility; this class yields CPU/source-device
    :class:`VinOracleBatch` objects whose candidate width is compact for a
    single sample or right-padded after offline collation.

    Attributes:
        config: Immutable construction policy for sources, batching, and
            worker lifecycle.
    """

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
        """Initialize and retain the datasets required by one Lightning stage.

        Args:
            stage: ``train``, ``val``, ``test``, or ``None``. ``None`` prepares
                both training and validation ownership paths.

        Notes:
            Repeated calls are idempotent for already-created sources.
            Validation and test share `_val_source`; when `use_train_as_val` is
            enabled they deliberately share `_train_source` as well.
        """

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
        """Build the training loader with optional row and candidate shuffling.

        Returns:
            DataLoader yielding :class:`VinOracleBatch`. Map-style batching
            produces poses ``PoseTW["B N_q 12"]``, RRI labels
            ``Tensor["B N_q", float32]``, and a hard prefix mask derived from
            `candidate_count`; iterable/online sources remain unbatched.
        """

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
        """Build the deterministic validation loader for the retained source.

        Returns:
            DataLoader yielding unshuffled :class:`VinOracleBatch` objects with
            the same compact/right-padded shape contract as the training loader.
        """

        plan = self._build_stage_plan(Stage.VAL)
        return DataLoader(
            plan.dataset,
            batch_size=self.config.batch_size if plan.use_batching else None,
            num_workers=self.config.num_workers,
            persistent_workers=self.config.persistent_workers if self.config.num_workers > 0 else False,
            collate_fn=VinOracleBatch.collate if plan.use_batching else None,
        )

    def test_dataloader(self) -> DataLoader:
        """Reuse the validation-loader contract for Lightning test evaluation."""

        return self.val_dataloader()

    # ------------------------------------------------------------------ helpers
    def iter_oracle_batches(self, *, stage: Stage) -> Iterator[VinOracleBatch]:
        """Return a direct iterator over one stage's oracle-labelled samples.

        This bypasses worker processes and `VinOracleBatch.collate`, so yielded
        candidate payloads retain their per-sample ``N_q`` width.
        """
        plan = self._build_stage_plan(stage)
        return iter(plan.dataset)

    def _describe_dataset(self, dataset: VinOracleDatasetBase, *, stage: Stage) -> dict[str, object]:
        from ..data_handling import VinOfflineDatasetConfig, VinOracleOnlineDataset

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


__all__ = ["VinDataModule", "VinDataModuleConfig", "VinOracleBatch"]
