"""Online Oracle label generation for VIN training."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Literal

import torch
from pydantic import Field
from torch.utils.data import IterableDataset

from ...configs import PathConfig
from ...data_handling.offline.batch import VinOracleBatch
from ...data_handling.raw import AseEfmDatasetConfig, EfmSnippetView
from ...pipelines.oracle_rri_labeler import OracleRriLabeler, OracleRriLabelerConfig, OracleRriSample
from ...utils import Console, Stage, TargetConfig, Verbosity


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

            yield _vin_batch_from_label(
                label_batch,
                efm_keep_keys=self._efm_keep_keys,
            )


def _vin_batch_from_label(
    label_batch: OracleRriSample,
    *,
    efm_keep_keys: set[str] | None,
) -> VinOracleBatch:
    """Adapt one online Oracle label result to the model-facing batch."""

    rri = label_batch.rri
    sample = label_batch.sample
    if efm_keep_keys is not None:
        sample = sample.prune_efm(efm_keep_keys)

    return VinOracleBatch(
        efm_snippet_view=sample,
        candidate_poses_world_cam=label_batch.depths.poses,
        reference_pose_world_rig=label_batch.depths.reference_pose,
        rri=rri.rri,
        pm_dist_before=rri.pm_dist_before,
        pm_dist_after=rri.pm_dist_after,
        pm_acc_before=rri.pm_acc_before,
        pm_comp_before=rri.pm_comp_before,
        pm_acc_after=rri.pm_acc_after,
        pm_comp_after=rri.pm_comp_after,
        p3d_cameras=label_batch.depths.p3d_cameras,
        candidate_count=torch.tensor(
            int(rri.rri.shape[0]),
            device=rri.rri.device,
            dtype=torch.int64,
        ),
        scene_id=sample.scene_id,
        snippet_id=sample.snippet_id,
        backbone_out=None,
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


__all__ = [
    "VinOracleOnlineDataset",
    "VinOracleOnlineDatasetConfig",
]
