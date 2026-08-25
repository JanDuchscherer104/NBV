#!/usr/bin/env python3
"""Reconcile one seeded linked-worktree Graphify generation incrementally."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


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


def run(root: Path) -> None:
    root = root.resolve()
    if not (root / ".git").exists():
        fail(f"Graphify reconciliation root is not a Git worktree: {root}")
    cli, interpreter = trusted_graphify_runtime(root)

    scripts = Path(__file__).resolve().parent
    # The inherited projection remains immutable during no-LLM setup. Its
    # generated provenance changes every commit, so rebuilding it would mark
    # the whole semantic corpus stale before upstream can re-extract it.
    # Upstream `update` reconciles just the AST tier and preserves semantic
    # nodes plus their content-addressed cache entries.
    subprocess.run([str(cli), "update", str(root)], cwd=root, check=True)
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
