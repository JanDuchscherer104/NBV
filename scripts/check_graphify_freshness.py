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
NEEDS_UPDATE = Path("graphify-out/needs_update")
INDEX_PATH = "graphify-input/index.md"
_FRONTMATTER_DELIM = re.compile(r"^---[ \t]*\r?$", re.MULTILINE)


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


def _json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"invalid {label}: expected a JSON object")
    return value


def _source_revision(index: Path) -> str:
    try:
        text = index.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ValueError(f"invalid projection index: {error}") from error
    values = [
        line.split(":", 1)[1].strip()
        for line in text.splitlines()
        if line.startswith("source_revision:")
    ]
    if len(values) != 1 or not values[0]:
        raise ValueError(
            "invalid projection index: source_revision must be one non-empty string"
        )
    return values[0]


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
    )
    for relative, label in paths:
        if not (root / relative).is_file():
            missing = True
            reasons.append(f"missing {label}: {relative.as_posix()}")

    projection_revision: str | None = None
    graph: dict[str, Any] | None = None
    digest: str | None = None
    node_present: bool | None = None
    if (root / PROJECTION_INDEX).is_file():
        try:
            projection_revision = _source_revision(root / PROJECTION_INDEX)
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

    if head is not None:
        if projection_revision is not None and projection_revision != head:
            reasons.append("projection source_revision does not match HEAD")
        if graph is not None and graph["built_at_commit"] != head:
            reasons.append("graph built_at_commit does not match HEAD")
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
    return {
        "state": state,
        "fresh": fresh,
        "head": head,
        "reasons": reasons,
        "next_action": (
            "graph-backed claims are permitted"
            if fresh
            else "use exact-source discovery; run an explicit Graphify refresh before graph-backed claims"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--quiet", action="store_true", help="emit no output")
    output.add_argument("--json", action="store_true", help="emit stable JSON")
    args = parser.parse_args(argv)
    try:
        result = check(Path.cwd())
    except Exception as error:  # Defensive outer fail-closed boundary.
        result = {
            "state": "invalid",
            "fresh": False,
            "head": None,
            "reasons": [f"unexpected freshness-check failure: {error}"],
            "next_action": "use exact-source discovery; run an explicit Graphify refresh before graph-backed claims",
        }
    if not args.quiet:
        if args.json:
            print(json.dumps(result, sort_keys=True))
        else:
            reasons = "; ".join(result["reasons"]) or "all freshness predicates pass"
            print(f"Graphify freshness: {result['state']} — {reasons}")
            print(f"Next action: {result['next_action']}")
    return 0 if result["fresh"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
