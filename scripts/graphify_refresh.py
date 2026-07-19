#!/usr/bin/env python3
"""Refresh ARIA-NBV's local Graphify graph through supported CLI commands."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "graphify-out"
STATE = OUT / "aria_nbv_freshness.json"
SEMANTIC_PREFIXES = (
    ".agents/",
    "aria_nbv/",
    "docs/",
)
SEMANTIC_SUFFIXES = {".bib", ".jsonl", ".md", ".pdf", ".png", ".qmd", ".svg", ".typ"}
STRUCTURAL_SUFFIXES = {".py", ".toml", ".yaml", ".yml"}


def _changed_paths() -> list[Path]:
    """Return normalized paths supplied by the post-commit dispatcher."""
    return [
        Path(line.strip())
        for line in os.environ.get("GRAPHIFY_CHANGED", "").splitlines()
        if line.strip()
    ]


def _is_semantic(path: Path) -> bool:
    value = path.as_posix()
    return path.name == ".graphifyignore" or (
        value.startswith(SEMANTIC_PREFIXES) and path.suffix.lower() in SEMANTIC_SUFFIXES
    )


def _is_code(path: Path) -> bool:
    value = path.as_posix()
    return path.name == "Makefile" or (
        value.startswith((".agents/", "aria_nbv/"))
        and path.suffix.lower() in STRUCTURAL_SUFFIXES
    )


def _git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _policy_digest() -> str:
    return hashlib.sha256((ROOT / ".graphifyignore").read_bytes()).hexdigest()


def _write_state(*, semantic_pending: bool) -> None:
    """Atomically record the commit and corpus policy represented locally."""
    OUT.mkdir(exist_ok=True)
    payload = {
        "built_at_commit": _git_head(),
        "corpus_policy_sha256": _policy_digest(),
        "semantic_pending": semantic_pending,
    }
    with tempfile.NamedTemporaryFile(
        "w", dir=OUT, delete=False, encoding="utf-8"
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(STATE)


def _semantic_pending() -> bool:
    """Return whether a prior semantic refresh remains outstanding."""
    if (OUT / "needs_update").exists():
        return True
    if not STATE.exists():
        return False
    try:
        return bool(
            json.loads(STATE.read_text(encoding="utf-8")).get("semantic_pending")
        )
    except (OSError, ValueError):
        return True


def main() -> int:
    """Update code nodes and flag semantic sources that need full extraction."""
    changed = _changed_paths()
    if os.environ.get("GRAPHIFY_SEMANTIC_COMPLETE") == "1":
        (OUT / "needs_update").unlink(missing_ok=True)
        _write_state(semantic_pending=False)
        return 0
    if not changed:
        return 0

    graphify = shutil.which("graphify")
    code_changed = any(_is_code(path) for path in changed)
    semantic_changed = any(_is_semantic(path) for path in changed)
    semantic_pending = _semantic_pending() or semantic_changed

    if code_changed:
        command = (
            [graphify, "update", "."]
            if graphify is not None
            else [sys.executable, "-m", "graphify", "update", "."]
        )
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            return result.returncode

    if semantic_pending:
        OUT.mkdir(exist_ok=True)
        (OUT / "needs_update").touch()

    if code_changed or semantic_changed:
        _write_state(semantic_pending=semantic_pending)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
