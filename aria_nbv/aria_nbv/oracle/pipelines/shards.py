"""Plan deterministic shards and promote validated rollout stores atomically.

Each manifest entry owns an ordered subset of immutable VIN source rows. A
build writes a fresh temporary rollout Zarr store, validates it, records its
owner sidecar, then renames the directory into place and writes ``_SUCCESS``
last. Existing partial or mismatched paths are preserved for operator review
rather than overwritten.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ...rollouts.manifest import (
    RolloutStoreInvocation,
    collect_runtime_provenance,
    manifest_json_bytes,
    manifest_sha256,
    read_rollout_store_manifest,
    utc_timestamp,
)
from ...rollouts.shard_manifest import (
    ROLLOUT_SHARD_OWNER_FILENAME,
    ROLLOUT_SHARD_SUCCESS_FILENAME,
    RolloutShardEntry,
    RolloutShardRow,
    read_rollout_shard_manifest,
    write_rollout_shard_manifest,
)
from ...rollouts.zarr_store import RolloutZarrWriteResult, validate_rollout_zarr_store
from ...utils.fingerprints import stable_config_hash, stable_msgspec_hash
from .rollout_dataset import RolloutDatasetWriterConfig, _RolloutSourceLineageBuilder


@dataclass(frozen=True, slots=True)
class RolloutShardRunResult:
    """Result of one strict rollout shard build or resume check."""

    final_dir: Path
    """Final promoted standalone rollout-store directory."""

    skipped: bool
    """Whether an already validated, provenance-matching shard was reused."""

    success_path: Path
    """Completion marker path written only after final promotion."""

    owner_path: Path
    """Owner/provenance sidecar path carried through the promoted directory."""

    store_result: RolloutZarrWriteResult | None = None
    """Fresh write summary, or ``None`` when a completed shard was skipped."""


@dataclass(frozen=True, slots=True)
class RolloutShardStatus:
    """Status for one planned rollout shard in a generation campaign."""

    shard_id: str
    """Canonical generation-shard identifier from the campaign manifest."""

    split: str
    """VIN dataset split owned by the shard."""

    final_dir: Path
    """Deterministic final rollout-store directory for the shard."""

    status: Literal["succeeded", "failed", "incomplete", "missing"]
    """Observed lifecycle state derived from final and failure markers."""

    num_source_rows: int
    """Number of immutable VIN source rows assigned by the manifest."""

    success_path: Path
    """Expected path of the write-last completion marker."""

    owner_path: Path
    """Expected path of the promoted owner/provenance sidecar."""

    failed_markers: tuple[Path, ...] = ()
    """Failure sidecars from attempts for this shard, ordered by path."""

    errors: tuple[str, ...] = ()
    """Validation or lifecycle problems explaining an incomplete state."""

    def to_jsonable(self) -> dict[str, Any]:
        """Return a stable JSON-compatible status payload."""

        return {
            "shard_id": self.shard_id,
            "split": self.split,
            "status": self.status,
            "num_source_rows": int(self.num_source_rows),
            "final_dir": self.final_dir.as_posix(),
            "success_path": self.success_path.as_posix(),
            "owner_path": self.owner_path.as_posix(),
            "failed_markers": [path.as_posix() for path in self.failed_markers],
            "errors": list(self.errors),
        }


@dataclass(frozen=True, slots=True)
class RolloutShardCampaignStatus:
    """Status summary for all shards planned by one rollout manifest."""

    manifest_path: Path
    """Resolved JSONL manifest that defines the campaign."""

    final_root: Path
    """Directory under which manifest shard ids map to final stores."""

    shards: tuple[RolloutShardStatus, ...]
    """Per-manifest-entry statuses in deterministic manifest order."""

    @property
    def counts(self) -> dict[str, int]:
        """Count succeeded, failed, incomplete, and missing planned shards.

        Returns:
            Mapping containing every lifecycle status, including zero-count
            states, so automation can consume a stable schema.
        """

        counts = {"succeeded": 0, "failed": 0, "incomplete": 0, "missing": 0}
        for shard in self.shards:
            counts[shard.status] += 1
        return counts

    def to_jsonable(self) -> dict[str, Any]:
        """Return a stable JSON-compatible campaign status payload."""

        return {
            "manifest_path": self.manifest_path.as_posix(),
            "final_root": self.final_root.as_posix(),
            "num_shards": len(self.shards),
            "counts": self.counts,
            "shards": [shard.to_jsonable() for shard in self.shards],
        }


def plan_rollout_shards(
    config: RolloutDatasetWriterConfig,
    *,
    rows_per_shard: int,
) -> list[RolloutShardEntry]:
    """Plan deterministic source-row rollout shard entries from a writer config.

    Planning opens the configured VIN offline dataset, preserves its selected
    sample-index order within each split, and records enough row lineage for a
    later build job to reject config/source drift before expensive rendering.
    """

    if rows_per_shard < 1:
        raise ValueError("rows_per_shard must be >= 1.")
    dataset = config.source.setup_target()
    if dataset is None:
        raise RuntimeError("VinOfflineDatasetConfig did not instantiate a dataset.")
    source_manifest_hash = stable_msgspec_hash(dataset.manifest)
    writer_config_hash = stable_config_hash(config)
    source_cache_version = str(dataset.manifest.version)
    source_store_dir = Path(config.source.store.store_dir).expanduser().resolve().as_posix()

    entries: list[RolloutShardEntry] = []
    for split, records in _records_by_split(dataset._records).items():
        for chunk in _chunks(records, rows_per_shard):
            rows = tuple(RolloutShardRow.from_index_record(record, order=order) for order, record in enumerate(chunk))
            shard_id = f"shard-{len(entries):06d}"
            split_manifest_hash = _RolloutSourceLineageBuilder.build_split_manifest_hash(
                source_manifest_hash=source_manifest_hash,
                split=split,
                records=[row.hash_record() for row in rows],
            )
            entry = RolloutShardEntry(
                shard_id=shard_id,
                split=split,
                rows=rows,
                writer_config_hash=writer_config_hash,
                source_manifest_hash=source_manifest_hash,
                source_cache_version=source_cache_version,
                split_manifest_hash=split_manifest_hash,
                source_store_dir=source_store_dir,
            )
            entry.validate()
            entries.append(entry)
    return entries


def write_rollout_shard_manifest_from_config(
    config: RolloutDatasetWriterConfig,
    *,
    manifest_path: Path | str,
    rows_per_shard: int,
) -> list[RolloutShardEntry]:
    """Plan and write a rollout shard JSONL manifest."""

    entries = plan_rollout_shards(config, rows_per_shard=rows_per_shard)
    write_rollout_shard_manifest(manifest_path, entries)
    return entries


def summarize_rollout_shard_campaign(
    manifest_path: Path | str,
    *,
    final_root: Path | str,
) -> RolloutShardCampaignStatus:
    """Summarize completion state for a rollout shard campaign.

    The summary is manifest-driven: every planned shard is checked at its
    deterministic final directory, and failed attempts are discovered from
    `_FAILED.<shard_id>.*.json` sidecars written beside final shards. This gives
    operators a retry list without scanning large Zarr payload trees.
    """

    resolved_manifest = Path(manifest_path).expanduser().resolve()
    resolved_final_root = Path(final_root).expanduser().resolve()
    entries = read_rollout_shard_manifest(resolved_manifest)
    statuses = tuple(_summarize_rollout_shard_entry(entry, final_root=resolved_final_root) for entry in entries)
    return RolloutShardCampaignStatus(
        manifest_path=resolved_manifest,
        final_root=resolved_final_root,
        shards=statuses,
    )


def run_rollout_shard(
    config: RolloutDatasetWriterConfig,
    *,
    shard_entry: RolloutShardEntry,
    output_tmp: Path | str,
    output_final: Path | str,
    invocation: RolloutStoreInvocation | None = None,
) -> RolloutShardRunResult:
    """Build one rollout shard with strict temp-to-final promotion semantics.

    A completed final directory is skipped only when the Zarr store validates,
    the embedded shard manifest matches the requested entry, and `_owner.json`
    is still the payload named by `_SUCCESS.json`. Any stale temp directory or
    incomplete/tampered final directory is left for operator review.
    """

    shard_entry.validate()
    config_hash = stable_config_hash(config)
    if config_hash != shard_entry.writer_config_hash:
        raise ValueError(
            f"Rollout shard {shard_entry.shard_id!r} writer config hash mismatch: "
            f"current={config_hash} manifest={shard_entry.writer_config_hash}."
        )
    tmp_dir = Path(output_tmp).expanduser().resolve()
    final_dir = Path(output_final).expanduser().resolve()
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    owner_path = final_dir / ROLLOUT_SHARD_OWNER_FILENAME
    success_path = final_dir / ROLLOUT_SHARD_SUCCESS_FILENAME

    if final_dir.exists():
        if _completed_shard_is_current(final_dir, shard_entry=shard_entry, writer_config_hash=config_hash):
            return RolloutShardRunResult(
                final_dir=final_dir,
                skipped=True,
                success_path=success_path,
                owner_path=owner_path,
                store_result=None,
            )
        raise RuntimeError(
            f"Final rollout shard path exists but is not a validated completed shard: {final_dir}. "
            "Remove or move the partial final path after operator review before retrying."
        )
    if tmp_dir.exists():
        raise RuntimeError(
            f"Temporary rollout shard path already exists: {tmp_dir}. "
            "Remove stale temp data after operator review before retrying."
        )

    try:
        shard_config = config.model_copy(deep=True)
        shard_config.store.store_dir = tmp_dir
        result = shard_config.setup_target().run(
            invocation=invocation or RolloutStoreInvocation.programmatic(),
            shard_entry=shard_entry,
        )
        validation = validate_rollout_zarr_store(tmp_dir)
        if not validation.ok:
            joined = "; ".join(validation.errors)
            raise RuntimeError(f"Rollout shard temp validation failed for {tmp_dir}: {joined}")
        owner_payload = _owner_payload(
            shard_entry=shard_entry,
            writer_config_hash=config_hash,
            result=result,
            output_tmp=tmp_dir,
            output_final=final_dir,
        )
        _write_json_atomic(tmp_dir / ROLLOUT_SHARD_OWNER_FILENAME, owner_payload)
        tmp_dir.rename(final_dir)
        result.store_dir = final_dir
        result.manifest_path = final_dir / result.manifest_path.name
        success_payload = _success_payload(
            shard_entry=shard_entry,
            writer_config_hash=config_hash,
            owner_payload=owner_payload,
            result=result,
        )
        _write_json_atomic(success_path, success_payload)
        return RolloutShardRunResult(
            final_dir=final_dir,
            skipped=False,
            success_path=success_path,
            owner_path=owner_path,
            store_result=result,
        )
    except Exception as exc:
        _write_failed_marker(
            final_dir.parent,
            shard_entry=shard_entry,
            writer_config_hash=config_hash,
            output_tmp=tmp_dir,
            output_final=final_dir,
            error=exc,
        )
        raise


def _summarize_rollout_shard_entry(
    entry: RolloutShardEntry,
    *,
    final_root: Path,
) -> RolloutShardStatus:
    final_dir = final_root / entry.shard_id
    success_path = final_dir / ROLLOUT_SHARD_SUCCESS_FILENAME
    owner_path = final_dir / ROLLOUT_SHARD_OWNER_FILENAME
    failed_markers = tuple(sorted(final_root.glob(f"_FAILED.{entry.shard_id}.*.json")))
    errors: list[str] = []

    if final_dir.exists():
        if _completed_shard_is_current(final_dir, shard_entry=entry, writer_config_hash=entry.writer_config_hash):
            status: Literal["succeeded", "failed", "incomplete", "missing"] = "succeeded"
        else:
            status = "incomplete"
            errors.append("final path exists but is not a validated completed shard")
    elif failed_markers:
        status = "failed"
    else:
        status = "missing"

    return RolloutShardStatus(
        shard_id=entry.shard_id,
        split=entry.split,
        final_dir=final_dir,
        status=status,
        num_source_rows=len(entry.rows),
        success_path=success_path,
        owner_path=owner_path,
        failed_markers=failed_markers,
        errors=tuple(errors),
    )


def _records_by_split(records: Iterable[Any]) -> dict[str, list[Any]]:
    groups: dict[str, list[Any]] = {}
    for record in records:
        groups.setdefault(str(record.split), []).append(record)
    return groups


def _chunks(records: list[Any], rows_per_shard: int) -> Iterable[list[Any]]:
    for start in range(0, len(records), rows_per_shard):
        yield records[start : start + rows_per_shard]


def _completed_shard_is_current(
    final_dir: Path,
    *,
    shard_entry: RolloutShardEntry,
    writer_config_hash: str,
) -> bool:
    success_path = final_dir / ROLLOUT_SHARD_SUCCESS_FILENAME
    owner_path = final_dir / ROLLOUT_SHARD_OWNER_FILENAME
    if not success_path.exists() or not owner_path.exists():
        return False
    validation = validate_rollout_zarr_store(final_dir)
    if not validation.ok:
        return False
    try:
        success = json.loads(success_path.read_text(encoding="utf-8"))
        owner = json.loads(owner_path.read_text(encoding="utf-8"))
        store_manifest = read_rollout_store_manifest(final_dir)
    except (json.JSONDecodeError, OSError):
        return False
    expected = {
        "shard_id": shard_entry.shard_id,
        "writer_config_hash": writer_config_hash,
        "source_manifest_hash": shard_entry.source_manifest_hash,
        "split_manifest_hash": shard_entry.split_manifest_hash,
    }
    if not all(success.get(key) == value and owner.get(key) == value for key, value in expected.items()):
        return False
    if success.get("owner_sha256") != manifest_sha256(owner):
        return False
    rollout_manifest_sha = manifest_sha256(store_manifest)
    if owner.get("rollout_manifest_sha256") != rollout_manifest_sha:
        return False
    if success.get("rollout_manifest_sha256") != rollout_manifest_sha:
        return False
    return store_manifest.get("generation", {}).get("shard") == shard_entry.to_jsonable()


def _owner_payload(
    *,
    shard_entry: RolloutShardEntry,
    writer_config_hash: str,
    result: RolloutZarrWriteResult,
    output_tmp: Path,
    output_final: Path,
) -> dict[str, Any]:
    return {
        "sidecar_kind": "rollout_shard_owner",
        "shard_id": shard_entry.shard_id,
        "writer_config_hash": writer_config_hash,
        "source_manifest_hash": shard_entry.source_manifest_hash,
        "split_manifest_hash": shard_entry.split_manifest_hash,
        "source_cache_version": shard_entry.source_cache_version,
        "split": shard_entry.split,
        "num_source_rows": len(shard_entry.rows),
        "output_tmp": output_tmp.as_posix(),
        "output_final": output_final.as_posix(),
        "rollout_manifest_sha256": result.manifest_sha256,
        "counts": {
            "rollouts": result.num_rollouts,
            "steps": result.num_steps,
            "candidates": result.num_candidates,
        },
        "runtime": collect_runtime_provenance(),
        "shard_entry": shard_entry.to_jsonable(),
    }


def _success_payload(
    *,
    shard_entry: RolloutShardEntry,
    writer_config_hash: str,
    owner_payload: dict[str, Any],
    result: RolloutZarrWriteResult,
) -> dict[str, Any]:
    return {
        "sidecar_kind": "rollout_shard_success",
        "shard_id": shard_entry.shard_id,
        "writer_config_hash": writer_config_hash,
        "source_manifest_hash": shard_entry.source_manifest_hash,
        "split_manifest_hash": shard_entry.split_manifest_hash,
        "source_cache_version": shard_entry.source_cache_version,
        "split": shard_entry.split,
        "num_source_rows": len(shard_entry.rows),
        "rollout_manifest_sha256": result.manifest_sha256,
        "owner_sha256": manifest_sha256(owner_payload),
    }


def _write_failed_marker(
    parent_dir: Path,
    *,
    shard_entry: RolloutShardEntry,
    writer_config_hash: str,
    output_tmp: Path,
    output_final: Path,
    error: Exception,
) -> None:
    parent_dir.mkdir(parents=True, exist_ok=True)
    timestamp = "".join(ch if ch.isalnum() else "-" for ch in utc_timestamp())
    marker = parent_dir / f"_FAILED.{shard_entry.shard_id}.{timestamp}.json"
    payload = {
        "sidecar_kind": "rollout_shard_failure",
        "shard_id": shard_entry.shard_id,
        "writer_config_hash": writer_config_hash,
        "source_manifest_hash": shard_entry.source_manifest_hash,
        "split_manifest_hash": shard_entry.split_manifest_hash,
        "output_tmp": output_tmp.as_posix(),
        "output_final": output_final.as_posix(),
        "error_type": error.__class__.__name__,
        "error": str(error),
        "runtime": collect_runtime_provenance(),
    }
    _write_json_atomic(marker, payload)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_bytes(manifest_json_bytes(payload))
    tmp_path.replace(path)


__all__ = [
    "RolloutShardCampaignStatus",
    "RolloutShardRunResult",
    "RolloutShardStatus",
    "plan_rollout_shards",
    "run_rollout_shard",
    "summarize_rollout_shard_campaign",
    "write_rollout_shard_manifest_from_config",
]
