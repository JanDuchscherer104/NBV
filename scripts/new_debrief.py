#!/usr/bin/env python3
"""Scaffold a dated agent debrief under .agents/memory/history/YYYY/MM/.

The frontmatter follows .agents/memory/README.md exactly:
required keys are id, date, title, status, topics, confidence,
canonical_updates_needed, and codex_thread. Dates are absolute ISO strings —
never relative.

Usage:
    scripts/new_debrief.py "<short title>" --thread-id "<thread-id>"
    make new-debrief TITLE="<short title>" CODEX_THREAD_ID="<thread-id>"
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORY_ROOT = REPO_ROOT / ".agents" / "memory" / "history"
CODEX_THREAD_ID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)
FULL_OID_PATTERN = re.compile(r"[0-9a-f]{40}")


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", title.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not slug:
        raise SystemExit("title must contain at least one alphanumeric character")
    return slug


def git_provenance() -> dict[str, str]:
    """Return portable Git identity or fail closed when it is unavailable."""
    commands = {
        "repo_head": ["git", "rev-parse", "--verify", "HEAD"],
        "repo_branch": ["git", "symbolic-ref", "--short", "-q", "HEAD"],
        "git_dir": ["git", "rev-parse", "--git-dir"],
        "git_common_dir": ["git", "rev-parse", "--git-common-dir"],
    }
    values: dict[str, str] = {}
    for key, command in commands.items():
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            if key == "repo_branch":
                values[key] = "detached"
                continue
            raise SystemExit(f"Git provenance unavailable: {' '.join(command)}")
        values[key] = result.stdout.strip()
    if not FULL_OID_PATTERN.fullmatch(values["repo_head"]):
        raise SystemExit("Git provenance unavailable: HEAD is not a full OID")
    if not values["repo_branch"]:
        values["repo_branch"] = "detached"
    git_dir = Path(values.pop("git_dir"))
    common_dir = Path(values.pop("git_common_dir"))
    if not git_dir.is_absolute():
        git_dir = (REPO_ROOT / git_dir).resolve()
    else:
        git_dir = git_dir.resolve()
    if not common_dir.is_absolute():
        common_dir = (REPO_ROOT / common_dir).resolve()
    else:
        common_dir = common_dir.resolve()
    values["worktree_kind"] = "primary" if git_dir == common_dir else "linked"
    return values


def render(
    today: date, title: str, codex_thread_id: str, provenance: dict[str, str]
) -> tuple[Path, str]:
    slug = slugify(title)
    target_dir = HISTORY_ROOT / f"{today.year:04d}" / f"{today.month:02d}"
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"{today.isoformat()}_{slug}.md"
    record_id = f"{today.isoformat()}_{slug}"
    body = f"""---
id: {record_id}
date: {today.isoformat()}
title: "{title}"
status: done
topics: []
confidence: high
canonical_updates_needed: []
touched_owner_paths: []
codex_thread: codex://threads/{codex_thread_id}
repo_head: {provenance["repo_head"]}
repo_branch: {json.dumps(provenance["repo_branch"])}
worktree_kind: {provenance["worktree_kind"]}
---

## Task
<one sentence>

## Method
<commands or approach>

## Findings
<what changed; cite file paths>

## Verification
<commands; pass/fail; blockers>

## Canonical Owner Impact
<list exact Typst/Python/configuration/test/setup/guidance owner updates, or say "none" explicitly>
"""
    return file_path, body


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold an agent debrief.")
    parser.add_argument("title", help="Short debrief title.")
    parser.add_argument(
        "--thread-id",
        required=True,
        help="Codex thread ID to embed as codex://threads/<thread-id>.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing debrief at the same path.",
    )
    args = parser.parse_args()

    if not CODEX_THREAD_ID_PATTERN.fullmatch(args.thread_id):
        parser.error("--thread-id must be a Codex thread ID")

    file_path, body = render(date.today(), args.title, args.thread_id, git_provenance())
    if file_path.exists() and not args.force:
        print(
            f"debrief already exists: {file_path.relative_to(REPO_ROOT)}",
            file=sys.stderr,
        )
        print("re-run with --force to overwrite", file=sys.stderr)
        return 1
    file_path.write_text(body, encoding="utf-8")
    print(file_path.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
