"""Deterministic JSONL shard manifests for rollout generation.

Rollout shard manifests split VIN offline source rows into Slurm-friendly work
units. Each JSONL row owns one rollout shard and lists the ordered VIN sample
rows that the shard must process. The manifest is intentionally small and
human-inspectable; heavy rollout data remains in standalone Zarr stores.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROLLOUT_SHARD_MANIFEST_VERSION = "rollout-shard-manifest-v1"
"""Version label for rollout generation JSONL shard manifests."""

ROLLOUT_SHARD_SUCCESS_FILENAME = "_SUCCESS.json"
"""Completion marker written last for a validated rollout shard."""

ROLLOUT_SHARD_OWNER_FILENAME = "_owner.json"
"""Shard owner/provenance sidecar written before final promotion."""


@dataclass(frozen=True, slots=True)
class RolloutShardRow:
    """One VIN offline source row owned by a rollout shard."""

    order: int
    """Zero-based processing order within this generated rollout shard."""

    sample_index: int
    """Stable VIN dataset sample index used to reopen the source row."""

    sample_key: str
    """Canonical VIN sample key used to reject index drift."""

    scene_id: str
    """Source scene identifier persisted into rollout lineage."""

    snippet_id: str
    """Source snippet identifier persisted into rollout lineage."""

    split: str
    """VIN dataset split; all rows in one entry must share it."""

    source_shard_id: str
    """Identifier of the immutable VIN storage shard containing the row."""

    source_shard_row: int
    """Zero-based row within ``source_shard_id``."""

    @classmethod
    def from_index_record(cls, record: Any, *, order: int) -> "RolloutShardRow":
        """Build a manifest row from a VIN offline index record."""

        return cls(
            order=int(order),
            sample_index=int(record.sample_index),
            sample_key=str(record.sample_key),
            scene_id=str(record.scene_id),
            snippet_id=str(record.snippet_id),
            split=str(record.split),
            source_shard_id=str(record.shard_id),
            source_shard_row=int(record.row),
        )

    @classmethod
    def from_jsonable(cls, payload: dict[str, Any]) -> "RolloutShardRow":
        """Decode one JSON row while restoring numeric lineage fields.

        Args:
            payload: Mapping emitted by :meth:`to_jsonable`.

        Returns:
            Typed source-row ownership record. Entry-level validation checks
            split consistency and contiguous ordering after decoding.
        """

        return cls(
            order=int(payload["order"]),
            sample_index=int(payload["sample_index"]),
            sample_key=str(payload["sample_key"]),
            scene_id=str(payload["scene_id"]),
            snippet_id=str(payload["snippet_id"]),
            split=str(payload["split"]),
            source_shard_id=str(payload["source_shard_id"]),
            source_shard_row=int(payload["source_shard_row"]),
        )

    def to_jsonable(self) -> dict[str, Any]:
        """Return a stable JSON-compatible row payload."""

        return {
            "order": int(self.order),
            "sample_index": int(self.sample_index),
            "sample_key": self.sample_key,
            "scene_id": self.scene_id,
            "snippet_id": self.snippet_id,
            "split": self.split,
            "source_shard_id": self.source_shard_id,
            "source_shard_row": int(self.source_shard_row),
        }

    def hash_record(self) -> dict[str, object]:
        """Return the row fields used for deterministic lineage hashing."""

        return self.to_jsonable()

    def matches_record(self, record: Any) -> bool:
        """Return whether a VIN offline index record matches this manifest row."""

        return (
            int(record.sample_index) == int(self.sample_index)
            and str(record.sample_key) == self.sample_key
            and str(record.scene_id) == self.scene_id
            and str(record.snippet_id) == self.snippet_id
            and str(record.split) == self.split
            and str(record.shard_id) == self.source_shard_id
            and int(record.row) == int(self.source_shard_row)
        )


@dataclass(frozen=True, slots=True)
class RolloutShardEntry:
    """One deterministic rollout generation shard entry."""

    shard_id: str
    """Canonical ``shard-000000`` style rollout-generation identifier."""

    split: str
    """VIN dataset split shared by all owned source rows."""

    rows: tuple[RolloutShardRow, ...]
    """Ordered immutable VIN source rows assigned to this output shard."""

    writer_config_hash: str
    """Hash of the complete writer configuration used for drift rejection."""

    source_manifest_hash: str
    """Hash of the immutable VIN offline-store manifest."""

    source_cache_version: str
    """VIN source cache schema/version recorded in generated lineage."""

    split_manifest_hash: str
    """Hash binding split name and ordered source-row records."""

    source_store_dir: str
    """Resolved VIN source-store directory used when the manifest was planned."""

    manifest_version: str = ROLLOUT_SHARD_MANIFEST_VERSION
    """JSONL ownership-contract version."""

    @classmethod
    def from_jsonable(cls, payload: dict[str, Any]) -> "RolloutShardEntry":
        """Decode and canonicalize one JSONL shard ownership entry.

        Args:
            payload: Parsed JSON object containing source rows and provenance
                hashes.

        Returns:
            Typed entry. Call :meth:`validate` before using it to build a
            rollout store.
        """

        return cls(
            manifest_version=str(payload["manifest_version"]),
            shard_id=canonical_rollout_shard_id(str(payload["shard_id"])),
            split=str(payload["split"]),
            rows=tuple(RolloutShardRow.from_jsonable(row) for row in payload["rows"]),
            writer_config_hash=str(payload["writer_config_hash"]),
            source_manifest_hash=str(payload["source_manifest_hash"]),
            source_cache_version=str(payload["source_cache_version"]),
            split_manifest_hash=str(payload["split_manifest_hash"]),
            source_store_dir=str(payload["source_store_dir"]),
        )

    def to_jsonable(self) -> dict[str, Any]:
        """Return a stable JSON-compatible shard payload."""

        return {
            "manifest_version": self.manifest_version,
            "shard_id": self.shard_id,
            "split": self.split,
            "num_rows": len(self.rows),
            "writer_config_hash": self.writer_config_hash,
            "source_manifest_hash": self.source_manifest_hash,
            "source_cache_version": self.source_cache_version,
            "split_manifest_hash": self.split_manifest_hash,
            "source_store_dir": self.source_store_dir,
            "rows": [row.to_jsonable() for row in self.rows],
        }

    def validate(self) -> None:
        """Raise when the entry violates the shard-manifest contract."""

        if self.manifest_version != ROLLOUT_SHARD_MANIFEST_VERSION:
            raise ValueError(
                f"Unsupported rollout shard manifest_version={self.manifest_version!r}; "
                f"expected {ROLLOUT_SHARD_MANIFEST_VERSION!r}."
            )
        if not self.rows:
            raise ValueError(f"Rollout shard {self.shard_id!r} has no source rows.")
        splits = {row.split for row in self.rows}
        if splits != {self.split}:
            raise ValueError(f"Rollout shard {self.shard_id!r} mixes row splits {sorted(splits)}.")
        orders = [row.order for row in self.rows]
        if orders != list(range(len(self.rows))):
            raise ValueError(f"Rollout shard {self.shard_id!r} row order must be contiguous from zero.")
        if any(not row.source_shard_id for row in self.rows):
            raise ValueError(f"Rollout shard {self.shard_id!r} contains an empty source_shard_id.")
        if any(row.source_shard_row < 0 for row in self.rows):
            raise ValueError(f"Rollout shard {self.shard_id!r} contains a negative source_shard_row.")


def canonical_rollout_shard_id(value: str | int) -> str:
    """Return the canonical ``shard-000000`` style rollout shard id."""

    raw = str(value)
    if raw.startswith("shard-"):
        suffix = raw.removeprefix("shard-")
        if suffix.isdigit():
            return f"shard-{int(suffix):06d}"
        return raw
    if raw.isdigit():
        return f"shard-{int(raw):06d}"
    return raw


def write_rollout_shard_manifest(path: Path | str, entries: list[RolloutShardEntry]) -> None:
    """Write rollout shard entries as stable JSONL."""

    output_path = Path(path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(entry.to_jsonable(), ensure_ascii=True, sort_keys=True) for entry in entries]
    payload = "\n".join(lines)
    if payload:
        payload += "\n"
    output_path.write_text(payload, encoding="utf-8")


def read_rollout_shard_manifest(path: Path | str) -> list[RolloutShardEntry]:
    """Read and validate all entries in a rollout shard JSONL manifest.

    Blank lines are ignored. Malformed rows, duplicate shard ids, mixed splits,
    or non-contiguous row ownership fail before any rollout generation begins.
    """

    manifest_path = Path(path).expanduser().resolve()
    entries: list[RolloutShardEntry] = []
    seen_shard_ids: set[str] = set()
    for line_no, line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entry = RolloutShardEntry.from_jsonable(json.loads(line))
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid rollout shard manifest line {line_no} in {manifest_path}: {exc}") from exc
        entry.validate()
        if entry.shard_id in seen_shard_ids:
            raise ValueError(f"Duplicate rollout shard id {entry.shard_id!r} in {manifest_path}.")
        seen_shard_ids.add(entry.shard_id)
        entries.append(entry)
    return entries


def load_rollout_shard_entry(path: Path | str, shard_id: str | int) -> RolloutShardEntry:
    """Load one validated manifest entry by canonical or numeric shard id.

    Args:
        path: Rollout shard JSONL manifest.
        shard_id: Numeric id or canonical ``shard-000000`` token.

    Returns:
        Matching validated ownership entry.

    Raises:
        KeyError: If the requested shard is absent from the manifest.
    """

    canonical = canonical_rollout_shard_id(shard_id)
    for entry in read_rollout_shard_manifest(path):
        if entry.shard_id == canonical:
            return entry
    raise KeyError(f"Rollout shard {canonical!r} was not found in {Path(path).expanduser().resolve()}.")


__all__ = [
    "ROLLOUT_SHARD_MANIFEST_VERSION",
    "ROLLOUT_SHARD_OWNER_FILENAME",
    "ROLLOUT_SHARD_SUCCESS_FILENAME",
    "RolloutShardEntry",
    "RolloutShardRow",
    "canonical_rollout_shard_id",
    "load_rollout_shard_entry",
    "read_rollout_shard_manifest",
    "write_rollout_shard_manifest",
]
