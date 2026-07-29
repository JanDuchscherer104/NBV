"""Tests for immutable rollout-shard collection registration."""

# ruff: noqa: S101

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("efm3d")

from aria_nbv.rollouts.collection import (
    ROLLOUT_COLLECTION_LEDGER_FILENAME,
    ROLLOUT_COLLECTION_MANIFEST_FILENAME,
    RolloutCollection,
    RolloutCollectionError,
    RolloutShardLogicalKey,
)
from aria_nbv.rollouts.manifest import RolloutStoreManifestContext, manifest_json_bytes, manifest_sha256
from aria_nbv.rollouts.shard_manifest import ROLLOUT_SHARD_OWNER_FILENAME, ROLLOUT_SHARD_SUCCESS_FILENAME
from aria_nbv.rollouts.zarr_store import write_rollout_zarr_store
from tests.rollout_fixtures import build_rollout_records


def _logical_key(*, sample_key: str, profile: str = "realistic-core-60") -> RolloutShardLogicalKey:
    return RolloutShardLogicalKey(
        campaign_id="v1-local-100scene-t1",
        split="train",
        source_sample_key=sample_key,
        target_id="chair-0",
        candidate_profile=profile,
        recipe_group="core-h1-h2",
        seed_group="seed-0",
    )


def _write_completed_shard(
    path: Path,
    *,
    shard_id: str,
    sample_key: str,
    seed: int,
    return_semantics: str = "cumulative_target_root_gain",
) -> Path:
    shard_entry = {
        "manifest_version": "rollout-shard-manifest-v1",
        "shard_id": shard_id,
        "split": "train",
        "rows": [
            {
                "order": 0,
                "sample_index": seed,
                "sample_key": sample_key,
                "scene_id": f"scene-{seed}",
                "snippet_id": f"snippet-{seed}",
                "split": "train",
                "source_shard_id": "vin-shard-000000",
                "source_shard_row": seed,
            }
        ],
        "source_manifest_hash": f"source-manifest-{seed}",
        "source_cache_version": "7",
        "split_manifest_hash": f"split-manifest-{seed}",
        "writer_config_hash": f"writer-config-{seed}",
    }
    records = build_rollout_records(horizon=1, num_samples=6, seed=seed)[:1]
    result = write_rollout_zarr_store(
        path,
        records,
        return_semantics=return_semantics,
        source_offline_store_version="7",
        split_manifest_hash=str(shard_entry["split_manifest_hash"]),
        manifest_context=RolloutStoreManifestContext(shard=shard_entry),
    )
    owner: dict[str, Any] = {
        "sidecar_kind": "rollout_shard_owner",
        "shard_id": shard_id,
        "writer_config_hash": shard_entry["writer_config_hash"],
        "source_manifest_hash": shard_entry["source_manifest_hash"],
        "split_manifest_hash": shard_entry["split_manifest_hash"],
        "source_cache_version": "7",
        "split": "train",
        "num_source_rows": 1,
        "output_tmp": f"{path}.tmp",
        "output_final": path.as_posix(),
        "rollout_manifest_sha256": result.manifest_sha256,
        "counts": {
            "rollouts": result.num_rollouts,
            "steps": result.num_steps,
            "candidates": result.num_candidates,
        },
        "runtime": {},
        "shard_entry": shard_entry,
    }
    success = {
        "sidecar_kind": "rollout_shard_success",
        "shard_id": shard_id,
        "writer_config_hash": shard_entry["writer_config_hash"],
        "source_manifest_hash": shard_entry["source_manifest_hash"],
        "split_manifest_hash": shard_entry["split_manifest_hash"],
        "source_cache_version": "7",
        "split": "train",
        "num_source_rows": 1,
        "rollout_manifest_sha256": result.manifest_sha256,
        "owner_sha256": manifest_sha256(owner),
    }
    (path / ROLLOUT_SHARD_OWNER_FILENAME).write_bytes(manifest_json_bytes(owner))
    (path / ROLLOUT_SHARD_SUCCESS_FILENAME).write_bytes(manifest_json_bytes(success))
    return path


def _tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(item.read_bytes())
    return digest.hexdigest()


def test_collection_registers_shards_without_mutating_them_and_rebuilds_deterministically(tmp_path: Path) -> None:
    shard_b = _write_completed_shard(
        tmp_path / "shards" / "shard-b",
        shard_id="shard-b",
        sample_key="sample-b",
        seed=32,
    )
    shard_a = _write_completed_shard(
        tmp_path / "shards" / "shard-a",
        shard_id="shard-a",
        sample_key="sample-a",
        seed=31,
    )
    before = {path: _tree_digest(path) for path in (shard_a, shard_b)}
    collection = RolloutCollection(tmp_path / "collection")

    entry_b = collection.register_shard(shard_b, logical_key=_logical_key(sample_key="sample-b"))
    entry_a = collection.register_shard(shard_a, logical_key=_logical_key(sample_key="sample-a"))

    snapshot = collection.snapshot()
    assert [entry.shard_id for entry in snapshot.entries] == ["shard-a", "shard-b"]
    assert snapshot.counts == {
        name: entry_a.counts[name] + entry_b.counts[name] for name in ("rollouts", "steps", "candidates")
    }
    assert collection.validate().ok
    assert {path: _tree_digest(path) for path in (shard_a, shard_b)} == before
    ledger = collection.collection_dir / ROLLOUT_COLLECTION_LEDGER_FILENAME
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 2

    manifest = collection.collection_dir / ROLLOUT_COLLECTION_MANIFEST_FILENAME
    first_manifest = manifest.read_bytes()
    manifest.unlink()
    collection.rebuild_snapshot()
    assert manifest.read_bytes() == first_manifest


