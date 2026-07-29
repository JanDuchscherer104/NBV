"""Append-only indexes over immutable validated rollout shards.

A collection is a small control-plane directory containing a JSONL ledger and
an atomically regenerated manifest.  Rollout Zarr shards remain independent,
read-only artifacts: registration validates their completion sidecars and
records their provenance without copying or modifying payload bytes.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import Any, BinaryIO

from .manifest import manifest_json_bytes, manifest_sha256, read_rollout_store_manifest, utc_timestamp
from .shard_manifest import ROLLOUT_SHARD_OWNER_FILENAME, ROLLOUT_SHARD_SUCCESS_FILENAME
from .zarr_store import RolloutZarrStoreReader, validate_rollout_zarr_store

ROLLOUT_COLLECTION_VERSION = "rollout-collection-v1"
"""Version of the immutable-shard collection contract."""

ROLLOUT_COLLECTION_LEDGER_FILENAME = "shards.jsonl"
"""Append-only registration ledger stored in a collection directory."""

ROLLOUT_COLLECTION_MANIFEST_FILENAME = "manifest.json"
"""Atomically regenerated snapshot of unique registered shards."""

_LOCK_FILENAME = ".collection.lock"
_LEDGER_EVENT_VERSION = "rollout-collection-registration-v1"
_COMPATIBILITY_FIELDS = (
    "schema_id",
    "schema_version",
    "reason_code_version",
    "target_protocol_version",
    "return_semantics",
)
_SIDECAR_SHARED_FIELDS = (
    "shard_id",
    "writer_config_hash",
    "source_manifest_hash",
    "split_manifest_hash",
    "source_cache_version",
    "split",
    "num_source_rows",
    "rollout_manifest_sha256",
)


class RolloutCollectionError(ValueError):
    """Reject an invalid shard, ledger, or collection compatibility change."""


@dataclass(frozen=True, order=True, slots=True)
class RolloutShardLogicalKey:
    """Scientific identity of one immutable rollout append unit.

    The key deliberately excludes filesystem paths and content hashes.  A
    second artifact claiming the same scientific unit is therefore either an
    idempotent registration of identical provenance or a rejected conflict.
    """

    campaign_id: str
    """Stable campaign identifier shared by all tranches."""

    split: str
    """Scene-level dataset split owned by the shard."""

    source_sample_key: str
    """Canonical VIN source-sample key for the rollout root."""

    target_id: str
    """Stable actor-visible target identity within the source sample."""

    candidate_profile: str
    """Named finite-candidate generation profile."""

    recipe_group: str
    """Named policy, horizon, and branching recipe group."""

    seed_group: str
    """Stable seed-family identity used for paired generation."""

    def __post_init__(self) -> None:
        """Reject empty key components before they reach the ledger."""

        for name, value in self.to_jsonable().items():
            if not value.strip():
                raise RolloutCollectionError(f"Logical shard key field {name!r} must be non-empty.")

    @classmethod
    def from_jsonable(cls, payload: dict[str, Any]) -> "RolloutShardLogicalKey":
        """Decode one logical key from a collection record."""

        try:
            return cls(
                campaign_id=str(payload["campaign_id"]),
                split=str(payload["split"]),
                source_sample_key=str(payload["source_sample_key"]),
                target_id=str(payload["target_id"]),
                candidate_profile=str(payload["candidate_profile"]),
                recipe_group=str(payload["recipe_group"]),
                seed_group=str(payload["seed_group"]),
            )
        except KeyError as exc:
            raise RolloutCollectionError(f"Logical shard key is missing field {exc.args[0]!r}.") from exc

    def to_jsonable(self) -> dict[str, str]:
        """Return the stable JSON representation used for ordering and hashing."""

        return {
            "campaign_id": self.campaign_id,
            "split": self.split,
            "source_sample_key": self.source_sample_key,
            "target_id": self.target_id,
            "candidate_profile": self.candidate_profile,
            "recipe_group": self.recipe_group,
            "seed_group": self.seed_group,
        }

    def canonical_id(self) -> str:
        """Return a compact deterministic identity for diagnostics."""

        encoded = json.dumps(self.to_jsonable(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class RolloutCollectionEntry:
    """One validated immutable shard registration."""

    logical_key: RolloutShardLogicalKey
    """Scientific identity used to reject duplicate conflicting artifacts."""

    shard_dir: Path
    """Resolved read-only shard directory referenced by the collection."""

    shard_id: str
    """Operational shard identifier from the owner sidecar."""

    rollout_manifest_sha256: str
    """Digest binding the shard's human-readable rollout manifest."""

    owner_sha256: str
    """Digest binding the immutable owner/provenance sidecar."""

    compatibility: dict[str, str]
    """Schema, invalidity, target-protocol, and return-semantics contract."""

    counts: dict[str, int]
    """Validated rollout, step, and candidate row counts."""

    registered_at_utc: str
    """UTC timestamp of the first successful registration."""

    def content_identity(self) -> tuple[str, str]:
        """Return the hashes that distinguish idempotence from conflict."""

        return self.rollout_manifest_sha256, self.owner_sha256

    def to_jsonable(self) -> dict[str, Any]:
        """Return a stable JSON-compatible snapshot row."""

        return {
            "logical_key": self.logical_key.to_jsonable(),
            "logical_key_id": self.logical_key.canonical_id(),
            "shard_dir": self.shard_dir.as_posix(),
            "shard_id": self.shard_id,
            "rollout_manifest_sha256": self.rollout_manifest_sha256,
            "owner_sha256": self.owner_sha256,
            "compatibility": dict(sorted(self.compatibility.items())),
            "counts": dict(sorted(self.counts.items())),
            "registered_at_utc": self.registered_at_utc,
        }


