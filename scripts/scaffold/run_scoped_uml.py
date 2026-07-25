#!/usr/bin/env python3
"""Generate one scoped UML file under the ARIA-NBV package boundary."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = (ROOT / "aria_nbv/aria_nbv").resolve()
PROJECT_PYTHON = ROOT / "aria_nbv/.venv/bin/python"


def resolve_python(override: str | None) -> Path:
    """Resolve the interpreter that owns the optional Syrenka dependency."""
    candidate = override or os.environ.get("UML_PYTHON")
    if candidate:
        path = Path(candidate)
        if not path.is_absolute():
            path = ROOT / path
        path = path.resolve(strict=False)
    elif PROJECT_PYTHON.is_file():
        path = PROJECT_PYTHON
    else:
        path = Path(sys.executable).resolve()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError(f"UML Python is not executable: {path}")
    return path


def parse_paths(root_arg: str, output_arg: str) -> tuple[Path, Path]:
    root = Path(root_arg).resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"UML_ROOT must be a directory: {root_arg}")
    try:
        root.relative_to(PACKAGE_ROOT)
    except ValueError as exc:
        raise ValueError("UML_ROOT must resolve inside aria_nbv/aria_nbv") from exc

    raw_output = Path(output_arg)
    if not raw_output.is_absolute():
        raise ValueError("UML_OUT must be an absolute path")
    output = raw_output.resolve(strict=False)
    try:
        output.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(
            "UML_OUT must be an ignored path inside the repository"
        ) from exc
    if output == root or root in output.parents:
        raise ValueError("UML_OUT must not be inside UML_ROOT")
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(output.relative_to(ROOT))],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if tracked.returncode == 0:
        raise ValueError("UML_OUT must not be tracked")
    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", str(output)],
        cwd=ROOT,
        check=False,
    )
    if ignored.returncode != 0:
        raise ValueError("UML_OUT must be ignored by repository policy")
    return root, output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--python",
        help="Python containing Syrenka (default: UML_PYTHON, then aria_nbv/.venv/bin/python)",
    )
    args = parser.parse_args()
    try:
        root, output = parse_paths(args.root, args.output)
        python = resolve_python(args.python)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    dependency = subprocess.run(
        [
            str(python),
            "-c",
            "import importlib.util; raise SystemExit(importlib.util.find_spec('syrenka') is None)",
        ],
        cwd=ROOT,
        check=False,
    )
    if dependency.returncode != 0:
        print(f"error: Syrenka is unavailable in UML Python: {python}", file=sys.stderr)
        return 2

    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix="uml-", suffix=".mmd", dir=output.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            subprocess.run(
                [str(python), "-m", "syrenka", "classdiagram", str(root)],
                cwd=ROOT,
                stdout=handle,
                check=True,
            )
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Wrote: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
