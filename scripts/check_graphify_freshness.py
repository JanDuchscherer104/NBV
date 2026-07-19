#!/usr/bin/env python3
"""Validate that the local Graphify graph matches source and corpus policy."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "graphify-out"


def _head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _policy_digest() -> str:
    return hashlib.sha256((ROOT / ".graphifyignore").read_bytes()).hexdigest()


def freshness_errors() -> list[str]:
    """Return reasons the local graph must not be trusted for navigation."""
    graph_path = OUT / "graph.json"
    state_path = OUT / "aria_nbv_freshness.json"
    if not graph_path.exists():
        return ["graphify-out/graph.json is absent"]
    if not state_path.exists():
        return ["Graphify freshness metadata is absent"]

    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    state = json.loads(state_path.read_text(encoding="utf-8"))
    head = _head()
    errors: list[str] = []
    if graph.get("built_at_commit") != head:
        errors.append("graph.json was built from a different commit")
    if state.get("built_at_commit") != head:
        errors.append("freshness metadata was built from a different commit")
    if state.get("corpus_policy_sha256") != _policy_digest():
        errors.append(".graphifyignore changed since the last refresh")
    if state.get("semantic_pending") or (OUT / "needs_update").exists():
        errors.append("documentation, literature, or diagram extraction is pending")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    errors = freshness_errors()
    if errors and not args.quiet:
        print("Graphify is stale; fall back to source files:")
        for error in errors:
            print(f"- {error}")
    elif not errors and not args.quiet:
        print("Graphify is fresh for the current commit and corpus policy.")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
