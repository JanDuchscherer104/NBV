#!/usr/bin/env python3
"""Validate registered current and superseded OMX evidence bundles.

Registered evidence is public-by-default. The privacy scan therefore rejects
machine/runtime locators, private paths and HTML, plus explicit credential
formats. It intentionally has no generic high-entropy or catch-all secret
regex because those produce unactionable false positives in technical prose.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

REGISTRY = ".agents/omx_artifacts.toml"
REQUIRED_FAMILIES = {
    "context",
    "specification",
    "plan",
    "test_specification",
    "review",
    "handoff",
}
CURRENT_ROOTS = (".omx/context/", ".omx/specs/", ".omx/plans/")
PRIVATE_PARTS = {
    "cache",
    "logs",
    "private",
    "raw",
    "runtime",
    "sessions",
    "state",
    "tmux",
    "transcripts",
    "ultragoal",
}
ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
IMMUTABLE_BUNDLE_FIELDS = (
    "id",
    "task",
    "classification",
    "baseline_commit",
    "handoff_sha256",
    "acceptance_sha256",
)
REGISTRY_FIELDS = {"schema_version", "bundle"}
BUNDLE_FIELDS = {
    *IMMUTABLE_BUNDLE_FIELDS,
    "status",
    "predecessor_bundle_id",
    "predecessor_registry_commit",
    "superseded_by",
    "artifact",
}
ARTIFACT_FIELDS = {
    "family",
    "role",
    "path",
    "native_path",
    "sha256",
    "bytes",
    "review_kinds",
}
RUNTIME_UUID = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
ABSOLUTE_PATH = re.compile(
    r"(?<![A-Za-z0-9_.:/-])(?:/[A-Za-z0-9._-]+){2,}(?=$|[\s`'\"),:;])"
    r"|\b[A-Za-z]:\\(?:[^\s`'\"<>|]+\\)+[^\s`'\"<>|]*"
)
PRIVATE_PATH = re.compile(
    r"(?<![A-Za-z0-9_.-])(?:"
    r"(?:\.?[A-Za-z0-9_.-]+/)+(?:private|raw)/"
    r"|(?:private|raw)/(?:[A-Za-z0-9_.-]+/)+"
    r")(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+",
    re.IGNORECASE,
)
HTML = re.compile(r"<!doctype\s+html\b|<html(?:\s|>)", re.IGNORECASE)
# fmt: off
SENSITIVE_TEXT = (
    (re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"), "private key"),
    (re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"), "GitHub token"),
    (re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}\b"), "OpenAI API key"),
    (re.compile(r"\b(?:AKIA|ASIA|AIDA|AROA)[A-Z0-9]{16}\b"), "AWS access key ID"),
    (re.compile(r"\baws_secret_access_key\b\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{40}\b", re.IGNORECASE), "AWS secret access key"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "Slack token"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"), "Google API key"),
    (re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"), "GitLab token"),
    (re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"), "Hugging Face token"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}\b", re.IGNORECASE), "bearer token"),
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE), "email address"),
)
# fmt: on


class ValidationError(ValueError):
    """Raised when a registry or artifact violates the lifecycle contract."""


@dataclass(frozen=True)
class Artifact:
    family: str
    role: str
    path: str
    native_path: str
    sha256: str
    bytes: int
    review_kinds: tuple[str, ...]


def _run(repo: Path, *args: str) -> str:
    result = subprocess.run(
        args,
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout


def _safe_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or str(path) != value:
        raise ValidationError(f"unsafe repository path: {value}")
    if path.suffix.lower() in {".html", ".htm"}:
        raise ValidationError(f"HTML is not accepted evidence: {value}")
    if PRIVATE_PARTS.intersection(part.lower() for part in path.parts):
        raise ValidationError(f"raw or private evidence directory: {value}")
    return path


def _digest(path: Path) -> tuple[str, int]:
    payload = path.read_bytes()
    return hashlib.sha256(payload).hexdigest(), len(payload)


def _scan_text(text: str, subject: object) -> None:
    checks = (
        (ABSOLUTE_PATH, "absolute path"),
        (RUNTIME_UUID, "runtime UUID"),
        (PRIVATE_PATH, "private or raw path part"),
        (HTML, "HTML content"),
        *SENSITIVE_TEXT,
    )
    for pattern, label in checks:
        if pattern.search(text):
            raise ValidationError(
                f"privacy threat ({label}) in registered evidence: {subject}"
            )


def _scan(path: Path) -> None:
    _scan_text(path.read_text(encoding="utf-8"), path)


def _json_identity(path: Path, bundle_id: str, task: str, label: str) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValidationError(f"invalid {label} JSON for {bundle_id}: {exc}") from exc
    if payload.get("bundle_id") != bundle_id or payload.get("task") != task:
        raise ValidationError(f"{label} identity mismatch for {bundle_id}")


def _parse_registry(payload: bytes) -> dict[str, Any]:
    text = payload.decode("utf-8")
    _scan_text(text, REGISTRY)
    data = tomllib.loads(text)
    unknown = set(data) - REGISTRY_FIELDS
    if unknown:
        raise ValidationError(f"unknown registry fields: {sorted(unknown)}")
    if data.get("schema_version") != 1:
        raise ValidationError("registry schema_version must be 1")
    if not isinstance(data.get("bundle"), list) or not data["bundle"]:
        raise ValidationError("registry must contain at least one bundle")
    for bundle in data["bundle"]:
        if not isinstance(bundle, dict):
            raise ValidationError("registry bundle must be a mapping")
        unknown = set(bundle) - BUNDLE_FIELDS
        if unknown:
            raise ValidationError(
                f"unknown bundle fields for {bundle.get('id')}: {sorted(unknown)}"
            )
        artifacts = bundle.get("artifact")
        if not isinstance(artifacts, list):
            raise ValidationError(f"bundle {bundle.get('id')} artifacts must be a list")
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                raise ValidationError(
                    f"bundle {bundle.get('id')} artifact must be a mapping"
                )
            unknown = set(artifact) - ARTIFACT_FIELDS
            if unknown:
                raise ValidationError(
                    f"unknown artifact fields for {bundle.get('id')}: {sorted(unknown)}"
                )
    return data


def load_registry(path: Path) -> dict[str, Any]:
    return _parse_registry(path.read_bytes())


def _artifacts(bundle: dict[str, Any]) -> list[Artifact]:
    items = bundle.get("artifact")
    if not isinstance(items, list) or not items:
        raise ValidationError(f"bundle {bundle.get('id')} has no artifacts")
    try:
        return [
            Artifact(
                family=item["family"],
                role=item["role"],
                path=item["path"],
                native_path=item["native_path"],
                sha256=item["sha256"],
                bytes=item["bytes"],
                review_kinds=tuple(item.get("review_kinds", ())),
            )
            for item in items
        ]
    except (KeyError, TypeError) as exc:
        raise ValidationError(f"invalid artifact in {bundle.get('id')}: {exc}") from exc


def _validate_baseline(repo: Path, bundle_id: str, baseline: object) -> None:
    if not HEX_40.fullmatch(str(baseline or "")):
        raise ValidationError(f"invalid baseline commit for {bundle_id}")
    commit = subprocess.run(
        ["git", "cat-file", "-e", f"{baseline}^{{commit}}"],
        cwd=repo,
        check=False,
        capture_output=True,
    )
    if commit.returncode:
        raise ValidationError(
            f"baseline is not a git commit for {bundle_id}: {baseline}"
        )
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", str(baseline), "HEAD"],
        cwd=repo,
        check=False,
        capture_output=True,
    )
    if ancestor.returncode:
        raise ValidationError(
            f"baseline is not an ancestor of HEAD for {bundle_id}: {baseline}"
        )


def validate_registry(repo: Path, registry_path: Path) -> set[str]:
    bundles = load_registry(registry_path)["bundle"]
    ids: set[str] = set()
    owned: set[str] = set()
    current_tasks: set[str] = set()
    parsed: dict[str, tuple[dict[str, Any], list[Artifact]]] = {}
    for bundle in bundles:
        bundle_id = bundle.get("id")
        task = bundle.get("task")
        status = bundle.get("status")
        if (
            not isinstance(bundle_id, str)
            or not ID.fullmatch(bundle_id)
            or bundle_id in ids
        ):
            raise ValidationError(f"duplicate or invalid bundle id: {bundle_id}")
        if not isinstance(task, str) or not ID.fullmatch(task):
            raise ValidationError(f"invalid task for {bundle_id}: {task}")
        if status not in {"current", "superseded"}:
            raise ValidationError(f"invalid status for {bundle_id}: {status}")
        _validate_baseline(repo, bundle_id, bundle.get("baseline_commit"))
        if bundle.get("classification") != "accepted-decision-evidence":
            raise ValidationError(f"invalid classification for {bundle_id}")
        if status == "current":
            if task in current_tasks:
                raise ValidationError(f"multiple current bundles for task {task}")
            current_tasks.add(task)
            if bundle.get("superseded_by"):
                raise ValidationError(f"current bundle {bundle_id} has a successor")
        elif not isinstance(bundle.get("superseded_by"), str):
            raise ValidationError(f"superseded bundle {bundle_id} lacks successor")
        ids.add(bundle_id)
        parsed[bundle_id] = (bundle, _artifacts(bundle))
    for bundle_id, (bundle, artifacts) in parsed.items():
        status = bundle["status"]
        families = [artifact.family for artifact in artifacts]
        if status == "current" and set(families) != REQUIRED_FAMILIES:
            raise ValidationError(f"bundle {bundle_id} role families differ")
        repeated = {family for family in families if families.count(family) > 1}
        if status == "current" and repeated - {"specification"}:
            raise ValidationError(
                f"bundle {bundle_id} has invalid repeated role families"
            )
        reviews = [a for a in artifacts if a.family == "review"]
        if status == "current" and (
            len(reviews) != 1 or set(reviews[0].review_kinds) != {"architect", "critic"}
        ):
            raise ValidationError(f"bundle {bundle_id} lacks Architect+Critic review")
        handoffs = [a for a in artifacts if a.family == "handoff"]
        if status == "current" and (
            len(handoffs) != 1
            or bundle.get("handoff_sha256") != handoffs[0].sha256
            or not HEX_64.fullmatch(str(bundle.get("handoff_sha256", "")))
        ):
            raise ValidationError(f"invalid handoff for {bundle_id}")
        acceptances = [
            a
            for a in artifacts
            if a.family == "specification" and a.role == "acceptance-record"
        ]
        if status == "current" and (
            len(acceptances) != 1
            or PurePosixPath(acceptances[0].path).suffix != ".json"
            or bundle.get("acceptance_sha256") != acceptances[0].sha256
            or not HEX_64.fullmatch(str(bundle.get("acceptance_sha256", "")))
        ):
            raise ValidationError(f"invalid acceptance record for {bundle_id}")

        for artifact in artifacts:
            path = _safe_path(artifact.path)
            native = _safe_path(artifact.native_path)
            if artifact.family not in REQUIRED_FAMILIES or not ID.fullmatch(
                artifact.role
            ):
                raise ValidationError(f"invalid role for {artifact.path}")
            if artifact.path in owned:
                raise ValidationError(
                    f"artifact path has multiple owners: {artifact.path}"
                )
            if (
                not HEX_64.fullmatch(artifact.sha256)
                or type(artifact.bytes) is not int
                or artifact.bytes < 0
            ):
                raise ValidationError(f"invalid digest metadata: {artifact.path}")
            if status == "current":
                if (
                    artifact.path != artifact.native_path
                    or not artifact.path.startswith(CURRENT_ROOTS)
                ):
                    raise ValidationError(
                        f"current artifact not at native role path: {artifact.path}"
                    )
            else:
                prefix = f".omx/archive/accepted-bundles/{bundle_id}/"
                expected = prefix + artifact.native_path.removeprefix(".omx/")
                if artifact.path != expected or not str(native).startswith(
                    CURRENT_ROOTS
                ):
                    raise ValidationError(f"invalid archive placement: {artifact.path}")
            disk = repo / path
            if not disk.is_file() or disk.is_symlink():
                raise ValidationError(f"missing or unsafe artifact: {artifact.path}")
            if _digest(disk) != (artifact.sha256, artifact.bytes):
                raise ValidationError(f"hash or byte drift: {artifact.path}")
            _scan(disk)
            owned.add(artifact.path)
        if status == "current":
            _json_identity(
                repo / handoffs[0].path, bundle_id, bundle["task"], "handoff"
            )
            _json_identity(
                repo / acceptances[0].path,
                bundle_id,
                bundle["task"],
                "acceptance record",
            )
    for bundle_id, (bundle, _) in parsed.items():
        if bundle["status"] == "current":
            continue
        seen = {bundle_id}
        node = bundle
        while node["status"] == "superseded":
            successor_id = node.get("superseded_by")
            if not isinstance(successor_id, str):
                raise ValidationError(f"invalid successor for {bundle_id}")
            successor = parsed.get(successor_id)
            if not successor or successor_id in seen:
                raise ValidationError(
                    f"invalid or cyclic successor {successor_id} for {bundle_id}"
                )
            if successor[0]["task"] != bundle["task"]:
                raise ValidationError(f"successor task mismatch for {bundle_id}")
            _validate_archive_source(repo, node, successor[0])
            seen.add(successor_id)
            node = successor[0]
    return owned


def _membership(bundle: dict[str, Any]) -> set[tuple[Any, ...]]:
    return {
        (
            item["family"],
            item["role"],
            item["native_path"],
            item["sha256"],
            item["bytes"],
            tuple(item.get("review_kinds", ())),
        )
        for item in bundle["artifact"]
    }


def validate_transition(previous: dict[str, Any], current: dict[str, Any]) -> None:
    old = {bundle["id"]: bundle for bundle in previous.get("bundle", [])}
    new = {bundle["id"]: bundle for bundle in current.get("bundle", [])}
    for bundle_id, before in old.items():
        after = new.get(bundle_id)
        if not after:
            raise ValidationError(f"registered bundle removed: {bundle_id}")
        if before["status"] == "superseded" or after["status"] == "current":
            if before != after:
                raise ValidationError(f"accepted bundle mutated: {bundle_id}")
            continue
        if (
            after["status"] != "superseded"
            or _membership(before) != _membership(after)
            or any(before.get(key) != after.get(key) for key in IMMUTABLE_BUNDLE_FIELDS)
        ):
            raise ValidationError(f"invalid or non-identical supersession: {bundle_id}")
        successor = new.get(after.get("superseded_by"))
        if (
            not successor
            or successor["status"] != "current"
            or successor["task"] != before["task"]
        ):
            raise ValidationError(f"invalid successor for {bundle_id}")
    for bundle_id, bundle in new.items():
        if bundle_id not in old and bundle["status"] != "current":
            raise ValidationError(f"new bundle must first be current: {bundle_id}")


def _previous_registry(repo: Path, ref: str) -> dict[str, Any] | None:
    _run(repo, "git", "rev-parse", "--verify", f"{ref}^{{commit}}")
    shown = subprocess.run(
        ["git", "show", f"{ref}:{REGISTRY}"], cwd=repo, check=False, capture_output=True
    )
    if shown.returncode == 0:
        return _parse_registry(shown.stdout)
    tree = subprocess.run(
        ["git", "ls-tree", "--name-only", ref, "--", REGISTRY],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    if not tree.stdout.strip():
        return None
    raise ValidationError(
        f"git show failed for {ref}:{REGISTRY}: {shown.stderr.decode().strip()}"
    )


def _validate_archive_source(
    repo: Path, archived: dict[str, Any], successor: dict[str, Any]
) -> None:
    bundle_id = archived["id"]
    if successor.get("predecessor_bundle_id") != bundle_id:
        raise ValidationError(f"successor predecessor mismatch for {bundle_id}")
    commit = successor.get("predecessor_registry_commit")
    if not HEX_40.fullmatch(str(commit or "")):
        raise ValidationError(f"invalid predecessor registry commit for {bundle_id}")
    previous = _previous_registry(repo, str(commit))
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", str(commit), "HEAD"],
        cwd=repo,
        check=False,
        capture_output=True,
    )
    if ancestor.returncode:
        raise ValidationError(
            f"predecessor registry commit is not an ancestor of HEAD for {bundle_id}"
        )
    if previous is None:
        raise ValidationError(f"predecessor registry is missing for {bundle_id}")
    before = next(
        (item for item in previous["bundle"] if item.get("id") == bundle_id), None
    )
    if before is None or before.get("status") != "current":
        raise ValidationError(f"predecessor bundle is not current for {bundle_id}")
    if _membership(before) != _membership(archived):
        raise ValidationError(f"predecessor artifact metadata drift for {bundle_id}")
    if any(before.get(key) != archived.get(key) for key in IMMUTABLE_BUNDLE_FIELDS):
        raise ValidationError(f"predecessor bundle metadata drift for {bundle_id}")
    for artifact in before["artifact"]:
        shown = subprocess.run(
            ["git", "show", f"{commit}:{artifact['native_path']}"],
            cwd=repo,
            check=False,
            capture_output=True,
        )
        if shown.returncode or (
            hashlib.sha256(shown.stdout).hexdigest(),
            len(shown.stdout),
        ) != (artifact["sha256"], artifact["bytes"]):
            raise ValidationError(
                f"predecessor artifact byte drift: {artifact['native_path']}"
            )


def validate_tracked(repo: Path, owned: set[str]) -> None:
    tracked = set(filter(None, _run(repo, "git", "ls-files", ".omx").splitlines()))
    if tracked != owned:
        raise ValidationError(
            f"tracked OMX membership differs; extra={sorted(tracked - owned)}, "
            f"missing={sorted(owned - tracked)}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--registry", type=Path, default=Path(REGISTRY))
    parser.add_argument("--previous-ref")
    parser.add_argument("--check-tracked", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    registry = args.registry if args.registry.is_absolute() else repo / args.registry
    try:
        owned = validate_registry(repo, registry)
        if args.previous_ref:
            previous = _previous_registry(repo, args.previous_ref)
            if previous is not None:
                validate_transition(previous, load_registry(registry))
        if args.check_tracked:
            validate_tracked(repo, owned)
    except (
        OSError,
        KeyError,
        subprocess.CalledProcessError,
        tomllib.TOMLDecodeError,
        ValidationError,
    ) as exc:
        print(f"OMX artifact validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"OMX artifact validation passed: {len(owned)} registered artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
