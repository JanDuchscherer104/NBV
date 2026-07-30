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
OMX_DURABLE_PATHS = (
    ".omx/context/",
    ".omx/interviews/",
    ".omx/specs/",
    ".omx/plans/",
)
OMX_DURABLE_SUFFIXES = (".md", ".json", ".html")
FORBIDDEN_TRACKED_RUNTIME_PATHS = {
    ".omx",
    ".codex/config.toml",
    ".codex/hooks.json",
}
ALLOWED_CODEX_MD_PREFIXES = (".codex/skills/graphify/",)

REQUIRED_NATIVE_KEYS = {
    "id",
    "date",
    "title",
    "status",
    "topics",
    "confidence",
    "canonical_updates_needed",
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


def check_tracked_omx_records(tracked_paths: list[str]) -> list[str]:
    errors: list[str] = []
    for tracked_path in tracked_paths:
        if not tracked_path.startswith(".omx/"):
            continue

        if not tracked_path.startswith(OMX_DURABLE_PATHS):
            errors.append(f"OMX runtime state must not be tracked: {tracked_path}")
        elif not tracked_path.endswith(OMX_DURABLE_SUFFIXES):
            errors.append(f"unsupported tracked OMX artifact: {tracked_path}")
    return errors


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
            resolved = REPO_ROOT / update_text
            if not resolved.exists():
                errors.append(f"{rel}: canonical update path does not exist: {update_text}")

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
        if tracked_path in FORBIDDEN_TRACKED_RUNTIME_PATHS:
            errors.append(f"runtime state must not be tracked: {tracked_path}")

    errors.extend(check_tracked_omx_records(tracked_paths))

    return errors


def main() -> int:
    errors = [*check_codex_notes(), *check_history_records(), *check_scaffold_alignment()]
    if not errors:
        print("agent memory validation passed")
        return 0

    print("agent memory validation failed", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