@dataclass(frozen=True, slots=True)
class RolloutCollectionSnapshot:
    """Deterministic materialized view of the append-only collection ledger."""

    collection_dir: Path
    """Resolved collection control-plane directory."""

    compatibility: dict[str, str]
    """Compatibility contract shared by every registered shard."""

    entries: tuple[RolloutCollectionEntry, ...]
    """Unique shard entries sorted by their logical keys."""

    ledger_sha256: str
    """Digest of the exact append-only ledger bytes used for this snapshot."""

    @property
    def counts(self) -> dict[str, int]:
        """Return row totals summed across unique validated shards."""

        names = ("rollouts", "steps", "candidates")
        return {name: sum(entry.counts[name] for entry in self.entries) for name in names}

    def to_jsonable(self) -> dict[str, Any]:
        """Return the deterministic collection-manifest payload."""

        return {
            "collection_version": ROLLOUT_COLLECTION_VERSION,
            "ledger_path": ROLLOUT_COLLECTION_LEDGER_FILENAME,
            "ledger_sha256": self.ledger_sha256,
            "compatibility": dict(sorted(self.compatibility.items())),
            "num_shards": len(self.entries),
            "counts": self.counts,
            "shards": [entry.to_jsonable() for entry in self.entries],
        }


@dataclass(frozen=True, slots=True)
class RolloutCollectionValidationResult:
    """Read-only validation result for a collection and its registered shards."""

    collection_dir: Path
    """Resolved collection directory checked by validation."""

    num_shards: int
    """Number of unique logical shards decoded from the ledger."""

    counts: dict[str, int]
    """Validated aggregate rollout, step, and candidate counts."""

    errors: tuple[str, ...] = field(default_factory=tuple)
    """Ledger, snapshot, compatibility, or shard validation failures."""

    @property
    def ok(self) -> bool:
        """Return ``True`` when the collection and all shard references validate."""

        return not self.errors


