from __future__ import annotations

import hashlib
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "scaffold" / "validate_omx_artifacts.py"
SPEC = importlib.util.spec_from_file_location("validate_omx_artifacts", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

MEMORY_SCRIPT = Path(__file__).parents[1] / "validate_agent_memory.py"
MEMORY_SPEC = importlib.util.spec_from_file_location(
    "validate_agent_memory", MEMORY_SCRIPT
)
assert MEMORY_SPEC and MEMORY_SPEC.loader
MEMORY_MODULE = importlib.util.module_from_spec(MEMORY_SPEC)
sys.modules[MEMORY_SPEC.name] = MEMORY_MODULE
MEMORY_SPEC.loader.exec_module(MEMORY_MODULE)


def _fixture(*parts: str) -> str:
    return "".join(parts)


class OmxArtifactValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "OMX Test")
        (self.repo / "README.md").write_text("fixture\n", encoding="utf-8")
        self.git("add", "README.md")
        self.git("commit", "-qm", "baseline")
        self.baseline = self.git("rev-parse", "HEAD").stdout.strip()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=self.repo, check=True, capture_output=True, text=True
        )

    def artifact(
        self,
        relative: str,
        family: str,
        role: str,
        text: str | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text or f"{role}\n", encoding="utf-8")
        payload = path.read_bytes()
        return {
            "family": family,
            "role": role,
            "path": relative,
            "native_path": relative,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
            **extra,
        }

    def bundle(self, bundle_id: str = "task-current", name: str = "") -> dict[str, Any]:
        prefix = f"{name}-" if name else ""
        definitions = [
            (f".omx/context/{prefix}context.md", "context", "context"),
            (f".omx/specs/{prefix}report.md", "specification", "report"),
            (
                f".omx/specs/{prefix}acceptance.json",
                "specification",
                "acceptance-record",
            ),
            (f".omx/plans/{prefix}plan.md", "plan", "plan"),
            (
                f".omx/specs/{prefix}test.md",
                "test_specification",
                "test-specification",
            ),
            (
                f".omx/plans/{prefix}review.md",
                "review",
                "independent-review",
            ),
            (f".omx/plans/{prefix}handoff.json", "handoff", "handoff"),
        ]
        artifacts = []
        for path, family, role in definitions:
            if family == "review":
                artifacts.append(
                    self.artifact(
                        path,
                        family,
                        role,
                        review_kinds=["architect", "critic"],
                    )
                )
            else:
                artifacts.append(self.artifact(path, family, role))
        handoff = next(item for item in artifacts if item["family"] == "handoff")
        acceptance = next(
            item for item in artifacts if item["role"] == "acceptance-record"
        )
        return {
            "id": bundle_id,
            "task": "task",
            "status": "current",
            "classification": "accepted-decision-evidence",
            "baseline_commit": self.baseline,
            "handoff_sha256": handoff["sha256"],
            "acceptance_sha256": acceptance["sha256"],
            "artifact": artifacts,
        }

    def write_registry(
        self, bundles: list[dict[str, Any]], relative: str = "registry.toml"
    ) -> Path:
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["schema_version = 1"]
        for bundle in bundles:
            lines.extend(["", "[[bundle]]"])
            for key in (
                "id",
                "task",
                "status",
                "classification",
                "baseline_commit",
                "handoff_sha256",
                "acceptance_sha256",
                "superseded_by",
            ):
                if key in bundle:
                    lines.append(f'{key} = "{bundle[key]}"')
            for artifact in bundle["artifact"]:
                lines.extend(["", "[[bundle.artifact]]"])
                for key in ("family", "role", "path", "native_path", "sha256"):
                    lines.append(f'{key} = "{artifact[key]}"')
                lines.append(f"bytes = {artifact['bytes']}")
                if artifact.get("review_kinds"):
                    values = ", ".join(
                        f'"{value}"' for value in artifact["review_kinds"]
                    )
                    lines.append(f"review_kinds = [{values}]")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def assert_invalid(self, bundle: dict[str, Any], message: str) -> None:
        with self.assertRaisesRegex(MODULE.ValidationError, message):
            MODULE.validate_registry(self.repo, self.write_registry([bundle]))

    def stage_registry(self, bundle: dict[str, Any]) -> None:
        self.write_registry([bundle], ".agents/omx_artifacts.toml")
        self.git("add", "-f", ".agents/omx_artifacts.toml", ".omx")

    def commit_registry(self, bundle: dict[str, Any], message: str) -> None:
        self.stage_registry(bundle)
        self.git("commit", "-qm", message)

    def archived(self, bundle: dict[str, Any], successor_id: str) -> dict[str, Any]:
        archived = deepcopy(bundle)
        archived["status"] = "superseded"
        archived["superseded_by"] = successor_id
        for artifact in archived["artifact"]:
            artifact["path"] = (
                f".omx/archive/accepted-bundles/{archived['id']}/"
                + artifact["native_path"].removeprefix(".omx/")
            )
        return archived

    def commit_supersession(
        self,
        original: dict[str, Any],
        successor: dict[str, Any],
        mutation: str | None = None,
    ) -> None:
        archived = self.archived(original, successor["id"])
        for artifact in archived["artifact"]:
            source = self.repo / artifact["native_path"]
            destination = self.repo / artifact["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
            source.unlink()

        if mutation == "membership":
            payload = b"extra archived evidence\n"
            path = f".omx/archive/accepted-bundles/{original['id']}/specs/extra.md"
            (self.repo / path).write_bytes(payload)
            archived["artifact"].append(
                {
                    "family": "specification",
                    "role": "extra-record",
                    "path": path,
                    "native_path": ".omx/specs/extra.md",
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "bytes": len(payload),
                }
            )
        elif mutation == "hash":
            artifact = archived["artifact"][0]
            target = self.repo / artifact["path"]
            target.write_text("changed during supersession\n", encoding="utf-8")
            payload = target.read_bytes()
            artifact["sha256"] = hashlib.sha256(payload).hexdigest()
            artifact["bytes"] = len(payload)
        elif mutation == "review":
            review = next(
                item for item in archived["artifact"] if item["family"] == "review"
            )
            review["review_kinds"] = ["architect"]

        self.write_registry([archived, successor], ".agents/omx_artifacts.toml")
        self.git("add", "-f", ".agents/omx_artifacts.toml", ".omx")
        self.git("commit", "-qm", f"supersede {mutation or 'valid'}")

    def test_success_hash_drift_and_acceptance_hash_required(self) -> None:
        bundle = self.bundle()
        registry = self.write_registry([bundle])
        self.assertEqual(len(MODULE.validate_registry(self.repo, registry)), 7)
        (self.repo / ".omx/context/context.md").write_text(
            "changed\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(MODULE.ValidationError, "hash or byte drift"):
            MODULE.validate_registry(self.repo, registry)
        bundle = self.bundle()
        bundle.pop("acceptance_sha256")
        self.assert_invalid(bundle, "invalid acceptance record")

    def test_repeated_non_specification_and_incomplete_review_fail(self) -> None:
        bundle = self.bundle()
        bundle["artifact"].append(
            self.artifact(".omx/plans/extra.md", "plan", "extra-plan")
        )
        self.assert_invalid(bundle, "invalid repeated role families")
        bundle = self.bundle()
        next(item for item in bundle["artifact"] if item["family"] == "review")[
            "review_kinds"
        ] = ["architect"]
        self.assert_invalid(bundle, r"Architect\+Critic")

    def test_privacy_scan_covers_current_and_superseded_artifacts(self) -> None:
        samples = (
            ("machine /home/example/repo/file\n", "absolute path"),
            ("runtime 019f9e3a-169a-7673-9df2-c4bd0277bd35\n", "runtime UUID"),
            ("see private/project/notes.md\n", "private or raw path part"),
            ("see local/raw/messages.jsonl\n", "private or raw path part"),
            ("<!doctype html><html>bad</html>\n", "HTML content"),
            (_fixture("-----BEGIN OPENSSH ", "PRIVATE KEY-----\n"), "private key"),
            (_fixture("token ghp_", "abcdefghijklmnopqrstuvwxyz\n"), "GitHub token"),
            (
                _fixture("token sk-proj-", "abcdefghijklmnopqrstuvwxyz\n"),
                "OpenAI API key",
            ),
            (_fixture("key AKIA", "ABCDEFGHIJKLMNOP\n"), "AWS access key ID"),
            (
                _fixture("aws_secret_", "access_key = ", "A" * 40, "\n"),
                "AWS secret access key",
            ),
            (
                _fixture("token xoxb-", "1234567890-abcdefghijklmnop\n"),
                "Slack token",
            ),
            (
                _fixture("key AIza", "SyA1234567890abcdefghijklmnopqrst\n"),
                "Google API key",
            ),
            (_fixture("token glpat-", "abcdefghijklmnopqrst\n"), "GitLab token"),
            (_fixture("token hf_", "abcdefghijklmnopqrst\n"), "Hugging Face token"),
            (
                _fixture("Authorization: Bearer ", "abcdefghijklmnopqrstuvwx\n"),
                "bearer token",
            ),
            ("contact owner@example.com\n", "email address"),
        )
        for text, message in samples:
            with self.subTest(message=message):
                bundle = self.bundle()
                target = self.repo / bundle["artifact"][0]["path"]
                target.write_text(text, encoding="utf-8")
                payload = target.read_bytes()
                bundle["artifact"][0]["sha256"] = hashlib.sha256(payload).hexdigest()
                bundle["artifact"][0]["bytes"] = len(payload)
                self.assert_invalid(bundle, message)

        current = self.bundle("task-new")
        old = self.bundle("task-old")
        archived = self.archived(old, current["id"])
        for artifact in archived["artifact"]:
            destination = self.repo / artifact["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((self.repo / artifact["native_path"]).read_bytes())
        unsafe = self.repo / archived["artifact"][0]["path"]
        unsafe.write_text("machine /home/example/repo/file\n", encoding="utf-8")
        payload = unsafe.read_bytes()
        archived["artifact"][0]["sha256"] = hashlib.sha256(payload).hexdigest()
        archived["artifact"][0]["bytes"] = len(payload)
        with self.assertRaisesRegex(MODULE.ValidationError, "absolute path"):
            MODULE.validate_registry(
                self.repo, self.write_registry([archived, current])
            )

    def test_unregistered_tracked_artifact_fails(self) -> None:
        bundle = self.bundle()
        self.stage_registry(bundle)
        MODULE.validate_tracked(
            self.repo,
            MODULE.validate_registry(
                self.repo, self.repo / ".agents/omx_artifacts.toml"
            ),
        )
        extra = self.repo / ".omx/plans/unregistered.md"
        extra.write_text("unregistered\n", encoding="utf-8")
        self.git("add", "-f", ".omx/plans/unregistered.md")
        with self.assertRaisesRegex(
            MODULE.ValidationError, "tracked OMX membership differs"
        ):
            MODULE.validate_tracked(
                self.repo,
                MODULE.validate_registry(
                    self.repo, self.repo / ".agents/omx_artifacts.toml"
                ),
            )

    def test_nonexistent_and_nonancestor_baselines_fail(self) -> None:
        bundle = self.bundle()
        bundle["baseline_commit"] = "0" * 40
        self.assert_invalid(bundle, "not a git commit")
        sibling = self.git("commit-tree", f"{self.baseline}^{{tree}}").stdout.strip()
        bundle = self.bundle()
        bundle["baseline_commit"] = sibling
        self.assert_invalid(bundle, "not an ancestor")

    def test_production_gate_rejects_base_bundle_mutation_and_removal(self) -> None:
        original = self.bundle("task-current")
        self.commit_registry(original, "accepted base")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        for change in ("mutation", "removal"):
            with self.subTest(change=change):
                bundle = deepcopy(original)
                self.git("checkout", "-qb", f"feature-{change}")
                if change == "mutation":
                    target = self.repo / bundle["artifact"][0]["path"]
                    target.write_text("mutated accepted evidence\n", encoding="utf-8")
                    payload = target.read_bytes()
                    bundle["artifact"][0]["sha256"] = hashlib.sha256(
                        payload
                    ).hexdigest()
                    bundle["artifact"][0]["bytes"] = len(payload)
                else:
                    bundle["id"] = "replacement-current"
                self.commit_registry(bundle, change)
                with patch.dict(
                    os.environ, {"GITHUB_BASE_REF": "", "GITHUB_ACTIONS": ""}
                ):
                    errors = MEMORY_MODULE.check_registered_omx_artifacts(
                        repo_root=self.repo, validator_path=SCRIPT
                    )
                self.assertRegex(
                    errors[0], "accepted bundle mutated|registered bundle removed"
                )
                self.git("checkout", "-q", "main")

    def test_history_backed_valid_supersession(self) -> None:
        original = self.bundle("task-old")
        self.commit_registry(original, "accepted base")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("checkout", "-qb", "feature-valid-supersession")
        successor = self.bundle("task-new", "successor")
        self.commit_supersession(original, successor)

        with patch.dict(os.environ, {"GITHUB_BASE_REF": "", "GITHUB_ACTIONS": ""}):
            self.assertEqual(
                MEMORY_MODULE.check_registered_omx_artifacts(
                    repo_root=self.repo, validator_path=SCRIPT
                ),
                [],
            )

    def test_history_backed_supersession_rejects_metadata_drift(self) -> None:
        original = self.bundle("task-old")
        self.commit_registry(original, "accepted base")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        for mutation in ("membership", "hash", "review"):
            with self.subTest(mutation=mutation):
                self.git("checkout", "-q", "main")
                self.git("checkout", "-qb", f"feature-{mutation}")
                successor = self.bundle("task-new", f"successor-{mutation}")
                self.commit_supersession(original, successor, mutation)
                with patch.dict(
                    os.environ, {"GITHUB_BASE_REF": "", "GITHUB_ACTIONS": ""}
                ):
                    errors = MEMORY_MODULE.check_registered_omx_artifacts(
                        repo_root=self.repo, validator_path=SCRIPT
                    )
                self.assertRegex(errors[0], "invalid or non-identical supersession")

    def test_production_gate_allows_pr1_bootstrap_without_base_registry(self) -> None:
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("checkout", "-qb", "feature-bootstrap")
        bundle = self.bundle()
        self.commit_registry(bundle, "bootstrap registry")
        with patch.dict(os.environ, {"GITHUB_BASE_REF": "", "GITHUB_ACTIONS": ""}):
            self.assertEqual(
                MEMORY_MODULE.check_registered_omx_artifacts(
                    repo_root=self.repo, validator_path=SCRIPT
                ),
                [],
            )

    def test_local_only_snapshot_fallback_is_explicit(self) -> None:
        bundle = self.bundle()
        self.stage_registry(bundle)
        output = StringIO()
        with (
            patch.dict(os.environ, {"GITHUB_BASE_REF": "", "GITHUB_ACTIONS": ""}),
            redirect_stdout(output),
        ):
            errors = MEMORY_MODULE.check_registered_omx_artifacts(
                repo_root=self.repo, validator_path=SCRIPT
            )
        self.assertEqual(errors, [])
        self.assertIn("local-only snapshot validation", output.getvalue())

    def test_hosted_ci_requires_a_valid_base_ref(self) -> None:
        bundle = self.bundle()
        self.stage_registry(bundle)
        with patch.dict(
            os.environ, {"GITHUB_BASE_REF": "missing", "GITHUB_ACTIONS": "true"}
        ):
            errors = MEMORY_MODULE.check_registered_omx_artifacts(
                repo_root=self.repo, validator_path=SCRIPT
            )
        self.assertRegex(errors[0], "hosted CI requires transition comparison")

    def test_workflow_runs_lifecycle_checks_with_full_history(self) -> None:
        workflow = (Path(__file__).parents[2] / ".github/workflows/ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertRegex(
            workflow,
            r"uses: actions/checkout@v4\s+with:\s+fetch-depth: 0",
        )
        for path in (
            ".omx/**",
            ".gitignore",
            "scripts/scaffold/**",
            "scripts/tests/test_validate_omx_artifacts.py",
        ):
            with self.subTest(path=path):
                self.assertGreaterEqual(workflow.count(f'- "{path}"'), 2)
        self.assertIn("python scripts/tests/test_validate_omx_artifacts.py", workflow)


if __name__ == "__main__":
    unittest.main()
