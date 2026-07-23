#!/usr/bin/env python3
"""Promote and validate immutable OMX decision bundles."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
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
RECOVERY_GIT_PATH = "omx-bootstrap"
JOURNAL_SCHEMA_VERSION = 1
SEED_SCHEMA_VERSION = 1
SEED_MANIFEST = "seed-manifest.json"
OMX_PINNED_VERSION = "0.20.3"
OMX_PINNED_INTEGRITY = "sha512-7wlSTA1Nc9c31WX9w8THYPwlaleWV1dk/0WXqRgxpph34EI4oJM+Z4Egv04Nn8wN2SLI9K2LMfeOpNKI+06LGg=="
LEGACY_PREDECESSOR_ID = "aria-nbv-agent-scaffold-simplification--c2c9c9381e40fd2f"
LEGACY_BOOTSTRAP_RECORD_SHA256 = (
    "54d4e7dfb5a63d1f3409082bd6e39b139f6118d4b087c71cc5cba6c95bd915b4"
)
LEGACY_REDACTION_ALLOWLIST = {
    ".omx/archive/accepted-bundles/"
    "aria-nbv-agent-scaffold-simplification--c2c9c9381e40fd2f/"
    "context/agent-scaffold-consensus-20260714T081220Z.md": (
        "5e73810eb1bb2645ee6169b98b7360926e6a9b32ff5c5c028defeccc80db95da"
    ),
}
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
    lexical = root / pure
    cursor = root
    for part in pure.parts:
        cursor /= part
        if cursor.is_symlink():
            return None, f"OMX path contains a symlink: {value}"
    resolved = lexical.resolve()
    required = (root / prefix).resolve()
    if required != resolved and required not in resolved.parents:
        return None, f"OMX path escapes required root: {value}"
    return resolved, None


def _safe_repo_relative(root: Path, value: str) -> tuple[Path | None, str | None]:
    pure = PurePosixPath(value)
    if pure.is_absolute() or not pure.parts or ".." in pure.parts:
        return None, f"repository path escapes root: {value}"
    cursor = root
    for part in pure.parts:
        cursor /= part
        if cursor.is_symlink():
            return None, f"repository path contains a symlink: {value}"
    resolved = (root / pure).resolve()
    required = root.resolve()
    if required != resolved and required not in resolved.parents:
        return None, f"repository path escapes root: {value}"
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


def _legacy_redaction_allowed(path: str, digest: str) -> bool:
    return LEGACY_REDACTION_ALLOWLIST.get(path) == digest


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
        if (
            architect.get("verdict") != "APPROVE"
            or architect.get("approved") is not True
        ):
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
            errors.append(
                "handoff Critic did not review the registered Architect review"
            )
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
            errors.append(
                f"bundle {bundle_id}: id does not derive from handoff SHA-256"
            )
        if bundle_id in bundle_ids:
            errors.append(f"duplicate bundle id: {bundle_id}")
        bundle_ids.add(bundle_id)
        by_id[bundle_id] = bundle
        if bundle.get("acceptance") != "explicit-user-acceptance":
            errors.append(f"bundle {bundle_id}: missing explicit user acceptance")
        if bundle.get("review_order") != ["architect", "critic"]:
            errors.append(
                f"bundle {bundle_id}: review order must be Architect then Critic"
            )
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
                errors.append(
                    f"bundle {bundle_id}: duplicate native path {native_path}"
                )
            native_paths.add(native_path)
            if not native_path.startswith(CURRENT_PREFIXES):
                errors.append(
                    f"bundle {bundle_id}: invalid native role path {native_path}"
                )
            try:
                expected_path = _canonical_path(bundle_id, status, native_path)
            except (ValueError, TypeError):
                expected_path = ""
            if path != expected_path:
                errors.append(
                    f"bundle {bundle_id}: invalid {status} placement for {role}"
                )
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
                redaction_errors = _redaction_errors(path, text)
                if redaction_errors and not _legacy_redaction_allowed(
                    path, str(artifact.get("sha256", ""))
                ):
                    errors.extend(redaction_errors)
            except UnicodeDecodeError:
                errors.append(f"bundle {bundle_id}: artifact is not UTF-8 text: {path}")
        if "handoff" not in role_map:
            errors.append(f"bundle {bundle_id}: handoff role is required")
        elif role_map["handoff"].get("sha256") != handoff_hash:
            errors.append(
                f"bundle {bundle_id}: handoff hash differs from bundle identity"
            )
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
                        handoff,
                        task=task,
                        source_commit=source_commit,
                        artifacts=role_map,
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
        elif (
            bundle.get("id")
            == "aria-nbv-agent-scaffold-simplification--c2c9c9381e40fd2f"
            and successor.get("task") == "aria-nbv-agent-scaffold-refresh"
        ):
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
            blob = _git(
                root, "rev-parse", f"{tombstone['source_commit']}:{original_path}"
            )
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
    value = {
        key: item
        for key, item in bundle.items()
        if key not in {"status", "superseded_by"}
    }
    value["artifacts"] = [
        {key: item for key, item in artifact.items() if key != "path"}
        for artifact in bundle.get("artifacts", [])
    ]
    return value


def _bundle_record_sha256(bundle: dict[str, Any]) -> str:
    encoded = json.dumps(
        bundle, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    return _bytes_sha256(encoded)


def _is_legacy_bootstrap_record(bundle: dict[str, Any]) -> bool:
    return (
        bundle.get("id") == LEGACY_PREDECESSOR_ID
        and bundle.get("status") == "superseded"
        and _bundle_record_sha256(bundle) == LEGACY_BOOTSTRAP_RECORD_SHA256
    )


def validate_history(
    current: dict[str, Any], previous: dict[str, Any], label: str
) -> list[str]:
    errors: list[str] = []
    old_by_id = {item["id"]: item for item in previous.get("bundles", [])}
    new_by_id = {item["id"]: item for item in current.get("bundles", [])}
    for bundle_id, new in new_by_id.items():
        if (
            bundle_id not in old_by_id
            and new.get("status") == "superseded"
            and not _is_legacy_bootstrap_record(new)
        ):
            errors.append(f"{label}: first-seen bundle must be current: {bundle_id}")
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
    history = _git(root, "rev-list", "--reverse", "--parents", "HEAD")
    if history.returncode:
        return [f"git rev-list failed: {history.stderr.strip()}"]
    expected = {bundle["id"]: bundle for bundle in registry.get("bundles", [])}
    registry_cache: dict[str, dict[str, Any] | None] = {}

    def registry_at(commit: str) -> dict[str, Any] | None:
        if commit not in registry_cache:
            registry_cache[commit] = _registry_at(root, commit)
        return registry_cache[commit]

    for row in history.stdout.splitlines():
        commit, *parents = row.split()
        historical = registry_at(commit)
        parent_registries = [
            parent_registry
            for parent in parents
            if (parent_registry := registry_at(parent)) is not None
        ]
        parent_bundle_ids = [
            {
                item["id"]
                for item in parent_registry.get("bundles", [])
                if isinstance(item, dict)
            }
            for parent_registry in parent_registries
        ]
        if historical is None:
            if any(bundle_ids & expected.keys() for bundle_ids in parent_bundle_ids):
                errors.append(
                    f"{commit}: registry deleted after accepted bundles existed"
                )
            continue
        historical_by_id = {item["id"]: item for item in historical.get("bundles", [])}
        for bundle_ids in parent_bundle_ids:
            for bundle_id in sorted(
                bundle_ids & expected.keys() - historical_by_id.keys()
            ):
                errors.append(f"{commit}: accepted bundle deleted: {bundle_id}")
        for bundle_id, bundle in historical_by_id.items():
            if bundle_id not in expected:
                continue
            first_seen = not any(
                bundle_id in bundle_ids for bundle_ids in parent_bundle_ids
            )
            if (
                first_seen
                and bundle.get("status") == "superseded"
                and not _is_legacy_bootstrap_record(bundle)
            ):
                errors.append(
                    f"{commit}: first-seen bundle must be current: {bundle_id}"
                )
            expected_artifacts = {
                item["native_path"]: item for item in expected[bundle_id]["artifacts"]
            }
            for artifact in bundle.get("artifacts", []):
                stable = expected_artifacts.get(artifact.get("native_path"))
                if stable is None:
                    errors.append(f"{commit}: artifact membership drift: {bundle_id}")
                    continue
                blob = _git(root, "show", f"{commit}:{artifact.get('path', '')}")
                if (
                    blob.returncode
                    or _bytes_sha256(blob.stdout.encode()) != stable["sha256"]
                ):
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


def _git_path(root: Path, name: str) -> Path:
    result = _git(root, "rev-parse", "--git-path", name)
    if result.returncode:
        raise ValueError(f"cannot resolve Git path {name}: {result.stderr.strip()}")
    path = Path(result.stdout.strip())
    return path if path.is_absolute() else root / path


def _recovery_root(root: Path) -> Path:
    return _git_path(root, RECOVERY_GIT_PATH)


def _index_path(root: Path) -> Path:
    return _git_path(root, "index")


def _remove_empty_parents(path: Path, root: Path) -> None:
    parent = path.parent
    boundary = root.resolve()
    while parent != boundary and boundary in parent.resolve().parents:
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def _load_journal(root: Path) -> tuple[Path, dict[str, Any]] | None:
    recovery = _recovery_root(root)
    journal_path = recovery / "journal.json"
    if not journal_path.exists():
        return None
    try:
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"recovery journal is unreadable: {exc}") from exc
    expected = {"schema_version", "worktree", "operation", "paths", "index"}
    errors = _exact_keys(journal, expected, "recovery journal")
    if errors or journal.get("schema_version") != JOURNAL_SCHEMA_VERSION:
        raise ValueError("invalid recovery journal: " + "; ".join(errors))
    if journal.get("worktree") != str(root.resolve()):
        raise ValueError("recovery journal belongs to another worktree")
    return recovery, journal


def _restore_backup(recovery: Path, entry: dict[str, Any], target: Path) -> None:
    if not entry.get("existed"):
        if target.exists() or target.is_symlink():
            if target.is_dir() and not target.is_symlink():
                raise ValueError(f"refusing to remove unexpected directory: {target}")
            target.unlink()
        return
    backup_name = entry.get("backup")
    expected = entry.get("sha256")
    if not isinstance(backup_name, str) or not isinstance(expected, str):
        raise ValueError(f"invalid backup entry for {target}")
    backup = recovery / "backups" / backup_name
    content = backup.read_bytes()
    if _bytes_sha256(content) != expected:
        raise ValueError(f"backup checksum mismatch for {target}")
    _atomic_write_bytes(target, content)


def _validate_backup_entry(recovery: Path, entry: dict[str, Any], label: str) -> None:
    if set(entry) != {"existed", "sha256", "backup"}:
        raise ValueError(f"invalid backup entry for {label}")
    if not entry.get("existed"):
        if entry.get("sha256") is not None or entry.get("backup") is not None:
            raise ValueError(f"invalid absent backup entry for {label}")
        return
    backup_name = entry.get("backup")
    expected = entry.get("sha256")
    if (
        not isinstance(backup_name, str)
        or PurePosixPath(backup_name).name != backup_name
        or not isinstance(expected, str)
        or not re.fullmatch(r"[0-9a-f]{64}", expected)
    ):
        raise ValueError(f"invalid backup metadata for {label}")
    backup = recovery / "backups" / backup_name
    if not backup.is_file() or backup.is_symlink() or sha256(backup) != expected:
        raise ValueError(f"backup checksum mismatch for {label}")


def recover_incomplete_transaction(root: Path) -> bool:
    loaded = _load_journal(root)
    if loaded is None:
        return False
    recovery, journal = loaded
    entries = journal.get("paths")
    if not isinstance(entries, list):
        raise ValueError("recovery journal paths must be a list")
    validated: list[tuple[dict[str, Any], Path]] = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "path",
            "existed",
            "sha256",
            "backup",
        }:
            raise ValueError("invalid recovery path entry")
        target, error = _safe_repo_relative(root, str(entry["path"]))
        if error or target is None:
            raise ValueError(error or "invalid recovery path")
        backup_entry = {key: entry[key] for key in ("existed", "sha256", "backup")}
        _validate_backup_entry(recovery, backup_entry, str(entry["path"]))
        validated.append((entry, target))
    index_entry = journal.get("index")
    if not isinstance(index_entry, dict):
        raise ValueError("invalid recovery index entry")
    _validate_backup_entry(recovery, index_entry, "Git index")
    restored: list[Path] = []
    for entry, target in reversed(validated):
        _restore_backup(recovery, entry, target)
        restored.append(target)
    _restore_backup(recovery, index_entry, _index_path(root))
    for target in restored:
        _remove_empty_parents(target, root)
    shutil.rmtree(recovery)
    _fsync_dir(recovery.parent)
    return True


def _backup_entry(recovery: Path, path: Path, relative: str) -> dict[str, Any]:
    if path.exists() or path.is_symlink():
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"transaction path is not a regular file: {relative}")
        content = path.read_bytes()
        digest = _bytes_sha256(content)
        backup_name = f"{digest}.bin"
        backup = recovery / "backups" / backup_name
        if not backup.exists():
            _atomic_write_bytes(backup, content)
        return {
            "path": relative,
            "existed": True,
            "sha256": digest,
            "backup": backup_name,
        }
    return {"path": relative, "existed": False, "sha256": None, "backup": None}


def _begin_transaction(root: Path, operation: str, paths: list[Path]) -> Path:
    recover_incomplete_transaction(root)
    recovery = _recovery_root(root)
    unique: dict[str, Path] = {}
    for path in paths:
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(f"transaction path escapes repository: {path}") from exc
        resolved, error = _safe_repo_relative(root, relative)
        if error or resolved is None:
            raise ValueError(error or f"invalid transaction path: {relative}")
        unique[relative] = resolved
    recovery.mkdir(parents=True, exist_ok=False)
    try:
        entries = [
            _backup_entry(recovery, path, relative)
            for relative, path in sorted(unique.items())
        ]
        index_path = _index_path(root)
        index_entry = _backup_entry(recovery, index_path, "index")
        index_entry.pop("path")
        journal = {
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "worktree": str(root.resolve()),
            "operation": operation,
            "paths": entries,
            "index": index_entry,
        }
        _atomic_write_bytes(
            recovery / "journal.json",
            (json.dumps(journal, indent=2, sort_keys=True) + "\n").encode(),
        )
        _fsync_dir(recovery)
    except BaseException:
        shutil.rmtree(recovery, ignore_errors=True)
        raise
    return recovery


def _finish_transaction(recovery: Path) -> None:
    shutil.rmtree(recovery)
    _fsync_dir(recovery.parent)


def _rollback_transaction(root: Path, exc: BaseException) -> int:
    try:
        recovered = recover_incomplete_transaction(root)
    except Exception as recovery_exc:
        print(
            f"transaction failed ({exc}); durable rollback failed: {recovery_exc}",
            file=sys.stderr,
        )
        return 1
    print(
        f"transaction rolled back: {exc}"
        if recovered
        else f"transaction failed before journaling: {exc}",
        file=sys.stderr,
    )
    return 1


def _registered_file_entries(
    registry: dict[str, Any], root: Path
) -> list[tuple[str, bytes, str, str]]:
    entries: list[tuple[str, bytes, str, str]] = []
    registry_bytes = (root / REGISTRY_REL).read_bytes()
    entries.append(
        (
            REGISTRY_REL.as_posix(),
            registry_bytes,
            "registry",
            _bytes_sha256(registry_bytes),
        )
    )
    for bundle in registry.get("bundles", []):
        for artifact in bundle.get("artifacts", []):
            path = str(artifact["path"])
            resolved, error = _safe_relative(root, path)
            if error or resolved is None or not resolved.is_file():
                raise ValueError(error or f"missing registered artifact: {path}")
            content = resolved.read_bytes()
            digest = _bytes_sha256(content)
            if digest != artifact.get("sha256"):
                raise ValueError(f"registered artifact hash mismatch: {path}")
            entries.append((path, content, str(artifact["role"]), digest))
    return sorted(entries)


def _tar_add_bytes(archive: tarfile.TarFile, path: str, content: bytes) -> None:
    info = tarfile.TarInfo(path)
    info.size = len(content)
    info.mode = 0o644
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    archive.addfile(info, io.BytesIO(content))


def export_seed(output_dir: Path, root: Path = REPO_ROOT) -> Path:
    output = output_dir.resolve()
    repo = root.resolve()
    if output == repo or repo in output.parents:
        raise ValueError("seed output must be outside the repository")
    registry = load_registry(root / REGISTRY_REL)
    errors = validate_registry(registry, root, check_git=False)
    if errors:
        raise ValueError("cannot export invalid registry: " + "\n".join(errors))
    entries = _registered_file_entries(registry, root)
    manifest = {
        "schema_version": SEED_SCHEMA_VERSION,
        "files": [
            {"path": path, "role": role, "bytes": len(content), "sha256": digest}
            for path, content, role, digest in entries
        ],
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    output.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".omx-seed-", dir=output)
    os.close(descriptor)
    try:
        with tarfile.open(temporary, "w", format=tarfile.PAX_FORMAT) as archive:
            _tar_add_bytes(archive, SEED_MANIFEST, manifest_bytes)
            for path, content, _role, _digest in entries:
                _tar_add_bytes(archive, path, content)
        digest = sha256(Path(temporary))
        target = output / f"{digest}.tar"
        if target.exists():
            if sha256(target) != digest:
                raise ValueError(f"seed path collision: {target}")
            Path(temporary).unlink()
        else:
            os.replace(temporary, target)
            _fsync_dir(output)
        verify_seed(target, root)
        return target
    finally:
        Path(temporary).unlink(missing_ok=True)


def verify_seed(seed_path: Path, root: Path = REPO_ROOT) -> dict[str, bytes]:
    expected_name = re.fullmatch(r"([0-9a-f]{64})\.tar", seed_path.name)
    if expected_name is None or sha256(seed_path) != expected_name.group(1):
        raise ValueError("seed filename/content digest mismatch")
    with tarfile.open(seed_path, "r:") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(names) != len(set(names)) or SEED_MANIFEST not in names:
            raise ValueError("seed contains duplicate paths or no manifest")
        for member in members:
            pure = PurePosixPath(member.name)
            if not member.isfile() or pure.is_absolute() or ".." in pure.parts:
                raise ValueError(f"unsafe seed member: {member.name}")
        extracted = {
            member.name: archive.extractfile(member).read()  # type: ignore[union-attr]
            for member in members
        }
    try:
        manifest = json.loads(extracted.pop(SEED_MANIFEST).decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid seed manifest: {exc}") from exc
    if (
        set(manifest) != {"schema_version", "files"}
        or manifest.get("schema_version") != SEED_SCHEMA_VERSION
    ):
        raise ValueError("unsupported seed manifest schema")
    declared: dict[str, dict[str, Any]] = {}
    for item in manifest.get("files", []):
        if not isinstance(item, dict) or set(item) != {
            "path",
            "role",
            "bytes",
            "sha256",
        }:
            raise ValueError("invalid seed file entry")
        path = str(item["path"])
        if path in declared:
            raise ValueError(f"duplicate seed manifest path: {path}")
        declared[path] = item
    if set(extracted) != set(declared):
        raise ValueError("seed payload membership differs from manifest")
    for path, content in extracted.items():
        item = declared[path]
        if len(content) != item["bytes"] or _bytes_sha256(content) != item["sha256"]:
            raise ValueError(f"seed payload checksum mismatch: {path}")
    try:
        registry = tomllib.loads(extracted[REGISTRY_REL.as_posix()].decode("utf-8"))
    except (KeyError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"seed registry is invalid: {exc}") from exc
    expected_metadata = {
        REGISTRY_REL.as_posix(): {
            "role": "registry",
            "bytes": len(extracted[REGISTRY_REL.as_posix()]),
            "sha256": _bytes_sha256(extracted[REGISTRY_REL.as_posix()]),
        }
    }
    for bundle in registry.get("bundles", []):
        for artifact in bundle.get("artifacts", []):
            expected_metadata[str(artifact.get("path", ""))] = {
                "role": artifact.get("role"),
                "bytes": artifact.get("bytes"),
                "sha256": artifact.get("sha256"),
            }
    for path, expected in expected_metadata.items():
        observed = declared.get(path, {})
        if any(observed.get(key) != value for key, value in expected.items()):
            raise ValueError(f"seed manifest metadata differs from registry: {path}")
    _seed_registry(extracted, root)
    return extracted


def _seed_registry(
    payloads: dict[str, bytes], root: Path = REPO_ROOT
) -> dict[str, Any]:
    try:
        registry = tomllib.loads(payloads[REGISTRY_REL.as_posix()].decode("utf-8"))
    except (KeyError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"seed registry is invalid: {exc}") from exc
    expected = {REGISTRY_REL.as_posix()}
    for bundle in registry.get("bundles", []):
        expected.update(
            str(item.get("path", "")) for item in bundle.get("artifacts", [])
        )
    if set(payloads) != expected:
        raise ValueError("seed does not exactly match registry membership")
    errors = _validate_registry_shape(registry)
    if errors:
        raise ValueError("invalid seed registry: " + "\n".join(errors))
    by_id = {
        str(bundle.get("id", "")): bundle
        for bundle in registry.get("bundles", [])
        if isinstance(bundle, dict)
    }
    bundle_ids: set[str] = set()
    current_tasks: set[str] = set()
    registered_paths: set[str] = set()
    for offset, bundle in enumerate(registry.get("bundles", [])):
        if not isinstance(bundle, dict):
            errors.append(f"seed bundle {offset} must be a table")
            continue
        status = str(bundle.get("status", ""))
        errors.extend(
            _exact_keys(bundle, BUNDLE_KEYS.get(status, set()), f"seed bundle {offset}")
            if status in BUNDLE_KEYS
            else [f"seed bundle {offset} status is invalid"]
        )
        bundle_id = str(bundle.get("id", ""))
        task = str(bundle.get("task", ""))
        handoff_hash = str(bundle.get("handoff_sha256", ""))
        if (
            not TASK_RE.fullmatch(task)
            or not BUNDLE_ID_RE.fullmatch(bundle_id)
            or bundle_id != canonical_bundle_id(task, handoff_hash)
        ):
            errors.append(f"seed bundle identity is invalid: {bundle_id}")
        if bundle_id in bundle_ids:
            errors.append(f"duplicate seed bundle id: {bundle_id}")
        bundle_ids.add(bundle_id)
        if bundle.get("acceptance") != "explicit-user-acceptance":
            errors.append(f"seed bundle {bundle_id}: missing explicit user acceptance")
        if bundle.get("review_order") != ["architect", "critic"]:
            errors.append(
                f"seed bundle {bundle_id}: review order must be Architect then Critic"
            )
        if status == "current":
            if task in current_tasks:
                errors.append(f"duplicate current seed task: {task}")
            current_tasks.add(task)
        if commit_error := _commit_error(root, str(bundle.get("source_commit", ""))):
            errors.append(f"seed bundle {bundle_id}: {commit_error}")
        role_map: dict[str, dict[str, Any]] = {}
        native_paths: set[str] = set()
        for index, artifact in enumerate(bundle.get("artifacts", [])):
            errors.extend(
                _validate_artifact_shape(
                    artifact,
                    f"seed bundle {bundle_id}.artifacts[{index}]",
                    str(bundle.get("source_commit", "")),
                )
            )
            if not isinstance(artifact, dict):
                continue
            role = str(artifact.get("role", ""))
            path = str(artifact.get("path", ""))
            native_path = str(artifact.get("native_path", ""))
            if role in role_map:
                errors.append(f"seed bundle {bundle_id}: duplicate role {role}")
            role_map[role] = artifact
            if native_path in native_paths:
                errors.append(
                    f"seed bundle {bundle_id}: duplicate native path {native_path}"
                )
            native_paths.add(native_path)
            if path in registered_paths:
                errors.append(f"duplicate seed artifact path: {path}")
            registered_paths.add(path)
            try:
                expected_path = _canonical_path(bundle_id, status, native_path)
            except (TypeError, ValueError):
                expected_path = ""
            if path != expected_path:
                errors.append(f"seed bundle {bundle_id}: invalid placement for {role}")
            content = payloads.get(path, b"")
            if len(content) != artifact.get("bytes") or _bytes_sha256(
                content
            ) != artifact.get("sha256"):
                errors.append(f"seed bundle {bundle_id}: payload mismatch: {path}")
            try:
                text = content.decode("utf-8")
                redaction_errors = _redaction_errors(path, text)
                if redaction_errors and not _legacy_redaction_allowed(
                    path, str(artifact.get("sha256", ""))
                ):
                    errors.extend(redaction_errors)
            except UnicodeDecodeError:
                errors.append(f"seed bundle {bundle_id}: artifact is not UTF-8: {path}")
        if "handoff" not in role_map:
            errors.append(f"seed bundle {bundle_id}: handoff role is required")
        elif role_map["handoff"].get("sha256") != handoff_hash:
            errors.append(
                f"seed bundle {bundle_id}: handoff hash differs from bundle identity"
            )
        if status == "current" and set(role_map) != set(CURRENT_REQUIRED_ROLES):
            errors.append(
                f"seed bundle {bundle_id}: current roles must be exactly "
                f"{list(CURRENT_REQUIRED_ROLES)}"
            )
        handoff_artifact = role_map.get("handoff", {})
        handoff_content = payloads.get(str(handoff_artifact.get("path", "")))
        if handoff_content is not None:
            try:
                handoff = json.loads(handoff_content.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                errors.append(f"seed bundle {bundle_id}: invalid handoff: {exc}")
            else:
                errors.extend(
                    _validate_handoff_data(
                        handoff,
                        task=task,
                        source_commit=str(bundle.get("source_commit", "")),
                        artifacts=role_map,
                    )
                )
        if status == "superseded":
            successor = by_id.get(str(bundle.get("superseded_by", "")))
            if successor is None or successor.get("status") != "current":
                errors.append(f"seed bundle {bundle_id}: successor is not current")
            elif successor.get("task") == task:
                pass
            elif (
                bundle_id == LEGACY_PREDECESSOR_ID
                and successor.get("task") == "aria-nbv-agent-scaffold-refresh"
            ):
                pass
            else:
                errors.append(f"seed bundle {bundle_id}: successor task differs")
    tombstone_paths: set[str] = set()
    for offset, tombstone in enumerate(registry["tombstones"]):
        errors.extend(
            _exact_keys(tombstone, TOMBSTONE_KEYS, f"seed tombstones[{offset}]")
        )
        if not isinstance(tombstone, dict):
            continue
        original_path = str(tombstone.get("original_path", ""))
        if original_path in tombstone_paths:
            errors.append(f"duplicate seed legacy tombstone: {original_path}")
        tombstone_paths.add(original_path)
        if not re.fullmatch(r"[0-9a-f]{40}", str(tombstone.get("blob_hash", ""))):
            errors.append(f"seed tombstones[{offset}].blob_hash must be a Git SHA-1")
        if commit_error := _commit_error(root, str(tombstone.get("source_commit", ""))):
            errors.append(f"seed tombstone {original_path}: {commit_error}")
        else:
            blob = _git(
                root, "rev-parse", f"{tombstone['source_commit']}:{original_path}"
            )
            if blob.returncode or blob.stdout.strip() != tombstone.get("blob_hash"):
                errors.append(
                    f"seed tombstone {original_path}: source blob hash differs"
                )
    if errors:
        raise ValueError("invalid seed registry: " + "\n".join(errors))
    return registry


def restore_seed(seed_path: Path, root: Path = REPO_ROOT) -> int:
    try:
        recover_incomplete_transaction(root)
        payloads = verify_seed(seed_path, root)
        registry = _seed_registry(payloads, root)
        targets: list[Path] = []
        for relative in sorted(payloads):
            target, error = _safe_repo_relative(root, relative)
            if error or target is None:
                raise ValueError(error or f"invalid seed path: {relative}")
            if relative != REGISTRY_REL.as_posix() and not relative.startswith(".omx/"):
                raise ValueError(
                    f"seed path is outside lifecycle ownership: {relative}"
                )
            targets.append(target)
        registry_path = root / REGISTRY_REL
        if (
            registry_path.exists()
            and registry_path.read_bytes() != payloads[REGISTRY_REL.as_posix()]
        ):
            raise ValueError("existing registry differs from verified seed")
        collisions = [
            path
            for path in targets
            if path != registry_path and (path.exists() or path.is_symlink())
        ]
        if collisions:
            raise ValueError(f"seed restore path already exists: {collisions[0]}")
        recovery = _begin_transaction(root, "restore-seed", targets)
        try:
            for relative, content in sorted(payloads.items()):
                target, _error = _safe_repo_relative(root, relative)
                assert target is not None
                _atomic_write_bytes(target, content)
            _FAULT_HOOK("restore_after_payload")
            errors = validate_registry(registry, root, check_git=False)
            if errors:
                raise ValueError("restored registry is invalid: " + "\n".join(errors))
            add = _git(root, "add", "--", *sorted(payloads))
            if add.returncode:
                raise ValueError(f"cannot stage restored seed: {add.stderr.strip()}")
            _FAULT_HOOK("restore_after_index")
            for relative, content in payloads.items():
                target, _error = _safe_repo_relative(root, relative)
                assert target is not None
                if target.read_bytes() != content:
                    raise ValueError(f"post-restore verification failed: {relative}")
            _finish_transaction(recovery)
        except Exception as exc:
            return _rollback_transaction(root, exc)
        return 0
    except Exception as exc:
        print(f"seed restore rejected: {exc}", file=sys.stderr)
        return 1


def _registered_snapshot(root: Path) -> dict[str, str]:
    registry = load_registry(root / REGISTRY_REL)
    return {
        path: digest
        for path, _content, _role, digest in _registered_file_entries(registry, root)
    }


def _protected_snapshot(root: Path) -> dict[str, str]:
    snapshot = _registered_snapshot(root)
    archive_root = root / ARCHIVE_PREFIX
    if archive_root.is_symlink():
        raise ValueError(f"unsafe accepted archive root: {ARCHIVE_PREFIX}")
    if archive_root.exists():
        for path in archive_root.rglob("*"):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink() or (not path.is_file() and not path.is_dir()):
                raise ValueError(f"unsafe accepted archive entry: {relative}")
            if path.is_file():
                snapshot[relative] = sha256(path)
    return snapshot


def _archive_entry_paths(root: Path) -> set[str]:
    """Return archive entries without following directory symlinks."""
    archive_root = root / ARCHIVE_PREFIX
    if archive_root.is_symlink():
        raise ValueError(f"unsafe accepted archive root: {ARCHIVE_PREFIX}")
    if not archive_root.is_dir():
        return set()
    entries: set[str] = set()
    pending = [archive_root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as children:
            for child in children:
                path = Path(child.path)
                entries.add(path.relative_to(root).as_posix())
                if child.is_dir(follow_symlinks=False):
                    pending.append(path)
    return entries


def _remove_new_archive_entries(root: Path, before: set[str]) -> None:
    """Remove archive entries created after ``before`` without following links."""
    archive_root = root / ARCHIVE_PREFIX
    if archive_root.is_symlink() or (
        archive_root.exists() and not archive_root.is_dir()
    ):
        archive_root.unlink()
        return
    created = _archive_entry_paths(root) - before
    for relative in sorted(created, key=lambda value: value.count("/"), reverse=True):
        target = root / relative
        try:
            if target.is_dir() and not target.is_symlink():
                target.rmdir()
            else:
                target.unlink()
        except FileNotFoundError:
            continue


def _verified_omx_install(executable: str) -> bool:
    """Verify the executed OMX entry point against the reviewed npm payload."""
    resolved = shutil.which(executable)
    if resolved is None:
        return False
    entrypoint = Path(resolved).resolve()
    package_root: Path | None = None
    metadata: dict[str, Any] = {}
    for candidate in entrypoint.parents:
        try:
            candidate_metadata = json.loads(
                (candidate / "package.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            continue
        if candidate_metadata.get("name") == "oh-my-codex":
            package_root = candidate
            metadata = candidate_metadata
            break
    if package_root is None or metadata.get("version") != OMX_PINNED_VERSION:
        return False
    try:
        relative_entrypoint = entrypoint.relative_to(package_root).as_posix()
    except ValueError:
        return False
    if relative_entrypoint != "dist/cli/omx.js":
        return False
    result = subprocess.run(
        [str(entrypoint), "--version"], check=False, capture_output=True, text=True
    )
    output = f"{result.stdout}\n{result.stderr}"
    version_matches = (
        result.returncode == 0
        and re.search(
            rf"(?<![0-9.])v?{re.escape(OMX_PINNED_VERSION)}(?![0-9.])", output
        )
        is not None
    )
    if not version_matches:
        return False
    npm = shutil.which("npm")
    if npm is None:
        return False
    with tempfile.TemporaryDirectory(prefix="omx-integrity-") as raw_temp:
        packed = subprocess.run(
            [
                npm,
                "pack",
                f"oh-my-codex@{OMX_PINNED_VERSION}",
                "--json",
                "--pack-destination",
                raw_temp,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        try:
            package = json.loads(packed.stdout)[0]
            archive = Path(raw_temp) / package["filename"]
        except (IndexError, KeyError, json.JSONDecodeError):
            return False
        if packed.returncode != 0 or package.get("integrity") != OMX_PINNED_INTEGRITY:
            return False
        try:
            with tarfile.open(archive, "r:gz") as payload:
                for member in payload.getmembers():
                    if not member.isfile() or not member.name.startswith("package/"):
                        continue
                    relative = member.name.removeprefix("package/")
                    installed = package_root / relative
                    source = payload.extractfile(member)
                    if source is None or not installed.is_file():
                        return False
                    if (
                        hashlib.sha256(source.read()).digest()
                        != hashlib.sha256(installed.read_bytes()).digest()
                    ):
                        return False
        except (OSError, tarfile.TarError):
            return False
    return True


def run_native_operation(command: list[str], root: Path = REPO_ROOT) -> int:
    allowed = command in (
        ["omx", "cleanup", "--dry-run"],
        ["omx", "cleanup"],
        ["omx", "cancel"],
    )
    allowed = allowed or (
        len(command) == 7
        and command[:5] == ["omx", "ultragoal", "create-goals", "--force", "--brief"]
        and command[-1] == "--json"
    )
    if not allowed:
        print("native OMX operation is outside the reviewed allowlist", file=sys.stderr)
        return 2
    if not _verified_omx_install(command[0]):
        print(
            "native OMX operation requires reviewed oh-my-codex "
            f"{OMX_PINNED_VERSION} integrity",
            file=sys.stderr,
        )
        return 2
    archive_entries_before: set[str] | None = None
    try:
        recover_incomplete_transaction(root)
        before = _protected_snapshot(root)
        archive_entries_before = _archive_entry_paths(root)
        protected_paths = [root / path for path in before]
        recovery = _begin_transaction(root, "native-operation", protected_paths)
        result = subprocess.run(command, cwd=root, check=False)
        after = _protected_snapshot(root)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        if archive_entries_before is not None:
            _remove_new_archive_entries(root, archive_entries_before)
        return _rollback_transaction(
            root, ValueError(f"native OMX operation damaged registered evidence: {exc}")
        )
    if after != before:
        _remove_new_archive_entries(root, archive_entries_before)
        return _rollback_transaction(
            root, ValueError("native OMX operation changed registered evidence")
        )
    _finish_transaction(recovery)
    return result.returncode


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
        errors.append(f"draft roles must be exactly {list(CURRENT_REQUIRED_ROLES)}")
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
        role: handoff_bytes if role == "handoff" else source_by_role[role].read_bytes()
        for role in CURRENT_REQUIRED_ROLES
    }
    return current, content_by_role


def promote(
    manifest_path: Path, acceptance: str, dry_run: bool, root: Path = REPO_ROOT
) -> int:
    try:
        recover_incomplete_transaction(root)
    except Exception as exc:
        print(f"promotion recovery failed: {exc}", file=sys.stderr)
        return 1
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
    for item in current["artifacts"]:
        _target, path_error = _safe_relative(root, str(item["native_path"]))
        if path_error:
            print(f"- {path_error}", file=sys.stderr)
            return 1
    collisions = [path for path in targets.values() if path.exists()]
    if collisions:
        print(
            f"- declared native path already exists: {collisions[0]}", file=sys.stderr
        )
        return 1
    current_errors = validate_registry(registry, root, check_git=False)
    if current_errors:
        for error in current_errors:
            print(f"- pre-mutation registry invalid: {error}", file=sys.stderr)
        return 1
    try:
        recovery = _begin_transaction(
            root, "promote", [registry_path, *targets.values()]
        )
        for role in CURRENT_REQUIRED_ROLES:
            target = targets[role]
            _atomic_write_bytes(target, content_by_role[role])
        _FAULT_HOOK("promote_after_payload")
        errors = validate_registry(candidate, root, check_git=False)
        if errors:
            raise ValueError("\n".join(errors))
        _atomic_write_bytes(registry_path, rendered.encode())
        _FAULT_HOOK("promote_after_registry")
        if validate_registry(candidate, root, check_git=False):
            raise ValueError("post-promotion verification failed")
        _finish_transaction(recovery)
    except Exception as exc:
        return _rollback_transaction(root, exc)
    return 0


def supersede(
    bundle_id: str,
    successor_manifest: Path,
    acceptance: str,
    dry_run: bool,
    root: Path = REPO_ROOT,
) -> int:
    try:
        recover_incomplete_transaction(root)
    except Exception as exc:
        print(f"supersession recovery failed: {exc}", file=sys.stderr)
        return 1
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
    for item in bundle["artifacts"]:
        path = predecessor_paths[str(item["role"])]
        if sha256(path) != item.get("sha256"):
            print(f"- current predecessor hash mismatch: {path}", file=sys.stderr)
            return 1
    archive_paths = {
        item["role"]: root
        / _canonical_path(bundle_id, "superseded", item["native_path"])
        for item in bundle["artifacts"]
    }
    archive_bundle_root = root / ARCHIVE_PREFIX / bundle_id
    if archive_bundle_root.exists() or archive_bundle_root.is_symlink():
        print(
            f"- predecessor archive root already exists: {archive_bundle_root}",
            file=sys.stderr,
        )
        return 1
    for path in [*archive_paths.values(), *predecessor_paths.values()]:
        relative = path.relative_to(root).as_posix()
        _target, path_error = _safe_relative(root, relative)
        if path_error:
            print(f"- {path_error}", file=sys.stderr)
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
        print(
            f"- successor native path already exists: {collisions[0]}", file=sys.stderr
        )
        return 1
    predecessor_content = {
        role: path.read_bytes() for role, path in predecessor_paths.items()
    }
    current_errors = validate_registry(registry, root, check_git=False)
    if current_errors:
        for error in current_errors:
            print(f"- pre-mutation registry invalid: {error}", file=sys.stderr)
        return 1
    try:
        recovery = _begin_transaction(
            root,
            "supersede",
            [
                registry_path,
                *predecessor_paths.values(),
                *archive_paths.values(),
                *successor_paths.values(),
            ],
        )
        for role, path in archive_paths.items():
            _atomic_write_bytes(path, predecessor_content[role])
        for path in predecessor_paths.values():
            if path not in set(successor_paths.values()):
                path.unlink()
                _fsync_dir(path.parent)
        _FAULT_HOOK("supersede_after_archive")
        for role, path in successor_paths.items():
            _atomic_write_bytes(path, successor_content[role])
        _FAULT_HOOK("supersede_after_successor")
        errors = validate_registry(candidate, root, check_git=False)
        if errors:
            raise ValueError("\n".join(errors))
        _atomic_write_bytes(registry_path, rendered.encode())
        _FAULT_HOOK("supersede_after_registry")
        if validate_registry(candidate, root, check_git=False):
            raise ValueError("post-supersession verification failed")
        _finish_transaction(recovery)
    except Exception as exc:
        return _rollback_transaction(root, exc)
    return 0


def check(root: Path = REPO_ROOT, baseline_ref: str | None = None) -> list[str]:
    registry = load_registry(root / REGISTRY_REL)
    errors = validate_registry(registry, root)
    if _load_journal(root) is not None:
        errors.append(
            "incomplete OMX lifecycle transaction; run a mutation command to recover"
        )
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
    actions.add_argument("--export-seed", type=Path)
    actions.add_argument("--verify-seed", type=Path)
    actions.add_argument("--restore-seed", type=Path)
    actions.add_argument("--run-native-operation", nargs=argparse.REMAINDER)
    parser.add_argument("--acceptance", default="")
    parser.add_argument("--baseline-ref")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    if args.export_seed:
        try:
            seed = export_seed(args.export_seed, args.repo_root)
        except (OSError, ValueError, tarfile.TarError, tomllib.TOMLDecodeError) as exc:
            print(f"seed export failed: {exc}", file=sys.stderr)
            return 1
        print(seed)
        return 0
    if args.verify_seed:
        try:
            payloads = verify_seed(args.verify_seed, args.repo_root)
        except (OSError, ValueError, tarfile.TarError) as exc:
            print(f"seed verification failed: {exc}", file=sys.stderr)
            return 1
        print(f"OMX seed valid: {len(payloads)} registered file(s)")
        return 0
    if args.restore_seed:
        return restore_seed(args.restore_seed, args.repo_root)
    if args.run_native_operation is not None:
        return run_native_operation(args.run_native_operation, args.repo_root)
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
