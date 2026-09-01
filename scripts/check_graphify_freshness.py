#!/usr/bin/env python3
"""Fail-closed freshness gate backed by Graphify's pinned detector."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
from typing import Any

PROJECTION_INDEX = Path("graphify-input/index.md")
GRAPH = Path("graphify-out/graph.json")
MANIFEST = Path("graphify-out/manifest.json")
INTERPRETER = Path("graphify-out/.graphify_python")
ROOT_MARKER = Path("graphify-out/.graphify_root")
NEEDS_UPDATE = Path("graphify-out/needs_update")
INDEX_PATH = "graphify-input/index.md"
PINNED_GRAPHIFY_VERSION = "0.9.48"
MAX_STALE_SOURCES = 128
GIT_OBJECT_REPAIR_COMMAND = "git fetch --all --prune"
FRESH_ACTION = 'graphify query "<question>"'
STALE_ACTION = (
    "python3 scripts/build_graphify_projection.py --output graphify-input "
    '--aria-code-ref "$(git rev-parse HEAD)" && graphify update .'
)
UNUSABLE_ACTION = "bash scripts/setup_worktree_env.sh"
_OWNER_DIGEST = re.compile(r"^- ([^:\r\n]+): sha256:([0-9a-f]{64})\r?$")
_OID = re.compile(r"^[0-9a-f]+$")


class _MissingGitObjectError(ValueError):
    """Identify a revision whose tree cannot be derived locally."""


def _head(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--end-of-options", "HEAD^{commit}"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode or not result.stdout.strip():
        raise _MissingGitObjectError(
            f"current Git HEAD is unavailable; repair with: {GIT_OBJECT_REPAIR_COMMAND}"
        )
    return _commit_oid(root, result.stdout.strip(), "current Git HEAD")


def _oid_length(root: Path) -> int:
    result = subprocess.run(
        ["git", "rev-parse", "--show-object-format"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode or result.stdout.strip() not in {"sha1", "sha256"}:
        raise ValueError("Git object format is unavailable")
    return 40 if result.stdout.strip() == "sha1" else 64


def _commit_oid(root: Path, value: str, label: str) -> str:
    length = _oid_length(root)
    if not _OID.fullmatch(value) or len(value) != length:
        raise _MissingGitObjectError(
            f"{label} must be a canonical full commit OID; repair with: "
            f"{GIT_OBJECT_REPAIR_COMMAND}"
        )
    result = subprocess.run(
        ["git", "cat-file", "-t", "--end-of-options", value],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode or result.stdout.strip() != "commit":
        raise _MissingGitObjectError(
            f"{label} does not resolve to a commit object; repair with: "
            f"{GIT_OBJECT_REPAIR_COMMAND}"
        )
    return value


def _is_ancestor(root: Path, older: str, newer: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", "--", older, newer],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise ValueError(
        f"Git merge-base failed: {result.stderr.strip() or result.stdout.strip()}"
    )


def _tree_oid(root: Path, revision: str, label: str) -> str:
    commit = _commit_oid(root, revision, label)
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--end-of-options", f"{commit}^{{tree}}"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    tree = result.stdout.strip()
    if result.returncode or not _OID.fullmatch(tree) or len(tree) != _oid_length(root):
        raise _MissingGitObjectError(
            f"{label} source tree is unavailable for {revision}; "
            f"repair with: {GIT_OBJECT_REPAIR_COMMAND}"
        )
    return tree


def _regular(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"missing or unsafe {label}: {path.as_posix()}")


def _local_regular(root: Path, relative: Path, label: str) -> Path:
    current = root
    for part in relative.parent.parts:
        current /= part
        if current.is_symlink() or not current.is_dir():
            raise ValueError(f"missing or unsafe {label} parent: {current.as_posix()}")
    path = root / relative
    _regular(path, label)
    return path


def _json_object(path: Path, label: str) -> dict[str, Any]:
    _regular(path, label)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"invalid {label}: expected a JSON object")
    return value


def _normalize_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", normalized):
        raise ValueError("unsafe source path")
    path = PurePosixPath(normalized)
    if path.is_absolute() or "." in path.parts or ".." in path.parts:
        raise ValueError("unsafe source path")
    return path.as_posix()


def _contained_existing(root: Path, value: str) -> str:
    candidate = Path(value)
    if candidate.is_absolute():
        try:
            candidate = candidate.resolve(strict=True)
            relative = candidate.relative_to(root.resolve()).as_posix()
        except (OSError, RuntimeError, ValueError) as error:
            raise ValueError(f"stale source escapes repository: {value}") from error
    else:
        relative = _normalize_path(value)
        candidate = root / relative
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ValueError(f"stale source is unavailable: {relative}: {error}") from error
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise ValueError(f"stale source escapes repository: {relative}")
    return relative


def _projection_metadata(
    index: Path,
) -> tuple[str, str | None, str, dict[str, str]]:
    try:
        text = index.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ValueError(f"invalid projection index: {error}") from error

    def single_value(key: str) -> str:
        values = [
            line.split(":", 1)[1].strip()
            for line in text.splitlines()
            if line.startswith(f"{key}:")
        ]
        if len(values) != 1 or not values[0]:
            raise ValueError(
                f"invalid projection index: {key} must be one non-empty string"
            )
        return values[0]

    revision = single_value("source_revision")
    if not _OID.fullmatch(revision):
        raise ValueError("invalid projection index: source_revision is not a full OID")
    tree_values = [
        line.split(":", 1)[1].strip()
        for line in text.splitlines()
        if line.startswith("source_tree:")
    ]
    if len(tree_values) > 1 or (tree_values and not _OID.fullmatch(tree_values[0])):
        raise ValueError("invalid projection index: source_tree is invalid")
    source_tree = tree_values[0] if tree_values else None
    owner_state = single_value("owner_worktree_state")
    if owner_state not in {"clean", "dirty"}:
        raise ValueError("invalid projection index: owner_worktree_state is invalid")
    try:
        start = text.splitlines().index("## Owner digests") + 1
    except ValueError as error:
        raise ValueError("invalid projection index: missing Owner digests") from error
    owners: dict[str, str] = {}
    for line in text.splitlines()[start:]:
        if line.startswith("## "):
            break
        if not line.strip():
            continue
        match = _OWNER_DIGEST.fullmatch(line)
        if match is None:
            raise ValueError(f"invalid projection index owner digest: {line}")
        owner, digest = match.groups()
        normalized = _normalize_path(owner)
        if normalized in owners:
            raise ValueError(f"invalid projection index: duplicate owner {normalized}")
        owners[normalized] = digest
    if not owners:
        raise ValueError("invalid projection index: Owner digests must not be empty")
    return revision, source_tree, owner_state, owners


def _graph_revision(root: Path) -> str:
    graph = _json_object(root / GRAPH, "graph")
    revision = graph.get("built_at_commit")
    nodes = graph.get("nodes")
    if not isinstance(revision, str) or not _OID.fullmatch(revision):
        raise ValueError("invalid graph: built_at_commit must be a full OID")
    if not isinstance(nodes, list) or any(not isinstance(node, dict) for node in nodes):
        raise ValueError("invalid graph: nodes must be a list of objects")
    found = False
    for node in nodes:
        source = node.get("source_file")
        if source is None:
            continue
        if not isinstance(source, str):
            raise ValueError("invalid graph: node source_file must be a string")
        if _normalize_path(source) == INDEX_PATH:
            found = True
    if not found:
        raise ValueError("graph has no node sourced from graphify-input/index.md")
    return revision


def _owner_reasons(
    root: Path,
    owners: dict[str, str],
    *,
    missing_is_change: bool = False,
) -> list[str]:
    reasons: list[str] = []
    for relative, expected in owners.items():
        owner = root / relative
        try:
            resolved = owner.resolve(strict=True)
        except FileNotFoundError as error:
            reason = f"projection owner is unavailable: {relative}: {error}"
            if missing_is_change and not owner.is_symlink():
                reasons.append(reason)
                continue
            raise ValueError(reason) from error
        except (OSError, RuntimeError) as error:
            raise ValueError(
                f"projection owner is unavailable: {relative}: {error}"
            ) from error
        if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
            raise ValueError(f"projection owner escapes repository: {relative}")
        if hashlib.sha256(resolved.read_bytes()).hexdigest() != expected:
            reasons.append(f"projection owner digest changed: {relative}")
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all", "--", *owners],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if status.returncode:
        raise ValueError("projection owner worktree status is unavailable")
    if status.stdout.strip():
        reasons.append("projection owner worktree is dirty")
    return reasons


def projection_owner_changes(root: Path) -> list[str]:
    """Return exact projection-owner changes for setup-owned reconciliation."""
    _local_regular(root, PROJECTION_INDEX, "projection index")
    projection_revision, _, owner_state, owners = _projection_metadata(
        root / PROJECTION_INDEX
    )
    if owner_state == "dirty":
        raise ValueError("projection was built from a dirty owner worktree")
    reasons = _owner_reasons(root, owners, missing_is_change=True)
    head = _head(root)
    if _tree_oid(root, projection_revision, "projection") != _tree_oid(
        root, head, "HEAD"
    ):
        reasons.append("projection source tree differs from HEAD")
    return reasons


def _graphify_interpreter(root: Path) -> str:
    marker = root / INTERPRETER
    _regular(marker, "Graphify interpreter marker")
    value = marker.read_text(encoding="utf-8").strip()
    candidate = Path(value)
    if not value or not candidate.is_absolute():
        raise ValueError("invalid Graphify interpreter marker")
    root = root.resolve()
    if candidate.is_absolute() and candidate.is_relative_to(root):
        raise ValueError("Graphify interpreter marker is inside repository")
    graphify = shutil.which("graphify")
    if graphify is None:
        raise ValueError("trusted Graphify CLI is unavailable")
    cli_path = Path(graphify).absolute()
    if cli_path.is_relative_to(root):
        raise ValueError("trusted Graphify CLI is inside repository")
    cli = cli_path.resolve(strict=True)
    if not cli.is_file() or not os.access(cli, os.X_OK):
        raise ValueError("trusted Graphify CLI is unsafe")
    try:
        shebang = cli.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, UnicodeDecodeError, IndexError) as error:
        raise ValueError("trusted Graphify CLI shebang is unavailable") from error
    if not shebang.startswith("#!"):
        raise ValueError("trusted Graphify CLI has no interpreter shebang")
    trusted = Path(shebang[2:].strip())
    if not trusted.is_absolute():
        raise ValueError("trusted Graphify CLI interpreter is not absolute")
    if trusted.is_relative_to(root):
        raise ValueError("trusted Graphify CLI interpreter is inside repository")
    try:
        trusted_canonical = trusted.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ValueError("trusted Graphify CLI interpreter is unavailable") from error
    if (
        trusted_canonical.is_relative_to(root)
        or not trusted.is_file()
        or not os.access(trusted, os.X_OK)
    ):
        raise ValueError("trusted Graphify CLI interpreter is unsafe")
    try:
        candidate = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ValueError("Graphify interpreter marker is unavailable") from error
    if candidate != trusted_canonical:
        raise ValueError("Graphify interpreter marker does not match trusted CLI")
    return str(trusted)


def _detect_incremental(
    root: Path, *, interpreter_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    interpreter = _graphify_interpreter(interpreter_root or root)
    manifest = (root / MANIFEST).resolve()
    _regular(manifest, "manifest")
    program = """
