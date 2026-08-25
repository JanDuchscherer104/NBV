#!/usr/bin/env python3
"""Reconcile one seeded linked-worktree Graphify generation incrementally."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile


PINNED_GRAPHIFY_VERSION = "0.9.48"
GRAPH = Path("graphify-out/graph.json")
PROJECTION = Path("graphify-input")
SEED = Path("graphify-out/.aria-worktree-seed.json")


def fail(message: str) -> None:
    raise ValueError(message)


def trusted_graphify_cli(root: Path) -> Path:
    """Return the installed CLI only when it is outside the repository."""
    discovered = shutil.which("graphify")
    if discovered is None:
        fail("trusted Graphify CLI is unavailable")
    cli = Path(discovered).absolute().resolve(strict=True)
    if cli.is_relative_to(root) or not cli.is_file() or not os.access(cli, os.X_OK):
        fail("trusted Graphify CLI is unsafe")
    return cli


def trusted_graphify_runtime(root: Path) -> tuple[Path, Path]:
    """Authenticate the CLI and marker before either executable runs."""
    cli = trusted_graphify_cli(root)
    try:
        shebang = cli.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, UnicodeDecodeError, IndexError) as error:
        fail(f"trusted Graphify CLI shebang is unavailable: {error}")
    if not shebang.startswith("#!"):
        fail("trusted Graphify CLI has no interpreter shebang")
    declared = Path(shebang[2:].strip())
    if not declared.is_absolute() or declared.is_relative_to(root):
        fail("trusted Graphify CLI interpreter is unsafe")
    try:
        canonical_interpreter = declared.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        fail(f"trusted Graphify CLI interpreter is unavailable: {error}")
    if not declared.is_file() or not os.access(declared, os.X_OK):
        fail("trusted Graphify CLI interpreter is unsafe")

    marker = root / "graphify-out/.graphify_python"
    if marker.is_symlink() or not marker.is_file():
        fail("Graphify interpreter marker is missing or unsafe")
    try:
        configured = Path(marker.read_text(encoding="utf-8").strip()).resolve(
            strict=True
        )
    except (OSError, RuntimeError, UnicodeDecodeError) as error:
        fail(f"Graphify interpreter marker is unavailable: {error}")
    if configured != canonical_interpreter:
        fail("Graphify interpreter marker does not match trusted CLI")

    with tempfile.TemporaryDirectory(prefix="aria-graphify-reconcile-trust-") as neutral:
        environment = {
            key: value
            for key, value in os.environ.items()
            if key not in {"PYTHONPATH", "PYTHONHOME"}
        }
        version = subprocess.run(
            [
                str(declared),
                "-I",
                "-c",
                "import graphify; from importlib.metadata import version; print(version('graphifyy'))",
            ],
            cwd=neutral,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
    if version.returncode or version.stdout.strip() != PINNED_GRAPHIFY_VERSION:
        detail = version.stderr.strip() or version.stdout.strip() or "unavailable"
        fail(
            f"trusted Graphify interpreter is not {PINNED_GRAPHIFY_VERSION}: {detail}"
        )
    return cli, declared


def head(root: Path) -> str:
    """Return the exact revision for the child-local projection."""
    return subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD^{commit}"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def semantic_counts(root: Path) -> tuple[int, int]:
    """Count semantic graph content so an AST update cannot silently discard it."""
    path = root / GRAPH
    if path.is_symlink() or not path.is_file():
        fail("Graphify graph is missing or unsafe")
    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        fail(f"Graphify graph is invalid: {error}")
    nodes = graph.get("nodes")
    edges = graph.get("links", graph.get("edges"))
    if not isinstance(nodes, list) or not isinstance(edges, list):
        fail("Graphify graph is invalid")
    return (
        sum(isinstance(node, dict) and node.get("_origin") == "semantic" for node in nodes),
        sum(isinstance(edge, dict) and edge.get("_origin") == "semantic" for edge in edges),
    )


def graph_revision(root: Path) -> str:
    """Return the provenance revision carried by the seeded graph."""
    path = root / GRAPH
    if path.is_symlink() or not path.is_file():
        fail("Graphify graph is missing or unsafe")
    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        fail(f"Graphify graph is invalid: {error}")
    revision = graph.get("built_at_commit")
    if not isinstance(revision, str) or not revision:
        fail("Graphify graph provenance is missing or invalid")
    return revision


def commit_tree(root: Path, revision: str) -> str:
    """Resolve one commit to its tree, failing before any child mutation."""
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"{revision}^{{tree}}"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode or not result.stdout.strip():
        fail(f"Graphify Git tree is unavailable for {revision}")
    return result.stdout.strip()


def graph_tree_matches_head(root: Path, graph_revision: str, revision: str) -> bool:
    """Whether the inherited graph was built from the destination's exact tree."""
    return commit_tree(root, graph_revision) == commit_tree(root, revision)


