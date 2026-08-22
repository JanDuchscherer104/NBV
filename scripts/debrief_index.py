#!/usr/bin/env python3
"""Build and validate the deterministic navigation index for debriefs.

The Markdown files under .agents/memory/history remain the evidence owner.
This module only projects their small frontmatter into byte-stable JSONL rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORY_PREFIX = ".agents/memory/history/"
INDEX_PATH = REPO_ROOT / ".agents" / "memory" / "index" / "debriefs.jsonl"
REPO_OBJECT_FORMAT_OID_LENGTHS = {"sha1": 40, "sha256": 64}
WORKTREE_KINDS = {"primary", "linked"}


def is_full_repo_oid(value: str, object_format: str) -> bool:
    """Return whether an OID matches its recorded Git object format."""
    length = REPO_OBJECT_FORMAT_OID_LENGTHS.get(object_format)
    return (
        length is not None
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def visible_history_paths(root: Path = REPO_ROOT) -> list[Path]:
    """Return existing visible tracked or untracked Markdown history files."""
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            HISTORY_PREFIX,
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    paths = {
        root / relative
        for relative in result.stdout.splitlines()
        if relative.startswith(HISTORY_PREFIX) and relative.endswith(".md")
    }
    visible: list[Path] = []
    history_root = root.resolve() / ".agents" / "memory" / "history"
    for path in sorted(paths, key=lambda candidate: candidate.as_posix()):
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            raise ValueError(
                f"symlinked debrief source is not allowed: {_source_path(path, root)}"
            )
        try:
            path.resolve().relative_to(history_root)
        except ValueError as exc:
            raise ValueError(
                f"debrief source resolves outside history: {_source_path(path, root)}"
            ) from exc
        if not stat.S_ISREG(mode):
            raise ValueError(
                f"debrief source must be a regular file: {_source_path(path, root)}"
            )
        visible.append(path)
    return visible


def _source_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _list_value(frontmatter: dict[str, object], key: str) -> list[str]:
    value = frontmatter.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list")
    return [str(item) for item in value]


def _touched_owner_paths(frontmatter: dict[str, object]) -> list[str]:
    if "touched_owner_paths" in frontmatter:
        return _list_value(frontmatter, "touched_owner_paths")
    legacy = _list_value(frontmatter, "files_touched")
    return [
        item.removeprefix("path: ").strip()
        for item in legacy
        if item.removeprefix("path: ").strip()
    ]


def row_for_path(path: Path, root: Path = REPO_ROOT) -> dict[str, Any]:
    """Render one source file through the canonical validator frontmatter parser."""
    from validate_agent_memory import parse_frontmatter

    content = path.read_bytes()
    frontmatter = parse_frontmatter(path)
    row: dict[str, Any] = {
        "source_path": _source_path(path, root),
        "source_sha256": hashlib.sha256(content).hexdigest(),
        "id": str(frontmatter.get("id", "")),
        "date": str(frontmatter.get("date", "")),
        "status": str(frontmatter.get("status", "")),
        "topics": _list_value(frontmatter, "topics"),
        "confidence": str(frontmatter.get("confidence", "")),
        "canonical_update_paths": _list_value(frontmatter, "canonical_updates_needed"),
        "touched_owner_paths": _touched_owner_paths(frontmatter),
        "codex_thread": None,
    }
    if "codex_thread" in frontmatter:
        codex_thread = frontmatter["codex_thread"]
        if not isinstance(codex_thread, str):
            raise ValueError("codex_thread must be a string when present")
        row["codex_thread"] = codex_thread

    provenance_keys = (
        "repo_object_format",
        "repo_head",
        "repo_branch",
        "worktree_kind",
    )
    provenance = {
        key: str(frontmatter[key]) for key in provenance_keys if key in frontmatter
    }
    if provenance:
        row["checkout_provenance"] = provenance
    return row


def render_index(root: Path = REPO_ROOT) -> bytes:
    """Return canonical JSONL for every visible history Markdown file."""
    rows = [row_for_path(path, root) for path in visible_history_paths(root)]
    rows.sort(key=lambda row: (row["source_path"].encode(), row["id"].encode()))
    return b"".join(
        (
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        for row in rows
    )


def check_index(root: Path = REPO_ROOT, index_path: Path | None = None) -> list[str]:
    """Return errors when the checked-in index differs from current sources."""
    target = index_path or root / ".agents" / "memory" / "index" / "debriefs.jsonl"
    try:
        expected = render_index(root)
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        return [f"cannot render debrief index: {exc}"]
    if not target.exists():
        return [f"missing debrief index: {target.relative_to(root).as_posix()}"]
    try:
        actual = target.read_bytes()
    except OSError as exc:
        return [f"cannot read debrief index: {exc}"]
    try:
        _parse_index(actual)
    except (KeyError, TypeError, UnicodeDecodeError, ValueError) as exc:
        return [f"malformed debrief index: {exc}"]
    if actual != expected:
        return [
            f"stale debrief index: regenerate {target.relative_to(root).as_posix()}"
        ]
    return []


def _parse_index(content: bytes) -> list[dict[str, Any]]:
    scalar_fields = {
        "source_path",
        "source_sha256",
        "id",
        "date",
        "status",
        "confidence",
    }
    list_fields = {"topics", "canonical_update_paths", "touched_owner_paths"}
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        value = json.loads(line)
        if not isinstance(value, dict):
            raise TypeError(f"line {line_number} must be a JSON object")
        missing = sorted((scalar_fields | list_fields) - value.keys())
        if missing:
            raise KeyError(f"line {line_number} missing fields: {', '.join(missing)}")
        for field in scalar_fields:
            if not isinstance(value[field], str):
                raise TypeError(f"line {line_number} {field} must be a string")
        for field in list_fields:
            if not isinstance(value[field], list) or not all(
                isinstance(item, str) for item in value[field]
            ):
                raise TypeError(f"line {line_number} {field} must be a string list")
        codex_thread = value.get("codex_thread")
        if codex_thread is not None and not isinstance(codex_thread, str):
            raise TypeError(f"line {line_number} codex_thread must be a string or null")
        if "codex_thread" not in value:
            raise KeyError(f"line {line_number} missing fields: codex_thread")
        provenance = value.get("checkout_provenance")
        if provenance is not None:
            if not isinstance(provenance, dict):
                raise TypeError(
                    f"line {line_number} checkout_provenance must be an object"
                )
            provenance_fields = {
                "repo_object_format",
                "repo_head",
                "repo_branch",
                "worktree_kind",
            }
            missing_provenance = sorted(provenance_fields - provenance.keys())
            if missing_provenance:
                raise KeyError(
                    f"line {line_number} checkout_provenance missing fields: "
                    f"{', '.join(missing_provenance)}"
                )
            if not all(
                isinstance(provenance[field], str) for field in provenance_fields
            ):
                raise TypeError(
                    f"line {line_number} checkout_provenance fields must be strings"
                )
            object_format = provenance["repo_object_format"]
            repo_head = provenance["repo_head"]
            if not is_full_repo_oid(repo_head, object_format):
                raise ValueError(
                    f"line {line_number} checkout_provenance repo_head does not "
                    "match repo_object_format"
                )
            if not provenance["repo_branch"]:
                raise ValueError(
                    f"line {line_number} checkout_provenance repo_branch is empty"
                )
            if provenance["worktree_kind"] not in WORKTREE_KINDS:
                raise ValueError(
                    f"line {line_number} checkout_provenance worktree_kind is invalid"
                )
        source_path = value["source_path"]
        relative = PurePosixPath(source_path)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not source_path.startswith(HISTORY_PREFIX)
        ):
            raise ValueError(f"line {line_number} has unsafe source_path")
        rows.append(value)
    return rows


def _safe_source_path(root: Path, source_path: str) -> Path:
    relative = PurePosixPath(source_path)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or not source_path.startswith(HISTORY_PREFIX)
    ):
        raise ValueError(f"unsafe debrief source path: {source_path}")
    history_root = root.resolve() / ".agents" / "memory" / "history"
    candidate = (root / Path(*relative.parts)).resolve()
    try:
        candidate.relative_to(history_root)
    except ValueError as exc:
        raise ValueError(f"debrief source path escapes history: {source_path}") from exc
    if not candidate.is_file():
        raise ValueError(f"debrief source is not a file: {source_path}")
    return candidate


def _query(root: Path, query: str) -> int:
    """Print the original Markdown source selected by an index id or path."""
    index_path = root / ".agents" / "memory" / "index" / "debriefs.jsonl"
    query_path = PurePosixPath(query)
    if (
        query_path.is_absolute()
        or ".." in query_path.parts
        or ("/" in query and not query.startswith(HISTORY_PREFIX))
    ):
        print(f"unsafe debrief query path: {query}", file=sys.stderr)
        return 1
    errors = check_index(root, index_path)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    rows = _parse_index(index_path.read_bytes())
    for row in rows:
        if query in {row["id"], row["source_path"]}:
            try:
                source = _safe_source_path(root, row["source_path"])
            except ValueError as exc:
                print(exc, file=sys.stderr)
                return 1
            print(source.read_text(encoding="utf-8"), end="")
            return 0
    print(f"debrief not found in index: {query}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate the index")
    parser.add_argument("--query", metavar="ID_OR_PATH", help="print source Markdown")
    args = parser.parse_args()
    if args.query:
        return _query(REPO_ROOT, args.query)
    if args.check:
        errors = check_index()
        for error in errors:
            print(error, file=sys.stderr)
        return int(bool(errors))
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_bytes(render_index())
    print(INDEX_PATH.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
