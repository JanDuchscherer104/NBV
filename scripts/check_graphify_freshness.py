#!/usr/bin/env python3
"""Fail-closed freshness check for the optional local Graphify artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Any


PROJECTION_INDEX = Path("graphify-input/index.md")
GRAPH = Path("graphify-out/graph.json")
STAT_INDEX = Path("graphify-out/cache/stat-index.json")
MANIFEST = Path("graphify-out/manifest.json")
NEEDS_UPDATE = Path("graphify-out/needs_update")
INDEX_PATH = "graphify-input/index.md"
_FRONTMATTER_DELIM = re.compile(r"^---[ \t]*\r?$", re.MULTILINE)
_OWNER_DIGEST = re.compile(r"^- ([^:\r\n]+): sha256:([0-9a-f]{64})\r?$")
_NATIVE_TEXT_SUFFIXES = {".html", ".md", ".py", ".qmd", ".rst", ".txt", ".yaml", ".yml"}
_DOC_TEXT_SUFFIXES = _NATIVE_TEXT_SUFFIXES - {".py"}
_NOISE_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}


def _head(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip()
    if result.returncode or not value:
        raise ValueError("current Git HEAD is unavailable")
    return value


def _is_ancestor(root: Path, older: str, newer: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"invalid {label}: expected a JSON object")
    return value


def _projection_metadata(index: Path) -> tuple[str, str, dict[str, str]]:
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
    owner_state = single_value("owner_worktree_state")
    if owner_state not in {"clean", "dirty"}:
        raise ValueError(
            "invalid projection index: owner_worktree_state must be clean or dirty"
        )

    lines = text.splitlines()
    try:
        section_start = lines.index("## Owner digests") + 1
    except ValueError as error:
        raise ValueError("invalid projection index: missing Owner digests") from error
    owner_digests: dict[str, str] = {}
    for line in lines[section_start:]:
        if line.startswith("## "):
            break
        if not line.strip():
            continue
        match = _OWNER_DIGEST.fullmatch(line)
        if match is None:
            raise ValueError(f"invalid projection index owner digest: {line}")
        owner, digest = match.groups()
        normalized = _normalize_path(owner)
        if normalized in owner_digests:
            raise ValueError(f"invalid projection index: duplicate owner {normalized}")
        owner_digests[normalized] = digest
    if not owner_digests:
        raise ValueError("invalid projection index: Owner digests must not be empty")
    return revision, owner_state, owner_digests


def _normalize_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", normalized):
        raise ValueError("unsafe source path")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("unsafe source path")
    result = path.as_posix()
    while result.startswith("./"):
        result = result[2:]
    return result


def _upstream_file_hash(content: bytes, relative_path: str) -> str:
    """Reproduce Graphify 0.9.31's content-plus-relative-path digest."""
    text = content.decode(errors="replace")
    opener = _FRONTMATTER_DELIM.match(text)
    if opener is not None:
        closer = _FRONTMATTER_DELIM.search(text, opener.end())
        if closer is not None:
            content = text[closer.start() + 3 :].encode()
    digest = hashlib.sha256()
    digest.update(content)
    digest.update(b"\x00")
    digest.update(relative_path.lower().encode())
    return digest.hexdigest()


def _index_digest(stat_index: dict[str, Any]) -> str:
    entry = stat_index.get(INDEX_PATH)
    if not isinstance(entry, dict):
        raise ValueError(
            "invalid stat index: missing object entry for graphify-input/index.md"
        )
    hashes = entry.get("hashes")
    if not isinstance(hashes, dict):
        raise ValueError("invalid stat index: index hashes must be an object")
    digest = hashes.get(INDEX_PATH)
    if not isinstance(digest, str) or not digest:
        raise ValueError("invalid stat index: index digest must be a non-empty string")
    return digest


def _manifest_drift(root: Path, manifest: dict[str, Any]) -> list[str]:
    """Return indexed paths whose current bytes differ from the manifest."""
    stale: list[str] = []
    repository = root.resolve()
    for raw_path, raw_entry in sorted(manifest.items()):
        if not isinstance(raw_path, str):
            raise ValueError("invalid manifest: source path must be a string")
        relative = _normalize_path(raw_path)
        source = repository / relative
        try:
            resolved = source.resolve(strict=False)
        except (OSError, RuntimeError) as error:
            raise ValueError(
                f"manifest source cannot be resolved: {relative}: {error}"
            ) from error
        if not resolved.is_relative_to(repository):
            raise ValueError(f"manifest source escapes repository: {relative}")
        if not resolved.is_file():
            stale.append(relative)
            continue
        if not isinstance(raw_entry, dict):
            raise ValueError(f"invalid manifest entry: {relative}")
        expected = (
            raw_entry.get("semantic_hash")
            or raw_entry.get("ast_hash")
            or raw_entry.get("hash")
        )
        if not isinstance(expected, str) or not expected:
            stale.append(relative)
            continue
        digest = hashlib.md5(resolved.read_bytes(), usedforsecurity=False).hexdigest()
        if digest != expected:
            stale.append(relative)
    return stale


