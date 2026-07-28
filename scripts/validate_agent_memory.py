#!/usr/bin/env python3
"""Validate agent memory scaffolding and native debrief hygiene.

This checker intentionally stays narrow:

- fail if legacy `.codex/*.md` notes reappear outside approved project skills,
- require frontmatter on native debriefs under `.agents/memory/history/`, and
- require the documented native-debrief keys for non-legacy records.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORY_ROOT = REPO_ROOT / ".agents" / "memory" / "history"
ALIGNMENT_CONTRACT = (
    REPO_ROOT / ".agents" / "references" / "alignment_tools_contract.md"
)
OMX_ARTIFACT_REGISTRY = REPO_ROOT / ".agents" / "omx_artifacts.toml"
OMX_ARTIFACT_VALIDATOR = (
    REPO_ROOT / "scripts" / "scaffold" / "validate_omx_artifacts.py"
)
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
        REPO_ROOT / "AGENTS.md",
        "Current thesis direction and interpretation are owned by the active Typst",
    ),
    (
        REPO_ROOT / "docs" / "AGENTS.md",
        "Current thesis direction and interpretation live in the active Typst thesis",
    ),
    (
        REPO_ROOT / ".agents" / "memory" / "README.md",
        "legacy journals awaiting claim-level PR2 disposition",
    ),
    (
        REPO_ROOT / ".agents" / "AGENTS_INTERNAL_DB.md",
        "not current-truth owners",
    ),
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
OMX_RECORD_PATHS = {
    ".omx/plans/": "plan",
    ".omx/specs/": "spec",
}
OMX_RECORD_STATUSES = {"current", "accepted"}
FORBIDDEN_TRACKED_RUNTIME_PATHS = {
    ".omx",
    ".codex/config.toml",
    ".codex/hooks.json",
    ".agents/memory/session-manifests",
    ".agents/memory/transcripts",
    ".mempalace",
    ".palace",
}
FORBIDDEN_TRACKED_RUNTIME_PREFIXES = (
    ".agents/memory/session-manifests/",
    ".agents/memory/transcripts/",
    ".mempalace/",
    ".palace/",
)
FORBIDDEN_OMX_RUNTIME_PREFIXES = (
    ".omx/cache/",
    ".omx/logs/",
    ".omx/state/",
    ".omx/tmp/",
    ".omx/ultragoal/",
)
ALLOWED_CODEX_MD_PREFIXES = (".codex/skills/graphify/",)
LEGACY_STATE_MENTION = re.compile(
    r"(?:\.agents/memory/state(?:/[A-Z_]+\.md)?|"
    r"(?:memory/)?state/(?:DECISIONS|PROJECT_STATE|OPEN_QUESTIONS|GOTCHAS)\.md|"
    r"(?<![A-Za-z0-9_/.])(?:DECISIONS|PROJECT_STATE|OPEN_QUESTIONS|GOTCHAS)\.md|"
    r"\b(?:canonical memory|memory state|decision journals?|state journals?)\b)",
    re.IGNORECASE,
)
LEGACY_STATE_BARE_NAME = re.compile(
    r"(?<![A-Za-z0-9_/])(?:DECISIONS|PROJECT_STATE|OPEN_QUESTIONS|GOTCHAS)"
    r"(?![A-Za-z0-9_/])"
)
LEGACY_STATE_MIGRATION_ONLY = (
    re.compile(r"\bmigration(?:-only)? evidence\b", re.IGNORECASE),
    re.compile(r"\blegacy migration\b", re.IGNORECASE),
    re.compile(r"\bread-only migration\b", re.IGNORECASE),
    re.compile(r"\bnot (?:a )?current[- ]truth\b", re.IGNORECASE),
    re.compile(
        r"\blegacy (?:state )?journals?\b.{0,120}\b(?:removed|retired|archived)\b|"
        r"\b(?:removed|retired|archived)\b.{0,120}\blegacy (?:state )?journals?\b",
        re.IGNORECASE,
    ),
)
LEGACY_STATE_NEGATED_OWNER = re.compile(
    r"\b(?:not|never) (?:a )?(?:authoritative|canonical|current owner|current[- ]truth|source of truth)\b|"
    r"\brather than (?:the )?(?:authoritative|canonical|current owner|current[- ]truth|source of truth)\b|"
    r"\bdo not (?:add|update|write|record|maintain)\b[^.;]*",
    re.IGNORECASE,
)
LEGACY_STATE_OWNER_ASSERTION = re.compile(
    r"\b(?:authoritative|canonical|current owner|current[- ]truth|source of truth|"
    r"current decisions?|current contract)\b|"
    r"\b(?:add|append|edit|maintain|persist|record|save|store|update|write)\b"
    r".{0,120}\b(?:facts?|it|journal|state|truth)\b",
    re.IGNORECASE,
)
LEGACY_STATE_WRITE_VERB = re.compile(
    r"\b(?:add|append|edit|maintain|persist|record|save|store|update|write)\b",
    re.IGNORECASE,
)
EXPLICIT_OWNER_SUBJECT = re.compile(
    r"(?P<subject>(?:the\s+)?[a-z][a-z0-9_./-]*"
    r"(?:\s+[a-z][a-z0-9_./-]*){0,7})\s+"
    r"(?:is|are|owns?|remains?|becomes?|serves(?:\s+as)?)(?:\s+the)?$",
    re.IGNORECASE,
)
EXPLICIT_USE_SUBJECT = re.compile(
    r"\buse\s+(?P<subject>(?:the\s+)?[a-z][a-z0-9_./-]*"
    r"(?:\s+[a-z][a-z0-9_./-]*){0,7})\s+as(?:\s+the)?$",
    re.IGNORECASE,
)
ANAPHORIC_OWNER_SUBJECTS = {
    "and",
    "but",
    "it",
    "journal",
    "journals",
    "state",
    "that",
    "these",
    "they",
    "this",
    "those",
    "which",
}
LEGACY_STATE_SCAN_SUFFIXES = {
    ".json",
    ".md",
    ".py",
    ".qmd",
    ".sh",
    ".toml",
    ".typ",
    ".yaml",
    ".yml",
}
LEGACY_STATE_SCAN_FILENAMES = {"Makefile"}
LEGACY_STATE_SCAN_EXCLUDED_PREFIXES = (
    ".agents/archive/",
    ".agents/memory/history/",
    ".agents/memory/state/",
    ".omx/",
    "aria_nbv/tests/",
    "scripts/tests/",
)
LEGACY_STATE_SCAN_EXCLUDED_PATHS = {
    ".agents/resolved.toml",
    "scripts/validate_agent_memory.py",
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
        if (rel := line.strip()).endswith(".md")
        and not any(rel.startswith(prefix) for prefix in ALLOWED_CODEX_MD_PREFIXES)
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

        expected_kind = next(
            (
                kind
                for prefix, kind in OMX_RECORD_PATHS.items()
                if tracked_path.startswith(prefix)
            ),
            None,
        )
        if expected_kind is None or not tracked_path.endswith(".md"):
            errors.append(f"OMX runtime state must not be tracked: {tracked_path}")
            continue

        path = REPO_ROOT / tracked_path
        try:
            frontmatter = parse_frontmatter(path)
        except ValueError as exc:
            errors.append(f"{tracked_path}: {exc}")
            continue

        if frontmatter.get("kind") != expected_kind:
            errors.append(f"{tracked_path}: `kind` must be `{expected_kind}`")
        if frontmatter.get("status") not in OMX_RECORD_STATUSES:
            errors.append(
                f"{tracked_path}: `status` must be one of {', '.join(sorted(OMX_RECORD_STATUSES))}"
            )
    return errors


def check_registered_omx_artifacts(
    repo_root: Path = REPO_ROOT,
    validator_path: Path = OMX_ARTIFACT_VALIDATOR,
) -> list[str]:
    hosted = os.environ.get("GITHUB_ACTIONS") == "true"
    explicit_ref = os.environ.get("OMX_ARTIFACT_PREVIOUS_REF")
    if hosted and not explicit_ref:
        return ["hosted CI requires OMX_ARTIFACT_PREVIOUS_REF"]
    base_name = os.environ.get("GITHUB_BASE_REF")
    base_ref = explicit_ref or (f"origin/{base_name}" if base_name else "origin/main")
    verify = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    previous_ref: str | None = None
    if verify.returncode == 0 and explicit_ref:
        resolved = subprocess.run(
            ["git", "rev-parse", f"{base_ref}^{{commit}}"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if resolved == head:
            return ["OMX artifact transition comparison cannot use HEAD itself"]
        previous_ref = resolved
    elif verify.returncode == 0:
        merge_base = subprocess.run(
            ["git", "merge-base", "HEAD", base_ref],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if merge_base.returncode == 0 and merge_base.stdout.strip():
            previous_ref = merge_base.stdout.strip()
        elif hosted:
            return [f"hosted CI could not determine merge base against {base_ref}"]
    elif explicit_ref and hosted:
        return [f"hosted CI requires transition comparison against {base_ref}"]
    elif explicit_ref:
        return [f"explicit OMX artifact transition ref is invalid: {base_ref}"]

    registry_path = repo_root / ".agents" / "omx_artifacts.toml"
    if registry_path.is_symlink():
        return ["OMX artifact registry must be a regular file"]
    if not registry_path.exists():
        tracked_registry = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", ".agents/omx_artifacts.toml"],
            cwd=repo_root,
            check=False,
            capture_output=True,
        )
        if tracked_registry.returncode == 0:
            return ["tracked OMX artifact registry is missing from the worktree"]
        if previous_ref:
            prior_registry = subprocess.run(
                ["git", "cat-file", "-e", f"{previous_ref}:.agents/omx_artifacts.toml"],
                cwd=repo_root,
                check=False,
                capture_output=True,
            )
            if prior_registry.returncode == 0:
                return ["accepted OMX artifact registry must not be removed"]
        return []

    command = [
        sys.executable,
        str(validator_path),
        "--repo",
        str(repo_root),
        "--registry",
        str(registry_path),
        "--check-tracked",
    ]
    if previous_ref:
        command.extend(["--previous-ref", previous_ref])
    else:
        print(
            "OMX artifact transition validation unavailable: "
            "running local-only snapshot validation (no valid remote base ref)."
        )
    result = subprocess.run(
        command,
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return []

    stderr_lines = [line.strip() for line in result.stderr.splitlines() if line.strip()]
    return [stderr_lines[-1] if stderr_lines else "OMX artifact validation failed"]


def check_forbidden_tracked_paths(tracked_paths: list[str]) -> list[str]:
    return [
        f"runtime or transcript evidence must not be tracked: {path}"
        for path in tracked_paths
        if is_forbidden_tracked_runtime_path(path)
    ]


def is_forbidden_tracked_runtime_path(path: str) -> bool:
    """Return whether a tracked path is private or operator-owned runtime state."""

    return (
        path in FORBIDDEN_TRACKED_RUNTIME_PATHS
        or path.startswith(FORBIDDEN_TRACKED_RUNTIME_PREFIXES)
        or path.startswith(FORBIDDEN_OMX_RUNTIME_PREFIXES)
        or (path.startswith(".omx/goals/") and "/artifacts/" in path)
    )


def _legacy_state_mentions(text: str) -> list[re.Match[str]]:
    """Return non-overlapping legacy-state mentions in source order."""

    matches = [
        *LEGACY_STATE_MENTION.finditer(text),
        *LEGACY_STATE_BARE_NAME.finditer(text),
    ]
    matches.sort(key=lambda match: (match.start(), -(match.end() - match.start())))
    selected: list[re.Match[str]] = []
    for match in matches:
        if selected and match.start() < selected[-1].end():
            continue
        selected.append(match)
    return selected


def _has_legacy_state_mention(text: str) -> bool:
    return bool(_legacy_state_mentions(text))


def _explicit_different_owner(prefix: str) -> bool:
    subject_match = EXPLICIT_OWNER_SUBJECT.search(
        prefix
    ) or EXPLICIT_USE_SUBJECT.search(prefix)
    if subject_match is None:
        return False
    subject = subject_match.group("subject").strip()
    words = subject.lower().split()
    return bool(
        words
        and words[-1] not in ANAPHORIC_OWNER_SUBJECTS
        and not _has_legacy_state_mention(subject)
    )


def _has_legacy_owner_assertion(text: str) -> bool:
    """Return whether an owner assertion refers to the legacy mention."""

    assertion_text = LEGACY_STATE_NEGATED_OWNER.sub("", text)
    for write_verb in LEGACY_STATE_WRITE_VERB.finditer(assertion_text):
        if _has_legacy_state_mention(
            assertion_text[write_verb.start() : write_verb.end() + 120]
        ):
            return True
    for assertion in LEGACY_STATE_OWNER_ASSERTION.finditer(assertion_text):
        clause_start = max(
            assertion_text.rfind(delimiter, 0, assertion.start())
            for delimiter in (".", ";", "!", "?")
        )
        clause = assertion_text[clause_start + 1 : assertion.end()]
        if _has_legacy_state_mention(clause):
            return True
        prefix = clause[: assertion.start() - clause_start - 1].strip()
        if not _explicit_different_owner(prefix):
            return True
    return False


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _paragraph_record(lines: list[str], line_index: int) -> tuple[int, str]:
    start = line_index
    while start > 0 and lines[start - 1].strip():
        start -= 1
    end = line_index + 1
    while end < len(lines) and lines[end].strip():
        end += 1
    return start + 1, " ".join(part.strip() for part in lines[start:end])


def _toml_string_records(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        strings = [entry for entry in value if isinstance(entry, str)]
        if strings:
            yield " . ".join(strings)
        for entry in value:
            if not isinstance(entry, str):
                yield from _toml_string_records(entry)
    elif isinstance(value, dict):
        for entry in value.values():
            yield from _toml_string_records(entry)


def _toml_records(text: str) -> list[tuple[int, str]]:
    """Decode complete TOML values so wrapped arrays cannot split ownership claims."""

    parsed = tomllib.loads(text)
    records: list[tuple[int, str]] = []
    search_offset = 0
    for record in _toml_string_records(parsed):
        mentions = _legacy_state_mentions(record)
        if not mentions:
            continue
        token = mentions[0].group(0)
        match = re.search(re.escape(token), text[search_offset:], re.IGNORECASE)
        if match is None:
            match = re.search(re.escape(token), text, re.IGNORECASE)
            offset = match.start() if match else 0
        else:
            offset = search_offset + match.start()
            search_offset += match.end()
        records.append((_line_number(text, offset), record))

    for match in re.finditer(r"(?m)^\s*#.*$", text):
        if _has_legacy_state_mention(match.group(0)):
            records.append((_line_number(text, match.start()), match.group(0)))
    return records


def _typst_bracket_spans(text: str) -> list[tuple[int, int]]:
    """Return balanced Typst bracket spans while ignoring strings and comments."""

    opening = {"[": "]", "(": ")", "{": "}"}
    closing = {value: key for key, value in opening.items()}
    stack: list[tuple[str, int]] = []
    spans: list[tuple[int, int]] = []
    quote: str | None = None
    escaped = False
    line_comment = False
    block_comment_depth = 0
    index = 0
    while index < len(text):
        char = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
            index += 1
            continue
        if block_comment_depth:
            if char == "/" and following == "*":
                block_comment_depth += 1
                index += 2
            elif char == "*" and following == "/":
                block_comment_depth -= 1
                index += 2
            else:
                index += 1
            continue
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char == "/" and following == "/":
            line_comment = True
            index += 2
            continue
        if char == "/" and following == "*":
            block_comment_depth = 1
            index += 2
            continue
        if char in {'"', "'"}:
            quote = char
        elif char in opening:
            stack.append((char, index))
        elif char in closing and stack and stack[-1][0] == closing[char]:
            _, start = stack.pop()
            spans.append((start, index + 1))
        index += 1
    return spans


def _typst_record(
    text: str, mention_offset: int, spans: list[tuple[int, int]]
) -> tuple[int, str]:
    candidates = sorted(
        (span for span in spans if span[0] <= mention_offset < span[1]),
        key=lambda span: span[1] - span[0],
    )
    selected: tuple[int, int] | None = None
    for span in candidates:
        line_start = text.rfind("\n", 0, span[0]) + 1
        prefix = text[line_start : span[0]].strip()
        selected = span
        if prefix.startswith("#") or prefix.endswith(("=", ":")):
            break
    if selected is None:
        lines = text.splitlines()
        line_index = _line_number(text, mention_offset) - 1
        return _paragraph_record(lines, line_index)
    return _line_number(text, selected[0]), text[selected[0] : selected[1]]


def _logical_owner_records(path: Path, text: str) -> list[tuple[int, str]]:
    lines = text.splitlines()
    if path.suffix in {".md", ".qmd"}:
        prose_records = {
            _paragraph_record(lines, _line_number(text, match.start()) - 1)
            for match in _legacy_state_mentions(text)
        }
        return sorted(prose_records)
    if path.suffix == ".toml":
        return _toml_records(text)
    if path.suffix == ".typ":
        spans = _typst_bracket_spans(text)
        typst_records = {
            _typst_record(text, match.start(), spans)
            for match in _legacy_state_mentions(text)
        }
        return sorted(typst_records)

    fallback_records: set[tuple[int, str]] = set()
    for line_index, line in enumerate(lines):
        if not _has_legacy_state_mention(line):
            continue
        start = max(0, line_index - 1)
        end = min(len(lines), line_index + 2)
        fallback_records.add(
            (line_index + 1, " ".join(part.strip() for part in lines[start:end]))
        )
    return sorted(fallback_records)


def check_legacy_state_owner_claims(
    tracked_paths: list[str], repo_root: Path = REPO_ROOT
) -> list[str]:
    """Reject active routes to legacy journals unless marked migration-only."""

    errors: list[str] = []
    for tracked_path in tracked_paths:
        if tracked_path in LEGACY_STATE_SCAN_EXCLUDED_PATHS or tracked_path.startswith(
            LEGACY_STATE_SCAN_EXCLUDED_PREFIXES
        ):
            continue
        path = repo_root / tracked_path
        if (
            path.suffix not in LEGACY_STATE_SCAN_SUFFIXES
            and path.name not in LEGACY_STATE_SCAN_FILENAMES
        ):
            continue
        if path.is_symlink() or not path.is_file():
            errors.append(f"{tracked_path}: tracked ownership source is unreadable")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(
                f"{tracked_path}: cannot inspect legacy-state ownership routes: {exc}"
            )
            continue
        if not _has_legacy_state_mention(text):
            continue
        try:
            records = _logical_owner_records(path, text)
        except tomllib.TOMLDecodeError as exc:
            errors.append(
                f"{tracked_path}: cannot parse tracked TOML ownership source: {exc}"
            )
            continue
        for line_number, context in records:
            normalized = " ".join(context.split())
            migration_only = any(
                pattern.search(normalized) for pattern in LEGACY_STATE_MIGRATION_ONLY
            )
            if migration_only and not _has_legacy_owner_assertion(normalized):
                continue
            errors.append(
                f"{tracked_path}:{line_number}: legacy state journal route lacks "
                "an explicit migration-only qualifier"
            )
    return errors


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
            if not resolved.exists():
                errors.append(
                    f"{rel}: canonical update path does not exist: {update_text}"
                )

    return errors


def check_scaffold_alignment() -> list[str]:
    errors: list[str] = []

    if not ALIGNMENT_CONTRACT.exists():
        errors.append(
            f"missing alignment tools contract: {ALIGNMENT_CONTRACT.relative_to(REPO_ROOT).as_posix()}"
        )

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
            errors.append(
                f"{rel}: missing scaffold ownership snippet: {expected_snippet}"
            )

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
    errors.extend(check_forbidden_tracked_paths(tracked_paths))
    errors.extend(check_legacy_state_owner_claims(tracked_paths))

    if OMX_ARTIFACT_REGISTRY.exists():
        errors.extend(check_registered_omx_artifacts())
    else:
        errors.extend(check_registered_omx_artifacts())
        errors.extend(check_tracked_omx_records(tracked_paths))

    return errors


def main() -> int:
    errors = [
        *check_codex_notes(),
        *check_history_records(),
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
