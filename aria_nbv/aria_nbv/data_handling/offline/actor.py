"""Typed actor-only projection over immutable VIN offline stores.

The module exposes the canonical :class:`aria_nbv.data_handling.raw.views.VinSnippetView`
needed by ``Q_H`` composition. It deliberately reads neither rollout facts nor
Oracle, GT, candidate-rendering, crop, selected-depth, or optional feature bags.

This module is the observation-side adapter used by
:class:`aria_nbv.data_handling.qh.QhDataset`. Rollout transitions and target
descriptors remain owned by :mod:`aria_nbv.rollouts`; privileged Oracle and GT
blocks never cross this projection. It owns immutable-source admission, exact
lineage checks, and worker-local reads, not rollout or model lifecycle.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, ClassVar, Literal

import numpy as np
import torch
from efm3d.aria.pose import PoseTW
from pydantic import Field

from ...utils import TargetConfig
from ...utils.fingerprints import stable_msgspec_hash
from ..identifiers import compact_ase_atek_sample_id
from ..raw.views import VinSnippetView
from .format import VinOfflineIndexRecord, VinOfflineShardSpec
from .store import OFFLINE_DATASET_VERSION, VinOfflineStoreConfig, VinOfflineStoreReader

_PROFILE_REQUIRED_BLOCKS = (
    "vin.points_world",
    "vin.lengths",
    "vin.t_world_rig",
)


@dataclass(frozen=True, slots=True)
class VinActorSample:
    """Frozen typed actor evidence and immutable source-row lineage.

    Attributes:
        snippet: Canonical actor-visible semidense and trajectory evidence.
    """

    sample_index: int
    """Global source index from ``sample_index.jsonl``."""

    sample_key: str
    """Stable compact ASE/ATEK sample key."""

    scene_id: str
    """ASE scene identifier retained for join audits."""

    snippet_id: str
    """ATEK snippet identifier retained for join audits."""

    # TODO: always make fuse of utils.schemas.Stage!
    split: str
    """Immutable source split recorded by the sample index."""

    source_shard_id: str
    """Shard containing this source row."""

    source_shard_row: int
    """Zero-based row inside :attr:`source_shard_id`."""

    source_offline_store_version: str
    """Strict immutable-store format version."""

    source_offline_store_manifest_hash: str
    """Stable hash of the complete immutable source manifest."""

    snippet: VinSnippetView
    """Typed points, lengths, and world-from-rig history used by the V0 actor."""


class VinActorSourceConfig(TargetConfig["VinActorSource"]):
    """Configure the narrow actor projection over one immutable VIN store."""

    profile: Literal["minimal_pose_target_v0"] = "minimal_pose_target_v0"
    """Closed actor profile; V1 observed-target evidence is not implemented."""

    store: VinOfflineStoreConfig = Field(default_factory=VinOfflineStoreConfig)
    """Immutable VIN source-store location and filenames."""

    # TODO: always make fuse of utils.schemas.Stage!
    split: Literal["train", "val", "all"] = "all"
    """Source split exposed through the map-style interface."""

    @property
    def target_type(self) -> type[VinActorSource]:
        """Runtime source constructed by :meth:`setup_target`."""

        return VinActorSource


class VinActorSource:
    """Read actor-visible arrays through a lazy, worker-local store reader.

    Construction validates manifest/index/shard contracts and all required
    blocks before workers start. Numeric Zarr handles are opened only by the
    process that first indexes the source and are discarded during pickling.
    :meth:`__getitem__` returns read-only arrays; downstream tensor adapters
    must copy them before mutation or device transfer.
    """

    _REBUILD_GUIDANCE: ClassVar[str] = (
        "Rebuild the VIN offline store and rollout corpus from the same immutable source manifest."
    )

    def __init__(self, config: VinActorSourceConfig) -> None:
        """Preflight immutable lineage and configured actor-block availability."""

        self.config = config
        reader = VinOfflineStoreReader(config.store)
        self.source_offline_store_version = str(reader.manifest.version)
        self.source_offline_store_manifest_hash = stable_msgspec_hash(reader.manifest)
        self._records = tuple(reader.get_split_records(config.split))
        self._index_by_sample_index = {record.sample_index: index for index, record in enumerate(self._records)}
        self._shards = {shard.shard_id: shard for shard in reader.manifest.shards}
        self._validate_store(reader)
        self._reader_pid: int | None = None
        self._reader: VinOfflineStoreReader | None = None

    def __len__(self) -> int:
        """Return the number of source rows in the configured split."""

        return len(self._records)

    @property
    def provenance(self) -> dict[str, object]:
        """Return the preflighted immutable-source identity without row reads."""

        return {
            "store_path": str(self.config.store.store_dir),
            "store_version": self.source_offline_store_version,
            "manifest_hash": self.source_offline_store_manifest_hash,
            "split": self.config.split,
            "row_count": len(self),
        }

    def __getitem__(self, index: int) -> VinActorSample:
        """Read one row as a canonical actor-visible VIN snippet."""

        record = self._record(index)
        reader = self._reader_for_process()
        points_world = torch.from_numpy(np.array(reader.read_numeric_block(record, "vin.points_world"), copy=True))
        lengths = torch.from_numpy(np.array(reader.read_numeric_block(record, "vin.lengths"), copy=True))
        t_world_rig = PoseTW(
            torch.from_numpy(np.array(reader.read_numeric_block(record, "vin.t_world_rig"), copy=True))
        )
        return VinActorSample(
            sample_index=record.sample_index,
            sample_key=record.sample_key,
            scene_id=record.scene_id,
            snippet_id=record.snippet_id,
            split=record.split,
            source_shard_id=record.shard_id,
            source_shard_row=record.row,
            source_offline_store_version=self.source_offline_store_version,
            source_offline_store_manifest_hash=self.source_offline_store_manifest_hash,
            snippet=VinSnippetView(
                points_world=points_world,
                lengths=lengths,
                t_world_rig=t_world_rig,
            ),
        )

    def index_for_sample(self, sample_index: int) -> int:
        """Resolve a sparse immutable sample index to this source's map index."""

        try:
            return self._index_by_sample_index[sample_index]
        except KeyError as error:
            raise KeyError(
                f"VIN sample_index={sample_index} is absent from split {self.config.split!r}. {self._REBUILD_GUIDANCE}",
            ) from error

    def __getstate__(self) -> dict[str, Any]:
        """Drop process-owned reader and Zarr handles before worker pickling."""

        state = self.__dict__.copy()
        state["_reader_pid"] = None
        state["_reader"] = None
        return state

    def validate_lineage(
        self,
        index: int,
        *,
        source_sample_index: int,
        source_sample_key: str,
        source_shard_id: str,
        source_shard_row: int,
        source_offline_store_version: str | int,
        source_offline_store_manifest_hash: str,
        scene_id: str | None = None,
        snippet_id: str | None = None,
        split: str | None = None,
    ) -> None:
        """Validate one rollout-to-source join without reading actor arrays.

        The check binds a rollout to the exact immutable manifest, sample,
        shard row, and optional scene/snippet/split facts. Any mismatch fails
        before :class:`aria_nbv.data_handling.qh.QhDataset` can create a
        training sample.

        Args:
            index: Actor-source index to validate.
            source_sample_index: Expected global VIN source index.
            source_sample_key: Expected stable VIN sample key.
            source_shard_id: Expected immutable VIN shard id.
            source_shard_row: Expected row within the VIN shard.
            source_offline_store_version: Expected strict store-format version.
            source_offline_store_manifest_hash: Expected complete manifest hash.
            scene_id: Expected ASE scene id when validating a rollout join.
            snippet_id: Expected ATEK snippet id when validating a rollout join.
            split: Expected immutable source split when validating a rollout join.
        """

        record = self._record(index)
        actual = {
            "source_sample_index": record.sample_index,
            "source_sample_key": record.sample_key,
            "source_shard_id": record.shard_id,
            "source_shard_row": record.row,
            "source_offline_store_version": self.source_offline_store_version,
            "source_offline_store_manifest_hash": self.source_offline_store_manifest_hash,
        }
        expected = {
            "source_sample_index": source_sample_index,
            "source_sample_key": source_sample_key,
            "source_shard_id": source_shard_id,
            "source_shard_row": source_shard_row,
            "source_offline_store_version": str(source_offline_store_version),
            "source_offline_store_manifest_hash": source_offline_store_manifest_hash,
        }
        actual["source_sample_key"] = compact_ase_atek_sample_id(actual["source_sample_key"])
        expected["source_sample_key"] = compact_ase_atek_sample_id(expected["source_sample_key"])
        if scene_id is not None:
            actual["scene_id"] = record.scene_id
            expected["scene_id"] = scene_id
        if snippet_id is not None:
            actual["snippet_id"] = compact_ase_atek_sample_id(record.snippet_id)
            expected["snippet_id"] = compact_ase_atek_sample_id(snippet_id)
        if split is not None:
            actual["split"] = record.split
            expected["split"] = split
        mismatches = [
            f"{name}: expected={expected[name]!r}, actual={actual[name]!r}"
            for name in actual
            if actual[name] != expected[name]
        ]
        if mismatches:
            raise ValueError(f"VIN actor source lineage mismatch ({'; '.join(mismatches)}). {self._REBUILD_GUIDANCE}")

    def _record(self, index: int) -> VinOfflineIndexRecord:
        """Normalize one Python index and return its preflighted source record."""

        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(f"VIN actor source index {index} is outside source length {len(self)}.")
        return self._records[index]

    def _reader_for_process(self) -> VinOfflineStoreReader:
        """Return the current process's lazily constructed immutable reader."""

        pid = os.getpid()
        if self._reader is None or self._reader_pid != pid:
            reader = VinOfflineStoreReader(self.config.store)
            manifest_hash = stable_msgspec_hash(reader.manifest)
            if manifest_hash != self.source_offline_store_manifest_hash:
                raise ValueError(
                    f"VIN offline manifest changed after actor-source preflight. {self._REBUILD_GUIDANCE}",
                )
            self._reader = reader
            self._reader_pid = pid
        return self._reader

    def _validate_store(self, reader: VinOfflineStoreReader) -> None:
        """Validate index addresses and required numeric blocks once at setup."""

        if reader.manifest.version != OFFLINE_DATASET_VERSION:
            raise ValueError(f"Unsupported VIN offline store version. {self._REBUILD_GUIDANCE}")
        if len(reader.sample_index) != len({record.sample_index for record in reader.sample_index}):
            raise ValueError(f"VIN sample indices must be unique. {self._REBUILD_GUIDANCE}")
        for record in self._records:
            shard = self._shards.get(record.shard_id)
            if shard is None:
                raise ValueError(
                    f"VIN sample {record.sample_key!r} references unknown shard {record.shard_id!r}. "
                    f"{self._REBUILD_GUIDANCE}",
                )
            if record.row < 0 or record.row >= shard.num_rows:
                raise ValueError(
                    f"VIN sample {record.sample_key!r} references invalid shard row {record.row}. "
                    f"{self._REBUILD_GUIDANCE}",
                )
            self._validate_required_blocks(record, shard)

    def _validate_required_blocks(self, record: VinOfflineIndexRecord, shard: VinOfflineShardSpec) -> None:
        """Require actor blocks to exist as numeric arrays in every selected shard."""

        for name in _PROFILE_REQUIRED_BLOCKS:
            block = shard.blocks.get(name)
            if block is None:
                raise ValueError(
                    f"Required actor block {name!r} is missing for sample {record.sample_key!r}. "
                    f"{self._REBUILD_GUIDANCE}",
                )
            if block.kind != "zarr_array":
                raise ValueError(
                    f"Actor block {name!r} must be a numeric Zarr array, not {block.kind!r}. {self._REBUILD_GUIDANCE}",
                )


__all__ = ["VinActorSample", "VinActorSource", "VinActorSourceConfig"]
