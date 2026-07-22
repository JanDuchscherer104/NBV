#!/usr/bin/env python3
"""Validate Graphify S-to-G authoring history and final-tree sync state."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tomllib

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
    return {
        path
        for _, old_path, new_path in _commit_changes(root, commit)
        for path in (old_path, new_path)
        if path is not None
    }


def _commit_changes(
    root: Path, commit: str
) -> list[tuple[str, str | None, str | None]]:
    """Return status plus before/after paths, retaining rename and deletion identity."""
    output = subprocess.check_output(
        [
            "git",
            "diff-tree",
            "--root",
            "--no-commit-id",
            "--name-status",
            "-M",
            "-r",
            "-z",
            commit,
        ],
        cwd=root,
    )
    fields = output.split(b"\0")
    changes: list[tuple[str, str | None, str | None]] = []
    index = 0
    while index < len(fields) and fields[index]:
        status = fields[index].decode("ascii")
        index += 1
        old_path = fields[index].decode("utf-8", errors="surrogateescape")
        index += 1
        if status.startswith(("R", "C")):
            new_path = fields[index].decode("utf-8", errors="surrogateescape")
            index += 1
        elif status == "D":
            new_path = None
        else:
            new_path = old_path
            old_path = None if status == "A" else old_path
        changes.append((status, old_path, new_path))
    return changes


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


def _config_at(root: Path, commit: str) -> dict:
    try:
        raw = subprocess.check_output(
            ["git", "show", f"{commit}:.graphify.toml"], cwd=root
        )
        value = tomllib.loads(raw.decode("utf-8"))
    except (
        subprocess.CalledProcessError,
        UnicodeError,
        tomllib.TOMLDecodeError,
    ) as exc:
        raise ContractError(
            f"{commit}: .graphify.toml is unavailable or malformed"
        ) from exc
    return value


def _selected_literature_dirs_at(root: Path, commit: str) -> set[str]:
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
    except subprocess.CalledProcessError:
        return selected_dirs
    except json.JSONDecodeError as exc:
        raise ContractError(
            f"{commit}: literature source manifest is malformed"
        ) from exc
    return selected_dirs


def _source_tree_digest_at(root: Path, commit: str) -> str:
    config = _config_at(root, commit)
    paths = _git(root, "ls-tree", "-r", "--name-only", commit).splitlines()
    selected_dirs = _selected_literature_dirs_at(root, commit)
    sources = []
    for path in paths:
        partition = classify_path(path, config, selected_literature_dirs=selected_dirs)
        if partition is None:
            continue
        blob = subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=root)
        sources.append({"path": path, "sha256": hashlib.sha256(blob).hexdigest()})
    return corpus_tree_digest(sources)


def _parent(root: Path, commit: str) -> str | None:
    parents = _git(root, "show", "-s", "--format=%P", commit).split()
    return parents[0] if parents else None


def _touched_partitions(root: Path, commit: str) -> set[str]:
    """Classify additions/modifications/deletions/renames against both manifest states."""
    parent = _parent(root, commit)
    before_selected = (
        _selected_literature_dirs_at(root, parent) if parent is not None else set()
    )
    after_selected = _selected_literature_dirs_at(root, commit)
    after_config = _config_at(root, commit)
    try:
        before_config = _config_at(root, parent) if parent is not None else after_config
    except ContractError:
        # The activation commit introduces the first repository Graphify contract.
        before_config = after_config
    touched: set[str] = set()
    for _, old_path, new_path in _commit_changes(root, commit):
        for path, selected, config in (
            (old_path, before_selected, before_config),
            (new_path, after_selected, after_config),
        ):
            if path is None:
                continue
            partition = classify_path(
                path,
                config,
                selected_literature_dirs=selected,
            )
            if partition is not None:
                touched.add(partition)
    return touched


def validate_authoring_history(root: Path, revisions: list[str]) -> list[str]:
    """Validate immediate graph-only children for a linear authoring range."""
    errors: list[str] = []
    pending: tuple[str, set[str], str] | None = None
    for commit in revisions:
        paths = _commit_paths(root, commit)
        canonical = paths & CANONICAL
        noncanonical_graph = {
            path
            for path in paths
            if path.startswith("graphify-out/") and path not in CANONICAL
        }
        touched = _touched_partitions(root, commit)
        corpus = bool(touched)
        if noncanonical_graph:
            errors.append(
                f"{commit}: graph-only commit changes noncanonical output: "
                + ", ".join(sorted(noncanonical_graph))
            )
        if canonical and corpus:
            errors.append(
                f"{commit}: mixed source and canonical graph authoring commit"
            )
            pending = None
            continue
        if pending is not None and not canonical:
            errors.append(
                f"{pending[0]}: corpus commit lacks immediate graph-only child "
                f"before {commit}"
            )
            pending = None
        if corpus:
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
                errors.append(
                    f"{commit}: corpus tree digest does not match {source_commit}"
                )
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
    parser.add_argument("--activation-range", action="store_true")
    parser.add_argument("--final-tree", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    authoring_range = args.authoring_range
    if args.activation_range:
        activation = load_config()["history"]["activation_commit"]
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", activation, "HEAD"],
            cwd=ROOT,
            check=False,
        ).returncode:
            errors.append(
                f"Graphify activation commit is not an ancestor: {activation}"
            )
        else:
            boundary_paths = _commit_paths(ROOT, activation)
            if boundary_paths != CANONICAL:
                errors.append(
                    "Graphify activation commit must be the immutable canonical "
                    "graph-only boundary"
                )
            authoring_range = f"{activation}..HEAD"
    if authoring_range:
        revisions = _git(
            ROOT, "rev-list", "--reverse", "--first-parent", authoring_range
        ).splitlines()
        errors.extend(validate_authoring_history(ROOT, revisions))
    if args.final_tree or not authoring_range:
        errors.extend(validate_final_tree(ROOT))
    if errors:
        print("Graphify history/final-tree validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Graphify history/final-tree state is synchronized.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