class RolloutCollection:
    """Register validated rollout shards without mutating their payloads.

    Registration is serialized by a local advisory lock.  Each successful new
    registration is durably appended to ``shards.jsonl`` before ``manifest.json``
    is regenerated through atomic replacement.  If snapshot replacement is
    interrupted, :meth:`rebuild_snapshot` deterministically recovers it from
    the authoritative ledger.
    """

    def __init__(self, collection_dir: Path | str) -> None:
        self.collection_dir = Path(collection_dir).expanduser().resolve()

    @property
    def ledger_path(self) -> Path:
        """Return the append-only JSONL ledger path."""

        return self.collection_dir / ROLLOUT_COLLECTION_LEDGER_FILENAME

    @property
    def manifest_path(self) -> Path:
        """Return the atomically regenerated snapshot path."""

        return self.collection_dir / ROLLOUT_COLLECTION_MANIFEST_FILENAME

    def register_shard(
        self,
        shard_dir: Path | str,
        *,
        logical_key: RolloutShardLogicalKey,
    ) -> RolloutCollectionEntry:
        """Validate and register one immutable completed rollout shard.

        Re-registering the same logical key with identical owner and rollout
        manifest hashes is idempotent.  The method rejects a different artifact
        claiming an existing logical key or any shard incompatible with the
        collection's schema and protocol contract.

        Args:
            shard_dir: Completed shard containing valid owner and success
                sidecars plus a validated standalone rollout Zarr store.
            logical_key: Scientific identity of the append unit.

        Returns:
            The existing or newly appended collection entry.
        """

        candidate = _validated_entry(Path(shard_dir), logical_key=logical_key)
        self.collection_dir.mkdir(parents=True, exist_ok=True)
        with self._locked_ledger() as ledger:
            events, ledger_bytes = _read_ledger(ledger)
            entries = _entries_from_events(events)
            existing = {entry.logical_key: entry for entry in entries}.get(logical_key)
            if existing is not None:
                if existing.content_identity() != candidate.content_identity():
                    raise RolloutCollectionError(
                        f"Logical shard key {logical_key.canonical_id()} is already registered with different hashes."
                    )
                _require_compatible(existing.compatibility, candidate.compatibility)
                self._write_snapshot(entries, ledger_bytes=ledger_bytes)
                return existing

            duplicate = next(
                (
                    entry
                    for entry in entries
                    if entry.shard_dir == candidate.shard_dir
                    or entry.content_identity() == candidate.content_identity()
                ),
                None,
            )
            if duplicate is not None:
                raise RolloutCollectionError(
                    f"Rollout shard {candidate.shard_id!r} is already registered under a different logical key."
                )
            if entries:
                _require_compatible(entries[0].compatibility, candidate.compatibility)
            event = _ledger_event(candidate, events=events)
            encoded = _jsonl_bytes(event)
            ledger.seek(0, os.SEEK_END)
            ledger.write(encoded)
            ledger.flush()
            os.fsync(ledger.fileno())
            entries.append(candidate)
            ledger_bytes += encoded
            self._write_snapshot(entries, ledger_bytes=ledger_bytes)
            return candidate

    def snapshot(self) -> RolloutCollectionSnapshot:
        """Decode the authoritative ledger into a deterministic sorted snapshot."""

        if not self.ledger_path.exists():
            return RolloutCollectionSnapshot(self.collection_dir, {}, (), hashlib.sha256(b"").hexdigest())
        with self._locked_ledger() as ledger:
            events, ledger_bytes = _read_ledger(ledger)
        return _snapshot(self.collection_dir, _entries_from_events(events), ledger_bytes=ledger_bytes)

    def rebuild_snapshot(self) -> RolloutCollectionSnapshot:
        """Validate ledger structure and atomically rebuild ``manifest.json``."""

        self.collection_dir.mkdir(parents=True, exist_ok=True)
        with self._locked_ledger() as ledger:
            events, ledger_bytes = _read_ledger(ledger)
            entries = _entries_from_events(events)
            return self._write_snapshot(entries, ledger_bytes=ledger_bytes)

    def validate(self) -> RolloutCollectionValidationResult:
        """Validate the ledger, snapshot, and every referenced immutable shard."""

        errors: list[str] = []
        try:
            snapshot = self.snapshot()
        except (OSError, RolloutCollectionError, json.JSONDecodeError) as exc:
            return RolloutCollectionValidationResult(self.collection_dir, 0, {}, (str(exc),))

        expected_payload = snapshot.to_jsonable()
        try:
            actual_payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            if actual_payload != expected_payload:
                errors.append("Collection manifest does not match the authoritative ledger snapshot.")
        except FileNotFoundError:
            errors.append("Collection manifest is missing; rebuild the snapshot from the ledger.")
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"Collection manifest cannot be read: {exc}.")

        for entry in snapshot.entries:
            try:
                current = _validated_entry(entry.shard_dir, logical_key=entry.logical_key)
                if current.content_identity() != entry.content_identity():
                    errors.append(f"Registered shard {entry.shard_id!r} no longer matches its ledger hashes.")
                _require_compatible(snapshot.compatibility, current.compatibility)
            except (OSError, RolloutCollectionError, json.JSONDecodeError) as exc:
                errors.append(f"Registered shard {entry.shard_id!r} is invalid: {exc}")

        return RolloutCollectionValidationResult(
            collection_dir=self.collection_dir,
            num_shards=len(snapshot.entries),
            counts=snapshot.counts,
            errors=tuple(errors),
        )

    def _write_snapshot(
        self,
        entries: list[RolloutCollectionEntry],
        *,
        ledger_bytes: bytes,
    ) -> RolloutCollectionSnapshot:
        snapshot = _snapshot(self.collection_dir, entries, ledger_bytes=ledger_bytes)
        _write_json_atomic(self.manifest_path, snapshot.to_jsonable())
        return snapshot

    def _locked_ledger(self) -> "_LockedLedger":
        self.collection_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.collection_dir / _LOCK_FILENAME
        lock = lock_path.open("a+b")
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        return _LockedLedger(lock, self.ledger_path)


