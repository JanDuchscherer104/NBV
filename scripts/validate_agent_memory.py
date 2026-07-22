#!/usr/bin/env python3
"""Validate agent memory scaffolding and native debrief hygiene.

This checker intentionally stays narrow:

- fail if legacy `.codex/*.md` notes reappear outside approved project skills,
- require frontmatter on native debriefs under `.agents/memory/history/`, and
- require the documented native-debrief keys for non-legacy records.
"""

from __future__ import annotations

import csv
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORY_ROOT = REPO_ROOT / ".agents" / "memory" / "history"
ALIGNMENT_CONTRACT = REPO_ROOT / ".agents" / "references" / "alignment_tools_contract.md"
ALIGNMENT_LINK_TARGETS = (
    (
        REPO_ROOT / "AGENTS.md",
        ".agents/references/alignment_tools_contract.md` when work crosses OMX,",
    ),
    (
        REPO_ROOT / ".agents" / "references" / "source_order.md",
        "- Optional tool boundary: `.agents/references/alignment_tools_contract.md`.",
    ),
    (
        REPO_ROOT / ".agents" / "references" / "verification_matrix.md",
        "Covers repo-owned scaffold alignment checks, required debrief frontmatter,",
    ),
)
SCAFFOLD_REQUIRED_SNIPPETS = (
    (
        REPO_ROOT / ".agents" / "references" / "alignment_tools_contract.md",
        "## Autoresearch Adapter",
    ),
    (
        REPO_ROOT / ".agents" / "references" / "alignment_tools_contract.md",
        "## Visual And UI Gates",
    ),
    (
        REPO_ROOT / ".agents" / "references" / "verification_matrix.md",
        "## Streamlit, Rerun, Offline, And Rollouts",
    ),
    (
        REPO_ROOT / ".agents" / "references" / "verification_matrix.md",
        "## KG And Optional Tooling",
    ),
    (
        REPO_ROOT / ".agents" / "references" / "verification_matrix.md",
        "## Python Package",
    ),
)
FORBIDDEN_TRACKED_RUNTIME_PATHS = {
    ".omx",
    ".codex/config.toml",
    ".codex/hooks.json",
}
ALLOWED_CODEX_MD_PREFIXES = (".codex/skills/graphify/",)
STATE_SALVAGE_LEDGER = REPO_ROOT / ".agents" / "baselines" / "scaffold_wp4_state_salvage.csv"
RETIRED_STATE_JOURNALS = (
    ".agents/memory/state/DECISIONS.md",
    ".agents/memory/state/GOTCHAS.md",
    ".agents/memory/state/OPEN_QUESTIONS.md",
    ".agents/memory/state/PROJECT_STATE.md",
)
EXPECTED_STATE_LEDGER_IDS = {
    "decisions-durable-repo-decisions",
    "decisions-technical-decisions",
    "decisions-working-project-decisions",
    "decisions-thesis-sharpening",
    "decisions-rollout-dto-store",
    "decisions-vin-offline-v7",
    "decisions-top-k-target-selector",
    "decisions-typst-notation",
    "decisions-target-first-rollout",
    "decisions-transcript-mined",
    "decisions-litkg",
    "gotchas-environment-tooling",
    "gotchas-training-validation",
    "gotchas-vin-offline",
    "gotchas-frames-geometry",
    "gotchas-evl-obb",
    "gotchas-config-pydantic",
    "gotchas-litkg",
    "questions-advisor-deferred",
    "questions-target-matching",
    "questions-qh-offline-rl",
    "questions-storage-scale",
    "questions-representation-ablation",
    "questions-recently-locked",
    "project-goal-core-claim",
    "project-current-thesis-spine",
    "project-ranked-priorities",
    "project-current-issues",
    "project-near-term-next-steps",
    "project-deferred-extensions",
    "project-pointers",
    "project-litkg-infrastructure",
}
STATE_REFERENCE_EXCLUDED_PREFIXES = (
    ".agents/archive/",
    ".agents/memory/history/",
    ".agents/memory/transcripts/",
    ".omx/",
    "graphify-out/",
)
STATE_REFERENCE_EXCLUDED_PATHS = {
    ".agents/baselines/scaffold_wp0_baseline.json",
    ".agents/baselines/scaffold_wp0_inventory.csv",
    ".agents/baselines/scaffold_wp4_state_salvage.csv",
    "scripts/validate_agent_memory.py",
    "scripts/validate_scaffold_wp0_baseline.py",
    "scripts/tests/test_scaffold_wp0_baseline.py",
    "aria_nbv/tests/agent_memory/test_validate_agent_memory.py",
}
RETIRED_STATE_PATTERN = re.compile(
    r"\.agents/memory/state|DECISIONS\.md|GOTCHAS\.md|OPEN_QUESTIONS\.md|PROJECT_STATE\.md"
)

REQUIRED_NATIVE_KEYS = {
    "id",
    "date",
    "title",
    "status",
    "topics",
    "confidence",
    "canonical_updates_needed",
}


def is_forbidden_tracked_runtime_path(path: str) -> bool:
    """Return whether a tracked path belongs to operator-only runtime state."""

    return path in FORBIDDEN_TRACKED_RUNTIME_PATHS or path.startswith(
        (
            ".omx/cache/",
            ".omx/logs/",
            ".omx/state/",
            ".omx/tmp/",
            ".omx/ultragoal/",
            ".omx/goals/autoresearch/run/",
        )
    )


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
                raise ValueError(f"`{current_key}` must be a list when using list items")
            current_value.append(list_match.group(1).strip().strip("\"'"))
            continue

        if current_key is not None and raw_line.startswith(" "):
            # Allow nested metadata under list items (for example `files_touched`
            # entries with `path` / `kind`). The validator does not need to
            # interpret that structure.
            continue

        raise ValueError(f"unsupported frontmatter line: {raw_line!r}")

    return data


