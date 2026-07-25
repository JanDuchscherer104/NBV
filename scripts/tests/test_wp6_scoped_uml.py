#!/usr/bin/env python3
"""Adversarial path tests for the single retained scoped UML command."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/scaffold/run_scoped_uml.py"
PACKAGE = ROOT / "aria_nbv/aria_nbv"


def run(
    root: Path | str,
    output: Path | str,
    *,
    python: Path | None = None,
    pythonpath: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(RUNNER),
        "--root",
        str(root),
        "--output",
        str(output),
    ]
    if python is not None:
        command.extend(["--python", str(python)])
    env = None
    if pythonpath is not None:
        env = {**os.environ, "PYTHONPATH": str(pythonpath)}
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="wp6-uml-") as tmp:
        tmp_path = Path(tmp)
        fake_package = tmp_path / "syrenka"
        fake_package.mkdir()
        (fake_package / "__init__.py").write_text("", encoding="utf-8")
        (fake_package / "__main__.py").write_text(
            "import sys\nprint('classDiagram')\nprint('class ' + sys.argv[-1].split('/')[-1])\n",
            encoding="utf-8",
        )
        output = ROOT / ".cache/wp6-uml/package.mmd"
        result = run(
            PACKAGE / "utils",
            output,
            python=Path(sys.executable),
            pythonpath=tmp_path,
        )
        assert result.returncode == 0, result.stderr
        assert output.read_text(encoding="utf-8").startswith("classDiagram\n")
        output.unlink()

        missing_python = tmp_path / "python-without-syrenka"
        missing_python.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        missing_python.chmod(0o755)
        missing = run(PACKAGE / "utils", output, python=missing_python)
        assert missing.returncode == 2
        assert "Syrenka is unavailable in UML Python" in missing.stderr

        outside = tmp_path / "outside"
        outside.mkdir()
        symlink = PACKAGE / ".wp6-symlink-probe"
        symlink.symlink_to(outside, target_is_directory=True)
        try:
            rejected = [
                run(ROOT, ROOT / ".cache/wp6-uml/root.mmd"),
                run(ROOT / "docs", ROOT / ".cache/wp6-uml/docs.mmd"),
                run(PACKAGE / "utils/../../..", ROOT / ".cache/wp6-uml/traversal.mmd"),
                run(symlink, ROOT / ".cache/wp6-uml/symlink.mmd"),
                run(PACKAGE / "utils", "relative.mmd"),
                run(PACKAGE / "utils", ROOT / "tracked-output.mmd"),
                run(PACKAGE / "utils", tmp_path / "outside.mmd"),
            ]
            assert all(item.returncode == 2 for item in rejected), [
                item.stderr for item in rejected
            ]
        finally:
            symlink.unlink(missing_ok=True)

    print("WP6 scoped UML: PASS (1 accepted, 8 rejected)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