class _LockedLedger:
    """Context manager holding the collection lock while a ledger is open."""

    def __init__(self, lock: BinaryIO, ledger_path: Path) -> None:
        self._lock = lock
        self._ledger_path = ledger_path
        self._ledger: BinaryIO | None = None

    def __enter__(self) -> BinaryIO:
        self._ledger = self._ledger_path.open("a+b")
        return self._ledger

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._ledger is not None:
            self._ledger.close()
        fcntl.flock(self._lock.fileno(), fcntl.LOCK_UN)
        self._lock.close()


def _validated_entry(shard_dir: Path, *, logical_key: RolloutShardLogicalKey) -> RolloutCollectionEntry:
    resolved = shard_dir.expanduser().resolve()
    validation = validate_rollout_zarr_store(resolved)
    if not validation.ok:
        raise RolloutCollectionError(f"Rollout shard validation failed: {validation.errors}")

    owner = _read_json_object(resolved / ROLLOUT_SHARD_OWNER_FILENAME)
    success = _read_json_object(resolved / ROLLOUT_SHARD_SUCCESS_FILENAME)
    manifest = read_rollout_store_manifest(resolved)
    if owner.get("sidecar_kind") != "rollout_shard_owner":
        raise RolloutCollectionError("Shard owner sidecar has an unsupported sidecar_kind.")
    if success.get("sidecar_kind") != "rollout_shard_success":
        raise RolloutCollectionError("Shard success sidecar has an unsupported sidecar_kind.")
    for field_name in _SIDECAR_SHARED_FIELDS:
        if owner.get(field_name) != success.get(field_name):
            raise RolloutCollectionError(f"Shard owner and success sidecars disagree on {field_name!r}.")

    owner_sha256 = manifest_sha256(owner)
    if success.get("owner_sha256") != owner_sha256:
        raise RolloutCollectionError("Shard success sidecar does not bind the owner sidecar hash.")
    rollout_manifest_sha256 = manifest_sha256(manifest)
    if owner.get("rollout_manifest_sha256") != rollout_manifest_sha256:
        raise RolloutCollectionError("Shard owner sidecar does not bind the rollout manifest hash.")
    if logical_key.split != str(owner.get("split", "")):
        raise RolloutCollectionError("Logical shard split does not match the owner sidecar split.")
    shard_entry = owner.get("shard_entry")
    if not isinstance(shard_entry, dict):
        raise RolloutCollectionError("Shard owner sidecar is missing its typed shard entry.")
    source_keys = {
        str(row.get("sample_key"))
        for row in shard_entry.get("rows", [])
        if isinstance(row, dict) and row.get("sample_key") is not None
    }
    if logical_key.source_sample_key not in source_keys:
        raise RolloutCollectionError("Logical source sample key is not owned by the shard entry.")
    if manifest.get("generation", {}).get("shard") != shard_entry:
        raise RolloutCollectionError("Rollout manifest shard provenance does not match the owner sidecar.")

    reader = RolloutZarrStoreReader(resolved)
    compatibility = {name: str(reader.root.attrs.get(name, "")) for name in _COMPATIBILITY_FIELDS}
    if any(not value for value in compatibility.values()):
        missing = [name for name, value in compatibility.items() if not value]
        raise RolloutCollectionError(f"Rollout shard is missing compatibility fields: {missing}.")
    counts = {
        "rollouts": int(validation.num_rollouts),
        "steps": int(validation.num_steps),
        "candidates": int(validation.num_candidates),
    }
    if owner.get("counts") != counts:
        raise RolloutCollectionError("Shard owner counts do not match fresh rollout-store validation.")
    return RolloutCollectionEntry(
        logical_key=logical_key,
        shard_dir=resolved,
        shard_id=str(owner["shard_id"]),
        rollout_manifest_sha256=rollout_manifest_sha256,
        owner_sha256=owner_sha256,
        compatibility=compatibility,
        counts=counts,
        registered_at_utc=utc_timestamp(),
    )


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RolloutCollectionError(f"Completed shard is missing required sidecar {path.name!r}.") from exc
    if not isinstance(payload, dict):
        raise RolloutCollectionError(f"Shard sidecar {path.name!r} must contain a JSON object.")
    return payload