def check_codex_notes() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", ".codex"],
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
        if (rel := line.strip()).endswith(".md")
        and not any(rel.startswith(prefix) for prefix in ALLOWED_CODEX_MD_PREFIXES)
    )
    if not notes:
        return []

    errors = ["legacy `.codex/*.md` notes are not allowed outside approved project skills:"] + [
        f"  - {note}" for note in notes
    ]
    return errors


def check_registered_omx_records() -> list[str]:
    validator = REPO_ROOT / "scripts" / "scaffold" / "validate_omx_artifacts.py"
    if not validator.is_file():
        return ["missing OMX artifact registry validator"]
    result = subprocess.run(
        [sys.executable, str(validator), "--check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return []
    details = [line for line in result.stderr.splitlines() if line.strip()]
    return ["registered OMX artifact validation failed", *details]


def check_history_records() -> list[str]:
    errors: list[str] = []
    if not HISTORY_ROOT.exists():
        return [f"missing history root: {HISTORY_ROOT.relative_to(REPO_ROOT).as_posix()}"]

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
            errors.append(f"{rel}: missing required frontmatter keys: {', '.join(missing_keys)}")
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
            if update_text in RETIRED_STATE_JOURNALS:
                # Dated debriefs are historical evidence. Their frontmatter
                # records the owner that existed when the task ran; it is not
                # an active promotion route after WP4 retirement.
                continue
            resolved = REPO_ROOT / update_text
            if not resolved.exists():
                errors.append(f"{rel}: canonical update path does not exist: {update_text}")

    return errors


def check_state_journal_retirement() -> list[str]:
    """Require a closed salvage ledger and no live journal consumers."""

    errors: list[str] = []
    for relative_path in RETIRED_STATE_JOURNALS:
        if (REPO_ROOT / relative_path).exists():
            errors.append(f"retired state journal still exists: {relative_path}")

    if not STATE_SALVAGE_LEDGER.is_file():
        return [*errors, "missing WP4 state salvage ledger"]

    with STATE_SALVAGE_LEDGER.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    row_ids = [str(row.get("id") or "").strip() for row in rows]
    if len(row_ids) != len(set(row_ids)):
        errors.append("WP4 state salvage ledger contains duplicate row ids")
    missing = sorted(EXPECTED_STATE_LEDGER_IDS - set(row_ids))
    extra = sorted(set(row_ids) - EXPECTED_STATE_LEDGER_IDS)
    if missing:
        errors.append(f"WP4 state salvage ledger is missing rows: {', '.join(missing)}")
    if extra:
        errors.append(f"WP4 state salvage ledger has unexpected rows: {', '.join(extra)}")

    allowed_statuses = {
        "already_owned",
        "migrated",
        "discarded_duplicate",
        "discarded_historical",
        "discarded_stale",
        "discarded_unsupported",
    }
    required_fields = (
        "source_path",
        "source_lines",
        "fact_category",
        "destination_owners",
        "evidence",
        "disposition_rationale",
        "verification",
        "rollback_commit",
    )
    for row in rows:
        row_id = str(row.get("id") or "<missing-id>").strip()
        status = str(row.get("status") or "").strip()
        if status not in allowed_statuses:
            errors.append(f"{row_id}: unresolved or invalid salvage status: {status or '<empty>'}")
        for field in required_fields:
            if not str(row.get(field) or "").strip():
                errors.append(f"{row_id}: empty salvage field: {field}")

    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        errors.append("git ls-files failed while scanning retired journal references")
        return errors

    for relative_path in sorted({line.strip() for line in result.stdout.splitlines() if line.strip()}):
        if relative_path in STATE_REFERENCE_EXCLUDED_PATHS or relative_path.startswith(
            STATE_REFERENCE_EXCLUDED_PREFIXES
        ):
            continue
        path = REPO_ROOT / relative_path
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        match = RETIRED_STATE_PATTERN.search(text)
        if match:
            line = text.count("\n", 0, match.start()) + 1
            errors.append(f"active retired-journal reference: {relative_path}:{line}")

    return errors


def check_scaffold_alignment() -> list[str]:
    errors: list[str] = []

    if not ALIGNMENT_CONTRACT.exists():
        errors.append(f"missing alignment tools contract: {ALIGNMENT_CONTRACT.relative_to(REPO_ROOT).as_posix()}")

    for path, expected_snippet in ALIGNMENT_LINK_TARGETS:
        rel = path.relative_to(REPO_ROOT).as_posix()
        if not path.exists():
            errors.append(f"missing scaffold alignment link target: {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        if expected_snippet not in text:
            errors.append(f"{rel}: missing expected alignment contract link")

    for path, expected_snippet in SCAFFOLD_REQUIRED_SNIPPETS:
        rel = path.relative_to(REPO_ROOT).as_posix()
        if not path.exists():
            errors.append(f"missing scaffold ownership target: {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        if expected_snippet not in text:
            errors.append(f"{rel}: missing scaffold ownership snippet: {expected_snippet}")

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
        errors.append(f"git ls-files failed while checking tracked runtime state{suffix}")
        return errors

    tracked_paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    for tracked_path in tracked_paths:
        if is_forbidden_tracked_runtime_path(tracked_path):
            errors.append(f"runtime state must not be tracked: {tracked_path}")

    errors.extend(check_registered_omx_records())

    return errors


def main() -> int:
    errors = [
        *check_codex_notes(),
        *check_history_records(),
        *check_scaffold_alignment(),
        *check_state_journal_retirement(),
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
