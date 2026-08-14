#!/usr/bin/env python3
"""Fail-closed freshness gate backed by Graphify's pinned detector."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
from typing import Any


PROJECTION_INDEX = Path("graphify-input/index.md")
GRAPH = Path("graphify-out/graph.json")
MANIFEST = Path("graphify-out/manifest.json")
INTERPRETER = Path("graphify-out/.graphify_python")
ROOT_MARKER = Path("graphify-out/.graphify_root")
NEEDS_UPDATE = Path("graphify-out/needs_update")
INDEX_PATH = "graphify-input/index.md"
PINNED_GRAPHIFY_VERSION = "0.9.31"
MAX_STALE_SOURCES = 128
_OWNER_DIGEST = re.compile(r"^- ([^:\r\n]+): sha256:([0-9a-f]{64})\r?$")


def _head(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode or not result.stdout.strip():
        raise ValueError("current Git HEAD is unavailable")
    return result.stdout.strip()


def _is_ancestor(root: Path, older: str, newer: str) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", older, newer],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )


def _regular(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"missing or unsafe {label}: {path.as_posix()}")


def _local_regular(root: Path, relative: Path, label: str) -> Path:
    current = root
    for part in relative.parent.parts:
        current /= part
        if current.is_symlink() or not current.is_dir():
            raise ValueError(f"missing or unsafe {label} parent: {current.as_posix()}")
    path = root / relative
    _regular(path, label)
    return path


def _json_object(path: Path, label: str) -> dict[str, Any]:
    _regular(path, label)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"invalid {label}: expected a JSON object")
    return value


def _normalize_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", normalized):
        raise ValueError("unsafe source path")
    path = PurePosixPath(normalized)
    if path.is_absolute() or "." in path.parts or ".." in path.parts:
        raise ValueError("unsafe source path")
    return path.as_posix()


def _contained_existing(root: Path, value: str) -> str:
    candidate = Path(value)
    if candidate.is_absolute():
        try:
            candidate = candidate.resolve(strict=True)
            relative = candidate.relative_to(root.resolve()).as_posix()
        except (OSError, RuntimeError, ValueError) as error:
            raise ValueError(f"stale source escapes repository: {value}") from error
    else:
        relative = _normalize_path(value)
        candidate = root / relative
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ValueError(f"stale source is unavailable: {relative}: {error}") from error
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise ValueError(f"stale source escapes repository: {relative}")
    return relative


def _projection_metadata(index: Path) -> tuple[str, str, dict[str, str]]:
    try:
        text = index.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ValueError(f"invalid projection index: {error}") from error

    def single_value(key: str) -> str:
        values = [
            line.split(":", 1)[1].strip()
            for line in text.splitlines()
            if line.startswith(f"{key}:")
        ]
        if len(values) != 1 or not values[0]:
            raise ValueError(
                f"invalid projection index: {key} must be one non-empty string"
            )
        return values[0]

    revision = single_value("source_revision")
    owner_state = single_value("owner_worktree_state")
    if owner_state not in {"clean", "dirty"}:
        raise ValueError("invalid projection index: owner_worktree_state is invalid")
    try:
        start = text.splitlines().index("## Owner digests") + 1
    except ValueError as error:
        raise ValueError("invalid projection index: missing Owner digests") from error
    owners: dict[str, str] = {}
    for line in text.splitlines()[start:]:
        if line.startswith("## "):
            break
        if not line.strip():
            continue
        match = _OWNER_DIGEST.fullmatch(line)
        if match is None:
            raise ValueError(f"invalid projection index owner digest: {line}")
        owner, digest = match.groups()
        normalized = _normalize_path(owner)
        if normalized in owners:
            raise ValueError(f"invalid projection index: duplicate owner {normalized}")
        owners[normalized] = digest
    if not owners:
        raise ValueError("invalid projection index: Owner digests must not be empty")
    return revision, owner_state, owners


def _graph_revision(root: Path) -> str:
    graph = _json_object(root / GRAPH, "graph")
    revision = graph.get("built_at_commit")
    nodes = graph.get("nodes")
    if not isinstance(revision, str) or not revision:
        raise ValueError("invalid graph: built_at_commit must be a non-empty string")
    if not isinstance(nodes, list) or any(not isinstance(node, dict) for node in nodes):
        raise ValueError("invalid graph: nodes must be a list of objects")
    found = False
    for node in nodes:
        source = node.get("source_file")
        if source is None:
            continue
        if not isinstance(source, str):
            raise ValueError("invalid graph: node source_file must be a string")
        if _normalize_path(source) == INDEX_PATH:
            found = True
    if not found:
        raise ValueError("graph has no node sourced from graphify-input/index.md")
    return revision


def _owner_reasons(root: Path, owners: dict[str, str]) -> list[str]:
    reasons: list[str] = []
    for relative, expected in owners.items():
        owner = root / relative
        try:
            resolved = owner.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise ValueError(
                f"projection owner is unavailable: {relative}: {error}"
            ) from error
        if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
            raise ValueError(f"projection owner escapes repository: {relative}")
        if hashlib.sha256(resolved.read_bytes()).hexdigest() != expected:
            reasons.append(f"projection owner digest changed: {relative}")
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all", "--", *owners],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if status.returncode:
        raise ValueError("projection owner worktree status is unavailable")
    if status.stdout.strip():
        reasons.append("projection owner worktree is dirty")
    return reasons


def _graphify_interpreter(root: Path) -> str:
    marker = root / INTERPRETER
    _regular(marker, "Graphify interpreter marker")
    value = marker.read_text(encoding="utf-8").strip()
    candidate = Path(value)
    if (
        not value
        or not candidate.is_absolute()
        or not candidate.is_file()
        or not os.access(candidate, os.X_OK)
    ):
        raise ValueError("invalid Graphify interpreter marker")
    return str(candidate)


def _detect_incremental(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    interpreter = _graphify_interpreter(root)
    manifest = (root / MANIFEST).resolve()
    _regular(manifest, "manifest")
    program = """