def _ledger_event(entry: RolloutCollectionEntry, *, events: list[dict[str, Any]]) -> dict[str, Any]:
    previous_hash = str(events[-1]["record_sha256"]) if events else None
    payload: dict[str, Any] = {
        "event_version": _LEDGER_EVENT_VERSION,
        "sequence": len(events),
        "previous_record_sha256": previous_hash,
        "entry": entry.to_jsonable(),
    }
    payload["record_sha256"] = manifest_sha256(payload)
    return payload


def _read_ledger(ledger: BinaryIO) -> tuple[list[dict[str, Any]], bytes]:
    ledger.seek(0)
    ledger_bytes = ledger.read()
    events: list[dict[str, Any]] = []
    previous_hash: str | None = None
    for line_number, raw_line in enumerate(ledger_bytes.splitlines(), start=1):
        if not raw_line.strip():
            raise RolloutCollectionError(f"Collection ledger contains a blank row at line {line_number}.")
        payload = json.loads(raw_line)
        if not isinstance(payload, dict):
            raise RolloutCollectionError(f"Collection ledger row {line_number} must be a JSON object.")
        record_hash = payload.pop("record_sha256", None)
        expected_hash = manifest_sha256(payload)
        payload["record_sha256"] = record_hash
        if payload.get("event_version") != _LEDGER_EVENT_VERSION:
            raise RolloutCollectionError(f"Collection ledger row {line_number} has an unsupported event version.")
        if payload.get("sequence") != line_number - 1:
            raise RolloutCollectionError(f"Collection ledger row {line_number} has a non-contiguous sequence.")
        if payload.get("previous_record_sha256") != previous_hash:
            raise RolloutCollectionError(f"Collection ledger row {line_number} breaks the hash chain.")
        if record_hash != expected_hash:
            raise RolloutCollectionError(f"Collection ledger row {line_number} has an invalid record hash.")
        previous_hash = str(record_hash)
        events.append(payload)
    return events, ledger_bytes