def _fallback_graphify_admitted(relative: str) -> bool:
    """Mirror the stable root corpus policy when Graphify is not importable."""
    path = PurePosixPath(relative)
    parts = path.parts
    if not parts or any(part in _NOISE_PARTS for part in parts):
        return False
    if relative == "AGENTS.md":
        return True
    if parts[0] == "aria_nbv":
        if len(parts) > 1 and parts[1] in {"tests", "scripts", ".omc", ".venv"}:
            return False
        return path.suffix in _NATIVE_TEXT_SUFFIXES
    if parts[0] == "docs":
        excluded = {
            "_build",
            "_extensions",
            "_freeze",
            "_generated",
            "_inv",
            "_site",
            "literature/pdf",
            "literature/tex-src",
            "reference",
            "site_libs",
        }
        scoped = "/".join(parts[1:3])
        if len(parts) > 1 and (parts[1] in excluded or scoped in excluded):
            return False
        return path.suffix in _DOC_TEXT_SUFFIXES
    if parts[:2] == (".agents", "references"):
        return path.suffix == ".md"
    if parts[:3] == (".agents", "memory", "state"):
        return path.suffix == ".md"
    if len(parts) == 4 and parts[:2] == (".agents", "skills"):
        return parts[-1] == "SKILL.md"
    if parts[0] == "graphify-input":
        return path.suffix == ".md"
    return False


def _unindexed_sources(root: Path, manifest: dict[str, Any]) -> list[str]:
    """Return currently admitted Graphify inputs absent from the manifest."""
    indexed = {_normalize_path(path) for path in manifest}
    try:
        from graphify.detect import detect
    except ImportError:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=root,
            check=False,
            capture_output=True,
        )
        if result.returncode:
            raise ValueError("tracked source inventory is unavailable")
        admitted = {
            _normalize_path(raw.decode("utf-8", errors="surrogateescape"))
            for raw in result.stdout.split(b"\0")
            if raw
            and _fallback_graphify_admitted(
                _normalize_path(raw.decode("utf-8", errors="surrogateescape"))
            )
        }
    else:
        detection = detect(root)
        admitted = set()
        repository = root.resolve()
        for paths in detection.get("files", {}).values():
            for raw_path in paths:
                try:
                    relative = Path(raw_path).resolve().relative_to(repository)
                except (OSError, RuntimeError, ValueError) as error:
                    raise ValueError(
                        f"detected source escapes repository: {raw_path}: {error}"
                    ) from error
                admitted.add(_normalize_path(relative.as_posix()))
    return sorted(admitted - indexed)


def _contains_index_node(graph: dict[str, Any]) -> bool:
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("invalid graph: nodes must be a list")
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("invalid graph: node must be an object")
        source = node.get("source_file")
        if source is None:
            continue
        if not isinstance(source, str):
            raise ValueError("invalid graph: node source_file must be a string")
        if _normalize_path(source) == INDEX_PATH:
            return True
    return False


def _live_owner_drift(
    root: Path, owner_digests: dict[str, str]
) -> tuple[list[str], list[str]]:
    reasons: list[str] = []
    stale: list[str] = []
    repository = root.resolve()
    owners = sorted(owner_digests)
    for relative in owners:
        owner = repository / relative
        try:
            resolved = owner.resolve(strict=False)
        except (OSError, RuntimeError) as error:
            raise ValueError(
                f"projection owner cannot be resolved: {relative}: {error}"
            )
        if not resolved.is_relative_to(repository):
            raise ValueError(f"projection owner escapes repository: {relative}")
        if not resolved.is_file():
            reasons.append(f"projection owner is missing: {relative}")
            stale.append(relative)
            continue
        try:
            digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
        except OSError as error:
            raise ValueError(f"projection owner cannot be read: {relative}: {error}")
        if digest != owner_digests[relative]:
            reasons.append(f"projection owner digest changed: {relative}")
            stale.append(relative)

    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all", "--", *owners],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise ValueError("projection owner worktree status is unavailable")
    if result.stdout.strip():
        reasons.append("projection owner worktree is dirty")
    return reasons, stale


