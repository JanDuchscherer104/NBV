#!/usr/bin/env python3
"""Validate agent memory scaffolding and native debrief hygiene.

This checker intentionally stays narrow:

- fail if legacy `.codex/*.md` notes reappear outside approved project skills,
- require frontmatter on native debriefs under `.agents/memory/history/`, and
- require the documented native-debrief keys for non-legacy records.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORY_ROOT = REPO_ROOT / ".agents" / "memory" / "history"
MIGRATION_RECEIPT = (
    HISTORY_ROOT / "2026" / "08" / "2026-08-16_ownership_migration_receipt.md"
)
OMX_DURABLE_PATHS = (
    ".omx/context/",
    ".omx/interviews/",
    ".omx/specs/",
    ".omx/plans/",
)
OMX_DURABLE_SUFFIXES = (".md", ".json", ".html")
OWNERSHIP_INVENTORY_PREFIX = ".omx/specs/ownership-branch-consolidation-inventory."
OMX_GENERATED_MARKERS = ("/cache/", "/logs/", "/state/", "/tmp/", "/runtime/")
FORBIDDEN_TRACKED_RUNTIME_PATHS = {
    ".omx",
    ".codex/config.toml",
    ".codex/hooks.json",
}
REQUIRED_NATIVE_KEYS = {
    "id",
    "date",
    "title",
    "status",
    "topics",
    "confidence",
    "canonical_updates_needed",
}
RETIRED_SOURCE_PATHS = {
    "docs/contents/thesis/roadmap.qmd",
    "docs/contents/thesis/questions.qmd",
    "docs/contents/thesis/m1_contract_report.qmd",
    ".agents/memory/state/PROJECT_STATE.md",
    ".agents/memory/state/DECISIONS.md",
    ".agents/memory/state/GOTCHAS.md",
    ".agents/memory/state/OPEN_QUESTIONS.md",
}
LEGACY_RECEIPT_CUTOFF = date(2026, 8, 13)
LEGACY_RECEIPT_STATUSES = {"done", "legacy-imported", "archived"}
RECEIPT_DISPOSITIONS = {
    "historical",
    "removed",
    "deferred-action",
    "code-owned",
    "test-owned",
}
RECEIPT_SOURCE_COUNTS = {
    "docs/contents/thesis/roadmap.qmd": 10,
    "docs/contents/thesis/questions.qmd": 13,
    "docs/contents/thesis/m1_contract_report.qmd": 6,
    ".agents/memory/state/PROJECT_STATE.md": 5,
    ".agents/memory/state/DECISIONS.md": 4,
    ".agents/memory/state/GOTCHAS.md": 3,
    ".agents/memory/state/OPEN_QUESTIONS.md": 6,
}


def parse_inline_list(value: str) -> list[str]:
    inner = value.strip()[1:-1].strip()
    if not inner:
        return []
    return [item.strip().strip("\"'") for item in inner.split(",") if item.strip()]


def parse_frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing YAML frontmatter")

    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        raise ValueError("unterminated YAML frontmatter")

    payload = parts[0].removeprefix("---\n")
    data: dict[str, object] = {}
    current_key: str | None = None

    for raw_line in payload.splitlines():
        if not raw_line.strip():
            continue

        key_match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", raw_line)
        if key_match:
            key = key_match.group(1)
            value = key_match.group(2).strip()

            if value == "":
                data[key] = []
                current_key = key
                continue

            if value.startswith("[") and value.endswith("]"):
                data[key] = parse_inline_list(value)
            else:
                data[key] = value.strip("\"'")
            current_key = None
            continue

        list_match = re.match(r"^\s*-\s+(.*)$", raw_line)
        if list_match and current_key is not None:
            current_value = data.get(current_key)
            if not isinstance(current_value, list):
                raise ValueError(
                    f"`{current_key}` must be a list when using list items"
                )
            current_value.append(list_match.group(1).strip().strip("\"'"))
            continue

        if current_key is not None and raw_line.startswith(" "):
            # Allow nested metadata under list items (for example `files_touched`
            # entries with `path` / `kind`). The validator does not need to
            # interpret that structure.
            continue

        raise ValueError(f"unsupported frontmatter line: {raw_line!r}")

    return data


def allows_retired_canonical_update(
    frontmatter: dict[str, object], update_path: str
) -> bool:
    """Allow only pre-cutoff, completed historical receipts for retired paths."""
    if update_path not in RETIRED_SOURCE_PATHS:
        return False
    try:
        historical_date = date.fromisoformat(str(frontmatter.get("date")))
    except ValueError:
        return False
    return (
        historical_date <= LEGACY_RECEIPT_CUTOFF
        and str(frontmatter.get("status", "")) in LEGACY_RECEIPT_STATUSES
    )


def check_codex_notes() -> list[str]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            ".codex",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        suffix = f": {stderr}" if stderr else ""
        return [f"git ls-files failed while checking visible .codex notes{suffix}"]

    notes = sorted(
        rel
        for line in result.stdout.splitlines()
        if (rel := line.strip()).endswith(".md") and (REPO_ROOT / rel).is_file()
    )
    if not notes:
        return []

    errors = [
        "legacy `.codex/*.md` notes are not allowed outside approved project skills:"
    ] + [f"  - {note}" for note in notes]
    return errors


def check_tracked_omx_records(tracked_paths: list[str]) -> list[str]:
    errors: list[str] = []
    for tracked_path in tracked_paths:
        if not tracked_path.startswith(".omx/"):
            continue

        if is_forbidden_tracked_runtime_path(tracked_path):
            errors.append(f"OMX runtime state must not be tracked: {tracked_path}")
        elif not tracked_path.startswith(OMX_DURABLE_PATHS):
            errors.append(f"OMX runtime state must not be tracked: {tracked_path}")
        elif not tracked_path.endswith(OMX_DURABLE_SUFFIXES):
            errors.append(f"unsupported tracked OMX artifact: {tracked_path}")
    return errors


def is_forbidden_tracked_runtime_path(tracked_path: str) -> bool:
    """Return whether an OMX path is a known generated/runtime artifact.

    Durable Markdown, JSON, and HTML records remain valid under the explicit
    context/interviews/specs/plans roots. This predicate only identifies the
    narrow set of known generated names and runtime/cache/transient directories;
    callers still enforce the durable-root and suffix allowlist.
    """
    if tracked_path == ".omx" or not tracked_path.startswith(".omx/"):
        return tracked_path in FORBIDDEN_TRACKED_RUNTIME_PATHS
    if tracked_path in FORBIDDEN_TRACKED_RUNTIME_PATHS:
        return True
    if tracked_path.startswith(OWNERSHIP_INVENTORY_PREFIX):
        return True
    normalized = "/" + tracked_path.removeprefix(".omx/")
    return (
        any(marker in normalized for marker in OMX_GENERATED_MARKERS)
        or tracked_path.startswith(".omx/ultragoal/")
        or (
            tracked_path.startswith(".omx/goals/")
            and tracked_path != ".omx/goals/autoresearch/task.json"
        )
    )


def check_history_records() -> list[str]:
    errors: list[str] = []
    if not HISTORY_ROOT.exists():
        return [
            f"missing history root: {HISTORY_ROOT.relative_to(REPO_ROOT).as_posix()}"
        ]

    for path in sorted(HISTORY_ROOT.rglob("*.md")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        try:
            frontmatter = parse_frontmatter(path)
        except ValueError as exc:
            errors.append(f"{rel}: {exc}")
            continue

        status = str(frontmatter.get("status", "")).strip()
        if status == "legacy-imported":
            continue

        missing_keys = sorted(REQUIRED_NATIVE_KEYS - frontmatter.keys())
        if missing_keys:
            errors.append(
                f"{rel}: missing required frontmatter keys: {', '.join(missing_keys)}"
            )
            continue

        canonical_updates = frontmatter.get("canonical_updates_needed")
        if not isinstance(canonical_updates, list):
            errors.append(f"{rel}: `canonical_updates_needed` must be a list or []")
            continue

        for update_path in canonical_updates:
            update_text = str(update_path).strip()
            if not update_text:
                errors.append(f"{rel}: empty path in `canonical_updates_needed`")
                continue
            resolved = REPO_ROOT / update_text
            if not resolved.exists() and update_text in RETIRED_SOURCE_PATHS:
                if allows_retired_canonical_update(frontmatter, update_text):
                    continue
                errors.append(
                    f"{rel}: retired canonical update requires a pre-cutoff legacy record: {update_text}"
                )
            elif not resolved.exists():
                errors.append(
                    f"{rel}: canonical update path does not exist: {update_text}"
                )

    return errors


def check_migration_receipt() -> list[str]:
    """Validate the compact 47-row immutable ownership migration receipt."""
    if not MIGRATION_RECEIPT.exists():
        return [
            f"missing migration receipt: {MIGRATION_RECEIPT.relative_to(REPO_ROOT)}"
        ]
    rows = []
    in_table = False
    for line in MIGRATION_RECEIPT.read_text(encoding="utf-8").splitlines():
        if line.startswith("| Row ID |"):
            in_table = True
            continue
        if not in_table or not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) == 6:
            rows.append(cells)
    errors: list[str] = []
    if len(rows) != 47:
        errors.append(f"migration receipt must contain 47 rows, found {len(rows)}")
        return errors
    if len({row[0] for row in rows}) != 47:
        errors.append("migration receipt row IDs must be unique")
    source_counts = Counter()
    immutable = re.compile(
        r"8fcabeffed7c898b6c7d0ec02c65e24097ea68d8\s*/\s*[0-9a-f]{40}\s*/\s*[^|]+\s+\([^)]*\)"
    )
    for row in rows:
        source_parts = [
            part.strip().replace("`", "") for part in row[1].split(" / ", 1)
        ]
        source = source_parts[0] if source_parts else ""
        if source not in RECEIPT_SOURCE_COUNTS:
            errors.append(f"{row[0]}: unknown retired source path: {source!r}")
            continue
        if source:
            source_counts[source] += 1
        if not immutable.search(" / ".join(source_parts[1:])):
            errors.append(f"{row[0]}: missing full immutable commit/blob/source anchor")
        if row[3] not in RECEIPT_DISPOSITIONS:
            errors.append(f"{row[0]}: unsupported disposition {row[3]!r}")
        if (
            "verified:" not in row[5]
            or "unverified" in row[5].lower()
            or "unresolved" in row[5].lower()
        ):
            errors.append(
                f"{row[0]}: destination verification is missing or unresolved"
            )
        destination = row[4].split("#", 1)[0].strip("`")
        if row[3] == "removed" and destination.startswith(
            "Git history/debrief provenance"
        ):
            continue
        if not (REPO_ROOT / destination).exists() or "#" not in row[4]:
            errors.append(f"{row[0]}: destination path/anchor is missing: {row[4]}")
    if source_counts != Counter(RECEIPT_SOURCE_COUNTS):
        errors.append(
            f"migration receipt source counts mismatch: {dict(source_counts)}"
        )
    return errors


def check_scaffold_alignment() -> list[str]:
    errors: list[str] = []

    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        suffix = f": {stderr}" if stderr else ""
        errors.append(
            f"git ls-files failed while checking tracked runtime state{suffix}"
        )
        return errors

    tracked_paths = [
        line.strip() for line in result.stdout.splitlines() if line.strip()
    ]
    for tracked_path in tracked_paths:
        if tracked_path in FORBIDDEN_TRACKED_RUNTIME_PATHS:
            errors.append(f"runtime state must not be tracked: {tracked_path}")

    errors.extend(check_tracked_omx_records(tracked_paths))

    return errors


def main() -> int:
    errors = [
        *check_codex_notes(),
        *check_history_records(),
        *check_migration_receipt(),
        *check_scaffold_alignment(),
    ]
    if not errors:
        print("agent memory validation passed")
        return 0

    print("agent memory validation failed", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
