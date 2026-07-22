#!/usr/bin/env python3
"""Promote and validate immutable OMX decision bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_REL = Path(".agents/omx_artifacts.toml")
REGISTRY_PATH = REPO_ROOT / REGISTRY_REL
SCHEMA_VERSION = 2
VALID_TRANSITIONS = {
    ("draft", "current"),
    ("draft", "rejected"),
    ("current", "superseded"),
}
CURRENT_REQUIRED_ROLES = (
    "context",
    "test_spec",
    "plan",
    "architect_review",
    "critic_review",
    "handoff",
)
BUNDLE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*--[0-9a-f]{16}$")
TASK_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CURRENT_PREFIXES = (".omx/context/", ".omx/specs/", ".omx/plans/")
ARCHIVE_PREFIX = ".omx/archive/accepted-bundles"
LEGACY_PREDECESSOR_ID = (
    "aria-nbv-agent-scaffold-simplification--c2c9c9381e40fd2f"
)
BUNDLE_KEYS = {
    "current": {
        "id",
        "task",
        "handoff_sha256",
        "status",
        "classification",
        "source_commit",
        "acceptance",
        "review_order",
        "artifacts",
    },
    "superseded": {
        "id",
        "task",
        "handoff_sha256",
        "status",
        "classification",
        "source_commit",
        "acceptance",
        "review_order",
        "superseded_by",
        "artifacts",
    },
}
DRAFT_BUNDLE_KEYS = {
    "task",
    "handoff_sha256",
    "status",
    "classification",
    "source_commit",
    "review_order",
    "artifacts",
}
ARTIFACT_KEYS = {"role", "path", "native_path", "source_commit", "sha256", "bytes"}
TOMBSTONE_KEYS = {
    "original_path",
    "source_commit",
    "blob_hash",
    "classification",
    "reason",
}
PLACEHOLDER_RE = re.compile(
    r"(?i)(?:<[^>]+>|\$\{?[A-Z][A-Z0-9_]*\}?|\[?REDACTED\]?|"
    r"CHANGEME|REPLACE_ME|EXAMPLE\.INVALID|X{3,}|\*{3,})"
)
REDACTION_PROBES = (
    ("private key", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("bearer credential", re.compile(r"(?i)\bBearer\s+[^\s`]+")),
    (
        "credential assignment",
        re.compile(
            r"(?i)\b(?:[A-Z0-9_]*(?:API|ACCESS|AUTH|PRIVATE)?[_-]?KEY|"
            r"[A-Z0-9_]*TOKEN|PASSWORD|PASSWD|SECRET|CREDENTIALS?)\b\s*[:=]\s*[^\s,;]+"
        ),
    ),
    (
        "machine-local path",
        re.compile(
            r"(?:^|[\s`'(])(?:/home/|/Users/|/tmp(?:/|\b)|/var/(?:tmp|cache)(?:/|\b)|"
            r"[A-Za-z]:\\Users\\|(?:^|/)\.cache/)"
        ),
    ),
    (
        "runtime identifier",
        re.compile(
            r"(?i)\b(?:tmux_pane|pane_id|session_id|runtime_id|run_id)\b\s*[:=]\s*[^\s,;]+"
        ),
    ),
)


def _no_fault(_phase: str) -> None:
    return None


_FAULT_HOOK: Callable[[str], None] = _no_fault


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def valid_transition(old: str, new: str) -> bool:
    return (old, new) in VALID_TRANSITIONS


def _bytes_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=root, check=False, capture_output=True, text=True
    )


def _exact_keys(value: Any, expected: set[str], label: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label} must be a table/object"]
    actual = set(value)
    return (
        []
        if actual == expected
        else [f"{label} keys must be exactly {sorted(expected)}; got {sorted(actual)}"]
    )


def _is_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _is_bool(value: Any) -> bool:
    return type(value) is bool


def canonical_bundle_id(task: str, handoff_sha256: str) -> str:
    return f"{task}--{handoff_sha256[:16]}"


def _canonical_path(bundle_id: str, status: str, native_path: str) -> str:
    if status == "current":
        return native_path
    relative = PurePosixPath(native_path).relative_to(".omx")
    return f"{ARCHIVE_PREFIX}/{bundle_id}/{relative.as_posix()}"


def _safe_relative(root: Path, value: str) -> tuple[Path | None, str | None]:
    pure = PurePosixPath(value)
    prefix = PurePosixPath(".omx")
    if (
        pure.is_absolute()
        or ".." in pure.parts
        or pure.parts[: len(prefix.parts)] != prefix.parts
    ):
        return None, f"OMX path escapes required root: {value}"
    resolved = (root / pure).resolve()
    required = (root / prefix).resolve()
    if required != resolved and required not in resolved.parents:
        return None, f"OMX path escapes required root: {value}"
    return resolved, None


def _commit_error(root: Path, commit: str) -> str | None:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        return f"invalid source commit: {commit!r}"
    if _git(root, "cat-file", "-e", f"{commit}^{{commit}}").returncode:
        return f"source commit does not exist: {commit}"
    if _git(root, "merge-base", "--is-ancestor", commit, "HEAD").returncode:
        return f"source commit is not an ancestor of HEAD: {commit}"
    return None


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def _redaction_errors(path: str, text: str) -> list[str]:
    errors: list[str] = []
    for label, pattern in REDACTION_PROBES:
        for match in pattern.finditer(text):
            probe = match.group(0)
            if PLACEHOLDER_RE.search(probe):
                continue
            errors.append(f"{path}: contains {label}: {probe[:48]!r}")
    return errors


def _validate_artifact_shape(
    artifact: Any, label: str, source_commit: str
) -> list[str]:
    errors = _exact_keys(artifact, ARTIFACT_KEYS, label)
    if errors:
        return errors
    assert isinstance(artifact, dict)
    for key in ("role", "path", "native_path", "source_commit", "sha256"):
        if not _is_str(artifact[key]):
            errors.append(f"{label}.{key} must be a non-empty string")
    if artifact.get("source_commit") != source_commit:
        errors.append(f"{label}.source_commit differs from bundle")
    if not re.fullmatch(r"[0-9a-f]{64}", str(artifact.get("sha256", ""))):
        errors.append(f"{label}.sha256 must be lowercase SHA-256")
    if not isinstance(artifact.get("bytes"), int) or artifact.get("bytes", -1) < 0:
        errors.append(f"{label}.bytes must be a non-negative integer")
    return errors


def _validate_handoff_data(
    handoff: Any,
    *,
    task: str,
    source_commit: str,
    artifacts: dict[str, dict[str, Any]],
) -> list[str]:
    if not isinstance(handoff, dict):
        return ["handoff must be an object"]
    errors: list[str] = []
    if handoff.get("task_slug") not in {None, task}:
        errors.append("handoff task does not match bundle")
    if handoff.get("status") != "approved":
        errors.append("handoff status must be approved")
    gate = handoff.get("ralplan_consensus_gate", handoff.get("consensus_gate", {}))
    if not isinstance(gate, dict) or gate.get("complete") is not True:
        errors.append("handoff consensus gate is incomplete")

    def check_link(item: Any, role: str, label: str) -> None:
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            return
        registered = artifacts.get(role, {})
        if item.get("sha256") != registered.get("sha256"):
            errors.append(f"{label} hash differs from registered artifact")
        if item.get("path") != registered.get("native_path"):
            errors.append(f"{label} path differs from registered native path")

    if handoff.get("schema_version") == 2:
        planning = handoff.get("planning_artifacts", {})
        check_link(planning.get("context"), "context", "handoff context")
        check_link(planning.get("plan"), "plan", "handoff plan")
        check_link(planning.get("test_spec"), "test_spec", "handoff test spec")
        architect = handoff.get("ralplan_architect_review", {})
        critic = handoff.get("ralplan_critic_review", {})
        check_link(architect, "architect_review", "handoff Architect review")
        check_link(critic, "critic_review", "handoff Critic review")
        if architect.get("verdict") != "APPROVE" or architect.get("approved") is not True:
            errors.append("handoff Architect review is not APPROVE")
        if critic.get("verdict") != "APPROVE" or critic.get("approved") is not True:
            errors.append("handoff Critic review is not APPROVE")
        plan_hash = artifacts.get("plan", {}).get("sha256")
        spec_hash = artifacts.get("test_spec", {}).get("sha256")
        for label, review in (("Architect", architect), ("Critic", critic)):
            if review.get("reviewed_plan_sha256") != plan_hash:
                errors.append(f"handoff {label} plan hash differs")
            if review.get("reviewed_test_spec_sha256") != spec_hash:
                errors.append(f"handoff {label} test-spec hash differs")
        if critic.get("reviewed_architect_sha256") != artifacts.get(
            "architect_review", {}
        ).get("sha256"):
            errors.append("handoff Critic did not review the registered Architect review")
    elif handoff.get("schema_version") == 1:
        embedded = handoff.get("planning_artifacts", {}).get("artifacts", [])
        expected = {
            item.get("native_path"): item.get("sha256")
            for item in artifacts.values()
            if item.get("role") != "handoff"
        }
        observed = {
            item.get("path"): item.get("sha256")
            for item in embedded
            if isinstance(item, dict)
        }
        if observed != expected:
            errors.append("predecessor handoff embedded artifact manifest differs")
        if handoff.get("plan_sha256") != artifacts.get("plan", {}).get("sha256"):
            errors.append("predecessor handoff plan hash differs")
    else:
        errors.append("handoff schema_version must be 1 or 2")
    return errors


def visible_omx_paths(root: Path) -> tuple[set[str], list[str]]:
    result = _git(
        root, "ls-files", "--cached", "--others", "--exclude-standard", "--", ".omx"
    )
    if result.returncode:
        return set(), [f"git ls-files failed: {result.stderr.strip()}"]
    return {
        line for line in result.stdout.splitlines() if line and (root / line).is_file()
    }, []


def _validate_registry_shape(registry: Any) -> list[str]:
    errors = _exact_keys(
        registry, {"schema_version", "bundles", "tombstones"}, "registry"
    )
    if errors:
        return errors
    assert isinstance(registry, dict)
    if registry["schema_version"] != SCHEMA_VERSION:
        errors.append(f"registry.schema_version must be integer {SCHEMA_VERSION}")
    if not isinstance(registry["bundles"], list):
        errors.append("registry.bundles must be an array")
    if not isinstance(registry["tombstones"], list):
        errors.append("registry.tombstones must be an array")
    return errors


def validate_registry(
    registry: dict[str, Any], root: Path = REPO_ROOT, *, check_git: bool = True
) -> list[str]:
    errors = _validate_registry_shape(registry)
    if errors:
        return errors
    bundles = registry["bundles"]
    bundle_ids: set[str] = set()
    current_tasks: set[str] = set()
    registered_paths: set[str] = set()
    by_id: dict[str, dict[str, Any]] = {}
    for offset, bundle in enumerate(bundles):
        status = bundle.get("status") if isinstance(bundle, dict) else None
        expected_keys = BUNDLE_KEYS.get(status, set())
        errors.extend(
            _exact_keys(bundle, expected_keys, f"bundles[{offset}]")
            if expected_keys
            else [f"bundles[{offset}].status is invalid"]
        )
        if not isinstance(bundle, dict) or not expected_keys:
            continue
        bundle_id = str(bundle["id"])
        task = str(bundle["task"])
        handoff_hash = str(bundle["handoff_sha256"])
        source_commit = str(bundle["source_commit"])
        if not TASK_RE.fullmatch(task):
            errors.append(f"bundle {bundle_id}: task slug is invalid")
        if not BUNDLE_ID_RE.fullmatch(bundle_id):
            errors.append(f"bundle id is not canonical: {bundle_id!r}")
        if not re.fullmatch(r"[0-9a-f]{64}", handoff_hash):
            errors.append(f"bundle {bundle_id}: handoff_sha256 is invalid")
        elif bundle_id != canonical_bundle_id(task, handoff_hash):
            errors.append(f"bundle {bundle_id}: id does not derive from handoff SHA-256")
        if bundle_id in bundle_ids:
            errors.append(f"duplicate bundle id: {bundle_id}")
        bundle_ids.add(bundle_id)
        by_id[bundle_id] = bundle
        if bundle.get("acceptance") != "explicit-user-acceptance":
            errors.append(f"bundle {bundle_id}: missing explicit user acceptance")
        if bundle.get("review_order") != ["architect", "critic"]:
            errors.append(f"bundle {bundle_id}: review order must be Architect then Critic")
        if commit_error := _commit_error(root, source_commit):
            errors.append(f"bundle {bundle_id}: {commit_error}")
        artifacts = bundle.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            errors.append(f"bundle {bundle_id}: artifacts must be a non-empty array")
            continue
        role_map: dict[str, dict[str, Any]] = {}
        native_paths: set[str] = set()
        for index, artifact in enumerate(artifacts):
            errors.extend(
                _validate_artifact_shape(
                    artifact, f"bundle {bundle_id}.artifacts[{index}]", source_commit
                )
            )
            if not isinstance(artifact, dict):
                continue
            role = str(artifact.get("role", ""))
            native_path = str(artifact.get("native_path", ""))
            path = str(artifact.get("path", ""))
            if role in role_map:
                errors.append(f"bundle {bundle_id}: duplicate role {role}")
            role_map[role] = artifact
            if native_path in native_paths:
                errors.append(f"bundle {bundle_id}: duplicate native path {native_path}")
            native_paths.add(native_path)
            if not native_path.startswith(CURRENT_PREFIXES):
                errors.append(f"bundle {bundle_id}: invalid native role path {native_path}")
            try:
                expected_path = _canonical_path(bundle_id, status, native_path)
            except (ValueError, TypeError):
                expected_path = ""
            if path != expected_path:
                errors.append(f"bundle {bundle_id}: invalid {status} placement for {role}")
            resolved, path_error = _safe_relative(root, path)
            if path_error:
                errors.append(f"bundle {bundle_id}: {path_error}")
                continue
            registered_paths.add(path)
            if resolved is None or not resolved.is_file():
                errors.append(f"bundle {bundle_id}: missing artifact {path}")
                continue
            content = resolved.read_bytes()
            if len(content) != artifact.get("bytes"):
                errors.append(f"bundle {bundle_id}: byte count mismatch: {path}")
            if _bytes_sha256(content) != artifact.get("sha256"):
                errors.append(f"bundle {bundle_id}: immutable hash mismatch: {path}")
            try:
                text = content.decode("utf-8")
                if bundle_id != LEGACY_PREDECESSOR_ID:
                    errors.extend(_redaction_errors(path, text))
            except UnicodeDecodeError:
                errors.append(f"bundle {bundle_id}: artifact is not UTF-8 text: {path}")
        if "handoff" not in role_map:
            errors.append(f"bundle {bundle_id}: handoff role is required")
        elif role_map["handoff"].get("sha256") != handoff_hash:
            errors.append(f"bundle {bundle_id}: handoff hash differs from bundle identity")
        if status == "current":
            if task in current_tasks:
                errors.append(f"duplicate current task: {task}")
            current_tasks.add(task)
            if set(role_map) != set(CURRENT_REQUIRED_ROLES):
                errors.append(
                    f"bundle {bundle_id}: current roles must be exactly {list(CURRENT_REQUIRED_ROLES)}"
                )
        handoff_artifact = role_map.get("handoff", {})
        handoff_path = root / str(handoff_artifact.get("path", ""))
        if handoff_path.is_file():
            try:
                handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"bundle {bundle_id}: invalid handoff JSON: {exc}")
            else:
                errors.extend(
                    _validate_handoff_data(
                        handoff, task=task, source_commit=source_commit, artifacts=role_map
                    )
                )

    for bundle in bundles:
        if not isinstance(bundle, dict) or bundle.get("status") != "superseded":
            continue
        successor = by_id.get(str(bundle.get("superseded_by", "")))
        if successor is None or successor.get("status") != "current":
            errors.append(f"bundle {bundle.get('id')}: successor is not current")
        elif successor.get("task") == bundle.get("task"):
            pass
        elif bundle.get("id") == "aria-nbv-agent-scaffold-simplification--c2c9c9381e40fd2f" and successor.get("task") == "aria-nbv-agent-scaffold-refresh":
            pass
        else:
            errors.append(f"bundle {bundle.get('id')}: successor task differs")
    for bundle in bundles:
        seen: set[str] = set()
        cursor = bundle
        while isinstance(cursor, dict) and cursor.get("status") == "superseded":
            cursor_id = str(cursor.get("id"))
            if cursor_id in seen:
                errors.append(f"bundle {bundle.get('id')}: cyclic supersession")
                break
            seen.add(cursor_id)
            cursor = by_id.get(str(cursor.get("superseded_by")), {})

    tombstone_paths: set[str] = set()
    for offset, tombstone in enumerate(registry["tombstones"]):
        errors.extend(_exact_keys(tombstone, TOMBSTONE_KEYS, f"tombstones[{offset}]"))
        if not isinstance(tombstone, dict):
            continue
        original_path = str(tombstone.get("original_path", ""))
        if original_path in tombstone_paths:
            errors.append(f"duplicate legacy tombstone: {original_path}")
        tombstone_paths.add(original_path)
        if not re.fullmatch(r"[0-9a-f]{40}", str(tombstone.get("blob_hash", ""))):
            errors.append(f"tombstones[{offset}].blob_hash must be a Git SHA-1")
        if commit_error := _commit_error(root, str(tombstone.get("source_commit", ""))):
            errors.append(f"tombstone {original_path}: {commit_error}")
        else:
            blob = _git(root, "rev-parse", f"{tombstone['source_commit']}:{original_path}")
            if blob.returncode or blob.stdout.strip() != tombstone.get("blob_hash"):
                errors.append(f"tombstone {original_path}: source blob hash differs")

    if check_git:
        visible, git_errors = visible_omx_paths(root)
        errors.extend(git_errors)
        for path in sorted(visible - registered_paths):
            errors.append(f"unregistered tracked or unignored OMX artifact: {path}")
        for path in sorted(registered_paths - visible):
            errors.append(f"registered OMX artifact is not tracked or visible: {path}")
    return errors


def _immutable_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    value = {key: item for key, item in bundle.items() if key not in {"status", "superseded_by"}}
    value["artifacts"] = [
        {key: item for key, item in artifact.items() if key != "path"}
        for artifact in bundle.get("artifacts", [])
    ]
    return value


def validate_history(
    current: dict[str, Any], previous: dict[str, Any], label: str
) -> list[str]:
    errors: list[str] = []
    old_by_id = {item["id"]: item for item in previous.get("bundles", [])}
    new_by_id = {item["id"]: item for item in current.get("bundles", [])}
    for bundle_id, old in old_by_id.items():
        new = new_by_id.get(bundle_id)
        if new is None:
            errors.append(f"{label}: current/superseded bundle deleted: {bundle_id}")
            continue
        if _immutable_bundle(old) != _immutable_bundle(new):
            errors.append(f"{label}: bundle content/hash rewrite: {bundle_id}")
        if old["status"] == "superseded" and new["status"] != "superseded":
            errors.append(f"{label}: superseded bundle reactivated: {bundle_id}")
        if old["status"] == "current" and new["status"] not in {
            "current",
            "superseded",
        }:
            errors.append(f"{label}: invalid current transition: {bundle_id}")
        if old["status"] == "superseded" and old.get("superseded_by") != new.get(
            "superseded_by"
        ):
            errors.append(f"{label}: supersession tombstone rewritten: {bundle_id}")
    old_tombstones = {
        item["original_path"]: item for item in previous.get("tombstones", [])
    }
    new_tombstones = {
        item["original_path"]: item for item in current.get("tombstones", [])
    }
    for path, old in old_tombstones.items():
        if new_tombstones.get(path) != old:
            errors.append(f"{label}: legacy tombstone deleted or rewritten: {path}")
    return errors


def _registry_at(root: Path, ref: str) -> dict[str, Any] | None:
    result = _git(root, "show", f"{ref}:{REGISTRY_REL.as_posix()}")
    if result.returncode:
        return None
    try:
        return tomllib.loads(result.stdout)
    except tomllib.TOMLDecodeError:
        return None


def historical_registries(
    root: Path, baseline_ref: str | None = None
) -> list[tuple[str, dict[str, Any]]]:
    refs: list[str] = []
    history = _git(
        root,
        "log",
        "--format=%H",
        "HEAD",
        "--",
        REGISTRY_REL.as_posix(),
    )
    if history.returncode == 0:
        refs.extend(history.stdout.splitlines())
    if baseline_ref:
        reachable = _git(root, "merge-base", "--is-ancestor", baseline_ref, "HEAD")
        if reachable.returncode == 0:
            refs.append(baseline_ref)
    result: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for ref in refs:
        resolved = _git(root, "rev-parse", "--verify", ref)
        key = resolved.stdout.strip() if resolved.returncode == 0 else ref
        if key in seen:
            continue
        seen.add(key)
        if registry := _registry_at(root, ref):
            result.append((ref, registry))
    return result


def validate_payload_history(registry: dict[str, Any], root: Path) -> list[str]:
    """Reject any committed mutation after a bundle first appears in the registry."""
    errors: list[str] = []
    history = _git(root, "rev-list", "--reverse", "HEAD")
    if history.returncode:
        return [f"git rev-list failed: {history.stderr.strip()}"]
    seen: set[str] = set()
    expected = {bundle["id"]: bundle for bundle in registry.get("bundles", [])}
    for commit in history.stdout.splitlines():
        historical = _registry_at(root, commit)
        if historical is None:
            if seen:
                errors.append(f"{commit}: registry deleted after accepted bundles existed")
            continue
        historical_by_id = {item["id"]: item for item in historical.get("bundles", [])}
        for bundle_id, bundle in historical_by_id.items():
            if bundle_id not in expected:
                continue
            seen.add(bundle_id)
            expected_artifacts = {
                item["native_path"]: item for item in expected[bundle_id]["artifacts"]
            }
            for artifact in bundle.get("artifacts", []):
                stable = expected_artifacts.get(artifact.get("native_path"))
                if stable is None:
                    errors.append(f"{commit}: artifact membership drift: {bundle_id}")
                    continue
                blob = _git(root, "show", f"{commit}:{artifact.get('path', '')}")
                if blob.returncode or _bytes_sha256(blob.stdout.encode()) != stable["sha256"]:
                    errors.append(
                        f"{commit}: committed payload mutation or missing path: {artifact.get('path')}"
                    )
    return errors


def _toml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_registry(registry: dict[str, Any]) -> str:
    lines = [f"schema_version = {SCHEMA_VERSION}", ""]
    if not registry.get("bundles"):
        lines.extend(["bundles = []", ""])
    if not registry.get("tombstones"):
        lines.extend(["tombstones = []", ""])
    for bundle in registry.get("bundles", []):
        lines.append("[[bundles]]")
        for key in (
            "id",
            "task",
            "handoff_sha256",
            "status",
            "classification",
            "source_commit",
            "acceptance",
        ):
            lines.append(f"{key} = {_toml_quote(str(bundle[key]))}")
        if "superseded_by" in bundle:
            lines.append(f"superseded_by = {_toml_quote(str(bundle['superseded_by']))}")
        lines.append('review_order = ["architect", "critic"]')
        lines.append("")
        for artifact in bundle["artifacts"]:
            lines.append("[[bundles.artifacts]]")
            for key in ("role", "path", "native_path", "source_commit", "sha256"):
                lines.append(f"{key} = {_toml_quote(str(artifact[key]))}")
            lines.append(f"bytes = {int(artifact['bytes'])}")
            lines.append("")
    for tombstone in registry.get("tombstones", []):
        lines.append("[[tombstones]]")
        for key in (
            "original_path",
            "source_commit",
            "blob_hash",
            "classification",
            "reason",
        ):
            lines.append(f"{key} = {_toml_quote(str(tombstone[key]))}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _fsync_dir(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_dir(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _load_draft(
    manifest_path: Path, root: Path
) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        bundle = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"invalid promotion manifest: {exc}"]
    errors = _exact_keys(bundle, DRAFT_BUNDLE_KEYS, "draft bundle")
    if errors or not isinstance(bundle, dict):
        return None, errors
    if bundle["status"] != "draft" or not valid_transition("draft", "current"):
        errors.append("promotion manifest must describe a draft bundle")
    if not TASK_RE.fullmatch(str(bundle.get("task", ""))):
        errors.append("draft task slug is invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", str(bundle.get("handoff_sha256", ""))):
        errors.append("draft handoff_sha256 must be lowercase SHA-256")
    if bundle["review_order"] != ["architect", "critic"]:
        errors.append("draft review_order must be Architect then Critic")
    source_commit = str(bundle["source_commit"])
    if commit_error := _commit_error(root, source_commit):
        errors.append(commit_error)
    artifacts = bundle["artifacts"]
    if not isinstance(artifacts, list) or len(artifacts) != len(CURRENT_REQUIRED_ROLES):
        return None, [*errors, "draft must contain exactly six artifacts"]
    role_map: dict[str, dict[str, Any]] = {}
    for offset, artifact in enumerate(artifacts):
        errors.extend(
            _validate_artifact_shape(
                artifact, f"draft.artifacts[{offset}]", source_commit
            )
        )
        if not isinstance(artifact, dict):
            continue
        role = str(artifact.get("role", ""))
        if role in role_map:
            errors.append(f"duplicate draft role: {role}")
        role_map[role] = artifact
        source, path_error = _safe_relative(root, str(artifact.get("path", "")))
        if path_error or source is None or not source.is_file():
            errors.append(
                path_error or f"missing draft artifact: {artifact.get('path')}"
            )
            continue
        if sha256(source) != artifact.get("sha256"):
            errors.append(f"draft hash mismatch: {artifact.get('path')}")
        if source.stat().st_size != artifact.get("bytes"):
            errors.append(f"draft byte count mismatch: {artifact.get('path')}")
        native_path = str(artifact.get("native_path", ""))
        _, native_error = _safe_relative(root, native_path)
        if native_error or not native_path.startswith(CURRENT_PREFIXES):
            errors.append(native_error or f"invalid native role path: {native_path}")
        try:
            errors.extend(
                _redaction_errors(
                    str(artifact.get("path")), source.read_text(encoding="utf-8")
                )
            )
        except UnicodeDecodeError:
            errors.append(f"draft artifact is not UTF-8: {artifact.get('path')}")
    if set(role_map) != set(CURRENT_REQUIRED_ROLES):
        errors.append(
            f"draft roles must be exactly {list(CURRENT_REQUIRED_ROLES)}"
        )
    handoff_source = root / str(role_map.get("handoff", {}).get("path", ""))
    if handoff_source.is_file():
        try:
            handoff = json.loads(handoff_source.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid draft handoff JSON: {exc}")
        else:
            draft_links = {
                role: {**artifact, "native_path": artifact["path"]}
                for role, artifact in role_map.items()
            }
            errors.extend(
                _validate_handoff_data(
                    handoff,
                    task=str(bundle["task"]),
                    source_commit=source_commit,
                    artifacts=draft_links,
                )
            )
            if sha256(handoff_source) != bundle.get("handoff_sha256"):
                errors.append("draft handoff hash differs from manifest")
    return (bundle if not errors else None), errors


def _canonical_handoff(
    handoff: dict[str, Any], native_paths: dict[str, str], hashes: dict[str, str]
) -> bytes:
    value = json.loads(json.dumps(handoff))
    for role in ("context", "plan", "test_spec"):
        value["planning_artifacts"][role] = {
            "path": native_paths[role],
            "sha256": hashes[role],
        }
    for role, key in (
        ("architect_review", "ralplan_architect_review"),
        ("critic_review", "ralplan_critic_review"),
    ):
        value[key]["path"] = native_paths[role]
        value[key]["sha256"] = hashes[role]
        value[key]["reviewed_plan_sha256"] = hashes["plan"]
        value[key]["reviewed_test_spec_sha256"] = hashes["test_spec"]
    value["ralplan_critic_review"]["reviewed_architect_sha256"] = hashes[
        "architect_review"
    ]
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _current_bundle(
    bundle: dict[str, Any], acceptance: str, root: Path
) -> tuple[dict[str, Any], dict[str, bytes]]:
    source_by_role = {item["role"]: root / item["path"] for item in bundle["artifacts"]}
    native_paths = {item["role"]: item["native_path"] for item in bundle["artifacts"]}
    hashes = {
        role: sha256(source_by_role[role])
        for role in CURRENT_REQUIRED_ROLES
        if role != "handoff"
    }
    handoff = json.loads(source_by_role["handoff"].read_text(encoding="utf-8"))
    handoff_bytes = _canonical_handoff(handoff, native_paths, hashes)
    hashes["handoff"] = _bytes_sha256(handoff_bytes)
    bundle_id = canonical_bundle_id(str(bundle["task"]), hashes["handoff"])
    current = {
        "id": bundle_id,
        "task": bundle["task"],
        "handoff_sha256": hashes["handoff"],
        "status": "current",
        "classification": bundle["classification"],
        "source_commit": bundle["source_commit"],
        "acceptance": acceptance,
        "review_order": ["architect", "critic"],
        "artifacts": [
            {
                "role": role,
                "path": native_paths[role],
                "native_path": native_paths[role],
                "source_commit": bundle["source_commit"],
                "sha256": hashes[role],
                "bytes": len(handoff_bytes)
                if role == "handoff"
                else source_by_role[role].stat().st_size,
            }
            for role in CURRENT_REQUIRED_ROLES
        ],
    }
    content_by_role = {
        role: handoff_bytes
        if role == "handoff"
        else source_by_role[role].read_bytes()
        for role in CURRENT_REQUIRED_ROLES
    }
    return current, content_by_role


def promote(
    manifest_path: Path, acceptance: str, dry_run: bool, root: Path = REPO_ROOT
) -> int:
    if acceptance != "explicit-user-acceptance":
        print(
            "promotion requires --acceptance explicit-user-acceptance", file=sys.stderr
        )
        return 2
    bundle, errors = _load_draft(manifest_path, root)
    if errors or bundle is None:
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    registry_path = root / REGISTRY_REL
    registry = (
        load_registry(registry_path)
        if registry_path.exists()
        else {"schema_version": SCHEMA_VERSION, "bundles": [], "tombstones": []}
    )
    current, content_by_role = _current_bundle(bundle, acceptance, root)
    bundle_id = str(current["id"])
    if any(item.get("id") == bundle_id for item in registry["bundles"]):
        print(f"- duplicate bundle id: {bundle_id}", file=sys.stderr)
        return 1
    if any(
        item.get("status") == "current" and item.get("task") == bundle["task"]
        for item in registry["bundles"]
    ):
        print("- duplicate current task; use atomic supersession", file=sys.stderr)
        return 1
    candidate = json.loads(json.dumps(registry))
    candidate["bundles"].append(current)
    history_errors = [
        error
        for label, prior in historical_registries(root)
        for error in validate_history(candidate, prior, label)
    ]
    if history_errors:
        for error in history_errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    rendered = render_registry(candidate)
    if dry_run:
        sys.stdout.write(rendered)
        return 0
    targets = {
        item["role"]: root / item["native_path"] for item in current["artifacts"]
    }
    collisions = [path for path in targets.values() if path.exists()]
    if collisions:
        print(f"- declared native path already exists: {collisions[0]}", file=sys.stderr)
        return 1
    before = registry_path.read_bytes() if registry_path.exists() else b""
    registry_existed = registry_path.exists()
    created: list[Path] = []
    try:
        for role in CURRENT_REQUIRED_ROLES:
            target = targets[role]
            _atomic_write_bytes(target, content_by_role[role])
            created.append(target)
        _FAULT_HOOK("promote_after_payload")
        errors = validate_registry(candidate, root, check_git=False)
        if errors:
            raise ValueError("\n".join(errors))
        _atomic_write_bytes(registry_path, rendered.encode())
        _FAULT_HOOK("promote_after_registry")
    except BaseException as exc:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        if registry_existed:
            _atomic_write_bytes(registry_path, before)
        else:
            registry_path.unlink(missing_ok=True)
        print(f"promotion rolled back: {exc}", file=sys.stderr)
        return 1
    return 0


def supersede(
    bundle_id: str,
    successor_manifest: Path,
    acceptance: str,
    dry_run: bool,
    root: Path = REPO_ROOT,
) -> int:
    if acceptance != "explicit-user-acceptance":
        print(
            "supersession requires --acceptance explicit-user-acceptance",
            file=sys.stderr,
        )
        return 2
    successor_draft, errors = _load_draft(successor_manifest, root)
    if errors or successor_draft is None:
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    registry_path = root / REGISTRY_REL
    registry = load_registry(registry_path)
    bundles = registry["bundles"]
    bundle = next((item for item in bundles if item.get("id") == bundle_id), None)
    if bundle is None:
        print("supersession requires a current predecessor bundle", file=sys.stderr)
        return 2
    if bundle.get("status") != "current" or not valid_transition(
        "current", "superseded"
    ):
        print("only current bundles may be superseded", file=sys.stderr)
        return 2
    successor, successor_content = _current_bundle(successor_draft, acceptance, root)
    successor_id = str(successor["id"])
    if any(item.get("id") == successor_id for item in bundles):
        print(f"- duplicate bundle id: {successor_id}", file=sys.stderr)
        return 1
    if successor_draft.get("task") != bundle.get("task"):
        print("- successor task must match predecessor task", file=sys.stderr)
        return 1
    candidate = json.loads(json.dumps(registry))
    candidate_bundle = next(
        item for item in candidate["bundles"] if item["id"] == bundle_id
    )
    candidate_bundle["status"] = "superseded"
    candidate_bundle["superseded_by"] = successor_id
    for artifact in candidate_bundle["artifacts"]:
        artifact["path"] = _canonical_path(
            bundle_id, "superseded", artifact["native_path"]
        )
    candidate["bundles"].append(successor)
    history_errors = [
        error
        for label, prior in historical_registries(root)
        for error in validate_history(candidate, prior, label)
    ]
    if history_errors:
        for error in history_errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    rendered = render_registry(candidate)
    if dry_run:
        sys.stdout.write(rendered)
        return 0
    predecessor_paths = {
        item["role"]: root / item["native_path"] for item in bundle["artifacts"]
    }
    if missing := [path for path in predecessor_paths.values() if not path.is_file()]:
        print(f"- current predecessor artifact missing: {missing[0]}", file=sys.stderr)
        return 1
    archive_paths = {
        item["role"]: root
        / _canonical_path(bundle_id, "superseded", item["native_path"])
        for item in bundle["artifacts"]
    }
    if collisions := [path for path in archive_paths.values() if path.exists()]:
        print(f"- predecessor archive path already exists: {collisions[0]}", file=sys.stderr)
        return 1
    successor_paths = {
        item["role"]: root / item["native_path"] for item in successor["artifacts"]
    }
    predecessor_path_set = set(predecessor_paths.values())
    if collisions := [
        path
        for path in successor_paths.values()
        if path.exists() and path not in predecessor_path_set
    ]:
        print(f"- successor native path already exists: {collisions[0]}", file=sys.stderr)
        return 1
    before = registry_path.read_bytes()
    predecessor_content = {
        role: path.read_bytes() for role, path in predecessor_paths.items()
    }
    created_archive: list[Path] = []
    created_successor: list[Path] = []
    try:
        for path in predecessor_paths.values():
            path.unlink()
        for role, path in archive_paths.items():
            _atomic_write_bytes(path, predecessor_content[role])
            created_archive.append(path)
        _FAULT_HOOK("supersede_after_archive")
        for role, path in successor_paths.items():
            _atomic_write_bytes(path, successor_content[role])
            created_successor.append(path)
        _FAULT_HOOK("supersede_after_successor")
        errors = validate_registry(candidate, root, check_git=False)
        if errors:
            raise ValueError("\n".join(errors))
        _atomic_write_bytes(registry_path, rendered.encode())
        _FAULT_HOOK("supersede_after_registry")
    except BaseException as exc:
        for path in reversed(created_successor):
            path.unlink(missing_ok=True)
        for path in reversed(created_archive):
            path.unlink(missing_ok=True)
        archive_bundle_root = root / ARCHIVE_PREFIX / bundle_id
        if archive_bundle_root.exists():
            shutil.rmtree(archive_bundle_root)
        for role, path in predecessor_paths.items():
            _atomic_write_bytes(path, predecessor_content[role])
        _atomic_write_bytes(registry_path, before)
        print(f"supersession rolled back: {exc}", file=sys.stderr)
        return 1
    return 0


def check(root: Path = REPO_ROOT, baseline_ref: str | None = None) -> list[str]:
    registry = load_registry(root / REGISTRY_REL)
    errors = validate_registry(registry, root)
    for label, previous in historical_registries(root, baseline_ref):
        errors.extend(validate_history(registry, previous, label))
    errors.extend(validate_payload_history(registry, root))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--promote-manifest", type=Path)
    actions.add_argument(
        "--supersede", nargs=2, metavar=("BUNDLE", "SUCCESSOR_MANIFEST")
    )
    parser.add_argument("--acceptance", default="")
    parser.add_argument("--baseline-ref")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    if args.promote_manifest:
        return promote(
            args.promote_manifest, args.acceptance, args.dry_run, args.repo_root
        )
    if args.supersede:
        return supersede(
            args.supersede[0],
            Path(args.supersede[1]),
            args.acceptance,
            args.dry_run,
            args.repo_root,
        )
    try:
        errors = check(args.repo_root, args.baseline_ref)
    except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        print(f"OMX artifact registry is unreadable: {exc}", file=sys.stderr)
        return 1
    if errors:
        print("OMX artifact validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    registry = load_registry(args.repo_root / REGISTRY_REL)
    print(
        f"OMX artifact registry valid: {len(registry['bundles'])} bundle(s), {len(registry['tombstones'])} legacy tombstone(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
