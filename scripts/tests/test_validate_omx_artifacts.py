#!/usr/bin/env python3
"""Regression tests for the registered OMX artifact lifecycle."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scaffold" / "validate_omx_artifacts.py"
SOURCE_REPO = SCRIPT.parents[2]
SPEC = importlib.util.spec_from_file_location("validate_omx_artifacts", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)

# Keep fixture vocabulary independent from implementation constants. These are the
# six roles bound by the approved successor handoff.
FIXTURE_ROLES = (
    "context",
    "test_spec",
    "plan",
    "architect_review",
    "critic_review",
    "handoff",
)


class OmxArtifactValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="omx-artifacts-")
        self.root = Path(self.temporary.name)
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        self.write(
            ".gitignore",
            "\n".join(
                (
                    ".omx/*",
                    "!.omx/context/",
                    ".omx/context/*",
                    "!.omx/context/*.md",
                    "!.omx/specs/",
                    ".omx/specs/*",
                    "!.omx/specs/*.md",
                    "!.omx/plans/",
                    ".omx/plans/*",
                    "!.omx/plans/*.md",
                    "!.omx/plans/*.json",
                    "!.omx/archive/",
                    ".omx/archive/*",
                    "!.omx/archive/accepted-bundles/",
                    ".omx/archive/accepted-bundles/*",
                    "!.omx/archive/accepted-bundles/*/",
                    "!.omx/archive/accepted-bundles/*/**",
                    "",
                )
            ),
        )
        self.write("README.md", "fixture\n")
        self.git("add", ".gitignore", "README.md")
        self.git("commit", "-qm", "fixture")
        self.source_commit = self.git("rev-parse", "HEAD").stdout.strip()
        self.registry_path = self.root / validator.REGISTRY_REL
        self.registry_path.parent.mkdir(parents=True)
        self.registry_path.write_text(
            validator.render_registry(
                {
                    "schema_version": validator.SCHEMA_VERSION,
                    "bundles": [],
                    "tombstones": [],
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        validator._FAULT_HOOK = lambda _phase: None
        self.temporary.cleanup()

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=check,
            capture_output=True,
            text=True,
        )

    def command(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args, "--repo-root", str(self.root)],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
        )

    def write(self, relative: str, content: str) -> str:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return hashlib.sha256(content.encode()).hexdigest()

    def make_draft(self, name: str, task: str | None = None) -> Path:
        task = task or name
        draft = f".omx/drafts/{name}"
        native = {
            "context": f".omx/context/{name}-context.md",
            "test_spec": f".omx/specs/{name}-test-spec.md",
            "plan": f".omx/plans/{name}-plan.md",
            "architect_review": f".omx/plans/{name}-architect-review.md",
            "critic_review": f".omx/plans/{name}-critic-review.md",
            "handoff": f".omx/plans/{name}-handoff.json",
        }
        sources = {
            role: f"{draft}/{role}.json" if role == "handoff" else f"{draft}/{role}.md"
            for role in FIXTURE_ROLES
        }
        hashes = {
            role: self.write(sources[role], f"{role} for {name}\n")
            for role in FIXTURE_ROLES
            if role != "handoff"
        }
        handoff = {
            "schema_version": 2,
            "task_slug": task,
            "status": "approved",
            "baseline_commit": self.source_commit,
            "revision_date": "2026-07-22",
            "planning_artifacts": {
                "context": {"path": sources["context"], "sha256": hashes["context"]},
                "plan": {"path": sources["plan"], "sha256": hashes["plan"]},
                "test_spec": {
                    "path": sources["test_spec"],
                    "sha256": hashes["test_spec"],
                },
            },
            "ralplan_architect_review": {
                "iteration": 1,
                "verdict": "APPROVE",
                "approved": True,
                "path": sources["architect_review"],
                "sha256": hashes["architect_review"],
                "reviewed_plan_sha256": hashes["plan"],
                "reviewed_test_spec_sha256": hashes["test_spec"],
            },
            "ralplan_critic_review": {
                "iteration": 1,
                "verdict": "APPROVE",
                "approved": True,
                "path": sources["critic_review"],
                "sha256": hashes["critic_review"],
                "reviewed_plan_sha256": hashes["plan"],
                "reviewed_test_spec_sha256": hashes["test_spec"],
                "reviewed_architect_sha256": hashes["architect_review"],
            },
            "ralplan_consensus_gate": {
                "complete": True,
                "review_order": ["architect", "critic"],
                "reason": "fixture approval",
            },
            "execution_handoff": {"authorization": "fixture"},
        }
        handoff_text = json.dumps(handoff, indent=2, sort_keys=True) + "\n"
        hashes["handoff"] = self.write(sources["handoff"], handoff_text)
        manifest = {
            "task": task,
            "handoff_sha256": hashes["handoff"],
            "status": "draft",
            "classification": "current-decision-evidence",
            "source_commit": self.source_commit,
            "review_order": ["architect", "critic"],
            "artifacts": [
                {
                    "role": role,
                    "path": sources[role],
                    "native_path": native[role],
                    "source_commit": self.source_commit,
                    "sha256": hashes[role],
                    "bytes": (self.root / sources[role]).stat().st_size,
                }
                for role in FIXTURE_ROLES
            ],
        }
        manifest_path = self.root / f"{name}.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest_path

    def promote(self, name: str, task: str | None = None) -> str:
        manifest = self.make_draft(name, task)
        self.assertEqual(
            validator.promote(manifest, "explicit-user-acceptance", False, self.root),
            0,
        )
        registry = validator.load_registry(self.registry_path)
        return next(
            item["id"] for item in registry["bundles"] if item["status"] == "current"
        )

    def commit_registry(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-qm", message)

    def registered_bytes(self) -> dict[str, bytes]:
        registry = validator.load_registry(self.registry_path)
        paths = [validator.REGISTRY_REL.as_posix()]
        paths.extend(
            item["path"]
            for bundle in registry["bundles"]
            for item in bundle["artifacts"]
        )
        return {path: (self.root / path).read_bytes() for path in paths}

    def test_promotion_uses_native_paths_and_requires_acceptance(self) -> None:
        manifest = self.make_draft("bundle-a")
        before = self.registry_path.read_bytes()
        self.assertEqual(validator.promote(manifest, "", False, self.root), 2)
        self.assertEqual(self.registry_path.read_bytes(), before)
        self.assertEqual(
            validator.promote(manifest, "explicit-user-acceptance", False, self.root),
            0,
        )
        registry = validator.load_registry(self.registry_path)
        bundle = registry["bundles"][0]
        self.assertEqual(bundle["status"], "current")
        self.assertEqual(
            bundle["id"],
            validator.canonical_bundle_id(bundle["task"], bundle["handoff_sha256"]),
        )
        self.assertTrue(
            all(item["path"] == item["native_path"] for item in bundle["artifacts"])
        )
        self.assertEqual(validator.validate_registry(registry, self.root), [])

    def test_fixture_roles_are_exact_without_importing_implementation_names(
        self,
    ) -> None:
        self.promote("bundle-a")
        registry = validator.load_registry(self.registry_path)
        observed = {item["role"] for item in registry["bundles"][0]["artifacts"]}
        self.assertEqual(observed, set(FIXTURE_ROLES))
        missing = json.loads(json.dumps(registry))
        missing["bundles"][0]["artifacts"].pop()
        self.assertTrue(
            any(
                "current roles must be exactly" in error
                for error in validator.validate_registry(missing, self.root)
            )
        )

    def test_handoff_requires_plan_architect_critic_hash_chain(self) -> None:
        manifest = self.make_draft("bundle-a")
        data = json.loads(manifest.read_text(encoding="utf-8"))
        handoff_item = next(
            item for item in data["artifacts"] if item["role"] == "handoff"
        )
        handoff_path = self.root / handoff_item["path"]
        handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
        handoff["ralplan_critic_review"]["reviewed_plan_sha256"] = "0" * 64
        handoff_path.write_text(json.dumps(handoff), encoding="utf-8")
        handoff_item["sha256"] = validator.sha256(handoff_path)
        handoff_item["bytes"] = handoff_path.stat().st_size
        data["handoff_sha256"] = handoff_item["sha256"]
        manifest.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(
            validator.promote(manifest, "explicit-user-acceptance", False, self.root), 1
        )

    def test_structured_redaction_probes_and_placeholder_exemptions(self) -> None:
        rejected = (
            "OPENAI_API_KEY=sk-live",
            "Authorization: Bearer abc.def",
            "-----BEGIN PRIVATE KEY-----",
            "/home/alice/project",
            "/Users/alice/project",
            "/tmp/report",
            "/var/cache/tool",
            ".cache/tool",
            "pane_id=%42",
            "session_id=abc123",
        )
        for probe in rejected:
            with self.subTest(probe=probe):
                self.assertTrue(validator._redaction_errors("fixture", probe))
        allowed = (
            "OPENAI_API_KEY=${OPENAI_API_KEY}",
            "Authorization: Bearer <REDACTED>",
            "https://github.com/example/project",
            "pane_id=<PANE_ID>",
        )
        for probe in allowed:
            with self.subTest(probe=probe):
                self.assertEqual(validator._redaction_errors("fixture", probe), [])

    def test_legacy_redaction_exception_is_exact_path_and_hash(self) -> None:
        [(path, digest)] = validator.LEGACY_REDACTION_ALLOWLIST.items()
        self.assertTrue(validator._legacy_redaction_allowed(path, digest))
        self.assertFalse(validator._legacy_redaction_allowed(path, "0" * 64))
        self.assertFalse(validator._legacy_redaction_allowed(path + ".copy", digest))

    def test_exact_allowlist_rejects_unregistered_paths(self) -> None:
        self.promote("bundle-a")
        self.write(".omx/plans/unregistered.md", "extra\n")
        errors = validator.validate_registry(
            validator.load_registry(self.registry_path), self.root
        )
        self.assertTrue(any("unregistered" in error for error in errors))

    def test_history_rejects_deletion_rewrite_and_reactivation(self) -> None:
        self.promote("bundle-a")
        current = validator.load_registry(self.registry_path)
        deleted = json.loads(json.dumps(current))
        deleted["bundles"] = []
        self.assertTrue(
            any(
                "deleted" in error
                for error in validator.validate_history(deleted, current, "base")
            )
        )
        rewritten = json.loads(json.dumps(current))
        rewritten["bundles"][0]["artifacts"][0]["sha256"] = "0" * 64
        self.assertTrue(
            any(
                "rewrite" in error
                for error in validator.validate_history(rewritten, current, "base")
            )
        )
        superseded = json.loads(json.dumps(current))
        superseded["bundles"][0]["status"] = "superseded"
        superseded["bundles"][0]["superseded_by"] = "successor"
        reactivated = json.loads(json.dumps(superseded))
        reactivated["bundles"][0]["status"] = "current"
        del reactivated["bundles"][0]["superseded_by"]
        self.assertTrue(
            any(
                "reactivated" in error
                for error in validator.validate_history(reactivated, superseded, "base")
            )
        )

    def test_history_rejects_first_seen_superseded_bundle_except_exact_bootstrap(
        self,
    ) -> None:
        self.promote("bundle-a")
        first_seen = validator.load_registry(self.registry_path)
        first_seen["bundles"][0]["status"] = "superseded"
        first_seen["bundles"][0]["superseded_by"] = "successor"
        empty = {
            "schema_version": validator.SCHEMA_VERSION,
            "bundles": [],
            "tombstones": [],
        }
        self.assertTrue(
            any(
                "first-seen bundle must be current" in error
                for error in validator.validate_history(first_seen, empty, "base")
            )
        )

        tracked = validator.load_registry(SOURCE_REPO / validator.REGISTRY_REL)
        bootstrap = next(
            bundle
            for bundle in tracked["bundles"]
            if bundle["id"] == validator.LEGACY_PREDECESSOR_ID
        )
        exact = {**empty, "bundles": [bootstrap]}
        self.assertEqual(validator.validate_history(exact, empty, "base"), [])
        for mutate in (
            lambda bundle: bundle.__setitem__("acceptance", "forged"),
            lambda bundle: bundle.__setitem__("superseded_by", "forged"),
            lambda bundle: bundle["artifacts"][0].__setitem__("bytes", 0),
        ):
            with self.subTest(mutate=mutate):
                adversarial = json.loads(json.dumps(exact))
                mutate(adversarial["bundles"][0])
                self.assertTrue(
                    any(
                        "first-seen bundle must be current" in error
                        for error in validator.validate_history(
                            adversarial, empty, "base"
                        )
                    )
                )

    def test_transition_classes_are_closed(self) -> None:
        self.assertTrue(validator.valid_transition("draft", "current"))
        self.assertTrue(validator.valid_transition("draft", "rejected"))
        self.assertTrue(validator.valid_transition("current", "superseded"))
        for transition in (
            ("current", "current"),
            ("current", "rejected"),
            ("superseded", "current"),
            ("superseded", "rejected"),
        ):
            with self.subTest(transition=transition):
                self.assertFalse(validator.valid_transition(*transition))

    def test_check_uses_all_committed_registry_revisions(self) -> None:
        self.promote("bundle-a")
        self.commit_registry("register bundle")
        registry = validator.load_registry(self.registry_path)
        registry["bundles"] = []
        self.registry_path.write_text(
            validator.render_registry(registry), encoding="utf-8"
        )
        self.assertTrue(any("deleted" in error for error in validator.check(self.root)))

    def test_check_rejects_intermediate_bundle_deletion(self) -> None:
        self.promote("bundle-a")
        self.commit_registry("register bundle")
        registry = validator.load_registry(self.registry_path)
        paths = [
            self.root / item["path"] for item in registry["bundles"][0]["artifacts"]
        ]
        registry["bundles"] = []
        self.registry_path.write_text(
            validator.render_registry(registry), encoding="utf-8"
        )
        for path in paths:
            path.unlink()
        self.commit_registry("delete bundle")
        self.write("README.md", "fixture after deletion\n")
        self.git("add", "README.md")
        self.git("commit", "-qm", "advance history")
        self.assertTrue(any("deleted" in error for error in validator.check(self.root)))

    def test_payload_history_rejects_initial_first_seen_superseded_bundle(self) -> None:
        self.promote("bundle-a")
        registry = validator.load_registry(self.registry_path)
        registry["bundles"][0]["status"] = "superseded"
        registry["bundles"][0]["superseded_by"] = "forged-successor"
        self.registry_path.write_text(
            validator.render_registry(registry), encoding="utf-8"
        )
        self.commit_registry("introduce forged superseded bundle")
        self.assertTrue(
            any(
                "first-seen bundle must be current" in error
                for error in validator.validate_payload_history(registry, self.root)
            )
        )

    def test_supersession_archives_predecessor_and_keeps_successor_native(self) -> None:
        predecessor_id = self.promote("bundle-a", "shared-task")
        predecessor = validator.load_registry(self.registry_path)["bundles"][0]
        predecessor_bytes = {
            item["native_path"]: (self.root / item["native_path"]).read_bytes()
            for item in predecessor["artifacts"]
        }
        successor = self.make_draft("bundle-b", "shared-task")
        self.assertEqual(
            validator.supersede(
                predecessor_id, successor, "explicit-user-acceptance", False, self.root
            ),
            0,
        )
        registry = validator.load_registry(self.registry_path)
        old = next(item for item in registry["bundles"] if item["id"] == predecessor_id)
        new = next(item for item in registry["bundles"] if item["status"] == "current")
        self.assertEqual(old["status"], "superseded")
        self.assertEqual(old["superseded_by"], new["id"])
        for item in old["artifacts"]:
            self.assertEqual(
                (self.root / item["path"]).read_bytes(),
                predecessor_bytes[item["native_path"]],
            )
            self.assertTrue(
                item["path"].startswith(f"{validator.ARCHIVE_PREFIX}/{predecessor_id}/")
            )
        self.assertTrue(
            all(item["path"] == item["native_path"] for item in new["artifacts"])
        )
        self.assertEqual(validator.validate_registry(registry, self.root), [])

    def test_supersession_rejects_different_task(self) -> None:
        predecessor_id = self.promote("bundle-a", "task-a")
        successor = self.make_draft("bundle-b", "task-b")
        self.assertEqual(
            validator.supersede(
                predecessor_id, successor, "explicit-user-acceptance", False, self.root
            ),
            1,
        )
        self.assertIn(
            "task must match",
            self.command(
                "--supersede",
                predecessor_id,
                str(successor),
                "--acceptance",
                "explicit-user-acceptance",
            ).stderr,
        )

    def test_supersession_fault_phases_restore_native_predecessor(self) -> None:
        predecessor_id = self.promote("bundle-a", "shared-task")
        before = self.registry_path.read_bytes()
        successor = self.make_draft("bundle-b", "shared-task")
        for fault_phase in (
            "supersede_after_archive",
            "supersede_after_successor",
            "supersede_after_registry",
        ):
            with self.subTest(fault_phase=fault_phase):
                validator._FAULT_HOOK = lambda phase: (
                    (_ for _ in ()).throw(RuntimeError("fault"))
                    if phase == fault_phase
                    else None
                )
                self.assertEqual(
                    validator.supersede(
                        predecessor_id,
                        successor,
                        "explicit-user-acceptance",
                        False,
                        self.root,
                    ),
                    1,
                )
                self.assertEqual(self.registry_path.read_bytes(), before)
                registry = validator.load_registry(self.registry_path)
                self.assertTrue(
                    all(
                        (self.root / item["native_path"]).is_file()
                        for item in registry["bundles"][0]["artifacts"]
                    )
                )
                self.assertFalse(
                    (self.root / validator.ARCHIVE_PREFIX / predecessor_id).exists()
                )
                validator._FAULT_HOOK = lambda _phase: None

    def test_promotion_fault_phases_restore_every_path(self) -> None:
        manifest = self.make_draft("bundle-a")
        before_registry = self.registry_path.read_bytes()
        data = json.loads(manifest.read_text(encoding="utf-8"))
        for fault_phase in ("promote_after_payload", "promote_after_registry"):
            with self.subTest(fault_phase=fault_phase):
                validator._FAULT_HOOK = lambda phase: (
                    (_ for _ in ()).throw(RuntimeError("fault"))
                    if phase == fault_phase
                    else None
                )
                self.assertEqual(
                    validator.promote(
                        manifest, "explicit-user-acceptance", False, self.root
                    ),
                    1,
                )
                self.assertEqual(self.registry_path.read_bytes(), before_registry)
                self.assertTrue(
                    all(
                        not (self.root / item["native_path"]).exists()
                        for item in data["artifacts"]
                    )
                )
                validator._FAULT_HOOK = lambda _phase: None

    def test_seed_restore_fault_phases_restore_every_path(self) -> None:
        self.promote("bundle-a")
        expected = self.registered_bytes()
        registry_bytes = self.registry_path.read_bytes()
        with tempfile.TemporaryDirectory(
            prefix="omx-seed-output-", dir=self.root.parent
        ) as raw_output:
            seed = validator.export_seed(Path(raw_output), self.root)
            payload_paths = [
                relative
                for relative in expected
                if relative != validator.REGISTRY_REL.as_posix()
            ]
            for relative in payload_paths:
                (self.root / relative).unlink()
            for fault_phase in ("restore_after_payload", "restore_after_index"):
                with self.subTest(fault_phase=fault_phase):
                    validator._FAULT_HOOK = lambda phase: (
                        (_ for _ in ()).throw(RuntimeError("fault"))
                        if phase == fault_phase
                        else None
                    )
                    self.assertEqual(validator.restore_seed(seed, self.root), 1)
                    self.assertEqual(self.registry_path.read_bytes(), registry_bytes)
                    self.assertTrue(
                        all(
                            not (self.root / relative).exists()
                            for relative in payload_paths
                        )
                    )
                    validator._FAULT_HOOK = lambda _phase: None
            self.assertEqual(validator.restore_seed(seed, self.root), 0)
            self.assertEqual(self.registered_bytes(), expected)

    def test_preexisting_archive_root_sentinel_is_never_removed(self) -> None:
        predecessor_id = self.promote("bundle-a", "shared-task")
        before = self.registered_bytes()
        archive_root = self.root / validator.ARCHIVE_PREFIX / predecessor_id
        sentinel = archive_root / "unowned-sentinel.txt"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("keep\n", encoding="utf-8")
        successor = self.make_draft("bundle-b", "shared-task")
        self.assertEqual(
            validator.supersede(
                predecessor_id,
                successor,
                "explicit-user-acceptance",
                False,
                self.root,
            ),
            1,
        )
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")
        self.assertEqual(self.registered_bytes(), before)

    def test_interrupted_supersession_recovers_on_restart(self) -> None:
        predecessor_id = self.promote("bundle-a", "shared-task")
        successor = self.make_draft("bundle-b", "shared-task")
        validator._FAULT_HOOK = lambda phase: (
            (_ for _ in ()).throw(KeyboardInterrupt())
            if phase == "supersede_after_archive"
            else None
        )
        with self.assertRaises(KeyboardInterrupt):
            validator.supersede(
                predecessor_id,
                successor,
                "explicit-user-acceptance",
                False,
                self.root,
            )
        self.assertTrue(
            (validator._recovery_root(self.root) / "journal.json").is_file()
        )
        validator._FAULT_HOOK = lambda _phase: None
        self.assertEqual(
            validator.supersede(
                predecessor_id,
                successor,
                "explicit-user-acceptance",
                False,
                self.root,
            ),
            0,
        )
        self.assertFalse(validator._recovery_root(self.root).exists())
        self.assertEqual(
            validator.validate_registry(
                validator.load_registry(self.registry_path), self.root
            ),
            [],
        )

    def test_recovery_validates_all_backups_before_first_restore_write(self) -> None:
        predecessor_id = self.promote("bundle-a", "shared-task")
        successor = self.make_draft("bundle-b", "shared-task")
        validator._FAULT_HOOK = lambda phase: (
            (_ for _ in ()).throw(KeyboardInterrupt())
            if phase == "supersede_after_archive"
            else None
        )
        with self.assertRaises(KeyboardInterrupt):
            validator.supersede(
                predecessor_id,
                successor,
                "explicit-user-acceptance",
                False,
                self.root,
            )
        recovery = validator._recovery_root(self.root)
        journal = json.loads((recovery / "journal.json").read_text(encoding="utf-8"))
        tracked = {
            entry["path"]: (
                (self.root / entry["path"]).read_bytes()
                if (self.root / entry["path"]).is_file()
                else None
            )
            for entry in journal["paths"]
        }
        index_before = validator._index_path(self.root).read_bytes()
        backup_name = next(
            entry["backup"] for entry in journal["paths"] if entry["existed"]
        )
        (recovery / "backups" / backup_name).write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "backup checksum mismatch"):
            validator.recover_incomplete_transaction(self.root)
        observed = {
            path: (
                (self.root / path).read_bytes()
                if (self.root / path).is_file()
                else None
            )
            for path in tracked
        }
        self.assertEqual(observed, tracked)
        self.assertEqual(validator._index_path(self.root).read_bytes(), index_before)

    def test_symlink_and_parent_escape_are_rejected_before_mutation(self) -> None:
        outside_temp = tempfile.TemporaryDirectory(
            prefix="omx-artifacts-outside-", dir=self.root.parent
        )
        self.addCleanup(outside_temp.cleanup)
        outside = Path(outside_temp.name)
        sentinel = outside / "sentinel.md"
        sentinel.write_text("keep\n", encoding="utf-8")
        manifest = self.make_draft("bundle-a")
        draft_link = self.root / ".omx/drafts/bundle-a/context.md"
        draft_link.unlink()
        draft_link.symlink_to(sentinel)
        before = self.registry_path.read_bytes()
        self.assertEqual(
            validator.promote(manifest, "explicit-user-acceptance", False, self.root),
            1,
        )
        self.assertEqual(self.registry_path.read_bytes(), before)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["artifacts"][0]["path"] = ".omx/../outside.md"
        manifest.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(
            validator.promote(manifest, "explicit-user-acceptance", False, self.root),
            1,
        )

    def test_seed_is_deterministic_verified_and_restorable(self) -> None:
        self.promote("bundle-a")
        expected = self.registered_bytes()
        with tempfile.TemporaryDirectory(
            prefix="omx-seed-output-", dir=self.root.parent
        ) as raw_output:
            output = Path(raw_output)
            first = validator.export_seed(output, self.root)
            second = validator.export_seed(output, self.root)
            self.assertEqual(first, second)
            self.assertEqual(set(validator.verify_seed(first)), set(expected))
            for relative in sorted(expected, reverse=True):
                (self.root / relative).unlink()
            index_before = validator._index_path(self.root).read_bytes()
            self.assertEqual(validator.restore_seed(first, self.root), 0)
            self.assertEqual(self.registered_bytes(), expected)
            self.assertNotEqual(
                validator._index_path(self.root).read_bytes(), index_before
            )

    def test_seed_restore_collision_preserves_sentinel(self) -> None:
        self.promote("bundle-a")
        expected = self.registered_bytes()
        with tempfile.TemporaryDirectory(
            prefix="omx-seed-output-", dir=self.root.parent
        ) as raw_output:
            seed = validator.export_seed(Path(raw_output), self.root)
            self.assertEqual(validator.restore_seed(seed, self.root), 1)
        self.assertEqual(self.registered_bytes(), expected)

    def test_interrupted_seed_restore_recovers_index_on_restart(self) -> None:
        self.promote("bundle-a")
        expected = self.registered_bytes()
        with tempfile.TemporaryDirectory(
            prefix="omx-seed-output-", dir=self.root.parent
        ) as raw_output:
            seed = validator.export_seed(Path(raw_output), self.root)
            for relative in sorted(expected, reverse=True):
                (self.root / relative).unlink()
            original_index = validator._index_path(self.root).read_bytes()
            validator._FAULT_HOOK = lambda phase: (
                (_ for _ in ()).throw(KeyboardInterrupt())
                if phase == "restore_after_index"
                else None
            )
            with self.assertRaises(KeyboardInterrupt):
                validator.restore_seed(seed, self.root)
            self.assertTrue(
                (validator._recovery_root(self.root) / "journal.json").is_file()
            )
            validator._FAULT_HOOK = lambda _phase: None
            self.assertEqual(validator.restore_seed(seed, self.root), 0)
            self.assertEqual(self.registered_bytes(), expected)
            self.assertNotEqual(
                validator._index_path(self.root).read_bytes(), original_index
            )

    def test_native_operation_isolation_restores_registered_mutation(self) -> None:
        self.promote("bundle-a")
        expected = self.registered_bytes()
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        fake_omx = fake_bin / "omx"
        fake_omx.write_text(
            "#!/bin/sh\n"
            'if [ "${1:-}" = --version ]; then\n'
            "  printf 'oh-my-codex v%s\\n' \"${OMX_TEST_VERSION:-0.20.3}\"\n"
            "  exit 0\n"
            "fi\n"
            "mkdir -p .omx/runtime\n"
            "printf 'runtime\\n' > .omx/runtime/native.txt\n"
            'if [ "${OMX_TEST_MUTATE:-0}" = 1 ]; then\n'
            "  printf '\\n# damage\\n' >> .agents/omx_artifacts.toml\n"
            'elif [ "${OMX_TEST_MUTATE:-0}" = unsafe ]; then\n'
            "  mkdir -p .omx/archive/accepted-bundles/native-created\n"
            '  ln -s "${OMX_TEST_OUTSIDE:?}" '
            ".omx/archive/accepted-bundles/native-created/link\n"
            "fi\n",
            encoding="utf-8",
        )
        fake_omx.chmod(0o755)
        old_path = os.environ.get("PATH", "")
        old_mutate = os.environ.get("OMX_TEST_MUTATE")
        old_outside = os.environ.get("OMX_TEST_OUTSIDE")
        old_version = os.environ.get("OMX_TEST_VERSION")

        def restore_environment() -> None:
            os.environ["PATH"] = old_path
            if old_mutate is None:
                os.environ.pop("OMX_TEST_MUTATE", None)
            else:
                os.environ["OMX_TEST_MUTATE"] = old_mutate
            if old_outside is None:
                os.environ.pop("OMX_TEST_OUTSIDE", None)
            else:
                os.environ["OMX_TEST_OUTSIDE"] = old_outside
            if old_version is None:
                os.environ.pop("OMX_TEST_VERSION", None)
            else:
                os.environ["OMX_TEST_VERSION"] = old_version

        self.addCleanup(restore_environment)
        os.environ["PATH"] = f"{fake_bin}{os.pathsep}{old_path}"
        os.environ.pop("OMX_TEST_MUTATE", None)
        with mock.patch.object(validator, "_verified_omx_install", return_value=True):
            self.assertEqual(
                validator.run_native_operation(["omx", "cleanup"], self.root), 0
            )
        self.assertEqual(self.registered_bytes(), expected)
        self.assertFalse(validator._verified_omx_install("omx"))
        os.environ["OMX_TEST_MUTATE"] = "1"
        with mock.patch.object(validator, "_verified_omx_install", return_value=True):
            self.assertEqual(
                validator.run_native_operation(["omx", "cleanup"], self.root), 1
            )
        self.assertEqual(self.registered_bytes(), expected)
        outside = self.root.parent / f"{self.root.name}-outside.txt"
        outside.write_text("keep\n", encoding="utf-8")
        self.addCleanup(outside.unlink)
        os.environ["OMX_TEST_MUTATE"] = "unsafe"
        os.environ["OMX_TEST_OUTSIDE"] = str(outside)
        with mock.patch.object(validator, "_verified_omx_install", return_value=True):
            self.assertEqual(
                validator.run_native_operation(["omx", "cleanup"], self.root), 1
            )
        self.assertFalse(
            (self.root / ".omx/archive/accepted-bundles/native-created").exists()
        )
        self.assertEqual(outside.read_text(encoding="utf-8"), "keep\n")
        self.assertEqual(self.registered_bytes(), expected)

    def test_recovery_journal_is_linked_worktree_specific(self) -> None:
        linked = self.root.parent / f"{self.root.name}-linked"
        self.git("worktree", "add", "-q", str(linked), "HEAD")
        try:
            target = linked / "transaction-target.txt"
            recovery = validator._begin_transaction(linked, "fixture", [target])
            self.assertTrue((linked / ".git").is_file())
            self.assertTrue((recovery / "journal.json").is_file())
            self.assertNotEqual(recovery, validator._recovery_root(self.root))
            target.write_text("partial\n", encoding="utf-8")
            self.assertTrue(validator.recover_incomplete_transaction(linked))
            self.assertFalse(target.exists())
        finally:
            self.git("worktree", "remove", "--force", str(linked))

    def test_promotion_collision_preserves_unowned_sentinel(self) -> None:
        manifest = self.make_draft("bundle-a")
        data = json.loads(manifest.read_text(encoding="utf-8"))
        target = self.root / data["artifacts"][0]["native_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("keep\n", encoding="utf-8")
        self.assertEqual(
            validator.promote(manifest, "explicit-user-acceptance", False, self.root), 1
        )
        self.assertEqual(target.read_text(encoding="utf-8"), "keep\n")

    def test_bundle_id_is_content_addressed_and_rejects_aliases(self) -> None:
        digest = "a" * 64
        expected = "task-name--aaaaaaaaaaaaaaaa"
        self.assertEqual(validator.canonical_bundle_id("task-name", digest), expected)
        for alias in (
            "Task-name--aaaaaaaaaaaaaaaa",
            "task/name--aaaaaaaaaaaaaaaa",
            "task-name--aaaa",
        ):
            self.assertIsNone(validator.BUNDLE_ID_RE.fullmatch(alias))

    def test_legacy_tombstones_are_append_only(self) -> None:
        prior = {
            "schema_version": validator.SCHEMA_VERSION,
            "bundles": [],
            "tombstones": [
                {
                    "original_path": ".omx/plans/legacy.md",
                    "source_commit": self.source_commit,
                    "blob_hash": "a" * 40,
                    "classification": "legacy-plan",
                    "reason": "retired",
                }
            ],
        }
        current = json.loads(json.dumps(prior))
        current["tombstones"] = []
        self.assertTrue(
            any(
                "tombstone" in error
                for error in validator.validate_history(current, prior, "base")
            )
        )


@unittest.skipUnless(
    os.environ.get("ARIA_OMX_NATIVE_ACCEPTANCE") == "1",
    "set ARIA_OMX_NATIVE_ACCEPTANCE=1 to run verified OMX 0.20.3 acceptance",
)
class OmxArtifactNativeAcceptanceTests(unittest.TestCase):
    APPROVED_SUCCESSOR_ID = "aria-nbv-agent-scaffold-refresh--b77c74dbe884e6f6"

    @staticmethod
    def registered_bytes(root: Path) -> dict[str, bytes]:
        registry = validator.load_registry(root / validator.REGISTRY_REL)
        paths = [validator.REGISTRY_REL.as_posix()]
        paths.extend(
            artifact["path"]
            for bundle in registry["bundles"]
            for artifact in bundle["artifacts"]
        )
        return {relative: (root / relative).read_bytes() for relative in paths}

    def test_exact_bundle_seed_purge_restore_and_real_native_lifecycle(self) -> None:
        host_before = self.registered_bytes(SOURCE_REPO)
        with tempfile.TemporaryDirectory(
            prefix="aria-omx-acceptance-", dir=SOURCE_REPO.parent
        ) as raw_outer:
            outer = Path(raw_outer)
            repository = outer / "repository"
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--quiet",
                    "--no-local",
                    str(SOURCE_REPO),
                    str(repository),
                ],
                check=True,
            )
            home = outer / "home"
            tmp = outer / "tmp"
            external = outer / "external"
            for path in (home, tmp, external):
                path.mkdir()
            sentinel = external / "outside-sentinel.txt"
            sentinel.write_text("outside evidence\n", encoding="utf-8")

            expected = self.registered_bytes(repository)
            self.assertEqual(expected, host_before)
            registry = validator.load_registry(repository / validator.REGISTRY_REL)
            by_id = {bundle["id"]: bundle for bundle in registry["bundles"]}
            self.assertEqual(
                by_id[validator.LEGACY_PREDECESSOR_ID]["status"], "superseded"
            )
            self.assertEqual(
                by_id[validator.LEGACY_PREDECESSOR_ID]["superseded_by"],
                self.APPROVED_SUCCESSOR_ID,
            )
            self.assertEqual(by_id[self.APPROVED_SUCCESSOR_ID]["status"], "current")

            isolated_environment = {
                "HOME": str(home),
                "CODEX_HOME": str(home / ".codex"),
                "XDG_CACHE_HOME": str(home / ".cache"),
                "XDG_CONFIG_HOME": str(home / ".config"),
                "XDG_DATA_HOME": str(home / ".local/share"),
                "XDG_STATE_HOME": str(home / ".local/state"),
                "TMPDIR": str(tmp),
            }
            commands = (
                ["omx", "cleanup", "--dry-run"],
                ["omx", "cleanup"],
                [
                    "omx",
                    "ultragoal",
                    "create-goals",
                    "--force",
                    "--brief",
                    "- Disposable lifecycle acceptance",
                    "--json",
                ],
                ["omx", "cancel"],
            )
            with (
                mock.patch.dict(os.environ, isolated_environment, clear=False),
                mock.patch.object(tempfile, "tempdir", None),
            ):
                self.assertTrue(validator._verified_omx_install("omx"))
                with mock.patch.object(
                    validator, "_verified_omx_install", return_value=True
                ):
                    for command in commands:
                        with self.subTest(command=command):
                            self.assertEqual(
                                validator.run_native_operation(command, repository),
                                0,
                            )
                            self.assertEqual(
                                self.registered_bytes(repository), expected
                            )

            seed = validator.export_seed(external, repository)
            self.assertEqual(set(validator.verify_seed(seed)), set(expected))
            for relative in expected:
                if relative.startswith(".omx/"):
                    (repository / relative).unlink()
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "outside evidence\n")
            self.assertEqual(validator.restore_seed(seed, repository), 0)
            self.assertEqual(self.registered_bytes(repository), expected)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "outside evidence\n")

        self.assertEqual(self.registered_bytes(SOURCE_REPO), host_before)


if __name__ == "__main__":
    unittest.main()
