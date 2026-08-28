"""Regression tests for the candidate scale-up pilot renderer."""

from __future__ import annotations

from pathlib import Path

import pytest

from aria_nbv.rollouts.candidate_benchmark import benchmark_binding_from_reader
from scripts.render_candidate_generation_scaleup_pilot import (
    _require_store_content_hash,
)


class _StoreReader:
    def __init__(self, store_dir: Path) -> None:
        self.store_dir = store_dir

    @staticmethod
    def manifest() -> dict[str, object]:
        return {}


def test_store_content_hash_rejects_candidate_payload_change_with_unchanged_manifest(
    tmp_path: Path,
) -> None:
    store = tmp_path / "rollouts.zarr"
    chunk = store / "candidates" / "positions" / "c" / "0"
    chunk.parent.mkdir(parents=True)
    (store / "manifest.json").write_text(
        '{"counts":{"candidates":1}}\n', encoding="utf-8"
    )
    chunk.write_bytes(b"candidate-payload-v1")
    reader = _StoreReader(store)
    expected = benchmark_binding_from_reader(reader)["store_content_sha256"]

    assert _require_store_content_hash(reader, expected, "fixture") == expected

    chunk.write_bytes(b"candidate-payload-v2")
    with pytest.raises(ValueError, match="fixture rollout store content hash"):
        _require_store_content_hash(reader, expected, "fixture")
