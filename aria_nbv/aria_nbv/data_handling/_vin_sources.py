"""Canonical VIN dataset-source configs for online and immutable offline data."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated, Any, Literal, TypeAlias

import torch
from pydantic import Field
from torch.utils.data import IterableDataset

from ..configs import PathConfig
from ..pipelines.oracle_rri_labeler import OracleRriLabeler, OracleRriLabelerConfig
from ..utils import Console, Stage, TargetConfig, Verbosity
from .offline.batch import VinOracleBatch
from .offline.dataset import VinOfflineDataset, VinOfflineDatasetConfig
from .raw import AseEfmDatasetConfig, EfmSnippetView


class VinOracleOnlineDataset(IterableDataset[VinOracleBatch]):
    """Iterable dataset yielding `VinOracleBatch` with online oracle labels."""

    is_map_style: bool = False
    """Whether the dataset supports random access and batching."""

    def __init__(
        self,
        *,
        base: IterableDataset[EfmSnippetView],
        labeler: OracleRriLabeler,
        max_attempts_per_batch: int,
        verbosity: Verbosity,
        efm_keep_keys: set[str] | None,
    ) -> None:
        """Store the online dataset dependencies."""
        super().__init__()
        self._base = base
        self._labeler = labeler
        self._max_attempts = int(max_attempts_per_batch)
        self._console = Console.with_prefix(self.__class__.__name__).set_verbosity(
            verbosity,
        )
        self._efm_keep_keys = efm_keep_keys

    def __iter__(self) -> Iterator[VinOracleBatch]:
        """Yield oracle-labelled VIN batches from the wrapped raw dataset."""
        base_iter = iter(self._base)
        attempts = 0
        while True:
            sample = next(base_iter)
            try:
                label_batch = self._labeler.run(sample)
            except ValueError as exc:
                attempts += 1
                self._console.warn(
                    f"skip: scene={sample.scene_id} snip={sample.snippet_id} err={exc}",
                )
                if attempts >= self._max_attempts:
                    raise RuntimeError(
                        f"Exceeded max_attempts_per_batch={self._max_attempts} without a valid oracle label batch.",
                    ) from exc
                continue

            attempts = 0
            oracle_rri = label_batch.rri.rri.detach()
            if oracle_rri.numel() == 0 or not torch.isfinite(oracle_rri).any():
                self._console.warn(
                    f"skip: empty/non-finite rri scene={sample.scene_id} snip={sample.snippet_id}",
                )
                continue

            yield VinOracleBatch.from_label(
                label_batch,
                efm_keep_keys=self._efm_keep_keys,
            )


def _default_online_train_ds() -> AseEfmDatasetConfig:
    """Return the default raw-dataset config used for online VIN training."""
    return AseEfmDatasetConfig(
        load_meshes=True,
        require_mesh=True,
        batch_size=1,
        verbosity=Verbosity.QUIET,
        is_debug=False,
        wds_shuffle=True,
    )


class VinOracleOnlineDatasetConfig(TargetConfig[VinOracleOnlineDataset]):
    """Configuration for online oracle VIN datasets."""

    kind: Literal["online"] = "online"
    """Discriminator for online datasets."""

    @property
    def target_type(self) -> type[VinOracleOnlineDataset]:
        """Return the factory target for `BaseConfig.setup_target`."""
        return VinOracleOnlineDataset

    paths: PathConfig = Field(default_factory=PathConfig)
    """Project path resolver."""

    dataset: AseEfmDatasetConfig = Field(default_factory=_default_online_train_ds)
    """EFM dataset configuration used to stream raw snippets."""

    train_overrides: dict[str, Any] | None = None
    """Optional field overrides applied for the train split."""

    val_overrides: dict[str, Any] | None = Field(
        default_factory=lambda: {"wds_shuffle": False, "wds_repeat": False},
    )
    """Optional field overrides applied for val/test splits."""

    labeler: OracleRriLabelerConfig = Field(default_factory=OracleRriLabelerConfig)
    """Oracle labeler configuration."""

    max_attempts_per_batch: int = 50
    """Maximum oracle attempts before raising."""

    efm_keep_keys: list[str] | None = None
    """Optional allowlist of EFM keys to keep in VIN batches."""

    prune_efm_snippet: bool = True
    """Whether to prune EFM snippets before returning VIN batches."""

    verbosity: Verbosity = Verbosity.NORMAL
    """Verbosity level for dataset and labeler diagnostics."""

    def setup_target(self, *, split: Stage) -> VinOracleOnlineDataset:
        """Instantiate the online VIN dataset for the requested split."""
        dataset_cfg = self._resolve_dataset_cfg(split)
        base = dataset_cfg.setup_target()
        labeler = self.labeler.setup_target()
        keep_keys = None
        if self.prune_efm_snippet and self.efm_keep_keys:
            keep_keys = {key for key in self.efm_keep_keys if key}
        return VinOracleOnlineDataset(
            base=base,
            labeler=labeler,
            max_attempts_per_batch=self.max_attempts_per_batch,
            verbosity=self.verbosity,
            efm_keep_keys=keep_keys,
        )

    def _resolve_dataset_cfg(self, split: Stage) -> AseEfmDatasetConfig:
        """Return the raw-dataset config after split-specific overrides."""
        dataset_cfg = self.dataset.model_copy(deep=True)
        dataset_cfg.paths = self.paths
        overrides = self.train_overrides if split is Stage.TRAIN else self.val_overrides
        if overrides:
            dataset_cfg = dataset_cfg.model_copy(deep=True, update=overrides)
        return dataset_cfg

    @property
    def is_map_style(self) -> bool:
        """Return whether this source yields a map-style dataset."""
        return False


class VinOfflineSourceConfig(TargetConfig[VinOfflineDataset]):
    """Configuration for the immutable VIN offline dataset source."""

    kind: Literal["offline"] = "offline"
    """Discriminator for the immutable offline dataset."""

    @property
    def target_type(self) -> type[VinOfflineDataset]:
        """Return the factory target for `BaseConfig.setup_target`."""

        return VinOfflineDataset

    paths: PathConfig = Field(default_factory=PathConfig)
    """Project path resolver."""

    offline: VinOfflineDatasetConfig = Field(default_factory=VinOfflineDatasetConfig)
    """Immutable VIN offline dataset configuration."""

    train_split: Literal["train", "val", "all"] = "train"
    """Offline split to use for training."""

    val_split: Literal["train", "val", "all"] = "val"
    """Offline split to use for validation and testing."""

    load_candidates_for_batch: bool = False
    """Whether VIN-batch reads should decode candidate diagnostics."""

    load_depths_for_batch: bool = False
    """Whether VIN-batch reads should decode candidate depth diagnostics."""

    load_candidate_pcs_for_batch: bool = False
    """Whether VIN-batch reads should decode candidate point-cloud diagnostics."""

    load_gt_obbs_for_batch: bool = True
    """Whether VIN-batch reads should decode compact GT OBB blocks."""

    load_detected_obbs_for_batch: bool = True
    """Whether VIN-batch reads should decode compact detected OBB blocks."""

    load_trajectory_metadata_for_batch: bool = True
    """Whether VIN-batch reads should decode trajectory metadata blocks."""

    def setup_target(self, *, split: Stage) -> VinOfflineDataset:
        """Instantiate the immutable offline VIN dataset for the requested split."""

        dataset_split = self.train_split if split is Stage.TRAIN else self.val_split
        offline_cfg = self.offline.model_copy(deep=True)
        offline_cfg.paths = self.paths
        offline_cfg.store.paths = self.paths
        offline_cfg.split = dataset_split
        offline_cfg.return_format = "vin_batch"
        offline_cfg.load_candidates = bool(self.load_candidates_for_batch)
        offline_cfg.load_depths = bool(self.load_depths_for_batch)
        offline_cfg.load_candidate_pcs = bool(self.load_candidate_pcs_for_batch)
        offline_cfg.load_gt_obbs = bool(self.load_gt_obbs_for_batch)
        offline_cfg.load_detected_obbs = bool(self.load_detected_obbs_for_batch)
        offline_cfg.load_trajectory_metadata = bool(self.load_trajectory_metadata_for_batch)
        return offline_cfg.setup_target()

    @property
    def is_map_style(self) -> bool:
        """Return whether this source yields a map-style dataset."""

        return True


VinDatasetSourceConfig: TypeAlias = Annotated[
    VinOracleOnlineDatasetConfig | VinOfflineSourceConfig,
    Field(discriminator="kind"),
]
"""Canonical split-aware VIN dataset-source union used by Lightning."""

__all__ = [
    "VinDatasetSourceConfig",
    "VinOfflineSourceConfig",
    "VinOracleOnlineDataset",
    "VinOracleOnlineDatasetConfig",
]