import json
import sys
from importlib.metadata import version
from pathlib import Path
from graphify.detect import detect_incremental
if version('graphifyy') != sys.argv[3]:
    raise RuntimeError('unexpected graphifyy version')
root = Path(sys.argv[1])
manifest = sys.argv[2]
kwargs = dict(
    manifest_path=manifest,
    follow_symlinks=False,
    google_workspace=False,
)
print(json.dumps({
    'ast': detect_incremental(root, kind='ast', **kwargs),
    'semantic': detect_incremental(root, kind='semantic', **kwargs),
}))
"""
    with tempfile.TemporaryDirectory(prefix="aria-graphify-freshness-") as output:
        env = {**os.environ, "GRAPHIFY_OUT": output}
        result = subprocess.run(
            [
                interpreter,
                "-c",
                program,
                str(root.resolve()),
                str(manifest),
                PINNED_GRAPHIFY_VERSION,
            ],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
    if result.returncode:
        raise ValueError(
            f"Graphify detector failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ValueError(f"Graphify detector returned invalid JSON: {error}") from error
    if not isinstance(payload, dict) or not all(
        isinstance(payload.get(kind), dict) for kind in ("ast", "semantic")
    ):
        raise ValueError("Graphify detector returned an invalid result")
    return payload["ast"], payload["semantic"]


def _detector_stale_sources(
    root: Path, ast: dict[str, Any], semantic: dict[str, Any]
) -> list[str]:
    stale: set[str] = set()
    supported_kinds = {"code", "document", "paper", "image", "video"}
    for result, accepted in (
        (ast, {"code"}),
        (semantic, {"document", "paper", "image"}),
    ):
        if result.get("scan_root") != str(root.resolve()):
            raise ValueError("Graphify detector reported an unexpected scan_root")
        for key in ("unclassified", "walk_errors", "skipped_sensitive"):
            values = result.get(key)
            if not isinstance(values, list):
                raise ValueError(f"Graphify detector has invalid {key}")
            if values:
                raise ValueError(f"Graphify detector reported {key}")
        files = result.get("new_files")
        if not isinstance(files, dict) or set(files) != supported_kinds:
            raise ValueError("Graphify detector has invalid new_files")
        for kind, paths in files.items():
            if not isinstance(paths, list) or any(
                not isinstance(path, str) for path in paths
            ):
                raise ValueError("Graphify detector has invalid source paths")
            if kind in accepted:
                stale.update(_contained_existing(root, path) for path in paths)
        for key in ("deleted_files", "excluded_files"):
            values = result.get(key)
            if not isinstance(values, list) or any(
                not isinstance(path, str) for path in values
            ):
                raise ValueError(f"Graphify detector has invalid {key}")
            if values:
                raise ValueError(f"Graphify detector reported {key}")
        files = result.get("files")
        if not isinstance(files, dict) or set(files) != supported_kinds:
            raise ValueError("Graphify detector has invalid files")
        for paths in files.values():
            if not isinstance(paths, list) or any(
                not isinstance(path, str) for path in paths
            ):
                raise ValueError("Graphify detector has invalid source paths")
        video = files["video"]
        if video:
            raise ValueError("Graphify detector reported unsupported video sources")
    if len(stale) > MAX_STALE_SOURCES:
        raise ValueError("Graphify detector reported an unbounded stale-source set")
    return sorted(stale)


def _result(
    state: str,
    head: str | None,
    graph_revision: str | None,
    stale_sources: list[str],
    reasons: list[str],
) -> dict[str, Any]:
    fresh = state == "fresh"
    usable = state in {"fresh", "usable-stale"}
    return {
        "state": state,
        "fresh": fresh,
        "usable": usable,
        "head": head,
        "graph_revision": graph_revision,
        "stale_sources": stale_sources,
        "reasons": reasons,
        "next_action": (
            "query Graphify first; validate consequential claims at source_location"
            if fresh
            else "query Graphify first; verify stale source_location paths directly and refresh before strict validation"
            if usable
            else "repair or rebuild Graphify before graph queries"
        ),
    }


def check(root: Path) -> dict[str, Any]:
    root = root.resolve()
    reasons: list[str] = []
    try:
        head = _head(root)
        projection_index = _local_regular(root, PROJECTION_INDEX, "projection index")
        root_marker = _local_regular(root, ROOT_MARKER, "Graphify root marker")
        try:
            marker_value = root_marker.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise ValueError(f"invalid Graphify root marker: {error}") from error
        if marker_value not in {str(root), f"{root}\n"}:
            raise ValueError("Graphify root marker is not bound to this worktree")
        for relative, label in (
            (GRAPH, "graph"),
            (MANIFEST, "manifest"),
            (INTERPRETER, "Graphify interpreter marker"),
        ):
            _local_regular(root, relative, label)
        projection_revision, owner_state, owners = _projection_metadata(
            projection_index
        )
        graph_revision = _graph_revision(root)
        if (root / NEEDS_UPDATE).exists() or (root / NEEDS_UPDATE).is_symlink():
            raise ValueError(
                "semantic refresh required: graphify-out/needs_update exists"
            )
        if owner_state == "dirty":
            raise ValueError("projection was built from a dirty owner worktree")
        reasons.extend(_owner_reasons(root, owners))
        if not _is_ancestor(root, projection_revision, head):
            raise ValueError("projection source_revision is not an ancestor of HEAD")
        if not _is_ancestor(root, graph_revision, head):
            raise ValueError("graph built_at_commit is not an ancestor of HEAD")
        ast, semantic = _detect_incremental(root)
        stale_sources = _detector_stale_sources(root, ast, semantic)
    except ValueError as error:
        return _result(
            "unusable",
            locals().get("head"),
            locals().get("graph_revision"),
            [],
            [*reasons, str(error)],
        )
    if (
        reasons
        or projection_revision != head
        or graph_revision != head
        or stale_sources
    ):
        return _result("usable-stale", head, graph_revision, stale_sources, reasons)
    return _result("fresh", head, graph_revision, stale_sources, reasons)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--quiet", action="store_true")
    output.add_argument("--json", action="store_true")
    parser.add_argument("--usable", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = check(Path.cwd())
    except Exception as error:
        result = _result(
            "unusable", None, None, [], [f"unexpected freshness-check failure: {error}"]
        )
    if not args.quiet:
        if args.json:
            print(json.dumps(result, sort_keys=True))
        else:
            print(
                f"Graphify freshness: {result['state']} — {'; '.join(result['reasons']) or 'all checks pass'}"
            )
            print(f"Next action: {result['next_action']}")
    return 0 if (result["usable"] if args.usable else result["fresh"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