import json
import sys
from importlib.metadata import version
from pathlib import Path
from graphify.detect import detect_incremental
if version('graphifyy') != sys.argv[3]:
    raise RuntimeError('unexpected graphifyy version')
root = Path(sys.argv[1])
manifest = sys.argv[2]
kwargs = dict(
    manifest_path=manifest,
    follow_symlinks=False,
    google_workspace=False,
)
print(json.dumps({
    'ast': detect_incremental(root, kind='ast', **kwargs),
    'semantic': detect_incremental(root, kind='semantic', **kwargs),
}))
"""
    with tempfile.TemporaryDirectory(prefix="aria-graphify-freshness-") as output:
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in {"PYTHONPATH", "PYTHONHOME"}
        }
        env["GRAPHIFY_OUT"] = output
        result = subprocess.run(
            [
                interpreter,
                "-c",
                program,
                str(root.resolve()),
                str(manifest),
                PINNED_GRAPHIFY_VERSION,
            ],
            check=False,
            capture_output=True,
            text=True,
            env=env,
            cwd=output,
        )
    if result.returncode:
        raise ValueError(
            f"Graphify detector failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ValueError(f"Graphify detector returned invalid JSON: {error}") from error
    if not isinstance(payload, dict) or not all(
        isinstance(payload.get(kind), dict) for kind in ("ast", "semantic")
    ):
        raise ValueError("Graphify detector returned an invalid result")
    return payload["ast"], payload["semantic"]


def _raw_commit_snapshot(
    root: Path, commit: str, projection: Path
) -> tempfile.TemporaryDirectory[str]:
    """Materialize ``commit`` from Git blobs without applying worktree filters."""
    git_dir = subprocess.run(
        ["git", "rev-parse", "--absolute-git-dir"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if git_dir.returncode or not git_dir.stdout.strip():
        raise ValueError("Git administrative directory is unavailable")
    temporary_root = Path(git_dir.stdout.strip()).resolve()
    if not temporary_root.is_dir():
        raise ValueError("Git administrative directory is unavailable")
    temporary = tempfile.TemporaryDirectory(
        prefix="aria-graphify-head-", dir=temporary_root
    )
    snapshot = Path(temporary.name)
    result = subprocess.run(
        ["git", "ls-tree", "-r", "-z", "--full-tree", commit],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if result.returncode:
        temporary.cleanup()
        detail = result.stderr.decode(errors="replace").strip()
        raise ValueError(f"Git HEAD tree listing failed: {detail}")
    try:
        for entry in result.stdout.split(b"\0"):
            if not entry:
                continue
            header, separator, raw_path = entry.partition(b"\t")
            fields = header.split()
            if not separator or len(fields) != 3:
                raise ValueError("Git HEAD tree has an invalid entry")
            mode, kind, raw_object = fields
            if mode == b"120000" or (mode == b"160000" and kind == b"commit"):
                continue
            if mode not in {b"100644", b"100755"} or kind != b"blob":
                raise ValueError("Git HEAD tree contains an unsupported entry")
            object_id = raw_object.decode("ascii")
            relative = PurePosixPath(raw_path.decode("utf-8", errors="surrogateescape"))
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Git HEAD tree contains an unsafe path")
            target = snapshot / Path(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as output:
                blob = subprocess.run(
                    ["git", "cat-file", "blob", object_id],
                    cwd=root,
                    check=False,
                    stdout=output,
                    stderr=subprocess.PIPE,
                )
            if blob.returncode:
                detail = blob.stderr.decode(errors="replace").strip()
                raise ValueError(f"Git HEAD blob materialization failed: {detail}")
    except (OSError, UnicodeError, ValueError) as error:
        temporary.cleanup()
        raise ValueError(f"Git HEAD tree materialization failed: {error}") from error

    def copy_projection(source: Path, target: Path) -> None:
        if source.is_symlink() or not source.is_dir():
            raise ValueError("generated Graphify projection is missing or unsafe")
        for entry in source.rglob("*"):
            relative = entry.relative_to(source)
            destination = target / relative
            if entry.is_symlink():
                raise ValueError(
                    "generated Graphify projection contains unsafe entries"
                )
            if entry.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            if not entry.is_file():
                raise ValueError(
                    "generated Graphify projection contains unsafe entries"
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(entry.read_bytes())

    copy_projection(projection, snapshot / "graphify-input")
    manifest = root / MANIFEST
    _regular(manifest, "manifest")
    (snapshot / MANIFEST).parent.mkdir(parents=True, exist_ok=True)
    (snapshot / MANIFEST).write_bytes(manifest.read_bytes())
    graph = root / GRAPH
    _regular(graph, "graph")
    (snapshot / GRAPH).parent.mkdir(parents=True, exist_ok=True)
    (snapshot / GRAPH).write_bytes(graph.read_bytes())
    # Graphify preserves tracked files from .gitignore exclusions.  The raw
    # blob snapshot intentionally has no checkout index, so give it a private
    # index for exactly ``commit`` without consulting the mutable source index
    # or applying checkout filters.
    common = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    common_dir = Path(common.stdout.strip())
    objects = common_dir / "objects"
    if common.returncode or not common.stdout.strip() or not objects.is_dir():
        temporary.cleanup()
        raise ValueError("Git common object directory is unavailable")
    snapshot_env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("GIT_")
    }
    initialized = subprocess.run(
        ["git", "init", "-q", str(snapshot)],
        check=False,
        capture_output=True,
        text=True,
        env=snapshot_env,
    )
    if initialized.returncode:
        temporary.cleanup()
        raise ValueError(
            "Git HEAD snapshot index initialization failed: "
            f"{initialized.stderr.strip() or initialized.stdout.strip()}"
        )
    alternates = snapshot / ".git" / "objects" / "info" / "alternates"
    try:
        alternates.parent.mkdir(parents=True, exist_ok=True)
        alternates.write_text(f"{objects}\n", encoding="utf-8")
    except OSError as error:
        temporary.cleanup()
        raise ValueError(f"Git HEAD snapshot index initialization failed: {error}") from error
    indexed = subprocess.run(
        ["git", "-C", str(snapshot), "read-tree", commit],
        check=False,
        capture_output=True,
        text=True,
        env=snapshot_env,
    )
    if indexed.returncode:
        temporary.cleanup()
        raise ValueError(
            "Git HEAD snapshot index initialization failed: "
            f"{indexed.stderr.strip() or indexed.stdout.strip()}"
        )
    return temporary


def _detector_stale_sources(
    root: Path, ast: dict[str, Any], semantic: dict[str, Any]
) -> list[str]:
    stale: set[str] = set()
    supported_kinds = {"code", "document", "paper", "image", "video"}
    for result, accepted in (
        (ast, {"code"}),
        (semantic, {"document", "paper", "image"}),
    ):
        if result.get("scan_root") != str(root.resolve()):
            raise ValueError("Graphify detector reported an unexpected scan_root")
        for key in ("unclassified", "walk_errors", "skipped_sensitive"):
            values = result.get(key)
            if not isinstance(values, list):
                raise ValueError(f"Graphify detector has invalid {key}")
            if values:
                raise ValueError(f"Graphify detector reported {key}")
        files = result.get("new_files")
        if not isinstance(files, dict) or set(files) != supported_kinds:
            raise ValueError("Graphify detector has invalid new_files")
        for kind, paths in files.items():
            if not isinstance(paths, list) or any(
                not isinstance(path, str) for path in paths
            ):
                raise ValueError("Graphify detector has invalid source paths")
            if kind in accepted:
                stale.update(_contained_existing(root, path) for path in paths)
        for key in ("deleted_files", "excluded_files"):
            values = result.get(key)
            if not isinstance(values, list) or any(
                not isinstance(path, str) for path in values
            ):
                raise ValueError(f"Graphify detector has invalid {key}")
            if values:
                raise ValueError(f"Graphify detector reported {key}")
        files = result.get("files")
        if not isinstance(files, dict) or set(files) != supported_kinds:
            raise ValueError("Graphify detector has invalid files")
        for paths in files.values():
            if not isinstance(paths, list) or any(
                not isinstance(path, str) for path in paths
            ):
                raise ValueError("Graphify detector has invalid source paths")
        video = files["video"]
        if video:
            raise ValueError("Graphify detector reported unsupported video sources")
    if len(stale) > MAX_STALE_SOURCES:
        raise ValueError("Graphify detector reported an unbounded stale-source set")
    return sorted(stale)


def _detector_sources(
    root: Path, result: dict[str, Any], accepted: set[str]
) -> tuple[set[str], dict[str, list[str]]]:
    """Validate one upstream detector result and return its accepted deltas."""
    supported_kinds = {"code", "document", "paper", "image", "video"}
    if result.get("scan_root") != str(root.resolve()):
        raise ValueError("Graphify detector reported an unexpected scan_root")
    for key in ("unclassified", "walk_errors", "skipped_sensitive"):
        values = result.get(key)
        if not isinstance(values, list):
            raise ValueError(f"Graphify detector has invalid {key}")
        if values:
            raise ValueError(f"Graphify detector reported {key}")
    new_files = result.get("new_files")
    if not isinstance(new_files, dict) or set(new_files) != supported_kinds:
        raise ValueError("Graphify detector has invalid new_files")
    stale: set[str] = set()
    for kind, paths in new_files.items():
        if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
            raise ValueError("Graphify detector has invalid source paths")
        if kind in accepted:
            stale.update(_contained_existing(root, path) for path in paths)
    for key in ("deleted_files", "excluded_files"):
        values = result.get(key)
        if not isinstance(values, list) or any(not isinstance(path, str) for path in values):
            raise ValueError(f"Graphify detector has invalid {key}")
        if values:
            raise ValueError(f"Graphify detector reported {key}")
    files = result.get("files")
    if not isinstance(files, dict) or set(files) != supported_kinds:
        raise ValueError("Graphify detector has invalid files")
    for paths in files.values():
        if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
            raise ValueError("Graphify detector has invalid source paths")
    if files["video"]:
        raise ValueError("Graphify detector reported unsupported video sources")
    return stale, files


def _result(
    state: str,
    head: str | None,
    graph_revision: str | None,
    stale_sources: list[str],
    reasons: list[str],
    next_action: str | None = None,
) -> dict[str, Any]:
    fresh = state == "fresh"
    usable = state in {"fresh", "usable-stale"}
    if next_action is None:
        if fresh:
            next_action = FRESH_ACTION
        elif usable:
            next_action = STALE_ACTION
        else:
            next_action = UNUSABLE_ACTION
    return {
        "state": state,
        "fresh": fresh,
        "usable": usable,
        "head": head,
        "graph_revision": graph_revision,
        "stale_sources": stale_sources,
        "reasons": reasons,
        "next_action": next_action,
    }


def check(root: Path) -> dict[str, Any]:
    root = root.resolve()
    reasons: list[str] = []
    next_action: str | None = None
    try:
        head = _head(root)
        projection_index = _local_regular(root, PROJECTION_INDEX, "projection index")
        root_marker = _local_regular(root, ROOT_MARKER, "Graphify root marker")
        try:
            marker_value = root_marker.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise ValueError(f"invalid Graphify root marker: {error}") from error
        if marker_value not in {str(root), f"{root}\n"}:
            raise ValueError("Graphify root marker is not bound to this worktree")
        for relative, label in (
            (GRAPH, "graph"),
            (MANIFEST, "manifest"),
            (INTERPRETER, "Graphify interpreter marker"),
        ):
            _local_regular(root, relative, label)
        projection_revision, projection_tree, owner_state, owners = (
            _projection_metadata(projection_index)
        )
        graph_revision = _graph_revision(root)
        pending = root / NEEDS_UPDATE
        if pending.exists() or pending.is_symlink():
            _regular(pending, "Graphify semantic refresh marker")
            reasons.append("semantic refresh required: graphify-out/needs_update exists")
        if owner_state == "dirty":
            raise ValueError("projection was built from a dirty owner worktree")
        reasons.extend(_owner_reasons(root, owners))
        head_tree = _tree_oid(root, head, "HEAD")
        projection_commit_tree = _tree_oid(root, projection_revision, "projection")
        if projection_tree is not None and projection_commit_tree != projection_tree:
            raise ValueError(
                "projection source_tree does not match source_revision tree"
            )
        projection_ancestor = _is_ancestor(root, projection_revision, head)
        graph_ancestor = _is_ancestor(root, graph_revision, head)
        graph_commit_tree = _tree_oid(root, graph_revision, "graph")
        ast, semantic = _detect_incremental(root)
        ast_stale, _ = _detector_sources(root, ast, {"code"})
        semantic_stale, _ = _detector_sources(
            root, semantic, {"document", "paper", "image"}
        )
        ast_refresh_required = bool(ast_stale)
        if len(ast_stale) > MAX_STALE_SOURCES:
            raise ValueError("Graphify detector reported an unbounded stale-source set")
        if len(semantic_stale) > MAX_STALE_SOURCES:
            raise ValueError("Graphify detector reported an unbounded stale-source set")
        overlay_stale = sorted(ast_stale | semantic_stale)
        committed_stale: list[str] = []
        if projection_commit_tree != head_tree or graph_commit_tree != head_tree:
            snapshot = _raw_commit_snapshot(
                root, head, root / PROJECTION_INDEX.parent
            )
            try:
                committed_ast, committed_semantic = _detect_incremental(
                    Path(snapshot.name), interpreter_root=root
                )
                snapshot_root = Path(snapshot.name)
                committed_ast_stale, _ = _detector_sources(
                    snapshot_root, committed_ast, {"code"}
                )
                committed_semantic_stale, _ = _detector_sources(
                    snapshot_root,
                    committed_semantic,
                    {"document", "paper", "image"},
                )
                if len(committed_ast_stale) > MAX_STALE_SOURCES:
                    raise ValueError(
                        "Graphify detector reported an unbounded stale-source set"
                    )
                if len(committed_semantic_stale) > MAX_STALE_SOURCES:
                    raise ValueError(
                        "Graphify detector reported an unbounded stale-source set"
                    )
                committed_stale = sorted(
                    committed_ast_stale | committed_semantic_stale
                )
            finally:
                snapshot.cleanup()
        stale_sources = sorted(set(overlay_stale) | set(committed_stale))
    except ValueError as error:
        if isinstance(error, _MissingGitObjectError):
            next_action = GIT_OBJECT_REPAIR_COMMAND
        return _result(
            "unusable",
            locals().get("head"),
            locals().get("graph_revision"),
            [],
            [*reasons, str(error)],
            next_action,
        )
    if (
        committed_stale
        and (not projection_ancestor or not graph_ancestor)
    ):
        return _result(
            "unusable",
            head,
            graph_revision,
            stale_sources,
            [*reasons, "non-ancestor Graphify corpus differs from HEAD"],
            STALE_ACTION,
        )
    if ast_refresh_required:
        return _result(
            "unusable",
            head,
            graph_revision,
            stale_sources,
            [*reasons, "Graphify AST refresh required"],
            STALE_ACTION,
        )
    if reasons or stale_sources:
        return _result("usable-stale", head, graph_revision, stale_sources, reasons)
    return _result("fresh", head, graph_revision, stale_sources, reasons)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--quiet", action="store_true")
    output.add_argument("--json", action="store_true")
    parser.add_argument("--usable", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = check(Path.cwd())
    except Exception as error:
        result = _result(
            "unusable", None, None, [], [f"unexpected freshness-check failure: {error}"]
        )
    if not args.quiet:
        if args.json:
            print(json.dumps(result, sort_keys=True))
        else:
            print(
                f"Graphify freshness: {result['state']} — {'; '.join(result['reasons']) or 'all checks pass'}"
            )
            print(f"Next action: {result['next_action']}")
    return 0 if (result["usable"] if args.usable else result["fresh"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
