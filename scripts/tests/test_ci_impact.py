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


def frontmatter_list_items(document: str, key: str) -> list[str]:
    """Return scalar items from one top-level frontmatter list."""
    frontmatter = document.split("---", 2)[1]
    lines = frontmatter.splitlines()
    key_index = next(
        index for index, line in enumerate(lines) if line.strip() == f"{key}:"
    )
    key_indent = len(lines[key_index]) - len(lines[key_index].lstrip())
    items: list[str] = []
    for line in lines[key_index + 1 :]:
        stripped = line.strip()
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= key_indent:
            break
        if not stripped.startswith("- "):
            continue
        value = stripped.removeprefix("- ").strip()
        if value[:1] in {"'", '"'} and value[-1:] == value[:1]:
            value = value[1:-1]
        items.append(value)
    return items


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
        self.assertIn(
            'pip install --upgrade pip pytest PyYAML "graphifyy==0.9.31"',
            workflow,
        )
        self.assertIn("TYPST_VERSION: 0.14.2", workflow)
        self.assertIn("TYPST_EXPECTED_VERSION: typst 0.14.2 (b33de9de)", workflow)
        self.assertIn(
            "https://github.com/typst/typst/releases/download/"
            "v0.14.2/typst-x86_64-unknown-linux-musl.tar.xz",
            workflow,
        )
        self.assertIn(
            "a6044cbad2a954deb921167e257e120ac0a16b20339ec01121194ff9d394996d",
            workflow,
        )
        self.assertIn("curl --fail --location --retry 5", workflow)
        self.assertIn("sha256sum --check --strict", workflow)
        self.assertIn('echo "${install_root}" >> "${GITHUB_PATH}"', workflow)
        self.assertIn(
            'test "$(typst --version)" = "${TYPST_EXPECTED_VERSION}"', workflow
        )
        self.assertNotIn("typst-community/setup-typst", workflow)
        self.assertNotIn("typst-version:", workflow)
        self.assertNotIn('token: ""', workflow)
        self.assertIn(
            "make agents-db-validate check-agent-memory scaffold-audit", workflow
        )
        self.assertIn("python3 scripts/tests/test_agent_governance_g002.py", workflow)
        self.assertIn("python3 scripts/tests/test_graphify_worktree_seed.py", workflow)
        self.assertIn('"scripts/build_graphify_projection.py"', workflow)
        self.assertIn('"scripts/check_graphify_freshness.py"', workflow)
        self.assertIn('"scripts/graphify_worktree_seed.py"', workflow)
        self.assertIn('"scripts/scaffold_audit.py"', workflow)
        self.assertIn('"scripts/scaffold/fixtures/routing.json"', workflow)
        self.assertIn('"scripts/setup_worktree_env.sh"', workflow)
        self.assertIn('"scripts/ci_impact.py"', workflow)
        self.assertIn('"scripts/tests/test_build_graphify_projection.py"', workflow)
        self.assertIn('"scripts/tests/test_ci_impact.py"', workflow)
        self.assertIn('"scripts/tests/test_agent_governance_g002.py"', workflow)
        self.assertIn('"scripts/tests/test_graphify_freshness.py"', workflow)
        self.assertIn('"scripts/tests/test_graphify_upstream_skill.py"', workflow)
        self.assertIn('"scripts/tests/test_graphify_worktree_seed.py"', workflow)
        self.assertIn(
            '"scripts/tests/test_ownership_consolidation_contract.py"', workflow
        )
        self.assertIn('"scripts/tests/test_validate_agent_memory_retired.py"', workflow)
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
        self.assertIn(
            "make ownership-consolidation-contract PYTHON_INTERPRETER=python",
            workflow,
        )
        self.assertIn("steps.impact.outputs.scaffold == 'true' ||", workflow)
        self.assertIn("steps.impact.outputs.docs == 'true'", workflow)
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
            "ci: agents-db-validate ownership-consolidation-contract",
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
            ".agents/skills/typst-authoring/SKILL.md": {"docs"},
            ".agents/skills/typst-authoring/references/workflow.md": {"docs"},
            "aria_nbv/aria_nbv/__init__.py": {"package"},
            "aria_nbv/aria_nbv/pose_generation/candidate_generation.py": {"package"},
            "aria_nbv/aria_nbv/pose_generation/geometry.py": {"package"},
            "aria_nbv/tests/pose_generation/test_api_geometry_contracts.py": {
                "package"
            },
            ".configs/example.toml": {"package"},
            ".graphifyignore": {"docs"},
            "scripts/build_graphify_projection.py": {"docs"},
            "scripts/tests/test_build_graphify_projection.py": {"docs"},
            "scripts/check_graphify_freshness.py": {"scaffold"},
            "scripts/graphify_worktree_seed.py": {"scaffold"},
            "scripts/scaffold_audit.py": {"scaffold"},
            "scripts/scaffold/fixtures/routing.json": {"scaffold"},
            "scripts/setup_worktree_env.sh": {"scaffold"},
            "scripts/tests/test_agent_governance_g002.py": {"scaffold"},
            "scripts/tests/test_graphify_freshness.py": {"scaffold"},
            "scripts/tests/test_graphify_upstream_skill.py": {"scaffold"},
            "scripts/tests/test_graphify_worktree_seed.py": {"scaffold"},
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
        context_path = REPO_ROOT / ".agents/skills/aria-nbv-context/SKILL.md"
        context_guidance = context_path.read_text(encoding="utf-8")
        boundary_owner = (
            ".agents/skills/aria-nbv-context/references/graphify-aria-boundary.md"
        )
        canonical_sources = frontmatter_list_items(
            context_guidance, "canonical_sources"
        )

        self.assertIn("scripts/check_graphify_freshness.py --json", context_guidance)
        self.assertIn("make graphify-state-check", context_guidance)
        self.assertIn("scripts/setup_worktree_env.sh", context_guidance)
        self.assertIn(boundary_owner, canonical_sources)
        for scalar in (boundary_owner, f"'{boundary_owner}'", f'"{boundary_owner}"'):
            with self.subTest(scalar=scalar):
                fixture = f"---\nmetadata:\n  canonical_sources:\n    - {scalar}\n---\n"
                self.assertIn(
                    boundary_owner,
                    frontmatter_list_items(fixture, "canonical_sources"),
                )
        wrong_list = f"---\nmetadata:\n  must_read:\n    - {boundary_owner}\n  canonical_sources:\n    - AGENTS.md\n---\n"
        self.assertNotIn(
            boundary_owner,
            frontmatter_list_items(wrong_list, "canonical_sources"),
        )
        self.assertTrue((REPO_ROOT / boundary_owner).is_file())
        self.assertEqual(
            (skill_root / ".graphify_version").read_text(encoding="utf-8").strip(),
            "0.9.31",
        )
        self.assertTrue((skill_root / "references/query.md").is_file())

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

    def test_freshness_fixture_uses_portable_graphify_resolution(self) -> None:
        fixture = (REPO_ROOT / "scripts/tests/test_graphify_freshness.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("/home/jd/repos/ARIA-NBV", fixture)
        self.assertIn('ROOT / "graphify-out/.graphify_python"', fixture)
        self.assertIn("Graphify 0.9.31 is required", fixture)


if __name__ == "__main__":
    unittest.main()