def seeded_tree_matches_head(root: Path, revision: str) -> bool:
    """Keep an inherited graph when its trusted seed has the destination tree."""
    path = root / SEED
    if not path.exists():
        return False
    if path.is_symlink() or not path.is_file():
        fail("Graphify worktree seed is missing or unsafe")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        fail(f"Graphify worktree seed is invalid: {error}")
    source_revision = payload.get("source_worktree_head")
    if not isinstance(source_revision, str) or not source_revision:
        fail("Graphify worktree seed source revision is invalid")
    return commit_tree(root, source_revision) == commit_tree(root, revision)


def stamp_graph_provenance(root: Path, revision: str) -> None:
    """Make the trusted Graphify output portable and bind it to this revision."""
    path = root / GRAPH
    if path.is_symlink() or not path.is_file():
        fail("Graphify graph is missing or unsafe")
    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        fail(f"Graphify graph is invalid: {error}")
    if not isinstance(graph, dict):
        fail("Graphify graph is invalid")
    root = root.resolve()
    for bucket in ("nodes", "edges", "links", "hyperedges"):
        items = graph.get(bucket, [])
        if not isinstance(items, list):
            fail(f"Graphify graph {bucket} must be a list")
        for item in items:
            if not isinstance(item, dict) or "source_file" not in item:
                continue
            source = item["source_file"]
            if source == "":
                # Graphify emits empty origins for synthetic AST symbols such as
                # imported typing aliases. They are not file provenance, so do
                # not preserve them as an unsafe path in the portable graph.
                item.pop("source_file")
                continue
            if not isinstance(source, str):
                fail("Graphify graph source_file is invalid")
            candidate = Path(source)
            if candidate.is_absolute():
                try:
                    relative = candidate.resolve(strict=True).relative_to(root)
                except (OSError, RuntimeError, ValueError):
                    fail(
                        f"Graphify graph source_file escapes repository: {source}"
                    )
            else:
                relative = PurePosixPath(source)
                if relative.is_absolute() or "." in relative.parts or ".." in relative.parts:
                    fail(f"Graphify graph source_file is unsafe: {source}")
            item["source_file"] = relative.as_posix()
    graph["built_at_commit"] = revision
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        fail(f"Graphify graph provenance cannot be written: {error}")


def _backup_generation(root: Path, backup: Path) -> None:
    """Copy the two reconciliation outputs so a failed update can roll back."""
    for relative in (PROJECTION, GRAPH.parent):
        source = root / relative
        if source.is_symlink() or not source.is_dir():
            fail(f"Graphify reconciliation state is missing or unsafe: {relative}")
        shutil.copytree(source, backup / relative, symlinks=True)


def _restore_generation(root: Path, backup: Path) -> None:
    """Restore the local reconciliation outputs after an ordinary failure."""
    for relative in (PROJECTION, GRAPH.parent):
        destination = root / relative
        if destination.is_symlink() or not destination.is_dir():
            fail(f"Graphify reconciliation state cannot be restored safely: {relative}")
        shutil.rmtree(destination)
        shutil.copytree(backup / relative, destination, symlinks=True)


def run(root: Path) -> None:
    root = root.resolve()
    if not (root / ".git").exists():
        fail(f"Graphify reconciliation root is not a Git worktree: {root}")
    cli, interpreter = trusted_graphify_runtime(root)
    revision = head(root)
    inherited_revision = graph_revision(root)
    before_counts = semantic_counts(root)
    equivalent_tree = (
        graph_tree_matches_head(root, inherited_revision, revision)
        or seeded_tree_matches_head(root, revision)
    )

    scripts = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="aria-graphify-reconcile-backup-") as temporary:
        backup = Path(temporary)
        _backup_generation(root, backup)
        try:
            subprocess.run(
                [
                    sys.executable,
                    str(scripts / "build_graphify_projection.py"),
                    "--output",
                    str(PROJECTION),
                    "--aria-code-ref",
                    revision,
                ],
                cwd=root,
                check=True,
            )
            if not equivalent_tree:
                subprocess.run([str(cli), "update", str(root)], cwd=root, check=True)
                after_counts = semantic_counts(root)
                if after_counts != before_counts:
                    fail("Graphify AST reconciliation changed inherited semantic graph content")
                stamp_graph_provenance(root, revision)
            subprocess.run(
                [
                    str(interpreter),
                    str(scripts / "check_graphify_freshness.py"),
                    "--usable",
                    "--quiet",
                ],
                cwd=root,
                check=True,
            )
        except BaseException:
            _restore_generation(root, backup)
            raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        run(args.root)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"error: Graphify reconciliation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
