#!/usr/bin/env python3
"""Reconcile one seeded linked-worktree Graphify generation incrementally."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile

import check_graphify_freshness as freshness


PINNED_GRAPHIFY_VERSION = "0.9.48"
GRAPH = Path("graphify-out/graph.json")
PROJECTION = Path("graphify-input")
_HEX_OID = re.compile(r"[0-9a-f]+\Z")
_PROJECTION_TREE_DRIFT = "projection source tree differs from HEAD"


def fail(message: str) -> None:
    raise ValueError(message)


def git_temporary_root(root: Path) -> Path:
    """Return repository-local administrative storage for transient work."""
    marker = root / ".git"
    if marker.is_dir():
        temporary_root = marker.resolve()
    elif marker.is_file():
        try:
            binding = marker.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError) as error:
            fail(f"Git administrative directory is unavailable: {error}")
        if not binding.startswith("gitdir: "):
            fail("Git administrative directory is unavailable")
        configured = Path(binding.removeprefix("gitdir: "))
        temporary_root = (
            configured if configured.is_absolute() else root / configured
        ).resolve()
    else:
        fail("Git administrative directory is unavailable")
    if not temporary_root.is_dir():
        fail("Git administrative directory is unavailable")
    return temporary_root


def trusted_graphify_cli(root: Path) -> Path:
    """Return the installed CLI only when it is outside the repository."""
    discovered = shutil.which("graphify")
    if discovered is None:
        fail("trusted Graphify CLI is unavailable")
    root = root.resolve()
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

    with tempfile.TemporaryDirectory(
        prefix="aria-graphify-reconcile-trust-", dir=git_temporary_root(root)
    ) as neutral:
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


def _object_format_length(root: Path) -> int:
    """Return the exact Git object-ID length for this repository."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-object-format"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    lengths = {"sha1": 40, "sha256": 64}
    length = lengths.get(result.stdout.strip())
    if result.returncode or length is None:
        fail("Git object format is unavailable")
    return length


def commit_oid(root: Path, revision: object, label: str) -> str:
    """Authenticate one canonical full commit object before it is used."""
    if (
        not isinstance(revision, str)
        or len(revision) != _object_format_length(root)
        or _HEX_OID.fullmatch(revision) is None
    ):
        fail(f"{label} must be a canonical full commit OID")
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode or result.stdout.strip() != revision:
        fail(f"{label} must resolve as a commit object")
    return revision


def head(root: Path) -> str:
    """Return the exact commit revision for the child-local projection."""
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--end-of-options", "HEAD^{commit}"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        fail("current Git HEAD is unavailable")
    return commit_oid(root, result.stdout.strip(), "current Git HEAD")


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
    return commit_oid(root, revision, "Graphify graph provenance")


def commit_tree(root: Path, revision: str) -> str:
    """Resolve one commit to its tree, failing before any child mutation."""
    commit = commit_oid(root, revision, "Graphify revision")
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--end-of-options", f"{commit}^{{tree}}"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode or not result.stdout.strip():
        fail(f"Graphify Git tree is unavailable for {commit}")
    return result.stdout.strip()


def graph_tree_matches_head(root: Path, graph_revision: str, revision: str) -> bool:
    """Whether the inherited graph was built from the destination's exact tree."""
    return commit_tree(root, graph_revision) == commit_tree(root, revision)


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


def configured_modes(raw: str | None = None) -> tuple[str, ...]:
    """Return the setup-declared upstream semantic consumers."""
    value = raw if raw is not None else os.environ.get("ARIA_NBV_GRAPHIFY_MODES", "standard")
    modes = tuple(item.strip() for item in value.split(",") if item.strip())
    if modes not in {("standard",), ("deep",), ("standard", "deep")}:
        fail("Graphify modes must be standard, deep, or standard,deep")
    return modes


def projection_rebuild_reasons(root: Path) -> list[str]:
    """Return projection-owner changes that require rebuilding generated Markdown."""

    return [
        reason
        for reason in freshness.projection_owner_changes(root)
        if reason != _PROJECTION_TREE_DRIFT
    ]


def run(root: Path, *, modes: tuple[str, ...] | None = None) -> None:
    root = root.resolve()
    if not (root / ".git").exists():
        fail(f"Graphify reconciliation root is not a Git worktree: {root}")
    cli, interpreter = trusted_graphify_runtime(root)
    revision = head(root)
    active_modes = configured_modes() if modes is None else modes
    rebuild_projection = bool(projection_rebuild_reasons(root))

    scripts = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(
        prefix="aria-graphify-reconcile-backup-", dir=git_temporary_root(root)
    ) as temporary:
        backup = Path(temporary)
        _backup_generation(root, backup)
        try:
            if rebuild_projection:
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
            # Graphify's detector and mode-specific cache are the only source
            # of truth for no-op, dirty-input, and cold-deep decisions. A Git
            # tree match cannot prove any of those runtime states.
            for mode in active_modes:
                command = [str(cli), "extract", str(root)]
                if mode == "deep":
                    command.extend(("--mode", "deep"))
                subprocess.run(command, cwd=root, check=True)
            # The extractor has reconciled the actual worktree inputs. Stamp
            # its local graph with this worktree's commit after success.
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
    parser.add_argument("--modes", default=None)
    args = parser.parse_args(argv)
    try:
        run(args.root, modes=configured_modes(args.modes))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"error: Graphify reconciliation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
