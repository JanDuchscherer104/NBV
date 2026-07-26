#!/usr/bin/env python3
"""Validate the repository's source-then-graph (S-to-G) history invariant."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import tomllib
from graphify_adapter import (
    _ARTIFACTS,
    CONFIG,
    IMPLEMENTATION,
    ROOT,
    AdapterError,
    Source,
    _manifest_rows,
    _literature_contract,
    classify_path,
    implementation_digest,
    is_fresh,
    load_config,
    source_digest,
)

CANONICAL = {f"graphify-out/{name}" for name in _ARTIFACTS}


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def _parents(root: Path, commit: str) -> list[str]:
    return _git(root, "show", "-s", "--format=%P", commit).split()


def _paths(root: Path, commit: str) -> set[str]:
    parents = _parents(root, commit)
    target = [parents[0], commit] if parents else ["--root", commit]
    command = ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "-z"]
    raw = subprocess.check_output([*command, *target], cwd=root).split(b"\0")
    return {value.decode("utf-8", "surrogateescape") for value in raw if value}


def _blob(root: Path, commit: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=root)


def _tree_context(root: Path, commit: str) -> tuple[dict[str, Any], set[str]]:
    config = tomllib.loads(_blob(root, commit, CONFIG.name).decode())
    manifest_path = _literature_contract(config).manifest
    manifest = _blob(root, commit, manifest_path).decode()
    selected = {directory for directory, _ in _manifest_rows(manifest)}
    return config, selected


def _contract_at(root: Path, commit: str) -> dict[str, str]:
    config, selected = _tree_context(root, commit)
    sources = [
        Source(path, family, hashlib.sha256(_blob(root, commit, path)).hexdigest(), "")
        for path in _git(root, "ls-tree", "-r", "--name-only", commit).splitlines()
        if (family := classify_path(path, config, selected))
    ]
    return {
        "built_source_commit": commit,
        "source_digest": source_digest(sources),
        "config_sha256": hashlib.sha256(_blob(root, commit, CONFIG.name)).hexdigest(),
        "adapter_sha256": implementation_digest(
            (path, _blob(root, commit, path)) for path in IMPLEMENTATION
        ),
    }


def _corpus_commit(root: Path, commit: str) -> bool:
    paths = _paths(root, commit)
    if paths & ({CONFIG.name} | set(IMPLEMENTATION)):
        return True
    parents = _parents(root, commit)
    revisions = [parents[0], commit] if parents else [commit]
    return any(
        classify_path(path, config, selected)
        for path in paths
        for config, selected in map(lambda item: _tree_context(root, item), revisions)
    )


def _validate_child(root: Path, source: str, graph: str) -> list[str]:
    paths = _paths(root, graph)
    errors: list[str] = []
    if _parents(root, graph) != [source]:
        errors.append(f"{graph}: not the single-parent child of {source}")
    if paths != CANONICAL:
        errors.append(f"{graph}: wrong graph artifact set")
        return errors
    try:
        manifest = json.loads(_blob(root, graph, "graphify-out/manifest.json"))
        expected = _contract_at(root, source)
        if not isinstance(manifest, dict):
            raise AdapterError(f"{graph}: manifest is not an object")
    except (AdapterError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        return [*errors, str(exc)]
    errors.extend(
        f"{graph}: manifest {key} does not match {source}"
        for key, value in expected.items()
        if manifest.get(key) != value
    )
    return errors


def validate_authoring_history(root: Path, revisions: list[str]) -> list[str]:
    errors: list[str] = []
    index = 0
    while index < len(revisions):
        commit = revisions[index]
        paths = _paths(root, commit)
        graph_paths = {path for path in paths if path.startswith("graphify-out/")}
        corpus = _corpus_commit(root, commit)
        if corpus and graph_paths:
            errors.append(f"{commit}: mixed source+graph commit")
            index += 1
            continue
        if corpus:
            if index + 1 == len(revisions):
                errors.append(f"{commit}: missing immediate graph-only child")
                break
            errors.extend(_validate_child(root, commit, revisions[index + 1]))
            index += 2
            continue
        if graph_paths:
            errors.append(f"{commit}: orphan graph-only commit")
            if paths != CANONICAL:
                errors.append(f"{commit}: wrong graph artifact set")
        index += 1
    return errors


def validate_final_tree(root: Path = ROOT) -> list[str]:
    return [] if is_fresh(root) else ["canonical graph is stale or invalid"]


def activation_authoring_range(
    root: Path, activation: str
) -> tuple[str | None, list[str]]:
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", activation, "HEAD"],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode:
        history = _git(root, "rev-list", "--reverse", "--first-parent", "HEAD")
        for commit in history.splitlines():
            tree = set(_git(root, "ls-tree", "-r", "--name-only", commit).splitlines())
            if CANONICAL <= tree:
                return f"{commit}..HEAD", []
        return None, []
    errors = (
        [] if _paths(root, activation) == CANONICAL else ["invalid activation commit"]
    )
    return f"{activation}..HEAD", errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authoring-range")
    parser.add_argument("--activation-range", action="store_true")
    parser.add_argument("--final-tree", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    authoring_range = args.authoring_range
    try:
        if args.activation_range:
            authoring_range, activation_errors = activation_authoring_range(
                ROOT, load_config()["history"]["activation_commit"]
            )
            errors.extend(activation_errors)
        if authoring_range:
            revisions = _git(
                ROOT, "rev-list", "--reverse", "--first-parent", authoring_range
            ).splitlines()
            errors.extend(validate_authoring_history(ROOT, revisions))
        if args.final_tree or not authoring_range:
            errors.extend(validate_final_tree(ROOT))
    except (AdapterError, subprocess.CalledProcessError) as exc:
        errors.append(str(exc))
    if errors:
        print("Graphify history/final-tree validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("Graphify history/final-tree state is synchronized.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