def test_collection_registration_is_idempotent_for_identical_provenance(tmp_path: Path) -> None:
    shard = _write_completed_shard(
        tmp_path / "shard",
        shard_id="shard-a",
        sample_key="sample-a",
        seed=41,
    )
    collection = RolloutCollection(tmp_path / "collection")
    key = _logical_key(sample_key="sample-a")
    first = collection.register_shard(shard, logical_key=key)
    ledger_before = collection.ledger_path.read_bytes()

    second = collection.register_shard(shard, logical_key=key)

    assert second == first
    assert collection.ledger_path.read_bytes() == ledger_before
    assert len(collection.snapshot().entries) == 1


def test_collection_rejects_logical_key_conflicts(tmp_path: Path) -> None:
    first = _write_completed_shard(
        tmp_path / "first",
        shard_id="shard-first",
        sample_key="sample-a",
        seed=51,
    )
    second = _write_completed_shard(
        tmp_path / "second",
        shard_id="shard-second",
        sample_key="sample-a",
        seed=52,
    )
    collection = RolloutCollection(tmp_path / "collection")
    key = _logical_key(sample_key="sample-a")
    collection.register_shard(first, logical_key=key)

    with pytest.raises(RolloutCollectionError, match="already registered with different hashes"):
        collection.register_shard(second, logical_key=key)

    assert len(collection.snapshot().entries) == 1


def test_collection_rejects_one_shard_claiming_multiple_logical_keys(tmp_path: Path) -> None:
    shard = _write_completed_shard(
        tmp_path / "shard",
        shard_id="shard-a",
        sample_key="sample-a",
        seed=56,
    )
    collection = RolloutCollection(tmp_path / "collection")
    collection.register_shard(shard, logical_key=_logical_key(sample_key="sample-a"))

    with pytest.raises(RolloutCollectionError, match="already registered under a different logical key"):
        collection.register_shard(
            shard,
            logical_key=_logical_key(sample_key="sample-a", profile="rich-local-60"),
        )


def test_collection_rejects_mixed_protocol_contracts(tmp_path: Path) -> None:
    first = _write_completed_shard(
        tmp_path / "first",
        shard_id="shard-first",
        sample_key="sample-a",
        seed=61,
    )
    incompatible = _write_completed_shard(
        tmp_path / "incompatible",
        shard_id="shard-incompatible",
        sample_key="sample-b",
        seed=62,
        return_semantics="alternate_return_contract",
    )
    collection = RolloutCollection(tmp_path / "collection")
    collection.register_shard(first, logical_key=_logical_key(sample_key="sample-a"))

    with pytest.raises(RolloutCollectionError, match="incompatible with the collection"):
        collection.register_shard(incompatible, logical_key=_logical_key(sample_key="sample-b"))


def test_collection_rejects_tampered_completion_sidecar(tmp_path: Path) -> None:
    shard = _write_completed_shard(
        tmp_path / "shard",
        shard_id="shard-a",
        sample_key="sample-a",
        seed=71,
    )
    success_path = shard / ROLLOUT_SHARD_SUCCESS_FILENAME
    success = json.loads(success_path.read_text(encoding="utf-8"))
    success["owner_sha256"] = "tampered"
    success_path.write_bytes(manifest_json_bytes(success))

    with pytest.raises(RolloutCollectionError, match="does not bind the owner sidecar hash"):
        RolloutCollection(tmp_path / "collection").register_shard(
            shard,
            logical_key=_logical_key(sample_key="sample-a"),
        )


def test_collection_validation_detects_ledger_tampering(tmp_path: Path) -> None:
    shard = _write_completed_shard(
        tmp_path / "shard",
        shard_id="shard-a",
        sample_key="sample-a",
        seed=81,
    )
    collection = RolloutCollection(tmp_path / "collection")
    collection.register_shard(shard, logical_key=_logical_key(sample_key="sample-a"))
    ledger = collection.ledger_path
    payload = json.loads(ledger.read_text(encoding="utf-8"))
    payload["entry"]["shard_id"] = "tampered"
    ledger.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

    validation = collection.validate()

    assert not validation.ok
    assert "invalid record hash" in validation.errors[0]
