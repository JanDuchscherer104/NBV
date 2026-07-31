#!/usr/bin/env python3
"""Regression tests for causal root-CI selection and aggregation."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from ci_impact import (  # noqa: E402
    CONFIG_PATH,
    REQUIRED_TIERS,
    ImpactPolicy,
    aggregate_succeeds,
    parse_labels_json,
    parse_nul_paths,
)

ALL = set(REQUIRED_TIERS)


class PolicySchemaTests(unittest.TestCase):
    def test_checked_in_policy_has_exact_schema_and_tiers(self) -> None:
        policy = ImpactPolicy.load(REPO_ROOT / CONFIG_PATH)

        self.assertEqual(policy.tiers, REQUIRED_TIERS)
        self.assertEqual(set(policy.tier_policy), ALL)
        self.assertEqual(set(policy.labels), {"ci:full"})
        self.assertEqual(policy.labels["ci:full"], frozenset(ALL))

    def assert_policy_rejected(self, policy_text: str, message: str) -> None:
        """Assert that an invalid policy fails with ``message``."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "impact.toml"
            path.write_text(policy_text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, message):
                ImpactPolicy.load(path)

    def test_schema_rejects_unknown_root_full_label_tier_and_tier_rule_keys(
        self,
    ) -> None:
        policy_text = (REPO_ROOT / CONFIG_PATH).read_text(encoding="utf-8")
        cases = (
            ("unknown = true\n" + policy_text, "root keys"),
            (
                policy_text.replace("[full]\n", "[full]\nunknown = true\n"),
                "full keys",
            ),
            (
                policy_text.replace(
                    "[labels]\n", '[labels]\n"ci:docs" = ["documentation"]\n'
                ),
                "only configured CI label",
            ),
            (
                policy_text + '\n[tier.unknown]\ninclude = ["unexpected/**"]\n',
                "tier tables",
            ),
            (
                policy_text.replace(
                    "[tier.governance]\n",
                    '[tier.governance]\nsubtract = ["package"]\n',
                ),
                "unknown keys",
            ),
        )
        for invalid, message in cases:
            with self.subTest(message=message):
                self.assert_policy_rejected(invalid, message)


