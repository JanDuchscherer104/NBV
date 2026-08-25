#!/usr/bin/env python3
"""Reconcile one seeded linked-worktree Graphify generation incrementally."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


PINNED_GRAPHIFY_VERSION = "0.9.48"


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


def run(root: Path) -> None:
    root = root.resolve()
    if not (root / ".git").exists():
        fail(f"Graphify reconciliation root is not a Git worktree: {root}")
    interpreter_marker = root / "graphify-out/.graphify_python"
    if interpreter_marker.is_symlink() or not interpreter_marker.is_file():
        fail("Graphify interpreter marker is missing or unsafe")
    interpreter = Path(interpreter_marker.read_text(encoding="utf-8").strip())
    if not interpreter.is_absolute() or not interpreter.is_file() or not os.access(interpreter, os.X_OK):
        fail("Graphify interpreter marker is unavailable")

    scripts = Path(__file__).resolve().parent
    # The inherited projection remains immutable during no-LLM setup. Its
    # generated provenance changes every commit, so rebuilding it would mark
    # the whole semantic corpus stale before upstream can re-extract it.
    # Upstream `update` reconciles just the AST tier and preserves semantic
    # nodes plus their content-addressed cache entries.
    subprocess.run([str(trusted_graphify_cli(root)), "update", str(root)], cwd=root, check=True)
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
