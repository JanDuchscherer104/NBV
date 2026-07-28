from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from fnmatch import fnmatchcase
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

REPO_ROOT = Path(__file__).parents[2]
LOCAL_TRANSITION_ENV = {
    "GITHUB_ACTIONS": "",
    "GITHUB_BASE_REF": "",
    "OMX_ARTIFACT_PREVIOUS_REF": "",
}


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
                f".omx/plans/{prefix}review.json",
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
                        text=json.dumps(
                            {
                                "schema_version": 1,
                                "bundle_id": bundle_id,
                                "task": "task",
                                "status": "approved",
                                "architect": "APPROVED",
                                "critic": "APPROVED",
                            }
                        )
                        + "\n",
                        review_kinds=["architect", "critic"],
                    )
                )
            else:
                text = None
                if role == "acceptance-record":
                    text = (
                        json.dumps(
                            {
                                "schema_version": 1,
                                "bundle_id": bundle_id,
                                "task": "task",
                                "status": "accepted",
                                "accepted_scope": "fixture contract",
                                "excluded_scope": [],
                                "actor_class": "repository-owner",
                                "instruction_channel": "direct-user-instruction",
                                "date": "2026-07-27",
                                "request_digest": "0" * 64,
                                "request_digest_normalization": "fixture",
                            }
                        )
                        + "\n"
                    )
                elif role == "handoff":
                    text = (
                        json.dumps(
                            {
                                "schema_version": 1,
                                "bundle_id": bundle_id,
                                "task": "task",
                                "status": "accepted",
                                "predecessor_bundle_id": None,
                                "predecessor_bundle_sha256": None,
                                "predecessor_chain_sha256": None,
                                "roles": sorted(MODULE.REQUIRED_FAMILIES),
                                "review": {
                                    "architect": "APPROVED",
                                    "critic": "APPROVED",
                                },
                                "execution": {
                                    "mode": "sequential",
                                    "next_package": "fixture",
                                    "write_scope": "fixture",
                                },
                                "constraints": [],
                            }
                        )
                        + "\n"
                    )
                artifacts.append(self.artifact(path, family, role, text=text))
        handoff = next(item for item in artifacts if item["family"] == "handoff")
        acceptance = next(
            item for item in artifacts if item["role"] == "acceptance-record"
        )
        return {
            "id": bundle_id,
            "task": "task",
            "status": "current",
            "contract_version": 2,
            "classification": "accepted-decision-evidence",
            "baseline_commit": self.baseline,
            "handoff_sha256": handoff["sha256"],
            "acceptance_sha256": acceptance["sha256"],
            "artifact": artifacts,
        }

    def write_registry(
        self,
        bundles: list[dict[str, Any]],
        relative: str = "registry.toml",
        schema_version: int = 2,
    ) -> Path:
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"schema_version = {schema_version}"]
        for bundle in bundles:
            lines.extend(["", "[[bundle]]"])
            for key in (
                "id",
                "task",
                "status",
                "contract_version",
                "classification",
                "baseline_commit",
                "handoff_sha256",
                "acceptance_sha256",
                "predecessor_bundle_id",
                "predecessor_bundle_sha256",
                "predecessor_chain_sha256",
                "predecessor_registry_commit",
                "superseded_by",
            ):
                if key in bundle and (
                    key == "contract_version" or isinstance(bundle[key], bool)
                ):
                    value = bundle[key]
                    rendered = str(value).lower() if isinstance(value, bool) else value
                    lines.append(f"{key} = {rendered}")
                elif key in bundle:
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

    def commit_registry(
        self, bundle: dict[str, Any], message: str, schema_version: int = 2
    ) -> None:
        self.write_registry(
            [bundle], ".agents/omx_artifacts.toml", schema_version=schema_version
        )
        self.git("add", "-f", ".agents/omx_artifacts.toml", ".omx")
        self.git("commit", "-qm", message)

    def run_validator(self, previous_ref: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repo",
                str(self.repo),
                "--registry",
                str(self.repo / ".agents/omx_artifacts.toml"),
                "--previous-ref",
                previous_ref,
                "--check-tracked",
            ],
            cwd=self.repo,
            check=False,
            capture_output=True,
            text=True,
        )

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

    def bind_predecessor(
        self,
        successor: dict[str, Any],
        predecessor: dict[str, Any],
        bundles: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        chain_bundles = {predecessor["id"]: predecessor} if bundles is None else bundles
        successor["predecessor_bundle_id"] = predecessor["id"]
        successor["predecessor_bundle_sha256"] = MODULE.bundle_content_sha256(
            predecessor
        )
        successor["predecessor_chain_sha256"] = MODULE.bundle_chain_sha256(
            predecessor["id"], chain_bundles
        )
        handoff = next(
            item for item in successor["artifact"] if item["family"] == "handoff"
        )
        path = self.repo / handoff["path"]
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["predecessor_bundle_id"] = predecessor["id"]
        payload["predecessor_bundle_sha256"] = successor["predecessor_bundle_sha256"]
        payload["predecessor_chain_sha256"] = successor["predecessor_chain_sha256"]
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        content = path.read_bytes()
        handoff["sha256"] = hashlib.sha256(content).hexdigest()
        handoff["bytes"] = len(content)
        successor["handoff_sha256"] = handoff["sha256"]

    def commit_supersession(
        self,
        original: dict[str, Any],
        successor: dict[str, Any],
        mutation: str | None = None,
    ) -> None:
        archived = self.archived(original, successor["id"])
        self.bind_predecessor(successor, original)
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

    def commit_second_supersession(self, successor: dict[str, Any]) -> None:
        registry = MODULE.load_registry(self.repo / ".agents/omx_artifacts.toml")
        current = next(
            item for item in registry["bundle"] if item["status"] == "current"
        )
        archived = self.archived(current, successor["id"])
        self.bind_predecessor(
            successor,
            current,
            {item["id"]: item for item in registry["bundle"]},
        )
        for artifact in archived["artifact"]:
            source = self.repo / artifact["native_path"]
            destination = self.repo / artifact["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
            source.unlink()
        previous = [item for item in registry["bundle"] if item["id"] != current["id"]]
        self.write_registry(
            [*previous, archived, successor], ".agents/omx_artifacts.toml"
        )
        self.git("add", "-f", ".agents/omx_artifacts.toml", ".omx")
        self.git("commit", "-qm", "second supersession")

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

    def test_contract_v2_artifact_families_are_bound_to_native_roots(self) -> None:
        wrong_roots = {
            "context": ".omx/plans/context.md",
            "specification": ".omx/context/report.md",
            "test_specification": ".omx/plans/test.md",
            "plan": ".omx/specs/plan.md",
            "review": ".omx/specs/review.json",
            "handoff": ".omx/specs/handoff.json",
        }
        for family, wrong_path in wrong_roots.items():
            with self.subTest(family=family):
                bundle = self.bundle()
                artifact = next(
                    item for item in bundle["artifact"] if item["family"] == family
                )
                source = self.repo / artifact["path"]
                destination = self.repo / wrong_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                source.replace(destination)
                artifact["path"] = wrong_path
                artifact["native_path"] = wrong_path

                self.assert_invalid(bundle, "invalid native role path")

    def test_contract_v2_native_root_check_is_independent_of_bundle_order(self) -> None:
        current = self.bundle()
        context = next(
            item for item in current["artifact"] if item["family"] == "context"
        )
        wrong_path = ".omx/plans/context.md"
        (self.repo / context["path"]).replace(self.repo / wrong_path)
        context["path"] = wrong_path
        context["native_path"] = wrong_path

        legacy = self.bundle("task-legacy", "legacy")
        legacy["contract_version"] = 1
        legacy["status"] = "superseded"
        legacy["superseded_by"] = current["id"]
        for artifact in legacy["artifact"]:
            source = self.repo / artifact["path"]
            artifact["path"] = (
                f".omx/archive/accepted-bundles/{legacy['id']}/"
                + artifact["native_path"].removeprefix(".omx/")
            )
            destination = self.repo / artifact["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.replace(destination)

        for bundles in ([current, legacy], [legacy, current]):
            with self.subTest(order=[bundle["id"] for bundle in bundles]):
                with self.assertRaisesRegex(
                    MODULE.ValidationError, "invalid native role path"
                ):
                    MODULE.validate_registry(self.repo, self.write_registry(bundles))

    def test_archived_contract_v2_family_keeps_native_root(self) -> None:
        original = self.bundle()
        successor = self.bundle("task-next", "next")
        self.commit_supersession(original, successor)
        registry = MODULE.load_registry(self.repo / ".agents/omx_artifacts.toml")
        archived = next(
            item for item in registry["bundle"] if item["status"] == "superseded"
        )
        context = next(
            item for item in archived["artifact"] if item["family"] == "context"
        )
        source = self.repo / context["path"]
        context["native_path"] = ".omx/plans/context.md"
        context["path"] = (
            f".omx/archive/accepted-bundles/{archived['id']}/plans/context.md"
        )
        destination = self.repo / context["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.replace(destination)
        current = next(
            item for item in registry["bundle"] if item["status"] == "current"
        )
        self.bind_predecessor(current, archived)

        with self.assertRaisesRegex(MODULE.ValidationError, "invalid native role path"):
            MODULE.validate_registry(self.repo, self.write_registry(registry["bundle"]))

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

    def test_acceptance_handoff_and_review_semantics_are_required(self) -> None:
        for role, text, message in (
            (
                "acceptance-record",
                json.dumps(
                    {
                        "schema_version": 1,
                        "bundle_id": "task-current",
                        "task": "task",
                        "accepted_scope": "fixture contract",
                        "actor_class": "unknown",
                        "instruction_channel": "direct-user-instruction",
                    }
                )
                + "\n",
                "acceptance record semantics mismatch",
            ),
            (
                "handoff",
                json.dumps(
                    {
                        "schema_version": 1,
                        "bundle_id": "task-current",
                        "task": "task",
                        "status": "draft",
                        "review": {
                            "architect": "APPROVED",
                            "critic": "APPROVED",
                        },
                    }
                )
                + "\n",
                "handoff acceptance mismatch",
            ),
            (
                "independent-review",
                json.dumps(
                    {
                        "schema_version": 1,
                        "bundle_id": "task-current",
                        "task": "task",
                        "status": "approved",
                        "architect": "APPROVED",
                        "critic": "BLOCK",
                    }
                )
                + "\n",
                "review contract mismatch",
            ),
        ):
            with self.subTest(role=role):
                bundle = self.bundle()
                artifact = next(
                    item for item in bundle["artifact"] if item["role"] == role
                )
                path = self.repo / artifact["path"]
                path.write_text(text, encoding="utf-8")
                payload = path.read_bytes()
                artifact["sha256"] = hashlib.sha256(payload).hexdigest()
                artifact["bytes"] = len(payload)
                if role == "acceptance-record":
                    bundle["acceptance_sha256"] = artifact["sha256"]
                elif role == "handoff":
                    bundle["handoff_sha256"] = artifact["sha256"]
                self.assert_invalid(bundle, message)

        bundle = self.bundle()
        acceptance = next(
            item for item in bundle["artifact"] if item["role"] == "acceptance-record"
        )
        acceptance_path = self.repo / acceptance["path"]
        duplicate = acceptance_path.read_text(encoding="utf-8").replace(
            '"status": "accepted"',
            '"status": "rejected", "status": "accepted"',
            1,
        )
        acceptance_path.write_text(duplicate, encoding="utf-8")
        content = acceptance_path.read_bytes()
        acceptance["sha256"] = hashlib.sha256(content).hexdigest()
        acceptance["bytes"] = len(content)
        bundle["acceptance_sha256"] = acceptance["sha256"]
        self.assert_invalid(bundle, "duplicate JSON key")

        bundle = self.bundle()
        review = next(item for item in bundle["artifact"] if item["family"] == "review")
        review_path = self.repo / review["path"]
        duplicate = review_path.read_text(encoding="utf-8").replace(
            '"critic": "APPROVED"',
            '"critic": "BLOCK", "critic": "APPROVED"',
            1,
        )
        review_path.write_text(duplicate, encoding="utf-8")
        content = review_path.read_bytes()
        review["sha256"] = hashlib.sha256(content).hexdigest()
        review["bytes"] = len(content)
        self.assert_invalid(bundle, "duplicate JSON key")

        bundle = self.bundle()
        bundle["contract_version"] = True
        self.assert_invalid(bundle, "invalid contract version")

        bundle = self.bundle()
        bundle["predecessor_bundle_id"] = False
        bundle["predecessor_bundle_sha256"] = False
        bundle["predecessor_chain_sha256"] = False
        handoff = next(
            item for item in bundle["artifact"] if item["family"] == "handoff"
        )
        handoff_path = self.repo / handoff["path"]
        payload = json.loads(handoff_path.read_text(encoding="utf-8"))
        payload["predecessor_bundle_id"] = False
        payload["predecessor_bundle_sha256"] = False
        payload["predecessor_chain_sha256"] = False
        handoff_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        content = handoff_path.read_bytes()
        handoff["sha256"] = hashlib.sha256(content).hexdigest()
        handoff["bytes"] = len(content)
        bundle["handoff_sha256"] = handoff["sha256"]
        self.assert_invalid(bundle, "lacks predecessor receipts")

        registry = self.write_registry([self.bundle()])
        registry.write_text(
            registry.read_text(encoding="utf-8").replace(
                "schema_version = 2", "schema_version = true", 1
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            MODULE.ValidationError, "registry schema_version must be 1 or 2"
        ):
            MODULE._parse_registry(registry.read_bytes())

        for predecessor_id in ("ghost-bundle", "task-current"):
            with self.subTest(predecessor_id=predecessor_id):
                bundle = self.bundle()
                bundle["predecessor_bundle_id"] = predecessor_id
                bundle["predecessor_bundle_sha256"] = "0" * 64
                bundle["predecessor_chain_sha256"] = "1" * 64
                handoff = next(
                    item for item in bundle["artifact"] if item["family"] == "handoff"
                )
                handoff_path = self.repo / handoff["path"]
                payload = json.loads(handoff_path.read_text(encoding="utf-8"))
                payload["predecessor_bundle_id"] = predecessor_id
                payload["predecessor_bundle_sha256"] = "0" * 64
                payload["predecessor_chain_sha256"] = "1" * 64
                handoff_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
                content = handoff_path.read_bytes()
                handoff["sha256"] = hashlib.sha256(content).hexdigest()
                handoff["bytes"] = len(content)
                bundle["handoff_sha256"] = handoff["sha256"]
                self.assert_invalid(bundle, "invalid predecessor link")

        for role, key, value, message in (
            ("acceptance-record", "status", "rejected", "acceptance record contract"),
            (
                "acceptance-record",
                "excluded_scope",
                "not-a-list",
                "acceptance record contract",
            ),
            ("acceptance-record", "date", 20260727, "acceptance record contract"),
            (
                "acceptance-record",
                "request_digest",
                0,
                "acceptance record contract",
            ),
            ("handoff", "schema_version", 999, "handoff acceptance mismatch"),
            ("handoff", "execution", None, "handoff contract mismatch"),
            ("handoff", "constraints", "not-a-list", "handoff contract mismatch"),
        ):
            with self.subTest(role=role, key=key):
                bundle = self.bundle()
                artifact = next(
                    item for item in bundle["artifact"] if item["role"] == role
                )
                path = self.repo / artifact["path"]
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload[key] = value
                path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
                content = path.read_bytes()
                artifact["sha256"] = hashlib.sha256(content).hexdigest()
                artifact["bytes"] = len(content)
                bundle[
                    "acceptance_sha256"
                    if role == "acceptance-record"
                    else "handoff_sha256"
                ] = artifact["sha256"]
                self.assert_invalid(bundle, message)

    def test_privacy_scan_covers_current_and_superseded_artifacts(self) -> None:
        samples = (
            ("machine /home/example/repo/file\n", "absolute path"),
            ("machine /tmp\n", "absolute path"),
            ("machine /root\n", "absolute path"),
            ("machine /etc\n", "absolute path"),
            ("machine /home/user/@private/file.txt\n", "privacy threat"),
            ("machine file:///home/user/@private/file.txt\n", "privacy threat"),
            ("machine file:///home/user/%40private/file.txt\n", "privacy threat"),
            (
                "machine file:%2F%2F%2Fhome%2Fuser%2Fprivate%2Fsecret.txt\n",
                "privacy threat",
            ),
            ("machine %252Fhome%252Fuser%252Fsecret.txt\n", "absolute path"),
            ("machine -/home/alice/secret.txt\n", "absolute path"),
            ("machine :/home/alice/secret.txt\n", "absolute path"),
            ("machine */home/alice/secret.txt\n", "absolute path"),
            ("machine !/home/alice/secret.txt\n", "absolute path"),
            ("machine x-/home/alice/secret.txt\n", "absolute path"),
            ("machine x!/home/alice/secret.txt\n", "absolute path"),
            ("machine x*/home/alice/secret.txt\n", "absolute path"),
            ("machine x(/home/alice/secret.txt\n", "absolute path"),
            ("machine x./home/alice/secret.txt\n", "absolute path"),
            ("machine x%252D%252Fhome%252Falice%252Fsecret.txt\n", "absolute path"),
            ("machine path=/tmp/secret.txt\n", "absolute path"),
            ("machine %2570ath%253D%252Ftmp%252Fsecret.txt\n", "absolute path"),
            ("machine %252D%252Fhome%252Falice%252Fsecret.txt\n", "absolute path"),
            ("machine </home/alice/secret.txt\n", "absolute path"),
            ("machine x</home/alice/secret.txt\n", "absolute path"),
            ("see docs/%70rivate/secret.txt\n", "private or raw path part"),
            ("see docs/%72aw/messages.jsonl\n", "private or raw path part"),
            ("machine C:/Users/alice/project/file.txt\n", "absolute path"),
            ("machine C:\\Users\\alice\\project\\file.txt\n", "absolute path"),
            ("machine \\\\server\\share\\project\\file.txt\n", "absolute path"),
            ("machine //server/share/project/file.txt\n", "absolute path"),
            (
                "machine C:%2FUsers%2Falice%2Fsecret.txt\n",
                "unsupported URI scheme",
            ),
            (
                "machine %255C%255Cserver%255Cshare%255Csecret.txt\n",
                "absolute path",
            ),
            (
                "machine %252F%252Fserver%252Fshare%252Fsecret.txt\n",
                "absolute path",
            ),
            ("machine path:/home/alice/project/file.txt\n", "absolute path"),
            ("machine workspace:/home/alice/project/file.txt\n", "absolute path"),
            ("machine javascript:alert(1)\n", "unsupported URI scheme"),
            ("machine javascript:*\n", "unsupported URI scheme"),
            ("machine javascript:**\n", "unsupported URI scheme"),
            ("machine file:**\n", "unsupported URI scheme"),
            ("machine 123:**\n", "unsupported URI scheme"),
            ("machine custom:__\n", "unsupported URI scheme"),
            ("custom**:**opaque\n", "unsupported URI scheme"),
            ("123**:**opaque\n", "unsupported URI scheme"),
            ("**safe ** javascript:**\n", "unsupported URI scheme"),
            ("**Owner:** javascript:**\n", "unsupported URI scheme"),
            ("__Owner:__ file:__\n", "unsupported URI scheme"),
            ("**Owner:**=javascript:opaque\n", "unsupported URI scheme"),
            ("**Owner:**=123:opaque\n", "unsupported URI scheme"),
            ("**Owner:**=https://\n", "malformed HTTP URI"),
            ("**Owner:** java**script:**alert(1)\n", "unsupported URI scheme"),
            ("[x](java**script:**alert(1))\n", "unsupported URI scheme"),
            ("**Owner:** javascript\\:alert(1)\n", "unsupported URI scheme"),
            ("**Owner:** \\/home/alice/secret\n", "absolute path"),
            ("**Owner:**/home/alice/secret\n", "absolute path"),
            ("__Owner:__/home/alice/secret\n", "absolute path"),
            ("**safe**/home/alice/secret\n", "absolute path"),
            ("**sa*fe**/home/alice/secret\n", "absolute path"),
            ("**sa\nfe**/home/alice/secret\n", "absolute path"),
            ("**Owner:\ncontinued**/home/alice/secret\n", "absolute path"),
            ("**safe /home/alice/secret**\n", "absolute path"),
            (
                "%252A%252AOwner%253A%252A%252A%252Fhome%252Falice%252Fsecret\n",
                "absolute path",
            ),
            (
                "%252A%252Asa%252Afe%252A%252A%252Fhome%252Falice%252Fsecret\n",
                "absolute path",
            ),
            (
                "&#42;&#42;Owner:&#42;&#42;/home/alice/secret\n",
                "absolute path",
            ),
            ("\\*\\*Owner:\\*\\*\\/home/alice/secret\n", "privacy threat"),
            (
                "%252A%252Asafe%2520%252A%252A%2520javascript%253A%252A%252A\n",
                "unsupported URI scheme",
            ),
            ("machine urn:isbn:9780000000000\n", "unsupported URI scheme"),
            ("machine urn:1234\n", "unsupported URI scheme"),
            ("machine tel:+49123\n", "unsupported URI scheme"),
            ("machine geo:48,11\n", "unsupported URI scheme"),
            ("machine data:,hello\n", "unsupported URI scheme"),
            ("machine custom:%31\n", "unsupported URI scheme"),
            ("machine 123:opaque\n", "unsupported URI scheme"),
            ("machine %2531%2532%2533%253Aopaque\n", "unsupported URI scheme"),
            ("machine custom:?query\n", "unsupported URI scheme"),
            ("machine javascript:AGENTS.md:1\n", "unsupported URI scheme"),
            ("machine file:AGENTS.md:1\n", "unsupported URI scheme"),
            (
                "machine %256aavascript%253Aalert%25281%2529\n",
                "unsupported URI scheme",
            ),
            ("machine https://\n", "malformed HTTP URI"),
            ("machine http:\n", "unsupported or malformed URI"),
            ("machine http%253A\n", "unsupported or malformed URI"),
            ("machine https://?q=value\n", "malformed HTTP URI"),
            ("machine https:443\n", "malformed HTTP URI"),
            ("machine https://example.invalid:abc/path\n", "malformed HTTP URI"),
            ("machine https://example.invalid:0\n", "malformed HTTP URI"),
            ("machine https://example.invalid:65536\n", "malformed HTTP URI"),
            ("machine https://example.invalid:65536/path\n", "malformed HTTP URI"),
            ("machine https://example.invalid:\n", "malformed HTTP URI"),
            (
                "machine https%253A%252F%252Fexample.invalid%253A\n",
                "malformed HTTP URI",
            ),
            ("machine https://example.invalid/%ZZ\n", "malformed HTTP URI"),
            (
                "machine https://example.invalid%253A\n",
                "malformed HTTP URI",
            ),
            (
                "machine %2568ttps%253A%252F%252Fexample.invalid%252F%2525ZZ\n",
                "malformed HTTP URI",
            ),
            ("machine </home/alice/project/file.txt>\n", "privacy threat"),
            (
                "machine https://example.invalid/docs,/home/alice/secret\n",
                "absolute path",
            ),
            (
                "machine https://example.invalid/docs)/home/alice/secret\n",
                "absolute path",
            ),
            (
                "machine [x](https://example.invalid/docs)/home/alice/secret\n",
                "absolute path",
            ),
            ("machine https://)/home/alice/secret\n", "absolute path"),
            ("machine https://[bad]/home/alice/secret\n", "absolute path"),
            ("runtime 019f9e3a-169a-7673-9df2-c4bd0277bd35\n", "runtime UUID"),
            (
                "runtime session_019f9e3a-169a-7673-9df2-c4bd0277bd35\n",
                "runtime UUID",
            ),
            ("see private/file.txt\n", "private or raw path part"),
            ("see raw/file.txt\n", "private or raw path part"),
            ("see private/project/notes.md\n", "private or raw path part"),
            ("see local/raw/messages.jsonl\n", "private or raw path part"),
            ("see local\\raw\\messages.jsonl\n", "private or raw path part"),
            ("private**/**file\n", "private or raw path part"),
            ("raw**/**file\n", "private or raw path part"),
            ("**/**home/alice\n", "absolute path"),
            (
                "https://example.invalid/private?download=1\n",
                "private or raw path part",
            ),
            ("https://example.invalid/raw#part\n", "private or raw path part"),
            ("https://example.invalid/?private=value\n", "private or raw path part"),
            ("https://example.invalid/?raw=value\n", "private or raw path part"),
            ("HEAD:path/private:1\n", "private or raw path part"),
            ("main:raw:2\n", "private or raw path part"),
            ("deadbeef:folder/raw:3\n", "private or raw path part"),
            (
                "https://example.invalid/%2570rivate%253Fdownload=1\n",
                "private or raw path part",
            ),
            ("<!doctype html><html>bad</html>\n", "HTML content"),
            ("<script src=x>bad</script>\n", "HTML content"),
            ("<meta charset=utf-8>\n", "HTML content"),
            ("<meta\ncharset=x\ncontent=y>\n", "HTML content"),
            ("<svg/onload=alert(1)>\n", "HTML content"),
            ("<img/src=x>\n", "HTML content"),
            ("%253Csvg%252Fonload%253Dalert%25281%2529%253E\n", "HTML content"),
            ("&lt;script src=x&gt;\n", "HTML content"),
            ("%253Cmeta%250Acharset=x%250Acontent=y%253E\n", "HTML content"),
            (
                r'note: {"path":"\u002fhome\u002falice\u002fsecret"}' + "\n",
                "absolute path",
            ),
            (
                "note%253A%2520%257B%2522path%2522%253A%2522%255Cu002fhome"
                "%255Cu002falice%255Cu002fsecret%2522%257D\n",
                "absolute path",
            ),
            (_fixture("-----BEGIN OPENSSH ", "PRIVATE KEY-----\n"), "private key"),
            (_fixture("token ghp_", "abcdefghijklmnopqrstuvwxyz\n"), "GitHub token"),
            (
                _fixture("token_ghp_", "abcdefghijklmnopqrstuvwxyz\n"),
                "GitHub token",
            ),
            (
                _fixture(
                    "https://example.invalid/ghp_", "abcdefghijklmnopqrstuvwxyz\n"
                ),
                "GitHub token",
            ),
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
            ("https://owner@example.com/path\n", "email address"),
        )
        for text, message in samples:
            with self.subTest(message=message, text=text):
                bundle = self.bundle()
                target = self.repo / bundle["artifact"][0]["path"]
                target.write_text(text, encoding="utf-8")
                payload = target.read_bytes()
                bundle["artifact"][0]["sha256"] = hashlib.sha256(payload).hexdigest()
                bundle["artifact"][0]["bytes"] = len(payload)
                self.assert_invalid(bundle, message)

        extension_payloads = (
            (r"\\server\share\secret.txt", "absolute path"),
            (r"\\\\server\\share\\secret.txt", "absolute path"),
            (r"//server\share\secret.txt", "absolute path"),
            ("%252F%252Fserver%255Cshare%255Csecret.txt", "absolute path"),
            (r"\/\/server\\share\\secret.txt", "absolute path"),
            (r"Bearer\%20abcdefghijklmnopqrstuvwx", "bearer token"),
            (r"ghp_\%61bcdefghijklmnopqrstuvwxyz", "GitHub token"),
            (r"r**a**w/file.txt", "private or raw path part"),
            (r"pr**iv**ate/file.txt", "private or raw path part"),
            (r"java**script**:alert(1)", "unsupported URI scheme"),
            (r"cust**om**:opaque", "unsupported URI scheme"),
            (r"cust**om**:", "unsupported URI scheme"),
            (r"cust*om*:", "unsupported URI scheme"),
            (r"c*u*s*t*o*m*:", "unsupported URI scheme"),
            (r"java*script*:alert(1)", "unsupported URI scheme"),
            (r"**/home/alice/secret**", "absolute path"),
            (r"__/home/alice/secret__", "absolute path"),
            (r"x**/home/alice/secret", "absolute path"),
            (r"**src/file**/home/alice/secret", "absolute path"),
            (r"**src/*/module.py**/home/alice/secret", "absolute path"),
            (r"src/**module.py**/home/alice/secret", "absolute path"),
            (r"**https://example.invalid/docs**/home/alice/secret", "absolute path"),
            (
                r"src/%252A%252Amodule.py%252A%252A%252Fhome%252Falice%252Fsecret",
                "absolute path",
            ),
            (r"**custom:**?opaque", "unsupported URI scheme"),
            (
                r"%252A%252Acustom%253A%252A%252A%253Fopaque",
                "unsupported URI scheme",
            ),
            (r"*https://example.invalid/docs*/home/alice/secret", "absolute path"),
            (r"_https://example.invalid/docs_/home/alice/secret", "absolute path"),
            (r"src/*module.py*/home/alice/secret", "absolute path"),
            (r"src/_module.py_/home/alice/secret", "absolute path"),
            (r"**custom:**,opaque", "unsupported URI scheme"),
            (r"src/*/module.py**/home/alice/secret", "absolute path"),
            (
                r"https://example.invalid/src/*/module.py**/home/alice/secret",
                "absolute path",
            ),
            (r"**custom:**//opaque", "unsupported URI scheme"),
            (r"__123:__//opaque", "unsupported URI scheme"),
            (
                r"[x](https://example.invalid/src/*/module.py)-/home/alice/secret",
                "absolute path",
            ),
            (
                r"[x](https://example.invalid/src/*/module.py)-custom://opaque",
                "unsupported URI scheme",
            ),
            (
                r"[x](https://example.invalid/src/*/module.py)-123://opaque",
                "unsupported URI scheme",
            ),
            (
                r"[x](https://example.invalid/src/*/module.py)-**custom:**//opaque",
                "unsupported URI scheme",
            ),
            (
                r"[x](https://example.invalid/?next=custom://opaque)",
                "unsupported URI scheme",
            ),
            (
                r"field,https://example.invalid/?next=123://opaque",
                "unsupported URI scheme",
            ),
            (
                r"https://example.invalid/path/custom://opaque",
                "unsupported URI scheme",
            ),
            (
                r"[x](https://example.invalid/docs)_/home/alice/secret",
                "absolute path",
            ),
            (r"custom.scheme:123", "unsupported URI scheme"),
            (r"123.456:789", "unsupported URI scheme"),
            (r"https://example.invalid/?next=/home/alice/secret", "absolute path"),
            (r"https://example.invalid/#/home/alice/secret", "absolute path"),
            (r"https://example.invalid/docs//home/alice/secret", "absolute path"),
            (
                r"https://example.invalid/?next=%252Fhome%252Falice%252Fsecret",
                "absolute path",
            ),
            (r"https://example.invalid//home/alice", "absolute path"),
            (r"https://example.invalid//server/share", "absolute path"),
            (r"https://example.invalid/a//b", "absolute path"),
            (r"https://example.invalid/a/%2Fb", "absolute path"),
            (r"https://example.invalid/a/%252Fb", "absolute path"),
            (r"https://example.invalid/?next=//machine", "absolute path"),
            (r"https://example.invalid/#//machine", "absolute path"),
            (
                r"https://example.invalid/?next=%252F%252Fmachine",
                "absolute path",
            ),
            (
                r"https://outer.invalid/?next=https://:443/x",
                "malformed HTTP URI",
            ),
            (
                r"https://outer.invalid/?next=https%253A%252F%252F%253A443%252Fx",
                "malformed HTTP URI",
            ),
        )
        for extension in (".md", ".csv", ".json"):
            for index, (unsafe_text, message) in enumerate(extension_payloads):
                bundle = self.bundle(f"layered-{extension[1:]}-{index}")
                content = f"header\n{unsafe_text}\ntrailer\n"
                if extension == ".json":
                    content = json.dumps({"note": content}) + "\n"
                bundle["artifact"].append(
                    self.artifact(
                        f".omx/specs/layered-{index}{extension}",
                        "specification",
                        f"layered-{extension[1:]}-{index}",
                        text=content,
                    )
                )
                self.assert_invalid(bundle, message)

        safe_texts = (
            "https://example.invalid/a_(b)/index",
            "https://example.invalid/a_(b_(c))/index",
            "[spec](https://example.invalid/a_(b)/index)",
            "<https://example.invalid/a_(b)/index>",
            "src/*/module.py",
            "src/a*/module.py",
            "src/?/module.py",
            "**/*.pdf",
            "**/__pycache__/**",
            "*note*:",
            "_note_:",
            "AGENTS.md:6-12",
        )
        for extension in (".md", ".csv", ".json"):
            bundle = self.bundle(f"safe-http-{extension[1:]}")
            content = "\n".join(safe_texts) + "\n"
            if extension == ".json":
                content = json.dumps({"text": safe_texts}) + "\n"
            bundle["artifact"].append(
                self.artifact(
                    f".omx/specs/safe-http{extension}",
                    "specification",
                    f"safe-http-{extension[1:]}",
                    text=content,
                )
            )
            MODULE.validate_registry(self.repo, self.write_registry([bundle]))

        deep_payloads = (
            "[" * 80 + '"safe"' + "]" * 80,
            "[" * 80 + r'"\u002fhome\u002falice\u002fsecret"' + "]" * 80,
            "[" * 1_100 + '"safe"' + "]" * 1_100,
        )
        for extension in (".md", ".csv", ".json"):
            for index, deep_json in enumerate(deep_payloads):
                bundle = self.bundle(f"deep-json-{extension[1:]}-{index}")
                content = deep_json if extension == ".json" else f"note: {deep_json}\n"
                bundle["artifact"].append(
                    self.artifact(
                        f".omx/specs/deep-json-{index}{extension}",
                        "specification",
                        f"deep-json-{extension[1:]}-{index}",
                        text=content,
                    )
                )
                expected = "nested JSON|invalid registered JSON evidence"
                if index == 1:
                    expected = f"privacy threat|{expected}"
                self.assert_invalid(
                    bundle,
                    expected,
                )

        large_integer_json = '{"value":' + "9" * 5_000 + "}"
        for extension in (".md", ".csv", ".json"):
            bundle = self.bundle(f"large-integer-{extension[1:]}")
            content = (
                large_integer_json
                if extension == ".json"
                else f"note: {large_integer_json}\n"
            )
            bundle["artifact"].append(
                self.artifact(
                    f".omx/specs/large-integer{extension}",
                    "specification",
                    f"large-integer-{extension[1:]}",
                    text=content,
                )
            )
            self.assert_invalid(
                bundle, "invalid registered JSON evidence|invalid nested JSON value"
            )

        bundle = self.bundle("embedded-json-attempts")
        bundle["artifact"].append(
            self.artifact(
                ".omx/specs/malformed-embedded.md",
                "specification",
                "malformed-embedded",
                text='\\"' * (MODULE.MAX_EMBEDDED_JSON_ATTEMPTS + 1),
            )
        )
        self.assert_invalid(bundle, "nested JSON exceeds attempt limit")

        bundle = self.bundle("unicode-json")
        acceptance = next(
            item for item in bundle["artifact"] if item["role"] == "acceptance-record"
        )
        acceptance_path = self.repo / acceptance["path"]
        acceptance_payload = json.loads(acceptance_path.read_text(encoding="utf-8"))
        acceptance_payload["accepted_scope"] = "UNICODE_PATH"
        encoded = json.dumps(acceptance_payload).replace(
            "UNICODE_PATH", r"\u002fhome\u002falice\u002fsecret"
        )
        acceptance_path.write_text(encoded + "\n", encoding="utf-8")
        payload = acceptance_path.read_bytes()
        acceptance["sha256"] = hashlib.sha256(payload).hexdigest()
        acceptance["bytes"] = len(payload)
        bundle["acceptance_sha256"] = acceptance["sha256"]
        self.assert_invalid(bundle, "absolute path")

        for index, nested_json in enumerate(
            (
                r'{"path":"\u002fhome\u002falice\u002fsecret"}',
                r'{"path":"\/home\/alice\/secret"}',
                r'{"note":"**sa*fe**\/home\/alice\/secret"}',
                r'{"note":"\\u002fhome\\u002falice\\u002fsecret"}',
                r'note: {"path":"\u002fhome\u002falice\u002fsecret"}',
                r'note: {"path":"**sa*fe**\u002fhome\u002falice\u002fsecret"}',
                "%7B%22path%22%3A%22%5Cu002fhome%5Cu002falice%5Cu002fsecret%22%7D",
            )
        ):
            bundle = self.bundle(f"nested-json-{index}")
            acceptance = next(
                item
                for item in bundle["artifact"]
                if item["role"] == "acceptance-record"
            )
            acceptance_path = self.repo / acceptance["path"]
            acceptance_payload = json.loads(acceptance_path.read_text(encoding="utf-8"))
            acceptance_payload["accepted_scope"] = nested_json
            acceptance_path.write_text(
                json.dumps(acceptance_payload) + "\n", encoding="utf-8"
            )
            payload = acceptance_path.read_bytes()
            acceptance["sha256"] = hashlib.sha256(payload).hexdigest()
            acceptance["bytes"] = len(payload)
            bundle["acceptance_sha256"] = acceptance["sha256"]
            self.assert_invalid(bundle, "absolute path")

        bundle = self.bundle("generic-json")
        bundle["artifact"].append(
            self.artifact(
                ".omx/specs/generic.json",
                "specification",
                "generic-json",
                text=r'{"note":"\u002fhome\u002falice\u002fsecret"}' + "\n",
            )
        )
        self.assert_invalid(bundle, "absolute path")

        bundle = self.bundle("duplicate-json")
        bundle["artifact"].append(
            self.artifact(
                ".omx/specs/duplicate.json",
                "specification",
                "duplicate-json",
                text='{"note":"first","note":"second"}\n',
            )
        )
        self.assert_invalid(bundle, "duplicate JSON key")

        safe_glob_values = (
            "src/*/module.py",
            "src/a*/module.py",
            "src/?/module.py",
            "**/*.pdf",
            "**/__pycache__/**",
        )
        safe_globs = "\n".join(safe_glob_values) + "\n"
        safe_globs_json = json.dumps({"text": safe_glob_values}) + "\n"
        old = self.bundle("task-old")
        old_path = self.repo / old["artifact"][0]["path"]
        old_path.write_text(safe_globs, encoding="utf-8")
        payload = old_path.read_bytes()
        old["artifact"][0]["sha256"] = hashlib.sha256(payload).hexdigest()
        old["artifact"][0]["bytes"] = len(payload)
        old["artifact"].extend(
            (
                self.artifact(
                    ".omx/specs/globs.csv",
                    "specification",
                    "glob-csv",
                    text=safe_globs,
                ),
                self.artifact(
                    ".omx/specs/globs.json",
                    "specification",
                    "glob-json",
                    text=safe_globs_json,
                ),
            )
        )
        self.commit_registry(old, "accepted base")
        current = self.bundle("task-new", "successor")
        self.commit_supersession(old, current)
        registry = MODULE.load_registry(self.repo / ".agents/omx_artifacts.toml")
        archived = next(
            item for item in registry["bundle"] if item["status"] == "superseded"
        )
        unsafe = self.repo / archived["artifact"][0]["path"]
        unsafe.write_text("machine /home/example/repo/file\n", encoding="utf-8")
        payload = unsafe.read_bytes()
        archived["artifact"][0]["sha256"] = hashlib.sha256(payload).hexdigest()
        archived["artifact"][0]["bytes"] = len(payload)
        with self.assertRaisesRegex(MODULE.ValidationError, "absolute path"):
            MODULE.validate_registry(self.repo, self.write_registry(registry["bundle"]))

        unsafe.write_text("r**a**w/file.txt\n", encoding="utf-8")
        payload = unsafe.read_bytes()
        archived["artifact"][0]["sha256"] = hashlib.sha256(payload).hexdigest()
        archived["artifact"][0]["bytes"] = len(payload)
        with self.assertRaisesRegex(MODULE.ValidationError, "private or raw path part"):
            MODULE.validate_registry(self.repo, self.write_registry(registry["bundle"]))

        unsafe.write_text("cust**om**:\n", encoding="utf-8")
        payload = unsafe.read_bytes()
        archived["artifact"][0]["sha256"] = hashlib.sha256(payload).hexdigest()
        archived["artifact"][0]["bytes"] = len(payload)
        with self.assertRaisesRegex(MODULE.ValidationError, "unsupported URI scheme"):
            MODULE.validate_registry(self.repo, self.write_registry(registry["bundle"]))

        unsafe.write_text(safe_globs, encoding="utf-8")
        payload = unsafe.read_bytes()
        archived["artifact"][0]["sha256"] = hashlib.sha256(payload).hexdigest()
        archived["artifact"][0]["bytes"] = len(payload)

        archived_by_role = {item["role"]: item for item in archived["artifact"]}
        archived_path_payloads = (
            {
                "context": ("**src/file**/home/alice/secret\n", safe_globs),
                "glob-csv": (
                    'field,"**src/*/module.py**/home/alice/secret"\n',
                    safe_globs,
                ),
                "glob-json": (
                    json.dumps({"note": "**src/file**/home/alice/secret"}) + "\n",
                    safe_globs_json,
                ),
            },
            {
                "context": ("src/**module.py**/home/alice/secret\n", safe_globs),
                "glob-csv": (
                    'field,"**https://example.invalid/docs**/home/alice/secret"\n',
                    safe_globs,
                ),
                "glob-json": (
                    json.dumps(
                        {
                            "note": "src/%252A%252Amodule.py%252A%252A%252Fhome"
                            "%252Falice%252Fsecret"
                        }
                    )
                    + "\n",
                    safe_globs_json,
                ),
            },
            {
                "context": (
                    "*https://example.invalid/docs*/home/alice/secret\n",
                    safe_globs,
                ),
                "glob-csv": (
                    'field,"src/*module.py*/home/alice/secret"\n',
                    safe_globs,
                ),
                "glob-json": (
                    json.dumps(
                        {"note": "_https://example.invalid/docs_/home/alice/secret"}
                    )
                    + "\n",
                    safe_globs_json,
                ),
            },
            {
                "context": ("src/*/module.py**/home/alice/secret\n", safe_globs),
                "glob-csv": (
                    "field,https://example.invalid/src/*/module.py**/home/alice/secret\n",
                    safe_globs,
                ),
                "glob-json": (
                    json.dumps({"note": "src/*/module.py**/home/alice/secret"}) + "\n",
                    safe_globs_json,
                ),
            },
            {
                "context": (
                    "[x](https://example.invalid/src/*/module.py)-/home/alice/secret\n",
                    safe_globs,
                ),
                "glob-csv": (
                    "field,[x](https://example.invalid/src/*/module.py)-/home/alice/secret\n",
                    safe_globs,
                ),
                "glob-json": (
                    json.dumps(
                        {
                            "note": "[x](https://example.invalid/src/*/module.py)"
                            "-/home/alice/secret"
                        }
                    )
                    + "\n",
                    safe_globs_json,
                ),
            },
            {
                "context": (
                    "[x](https://example.invalid/docs)_/home/alice/secret\n",
                    safe_globs,
                ),
                "glob-csv": (
                    "field,[x](https://example.invalid/docs)_/home/alice/secret\n",
                    safe_globs,
                ),
                "glob-json": (
                    json.dumps(
                        {"note": "[x](https://example.invalid/docs)_/home/alice/secret"}
                    )
                    + "\n",
                    safe_globs_json,
                ),
            },
            {
                "context": (
                    "https://example.invalid/?next=/home/alice/secret\n",
                    safe_globs,
                ),
                "glob-csv": (
                    "field,https://example.invalid/#/home/alice/secret\n",
                    safe_globs,
                ),
                "glob-json": (
                    json.dumps(
                        {
                            "note": "https://example.invalid/"
                            "?next=%252Fhome%252Falice%252Fsecret"
                        }
                    )
                    + "\n",
                    safe_globs_json,
                ),
            },
            {
                "context": ("https://example.invalid//home/alice\n", safe_globs),
                "glob-csv": (
                    "field,https://example.invalid//server/share\n",
                    safe_globs,
                ),
                "glob-json": (
                    json.dumps({"note": "https://example.invalid//home/alice"}) + "\n",
                    safe_globs_json,
                ),
            },
            {
                "context": ("https://example.invalid/a//b\n", safe_globs),
                "glob-csv": (
                    "field,https://example.invalid/a/%2Fb\n",
                    safe_globs,
                ),
                "glob-json": (
                    json.dumps({"note": "https://example.invalid/a/%252Fb"}) + "\n",
                    safe_globs_json,
                ),
            },
            {
                "context": (
                    "https://example.invalid/?next=//machine\n",
                    safe_globs,
                ),
                "glob-csv": (
                    "field,https://example.invalid/#//machine\n",
                    safe_globs,
                ),
                "glob-json": (
                    json.dumps(
                        {"note": "https://example.invalid/?next=%252F%252Fmachine"}
                    )
                    + "\n",
                    safe_globs_json,
                ),
            },
        )
        for archived_payloads in archived_path_payloads:
            for role, (unsafe_text, safe_text) in archived_payloads.items():
                artifact = archived_by_role[role]
                path = self.repo / artifact["path"]
                path.write_text(unsafe_text, encoding="utf-8")
                payload = path.read_bytes()
                artifact["sha256"] = hashlib.sha256(payload).hexdigest()
                artifact["bytes"] = len(payload)
                with self.assertRaisesRegex(MODULE.ValidationError, "absolute path"):
                    MODULE.validate_registry(
                        self.repo, self.write_registry(registry["bundle"])
                    )
                path.write_text(safe_text, encoding="utf-8")
                payload = path.read_bytes()
                artifact["sha256"] = hashlib.sha256(payload).hexdigest()
                artifact["bytes"] = len(payload)

        archived_http_payloads = {
            "context": (
                "https://outer.invalid/?next=https://:443/x\n",
                safe_globs,
            ),
            "glob-csv": (
                "field,https://outer.invalid/?next=https%253A%252F%252F%253A443%252Fx\n",
                safe_globs,
            ),
            "glob-json": (
                json.dumps({"note": "https://outer.invalid/path/https://:443/x"})
                + "\n",
                safe_globs_json,
            ),
        }
        for role, (unsafe_text, safe_text) in archived_http_payloads.items():
            artifact = archived_by_role[role]
            path = self.repo / artifact["path"]
            path.write_text(unsafe_text, encoding="utf-8")
            payload = path.read_bytes()
            artifact["sha256"] = hashlib.sha256(payload).hexdigest()
            artifact["bytes"] = len(payload)
            with self.assertRaisesRegex(MODULE.ValidationError, "malformed HTTP URI"):
                MODULE.validate_registry(
                    self.repo, self.write_registry(registry["bundle"])
                )
            path.write_text(safe_text, encoding="utf-8")
            payload = path.read_bytes()
            artifact["sha256"] = hashlib.sha256(payload).hexdigest()
            artifact["bytes"] = len(payload)

        archived_scheme_payloads = (
            {
                "context": ("cust*om*:\n", safe_globs),
                "glob-csv": ("field,java*script*:alert(1)\n", safe_globs),
                "glob-json": (
                    json.dumps({"note": "cust*om*:"}) + "\n",
                    safe_globs_json,
                ),
            },
            {
                "context": ("**custom:**?opaque\n", safe_globs),
                "glob-csv": (
                    "field,%252A%252Acustom%253A%252A%252A%253Fopaque\n",
                    safe_globs,
                ),
                "glob-json": (
                    json.dumps({"note": "**custom:**?opaque"}) + "\n",
                    safe_globs_json,
                ),
            },
            {
                "context": ("**custom:**,opaque\n", safe_globs),
                "glob-csv": ("field,**custom:**.opaque\n", safe_globs),
                "glob-json": (
                    json.dumps({"note": "**custom:**;opaque"}) + "\n",
                    safe_globs_json,
                ),
            },
            {
                "context": ("**custom:**//opaque\n", safe_globs),
                "glob-csv": ("field,__custom:__//opaque\n", safe_globs),
                "glob-json": (
                    json.dumps({"note": "**123:**//opaque"}) + "\n",
                    safe_globs_json,
                ),
            },
            {
                "context": (
                    "[x](https://example.invalid/src/*/module.py)-custom://opaque\n",
                    safe_globs,
                ),
                "glob-csv": (
                    "field,[x](https://example.invalid/src/*/module.py)-123://opaque\n",
                    safe_globs,
                ),
                "glob-json": (
                    json.dumps(
                        {
                            "note": "[x](https://example.invalid/src/*/module.py)"
                            "-**custom:**//opaque"
                        }
                    )
                    + "\n",
                    safe_globs_json,
                ),
            },
            {
                "context": (
                    "[x](https://example.invalid/?next=custom://opaque)\n",
                    safe_globs,
                ),
                "glob-csv": (
                    "field,https://example.invalid/?next=123://opaque\n",
                    safe_globs,
                ),
                "glob-json": (
                    json.dumps({"note": "https://example.invalid/path/custom://opaque"})
                    + "\n",
                    safe_globs_json,
                ),
            },
            {
                "context": ("custom.scheme:123\n", safe_globs),
                "glob-csv": ("field,123.456:789\n", safe_globs),
                "glob-json": (
                    json.dumps({"note": "custom.scheme:123"}) + "\n",
                    safe_globs_json,
                ),
            },
        )
        for archived_payloads in archived_scheme_payloads:
            for role, (unsafe_text, safe_text) in archived_payloads.items():
                artifact = archived_by_role[role]
                path = self.repo / artifact["path"]
                path.write_text(unsafe_text, encoding="utf-8")
                payload = path.read_bytes()
                artifact["sha256"] = hashlib.sha256(payload).hexdigest()
                artifact["bytes"] = len(payload)
                with self.assertRaisesRegex(
                    MODULE.ValidationError, "unsupported URI scheme"
                ):
                    MODULE.validate_registry(
                        self.repo, self.write_registry(registry["bundle"])
                    )
                path.write_text(safe_text, encoding="utf-8")
                payload = path.read_bytes()
                artifact["sha256"] = hashlib.sha256(payload).hexdigest()
                artifact["bytes"] = len(payload)
        MODULE.validate_registry(self.repo, self.write_registry(registry["bundle"]))

        MODULE._scan_text(
            (
                "https://example.invalid/docs and "
                "https://example.invalid:443/a%20b?q=value#section plus "
                "<https://example.invalid/docs> plus "
                "[spec](https://example.invalid/docs_(v2)) plus "
                "<https://example.invalid/docs_(v2)> plus "
                "aria_nbv/**/AGENTS.md, AGENTS.md:6-12, "
                "__pycache__/module.pyc, "
                "main:.graphifyignore:34-51, Makefile:181-194, "
                "main:Makefile:181-194, origin/main:AGENTS.md:30-31, "
                "HEAD:src/pkg.module.py:12-20, HEAD:src/tool:12, HEAD:LICENSE:1, "
                "HEAD:scripts/run_checks:42, origin/main:Dockerfile:8-9, "
                "**Architect/Critic:**, and **owner:**\n"
            ),
            "non-path syntax",
            contract_version=2,
        )
        MODULE._scan_text(
            "./relative ../parent\n", "relative paths", contract_version=2
        )
        MODULE._scan_text("historical /tmp reference\n", "legacy", contract_version=1)
        MODULE._scan_text(
            "legacy <bundle-id> placeholder\n", "legacy", contract_version=1
        )
        for legacy in (
            "C:/Users/alice/project/file.txt",
            "\\\\server\\share\\project\\file.txt",
            "file:///tmp",
            "%252Fhome%252Falice%252Fsecret.txt",
            "<div>legacy HTML fragment</div>",
            "session_019f9e3a-169a-7673-9df2-c4bd0277bd35",
            _fixture("token_ghp_", "abcdefghijklmnopqrstuvwxyz"),
        ):
            MODULE._scan_text(legacy, "legacy", contract_version=1)

        with self.assertRaisesRegex(MODULE.ValidationError, "absolute path"):
            MODULE._scan_decoded_strings(
                json.loads(r'{"path":"\u002fhome\u002falice\u002fsecret"}'),
                "decoded JSON",
                contract_version=2,
            )

    def test_registry_schema_and_privacy_cover_metadata(self) -> None:
        for insertion, message in (
            ('mystery = "value"\n', "unknown bundle fields"),
            (
                _fixture('secret = "ghp_', 'abcdefghijklmnopqrstuvwxyz"\n'),
                "GitHub token",
            ),
        ):
            with self.subTest(message=message):
                registry = self.write_registry([self.bundle()])
                text = registry.read_text(encoding="utf-8").replace(
                    "[[bundle]]\n", f"[[bundle]]\n{insertion}", 1
                )
                registry.write_text(text, encoding="utf-8")
                with self.assertRaisesRegex(MODULE.ValidationError, message):
                    MODULE.load_registry(registry)

        registry = self.write_registry([self.bundle()])
        text = registry.read_text(encoding="utf-8").replace(
            "[[bundle.artifact]]\n",
            '[[bundle.artifact]]\nmystery = "value"\n',
            1,
        )
        registry.write_text(text, encoding="utf-8")
        with self.assertRaisesRegex(MODULE.ValidationError, "unknown artifact fields"):
            MODULE.load_registry(registry)

        for encoded, message in (
            (r"\u002Foperator\u002Fsecret", "absolute path"),
            (r"owner\u0040example.com", "email address"),
            (_fixture(r"ghp_\u0061", "bcdefghijklmnopqrstuvwxyz"), "GitHub token"),
        ):
            with self.subTest(decoded_registry_value=message):
                bundle = self.bundle()
                bundle["artifact"][0]["review_kinds"] = [encoded]
                registry = self.write_registry([bundle])
                with self.assertRaisesRegex(MODULE.ValidationError, message):
                    MODULE.load_registry(registry)

        bundle = self.bundle()
        bundle["artifact"][0]["review_kinds"] = ["architect"]
        registry = self.write_registry([bundle])
        with self.assertRaisesRegex(
            MODULE.ValidationError, "only review artifacts may declare review_kinds"
        ):
            MODULE.load_registry(registry)

        for old, new, message in (
            ('status = "current"', 'status = ["current"]', "status must be a string"),
            (
                'path = ".omx/context/context.md"',
                "path = 7",
                "artifact field path must be a string",
            ),
            (
                'review_kinds = ["architect", "critic"]',
                'review_kinds = [["architect"], "critic"]',
                "review_kinds must be a string list",
            ),
            (
                'review_kinds = ["architect", "critic"]',
                'review_kinds = ["architect", "critic", "critic"]',
                "review_kinds must be unique",
            ),
        ):
            registry = self.write_registry([self.bundle()])
            registry.write_text(
                registry.read_text(encoding="utf-8").replace(old, new, 1),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(MODULE.ValidationError, message):
                MODULE.load_registry(registry)

        with self.assertRaisesRegex(MODULE.ValidationError, "invalid UTF-8 registry"):
            MODULE._parse_registry(b"\xff")

        with self.assertRaisesRegex(
            MODULE.ValidationError, "registry exceeds byte limit"
        ):
            MODULE._parse_registry(b"x" * (MODULE.MAX_REGISTRY_BYTES + 1))

        oversized_registry = self.repo / "oversized-registry.toml"
        oversized_registry.write_bytes(b"x" * (MODULE.MAX_REGISTRY_BYTES + 1))
        with self.assertRaisesRegex(
            MODULE.ValidationError, "registry exceeds byte limit"
        ):
            MODULE.load_registry(oversized_registry)

        symlink_target = self.write_registry([self.bundle("symlink-registry")])
        symlink_registry = self.repo / "registry-link.toml"
        symlink_registry.symlink_to(symlink_target.name)
        with self.assertRaisesRegex(MODULE.ValidationError, "regular file"):
            MODULE.load_registry(symlink_registry)

        bundle = self.bundle("invalid-utf8")
        target = self.repo / bundle["artifact"][0]["path"]
        target.write_bytes(b"\xff")
        content = target.read_bytes()
        bundle["artifact"][0]["sha256"] = hashlib.sha256(content).hexdigest()
        bundle["artifact"][0]["bytes"] = len(content)
        self.assert_invalid(bundle, "invalid UTF-8 registered evidence")

        bundle = self.bundle("surrogate-json")
        bundle["artifact"].append(
            self.artifact(
                ".omx/specs/surrogate.json",
                "specification",
                "surrogate-json",
                text=r'{"note":"\ud800"}' + "\n",
            )
        )
        self.assert_invalid(bundle, "invalid Unicode")

        bundle = self.bundle("nested-handoff-role")
        handoff = next(
            item for item in bundle["artifact"] if item["family"] == "handoff"
        )
        handoff_path = self.repo / handoff["path"]
        handoff_payload = json.loads(handoff_path.read_text(encoding="utf-8"))
        handoff_payload["roles"][0] = ["context"]
        handoff_path.write_text(json.dumps(handoff_payload) + "\n", encoding="utf-8")
        content = handoff_path.read_bytes()
        handoff["sha256"] = hashlib.sha256(content).hexdigest()
        handoff["bytes"] = len(content)
        bundle["handoff_sha256"] = handoff["sha256"]
        self.assert_invalid(bundle, "handoff contract mismatch")

        stale = self.bundle("oversized-stale-metadata")
        stale_target = self.repo / stale["artifact"][0]["path"]
        stale_target.write_text("x" * (MODULE.MAX_ARTIFACT_BYTES + 1), encoding="utf-8")
        self.assert_invalid(stale, "artifact exceeds byte limit")

        bundle = self.bundle("oversized-artifact")
        target = self.repo / bundle["artifact"][0]["path"]
        target.write_text("x" * (MODULE.MAX_ARTIFACT_BYTES + 1), encoding="utf-8")
        content = target.read_bytes()
        bundle["artifact"][0]["sha256"] = hashlib.sha256(content).hexdigest()
        bundle["artifact"][0]["bytes"] = len(content)
        self.assert_invalid(bundle, "artifact exceeds byte limit")

    def test_predecessor_chain_has_a_hard_limit(self) -> None:
        bundles: dict[str, dict[str, Any]] = {}
        predecessor: str | None = None
        for index in range(MODULE.MAX_BUNDLE_CHAIN_LENGTH + 1):
            bundle_id = f"bundle-{index}"
            bundle: dict[str, Any] = {
                "id": bundle_id,
                "task": "bounded-chain",
                "status": "superseded",
                "contract_version": 2,
                "classification": "accepted-decision-evidence",
                "baseline_commit": self.baseline,
                "handoff_sha256": "0" * 64,
                "acceptance_sha256": "0" * 64,
                "artifact": [],
            }
            if predecessor is not None:
                bundle["predecessor_bundle_id"] = predecessor
            bundles[bundle_id] = bundle
            predecessor = bundle_id
        bounded = dict(list(bundles.items())[:200])
        original_digest = MODULE.bundle_content_sha256
        with patch.object(
            MODULE, "bundle_content_sha256", wraps=original_digest
        ) as digest:
            self.assertEqual(len(MODULE._bundle_chain_digests(bounded)), len(bounded))
            self.assertEqual(digest.call_count, len(bounded))
        with self.assertRaisesRegex(MODULE.ValidationError, "chain exceeds limit"):
            MODULE.bundle_chain_sha256(predecessor, bundles)

    def test_registry_entry_counts_have_hard_limits(self) -> None:
        bundle = self.bundle()
        registry = self.write_registry([bundle])
        payload = registry.read_bytes()
        with patch.object(MODULE, "MAX_REGISTRY_BUNDLES", 0):
            with self.assertRaisesRegex(MODULE.ValidationError, "bundle-count limit"):
                MODULE._parse_registry(payload)
        with patch.object(MODULE, "MAX_ARTIFACTS_PER_BUNDLE", 0):
            with self.assertRaisesRegex(MODULE.ValidationError, "artifact-count limit"):
                MODULE._parse_registry(payload)
        with patch.object(MODULE, "MAX_REGISTRY_ARTIFACTS", 0):
            with self.assertRaisesRegex(
                MODULE.ValidationError, "total artifact-count limit"
            ):
                MODULE._parse_registry(payload)

    def test_historical_registry_byte_limit_is_checked_before_git_show(self) -> None:
        bundle = self.bundle()
        self.commit_registry(bundle, "accepted base")
        with patch.object(MODULE, "MAX_REGISTRY_BYTES", 1):
            with self.assertRaisesRegex(
                MODULE.ValidationError, "historical registry exceeds byte limit"
            ):
                MODULE._previous_registry(self.repo, "HEAD")

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

    def test_tracked_membership_preserves_control_characters(self) -> None:
        for separator in ("\t", "\n"):
            with self.subTest(separator=repr(separator)):
                relative = f".omx/context/a{separator}b.md"
                path = self.repo / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("evidence\n", encoding="utf-8")
                self.git("add", "-f", "--", relative)

                MODULE.validate_tracked(self.repo, {relative})

                self.git("rm", "-f", "--", relative)

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
                    for role, bundle_key in (
                        ("handoff", "handoff_sha256"),
                        ("acceptance-record", "acceptance_sha256"),
                        ("independent-review", None),
                    ):
                        artifact = next(
                            item for item in bundle["artifact"] if item["role"] == role
                        )
                        target = self.repo / artifact["path"]
                        identity = json.loads(target.read_text(encoding="utf-8"))
                        identity["bundle_id"] = bundle["id"]
                        identity["task"] = bundle["task"]
                        target.write_text(json.dumps(identity) + "\n", encoding="utf-8")
                        payload = target.read_bytes()
                        artifact["sha256"] = hashlib.sha256(payload).hexdigest()
                        artifact["bytes"] = len(payload)
                        if bundle_key is not None:
                            bundle[bundle_key] = artifact["sha256"]
                self.commit_registry(bundle, change)
                with patch.dict(os.environ, LOCAL_TRANSITION_ENV):
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

        with patch.dict(os.environ, LOCAL_TRANSITION_ENV):
            self.assertEqual(
                MEMORY_MODULE.check_registered_omx_artifacts(
                    repo_root=self.repo, validator_path=SCRIPT
                ),
                [],
            )

    def test_full_history_rejects_restored_accepted_bundle_mutation(self) -> None:
        original = self.bundle("task-current")
        self.commit_registry(original, "accepted base")
        previous = self.git("rev-parse", "HEAD").stdout.strip()

        mutated = deepcopy(original)
        target = self.repo / mutated["artifact"][0]["path"]
        original_payload = target.read_bytes()
        target.write_text("transient accepted evidence mutation\n", encoding="utf-8")
        payload = target.read_bytes()
        mutated["artifact"][0]["sha256"] = hashlib.sha256(payload).hexdigest()
        mutated["artifact"][0]["bytes"] = len(payload)
        self.commit_registry(mutated, "transient accepted mutation")

        target.write_bytes(original_payload)
        self.commit_registry(original, "restore accepted state")
        result = self.run_validator(previous)

        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(result.stderr, "accepted bundle mutated")
        self.assertNotIn(
            "omx-artifact-history-", self.git("worktree", "list", "--porcelain").stdout
        )

    def test_full_history_rejects_restored_registry_symlinks(self) -> None:
        bundle = self.bundle("task-current")
        self.commit_registry(bundle, "accepted base")
        previous = self.git("rev-parse", "HEAD").stdout.strip()
        registry = self.repo / ".agents/omx_artifacts.toml"
        registry_payload = registry.read_bytes()

        for kind in ("regular", "dangling"):
            with self.subTest(kind=kind):
                self.git("checkout", "-q", "main")
                self.git("checkout", "-qb", f"feature-{kind}-registry-link")
                target = self.repo / ".agents/omx-artifacts-target.toml"
                registry.unlink()
                if kind == "regular":
                    target.write_bytes(registry_payload)
                registry.symlink_to(target.name)
                self.git("add", "-A")
                self.git("commit", "-qm", f"transient {kind} registry symlink")

                registry.unlink()
                registry.write_bytes(registry_payload)
                if target.exists():
                    target.unlink()
                self.git("add", "-A")
                self.git("commit", "-qm", "restore regular registry")
                result = self.run_validator(previous)

                self.assertNotEqual(result.returncode, 0)
                self.assertRegex(
                    result.stderr, "historical registry must be a regular file"
                )

    def test_full_history_accepts_valid_multi_commit_successor_chain(self) -> None:
        first = self.bundle("task-first")
        self.commit_registry(first, "first accepted bundle")
        previous = self.git("rev-parse", "HEAD").stdout.strip()
        second = self.bundle("task-second", "second")
        self.commit_supersession(first, second)
        third = self.bundle("task-third", "third")
        self.commit_second_supersession(third)

        result = self.run_validator(previous)

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_full_history_allows_registry_free_prefix_without_omx_payload(self) -> None:
        previous = self.git("rev-parse", "HEAD").stdout.strip()
        (self.repo / "README.md").write_text("prefix change\n", encoding="utf-8")
        self.git("add", "README.md")
        self.git("commit", "-qm", "registry-free prefix")
        self.commit_registry(self.bundle("task-current"), "bootstrap registry")

        result = self.run_validator(previous)

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_full_history_allows_unchanged_prepolicy_omx_until_bootstrap(
        self,
    ) -> None:
        bundle = self.bundle("task-current")
        self.git("add", "-f", ".omx")
        self.git("commit", "-qm", "prepolicy OMX evidence")
        previous = self.git("rev-parse", "HEAD").stdout.strip()
        (self.repo / "README.md").write_text("ownership contract\n", encoding="utf-8")
        self.git("add", "README.md")
        self.git("commit", "-qm", "define ownership before bootstrap")
        self.commit_registry(bundle, "bootstrap accepted registry")

        result = self.run_validator(previous)

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_full_history_rejects_registry_free_prefix_with_omx_payload(self) -> None:
        previous = self.git("rev-parse", "HEAD").stdout.strip()
        payload = self.repo / ".omx/plans/unregistered.md"
        payload.parent.mkdir(parents=True)
        payload.write_text("transient unregistered payload\n", encoding="utf-8")
        self.git("add", "-f", ".omx/plans/unregistered.md")
        self.git("commit", "-qm", "transient registry-free OMX payload")
        self.git("rm", "-q", ".omx/plans/unregistered.md")
        self.git("commit", "-qm", "remove transient OMX payload")
        self.commit_registry(self.bundle("task-current"), "bootstrap registry")

        result = self.run_validator(previous)

        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(
            result.stderr, "registry-free OMX payload changed after previous_ref"
        )

    def test_full_history_requires_previous_ref_to_ancestor_head(self) -> None:
        self.commit_registry(self.bundle("task-current"), "accepted registry")
        sibling = self.git("commit-tree", f"{self.baseline}^{{tree}}").stdout.strip()

        result = self.run_validator(sibling)

        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(result.stderr, "previous_ref must be an ancestor of HEAD")

    def test_full_history_rejects_previous_ref_on_merge_side_parent(self) -> None:
        self.commit_registry(self.bundle("task-current"), "accepted registry")
        self.git("checkout", "-qb", "feature")
        (self.repo / "feature.txt").write_text("feature\n", encoding="utf-8")
        self.git("add", "feature.txt")
        self.git("commit", "-qm", "feature commit")
        feature = self.git("rev-parse", "HEAD").stdout.strip()

        self.git("checkout", "-q", "main")
        (self.repo / "main.txt").write_text("main\n", encoding="utf-8")
        self.git("add", "main.txt")
        self.git("commit", "-qm", "main commit")
        side_parent = self.git("rev-parse", "HEAD").stdout.strip()

        self.git("checkout", "-q", "feature")
        self.git("merge", "--no-ff", "-qm", "merge main", side_parent)
        self.assertEqual(
            self.git("rev-parse", "HEAD^1").stdout.strip(),
            feature,
        )

        result = self.run_validator(side_parent)

        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(result.stderr, "first-parent chain")

    def test_pr_head_checkout_exposes_transient_commits_behind_merge_ref(self) -> None:
        previous = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("checkout", "-qb", "feature")
        payload = self.repo / ".omx/plans/unregistered.md"
        payload.parent.mkdir(parents=True)
        payload.write_text("transient unregistered payload\n", encoding="utf-8")
        self.git("add", "-f", ".omx/plans/unregistered.md")
        self.git("commit", "-qm", "transient registry-free payload")
        self.git("rm", "-q", ".omx/plans/unregistered.md")
        self.git("commit", "-qm", "remove transient payload")
        self.commit_registry(self.bundle("task-current"), "accepted registry")
        feature = self.git("rev-parse", "HEAD").stdout.strip()

        self.git("checkout", "-q", "main")
        self.git("merge", "--no-ff", "-qm", "synthetic pull request merge", feature)
        self.assertEqual(self.git("rev-parse", "HEAD^1").stdout.strip(), previous)
        self.assertEqual(self.git("rev-parse", "HEAD^2").stdout.strip(), feature)

        self.git("checkout", "--detach", "-q", feature)
        result = self.run_validator(previous)

        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(
            result.stderr, "registry-free OMX payload changed after previous_ref"
        )

    def test_pr_history_uses_merge_base_when_base_branch_advances(self) -> None:
        fork = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("checkout", "-qb", "feature")
        payload = self.repo / ".omx/plans/unregistered.md"
        payload.parent.mkdir(parents=True)
        payload.write_text("transient unregistered payload\n", encoding="utf-8")
        self.git("add", "-f", ".omx/plans/unregistered.md")
        self.git("commit", "-qm", "transient registry-free payload")
        self.git("rm", "-q", ".omx/plans/unregistered.md")
        self.git("commit", "-qm", "remove transient payload")
        self.commit_registry(self.bundle("task-current"), "accepted registry")
        feature = self.git("rev-parse", "HEAD").stdout.strip()

        self.git("checkout", "-q", "main")
        (self.repo / "main.txt").write_text("main advanced\n", encoding="utf-8")
        self.git("add", "main.txt")
        self.git("commit", "-qm", "advance base branch")
        base_tip = self.git("rev-parse", "HEAD").stdout.strip()

        self.git("checkout", "--detach", "-q", feature)
        ancestry = subprocess.run(
            ["git", "merge-base", "--is-ancestor", base_tip, "HEAD"],
            cwd=self.repo,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(ancestry.returncode, 0)
        merge_base = self.git("merge-base", "HEAD", base_tip).stdout.strip()
        self.assertEqual(merge_base, fork)

        base_tip_result = self.run_validator(base_tip)
        merge_base_result = self.run_validator(merge_base)

        self.assertNotEqual(base_tip_result.returncode, 0)
        self.assertRegex(
            base_tip_result.stderr, "previous_ref must be an ancestor of HEAD"
        )
        self.assertNotEqual(merge_base_result.returncode, 0)
        self.assertRegex(
            merge_base_result.stderr,
            "registry-free OMX payload changed after previous_ref",
        )

    def test_full_history_disables_lfs_process_filter(self) -> None:
        bundle = self.bundle("task-current")
        self.git("config", "filter.lfs.clean", "cat")
        self.git("config", "filter.lfs.smudge", "cat")
        self.git("config", "filter.lfs.process", "")
        self.git("config", "filter.lfs.required", "false")
        (self.repo / ".gitattributes").write_text(
            ".omx/** filter=lfs\n", encoding="utf-8"
        )
        self.commit_registry(bundle, "accepted registry")
        previous = self.git("rev-parse", "HEAD").stdout.strip()
        (self.repo / "README.md").write_text("next snapshot\n", encoding="utf-8")
        self.git("add", "README.md")
        self.git("commit", "-qm", "next snapshot")
        self.git("config", "filter.lfs.process", "false")
        self.git("config", "filter.lfs.required", "true")

        result = self.run_validator(previous)

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_lfs_pointer_is_not_accepted_evidence(self) -> None:
        bundle = self.bundle("task-current")
        artifact = bundle["artifact"][0]
        target = self.repo / artifact["path"]
        target.write_text(
            "version https://git-lfs.github.com/spec/v1\n"
            f"oid sha256:{'0' * 64}\n"
            "size 123\n",
            encoding="utf-8",
        )
        payload = target.read_bytes()
        artifact["sha256"] = hashlib.sha256(payload).hexdigest()
        artifact["bytes"] = len(payload)
        registry = self.write_registry([bundle])

        with self.assertRaisesRegex(MODULE.ValidationError, "LFS pointers"):
            MODULE.validate_registry(self.repo, registry)

    def test_extended_lfs_pointer_is_rejected_in_archived_v1_bundle(self) -> None:
        original = self.bundle("task-v1")
        original.pop("contract_version")
        artifact = original["artifact"][0]
        target = self.repo / artifact["path"]
        target.write_text(
            "version https://git-lfs.github.com/spec/v1\n"
            f"ext-0-example sha256:{'1' * 64} 123\n"
            f"oid sha256:{'0' * 64}\n"
            "size 123\n",
            encoding="utf-8",
        )
        payload = target.read_bytes()
        artifact["sha256"] = hashlib.sha256(payload).hexdigest()
        artifact["bytes"] = len(payload)
        self.commit_registry(original, "legacy v1", schema_version=1)

        successor = self.bundle("task-v2", "successor")
        self.commit_supersession(original, successor)

        with self.assertRaisesRegex(MODULE.ValidationError, "LFS pointers"):
            MODULE.validate_registry(
                self.repo, self.repo / ".agents/omx_artifacts.toml"
            )

    def test_full_history_rejects_restored_registry_removal(self) -> None:
        bundle = self.bundle("task-current")
        self.commit_registry(bundle, "accepted base")
        previous = self.git("rev-parse", "HEAD").stdout.strip()
        registry = self.repo / ".agents/omx_artifacts.toml"
        registry_payload = registry.read_bytes()
        self.git("rm", "-q", ".agents/omx_artifacts.toml")
        self.git("commit", "-qm", "transient registry removal")
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_bytes(registry_payload)
        self.git("add", ".agents/omx_artifacts.toml")
        self.git("commit", "-qm", "restore registry")

        result = self.run_validator(previous)

        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(
            result.stderr, "accepted OMX artifact registry must not disappear"
        )

    def test_semantic_rollback_is_a_new_successor_chain(self) -> None:
        first = self.bundle("task-first")
        self.commit_registry(first, "first accepted bundle")
        second = self.bundle("task-second", "second")
        self.commit_supersession(first, second)
        third = self.bundle("task-rollback", "rollback")
        self.commit_second_supersession(third)

        registry = self.repo / ".agents/omx_artifacts.toml"
        self.assertEqual(len(MODULE.validate_registry(self.repo, registry)), 21)
        by_id = {item["id"]: item for item in MODULE.load_registry(registry)["bundle"]}
        self.assertEqual(by_id[first["id"]]["superseded_by"], second["id"])
        self.assertEqual(by_id[second["id"]]["superseded_by"], third["id"])
        self.assertEqual(by_id[third["id"]]["status"], "current")

    def test_predecessor_bundle_digest_detects_drift(self) -> None:
        original = self.bundle("task-old")
        self.commit_registry(original, "accepted base")
        successor = self.bundle("task-new", "successor")
        self.commit_supersession(original, successor)
        registry = MODULE.load_registry(self.repo / ".agents/omx_artifacts.toml")
        current = next(
            item for item in registry["bundle"] if item["status"] == "current"
        )
        current["predecessor_bundle_sha256"] = "0" * 64
        handoff = next(
            item for item in current["artifact"] if item["family"] == "handoff"
        )
        handoff_path = self.repo / handoff["path"]
        payload = json.loads(handoff_path.read_text(encoding="utf-8"))
        payload["predecessor_bundle_sha256"] = "0" * 64
        handoff_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        content = handoff_path.read_bytes()
        handoff["sha256"] = hashlib.sha256(content).hexdigest()
        handoff["bytes"] = len(content)
        current["handoff_sha256"] = handoff["sha256"]
        self.write_registry(registry["bundle"], ".agents/omx_artifacts.toml")
        with self.assertRaisesRegex(MODULE.ValidationError, "content digest drift"):
            MODULE.validate_registry(
                self.repo, self.repo / ".agents/omx_artifacts.toml"
            )

    def test_contract_v2_cannot_downgrade_to_v1(self) -> None:
        original = self.bundle("task-old")
        self.commit_registry(original, "accepted base")
        successor = self.bundle("task-new", "successor")
        self.commit_supersession(original, successor)
        registry_path = self.repo / ".agents/omx_artifacts.toml"
        registry = MODULE.load_registry(registry_path)
        current = next(
            item for item in registry["bundle"] if item["status"] == "current"
        )
        current.pop("contract_version")
        current.pop("predecessor_bundle_sha256")
        current.pop("predecessor_chain_sha256")
        self.write_registry(
            registry["bundle"],
            ".agents/omx_artifacts.toml",
            schema_version=1,
        )
        with self.assertRaisesRegex(
            MODULE.ValidationError, "live registry schema_version must be 2"
        ):
            MODULE.validate_registry(self.repo, registry_path)
        with self.assertRaisesRegex(
            MODULE.ValidationError, "live registry schema_version must be 2"
        ):
            MODULE.validate_transition(
                {"schema_version": 2, "bundle": []},
                MODULE._parse_registry(registry_path.read_bytes()),
            )

    def test_head_receipt_binds_the_complete_predecessor_chain(self) -> None:
        first = self.bundle("task-first")
        self.commit_registry(first, "first accepted bundle")
        second = self.bundle("task-second", "second")
        self.commit_supersession(first, second)
        third = self.bundle("task-third", "third")
        self.commit_second_supersession(third)

        registry_path = self.repo / ".agents/omx_artifacts.toml"
        registry = MODULE.load_registry(registry_path)
        by_id = {item["id"]: item for item in registry["bundle"]}
        first_archived = by_id[first["id"]]
        second_archived = by_id[second["id"]]

        first_artifact = first_archived["artifact"][0]
        target = self.repo / first_artifact["path"]
        target.write_text("rewritten oldest evidence\n", encoding="utf-8")
        content = target.read_bytes()
        first_artifact["sha256"] = hashlib.sha256(content).hexdigest()
        first_artifact["bytes"] = len(content)

        second_archived["predecessor_bundle_sha256"] = MODULE.bundle_content_sha256(
            first_archived
        )
        second_handoff = next(
            item for item in second_archived["artifact"] if item["family"] == "handoff"
        )
        handoff_path = self.repo / second_handoff["path"]
        handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
        handoff["predecessor_bundle_sha256"] = second_archived[
            "predecessor_bundle_sha256"
        ]
        handoff_path.write_text(json.dumps(handoff) + "\n", encoding="utf-8")
        content = handoff_path.read_bytes()
        second_handoff["sha256"] = hashlib.sha256(content).hexdigest()
        second_handoff["bytes"] = len(content)
        second_archived["handoff_sha256"] = second_handoff["sha256"]

        self.write_registry(registry["bundle"], ".agents/omx_artifacts.toml")
        with self.assertRaisesRegex(MODULE.ValidationError, "chain digest drift"):
            MODULE.validate_registry(self.repo, registry_path)

    def test_v2_migration_receipt_binds_legacy_v1_prefix(self) -> None:
        first = self.bundle("task-first")
        first.pop("contract_version")
        self.commit_registry(first, "legacy first", schema_version=1)
        predecessor_commit = self.git("rev-parse", "HEAD").stdout.strip()

        second = self.bundle("task-second", "second")
        second.pop("contract_version")
        second["predecessor_bundle_id"] = first["id"]
        second["predecessor_registry_commit"] = predecessor_commit
        first_archived = self.archived(first, second["id"])
        for artifact in first_archived["artifact"]:
            source = self.repo / artifact["native_path"]
            destination = self.repo / artifact["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
            source.unlink()
        self.write_registry(
            [first_archived, second],
            ".agents/omx_artifacts.toml",
            schema_version=1,
        )
        self.git("add", "-f", ".agents/omx_artifacts.toml", ".omx")
        self.git("commit", "-qm", "legacy second")

        legacy_registry = MODULE._parse_registry(
            (self.repo / ".agents/omx_artifacts.toml").read_bytes()
        )
        third = self.bundle("task-third", "third")
        second_archived = self.archived(second, third["id"])
        self.bind_predecessor(
            third,
            second,
            {item["id"]: item for item in legacy_registry["bundle"]},
        )
        for artifact in second_archived["artifact"]:
            source = self.repo / artifact["native_path"]
            destination = self.repo / artifact["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
            source.unlink()
        registry_path = self.write_registry(
            [first_archived, second_archived, third],
            ".agents/omx_artifacts.toml",
            schema_version=2,
        )
        MODULE.validate_registry(self.repo, registry_path)

        first_archived["contract_version"] = 2
        self.write_registry(
            [first_archived, second_archived, third],
            ".agents/omx_artifacts.toml",
            schema_version=2,
        )
        with self.assertRaisesRegex(
            MODULE.ValidationError, "contract version downgrade"
        ):
            MODULE.validate_registry(self.repo, registry_path)
        first_archived.pop("contract_version")

        oldest_artifact = first_archived["artifact"][0]
        target = self.repo / oldest_artifact["path"]
        target.write_text("rewritten legacy evidence\n", encoding="utf-8")
        content = target.read_bytes()
        oldest_artifact["sha256"] = hashlib.sha256(content).hexdigest()
        oldest_artifact["bytes"] = len(content)
        self.write_registry(
            [first_archived, second_archived, third],
            ".agents/omx_artifacts.toml",
            schema_version=2,
        )
        with self.assertRaisesRegex(MODULE.ValidationError, "chain digest drift"):
            MODULE.validate_registry(self.repo, registry_path)

    def test_content_receipt_survives_squash_like_history(self) -> None:
        original = self.bundle("task-old")
        self.commit_registry(original, "accepted base")
        internal_predecessor = self.git("rev-parse", "HEAD").stdout.strip()
        successor = self.bundle("task-new", "successor")
        self.commit_supersession(original, successor)

        tree = self.git("rev-parse", "HEAD^{tree}").stdout.strip()
        squashed = self.git(
            "commit-tree", tree, "-p", self.baseline, "-m", "squashed result"
        ).stdout.strip()
        self.git("branch", "-f", "squashed", squashed)
        self.git("checkout", "-q", "squashed")
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", internal_predecessor, "HEAD"],
            cwd=self.repo,
            check=False,
        )
        self.assertNotEqual(ancestor.returncode, 0)
        MODULE.validate_registry(self.repo, self.repo / ".agents/omx_artifacts.toml")

    def test_superseded_bundle_must_have_been_complete(self) -> None:
        original = self.bundle("task-old")
        review = next(
            item for item in original["artifact"] if item["family"] == "review"
        )
        original["artifact"].remove(review)
        (self.repo / review["path"]).unlink()
        self.commit_registry(original, "invalid accepted base")
        successor = self.bundle("task-new", "successor")
        self.commit_supersession(original, successor)
        with self.assertRaisesRegex(MODULE.ValidationError, "role families differ"):
            MODULE.validate_registry(
                self.repo, self.repo / ".agents/omx_artifacts.toml"
            )

    def test_branch_history_omits_literal_secret_fixtures(self) -> None:
        previous = os.environ.get("OMX_ARTIFACT_PREVIOUS_REF") or "origin/main"
        commits = subprocess.run(
            ["git", "rev-list", f"{previous}..HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        for commit in commits:
            shown = subprocess.run(
                [
                    "git",
                    "show",
                    f"{commit}:scripts/tests/test_validate_omx_artifacts.py",
                ],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            if shown.returncode:
                continue
            findings = [
                label
                for pattern, label in MODULE.SENSITIVE_TEXT
                if label != "email address" and pattern.search(shown.stdout)
            ]
            self.assertEqual(findings, [], msg=f"{commit}: {findings}")

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
                with patch.dict(os.environ, LOCAL_TRANSITION_ENV):
                    errors = MEMORY_MODULE.check_registered_omx_artifacts(
                        repo_root=self.repo, validator_path=SCRIPT
                    )
                self.assertRegex(
                    errors[0],
                    "invalid or non-identical supersession|predecessor content digest drift|lacks Architect\\+Critic review",
                )

    def test_production_gate_allows_pr1_bootstrap_without_base_registry(self) -> None:
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("checkout", "-qb", "feature-bootstrap")
        bundle = self.bundle()
        self.commit_registry(bundle, "bootstrap registry")
        with patch.dict(os.environ, LOCAL_TRANSITION_ENV):
            self.assertEqual(
                MEMORY_MODULE.check_registered_omx_artifacts(
                    repo_root=self.repo, validator_path=SCRIPT
                ),
                [],
            )

    def test_production_gate_rejects_registry_and_artifact_erasure(self) -> None:
        bundle = self.bundle()
        self.commit_registry(bundle, "accepted base")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("checkout", "-qb", "feature-erasure")
        self.git("rm", "-qr", ".agents/omx_artifacts.toml", ".omx")
        self.git("commit", "-qm", "erase accepted evidence")
        with patch.dict(os.environ, LOCAL_TRANSITION_ENV):
            errors = MEMORY_MODULE.check_registered_omx_artifacts(
                repo_root=self.repo, validator_path=SCRIPT
            )
        self.assertEqual(errors, ["accepted OMX artifact registry must not be removed"])

    def test_production_gate_rejects_symlinked_registry(self) -> None:
        bundle = self.bundle()
        self.commit_registry(bundle, "accepted base")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("checkout", "-qb", "feature-symlink")
        registry = self.repo / ".agents/omx_artifacts.toml"
        target = self.repo / ".agents/omx_artifacts-target.toml"
        registry.replace(target)
        registry.symlink_to(target.name)
        self.git("add", "-A")
        self.git("commit", "-qm", "replace registry with symlink")
        with patch.dict(os.environ, LOCAL_TRANSITION_ENV):
            errors = MEMORY_MODULE.check_registered_omx_artifacts(
                repo_root=self.repo, validator_path=SCRIPT
            )
        self.assertRegex(errors[0], "registry must be a regular file")
        with self.assertRaisesRegex(
            MODULE.ValidationError, "historical registry must be a regular file"
        ):
            MODULE._previous_registry(self.repo, "HEAD")

    def test_bootstrap_rejects_dangling_registry_symlink(self) -> None:
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("checkout", "-qb", "feature-dangling-registry")
        registry = self.repo / ".agents/omx_artifacts.toml"
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.symlink_to("missing-registry.toml")
        self.git("add", ".agents/omx_artifacts.toml")
        self.git("commit", "-qm", "add dangling registry symlink")
        with patch.dict(os.environ, LOCAL_TRANSITION_ENV):
            errors = MEMORY_MODULE.check_registered_omx_artifacts(
                repo_root=self.repo, validator_path=SCRIPT
            )
        self.assertEqual(errors, ["OMX artifact registry must be a regular file"])

    def test_local_only_snapshot_fallback_is_explicit(self) -> None:
        bundle = self.bundle()
        self.stage_registry(bundle)
        output = StringIO()
        with (
            patch.dict(os.environ, LOCAL_TRANSITION_ENV),
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
            os.environ,
            {
                "GITHUB_ACTIONS": "true",
                "OMX_ARTIFACT_PREVIOUS_REF": "missing",
            },
        ):
            errors = MEMORY_MODULE.check_registered_omx_artifacts(
                repo_root=self.repo, validator_path=SCRIPT
            )
        self.assertRegex(errors[0], "hosted CI requires transition comparison")

    def test_explicit_invalid_local_ref_fails_closed(self) -> None:
        bundle = self.bundle()
        self.stage_registry(bundle)
        with patch.dict(
            os.environ,
            {
                "GITHUB_ACTIONS": "",
                "GITHUB_BASE_REF": "",
                "OMX_ARTIFACT_PREVIOUS_REF": "definitely-missing-ref",
            },
        ):
            errors = MEMORY_MODULE.check_registered_omx_artifacts(
                repo_root=self.repo, validator_path=SCRIPT
            )
        self.assertRegex(errors[0], "explicit OMX artifact transition ref is invalid")

    def test_hosted_ci_uses_explicit_previous_sha_and_rejects_self(self) -> None:
        original = self.bundle("task-current")
        self.commit_registry(original, "accepted base")
        previous = self.git("rev-parse", "HEAD").stdout.strip()
        target = self.repo / original["artifact"][0]["path"]
        target.write_text("mutated accepted evidence\n", encoding="utf-8")
        payload = target.read_bytes()
        original["artifact"][0]["sha256"] = hashlib.sha256(payload).hexdigest()
        original["artifact"][0]["bytes"] = len(payload)
        self.commit_registry(original, "invalid mutation")

        with patch.dict(
            os.environ,
            {
                "GITHUB_ACTIONS": "true",
                "OMX_ARTIFACT_PREVIOUS_REF": previous,
            },
        ):
            errors = MEMORY_MODULE.check_registered_omx_artifacts(
                repo_root=self.repo, validator_path=SCRIPT
            )
        self.assertRegex(errors[0], "accepted bundle mutated")

        with patch.dict(
            os.environ,
            {
                "GITHUB_ACTIONS": "true",
                "OMX_ARTIFACT_PREVIOUS_REF": self.git(
                    "rev-parse", "HEAD"
                ).stdout.strip(),
            },
        ):
            errors = MEMORY_MODULE.check_registered_omx_artifacts(
                repo_root=self.repo, validator_path=SCRIPT
            )
        self.assertRegex(errors[0], "cannot use HEAD itself")

    def test_private_runtime_paths_are_never_tracked(self) -> None:
        errors = MEMORY_MODULE.check_forbidden_tracked_paths(
            [
                ".agents/memory/transcripts/raw/messages.jsonl",
                ".agents/memory/transcripts",
                ".agents/memory/session-manifests/corpus.json",
                ".agents/memory/session-manifests",
                ".mempalace/palace.db",
                ".mempalace",
                ".palace/runtime.json",
                ".palace",
                ".agents/memory/history/2026/07/debrief.md",
            ]
        )
        self.assertEqual(len(errors), 8)
        self.assertTrue(all("must not be tracked" in error for error in errors))

    def test_force_tracked_private_root_symlinks_are_rejected(self) -> None:
        roots = (
            ".agents/memory/transcripts",
            ".agents/memory/session-manifests",
            ".mempalace",
            ".palace",
        )
        for root in roots:
            path = self.repo / root
            path.parent.mkdir(parents=True, exist_ok=True)
            path.symlink_to("private-runtime-target")
            self.git("add", "-f", root)
        tracked = self.git("ls-files").stdout.splitlines()
        errors = MEMORY_MODULE.check_forbidden_tracked_paths(tracked)
        self.assertEqual(len(errors), len(roots))

    def test_workflow_runs_lifecycle_checks_with_full_history(self) -> None:
        workflow = (Path(__file__).parents[2] / ".github/workflows/ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertRegex(
            workflow,
            r"uses: actions/checkout@v4\s+with:\s+fetch-depth: 0",
        )
        self.assertIn(
            "ref: ${{ github.event.pull_request.head.sha || github.sha }}", workflow
        )
        trigger_block = workflow.split("\npermissions:", maxsplit=1)[0]
        self.assertRegex(
            trigger_block,
            r"(?ms)^on:\s*\n  pull_request:\s*\n  push:\s*\n    branches:\s*\n"
            r"      - main\s*\n  workflow_dispatch:",
        )
        self.assertNotRegex(trigger_block, r"(?m)^\s+(?:paths|paths-ignore):")
        self.assertIn("python scripts/tests/test_validate_omx_artifacts.py", workflow)
        self.assertIn("OMX_ARTIFACT_PREVIOUS_REF=${previous_ref}", workflow)
        self.assertIn("github.event.pull_request.base.sha", workflow)
        self.assertIn("github.event.before", workflow)
        self.assertIn('git merge-base HEAD "${PR_BASE_SHA}"', workflow)
        self.assertIn(
            'echo "OMX_ARTIFACT_PREVIOUS_REF=${previous_ref}" >> "${GITHUB_ENV}"',
            workflow,
        )
        self.assertNotRegex(
            workflow, r"OMX_ARTIFACT_PREVIOUS_REF:\s*\$\{\{[^\n]+base\.sha"
        )

    def test_repository_successor_and_loc_manifest_are_reproducible(self) -> None:
        registry_path = REPO_ROOT / ".agents/omx_artifacts.toml"
        registry = MODULE.load_registry(registry_path)
        MODULE.validate_registry(REPO_ROOT, registry_path)
        current = next(
            item for item in registry["bundle"] if item["status"] == "current"
        )
        archived = next(
            item
            for item in registry["bundle"]
            if item["id"] == current["predecessor_bundle_id"]
        )
        self.assertEqual(current["predecessor_bundle_id"], archived["id"])
        self.assertEqual(
            current["predecessor_bundle_sha256"],
            MODULE.bundle_content_sha256(archived),
        )
        self.assertEqual(
            current["predecessor_chain_sha256"],
            MODULE.bundle_chain_sha256(
                archived["id"], {item["id"]: item for item in registry["bundle"]}
            ),
        )

        inventory_path = REPO_ROOT / next(
            item["path"]
            for item in current["artifact"]
            if item["role"] == "path-inventory"
        )
        with inventory_path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            path_fields = reader.fieldnames
            inventory = list(reader)
        history_base = "b8166fc8ab60c41d0f8a6eecfef8e4a2bf3b161c"
        history_head = "5bc48d461eb6679a28d45fc0f2bf7fc6a1222121"
        history_range = f"{history_base}..{history_head}"
        history_paths = subprocess.run(
            [
                "git",
                "log",
                "--first-parent",
                "--format=",
                "--name-only",
                history_range,
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        expected_history_paths = sorted({path for path in history_paths if path})
        net_paths = set(
            subprocess.run(
                ["git", "diff", "--name-only", history_range],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.splitlines()
        )
        allowed_dispositions = {
            "retain-as-is",
            "reimplement-minimally",
            "replace-with-upstream",
            "prune-redundant",
            "transient-or-reverted",
            "defer-with-owner",
        }
        allowed_states = {"final-net", "transient-or-reverted"}
        allowed_target_prs = {"PR1", "PR2", "PR3", "PR4", "PR5"}
        self.assertEqual(
            path_fields,
            [
                "source",
                "type",
                "final_state",
                "target_pr",
                "disposition",
                "owner",
                "reason",
                "verification",
            ],
        )
        self.assertEqual(len(inventory), 391)
        self.assertEqual([row["source"] for row in inventory], expected_history_paths)
        self.assertEqual(len({row["source"] for row in inventory}), len(inventory))
        self.assertEqual(len(net_paths), 366)
        self.assertEqual(
            {row["source"] for row in inventory if row["final_state"] == "final-net"},
            net_paths,
        )
        self.assertEqual(
            {row["disposition"] for row in inventory} - allowed_dispositions,
            set(),
        )
        for row in inventory:
            self.assertEqual(row["type"], "path")
            self.assertIn(row["final_state"], allowed_states)
            self.assertEqual(
                row["final_state"],
                "final-net" if row["source"] in net_paths else "transient-or-reverted",
            )
            self.assertIn(row["target_pr"], allowed_target_prs)
            self.assertTrue(all(row[field].strip() for field in row))

        commit_inventory_path = REPO_ROOT / next(
            item["path"]
            for item in current["artifact"]
            if item["role"] == "commit-inventory"
        )
        with commit_inventory_path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            commit_fields = reader.fieldnames
            commit_inventory = list(reader)
        expected_commits = subprocess.run(
            ["git", "rev-list", "--first-parent", "--reverse", history_range],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        expected_subjects = [
            subprocess.run(
                ["git", "show", "-s", "--format=%s", commit],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.rstrip("\n")
            for commit in expected_commits
        ]
        self.assertEqual(
            commit_fields,
            [
                "source",
                "type",
                "subject",
                "final_state",
                "target_pr",
                "disposition",
                "owner",
                "reason",
                "verification",
            ],
        )
        self.assertEqual(len(commit_inventory), 130)
        self.assertEqual([row["source"] for row in commit_inventory], expected_commits)
        self.assertEqual(
            [row["subject"] for row in commit_inventory], expected_subjects
        )
        self.assertEqual(
            len({row["source"] for row in commit_inventory}), len(commit_inventory)
        )
        for row in commit_inventory:
            self.assertEqual(row["type"], "commit")
            self.assertIn(row["final_state"], allowed_states)
            self.assertIn(row["target_pr"], allowed_target_prs)
            self.assertIn(row["disposition"], allowed_dispositions)
            self.assertTrue(all(row[field].strip() for field in row))

        manifest_item = next(
            item for item in current["artifact"] if item["role"] == "loc-manifest"
        )
        manifest = json.loads((REPO_ROOT / manifest_item["path"]).read_text())
        baseline = manifest["baseline_commit"]
        tracked = self.git_at(REPO_ROOT, "ls-tree", "-r", "--name-only", baseline)
        selection = manifest["selection"]
        active = sorted(
            path
            for path in tracked
            if self.matches(path, selection["active_include"])
            and not self.matches(path, selection["active_exclude"])
        )
        selected = {path: self.category_for(path, selection) for path in active}
        for rule in selection["supplemental_rules"]:
            for path in tracked:
                if any(path.startswith(prefix) for prefix in rule["prefix_any"]):
                    selected.setdefault(path, rule["category"])

        expected = []
        for path, category in sorted(
            selected.items(), key=lambda item: (item[1], item[0])
        ):
            payload = subprocess.run(
                ["git", "show", f"{baseline}:{path}"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
            ).stdout
            expected.append(
                {
                    "category": category,
                    "path": path,
                    "physical_lines": len(payload.splitlines()),
                }
            )
        self.assertEqual(manifest["rows"], expected)
        self.assertEqual(manifest["summary"], self.loc_summary(expected, active))

    @staticmethod
    def git_at(repo: Path, *args: str) -> list[str]:
        return subprocess.run(
            ["git", *args], cwd=repo, check=True, capture_output=True, text=True
        ).stdout.splitlines()

    @staticmethod
    def matches(path: str, patterns: list[str]) -> bool:
        return any(fnmatchcase(path, pattern) for pattern in patterns)

    @staticmethod
    def category_for(path: str, selection: dict[str, Any]) -> str:
        for rule in selection["category_rules"]:
            if rule.get("default"):
                return str(rule["category"])
            if any(path.startswith(prefix) for prefix in rule.get("prefix_any", [])):
                return str(rule["category"])
            if any(value in path for value in rule.get("contains_any", [])):
                return str(rule["category"])
        raise AssertionError(f"no category rule for {path}")

    @staticmethod
    def loc_summary(rows: list[dict[str, Any]], active: list[str]) -> dict[str, Any]:
        categories: dict[str, Any] = {}
        for category in ("generated", "production", "test", "upstream"):
            selected = [row for row in rows if row["category"] == category]
            categories[category] = {
                "file_count": len(selected),
                "physical_lines": sum(row["physical_lines"] for row in selected),
                "paths_sha256": hashlib.sha256(
                    "".join(f"{row['path']}\n" for row in selected).encode()
                ).hexdigest(),
                "path_lines_sha256": hashlib.sha256(
                    "".join(
                        f"{row['path']}\t{row['physical_lines']}\n" for row in selected
                    ).encode()
                ).hexdigest(),
            }
        active_set = set(active)
        return {
            "active_scaffold": {
                "file_count": len(active),
                "physical_lines": sum(
                    row["physical_lines"] for row in rows if row["path"] in active_set
                ),
            },
            "categories": categories,
        }


if __name__ == "__main__":
    unittest.main()
