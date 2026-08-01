#!/usr/bin/env python3
"""Regression checks for the Graphify skill's Codex-only semantic workflow."""

from __future__ import annotations

import json
from pathlib import Path
import re
import tempfile


SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"


def _assert_skill_contract() -> None:
    text = SKILL.read_text(encoding="utf-8")
    required = (
        "spawn_agent",
        "wait_agent",
        "executor",
        ".graphify_runs/<run-id>",
        "expected_chunks.json",
        "literal absolute run-scoped chunk",
        "Never glob chunk files",
        "input_tokens: 0",
        "output_tokens: 0",
        "semantic refresh incomplete",
        "re.fullmatch",
        "chunk_[0-9]{2}",
        "Invalid expected chunk",
        "RUN_ID=$(python3 -c 'import uuid; print(uuid.uuid4())')",
        "RUN_DIR=\"$(pwd)/graphify-out/.graphify_runs/${RUN_ID}\"",
        "mkdir -p \"$RUN_DIR\"",
        "expected_chunks.json').write_text('[]'",
    )
    missing = [phrase for phrase in required if phrase not in text]
    if missing:
        raise AssertionError(f"skill misses Codex semantic contract: {missing}")
    if "Task" + "(" in text:
        raise AssertionError("skill still contains the retired generic dispatch instruction")
    forbidden = (
        "graphify-out/.graphify_cached.json",
        "graphify-out/.graphify_uncached.txt",
        "graphify-out/.graphify_semantic_new.json",
        "glob(",
        "more than half the chunks",
        "skip that chunk",
    )
    present = [phrase for phrase in forbidden if phrase in text]
    if present:
        raise AssertionError(f"skill retains shared or partial-success workflow: {present}")
    if text.index("RUN_ID=$(python3 -c 'import uuid; print(uuid.uuid4())')") > text.index("Path('RUN_DIR')"):
        raise AssertionError("RUN_DIR initialization must precede every run-scoped recipe")


def _merge_current_run(run: Path) -> list[dict[str, object]]:
    expected = json.loads((run / "expected_chunks.json").read_text(encoding="utf-8"))
    if not isinstance(expected, list) or not all(isinstance(name, str) for name in expected):
        raise ValueError("expected_chunks.json must be a list of filenames")
    chunks: list[dict[str, object]] = []
    for name in expected:
        candidate = run / name
        if candidate.parent != run or not re.fullmatch(r"chunk_[0-9]{2}\.json", name):
            raise ValueError("expected chunk escapes the current run")
        value = json.loads(candidate.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not isinstance(value.get("nodes"), list) or not isinstance(value.get("edges"), list) or ("hyperedges" in value and not isinstance(value["hyperedges"], list)):
            raise ValueError("expected chunk is invalid")
        chunks.append(value)
    return chunks


def _collect_current_run(run: Path) -> dict[str, object]:
    """Fail closed on every expected chunk and materialize an empty result."""
    chunks = _merge_current_run(run)
    merged = {
        "nodes": [node for chunk in chunks for node in chunk["nodes"]],
        "edges": [edge for chunk in chunks for edge in chunk["edges"]],
        "hyperedges": [item for chunk in chunks for item in chunk.get("hyperedges", [])],
        "input_tokens": sum(int(chunk.get("input_tokens", 0)) for chunk in chunks),
        "output_tokens": sum(int(chunk.get("output_tokens", 0)) for chunk in chunks),
    }
    (run / "semantic_new.json").write_text(json.dumps(merged), encoding="utf-8")
    return merged


def _assert_interrupted_run_isolation() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / ".graphify_runs"
        stale = root / "interrupted"
        current = root / "clean"
        stale.mkdir(parents=True)
        current.mkdir()
        (stale / "expected_chunks.json").write_text('["chunk_00.json"]', encoding="utf-8")
        (stale / "chunk_00.json").write_text('{"nodes":["stale"],"edges":[]}', encoding="utf-8")
        (stale / "cached.json").write_text('{"nodes":["stale"],"edges":[]}', encoding="utf-8")
        (current / "expected_chunks.json").write_text('["chunk_00.json"]', encoding="utf-8")
        (current / "chunk_00.json").write_text('{"nodes":["current"],"edges":[]}', encoding="utf-8")
        merged = _collect_current_run(current)
        assert merged["nodes"] == ["current"]
        empty = root / "empty"
        empty.mkdir()
        (empty / "expected_chunks.json").write_text("[]", encoding="utf-8")
        assert _collect_current_run(empty)["nodes"] == []
        assert (empty / "semantic_new.json").is_file()
        initialized = root / "initialized"
        initialized.mkdir()
        (initialized / "expected_chunks.json").write_text("[]", encoding="utf-8")
        assert initialized.is_absolute() is True
        recipe = SKILL.read_text(encoding="utf-8")
        assert "graphify-out/.graphify_semantic.json').write_text" in recipe
        assert "If all files are cached" in recipe
        (current / "expected_chunks.json").write_text('["chunk_01.json"]', encoding="utf-8")
        try:
            _collect_current_run(current)
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("missing expected chunk was accepted")


def main() -> int:
    _assert_skill_contract()
    _assert_interrupted_run_isolation()
    print("Graphify Codex semantic contract checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
