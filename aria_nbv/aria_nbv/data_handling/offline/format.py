"""Typed manifest and index records for the VIN offline dataset format.

The new offline dataset format is an immutable indexed-shard layout optimized
for multi-worker random access. This module owns the normalized metadata
records shared by the writer and runtime dataset reader:

- the top-level dataset manifest,
- per-shard block descriptors, and
- sample-index records used for global random access and split membership.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Self

import msgspec


@dataclass(slots=True)
class VinOfflineBlockSpec:
    """Descriptor for one stored block inside a shard.

    Attributes:
        name: Logical block name, for example ``"vin.points_world"``.
        kind: Storage kind such as ``"zarr_array"`` or
            ``"msgpack_indexed_records"``.
        paths: Relative array names or file paths that materialize the block.
        dtype: NumPy dtype name for numeric blocks.
        shape: Full stored array shape for numeric blocks.
        optional: Whether the block may be absent for some datasets.
    """

    name: str
    """Stable dotted block key, such as ``vin.points_world`` or ``oracle.rri``."""

    kind: str
    """Decoder contract: ``zarr_array`` or ``msgpack_indexed_records``."""

    paths: list[str]
    """Shard-relative Zarr path or MessagePack payload/offset file pair."""

    dtype: str | None = None
    """Exact NumPy dtype name for numeric blocks; ``None`` for record payloads."""

    shape: list[int] | None = None
    """Full persisted shape including the leading shard-row axis."""

    optional: bool = False
    """Whether the block may be absent in a valid dataset."""

    @staticmethod
    def zarr_array_path(name: str) -> str:
        """Return the hierarchical Zarr path for a logical block name.

        Args:
            name: Logical block name, for example ``"oracle.p3d.R"``.

        Returns:
            Zarr array path relative to the shard root.
        """

        return name.replace(".", "/")

    @staticmethod
    def msgpack_records_path(name: str) -> str:
        """Return the msgpack filename used for one logical record block.

        Args:
            name: Logical block name.

        Returns:
            Shard-local msgpack filename.
        """

        safe_stem = name.replace("/", "__").replace(".", "__")
        return f"{safe_stem}.msgpack"

    @staticmethod
    def msgpack_records_offsets_path(name: str) -> str:
        """Return the offsets filename used for indexed record blocks.

        Args:
            name: Logical block name.

        Returns:
            Shard-local NumPy offsets filename.
        """

        safe_stem = name.replace("/", "__").replace(".", "__")
        return f"{safe_stem}.offsets.npy"

    @classmethod
    def for_zarr_array(
        cls,
        *,
        name: str,
        array_path: str,
        dtype: str,
        shape: list[int],
        optional: bool = False,
    ) -> Self:
        """Build a block descriptor for one Zarr-backed numeric array.

        Args:
            name: Logical block name.
            array_path: Relative Zarr array path inside the shard.
            dtype: Stored NumPy dtype name.
            shape: Full stored array shape.
            optional: Whether the block is optional.

        Returns:
            Block descriptor for the stored array.
        """

        return cls(
            name=name,
            kind="zarr_array",
            paths=[array_path],
            dtype=dtype,
            shape=shape,
            optional=optional,
        )

    @classmethod
    def for_indexed_msgpack_records(
        cls,
        *,
        name: str,
        relative_payload_path: str,
        relative_offsets_path: str,
        num_records: int,
        optional: bool = True,
    ) -> Self:
        """Build a block descriptor for indexed per-row MessagePack records.

        Args:
            name: Logical block name.
            relative_payload_path: Shard-local concatenated payload blob path.
            relative_offsets_path: Shard-local NumPy offsets path.
            num_records: Number of stored per-row records.
            optional: Whether the block is optional.

        Returns:
            Block descriptor for the indexed record block.
        """

        return cls(
            name=name,
            kind="msgpack_indexed_records",
            paths=[relative_payload_path, relative_offsets_path],
            dtype=None,
            shape=[num_records],
            optional=optional,
        )


@dataclass(slots=True)
class VinOfflineShardSpec:
    """Descriptor for one immutable dataset shard.

    Attributes:
        shard_id: Stable shard identifier, for example ``"shard-000003"``.
        relative_dir: Relative directory containing the shard files.
        row_start: Global row offset covered by the shard.
        num_rows: Number of samples stored in the shard.
        blocks: Stored block descriptors keyed by logical block name.
    """

    shard_id: str
    """Stable shard identifier."""

    relative_dir: str
    """Relative directory that contains shard artifacts."""

    row_start: int
    """Global row offset covered by this shard."""

    num_rows: int
    """Number of samples stored in this shard."""

    blocks: dict[str, VinOfflineBlockSpec] = field(default_factory=dict)
    """Stored block descriptors keyed by logical block name."""


@dataclass(slots=True)
class VinOfflineMaterializedBlocks:
    """Declare optional payload families present in a VIN offline store.

    The flags describe store-wide availability, while each shard's
    :class:`VinOfflineBlockSpec` entries remain the authoritative physical
    inventory. Backbone and detected-OBB blocks are actor-visible EVL evidence;
    GT OBBs and candidate depths remain oracle supervision or diagnostics.
    """

    backbone: bool
    """Whether checkpoint-dependent EVL voxel/evidence outputs are materialized."""

    depths: bool
    """Whether oracle-rendered candidate depth maps and validity masks are materialized."""

    candidate_pcs: bool
    """Whether oracle candidate point-cloud diagnostic records are materialized."""

    gt_obbs: bool = False
    """Whether ASE GT OBB label/evaluation blocks are materialized."""

    detected_obbs: bool = False
    """Whether actor-visible EVL detected-OBB blocks are materialized."""

    trajectory: bool = False
    """Whether MPS/EFM pose timestamps and world-frame gravity are materialized."""


@dataclass(slots=True)
class VinOfflineManifest:
    """Top-level manifest for one immutable VIN offline dataset.

    Attributes:
        version: Dataset-format version.
        created_at: UTC creation timestamp.
        source: Raw dataset provenance and configuration snapshot.
        oracle: Oracle-label pipeline provenance and storage policy.
        vin: VIN-specific materialization settings.
        materialized_blocks: Flags for optional stored blocks.
        stats: Aggregate dataset statistics.
        provenance: Writer provenance and build hints.
        shards: Immutable shard descriptors.
    """

    version: int
    """Strict dataset-format version checked against :data:`OFFLINE_DATASET_VERSION`."""

    created_at: str
    """UTC creation timestamp."""

    source: dict[str, Any]
    """ATEK/ASE source config and signature for shard, scene, and mesh lineage."""

    oracle: dict[str, Any]
    """Oracle/EVL config signatures, resolved asset paths, and candidate policy.

    The signatures hash serialized configuration, not checkpoint contents.
    """

    vin: dict[str, Any]
    """VIN point padding and MPS semidense-collapse settings used by the writer."""

    materialized_blocks: VinOfflineMaterializedBlocks
    """Flags describing which optional blocks are materialized."""

    stats: dict[str, Any] = field(default_factory=dict)
    """Build counts for samples, shards, split membership, and interruption state."""

    provenance: dict[str, Any] = field(default_factory=dict)
    """Writer identity, split policy, destination, and finalization provenance."""

    shards: list[VinOfflineShardSpec] = field(default_factory=list)
    """Immutable shard descriptors."""

    def write(self, path: Path) -> None:
        """Persist the manifest to disk.

        Args:
            path: Destination manifest path.
        """

        path.write_bytes(msgspec.json.encode(self))

    @classmethod
    def read(cls, path: Path) -> "VinOfflineManifest":
        """Load a manifest from disk.

        Args:
            path: Manifest JSON path.

        Returns:
            Deserialized manifest.
        """

        return msgspec.json.decode(path.read_bytes(), type=cls)


@dataclass(slots=True)
class VinOfflineIndexRecord:
    """Global sample-index entry for VIN offline random access.

    Attributes:
        sample_index: Global zero-based sample index.
        sample_key: Stable dataset sample key.
        scene_id: ASE scene identifier.
        snippet_id: ASE snippet identifier.
        split: Canonical split membership: ``all``, ``train``, or ``val``.
        shard_id: Shard that stores the sample.
        row: Zero-based row offset inside the shard.
    """

    sample_index: int
    """Global zero-based sample index."""

    sample_key: str
    """Stable compact ASE/ATEK sample key, independent of iteration order."""

    scene_id: str
    """ASE scene identifier used for mesh pairing and scene-disjoint lineage."""

    snippet_id: str
    """Compact ATEK sample identifier originating from a WebDataset shard key."""

    split: str
    """Deterministic ``train`` or ``val`` membership; ``all`` is the union view."""

    shard_id: str
    """Shard that stores the sample."""

    row: int
    """Zero-based row offset inside the shard."""

    @classmethod
    def read_many(cls, path: Path) -> list[Self]:
        """Read the global sample index.

        Args:
            path: ``sample_index.jsonl`` path.

        Returns:
            Parsed sample-index records.
        """

        records: list[Self] = []
        for line in path.read_bytes().splitlines():
            if line.strip():
                records.append(msgspec.json.decode(line, type=cls))
        return records

    @classmethod
    def write_many(cls, path: Path, records: list[Self]) -> None:
        """Write the global sample index.

        Args:
            path: Destination ``sample_index.jsonl`` path.
            records: Global sample-index records to persist.
        """

        payload = b"\n".join(msgspec.json.encode(record) for record in records)
        if payload:
            payload += b"\n"
        path.write_bytes(payload)


__all__ = [
    "VinOfflineBlockSpec",
    "VinOfflineIndexRecord",
    "VinOfflineManifest",
    "VinOfflineMaterializedBlocks",
    "VinOfflineShardSpec",
]
