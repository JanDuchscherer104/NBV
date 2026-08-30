"""Presentation-free validation of promoted rollout shard metadata."""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Mapping
from typing import Any, Literal, cast

from ...rollouts.manifest import manifest_sha256
from ...rollouts.shard_manifest import RolloutShardEntry

PromotionMarkerReadStatus = Literal["present", "missing_file", "invalid_json", "unreadable", "oversized"]
"""Outcome of reading one small promotion marker without following unsafe entries."""

_MAX_PROMOTION_MARKER_JSON_BYTES = 1_048_576


def read_promotion_marker_json(
    path: os.PathLike[str] | str,
) -> tuple[PromotionMarkerReadStatus, Mapping[str, Any] | None]:
    """Read one bounded promotion marker without blocking on special files.

    Markers are intentionally small control-plane documents.  Opening them
    nonblocking and admitting only regular files prevents a FIFO, directory,
    device, or broken alias from stalling promotion inspection.  Large rollout
    manifests and indexes are not read through this bounded control-plane seam.
    """

    descriptor: int | None = None
    try:
        if not stat.S_ISREG(os.lstat(path).st_mode):
            return "unreadable", None
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return "unreadable", None
        chunks: list[bytes] = []
        remaining = _MAX_PROMOTION_MARKER_JSON_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
    except FileNotFoundError:
        return "missing_file", None
    except OSError:
        return "unreadable", None
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if len(payload) > _MAX_PROMOTION_MARKER_JSON_BYTES:
        return "oversized", None
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError):
        return "invalid_json", None
    if not isinstance(decoded, Mapping):
        return "invalid_json", None
    return "present", cast(Mapping[str, Any], decoded)


def promotion_metadata_validation_error(
    *,
    store_manifest: Mapping[str, Any],
    success: Mapping[str, Any],
    owner: Mapping[str, Any],
) -> str | None:
    """Validate typed promotion metadata without opening Zarr arrays."""

    if success.get("sidecar_kind") != "rollout_shard_success":
        return "success marker has no typed sidecar kind"
    if owner.get("sidecar_kind") != "rollout_shard_owner":
        return "owner marker has no typed sidecar kind"
    generation = store_manifest.get("generation")
    shard_payload = generation.get("shard") if isinstance(generation, Mapping) else None
    if not isinstance(shard_payload, Mapping):
        return "manifest has no matching typed shard ownership"
    try:
        shard_entry = RolloutShardEntry.from_jsonable(dict(shard_payload))
        shard_entry.validate()
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
        return "manifest has malformed typed shard ownership"
    stored_shard = dict(shard_payload)
    expected_shard = shard_entry.to_jsonable()
    if shard_entry.campaign_binding is None:
        stored_shard.pop("campaign_binding", None)
        expected_shard.pop("campaign_binding", None)
    if not _json_value_matches(stored_shard, expected_shard):
        return "manifest has noncanonical typed shard ownership"

    campaign_binding = None if shard_entry.campaign_binding is None else shard_entry.campaign_binding.to_jsonable()
    expected = {
        "shard_id": shard_entry.shard_id,
        "writer_config_hash": shard_entry.writer_config_hash,
        "source_manifest_hash": shard_entry.source_manifest_hash,
        "split_manifest_hash": shard_entry.split_manifest_hash,
        "generation_revision_hash": shard_entry.generation_revision_hash,
        "source_cache_version": shard_entry.source_cache_version,
        "split": shard_entry.split,
        "num_source_rows": len(shard_entry.rows),
        "campaign_binding": campaign_binding,
    }
    if any(
        key not in success
        or key not in owner
        or not _json_value_matches(success[key], value)
        or not _json_value_matches(owner[key], value)
        for key, value in expected.items()
    ):
        return "markers have incomplete or inconsistent typed ownership"
    manifest_hash = manifest_sha256(dict(store_manifest))
    if success.get("rollout_manifest_sha256") != manifest_hash or owner.get("rollout_manifest_sha256") != manifest_hash:
        return "markers do not bind the rollout manifest"
    content_hash = owner.get("rollout_store_content_sha256")
    if not _is_sha256(content_hash) or success.get("rollout_store_content_sha256") != content_hash:
        return "markers have invalid or inconsistent store-content binding"
    if not _is_sha256(success.get("owner_sha256")) or success.get("owner_sha256") != manifest_sha256(dict(owner)):
        return "success marker does not bind its owner marker"
    return None


def _json_value_matches(observed: Any, expected: Any) -> bool:
    """Return whether JSON-like values match without Python scalar coercion."""

    if type(observed) is not type(expected):
        return False
    if isinstance(expected, Mapping):
        return observed.keys() == expected.keys() and all(
            _json_value_matches(observed[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(observed) == len(expected) and all(
            _json_value_matches(item, value) for item, value in zip(observed, expected, strict=True)
        )
    return bool(observed == expected)


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


__all__ = ["promotion_metadata_validation_error", "read_promotion_marker_json"]
