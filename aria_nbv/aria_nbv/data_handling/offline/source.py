"""Immutable VIN offline dataset source configuration."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from ...configs import PathConfig
from ...utils import Stage, TargetConfig
from .dataset import VinOfflineDataset, VinOfflineDatasetConfig


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

    train_split: Stage = Stage.TRAIN
    """Stored stage used for training."""

    val_split: Stage = Stage.VAL
    """Stored stage used for validation."""

    test_split: Stage = Stage.VAL
    """Stored stage used for testing when no distinct held-out split exists."""

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

    @field_validator("train_split", "val_split", "test_split", mode="before")
    @classmethod
    def _normalize_stage(cls, value: Stage | str) -> Stage:
        """Normalize config-file stage text before it enters source selection."""

        return Stage.from_str(value)

    def setup_target(self, *, split: Stage) -> VinOfflineDataset:
        """Instantiate the immutable offline VIN dataset for the requested split."""

        dataset_split = {
            Stage.TRAIN: self.train_split,
            Stage.VAL: self.val_split,
            Stage.TEST: self.test_split,
        }[split]
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


__all__ = ["VinOfflineSourceConfig"]
