#!/usr/bin/env python3
"""Regression tests for the root CI impact selector."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from ci_impact import FAMILIES, parse_nul_paths, select_families  # noqa: E402

ALL = set(FAMILIES)


class SelectionTests(unittest.TestCase):
    def test_workflow_keeps_stable_unfiltered_ci_identity(self) -> None:
        workflow = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        pull_request_block = workflow.split("  pull_request:\n", 1)[1].split(
            "  push:\n", 1
        )[0]

        self.assertTrue(workflow.startswith("name: Root Verification\n"))
        self.assertEqual(pull_request_block.strip(), "")
        self.assertIn("permissions:\n  contents: read\n", workflow)
        self.assertIn("jobs:\n  ci:\n", workflow)
        self.assertNotIn("ci-gate", workflow)
        self.assertNotIn("Install Graphify", workflow)
        self.assertNotIn("Validate Graphify", workflow)
        self.assertNotIn('pip install "graphifyy==', workflow)
        self.assertIn('"scripts/build_graphify_projection.py"', workflow)
        self.assertIn('"scripts/tests/test_build_graphify_projection.py"', workflow)
        self.assertIn(
            "make qmd-frontmatter-check graphify-projection-self-test", workflow
        )

    def test_representative_narrow_and_overlap_paths(self) -> None:
        cases = {
            "docs/index.qmd": {"docs"},
            ".agents/references/source_order.md": {"scaffold"},
            ".agents/example.qmd": {"scaffold"},
            "aria_nbv/aria_nbv/__init__.py": {"package"},
            ".configs/example.toml": {"package"},
            ".graphifyignore": {"docs"},
            "scripts/build_graphify_projection.py": {"docs"},
            "scripts/tests/test_build_graphify_projection.py": {"docs"},
            "docs/literature/sources.jsonl": {"docs"},
            "docs/literature/README.md": {"docs"},
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(select_families([path]), expected)

    def test_multi_family_diff_unions_selections(self) -> None:
        self.assertEqual(
            select_families(["docs/index.qmd", ".configs/example.toml"]),
            {"docs", "package"},
        )

    def test_cross_family_rename_reports_source_and_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            subprocess.run(["git", "init", "-q", repo], check=True)
            subprocess.run(
                ["git", "-C", repo, "config", "user.email", "ci@example.invalid"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo, "config", "user.name", "CI Test"], check=True
            )
            source = repo / "aria_nbv/source.py"
            source.parent.mkdir()
            source.write_text("VALUE = 1\n", encoding="utf-8")
            subprocess.run(["git", "-C", repo, "add", "."], check=True)
            subprocess.run(["git", "-C", repo, "commit", "-qm", "base"], check=True)
            destination = repo / "docs/source.py"
            destination.parent.mkdir()
            source.rename(destination)
            subprocess.run(["git", "-C", repo, "add", "-A"], check=True)

            changed = subprocess.run(
                [
                    "git",
                    "-C",
                    repo,
                    "diff",
                    "--cached",
                    "--no-renames",
                    "--name-only",
                    "-z",
                    "HEAD",
                ],
                check=True,
                capture_output=True,
            ).stdout

            self.assertEqual(
                select_families(parse_nul_paths(changed)),
                {"package", "docs"},
            )

    def test_shared_control_paths_select_full(self) -> None:
        for path in ("Makefile", "aria_nbv/uv.lock", "scripts/ci_impact.py"):
            with self.subTest(path=path):
                self.assertEqual(select_families([path]), ALL)

    def test_unknown_paths_fail_closed_alone_or_in_mixed_diff(self) -> None:
        self.assertEqual(select_families(["unexpected/new.txt"]), ALL)
        self.assertEqual(select_families(["docs/index.qmd", "unexpected/new.txt"]), ALL)

    def test_nul_parser_rejects_empty_or_malformed_input(self) -> None:
        for raw in (b"", b"docs/index.qmd", b"docs/index.qmd\0\0"):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    parse_nul_paths(raw)

    def test_cli_full_mode_writes_all_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "outputs"
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts/ci_impact.py"),
                    "--full",
                    "--github-output",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                set(output.read_text(encoding="utf-8").splitlines()),
                {f"{family}=true" for family in FAMILIES},
            )

    def test_cli_detector_failure_is_nonzero(self) -> None:
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts/ci_impact.py")],
            input=b"not-nul-terminated",
            check=False,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
