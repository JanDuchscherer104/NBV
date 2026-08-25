#!/usr/bin/env python3
"""Reconcile one seeded linked-worktree Graphify generation incrementally."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


PINNED_GRAPHIFY_VERSION = "0.9.48"
GRAPH = Path("graphify-out/graph.json")
PROJECTION = Path("graphify-input")
RECEIPT = Path("graphify-out/.aria-graphify-reconcile.json")


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


def projection_hashes(root: Path) -> dict[str, str]:
    """Hash local projection inputs before and after deterministic regeneration."""
    projection = root / PROJECTION
    if projection.is_symlink() or not projection.is_dir():
        fail("Graphify projection is missing or unsafe")
    hashes: dict[str, str] = {}
    for path in projection.rglob("*.md"):
        if path.is_symlink() or not path.is_file():
            fail(f"Graphify projection source is unsafe: {path}")
        hashes[path.relative_to(root).as_posix()] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    if not hashes:
        fail("Graphify projection has no Markdown sources")
    return hashes


def semantic_sources(interpreter: Path, root: Path) -> dict[str, str]:
    """Return Graphify's semantic corpus with content digests."""
    program = """
import json
import sys
from pathlib import Path
from graphify.detect import detect

root = Path(sys.argv[1]).resolve()
result = detect(root, follow_symlinks=False, google_workspace=False)
files = result.get('files', {})
print(json.dumps({kind: files.get(kind, []) for kind in ('document', 'paper', 'image')}))
"""
    result = subprocess.run(
        [str(interpreter), "-I", "-c", program, str(root)],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        fail(f"Graphify semantic corpus detection failed: {result.stderr.strip()}")
    try:
        groups = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        fail(f"Graphify semantic corpus detection returned invalid JSON: {error}")
    if not isinstance(groups, dict):
        fail("Graphify semantic corpus detection returned an invalid result")
    sources: dict[str, str] = {}
    for kind in ("document", "paper", "image"):
        paths = groups.get(kind)
        if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
            fail("Graphify semantic corpus detection returned invalid paths")
        for raw in paths:
            path = root / raw
            try:
                resolved = path.resolve(strict=True)
                relative = resolved.relative_to(root).as_posix()
            except (OSError, RuntimeError, ValueError) as error:
                fail(f"Graphify semantic source is unsafe: {raw}: {error}")
            if not resolved.is_file():
                fail(f"Graphify semantic source is unsafe: {raw}")
            sources[relative] = hashlib.sha256(resolved.read_bytes()).hexdigest()
    if not sources:
        fail("Graphify semantic corpus is empty")
    return dict(sorted(sources.items()))


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


def write_receipt(
    root: Path,
    revision: str,
    semantic: dict[str, str],
    projection_drift: list[str],
    counts: tuple[int, int],
) -> None:
    """Publish the child-local semantic baseline after a successful update."""
    receipt = root / RECEIPT
    if receipt.is_symlink():
        fail("Graphify reconciliation receipt is unsafe")
    payload = {
        "schema_version": 1,
        "head": revision,
        "projection_semantic_drift": projection_drift,
        "semantic_edge_count": counts[1],
        "semantic_node_count": counts[0],
        "semantic_source_hashes": semantic,
    }
    temporary = receipt.with_name(f".{receipt.name}.tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(receipt)


def run(root: Path) -> None:
    root = root.resolve()
    if not (root / ".git").exists():
        fail(f"Graphify reconciliation root is not a Git worktree: {root}")
    cli, interpreter = trusted_graphify_runtime(root)
    revision = head(root)
    before_projection = projection_hashes(root)
    before_counts = semantic_counts(root)

    scripts = Path(__file__).resolve().parent
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
    after_projection = projection_hashes(root)
    projection_drift = sorted(
        path
        for path in set(before_projection) | set(after_projection)
        if before_projection.get(path) != after_projection.get(path)
    )
    semantic = semantic_sources(interpreter, root)
    subprocess.run([str(cli), "update", str(root)], cwd=root, check=True)
    after_counts = semantic_counts(root)
    if after_counts != before_counts:
        fail("Graphify AST reconciliation changed inherited semantic graph content")
    write_receipt(root, revision, semantic, projection_drift, after_counts)
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
