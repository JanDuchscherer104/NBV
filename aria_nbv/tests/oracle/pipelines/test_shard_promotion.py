"""Canonical contracts for rollout shard promotion metadata."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from aria_nbv.oracle.pipelines.shard_promotion import promotion_metadata_validation_error
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