def check(root: Path) -> dict[str, Any]:
    """Return the stable freshness result without printing or exiting."""
    reasons: list[str] = []
    invalid = False
    missing = False

    try:
        head = _head(root)
    except ValueError as error:
        head = None
        invalid = True
        reasons.append(str(error))

    paths = (
        (PROJECTION_INDEX, "projection index"),
        (GRAPH, "graph"),
        (STAT_INDEX, "stat index"),
        (MANIFEST, "manifest"),
    )
    for relative, label in paths:
        if not (root / relative).is_file():
            missing = True
            reasons.append(f"missing {label}: {relative.as_posix()}")

    projection_revision: str | None = None
    owner_worktree_state: str | None = None
    owner_digests: dict[str, str] | None = None
    graph: dict[str, Any] | None = None
    graph_revision: str | None = None
    manifest: dict[str, Any] | None = None
    digest: str | None = None
    node_present: bool | None = None
    if (root / PROJECTION_INDEX).is_file():
        try:
            (
                projection_revision,
                owner_worktree_state,
                owner_digests,
            ) = _projection_metadata(root / PROJECTION_INDEX)
        except ValueError as error:
            invalid = True
            reasons.append(str(error))
    if (root / GRAPH).is_file():
        try:
            graph = _json_object(root / GRAPH, "graph")
            built_at_commit = graph.get("built_at_commit")
            if not isinstance(built_at_commit, str) or not built_at_commit:
                raise ValueError(
                    "invalid graph: built_at_commit must be a non-empty string"
                )
            graph_revision = built_at_commit
            node_present = _contains_index_node(graph)
        except ValueError as error:
            invalid = True
            reasons.append(str(error))
    if (root / STAT_INDEX).is_file():
        try:
            digest = _index_digest(_json_object(root / STAT_INDEX, "stat index"))
        except ValueError as error:
            invalid = True
            reasons.append(str(error))
    if (root / MANIFEST).is_file():
        try:
            manifest = _json_object(root / MANIFEST, "manifest")
        except ValueError as error:
            invalid = True
            reasons.append(str(error))

    stale_sources: list[str] = []
    if head is not None:
        if (
            projection_revision is not None
            and projection_revision != head
            and not _is_ancestor(root, projection_revision, head)
        ):
            reasons.append("projection source_revision is not an ancestor of HEAD")
        if owner_worktree_state == "dirty":
            reasons.append("projection was built from a dirty owner worktree")
        if owner_digests is not None:
            try:
                owner_reasons, stale_owners = _live_owner_drift(root, owner_digests)
                reasons.extend(owner_reasons)
                stale_sources.extend(stale_owners)
            except ValueError as error:
                invalid = True
                reasons.append(str(error))
        if (
            graph_revision is not None
            and graph_revision != head
            and not _is_ancestor(root, graph_revision, head)
        ):
            reasons.append("graph built_at_commit is not an ancestor of HEAD")
        if manifest is not None:
            try:
                stale_sources.extend(_manifest_drift(root, manifest))
                stale_sources.extend(_unindexed_sources(root, manifest))
            except ValueError as error:
                invalid = True
                reasons.append(str(error))
            stale_sources = sorted(set(stale_sources))
            if stale_sources:
                reasons.append(
                    f"{len(stale_sources)} source(s) differ from or are absent from the Graphify manifest"
                )
        if (root / PROJECTION_INDEX).is_file() and digest is not None:
            actual_digest = _upstream_file_hash(
                (root / PROJECTION_INDEX).read_bytes(), INDEX_PATH
            )
        else:
            actual_digest = None
        if actual_digest is not None and digest != actual_digest:
            reasons.append("projection index digest does not match stat index")
        if node_present is False:
            reasons.append("graph has no node sourced from graphify-input/index.md")

    semantic_stale = (root / NEEDS_UPDATE).exists()
    if semantic_stale:
        reasons.append("semantic refresh required: graphify-out/needs_update exists")

    if invalid:
        state = "invalid"
    elif missing:
        state = "missing"
    elif semantic_stale:
        state = "semantic-stale"
    elif reasons:
        state = "structural-stale"
    else:
        state = "fresh"

    fresh = state == "fresh"
    usable = state not in {"invalid", "missing"}
    return {
        "state": state,
        "fresh": fresh,
        "usable": usable,
        "head": head,
        "graph_revision": graph_revision,
        "stale_sources": stale_sources,
        "reasons": reasons,
        "next_action": (
            "query Graphify first; validate consequential claims at source_location"
            if fresh
            else (
                "query Graphify first; verify stale source_location paths directly and refresh before strict scaffold validation"
                if usable
                else "repair or rebuild Graphify before graph queries"
            )
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--quiet", action="store_true", help="emit no output")
    output.add_argument("--json", action="store_true", help="emit stable JSON")
    parser.add_argument(
        "--usable",
        action="store_true",
        help="succeed for a structurally valid graph even when refresh is pending",
    )
    parser.add_argument(
        "--optional",
        action="store_true",
        help="also succeed when no local Graphify snapshot exists",
    )
    args = parser.parse_args(argv)
    try:
        result = check(Path.cwd())
    except Exception as error:  # Defensive outer fail-closed boundary.
        result = {
            "state": "invalid",
            "fresh": False,
            "usable": False,
            "head": None,
            "graph_revision": None,
            "stale_sources": [],
            "reasons": [f"unexpected freshness-check failure: {error}"],
            "next_action": "repair or rebuild Graphify before graph queries",
        }
    if not args.quiet:
        if args.json:
            print(json.dumps(result, sort_keys=True))
        else:
            reasons = "; ".join(result["reasons"]) or "all freshness predicates pass"
            print(f"Graphify freshness: {result['state']} — {reasons}")
            print(f"Next action: {result['next_action']}")
    success = result["usable"] if args.usable else result["fresh"]
    if args.optional and result["state"] == "missing":
        success = True
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
