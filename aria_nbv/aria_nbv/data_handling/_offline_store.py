"""Low-level storage primitives for the VIN offline dataset format.

This module owns the immutable on-disk layout of the VIN offline dataset:

- path and split configuration,
- per-shard block materialization helpers,
- manifest and sample-index loading, and
- Zarr-backed random-access reads for fixed-size tensor blocks.
- indexed per-row MessagePack reads for optional diagnostic payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path  # noqa: TC003 - Pydantic config annotations need Path at runtime.
from typing import Any

import msgspec
import numpy as np
import zarr
from pydantic import Field, field_validator

from ..configs import PathConfig
from ..utils import BaseConfig
from ..utils.config_paths import resolve_cache_artifact_dir
from ._offline_format import (
    VinOfflineBlockSpec,
    VinOfflineIndexRecord,
    VinOfflineManifest,
    VinOfflineShardSpec,
)

OFFLINE_DATASET_VERSION = 7
"""Version of the immutable VIN offline dataset format."""


class VinOfflineStoreConfig(BaseConfig):
    """Filesystem configuration for one immutable VIN offline dataset."""

    paths: PathConfig = Field(default_factory=PathConfig)
    """Project path resolver."""

    store_dir: Path = Field(default_factory=lambda: PathConfig().offline_cache_dir / "vin_offline")
    """Root directory containing the immutable VIN offline dataset."""

    manifest_filename: str = "manifest.json"
    """Filename of the top-level manifest."""

    sample_index_filename: str = "sample_index.jsonl"
    """Filename of the global sample index."""

    shards_dirname: str = "shards"
    """Directory containing immutable shard subdirectories."""

    splits_dirname: str = "splits"
    """Directory containing split membership arrays."""

    _resolve_store_dir = field_validator("store_dir", mode="before")(resolve_cache_artifact_dir)

    @property
    def manifest_path(self) -> Path:
        """Return the resolved path to the store-owned ``manifest.json``."""

        return self.store_dir / self.manifest_filename

    @property
    def sample_index_path(self) -> Path:
        """Return the resolved path to the global ``sample_index.jsonl``."""

        return self.store_dir / self.sample_index_filename

    @property
    def shards_dir(self) -> Path:
        """Return the absolute shard root directory."""

        return self.store_dir / self.shards_dirname

    @property
    def splits_dir(self) -> Path:
        """Return the absolute split-array directory."""

        return self.store_dir / self.splits_dirname

    def split_path(self, split: str) -> Path:
        """Return the split-array path for one split.

        Args:
            split: Split name such as ``"all"``, ``"train"``, or ``"val"``.

        Returns:
            Absolute split-array path.
        """

        return self.splits_dir / f"{split}.npy"

    def write_split_indices(self, split_to_indices: dict[str, np.ndarray]) -> None:
        """Persist split membership arrays.

        Args:
            split_to_indices: Split membership arrays keyed by split name.
        """

        self.splits_dir.mkdir(parents=True, exist_ok=True)
        for split, indices in split_to_indices.items():
            np.save(self.split_path(split), np.asarray(indices, dtype=np.int64), allow_pickle=False)

    def read_split_indices(self, split: str) -> np.ndarray:
        """Load the global sample indices for one split.

        Args:
            split: Split name such as ``"all"``, ``"train"``, or ``"val"``.

        Returns:
            Global sample indices for the requested split.
        """

        return np.load(self.split_path(split), allow_pickle=False)


@dataclass(slots=True)
class VinOfflineShardWriter:
    """Materialize one immutable shard for the VIN offline dataset."""

    shard_dir: Path
    """Destination shard directory."""

    @staticmethod
    def _row_chunk_shape(array: np.ndarray) -> tuple[int, ...]:
        """Choose a chunk shape aligned with row-wise random-access reads.

        Args:
            array: Stacked block array whose first axis is the sample row axis.

        Returns:
            Chunk shape used for the stored Zarr array.
        """

        if array.ndim <= 1:
            return (min(int(array.shape[0]), 1024),)
        return (1, *array.shape[1:])

    def write_numeric_block(self, name: str, array: np.ndarray) -> VinOfflineBlockSpec:
        """Write one fixed-size numeric block into the shard Zarr group.

        Args:
            name: Logical block name.
            array: NumPy array to store.

        Returns:
            Block descriptor for the stored array.
        """

        group = zarr.open_group(str(self.shard_dir), mode="a")
        rel_path = VinOfflineBlockSpec.zarr_array_path(name)
        zarr_array = group.create_array(
            name=rel_path,
            shape=array.shape,
            chunks=self._row_chunk_shape(array),
            dtype=array.dtype,
            overwrite=True,
        )
        zarr_array[:] = array
        return VinOfflineBlockSpec.for_zarr_array(
            name=name,
            array_path=rel_path,
            dtype=str(array.dtype),
            shape=list(array.shape),
        )

    def write_record_block(self, name: str, records: list[Any]) -> VinOfflineBlockSpec:
        """Write one indexed per-row diagnostic record block for the shard.

        Args:
            name: Logical block name.
            records: Per-row msgspec-compatible payload objects.

        Returns:
            Block descriptor for the stored indexed record block.
        """

        payload_rel_path = VinOfflineBlockSpec.msgpack_records_path(name)
        offsets_rel_path = VinOfflineBlockSpec.msgpack_records_offsets_path(name)
        encoded_records: list[bytes] = []
        for index, record in enumerate(records):
            try:
                encoded_records.append(msgspec.msgpack.encode(record))
            except TypeError as exc:
                raise TypeError(f"Failed to encode record block {name!r} row {index}.") from exc

        offsets = np.zeros((len(records) + 1,), dtype=np.int64)
        with (self.shard_dir / payload_rel_path).open("wb") as handle:
            for index, payload in enumerate(encoded_records, start=1):
                handle.write(payload)
                offsets[index] = offsets[index - 1] + len(payload)
        np.save(self.shard_dir / offsets_rel_path, offsets, allow_pickle=False)
        return VinOfflineBlockSpec.for_indexed_msgpack_records(
            name=name,
            relative_payload_path=payload_rel_path,
            relative_offsets_path=offsets_rel_path,
            num_records=len(records),
        )


@dataclass(slots=True)
class IndexedMsgpackRecordBlock:
    """Indexed per-row MessagePack record block stored for one shard."""

    payload_path: Path
    """Shard-local concatenated payload blob path."""

    offsets: np.ndarray
    """``ndarray["N_rows+1", int64]`` byte boundaries into the payload blob."""

    def read(self, row: int) -> Any:
        """Read and decode one record by row index."""

        if row < 0 or row + 1 >= int(self.offsets.shape[0]):
            raise IndexError("Record row out of range.")
        start = int(self.offsets[row])
        end = int(self.offsets[row + 1])
        if end < start:
            raise ValueError("Indexed record offsets are invalid.")
        with self.payload_path.open("rb") as handle:
            handle.seek(start)
            payload = handle.read(end - start)
        return msgspec.msgpack.decode(payload)


@dataclass(slots=True)
class OpenedShard:
    """Hold lazily opened, worker-local handles for one immutable shard.

    Instances belong to one :class:`VinOfflineStoreReader` process and are not
    persisted or shared across DataLoader workers. The manifest descriptor owns
    physical layout; this object only caches read-only Zarr and MessagePack
    handles for repeated row access.
    """

    spec: VinOfflineShardSpec
    """Shard descriptor backing the opened state."""

    arrays: dict[str, Any] = field(default_factory=dict)
    """Read-only Zarr arrays keyed by manifest logical block name."""

    indexed_record_blocks: dict[str, IndexedMsgpackRecordBlock] = field(default_factory=dict)
    """Worker-local indexed MessagePack readers keyed by logical block name."""


class VinOfflineStoreReader:
    """Read immutable VIN offline datasets with Zarr-backed random access."""

    def __init__(self, config: VinOfflineStoreConfig) -> None:
        """Load the manifest, sample index, and split metadata.

        Args:
            config: Store configuration pointing at an immutable dataset.
        """

        self.config = config
        self.manifest = VinOfflineManifest.read(config.manifest_path)
        if self.manifest.version != OFFLINE_DATASET_VERSION:
            raise ValueError(
                "Unsupported VIN offline dataset version "
                f"{self.manifest.version}; expected {OFFLINE_DATASET_VERSION}. "
                "Rebuild the store with the current VIN offline writer.",
            )
        self.sample_index = VinOfflineIndexRecord.read_many(config.sample_index_path)
        self._records_by_sample_index = {record.sample_index: record for record in self.sample_index}
        self._shards = {spec.shard_id: spec for spec in self.manifest.shards}
        self._opened: dict[str, OpenedShard] = {}
        self._split_cache: dict[str, np.ndarray] = {}

    def get_split_records(self, split: str) -> list[VinOfflineIndexRecord]:
        """Return index records for the requested split.

        Args:
            split: Split name such as ``"all"``, ``"train"``, or ``"val"``.

        Returns:
            Ordered index records for the split.
        """

        if split not in self._split_cache:
            self._split_cache[split] = self.config.read_split_indices(split)
        return [self._records_by_sample_index[int(idx)] for idx in self._split_cache[split]]

    def _open_shard(self, shard_id: str) -> OpenedShard:
        """Open one shard and cache its Zarr-backed blocks.

        Args:
            shard_id: Stable shard identifier.

        Returns:
            Worker-local opened shard handle.
        """

        opened = self._opened.get(shard_id)
        if opened is not None:
            return opened

        spec = self._shards[shard_id]
        shard_dir = self.config.store_dir / spec.relative_dir
        opened = OpenedShard(spec=spec)
        group = zarr.open_group(store=zarr.storage.LocalStore(str(shard_dir), read_only=True), mode="r")
        for block_name, block_spec in spec.blocks.items():
            if block_spec.kind == "zarr_array":
                opened.arrays[block_name] = group[block_spec.paths[0]]
            elif block_spec.kind == "msgpack_indexed_records":
                opened.indexed_record_blocks[block_name] = IndexedMsgpackRecordBlock(
                    payload_path=shard_dir / block_spec.paths[0],
                    offsets=np.load(shard_dir / block_spec.paths[1], allow_pickle=False),
                )
            else:
                raise ValueError(
                    "Unsupported VIN offline block kind "
                    f"{block_spec.kind!r} for {block_name!r} in shard {shard_id!r}. "
                    "Rebuild the store with the current VIN offline writer.",
                )
        self._opened[shard_id] = opened
        return opened

    def read_numeric_block(self, record: VinOfflineIndexRecord, block_name: str) -> np.ndarray:
        """Read one numeric block row for a sample.

        Args:
            record: Global sample-index record.
            block_name: Logical block name.

        Returns:
            NumPy array view for the requested sample row.
        """

        opened = self._open_shard(record.shard_id)
        return np.asarray(opened.arrays[block_name][record.row])

    def read_optional_record(self, record: VinOfflineIndexRecord, block_name: str) -> Any | None:
        """Read one optional per-row diagnostic record.

        Args:
            record: Global sample-index record.
            block_name: Logical block name.

        Returns:
            Stored per-row Python object or ``None``.
        """

        opened = self._open_shard(record.shard_id)
        if block_name not in opened.spec.blocks:
            return None
        return opened.indexed_record_blocks[block_name].read(record.row)


__all__ = [
    "OFFLINE_DATASET_VERSION",
    "VinOfflineStoreConfig",
    "VinOfflineStoreReader",
]
