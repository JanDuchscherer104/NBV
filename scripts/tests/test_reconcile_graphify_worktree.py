#!/usr/bin/env python3
"""Contract tests for the setup-owned incremental Graphify reconciler."""

from __future__ import annotations

import json
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
            projection = root / "graphify-input"
            projection.mkdir()
            (projection / "index.md").write_text("# fixture\n", encoding="utf-8")
            (output / "graph.json").write_text(
                json.dumps(
                    {
                        "nodes": [{"_origin": "semantic"}],
                        "links": [{"_origin": "semantic"}],
                    }
                ),
                encoding="utf-8",
            )
            interpreter = root.parent / "trusted-python"
            interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
            interpreter.chmod(0o755)
            (output / ".graphify_python").write_text(
                f"{interpreter}\n", encoding="utf-8"
            )
            graphify = root.parent / "trusted-graphify"
            graphify.write_text(f"#!{interpreter}\n", encoding="utf-8")
            graphify.chmod(0o755)
            recorded: list[tuple[str, ...]] = []

            def completed(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                recorded.append(tuple(command))
                if command[:3] == ["git", "rev-parse", "--verify"]:
                    return subprocess.CompletedProcess(command, 0, "a" * 40 + "\n", "")
                if command[:3] == [str(interpreter), "-I", "-c"]:
                    if "detect" in command[3]:
                        return subprocess.CompletedProcess(
                            command,
                            0,
                            '{"document": ["graphify-input/index.md"], "paper": [], "image": []}\n',
                            "",
                        )
                    return subprocess.CompletedProcess(
                        command, 0, f"{reconcile.PINNED_GRAPHIFY_VERSION}\n", ""
                    )
                return subprocess.CompletedProcess(command, 0, "", "")

            with (
                mock.patch.object(reconcile.shutil, "which", return_value=str(graphify)),
                mock.patch.object(reconcile.subprocess, "run", side_effect=completed),
            ):
                reconcile.run(root)

        self.assertEqual(recorded[0][:3], (str(interpreter), "-I", "-c"))
        self.assertTrue(
            any(
                any("build_graphify_projection.py" in item for item in command)
                for command in recorded
            )
        )
        update = (str(graphify.resolve()), "update", str(root.resolve()))
        self.assertIn(update, recorded)
        self.assertEqual(recorded[-1][-2:], ("--usable", "--quiet"))
        self.assertNotIn("extract", update)

    def test_rejects_a_marker_that_differs_from_the_cli_interpreter(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aria-reconcile-") as temporary:
            root = Path(temporary)
            output = root / "graphify-out"
            output.mkdir()
            trusted = root.parent / "trusted-python"
            trusted.write_text("#!/bin/sh\n", encoding="utf-8")
            trusted.chmod(0o755)
            marker = root.parent / "other-python"
            marker.write_text("#!/bin/sh\n", encoding="utf-8")
            marker.chmod(0o755)
            (output / ".graphify_python").write_text(f"{marker}\n", encoding="utf-8")
            cli = root.parent / "trusted-graphify"
            cli.write_text(f"#!{trusted}\n", encoding="utf-8")
            cli.chmod(0o755)
            with mock.patch.object(reconcile.shutil, "which", return_value=str(cli)):
                with self.assertRaisesRegex(ValueError, "does not match"):
                    reconcile.trusted_graphify_runtime(root)

    def test_rejects_an_unpinned_cli_before_update(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aria-reconcile-") as temporary:
            root = Path(temporary)
            (root / ".git").mkdir()
            output = root / "graphify-out"
            output.mkdir()
            interpreter = root.parent / "trusted-python"
            interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
            interpreter.chmod(0o755)
            (output / ".graphify_python").write_text(
                f"{interpreter}\n", encoding="utf-8"
            )
            cli = root.parent / "trusted-graphify"
            cli.write_text(f"#!{interpreter}\n", encoding="utf-8")
            cli.chmod(0o755)
            recorded: list[tuple[str, ...]] = []

            def wrong_version(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                recorded.append(tuple(command))
                return subprocess.CompletedProcess(command, 0, "0.0.0\n", "")

            with (
                mock.patch.object(reconcile.shutil, "which", return_value=str(cli)),
                mock.patch.object(
                    reconcile.subprocess, "run", side_effect=wrong_version
                ),
            ):
                with self.assertRaisesRegex(ValueError, "not 0.9.48"):
                    reconcile.run(root)
            self.assertEqual(len(recorded), 1)

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