def _entries_from_events(events: list[dict[str, Any]]) -> list[RolloutCollectionEntry]:
    entries: list[RolloutCollectionEntry] = []
    by_key: dict[RolloutShardLogicalKey, RolloutCollectionEntry] = {}
    by_shard_dir: dict[Path, RolloutCollectionEntry] = {}
    by_content: dict[tuple[str, str], RolloutCollectionEntry] = {}
    for event in events:
        entry = _entry_from_jsonable(event.get("entry"))
        existing = by_key.get(entry.logical_key)
        if existing is not None:
            if existing.content_identity() != entry.content_identity():
                raise RolloutCollectionError(
                    f"Collection ledger contains conflicting records for {entry.logical_key.canonical_id()}."
                )
            continue
        if entry.shard_dir in by_shard_dir or entry.content_identity() in by_content:
            raise RolloutCollectionError(
                f"Collection ledger registers shard {entry.shard_id!r} under multiple logical keys."
            )
        if entries:
            _require_compatible(entries[0].compatibility, entry.compatibility)
        by_key[entry.logical_key] = entry
        by_shard_dir[entry.shard_dir] = entry
        by_content[entry.content_identity()] = entry
        entries.append(entry)
    return entries


def _entry_from_jsonable(payload: object) -> RolloutCollectionEntry:
    if not isinstance(payload, dict):
        raise RolloutCollectionError("Collection ledger event is missing an entry object.")
    logical_payload = payload.get("logical_key")
    if not isinstance(logical_payload, dict):
        raise RolloutCollectionError("Collection entry is missing its logical key.")
    logical_key = RolloutShardLogicalKey.from_jsonable(logical_payload)
    if payload.get("logical_key_id") != logical_key.canonical_id():
        raise RolloutCollectionError("Collection entry logical_key_id does not match its logical key.")
    compatibility = payload.get("compatibility")
    counts = payload.get("counts")
    if not isinstance(compatibility, dict) or not isinstance(counts, dict):
        raise RolloutCollectionError("Collection entry compatibility and counts must be JSON objects.")
    return RolloutCollectionEntry(
        logical_key=logical_key,
        shard_dir=Path(str(payload["shard_dir"])).expanduser().resolve(),
        shard_id=str(payload["shard_id"]),
        rollout_manifest_sha256=str(payload["rollout_manifest_sha256"]),
        owner_sha256=str(payload["owner_sha256"]),
        compatibility={str(name): str(value) for name, value in compatibility.items()},
        counts={str(name): int(value) for name, value in counts.items()},
        registered_at_utc=str(payload["registered_at_utc"]),
    )


def _require_compatible(expected: dict[str, str], actual: dict[str, str]) -> None:
    if expected != actual:
        differences = {
            name: {"expected": expected.get(name), "actual": actual.get(name)}
            for name in sorted(set(expected) | set(actual))
            if expected.get(name) != actual.get(name)
        }
        raise RolloutCollectionError(f"Rollout shard is incompatible with the collection: {differences}.")


def _snapshot(
    collection_dir: Path,
    entries: list[RolloutCollectionEntry],
    *,
    ledger_bytes: bytes,
) -> RolloutCollectionSnapshot:
    ordered = tuple(sorted(entries, key=lambda entry: entry.logical_key))
    compatibility = {} if not ordered else ordered[0].compatibility
    return RolloutCollectionSnapshot(
        collection_dir=collection_dir,
        compatibility=compatibility,
        entries=ordered,
        ledger_sha256=hashlib.sha256(ledger_bytes).hexdigest(),
    )


def _jsonl_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with tmp_path.open("wb") as stream:
        stream.write(manifest_json_bytes(payload))
        stream.flush()
        os.fsync(stream.fileno())
    tmp_path.replace(path)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


__all__ = [
    "ROLLOUT_COLLECTION_LEDGER_FILENAME",
    "ROLLOUT_COLLECTION_MANIFEST_FILENAME",
    "ROLLOUT_COLLECTION_VERSION",
    "RolloutCollection",
    "RolloutCollectionEntry",
    "RolloutCollectionError",
    "RolloutCollectionSnapshot",
    "RolloutCollectionValidationResult",
    "RolloutShardLogicalKey",
]
