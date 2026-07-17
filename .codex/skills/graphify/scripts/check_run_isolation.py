#!/usr/bin/env python3
"""Verify Graphify semantic runs never follow a replaced shared pointer."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

SKILL_PATH = Path(__file__).resolve().parents[1] / "SKILL.md"


def _assert_skill_contract() -> None:
    """Check run isolation without weakening established Graphify safeguards."""

    skill = SKILL_PATH.read_text(encoding="utf-8")
    section = skill.split("**Step B0 -", maxsplit=1)[1].split("#### Part C", maxsplit=1)[0]

    required_contracts = (
        'if ! "$PYTHON" -c "import graphify"',
        'GRAPHIFY_RUN_ID="$(',
        'GRAPHIFY_RUN_DIR="graphify-out/.graphify_runs/$GRAPHIFY_RUN_ID"',
        "expected = json.loads((run_dir / 'expected_chunks.json')",
        "Treat the persisted\nchunk file—not a possibly truncated chat result—as the merge input and success\nsignal.",
        "Never glob or sweep old\nrun directories",
    )
    for contract in required_contracts:
        if contract not in skill:
            raise AssertionError(f"Graphify safeguard missing: {contract!r}")

    pointer_read = "Path('graphify-out/.graphify_run_dir').read_text"
    if pointer_read in section:
        raise AssertionError("Steps B0-B3 still reread the mutable run pointer")
    if section.count("run_dir = Path('RUN_DIR')") != 5:
        raise AssertionError("every run-scoped B0-B3 block must use the RUN_DIR literal")
    if "run_dir.glob(" in section or "run_dir.rglob(" in section:
        raise AssertionError("semantic merge must not glob run artifacts")


def _merge_manifest(run_dir: Path) -> dict[str, object]:
    """Merge only chunks named by one immutable run directory's manifest."""

    expected = json.loads((run_dir / "expected_chunks.json").read_text(encoding="utf-8"))
    nodes: list[dict[str, str]] = []
    edges: list[dict[str, str]] = []
    for name in expected:
        chunk = json.loads((run_dir / name).read_text(encoding="utf-8"))
        nodes.extend(chunk["nodes"])
        edges.extend(chunk["edges"])
    return {"nodes": nodes, "edges": edges}


def _simulate_pointer_replacement() -> None:
    """Prove a captured run remains isolated after the shared pointer changes."""

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        original = root / "run-original"
        replacement = root / "run-replacement"
        original.mkdir()
        replacement.mkdir()
        pointer = root / ".graphify_run_dir"

        pointer.write_text(f"{original}\n", encoding="utf-8")
        captured_run = Path(pointer.read_text(encoding="utf-8").strip())

        for run_dir, node_id in ((original, "original"), (replacement, "replacement")):
            (run_dir / "expected_chunks.json").write_text(json.dumps(["chunk_01.json"]), encoding="utf-8")
            (run_dir / "chunk_01.json").write_text(
                json.dumps({"nodes": [{"id": node_id}], "edges": []}), encoding="utf-8"
            )

        pointer.write_text(f"{replacement}\n", encoding="utf-8")
        merged = _merge_manifest(captured_run)
        if merged["nodes"] != [{"id": "original"}]:
            raise AssertionError("merge followed the replaced pointer instead of the captured run")


def main() -> None:
    """Run the static contract check and pointer-replacement regression."""

    _assert_skill_contract()
    _simulate_pointer_replacement()
    print("Graphify run isolation: PASS")


if __name__ == "__main__":
    main()
