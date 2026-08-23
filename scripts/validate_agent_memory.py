#!/usr/bin/env python3
"""Validate agent memory scaffolding and native debrief hygiene.

This checker intentionally stays narrow:

- fail if legacy `.codex/*.md` notes reappear outside approved project skills,
- require frontmatter on native debriefs under `.agents/memory/history/`, and
- require the documented native-debrief keys for non-legacy records.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from debrief_index import (
    REPO_OBJECT_FORMAT_OID_LENGTHS,
    check_index,
    is_full_repo_oid,
    visible_history_paths,
)

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
NATIVE_THREAD_CUTOFF = date(2026, 8, 21)
NATIVE_PROVENANCE_CUTOFF = date(2026, 8, 22)
NATIVE_LIVE_PROVENANCE_CUTOFF = date(2026, 8, 23)
CODEX_THREAD_URI_PATTERN = re.compile(
    r"^codex://threads/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
WORKTREE_KINDS = {"primary", "linked"}
PROPOSAL_TARGET = ".agents/references/human_owner_intent.md"
PROPOSAL_FIELDS = (
    "Proposed statement",
    "Evidence",
    "Current owner or conflict",
    "Scope and target owner",
    "Disposition",
)
COMMIT_LINK_PATTERN = re.compile(
    r"^- \[([0-9a-f]+)\]"
    r"\(https://github\.com/JanDuchscherer104/ARIA-NBV/commit/([0-9a-f]+)\)"
    r" — ([^:]+): (.+)$"
)
NONE_COMMIT_PATTERN = re.compile(r"^- none — no repository commit \(([^()]+)\)$")
PLANNING_READ_ONLY_REASON = "planning/read-only"
NOT_YET_RECORDED_REASON = "not yet recorded"
RETIRED_SOURCE_PATHS = {
    "docs/contents/thesis/roadmap.qmd",
    "docs/contents/thesis/questions.qmd",
    "docs/contents/thesis/m1_contract_report.qmd",
    ".agents/memory/state/PROJECT_STATE.md",
    ".agents/memory/state/DECISIONS.md",
    ".agents/memory/state/GOTCHAS.md",
    ".agents/memory/state/OPEN_QUESTIONS.md",
    ".agents/references/source_order.md",
}
# This commit is the immutable source tree immediately before the retired
# owners were removed. CI fetches full history so these object lookups remain
# available in clean checkouts.
RETIREMENT_CUTOVER_COMMIT = "4748c4dd01e77bae5bdb2ff6932e8980a9416b4c"
RECEIPT_DISPOSITIONS = {
    "historical",
    "removed",
    "deferred-action",
    "code-owned",
    "test-owned",
}
NONCANONICAL_RECEIPT_DESTINATIONS = {".agents/references/source_order.md"}
DEBRIEF_INDEX_PATH = ".agents/memory/index/debriefs.jsonl"
RECEIPT_SOURCE_COUNTS = {
    "docs/contents/thesis/roadmap.qmd": 10,
    "docs/contents/thesis/questions.qmd": 13,
    "docs/contents/thesis/m1_contract_report.qmd": 6,
    ".agents/memory/state/PROJECT_STATE.md": 5,
    ".agents/memory/state/DECISIONS.md": 4,
    ".agents/memory/state/GOTCHAS.md": 3,
    ".agents/memory/state/OPEN_QUESTIONS.md": 6,
}
AGENTS_DB_PATHS = (
    REPO_ROOT / ".agents" / "issues.toml",
    REPO_ROOT / ".agents" / "todos.toml",
    REPO_ROOT / ".agents" / "refactors.toml",
)


def parse_inline_list(value: str) -> list[str]:
    inner = value.strip()[1:-1].strip()
    if not inner:
        return []
    return [item.strip().strip("\"'") for item in inner.split(",") if item.strip()]


def parse_scalar(value: str) -> str:
    """Decode generated JSON strings while preserving legacy scalar behavior."""
    if value.startswith('"') and value.endswith('"'):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(decoded, str):
                return decoded
    return value.strip("\"'")


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
                data[key] = parse_scalar(value)
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


def is_valid_repo_branch(value: str) -> bool:
    """Accept the detached sentinel or any Git-valid branch name."""
    if value == "detached":
        return True
    result = subprocess.run(
        ["git", "check-ref-format", "--branch", value],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


def allows_retired_canonical_update(
    frontmatter: dict[str, object], update_path: str, record_path: Path | None = None
) -> bool:
    """Allow only an unchanged tracked record from the retirement cutover."""
    if update_path not in RETIRED_SOURCE_PATHS:
        return False
    if record_path is None:
        return False
    try:
        relative_path = record_path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return False
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", relative_path],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
    )
    if tracked.returncode != 0:
        return False
    cutover_blob = subprocess.run(
        ["git", "rev-parse", f"{RETIREMENT_CUTOVER_COMMIT}:{relative_path}"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if cutover_blob.returncode != 0:
        return False
    current_blob = subprocess.run(
        ["git", "hash-object", "--", relative_path],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return (
        current_blob.returncode == 0
        and current_blob.stdout.strip() == cutover_blob.stdout.strip()
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

    if HISTORY_ROOT == REPO_ROOT / ".agents" / "memory" / "history":
        history_paths = visible_history_paths(REPO_ROOT)
    else:
        history_paths = sorted(HISTORY_ROOT.rglob("*.md"))
    for path in history_paths:
        rel = path.relative_to(REPO_ROOT).as_posix()
        try:
            frontmatter = parse_frontmatter(path)
        except ValueError as exc:
            errors.append(f"{rel}: {exc}")
            continue

        status = str(frontmatter.get("status", "")).strip()
        canonical_updates = frontmatter.get("canonical_updates_needed")
        if status == "legacy-imported":
            if isinstance(canonical_updates, list):
                for update_path in canonical_updates:
                    update_text = str(update_path).strip()
                    if (
                        update_text in RETIRED_SOURCE_PATHS
                        and not allows_retired_canonical_update(
                            frontmatter, update_text, path
                        )
                    ):
                        errors.append(
                            f"{rel}: retired canonical update requires an unchanged cutover record: {update_text}"
                        )
            continue

        missing_keys = sorted(REQUIRED_NATIVE_KEYS - frontmatter.keys())
        if missing_keys:
            errors.append(
                f"{rel}: missing required frontmatter keys: {', '.join(missing_keys)}"
            )
            continue

        record_date_text = str(frontmatter["date"]).strip()
        try:
            record_date = date.fromisoformat(record_date_text)
        except ValueError:
            errors.append(f"{rel}: `date` must be an absolute ISO date")
            continue
        if record_date >= NATIVE_THREAD_CUTOFF:
            codex_thread = str(frontmatter.get("codex_thread", "")).strip()
            if not CODEX_THREAD_URI_PATTERN.fullmatch(codex_thread):
                errors.append(
                    f"{rel}: `codex_thread` must be codex://threads/<uuid> "
                    f"for native records dated on or after {NATIVE_THREAD_CUTOFF}"
                )

        if record_date >= NATIVE_PROVENANCE_CUTOFF:
            provenance_fields = {
                "repo_object_format",
                "repo_head",
                "repo_branch",
                "worktree_kind",
            }
            missing_provenance = sorted(provenance_fields - frontmatter.keys())
            if missing_provenance:
                errors.append(
                    f"{rel}: missing required checkout provenance: "
                    f"{', '.join(missing_provenance)}"
                )
            else:
                repo_object_format = str(frontmatter["repo_object_format"]).strip()
                repo_head = str(frontmatter["repo_head"]).strip()
                repo_branch = str(frontmatter["repo_branch"]).strip()
                worktree_kind = str(frontmatter["worktree_kind"]).strip()
                if repo_object_format not in REPO_OBJECT_FORMAT_OID_LENGTHS:
                    errors.append(f"{rel}: repo_object_format must be sha1 or sha256")
                elif not is_full_repo_oid(repo_head, repo_object_format):
                    errors.append(
                        f"{rel}: repo_head must be a full {repo_object_format} Git OID"
                    )
                else:
                    if record_date >= NATIVE_LIVE_PROVENANCE_CUTOFF:
                        git_root = subprocess.run(
                            ["git", "rev-parse", "--is-inside-work-tree"],
                            cwd=REPO_ROOT,
                            check=False,
                            capture_output=True,
                        )
                        if git_root.returncode == 0:
                            repo_head_exists = subprocess.run(
                                ["git", "cat-file", "-e", f"{repo_head}^{{commit}}"],
                                cwd=REPO_ROOT,
                                check=False,
                                capture_output=True,
                            )
                            if repo_head_exists.returncode != 0:
                                errors.append(
                                    f"{rel}: repo_head must resolve to a repository commit: {repo_head}"
                                )
                            else:
                                repo_head_is_current = subprocess.run(
                                    [
                                        "git",
                                        "merge-base",
                                        "--is-ancestor",
                                        repo_head,
                                        "HEAD",
                                    ],
                                    cwd=REPO_ROOT,
                                    check=False,
                                    capture_output=True,
                                )
                                if repo_head_is_current.returncode != 0:
                                    errors.append(
                                        f"{rel}: repo_head is not an ancestor of live HEAD: {repo_head}"
                                    )
                if not is_valid_repo_branch(repo_branch):
                    errors.append(
                        f"{rel}: repo_branch must be a valid Git branch or detached"
                    )
                if worktree_kind not in WORKTREE_KINDS:
                    errors.append(f"{rel}: worktree_kind must be primary or linked")

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
                if allows_retired_canonical_update(frontmatter, update_text, path):
                    continue
                errors.append(
                    f"{rel}: retired canonical update requires an allowlisted historical record: {update_text}"
                )
            elif not resolved.exists():
                errors.append(
                    f"{rel}: canonical update path does not exist: {update_text}"
                )

        if record_date >= date(2026, 8, 23):
            errors.extend(check_proposal_body(path, canonical_updates))
        errors.extend(check_commit_links(path, frontmatter, record_date))

    return errors


def _body_sections(path: Path) -> dict[str, list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        body = lines[lines.index("---", 1) + 1 :]
    except ValueError:
        return {}
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in body:
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return sections


def check_proposal_body(path: Path, canonical_updates: object) -> list[str]:
    """Require the existing target path to carry the five-field proposal body."""
    if (
        not isinstance(canonical_updates, list)
        or PROPOSAL_TARGET not in canonical_updates
    ):
        return []
    rel = (
        path.relative_to(REPO_ROOT).as_posix()
        if path.is_relative_to(REPO_ROOT)
        else path.as_posix()
    )
    section = _body_sections(path).get("Human Intent Proposal")
    if section is None:
        return [f"{rel}: proposal target requires `## Human Intent Proposal`"]
    fields: dict[str, str] = {}
    for line in section:
        if not line.strip():
            continue
        match = re.fullmatch(r"- ([^:]+):\s*(.+)", line)
        if not match or match.group(1) not in PROPOSAL_FIELDS:
            return [f"{rel}: proposal body must contain exactly the five named fields"]
        field, value = match.groups()
        if field in fields:
            return [f"{rel}: proposal field is duplicated: {field}"]
        fields[field] = value.strip()
    if tuple(fields) != PROPOSAL_FIELDS or any(
        not fields[field] for field in PROPOSAL_FIELDS
    ):
        return [f"{rel}: proposal body must contain exactly the five named fields"]
    for field in PROPOSAL_FIELDS[:-1]:
        value = fields[field]
        if value.lower() == "none" or re.search(r"<[^>\n]*>", value):
            return [f"{rel}: proposal field must contain concrete evidence: {field}"]
    disposition = fields["Disposition"]
    if disposition not in {"proposed", "accept", "reject", "narrow", "defer"}:
        return [f"{rel}: unsupported proposal disposition: {disposition}"]
    return []


def check_commit_links(
    path: Path, frontmatter: dict[str, object], record_date: date
) -> list[str]:
    """Validate immutable workpackage links for current committed debriefs."""
    if record_date < date(2026, 8, 23):
        return []
    section = _body_sections(path).get("Commits")
    if section is None:
        rel = (
            path.relative_to(REPO_ROOT).as_posix()
            if path.is_relative_to(REPO_ROOT)
            else path.as_posix()
        )
        return [f"{rel}: `## Commits` must contain a commit link or none line"]
    rel = (
        path.relative_to(REPO_ROOT).as_posix()
        if path.is_relative_to(REPO_ROOT)
        else path.as_posix()
    )
    lines = [line.strip() for line in section if line.strip()]
    if not lines:
        return [f"{rel}: `## Commits` must contain a commit link or none line"]
    none_matches = [NONE_COMMIT_PATTERN.fullmatch(line) for line in lines]
    if any(none_matches):
        if len(lines) != 1:
            return [f"{rel}: `none` cannot coexist with a commit OID"]
        reason = none_matches[0].group(1) if none_matches[0] else ""
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", rel],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
        ).returncode == 0
        if reason == NOT_YET_RECORDED_REASON:
            if tracked:
                return [
                    f"{rel}: tracked debriefs must replace the scaffold placeholder"
                    " with immutable commit links or an exact planning/read-only reason"
                ]
            return []
        if reason != PLANNING_READ_ONLY_REASON:
            return [
                f"{rel}: no-commit records must use the exact reason"
                f" `{PLANNING_READ_ONLY_REASON}`"
            ]
        touched_owner_paths = frontmatter.get("touched_owner_paths", [])
        if tracked and touched_owner_paths:
            return [
                f"{rel}: tracked no-commit records require empty `touched_owner_paths`"
            ]
        return []
    object_format = str(frontmatter.get("repo_object_format", "sha1"))
    repo_head = str(frontmatter.get("repo_head", ""))
    oid_length = REPO_OBJECT_FORMAT_OID_LENGTHS.get(object_format)
    if oid_length is None or not is_full_repo_oid(repo_head, object_format):
        return [f"{rel}: commit links require valid checkout provenance"]
    seen: set[str] = set()
    errors: list[str] = []
    for line in lines:
        match = COMMIT_LINK_PATTERN.fullmatch(line)
        if not match:
            errors.append(f"{rel}: invalid commit-link grammar: {line}")
            continue
        label_oid, url_oid, _workpackage, _outcome = match.groups()
        if len(label_oid) != oid_length or len(url_oid) != oid_length:
            errors.append(f"{rel}: commit links must use full {object_format} OIDs")
            continue
        if label_oid != url_oid:
            errors.append(f"{rel}: commit link label and URL OID differ")
        if label_oid in seen:
            errors.append(f"{rel}: duplicate commit OID: {label_oid}")
        seen.add(label_oid)
        exists = subprocess.run(
            ["git", "cat-file", "-e", f"{label_oid}^{{commit}}"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
        )
        if exists.returncode != 0:
            errors.append(f"{rel}: commit OID is not a repository commit: {label_oid}")
            continue
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", label_oid, repo_head],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
        )
        if ancestor.returncode != 0:
            errors.append(
                f"{rel}: commit OID is not an ancestor of repo_head: {label_oid}"
            )
            continue
        try:
            source_path = path.resolve().relative_to(REPO_ROOT).as_posix()
        except ValueError:
            continue
        changed_paths = subprocess.run(
            [
                "git",
                "diff-tree",
                "--root",
                "--no-commit-id",
                "--name-only",
                "-r",
                "-m",
                "--find-renames",
                label_oid,
                "--",
                source_path,
                DEBRIEF_INDEX_PATH,
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if changed_paths.returncode != 0:
            errors.append(
                f"{rel}: unable to inspect linked commit changes: {label_oid}"
            )
        else:
            changed = set(changed_paths.stdout.splitlines())
            if source_path in changed:
                errors.append(
                    f"{rel}: linked commit creates or modifies the debrief source: {label_oid}"
                )
            if DEBRIEF_INDEX_PATH in changed:
                errors.append(
                    f"{rel}: linked commit creates or modifies the debrief index: {label_oid}"
                )
    return errors


def _markdown_table_rows(text: str, header: str, columns: int) -> list[list[str]]:
    """Return one named Markdown table without consuming later receipt tables."""
    lines = text.splitlines()
    try:
        start = lines.index(header)
    except ValueError:
        return []

    rows: list[list[str]] = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) == columns:
            rows.append(cells)
    return rows


def check_migration_receipt() -> list[str]:
    """Validate the compact 47-row immutable ownership migration receipt."""
    if not MIGRATION_RECEIPT.exists():
        return [
            f"missing migration receipt: {MIGRATION_RECEIPT.relative_to(REPO_ROOT)}"
        ]
    receipt_text = MIGRATION_RECEIPT.read_text(encoding="utf-8")
    rows = _markdown_table_rows(
        receipt_text,
        "| Row ID | Immutable source (commit/blob/heading or span) | Subject | Disposition | Exact destination path + anchor/symbol | Verification |",
        6,
    )
    errors: list[str] = []
    if len(rows) != 47:
        errors.append(f"migration receipt must contain 47 rows, found {len(rows)}")
        return errors
    if len({row[0] for row in rows}) != 47:
        errors.append("migration receipt row IDs must be unique")
    source_counts: Counter[str] = Counter()
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
        destination_ref = row[4].strip("`")
        destination = destination_ref.split("#", 1)[0]
        if row[3] == "removed" and destination.startswith(
            "Git history/debrief provenance"
        ):
            continue
        if destination in NONCANONICAL_RECEIPT_DESTINATIONS:
            errors.append(
                f"{row[0]}: receipt destination is a compatibility pointer, not a canonical owner: {destination}"
            )
            continue
        if "#" not in destination_ref:
            errors.append(f"{row[0]}: destination path/anchor is missing: {row[4]}")
            continue
        anchor = destination_ref.split("#", 1)[1]
        destination_path = REPO_ROOT / destination
        if not destination_path.exists() or not destination_anchor_exists(
            destination_path, anchor
        ):
            errors.append(f"{row[0]}: destination path/anchor is missing: {row[4]}")
    if source_counts != Counter(RECEIPT_SOURCE_COUNTS):
        errors.append(
            f"migration receipt source counts mismatch: {dict(source_counts)}"
        )

    deferred_rows = {row[0]: row for row in rows if row[3] == "deferred-action"}
    qualifications = _markdown_table_rows(
        receipt_text,
        "| Receipt row | Materialized canonical owner | Backlog ID | Action owner | Acceptance | Gate |",
        6,
    )
    qualification_by_id = {row[0]: row for row in qualifications}
    if set(qualification_by_id) != set(deferred_rows):
        errors.append(
            "deferred-action qualification rows must exactly match receipt rows: "
            f"expected {sorted(deferred_rows)}, found {sorted(qualification_by_id)}"
        )

    agents_db_text = "\n".join(
        path.read_text(encoding="utf-8") for path in AGENTS_DB_PATHS
    )
    for row_id, row in qualification_by_id.items():
        if any(not cell or cell in {"-", "—"} for cell in row[1:]):
            errors.append(f"{row_id}: deferred-action qualification is incomplete")
            continue
        canonical_owner = row[1].strip("`")
        expected_owner = deferred_rows.get(row_id, ["", "", "", "", ""])[4].strip("`")
        if canonical_owner != expected_owner:
            errors.append(
                f"{row_id}: qualified canonical owner does not match receipt destination"
            )
        backlog_id = row[2].strip("`")
        if not re.fullmatch(r"(?:issue|todo|refactor)-\d{3}", backlog_id):
            errors.append(f"{row_id}: invalid deferred backlog ID {backlog_id!r}")
        elif f'id = "{backlog_id}"' not in agents_db_text:
            errors.append(f"{row_id}: deferred backlog ID does not exist: {backlog_id}")
    return errors


def _heading_slug(value: str) -> str:
    """Return the stable heading slug used by receipt Markdown pointers."""
    value = re.sub(r"[`*_]", "", value).strip().lower()
    value = re.sub(r"[^\w\s-]", "", value)
    return re.sub(r"[-\s]+", "-", value).strip("-")


def destination_anchor_exists(path: Path, anchor: str) -> bool:
    """Resolve the narrow anchor forms used by the migration receipt."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        tree = ast.parse(text, filename=path.as_posix())
        return any(
            isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == anchor
            for node in ast.walk(tree)
        )
    if path.suffix in {".md", ".qmd"}:
        expected = _heading_slug(anchor)
        headings = re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", text, flags=re.MULTILINE)
        return expected in {_heading_slug(heading) for heading in headings}
    if path.suffix in {".yml", ".yaml"} and anchor.startswith("workflow:name="):
        expected = re.escape(anchor.removeprefix("workflow:name="))
        return (
            re.search(
                rf"^\s*name:\s*['\"]?{expected}['\"]?\s*$", text, flags=re.MULTILINE
            )
            is not None
        )
    if path.suffix == ".typ":
        return f"<{anchor}>" in text or anchor in text
    return anchor in text


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
        *check_index(),
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
