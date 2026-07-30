"""Generate immutable VIN offline stores from Oracle-labelled snippets.

This module owns composition of raw snippet streaming, Oracle labels, optional EVL
features, immutable codecs, split assignment, and shard promotion.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import torch
from pydantic import Field

from ...configs import PathConfig
from ...data_handling.ase_efm.dataset import AseEfmDatasetConfig
from ...data_handling.ase_efm.views import EfmSnippetView
from ...data_handling.vin_store.adapter import DEFAULT_VIN_SNIPPET_PAD_POINTS, build_vin_snippet_view
from ...data_handling.vin_store.format import (
    VinOfflineIndexRecord,
    VinOfflineManifest,
    VinOfflineMaterializedBlocks,
    VinOfflineShardSpec,
)
from ...data_handling.vin_store.store import OFFLINE_DATASET_VERSION, VinOfflineStoreConfig
from ...data_handling.vin_store.writer import (
    DEFAULT_BACKBONE_NUMERIC_KEEP_FIELDS,
    DEFAULT_BACKBONE_PAYLOAD_KEEP_FIELDS,
    PreparedVinOfflineSample,
    assign_offline_splits,
    flush_prepared_samples_to_shard,
    prepare_vin_offline_sample,
)
from ...utils import Console, TargetConfig, Verbosity
from ...utils.fingerprints import stable_json_signature
from ...vin.backbones import EvlBackboneConfig

if TYPE_CHECKING:
    from ...vin.types import EvlBackboneOutput
    from .scene_labels import OracleRriSample

from .scene_labels import OracleRriLabelerConfig


class VinOfflineWriterConfig(TargetConfig["VinOfflineWriter"]):
    """Configure immutable VIN offline generation from raw snippets."""

    @property
    def target_type(self) -> type["VinOfflineWriter"]:
        """Return the generation pipeline factory target."""

        return VinOfflineWriter

    paths: PathConfig = Field(default_factory=PathConfig)
    """Project path resolver."""

    store: VinOfflineStoreConfig = Field(default_factory=VinOfflineStoreConfig)
    """Output store configuration."""

    dataset: AseEfmDatasetConfig = Field(default_factory=lambda: AseEfmDatasetConfig(wds_shuffle=True))
    """Raw ASE/EFM dataset configuration used to stream snippets."""

    labeler: OracleRriLabelerConfig = Field(default_factory=OracleRriLabelerConfig)
    """Oracle labeler configuration."""

    backbone: EvlBackboneConfig | None = Field(default_factory=EvlBackboneConfig)
    """Optional EVL backbone configuration."""

    include_backbone: bool = True
    """Whether to persist actor-visible EVL outputs with manifest provenance."""

    include_depths: bool = True
    """Whether to persist GT-mesh-rendered candidate depths and validity masks."""

    include_pointclouds: bool = False
    """Whether rich diagnostic payloads may include candidate point clouds."""

    include_diagnostic_payloads: bool = False
    """Whether to write rich msgpack diagnostic records alongside numeric blocks."""

    include_gt_obbs: bool = True
    """Whether to persist compact GT OBBs as label/evaluation assets."""

    include_detected_obbs: bool = True
    """Whether to persist actor-visible EVL detected boxes from backbone outputs."""

    include_trajectory_metadata: bool = True
    """Whether to persist trajectory timestamps and gravity."""

    backbone_numeric_keep_fields: list[str] | None = Field(
        default_factory=lambda: list(DEFAULT_BACKBONE_NUMERIC_KEEP_FIELDS),
    )
    """EVL fields written as canonical fixed numeric training blocks; ``None`` keeps all supported fields."""

    backbone_payload_keep_fields: list[str] | None = Field(
        default_factory=lambda: list(DEFAULT_BACKBONE_PAYLOAD_KEEP_FIELDS),
    )
    """EVL backbone fields written to the optional rich diagnostic payload."""

    vin_pad_points: int = Field(default=DEFAULT_VIN_SNIPPET_PAD_POINTS, ge=0)
    """Fixed ``K_store`` row count for world-frame semidense VIN point tensors."""

    semidense_max_points: int | None = None
    """Optional cap on collapsed semidense points before padding."""

    semidense_include_obs_count: bool = False
    """Whether VIN points include observation counts."""

    max_candidates: int | None = None
    """Maximum number of candidates stored per sample."""

    samples_per_shard: int = Field(default=64, ge=1)
    """Number of samples stored in each immutable shard."""

    max_samples: int | None = None
    """Optional cap on the number of processed samples."""

    train_val_split: float = Field(default=0.2, ge=0.0, le=1.0)
    """Fraction of samples assigned to the validation split."""

    overwrite: bool = False
    """Whether an existing store directory may be replaced."""

    num_failures_allowed: int = 40
    """Maximum number of tolerated sample failures before aborting."""

    verbosity: Verbosity = Verbosity.NORMAL
    """Verbosity level for dataset build logging."""


class VinOfflineWriter:
    """Compose raw data, Oracle labels, optional features, and offline codecs."""

    def __init__(self, config: VinOfflineWriterConfig) -> None:
        """Initialize the pipeline and its runtime dependencies.

        Args:
            config: Offline generation configuration.
        """

        self.config = config
        self.console = Console.with_prefix(self.__class__.__name__).set_verbosity(config.verbosity)
        self._dataset = config.dataset.setup_target()
        self._labeler = config.labeler.setup_target()
        self._backbone = (
            config.backbone.setup_target() if config.include_backbone and config.backbone is not None else None
        )

    def _resolve_max_candidates(self) -> int:
        """Return the candidate budget stored per sample."""

        if self.config.max_candidates is not None:
            return int(self.config.max_candidates)
        return int(getattr(self.config.labeler.depth, "max_candidates_final", 60))

    def _prepare_row(
        self,
        *,
        sample: EfmSnippetView,
        label_batch: OracleRriSample,
        backbone_out: EvlBackboneOutput | None,
        max_candidates: int,
    ) -> PreparedVinOfflineSample:
        """Convert one labelled raw snippet into a prepared storage row."""

        vin_snippet = build_vin_snippet_view(
            sample,
            device=torch.device("cpu"),
            max_points=self.config.semidense_max_points,
            include_inv_dist_std=True,
            include_obs_count=self.config.semidense_include_obs_count,
            pad_points=self.config.vin_pad_points,
        )
        return prepare_vin_offline_sample(
            scene_id=sample.scene_id,
            snippet_id=sample.snippet_id,
            vin_snippet=vin_snippet,
            candidates=label_batch.candidates,
            depths=label_batch.depths,
            rri=label_batch.rri,
            candidate_pcs=label_batch.candidate_pcs if self.config.include_pointclouds else None,
            backbone_out=backbone_out if self.config.include_backbone else None,
            max_candidates=max_candidates,
            source_sample=sample,
            include_depths=self.config.include_depths,
            include_candidate_pcs=self.config.include_pointclouds,
            include_backbone=self.config.include_backbone,
            include_diagnostic_payloads=self.config.include_diagnostic_payloads,
            include_gt_obbs=self.config.include_gt_obbs,
            include_detected_obbs=self.config.include_detected_obbs,
            include_trajectory_metadata=self.config.include_trajectory_metadata,
            backbone_numeric_keep_fields=(
                set(self.config.backbone_numeric_keep_fields)
                if self.config.backbone_numeric_keep_fields is not None
                else None
            ),
            backbone_payload_keep_fields=(
                set(self.config.backbone_payload_keep_fields)
                if self.config.backbone_payload_keep_fields is not None
                else None
            ),
        )

    def run(self) -> VinOfflineManifest:
        """Build the configured immutable VIN offline dataset."""

        store_dir = self.config.store.store_dir
        temp_dir = store_dir.with_name(f"{store_dir.name}.tmp")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        if store_dir.exists() and not self.config.overwrite:
            raise FileExistsError(
                f"VIN offline dataset already exists at {store_dir} (set overwrite=True to replace).",
            )
        temp_dir.mkdir(parents=True, exist_ok=True)
        (temp_dir / self.config.store.shards_dirname).mkdir(parents=True, exist_ok=True)

        max_candidates = self._resolve_max_candidates()
        prepared_rows: list[PreparedVinOfflineSample] = []
        shard_specs: list[VinOfflineShardSpec] = []
        index_records: list[VinOfflineIndexRecord] = []
        failures = 0
        processed = 0
        interrupted = False

        try:
            for sample in self._dataset:
                if self.config.max_samples is not None and processed >= int(self.config.max_samples):
                    break
                try:
                    label_batch = self._labeler.run(sample)
                    backbone_out = self._backbone.forward(sample.efm) if self._backbone is not None else None
                    prepared_rows.append(
                        self._prepare_row(
                            sample=sample,
                            label_batch=label_batch,
                            backbone_out=backbone_out,
                            max_candidates=max_candidates,
                        ),
                    )
                    processed += 1
                    if len(prepared_rows) >= int(self.config.samples_per_shard):
                        shard_spec, local_records = flush_prepared_samples_to_shard(
                            shard_index=len(shard_specs),
                            shard_dir=temp_dir / self.config.store.shards_dirname / f"shard-{len(shard_specs):06d}",
                            rows=prepared_rows,
                        )
                        shard_specs.append(shard_spec)
                        index_records.extend(local_records)
                        prepared_rows = []
                except Exception as exc:
                    failures += 1
                    self.console.error(
                        f"Failed to build offline sample for scene={sample.scene_id} snippet={sample.snippet_id}: {exc}",
                    )
                    if failures > int(self.config.num_failures_allowed):
                        raise RuntimeError(
                            f"Exceeded num_failures_allowed={self.config.num_failures_allowed} while building offline data.",
                        ) from exc
        except KeyboardInterrupt:
            interrupted = True
            self.console.log("Interrupted by user; finalizing already prepared VIN offline samples.")

        if prepared_rows:
            shard_spec, local_records = flush_prepared_samples_to_shard(
                shard_index=len(shard_specs),
                shard_dir=temp_dir / self.config.store.shards_dirname / f"shard-{len(shard_specs):06d}",
                rows=prepared_rows,
            )
            shard_specs.append(shard_spec)
            index_records.extend(local_records)

        split_indices = assign_offline_splits(records=index_records, val_fraction=self.config.train_val_split)
        row_start = 0
        for shard_spec in shard_specs:
            shard_spec.row_start = row_start
            row_start += int(shard_spec.num_rows)

        materialized_block_names = {block_name for shard_spec in shard_specs for block_name in shard_spec.blocks}
        dataset_config = self.config.dataset.model_dump_cache(exclude_none=True)
        labeler_config = self.config.labeler.model_dump_cache(exclude_none=True)
        backbone_config = (
            self.config.backbone.model_dump_cache(exclude_none=True) if self.config.backbone is not None else None
        )
        manifest = VinOfflineManifest(
            version=OFFLINE_DATASET_VERSION,
            created_at=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            source={
                "dataset_config": dataset_config,
                "dataset_signature": stable_json_signature(dataset_config),
            },
            oracle={
                "labeler_config": labeler_config,
                "labeler_signature": stable_json_signature(labeler_config),
                "backbone_config": backbone_config,
                "backbone_signature": stable_json_signature(backbone_config) if backbone_config is not None else None,
                "max_candidates": max_candidates,
                "backbone_numeric_keep_fields": self.config.backbone_numeric_keep_fields,
                "backbone_payload_keep_fields": self.config.backbone_payload_keep_fields,
            },
            vin={
                "pad_points": int(self.config.vin_pad_points),
                "semidense_max_points": self.config.semidense_max_points,
                "include_inv_dist_std": True,
                "include_obs_count": bool(self.config.semidense_include_obs_count),
            },
            materialized_blocks=VinOfflineMaterializedBlocks(
                backbone=bool(self.config.include_backbone),
                depths=bool(self.config.include_depths),
                candidate_pcs=bool(self.config.include_diagnostic_payloads and self.config.include_pointclouds),
                gt_obbs="gt.obbs" in materialized_block_names,
                detected_obbs="detected.obbs" in materialized_block_names,
                trajectory=(
                    "vin.trajectory.time_ns" in materialized_block_names
                    or "vin.trajectory.gravity_in_world" in materialized_block_names
                ),
            ),
            stats={
                "num_samples": len(index_records),
                "num_shards": len(shard_specs),
                "num_train": int(split_indices["train"].shape[0]),
                "num_val": int(split_indices["val"].shape[0]),
                "interrupted": interrupted,
            },
            provenance={
                "writer": self.__class__.__name__,
                "store_dir": store_dir.as_posix(),
                "split_policy": "sha1(sample_key)",
                "finalized_after_interrupt": interrupted,
            },
            shards=shard_specs,
        )

        manifest.write(temp_dir / self.config.store.manifest_filename)
        VinOfflineIndexRecord.write_many(temp_dir / self.config.store.sample_index_filename, index_records)
        self.config.store.model_copy(update={"store_dir": temp_dir}).write_split_indices(split_indices)
        if store_dir.exists():
            shutil.rmtree(store_dir)
        temp_dir.rename(store_dir)
        self.console.log(
            f"Wrote VIN offline dataset with {len(index_records)} samples across {len(shard_specs)} shards to {store_dir}",
        )
        if interrupted:
            self.console.log("Partial VIN offline dataset finalized after Ctrl-C.")
        return manifest


__all__ = ["VinOfflineWriter", "VinOfflineWriterConfig"]
