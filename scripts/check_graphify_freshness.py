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


def _git_paths(*args: str) -> set[Path]:
    output = subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.STDOUT)
    return {
        Path(value.decode(errors="surrogateescape"))
        for value in output.split(b"\0")
        if value
    }


def _is_graphify_source(path: Path) -> bool:
    if path.name == ".graphifyignore":
        return True
    result = subprocess.run(
        [
            "git",
            "-c",
            f"core.excludesFile={ROOT / '.graphifyignore'}",
            "check-ignore",
            "--no-index",
            "-q",
            "--",
            path.as_posix(),
        ],
        cwd=ROOT,
        check=False,
    )
    return result.returncode != 0


def _dirty_graphify_sources() -> list[str]:
    changed = _git_paths("diff", "--name-only", "-z", "HEAD", "--")
    untracked = _git_paths("ls-files", "--others", "--exclude-standard", "-z")
    return sorted(
        path.as_posix() for path in changed | untracked if _is_graphify_source(path)
    )


def _read_json_object(
    path: Path, label: str
) -> tuple[dict[str, object] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"{label} is malformed JSON: {exc}"
    except OSError as exc:
        return None, f"{label} cannot be read: {exc}"
    if not isinstance(data, dict):
        return None, f"{label} is not a JSON object"
    return data, None


def freshness_errors() -> list[str]:
    """Return reasons the local graph must not be trusted for navigation."""
    graph_path = OUT / "graph.json"
    state_path = OUT / "aria_nbv_freshness.json"
    if not graph_path.exists():
        return ["graphify-out/graph.json is absent"]
    if not state_path.exists():
        return ["Graphify freshness metadata is absent"]

    errors: list[str] = []
    graph, graph_error = _read_json_object(graph_path, "graphify-out/graph.json")
    state, state_error = _read_json_object(state_path, "Graphify freshness metadata")
    if graph_error:
        errors.append(graph_error)
    if state_error:
        errors.append(state_error)
    if errors:
        return errors

    assert graph is not None and state is not None
    head = _head()
    if graph.get("built_at_commit") != head:
        errors.append("graph.json was built from a different commit")
    if state.get("built_at_commit") != head:
        errors.append("freshness metadata was built from a different commit")
    if state.get("corpus_policy_sha256") != _policy_digest():
        errors.append(".graphifyignore changed since the last refresh")
    dirty_sources = _dirty_graphify_sources()
    if dirty_sources:
        errors.append(
            "Graphify corpus sources have uncommitted changes: "
            + ", ".join(dirty_sources[:10])
        )
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
