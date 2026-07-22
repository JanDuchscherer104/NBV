#!/usr/bin/env python3
"""Validate Graphify S-to-G authoring history and final-tree sync state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from graphify_contract import (
    ContractError,
    ROOT,
    classify_path,
    collect_sources,
    corpus_tree_digest,
    load_canonical,
    load_config,
)

CANONICAL = {
    "graphify-out/graph.json",
    "graphify-out/manifest.json",
    "graphify-out/GRAPH_REPORT.md",
}


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def _commit_paths(root: Path, commit: str) -> set[str]:
    output = subprocess.check_output(
        ["git", "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "-z", commit],
        cwd=root,
    )
    return {
        value.decode("utf-8", errors="surrogateescape")
        for value in output.split(b"\0")
        if value
    }


def _manifest_at(root: Path, commit: str) -> dict:
    try:
        raw = subprocess.check_output(
            ["git", "show", f"{commit}:graphify-out/manifest.json"], cwd=root
        )
        value = json.loads(raw)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise ContractError(f"{commit}: canonical manifest is unavailable") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{commit}: canonical manifest is not an object")
    return value


def _source_tree_digest_at(root: Path, commit: str) -> str:
    config = load_config(root)
    paths = _git(root, "ls-tree", "-r", "--name-only", commit).splitlines()
    selected_dirs: set[str] = set()
    try:
        manifest_raw = subprocess.check_output(
            ["git", "show", f"{commit}:docs/literature/sources.jsonl"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        for line in manifest_raw.splitlines():
            record = json.loads(line)
            if record.get("tex_dir"):
                selected_dirs.add(record["tex_dir"])
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        pass
    sources = []
    for path in paths:
        partition = classify_path(
            path, config, selected_literature_dirs=selected_dirs
        )
        if partition is None:
            continue
        blob = subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=root)
        import hashlib

        sources.append({"path": path, "sha256": hashlib.sha256(blob).hexdigest()})
    return corpus_tree_digest(sources)


def validate_authoring_history(root: Path, revisions: list[str]) -> list[str]:
    """Validate immediate graph-only children for a linear authoring range."""
    config = load_config(root)
    errors: list[str] = []
    pending: tuple[str, set[str], str] | None = None
    for commit in revisions:
        paths = _commit_paths(root, commit)
        canonical = paths & CANONICAL
        noncanonical_graph = {
            path for path in paths if path.startswith("graphify-out/") and path not in CANONICAL
        }
        corpus = {
            path
            for path in paths - CANONICAL
            if classify_path(path, config) is not None
        }
        if noncanonical_graph:
            errors.append(
                f"{commit}: graph-only commit changes noncanonical output: "
                + ", ".join(sorted(noncanonical_graph))
            )
        if canonical and corpus:
            errors.append(f"{commit}: mixed source and canonical graph authoring commit")
            continue
        if corpus:
            if pending is not None:
                errors.append(f"{commit}: corpus commit follows unsynchronized {pending[0]}")
            touched = {
                partition
                for path in corpus
                if (partition := classify_path(path, config)) is not None
            }
            pending = (commit, touched, _source_tree_digest_at(root, commit))
            continue
        if canonical:
            if paths - CANONICAL:
                errors.append(f"{commit}: graph commit contains non-graph changes")
                continue
            if pending is None:
                continue
            manifest = _manifest_at(root, commit)
            source_commit, touched, digest = pending
            if manifest.get("corpus_tree_sha256") != digest:
                errors.append(f"{commit}: corpus tree digest does not match {source_commit}")
            refreshed = set(manifest.get("sync", {}).get("refreshed_partitions", []))
            if not touched <= refreshed:
                errors.append(
                    f"{commit}: does not refresh touched partitions: "
                    + ", ".join(sorted(touched - refreshed))
                )
            pending = None
    if pending is not None:
        errors.append(f"{pending[0]}: corpus commit lacks immediate graph-only child")
    return errors


def validate_final_tree(root: Path = ROOT) -> list[str]:
    """Validate merge/squash state by final corpus digest, independent of SHA."""
    try:
        graph, manifest = load_canonical(root / "graphify-out")
        current = corpus_tree_digest(collect_sources(root))
    except ContractError as exc:
        return [str(exc)]
    errors: list[str] = []
    if manifest.get("corpus_tree_sha256") != current:
        errors.append("canonical manifest does not match the final corpus tree")
    if graph.get("corpus_tree_sha256") != current:
        errors.append("canonical graph does not match the final corpus tree")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authoring-range")
    parser.add_argument("--final-tree", action="store_true")
    args = parser.parse_args()
    if args.authoring_range:
        revisions = _git(ROOT, "rev-list", "--reverse", "--first-parent", args.authoring_range).splitlines()
        errors = validate_authoring_history(ROOT, revisions)
    else:
        errors = validate_final_tree(ROOT)
    if errors:
        print("Graphify history/final-tree validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Graphify history/final-tree state is synchronized.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
