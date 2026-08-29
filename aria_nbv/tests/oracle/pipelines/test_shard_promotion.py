"""Canonical contracts for rollout shard promotion metadata."""

from __future__ import annotations

import os
import signal
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from aria_nbv.oracle.pipelines.shard_promotion import promotion_metadata_validation_error, read_promotion_marker_json
from aria_nbv.rollouts.manifest import manifest_sha256
from aria_nbv.rollouts.shard_manifest import RolloutShardEntry, RolloutShardRow, build_rollout_split_manifest_hash


def _promotion_metadata() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    row = RolloutShardRow(0, 4, "sample-4", "scene", "snippet", "train", "source", 2)
    source_hash = "a" * 64
    entry = RolloutShardEntry(
        shard_id="shard-000001",
        split="train",
        rows=(row,),
        writer_config_hash="b" * 64,
        source_manifest_hash=source_hash,
        source_cache_version="10",
        split_manifest_hash=build_rollout_split_manifest_hash(
            source_manifest_hash=source_hash, split="train", records=[row.hash_record()]
        ),
        source_store_dir="root",
        generation_revision_hash="c" * 64,
    )
    entry.validate()
    store_manifest = {"generation": {"shard": entry.to_jsonable()}}
    owner = {
        "sidecar_kind": "rollout_shard_owner",
        "shard_id": entry.shard_id,
        "writer_config_hash": entry.writer_config_hash,
        "source_manifest_hash": entry.source_manifest_hash,
        "split_manifest_hash": entry.split_manifest_hash,
        "generation_revision_hash": entry.generation_revision_hash,
        "source_cache_version": entry.source_cache_version,
        "split": entry.split,
        "num_source_rows": len(entry.rows),
        "rollout_manifest_sha256": manifest_sha256(store_manifest),
        "rollout_store_content_sha256": "d" * 64,
        "campaign_binding": None,
    }
    success = {
        "sidecar_kind": "rollout_shard_success",
        **{key: value for key, value in owner.items() if key != "sidecar_kind"},
        "owner_sha256": manifest_sha256(owner),
    }
    return store_manifest, success, owner


def test_promotion_metadata_accepts_canonical_typed_shard() -> None:
    store_manifest, success, owner = _promotion_metadata()

    assert promotion_metadata_validation_error(store_manifest=store_manifest, success=success, owner=owner) is None


def test_read_promotion_marker_json_rejects_nonregular_entries_without_blocking(tmp_path: Path) -> None:
    """Control-plane marker reads must reject FIFOs rather than wait for writers."""

    marker = tmp_path / "_SUCCESS.json"
    os.mkfifo(marker)
    previous_handler = signal.getsignal(signal.SIGALRM)

    def _deadline(_signum: int, _frame: object) -> None:
        raise TimeoutError("promotion marker FIFO read exceeded its two-second deadline")

    signal.signal(signal.SIGALRM, _deadline)
    signal.setitimer(signal.ITIMER_REAL, 2)
    try:
        assert read_promotion_marker_json(marker) == ("unreadable", None)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        (b"{", "invalid_json"),
        (b"[]", "invalid_json"),
        (b'{"x":' + b"1" * 5_000 + b"}", "invalid_json"),
        (b"{" + b" " * 1_048_576 + b"}", "oversized"),
    ],
)
def test_read_promotion_marker_json_fails_closed_for_invalid_or_oversized_payload(
    payload: bytes, status: str, tmp_path: Path
) -> None:
    marker = tmp_path / "_SUCCESS.json"
    marker.write_bytes(payload)

    assert read_promotion_marker_json(marker) == (status, None)


@pytest.mark.parametrize("entry_kind", ["missing", "directory", "device", "broken_alias", "regular_alias"])
def test_read_promotion_marker_json_fails_closed_for_nonregular_or_missing_entries(
    entry_kind: str, tmp_path: Path
) -> None:
    marker = tmp_path / "_SUCCESS.json"
    if entry_kind == "directory":
        marker.mkdir()
    elif entry_kind == "device":
        marker.symlink_to(os.devnull)
    elif entry_kind == "broken_alias":
        marker.symlink_to(tmp_path / "missing.json")
    elif entry_kind == "regular_alias":
        target = tmp_path / "marker.json"
        target.write_text("{}", encoding="utf-8")
        marker.symlink_to(target)

    status, payload = read_promotion_marker_json(marker)

    assert payload is None
    assert status == ("missing_file" if entry_kind == "missing" else "unreadable")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda shard: shard["rows"][0].pop("sample_key"),
        lambda shard: shard["rows"][0].update(order=1),
        lambda shard: shard.update(split_manifest_hash="0" * 64),
    ],
)
def test_promotion_metadata_rejects_malformed_typed_rows(mutate: Callable[[dict[str, Any]], Any]) -> None:
    store_manifest, success, owner = _promotion_metadata()
    mutate(store_manifest["generation"]["shard"])

    error = promotion_metadata_validation_error(store_manifest=store_manifest, success=success, owner=owner)

    assert error is not None
    assert "typed shard ownership" in error


@pytest.mark.parametrize(
    "mutate",
    [
        lambda _manifest, success, owner: (
            success.__setitem__("num_source_rows", True),
            owner.__setitem__("num_source_rows", True),
        ),
        lambda _manifest, success, owner: (success.pop("campaign_binding"), owner.pop("campaign_binding")),
        lambda manifest, _success, _owner: manifest["generation"]["shard"].__setitem__("rows", [{"order": True}]),
    ],
)
def test_promotion_metadata_rejects_noncanonical_json_marker_or_nested_row(
    mutate: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], Any],
) -> None:
    store_manifest, success, owner = _promotion_metadata()
    mutate(store_manifest, success, owner)

    assert promotion_metadata_validation_error(store_manifest=store_manifest, success=success, owner=owner) is not None


def test_promotion_metadata_rejects_marker_binding_mismatch() -> None:
    store_manifest, success, owner = _promotion_metadata()
    success["owner_sha256"] = "0" * 64

    error = promotion_metadata_validation_error(store_manifest=store_manifest, success=success, owner=owner)

    assert error == "success marker does not bind its owner marker"
