#!/usr/bin/env python3
"""Contract tests for the setup-owned incremental Graphify reconciler."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import reconcile_graphify_worktree as reconcile  # noqa: E402


class ReconcileGraphifyWorktreeTests(unittest.TestCase):
    def test_runs_projection_incremental_update_then_usable_admission(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aria-reconcile-") as temporary:
            root = Path(temporary)
            (root / ".git").mkdir()
            output = root / "graphify-out"
            output.mkdir()
            interpreter = root / "trusted-python"
            interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
            interpreter.chmod(0o755)
            (output / ".graphify_python").write_text(
                f"{interpreter}\n", encoding="utf-8"
            )
            graphify = root.parent / "trusted-graphify"
            graphify.write_text("#!/bin/sh\n", encoding="utf-8")
            graphify.chmod(0o755)
            recorded: list[tuple[str, ...]] = []

            def completed(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                recorded.append(tuple(command))
                if command[:3] == ["git", "rev-parse", "--verify"]:
                    return subprocess.CompletedProcess(command, 0, "a" * 40 + "\n", "")
                return subprocess.CompletedProcess(command, 0, "", "")

            with (
                mock.patch.object(reconcile.shutil, "which", return_value=str(graphify)),
                mock.patch.object(reconcile.subprocess, "run", side_effect=completed),
            ):
                reconcile.run(root)

        self.assertEqual(recorded[0], (str(graphify.resolve()), "update", str(root.resolve())))
        self.assertEqual(recorded[1][-2:], ("--usable", "--quiet"))
        self.assertNotIn("extract", recorded[0])
        self.assertFalse(any("build_graphify_projection.py" in command for command in recorded))

    def test_rejects_a_repository_local_graphify_cli(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aria-reconcile-") as temporary:
            root = Path(temporary)
            cli = root / "graphify"
            cli.write_text("#!/bin/sh\n", encoding="utf-8")
            cli.chmod(0o755)
            with mock.patch.object(reconcile.shutil, "which", return_value=str(cli)):
                with self.assertRaisesRegex(ValueError, "unsafe"):
                    reconcile.trusted_graphify_cli(root)


if __name__ == "__main__":
    unittest.main()
