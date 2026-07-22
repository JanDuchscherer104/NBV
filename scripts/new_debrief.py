#!/usr/bin/env python3
"""Scaffold a dated agent debrief under .agents/memory/history/YYYY/MM/.

The frontmatter follows .agents/references/agent_memory_templates.md exactly:
required keys are id, date, title, status, topics, confidence, and
canonical_updates_needed. Dates are absolute ISO strings — never relative.

Usage:
    scripts/new_debrief.py "<short title>"
    make new-debrief TITLE="<short title>"
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORY_ROOT = REPO_ROOT / ".agents" / "memory" / "history"


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", title.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not slug:
        raise SystemExit("title must contain at least one alphanumeric character")
    return slug


def render(today: date, title: str) -> tuple[Path, str]:
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
---

## Task
<one sentence>

## Method
<commands or approach>

## Findings
<what changed; cite file paths>

## Verification
<commands; pass/fail; blockers>

## Source Owner Impact
<list exact package/docs/reference/backlog owner updates, or say "none" explicitly>
"""
    return file_path, body


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold an agent debrief.")
    parser.add_argument("title", help="Short debrief title.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing debrief at the same path.",
    )
    args = parser.parse_args()

    file_path, body = render(date.today(), args.title)
    if file_path.exists() and not args.force:
        print(f"debrief already exists: {file_path.relative_to(REPO_ROOT)}", file=sys.stderr)
        print("re-run with --force to overwrite", file=sys.stderr)
        return 1
    file_path.write_text(body, encoding="utf-8")
    print(file_path.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
