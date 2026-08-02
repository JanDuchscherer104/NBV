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
        self.assertIn('"scripts/check_graphify_freshness.py"', workflow)
        self.assertIn('"scripts/setup_worktree_env.sh"', workflow)
        self.assertIn('"scripts/ci_impact.py"', workflow)
        self.assertIn('"scripts/tests/test_build_graphify_projection.py"', workflow)
        self.assertIn('"scripts/tests/test_ci_impact.py"', workflow)
        self.assertIn('"scripts/tests/test_graphify_freshness.py"', workflow)
        self.assertIn('"scripts/tests/test_graphify_upstream_skill.py"', workflow)
        self.assertIn('"scripts/tests/test_setup_worktree_env.sh"', workflow)
        self.assertIn("bash scripts/tests/test_setup_worktree_env.sh", workflow)
        self.assertIn("python3 scripts/tests/test_graphify_freshness.py", workflow)
        self.assertIn(
            "python3 scripts/tests/test_graphify_upstream_skill.py",
            workflow,
        )
        self.assertIn(
            "make qmd-frontmatter-check api-docs-self-test docs-render-core", workflow
        )
        makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn(
            "docs-render-core: graphify-projection-self-test "
            "graphify-projection-live-check",
            makefile,
        )
        self.assertIn("graphify-projection-live-check: _check_python", makefile)
        self.assertIn("graphify-usable-check: _check_python", makefile)
        self.assertIn("graphify-state-check: _check_python", makefile)
        self.assertIn(
            "scaffold-check: agents-db-validate check-agent-memory "
            "scaffold-audit scaffold-audit-self-test graphify-state-check",
            makefile,
        )
        self.assertIn(
            "scripts/build_graphify_projection.py --check --aria-code-ref "
            '"$$(git rev-parse HEAD)"',
            makefile,
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
            "scripts/check_graphify_freshness.py": {"scaffold"},
            "scripts/setup_worktree_env.sh": {"scaffold"},
            "scripts/tests/test_graphify_freshness.py": {"scaffold"},
            "scripts/tests/test_graphify_upstream_skill.py": {"scaffold"},
            "scripts/tests/test_setup_worktree_env.sh": {"scaffold"},
            "docs/literature/sources.jsonl": {"docs"},
            "docs/literature/README.md": {"docs"},
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(select_families([path]), expected)

    def test_graphify_corpus_admits_only_bounded_routing_owners(self) -> None:
        policy = (REPO_ROOT / ".graphifyignore").read_text(encoding="utf-8")
        cases = {
            "AGENTS.md": False,
            "aria_nbv/AGENTS.md": False,
            "docs/AGENTS.md": False,
            ".agents/skills/agent-behavior/SKILL.md": False,
            ".agents/skills/agent-behavior/references/detail.md": True,
            ".agents/skills/agent-behavior/scripts/helper.py": True,
            "aria_nbv/tests/test_projection.py": True,
            "scripts/tests/test_ci_impact.py": True,
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / ".gitignore").write_text(policy, encoding="utf-8")
            for relative in cases:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture\n", encoding="utf-8")

            for relative, expected_ignored in cases.items():
                result = subprocess.run(
                    ["git", "check-ignore", "--no-index", "--quiet", relative],
                    cwd=root,
                    check=False,
                )
                self.assertEqual(
                    result.returncode == 0,
                    expected_ignored,
                    f"unexpected corpus policy for {relative}",
                )

    def test_graphify_guidance_uses_graph_by_default_and_validates_state(self) -> None:
        skill_root = REPO_ROOT / ".agents/skills/graphify"
        context_guidance = (
            REPO_ROOT / ".agents/skills/aria-nbv-context/SKILL.md"
        ).read_text(encoding="utf-8")
        root_guidance = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("scripts/check_graphify_freshness.py --json", context_guidance)
        self.assertIn("result says `usable: true`", context_guidance)
        self.assertIn("make graphify-state-check", context_guidance)
        self.assertIn("scripts/build_graphify_projection.py", context_guidance)
        self.assertIn('fork_turns="none"', context_guidance)
        self.assertIn("every dispatched file", context_guidance)
        self.assertEqual(
            (skill_root / ".graphify_version").read_text(encoding="utf-8").strip(),
            "0.9.31",
        )
        self.assertTrue((skill_root / "references/query.md").is_file())
        self.assertIn("aria-nbv-context", root_guidance)
        self.assertNotIn("graphify query", root_guidance)
        self.assertNotIn("graphify install", root_guidance)

        hooks = (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
        self.assertIn("id: graphify-usable-check", hooks)
        self.assertIn("entry: make graphify-usable-check", hooks)
        self.assertIn("id: graphify-state-check", hooks)
        self.assertIn("entry: make graphify-state-check", hooks)
        self.assertIn("- pre-push", hooks)

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