class SelectionTests(unittest.TestCase):
    policy: ImpactPolicy

    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = ImpactPolicy.load(REPO_ROOT / CONFIG_PATH)

    def test_representative_tiers_and_overlap(self) -> None:
        cases = {
            ".agents/skills/aria-grill/SKILL.md": {"governance"},
            ".agents/references/source_order.md": {"governance", "graphify"},
            "aria_nbv/aria_nbv/lightning/qh_module.py": {
                "scientific",
                "graphify",
            },
            "aria_nbv/aria_nbv/rendering/candidate_depth_renderer.py": {
                "package",
                "graphify",
            },
            "aria_nbv/aria_nbv/vin/models/scene_myopic.py": {
                "package",
                "graphify",
            },
            "aria_nbv/aria_nbv/targets/protocol.py": {"package", "graphify"},
            "aria_nbv/tests/rendering/test_candidate_renderer_cpu_backend.py": {
                "package"
            },
            "docs/contents/thesis/questions.qmd": {"documentation", "graphify"},
            ".graphifyignore": {"graphify"},
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(self.policy.select([path]), expected)

    def test_documentation_tier_executes_quartodoc_config_regression(self) -> None:
        test_path = "scripts/tests/test_quartodoc_expand_config.py"
        self.assertEqual(self.policy.select([test_path]), {"documentation"})

        result = subprocess.run(
            [
                "make",
                "--dry-run",
                "ci-documentation",
                "PYTHON_INTERPRETER=python",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "python -m pytest --import-mode=importlib "
            "scripts/tests/test_quartodoc_expand_config.py",
            result.stdout,
        )
        workflow = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        documentation_job = workflow.split("  documentation:\n", 1)[1].split(
            "\n  graphify:\n", 1
        )[0]
        self.assertIn(
            "python -m pip install --upgrade pip PyYAML pytest",
            documentation_job,
        )

    def test_agent_graphify_corpus_excludes_history_transcripts_skills_and_work(
        self,
    ) -> None:
        corpus = (
            ".agents/AGENTS_INTERNAL_DB.md",
            ".agents/issues.toml",
            ".agents/references/source_order.md",
            ".agents/memory/state/DECISIONS.md",
        )
        excluded = (
            ".agents/archive/old.md",
            ".agents/memory/history/2026/07/debrief.md",
            ".agents/memory/transcripts/raw/chat.jsonl",
            ".agents/skills/agent-behavior/SKILL.md",
            ".agents/work/review.md",
        )
        for path in corpus:
            with self.subTest(path=path):
                self.assertIn("graphify", self.policy.select([path]))
        for path in excluded:
            with self.subTest(path=path):
                self.assertEqual(self.policy.select([path]), {"governance"})

    def test_multi_path_selection_is_a_union(self) -> None:
        self.assertEqual(
            self.policy.select(
                ["docs/index.qmd", "aria_nbv/tests/rendering/test_x.py"]
            ),
            {"documentation", "graphify", "package"},
        )

    def test_scientific_and_package_targets_own_distinct_contracts(self) -> None:
        scientific = subprocess.run(
            ["make", "--dry-run", "ci-scientific", "PYTEST_ARGS="],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        package = subprocess.run(
            [
                "make",
                "--dry-run",
                "ci-package",
                "PYTHON_INTERPRETER=python",
                "PYTEST_ARGS=",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(scientific.returncode, 0, scientific.stderr)
        self.assertEqual(package.returncode, 0, package.stderr)
        self.assertIn("tests/lightning/test_qh_module.py", scientific.stdout)
        self.assertNotIn(
            "tests/rendering/test_candidate_renderer_cpu_backend.py", scientific.stdout
        )
        self.assertIn(
            "tests/rendering/test_candidate_renderer_cpu_backend.py",
            package.stdout,
        )
        self.assertNotIn("tests/lightning/test_qh_module.py", package.stdout)
        self.assertIn(
            "./scripts/tests/test_quarto_generate_api_docs.sh",
            package.stdout,
        )
        self.assertIn(
            "python -m pytest --import-mode=importlib "
            "scripts/tests/test_quartodoc_expand_config.py",
            package.stdout,
        )

    def test_shared_controls_and_unknown_paths_fail_closed(self) -> None:
        for paths in (
            ["Makefile"],
            ["aria_nbv/uv.lock"],
            ["unexpected/new.txt"],
            ["docs/index.qmd", "unexpected/new.txt"],
        ):
            with self.subTest(paths=paths):
                self.assertEqual(self.policy.select(paths), ALL)

    def test_labels_only_add_and_unknown_labels_are_inert(self) -> None:
        path = [".agents/skills/aria-grill/SKILL.md"]
        baseline = self.policy.select(path)

        self.assertEqual(self.policy.select(path, ["unknown"]), baseline)
        self.assertEqual(self.policy.select(path, ["-package"]), baseline)
        self.assertEqual(self.policy.select(path, ["ci:full"]), ALL)
        self.assertTrue(baseline <= self.policy.select(path, ["ci:full"]))

    def test_cross_tier_rename_reports_source_and_destination(self) -> None:
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
            source = repo / "aria_nbv/aria_nbv/rendering/source.py"
            source.parent.mkdir(parents=True)
            source.write_text("VALUE = 1\n", encoding="utf-8")
            subprocess.run(["git", "-C", repo, "add", "."], check=True)
            subprocess.run(["git", "-C", repo, "commit", "-qm", "base"], check=True)
            destination = repo / "docs/contents/source.py"
            destination.parent.mkdir(parents=True)
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
                self.policy.select(parse_nul_paths(changed)),
                {"package", "documentation", "graphify"},
            )

    def test_nul_and_label_parsers_reject_malformed_values(self) -> None:
        self.assertEqual(parse_nul_paths(b""), [])
        for path_bytes in (b"docs/index.qmd", b"docs/index.qmd\0\0"):
            with self.subTest(raw=path_bytes):
                with self.assertRaises(ValueError):
                    parse_nul_paths(path_bytes)
        for labels_json in ('{"name":"ci:full"}', '["ci:full", 2]', "not-json"):
            with self.subTest(raw=labels_json):
                with self.assertRaises(ValueError):
                    parse_labels_json(labels_json)


class AggregateTests(unittest.TestCase):
    def test_selected_success_and_unselected_skipped_or_success_pass(self) -> None:
        selected = {tier: tier == "scientific" for tier in REQUIRED_TIERS}
        skipped = {tier: "skipped" for tier in REQUIRED_TIERS}
        skipped["scientific"] = "success"
        eager = dict.fromkeys(REQUIRED_TIERS, "success")

        self.assertTrue(aggregate_succeeds(selected, skipped, impact_result="success"))
        self.assertTrue(aggregate_succeeds(selected, eager, impact_result="success"))

    def test_selected_skip_and_any_failure_cancel_or_missing_fail(self) -> None:
        selected = {tier: tier == "scientific" for tier in REQUIRED_TIERS}
        baseline = {tier: "skipped" for tier in REQUIRED_TIERS}
        baseline["scientific"] = "success"

        selected_skip = dict(baseline)
        selected_skip["scientific"] = "skipped"
        self.assertFalse(
            aggregate_succeeds(selected, selected_skip, impact_result="success")
        )
        for bad_result in ("failure", "cancelled", ""):
            results = dict(baseline)
            results["package"] = bad_result
            with self.subTest(result=bad_result):
                self.assertFalse(
                    aggregate_succeeds(selected, results, impact_result="success")
                )
        self.assertFalse(
            aggregate_succeeds(selected, baseline, impact_result="failure")
        )
        self.assertFalse(
            aggregate_succeeds(
                selected,
                {"scientific": "success"},
                impact_result="success",
            )
        )


class WorkflowContractTests(unittest.TestCase):
    workflow: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = (REPO_ROOT / ".github/workflows/ci.yml").read_text(
            encoding="utf-8"
        )

    def test_workflow_has_exact_unique_aggregate_identity(self) -> None:
        jobs = re.findall(
            r"^  ([a-z][a-z-]*):\n", self.workflow.split("jobs:\n", 1)[1], re.M
        )

        self.assertTrue(self.workflow.startswith("name: Root Verification\n"))
        self.assertEqual(
            jobs,
            [
                "impact",
                "governance",
                "scientific",
                "package",
                "documentation",
                "graphify",
                "ci",
            ],
        )
        self.assertEqual(jobs.count("ci"), 1)
        ci_block = self.workflow.split("  ci:\n", 1)[1]
        self.assertIn("    if: always()\n", ci_block)
        self.assertIn(
            "needs: [impact, governance, scientific, package, documentation, graphify]",
            ci_block,
        )

    def test_each_policy_tier_has_one_workflow_job_and_make_target(self) -> None:
        makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
        for tier in REQUIRED_TIERS:
            with self.subTest(tier=tier):
                self.assertEqual(self.workflow.count(f"  {tier}:\n"), 1)
                self.assertIn(f"run: make ci-{tier}", self.workflow)
                self.assertRegex(makefile, rf"(?m)^ci-{tier}:[^\n]*")

    def test_pull_request_jobs_validate_default_synthetic_merge_checkout(self) -> None:
        self.assertEqual(self.workflow.count("uses: actions/checkout@v4"), 7)
        self.assertNotIn(
            "ref: ${{ github.event.pull_request.head.sha || github.sha }}",
            self.workflow,
        )
        self.assertNotRegex(
            self.workflow,
            r"(?m)^\s+ref:\s+\$\{\{\s*github\.event\.pull_request\.head\.sha",
        )

    def test_governance_target_executes_g002_and_g003_regression_suites(self) -> None:
        makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn(
            "ci-governance: agents-db-validate check-agent-memory "
            "scaffold-audit scaffold-audit-self-test",
            makefile,
        )

    def test_workflow_triggers_are_unfiltered_and_cover_queue_events(self) -> None:
        trigger_block = self.workflow.split("on:\n", 1)[1].split("\npermissions:", 1)[0]

        self.assertIn(
            "pull_request:\n    types: [opened, synchronize, reopened, labeled, unlabeled]",
            trigger_block,
        )
        self.assertIn("merge_group:\n    types: [checks_requested]", trigger_block)
        self.assertIn("push:\n    branches: [main]", trigger_block)
        self.assertIn("workflow_dispatch:", trigger_block)
        self.assertNotIn("paths:", trigger_block)

    def test_pr_selection_uses_three_dot_diff_and_json_label_environment(self) -> None:
        self.assertIn(
            'git diff --no-renames --name-only -z "$PR_BASE_SHA...$PR_HEAD_SHA"',
            self.workflow,
        )
        self.assertIn(
            "PR_LABELS_JSON: ${{ toJSON(github.event.pull_request.labels.*.name) }}",
            self.workflow,
        )
        run_block = self.workflow.split("      - name: Select affected CI tiers\n", 1)[
            1
        ].split("\n  governance:", 1)[0]
        self.assertNotIn(
            "${{ github.event.pull_request.labels", run_block.split("run: |", 1)[1]
        )
        self.assertIn('--labels-json "$PR_LABELS_JSON"', run_block)

    def test_impact_job_owns_ratchet_once_against_pr_base(self) -> None:
        impact = self.workflow.split("  impact:\n", 1)[1].split("\n  governance:\n", 1)[
            0
        ]
        self.assertEqual(self.workflow.count("make python-standards-ratchet"), 1)
        self.assertIn("make python-standards-ratchet", impact)
        self.assertIn('PYTHON_STANDARDS_BASE="$PR_BASE_SHA"', impact)

        for job, next_job in (("scientific", "package"), ("package", "documentation")):
            block = self.workflow.split(f"  {job}:\n", 1)[1].split(
                f"\n  {next_job}:\n", 1
            )[0]
            with self.subTest(job=job):
                self.assertNotIn("python-standards-ratchet", block)


class CliTests(unittest.TestCase):
    def test_cli_full_mode_writes_all_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "outputs"
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts/ci_impact.py"),
                    "--config",
                    str(REPO_ROOT / CONFIG_PATH),
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
                {f"{tier}=true" for tier in REQUIRED_TIERS},
            )

    def test_cli_aggregate_mode_obeys_skipped_path_contract(self) -> None:
        env = os.environ.copy()
        env.update(
            {
                "CI_IMPACT_RESULT": "success",
                "CI_SELECTED_JSON": '{"governance":"false","scientific":"true",'
                '"package":"false","documentation":"false","graphify":"false"}',
                "CI_RESULTS_JSON": '{"governance":"skipped","scientific":"success",'
                '"package":"skipped","documentation":"skipped","graphify":"skipped"}',
            }
        )
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/ci_impact.py"),
                "--config",
                str(REPO_ROOT / CONFIG_PATH),
                "--check-aggregate",
            ],
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cli_detector_failure_is_nonzero(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/ci_impact.py"),
                "--config",
                str(REPO_ROOT / CONFIG_PATH),
            ],
            input=b"not-nul-terminated",
            check=False,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
