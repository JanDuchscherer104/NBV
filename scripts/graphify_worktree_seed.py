#!/usr/bin/env python3
"""Fail-closed Graphify artifact seed for a linked ARIA-NBV worktree."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
from typing import Any


CORE = (
    Path("graphify-out/graph.json"),
    Path("graphify-out/manifest.json"),
    Path("graphify-out/.graphify_python"),
)
ROOT = Path("graphify-out/.graphify_root")
SENTINEL = Path("graphify-out/.aria-worktree-seed.json")
GRAPHIFY_DISTRIBUTION = "graphifyy"
PINNED_GRAPHIFY_VERSION = "0.9.31"


def fail(message: str) -> None:
    raise ValueError(message)


def regular(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        fail(f"{label} must be a regular local file: {path}")


def validate_parent_chain(
    root: Path, relative: Path, label: str, *, require_existing: bool
) -> None:
    """Reject symlinked or non-directory parents below an already-resolved root."""
    current = root
    for part in relative.parent.parts:
        current /= part
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            fail(f"unsafe {label} parent: {current}")
        if require_existing and not current.exists():
            fail(f"unsafe {label} parent: {current}")


def safe_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        fail(f"unsafe {label} path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or "." in path.parts or ".." in path.parts:
        fail(f"unsafe {label} path: {value!r}")
    return Path(*path.parts)


def json_object(path: Path, label: str) -> dict[str, Any]:
    regular(path, label)
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        fail(f"invalid {label}: {error}")
    if not isinstance(result, dict):
        fail(f"invalid {label}: expected a JSON object")
    return result


def git(root: Path, git_dir: Path | None, *args: str) -> str:
    command = ["git"]
    command.extend(
        (f"--git-dir={git_dir}", f"--work-tree={root}")
        if git_dir
        else ("-C", str(root))
    )
    result = subprocess.run(
        [*command, *args], capture_output=True, text=True, check=False
    )
    if result.returncode:
        fail(f"Git metadata unavailable for {root}: {result.stderr.strip()}")
    return result.stdout.strip()


def common_dir(root: Path, git_dir: Path | None) -> Path:
    value = Path(git(root, git_dir, "rev-parse", "--git-common-dir"))
    return value.resolve() if value.is_absolute() else (root / value).resolve()


def validate_topology(
    source: Path,
    destination: Path,
    source_git_dir: Path | None,
    destination_git_dir: Path | None,
) -> Path:
    if source == destination:
        fail("source and destination worktrees must differ")
    common = common_dir(source, source_git_dir)
    if common != common_dir(destination, destination_git_dir):
        fail("source and destination must belong to the same Git common directory")
    worktrees = {
        Path(line[9:]).resolve()
        for line in git(
            source, source_git_dir, "worktree", "list", "--porcelain"
        ).splitlines()
        if line.startswith("worktree ")
    }
    if source not in worktrees or destination not in worktrees:
        fail("source and destination must both be registered Git worktrees")
    return common


def manifest_markdown(root: Path) -> list[Path]:
    manifest = json_object(root / CORE[1], "source manifest")
    entries: Any = manifest.get("files", manifest)
    if not isinstance(entries, dict) or not entries:
        fail("invalid source manifest: files must be a non-empty object")
    result: list[Path] = []
    for raw, entry in entries.items():
        path = safe_path(raw, "manifest")
        if not isinstance(entry, dict):
            fail(f"invalid source manifest entry: {path}")
        if path.parts[0] == "graphify-input" and path.suffix.lower() == ".md":
            validate_parent_chain(root, path, "source", require_existing=True)
            regular(root / path, "manifest source")
            result.append(path)
    index = Path("graphify-input/index.md")
    if index not in result:
        fail("source manifest must include graphify-input/index.md")
    return sorted(set(result))


def validate_graph(root: Path) -> str:
    graph = json_object(root / CORE[0], "source graph")
    if not isinstance(graph.get("nodes"), list) or any(
        not isinstance(node, dict) for node in graph["nodes"]
    ):
        fail("invalid source graph: nodes must be a list of objects")
    if (
        not isinstance(graph.get("built_at_commit"), str)
        or not graph["built_at_commit"]
    ):
        fail("invalid source graph: built_at_commit must be a non-empty string")
    if not any(
        node.get("source_file") == "graphify-input/index.md" for node in graph["nodes"]
    ):
        fail("invalid source graph: missing graphify-input/index.md node")
    return graph["built_at_commit"]


def validate_interpreter(root: Path) -> None:
    marker = root / CORE[2]
    regular(marker, "source Graphify interpreter marker")
    try:
        configured = Path(marker.read_text(encoding="utf-8").strip())
    except (OSError, UnicodeDecodeError) as error:
        fail(f"invalid source Graphify interpreter marker: {error}")
    if (
        not configured.is_absolute()
        or not configured.is_file()
        or not os.access(configured, os.X_OK)
    ):
        fail("invalid source Graphify interpreter marker")
    result = subprocess.run(
        [
            str(configured),
            "-c",
            "import graphify; from importlib.metadata import version; print(version('graphifyy'))",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        fail("source Graphify interpreter cannot import graphify")
    if result.stdout.strip() != PINNED_GRAPHIFY_VERSION:
        fail(
            f"source Graphify interpreter has {GRAPHIFY_DISTRIBUTION} {result.stdout.strip()!r}; "
            f"expected {PINNED_GRAPHIFY_VERSION}"
        )


def validate_source(source: Path) -> tuple[list[Path], str]:
    for path in (*CORE, Path("graphify-out/needs_update")):
        validate_parent_chain(source, path, "source", require_existing=True)
    if (source / "graphify-out/needs_update").exists() or (
        source / "graphify-out/needs_update"
    ).is_symlink():
        fail("source Graphify refresh is pending: graphify-out/needs_update exists")
    graph_revision = validate_graph(source)
    markdown = manifest_markdown(source)
    validate_interpreter(source)
    return markdown, graph_revision


def owned_files(payload: dict[str, Any]) -> list[Path]:
    if payload.get("schema_version") != 1:
        fail("invalid worktree seed sentinel schema")
    raw = payload.get("files")
    if not isinstance(raw, list) or not raw:
        fail("invalid worktree seed sentinel files")
    files = [safe_path(item, "worktree seed") for item in raw]
    if len(files) != len(set(files)):
        fail("invalid worktree seed sentinel: duplicate files")
    return files


def validate_owned(destination: Path, common: Path) -> None:
    validate_parent_chain(destination, SENTINEL, "destination", require_existing=True)
    payload = json_object(destination / SENTINEL, "worktree seed sentinel")
    if payload.get("target_root") != str(destination) or payload.get(
        "git_common_dir"
    ) != str(common):
        fail("worktree seed sentinel is bound to another worktree")
    files = owned_files(payload)
    if not set((*CORE, ROOT)).issubset(files):
        fail("partial owned Graphify seed install")
    for path in files:
        validate_parent_chain(destination, path, "destination", require_existing=True)
        regular(destination / path, "seeded artifact")
    if (destination / ROOT).read_text(encoding="utf-8") != f"{destination}\n":
        fail("child .graphify_root is not bound to this worktree")
    validate_graph(destination)
    manifest_markdown(destination)


def seed(
    source: Path,
    destination: Path,
    *,
    check: bool,
    source_git_dir: Path | None,
    destination_git_dir: Path | None,
) -> None:
    source, destination = source.resolve(), destination.resolve()
    if not source.is_dir() or not destination.is_dir():
        fail("source and destination must be directories")
    common = validate_topology(source, destination, source_git_dir, destination_git_dir)
    for path in (*CORE, ROOT, SENTINEL, Path("graphify-input/index.md")):
        validate_parent_chain(destination, path, "destination", require_existing=False)
    sentinel = destination / SENTINEL
    if sentinel.exists() or sentinel.is_symlink():
        validate_owned(destination, common)
        return
    markdown, graph_revision = validate_source(source)
    source_head = git(source, source_git_dir, "rev-parse", "HEAD")
    targets = [*CORE, *markdown, ROOT, SENTINEL]
    for path in targets:
        validate_parent_chain(destination, path, "destination", require_existing=False)
    if any(
        (destination / path).exists() or (destination / path).is_symlink()
        for path in targets
    ):
        fail(
            "destination collision: Graphify seed paths exist without an ownership sentinel"
        )
    if check:
        fail("missing seeded Graphify artifacts")
    staged = Path(tempfile.mkdtemp(prefix=".graphify-seed-", dir=destination))
    try:
        files = [*CORE, *markdown]
        for path in files:
            target = staged / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / path, target)
        (staged / ROOT).write_text(f"{destination}\n", encoding="utf-8")
        provenance = {
            "files": [str(path) for path in [*files, ROOT]],
            "git_common_dir": str(common),
            "schema_version": 1,
            "source_graph_revision": graph_revision,
            "source_worktree": str(source),
            "source_worktree_head": source_head,
            "target_root": str(destination),
        }
        (staged / SENTINEL).write_text(
            json.dumps(provenance, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        for path in [*files, ROOT, SENTINEL]:
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged / path, target)
    finally:
        shutil.rmtree(staged, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--source-git-dir", type=Path)
    parser.add_argument("--destination-git-dir", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        seed(
            args.source,
            args.destination,
            check=args.check,
            source_git_dir=args.source_git_dir,
            destination_git_dir=args.destination_git_dir,
        )
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
