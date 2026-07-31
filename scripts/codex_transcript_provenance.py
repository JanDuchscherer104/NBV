#!/usr/bin/env python3
"""Capture and validate redacted commit-scoped Codex transcript provenance."""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import tempfile
from typing import Any, Iterable, Iterator, Sequence

from codex_transcript_extract import (
    dedupe_chat_messages,
    extract_session,
    find_exact_session_path,
)

SCHEMA = "aria-codex-commit-transcript/v1"
AUTHORITY = "non-authoritative commit provenance"
TRAILER = "Codex-Transcript"
ARTIFACT_PREFIX = ".agents/memory/transcripts/commits/"
STATE_NAME = "aria-codex-transcript-state.json"
CAPTURE_SCOPE_KIND = "timestamp-start"
ZERO_OID = "0" * 40
ENV_SECRET_NAMES = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "OPENAI_API_KEY",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "SLACK_TOKEN",
    "SLACK_BOT_TOKEN",
    "SLACK_APP_TOKEN",
    "API_KEY",
    "ACCESS_TOKEN",
    "AUTH_TOKEN",
    "TOKEN",
    "PASSWORD",
    "SECRET",
)
_ENV_SECRET_NAMES_PATTERN = "|".join(map(re.escape, ENV_SECRET_NAMES))
KEYED_SECRET_START_PATTERN = re.compile(
    rf"""
    (?<![A-Z0-9_])
    (?:"(?:{_ENV_SECRET_NAMES_PATTERN})"
      |'(?:{_ENV_SECRET_NAMES_PATTERN})'
      |(?:{_ENV_SECRET_NAMES_PATTERN}))
    [ \t\r\n]*[:=][ \t\r\n]*
    """,
    re.IGNORECASE | re.VERBOSE,
)
KEYED_SECRET_RESIDUAL_PATTERN = re.compile(
    rf"""
    (?<![A-Z0-9_])
    (?:"(?:{_ENV_SECRET_NAMES_PATTERN})"
      |'(?:{_ENV_SECRET_NAMES_PATTERN})'
      |(?:{_ENV_SECRET_NAMES_PATTERN}))
    [ \t\r\n]*[:=][ \t\r\n]*
    """,
    re.IGNORECASE | re.VERBOSE,
)
SANITIZER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private-key",
        re.compile(
            r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "authorization",
        re.compile(r"(?i)\bAuthorization\s*:\s*(?:Bearer|Basic)\s+[^\s,;]+"),
    ),
    ("bearer", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}")),
    (
        "url-credentials",
        re.compile(r"\b([a-z][a-z0-9+.-]*://)[^\s/@:]+:[^\s/@]+@", re.IGNORECASE),
    ),
    (
        "prefixed-token",
        re.compile(
            r"\b(?:AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{16,}|xox[baprs]-[A-Za-z0-9-]{12,})\b"
        ),
    ),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    ),
    (
        "email",
        re.compile(
            r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])",
            re.IGNORECASE,
        ),
    ),
    (
        "runtime-id",
        re.compile(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
            re.IGNORECASE,
        ),
    ),
    (
        "machine-path",
        re.compile(r"(?<![\w:<>])/(?:[^/\s'\"`<>]+)(?:/[^\s'\"`<>]*)?"),
    ),
    (
        "windows-path",
        re.compile(r"(?i)(?<![A-Z0-9_])[A-Z]:\\(?:[^\s'\"`<>]+\\?)+"),
    ),
    (
        "unc-path",
        re.compile(r"(?<!\\)\\\\[^\\\s'\"`<>]+\\[^\s'\"`<>]+"),
    ),
)
ALLOWED_REDACTION_CLASSES = frozenset(
    {name for name, _ in SANITIZER_PATTERNS}
    | {"repo-path", "home-path", "high-entropy-token", "env-secret"}
)
RUNTIME_TAGS = (
    "skill",
    "recommended_plugins",
    "app-context",
    "environment_context",
    "permissions instructions",
    "permissions_instructions",
    "apps_instructions",
    "plugins_instructions",
    "skills_instructions",
    "multi_agent_mode",
    "instructions",
    "identity",
    "constraints",
    "scope_guard",
    "ask_gate",
    "execution_loop",
    "posture_overlay",
    "model_class_guidance",
    "native_subagent_leaf_guard",
    "developer",
    "system",
)
INJECTED_PREFIXES = tuple(f"<{tag}>" for tag in RUNTIME_TAGS) + (
    "# agents.md instructions",
    "<developer",
    "<system",
)


class ProvenanceError(RuntimeError):
    """Raised when transcript provenance violates the commit contract."""


def _run_git(repo: Path, *args: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ProvenanceError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def _run_git_bytes(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = (
            (result.stderr or result.stdout).decode("utf-8", errors="replace").strip()
        )
        raise ProvenanceError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def _nul_fields(data: bytes, *, context: str) -> list[bytes]:
    if not data:
        return []
    if not data.endswith(b"\0"):
        raise ProvenanceError(f"{context} is not NUL-delimited")
    return data[:-1].split(b"\0")


def _name_status_changes(
    repo: Path, *arguments: str
) -> list[tuple[str, tuple[bytes, ...]]]:
    fields = _nul_fields(
        _run_git_bytes(repo, *arguments, "-z"),
        context="Git name-status output",
    )
    changes: list[tuple[str, tuple[bytes, ...]]] = []
    index = 0
    while index < len(fields):
        try:
            status = fields[index].decode("ascii")
        except UnicodeDecodeError as error:
            raise ProvenanceError("Git name-status output is malformed") from error
        if status[:1] in {"R", "C"}:
            score = status[1:]
            status_is_valid = (
                1 <= len(score) <= 3 and score.isdigit() and int(score) <= 100
            )
        else:
            status_is_valid = status in {"A", "D", "M", "T", "U", "X", "B"}
        if not status_is_valid:
            raise ProvenanceError("Git name-status output has an invalid status")
        path_count = 2 if status.startswith(("R", "C")) else 1
        path_start = index + 1
        path_end = path_start + path_count
        if path_end > len(fields):
            raise ProvenanceError("Git name-status output is malformed")
        changes.append((status, tuple(fields[path_start:path_end])))
        index = path_end
    return changes


def _transcript_path(raw_path: bytes) -> str:
    try:
        return raw_path.decode("ascii")
    except UnicodeDecodeError as error:
        raise ProvenanceError("transcript artifact path is not ASCII") from error


def _repo_root(repo: Path) -> Path:
    return Path(_run_git(repo, "rev-parse", "--show-toplevel")).resolve()


def _common_dir(repo: Path) -> Path:
    value = _run_git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(value).resolve()


def _git_dir(repo: Path) -> Path:
    return Path(_run_git(repo, "rev-parse", "--absolute-git-dir")).resolve()


def _worktree_paths(repo: Path) -> list[Path]:
    output = _run_git(repo, "worktree", "list", "--porcelain")
    return [
        Path(line.removeprefix("worktree ")).resolve()
        for line in output.splitlines()
        if line.startswith("worktree ")
    ]


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_timestamp(value: str, *, context: str) -> tuple[datetime, str]:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (AttributeError, ValueError) as error:
        raise ProvenanceError(f"{context} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ProvenanceError(f"{context} must include a UTC offset")
    parsed = parsed.astimezone(timezone.utc)
    return (
        parsed,
        parsed.isoformat(timespec="microseconds").replace("+00:00", "Z"),
    )


def _select_capture_messages(
    messages: Sequence[dict[str, Any]], scope_start: str
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    start, canonical_start = _canonical_timestamp(
        scope_start, context="capture scope start"
    )
    selected: list[dict[str, Any]] = []
    for record in messages:
        timestamp = record.get("timestamp")
        if not isinstance(timestamp, str):
            continue
        try:
            message_time, _ = _canonical_timestamp(
                timestamp, context="session message timestamp"
            )
        except ProvenanceError:
            continue
        if message_time >= start:
            selected.append(record)
    return selected, {
        "kind": CAPTURE_SCOPE_KIND,
        "start_timestamp": canonical_start,
    }


def _load_json_without_duplicates(data: bytes) -> dict[str, object]:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ProvenanceError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(data, object_pairs_hook=reject_duplicates)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ProvenanceError(f"malformed transcript artifact JSON: {error}") from error
    if not isinstance(value, dict):
        raise ProvenanceError("transcript artifact must be a JSON object")
    return value


def _snapshot_session(source: Path, common_dir: Path) -> tuple[Path, bytes]:
    snapshot_dir = common_dir / "aria-codex-snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    for _ in range(3):
        try:
            before = source.stat()
            data = source.read_bytes()
            after = source.stat()
        except OSError as error:
            raise ProvenanceError(f"cannot snapshot Codex session: {error}") from error
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            continue
        fd, temp_name = tempfile.mkstemp(
            prefix="session-", suffix=".jsonl.tmp", dir=snapshot_dir
        )
        temp = Path(temp_name)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        final = temp.with_suffix("")
        os.replace(temp, final)
        return final, data
    raise ProvenanceError("Codex session changed during capture; retry the commit")


def _session_belongs_to_repo(cwd: str | None, repo: Path) -> bool:
    if not cwd:
        return False
    try:
        return _common_dir(Path(cwd)) == _common_dir(repo)
    except (OSError, ProvenanceError):
        return False


def _reserved_name_match(body: str) -> tuple[str, int, bool] | None:
    """Return the reserved name, consumed width, and exact-spelling status."""
    for name in sorted(RUNTIME_TAGS, key=len, reverse=True):
        normalized = "".join(character for character in name if character.isalnum())
        pattern = r"[\s_-]*".join(map(re.escape, normalized))
        match = re.match(
            rf"{pattern}(?=$|[^A-Za-z0-9_-])",
            body,
            flags=re.IGNORECASE,
        )
        if match is None:
            continue
        raw_name = body[: match.end()]
        return name, match.end(), raw_name.casefold() == name.casefold()
    return None


def _tag_end(text: str, start: int) -> int | None:
    quote: str | None = None
    for index in range(start + 1, len(text)):
        character = text[index]
        if quote is not None:
            if character == quote:
                quote = None
            continue
        if character in {'"', "'"}:
            quote = character
        elif character == ">":
            return index
    return None


def _reserved_tag(
    body: str,
) -> tuple[str, bool] | None:
    closing = body.startswith("/")
    name_body = body[1:] if closing else body
    malformed_prefix = re.match(r"[^A-Za-z0-9_-]*", name_body)
    assert malformed_prefix is not None
    prefix_width = malformed_prefix.end()
    match = _reserved_name_match(name_body[prefix_width:])
    if match is None:
        return None
    name, name_width, exact = match
    if prefix_width or not exact:
        raise ProvenanceError("malformed reserved runtime tag syntax")
    remainder = name_body[name_width:]
    if closing:
        if remainder.strip():
            raise ProvenanceError("malformed reserved runtime closing tag")
        return name, True
    if remainder.rstrip().endswith("/"):
        raise ProvenanceError("self-closing reserved runtime tag is forbidden")
    attribute_pattern = re.compile(
        r"""(?:\s+[A-Za-z_:][A-Za-z0-9_.:-]*\s*=\s*(?:"[^"<>]*"|'[^'<>]*'))*\s*"""
    )
    if attribute_pattern.fullmatch(remainder) is None:
        raise ProvenanceError("malformed reserved runtime tag attributes")
    return name, False


def _reject_embedded_reserved_tag(body: str) -> None:
    """Reject reserved syntax hidden behind another angle delimiter."""
    cursor = 0
    while True:
        opening = body.find("<", cursor)
        if opening < 0:
            return
        if _reserved_tag(body[opening + 1 :]) is not None:
            raise ProvenanceError("reserved runtime tag has malformed delimiters")
        cursor = opening + 1


def _strip_reserved_tags(text: str) -> str:
    """Strip balanced reserved blocks or reject ambiguous reserved syntax."""
    output: list[str] = []
    stack: list[str] = []
    cursor = 0
    while cursor < len(text):
        opening = text.find("<", cursor)
        if opening < 0:
            if not stack:
                output.append(text[cursor:])
            break
        if not stack:
            output.append(text[cursor:opening])
        end = _tag_end(text, opening)
        if end is None:
            tail = text[opening + 1 :]
            if _reserved_tag(tail) is not None:
                raise ProvenanceError("unterminated reserved runtime tag")
            _reject_embedded_reserved_tag(tail)
            if not stack:
                output.append(text[opening:])
            break
        body = text[opening + 1 : end]
        _reject_embedded_reserved_tag(body)
        tag = _reserved_tag(body)
        if tag is None:
            if not stack:
                output.append(text[opening : end + 1])
            cursor = end + 1
            continue
        name, closing = tag
        if closing:
            if not stack or stack[-1] != name:
                raise ProvenanceError("mismatched reserved runtime closing tag")
            stack.pop()
        else:
            stack.append(name)
        cursor = end + 1
    if stack:
        raise ProvenanceError("unterminated reserved runtime tag")
    return "".join(output).strip()


def _is_injected(text: str) -> bool:
    lowered = text.lstrip().lower()
    if lowered.startswith(INJECTED_PREFIXES):
        return True
    if "# agents.md instructions for " in lowered or "<instructions>" in lowered:
        return True
    return "agent guidance" in lowered[:1600] and "source order" in lowered[:1600]


def _is_high_entropy_token(value: str) -> bool:
    if value == SCHEMA:
        return False
    classes = sum(
        bool(re.search(pattern, value))
        for pattern in (r"[a-z]", r"[A-Z]", r"\d", r"[_+/=\-]")
    )
    if classes < 2 or len(set(value)) < 10:
        return False
    probabilities = [count / len(value) for count in Counter(value).values()]
    entropy = -sum(
        probability * math.log2(probability) for probability in probabilities
    )
    return entropy >= 3.5


def _keyed_secret_value_end(text: str, start: int) -> int:
    cursor = start
    while cursor < len(text):
        character = text[cursor]
        if character in " \t\r\n,;}]":
            break
        if character == "\\":
            if cursor + 1 >= len(text):
                raise ProvenanceError(
                    "keyed secret contains an incomplete escape sequence"
                )
            cursor += 2
            continue
        if character in {'"', "'"}:
            quote = character
            cursor += 1
            while cursor < len(text):
                character = text[cursor]
                if character == quote:
                    cursor += 1
                    break
                if character == "\\" and quote == '"':
                    if cursor + 1 >= len(text):
                        raise ProvenanceError(
                            "keyed secret contains an incomplete escape sequence"
                        )
                    cursor += 2
                    continue
                cursor += 1
            else:
                raise ProvenanceError("keyed secret contains an unterminated quote")
            continue
        cursor += 1
    return cursor


def _keyed_secret_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = 0
    while match := KEYED_SECRET_START_PATTERN.search(text, cursor):
        end = _keyed_secret_value_end(text, match.end())
        spans.append((match.start(), end))
        cursor = end
    return spans


def _redact_keyed_secrets(text: str) -> tuple[str, int]:
    spans = _keyed_secret_spans(text)
    if not spans:
        return text, 0
    pieces: list[str] = []
    cursor = 0
    for start, end in spans:
        pieces.extend((text[cursor:start], "<redacted:env-secret>"))
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces), len(spans)


def _redact(text: str, repo_paths: Iterable[Path]) -> tuple[str, Counter[str]]:
    redacted = text
    counts: Counter[str] = Counter()
    for path in sorted(
        {str(path.resolve()) for path in repo_paths}, key=len, reverse=True
    ):
        occurrences = redacted.count(path)
        if occurrences:
            redacted = redacted.replace(path, "<redacted:repo-path>")
            counts["repo-path"] += occurrences
    home = str(Path.home().resolve())
    occurrences = redacted.count(home)
    if occurrences:
        redacted = redacted.replace(home, "<redacted:home-path>")
        counts["home-path"] += occurrences
    redacted, keyed_secret_count = _redact_keyed_secrets(redacted)
    counts["env-secret"] += keyed_secret_count
    for redaction_class, pattern in SANITIZER_PATTERNS:
        redacted, replacements = pattern.subn(f"<redacted:{redaction_class}>", redacted)
        counts[redaction_class] += replacements

    token_pattern = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9_+/=\-]{24,}(?![A-Za-z0-9])")

    def redact_entropy(match: re.Match[str]) -> str:
        value = match.group(0)
        if not _is_high_entropy_token(value):
            return value
        counts["high-entropy-token"] += 1
        return "<redacted:high-entropy-token>"

    redacted = token_pattern.sub(redact_entropy, redacted)
    return redacted.strip(), counts


def _residual_scan(text: str, *, serialized_artifact: bool = False) -> None:
    scan_text = text
    if serialized_artifact:
        scan_text = re.sub(
            r'"(?:canonical_payload_hash|message_hash|non_transcript_tree_hash|session_snapshot_hash|snapshot_id|thread_hash)":"[0-9a-f]+"',
            "",
            scan_text,
        )
        scan_text = re.sub(
            r'"(?:expected_parent|pre_commit_head)":(?:null|"[0-9a-f]+")', "", scan_text
        )
    try:
        stripped = _strip_reserved_tags(scan_text)
    except ProvenanceError as error:
        raise ProvenanceError(
            "sanitizer residual scan found malformed injected runtime context"
        ) from error
    if stripped != scan_text.strip() or _is_injected(scan_text):
        raise ProvenanceError("sanitizer residual scan found injected runtime context")
    if KEYED_SECRET_RESIDUAL_PATTERN.search(scan_text):
        raise ProvenanceError("sanitizer residual scan found env-secret content")
    decoded_only_classes = {"machine-path", "windows-path", "unc-path"}
    for redaction_class, pattern in SANITIZER_PATTERNS:
        if serialized_artifact and redaction_class in decoded_only_classes:
            continue
        if pattern.search(scan_text):
            raise ProvenanceError(
                f"sanitizer residual scan found {redaction_class} content"
            )
    entropy_text = re.sub(r'"[A-Za-z_]+"\s*:', "", scan_text)
    for token in re.findall(
        r"(?<![A-Za-z0-9])[A-Za-z0-9_+/=\-]{24,}(?![A-Za-z0-9])",
        entropy_text,
    ):
        if _is_high_entropy_token(token):
            raise ProvenanceError(
                "sanitizer residual scan found high-entropy token-like content"
            )


def _artifact_payload(
    *,
    thread_id: str,
    snapshot: bytes,
    messages: Sequence[dict[str, Any]],
    repo: Path,
    pre_commit_head: str | None,
    commit_mode: str,
    expected_parent: str,
    non_transcript_tree_hash: str,
    capture_scope: dict[str, str],
) -> dict[str, object]:
    sanitized: list[dict[str, str]] = []
    redaction_counts: Counter[str] = Counter()
    repo_paths = _worktree_paths(repo)
    for record in messages:
        role = str(record.get("role") or "")
        if role not in {"user", "assistant"}:
            continue
        if not _session_belongs_to_repo(str(record.get("cwd") or "") or None, repo):
            continue
        text = str(record.get("text") or "")
        try:
            text = _strip_reserved_tags(text)
        except ProvenanceError:
            continue
        if not text or _is_injected(text):
            continue
        clean, message_redactions = _redact(text, repo_paths)
        redaction_counts.update(message_redactions)
        if not clean:
            continue
        _residual_scan(clean)
        sanitized.append(
            {"role": role, "text": clean, "message_hash": _sha256(clean.encode())}
        )
    if not sanitized:
        raise ProvenanceError(
            "exact Codex session contains no eligible user/assistant messages"
        )
    snapshot_hash = _sha256(snapshot)
    snapshot_identity = {
        "session_snapshot_hash": snapshot_hash,
        "pre_commit_head": pre_commit_head,
        "commit_mode": commit_mode,
        "expected_parent": expected_parent,
        "non_transcript_tree_hash": non_transcript_tree_hash,
        "capture_scope": capture_scope,
    }
    body: dict[str, object] = {
        "schema": SCHEMA,
        "authority": AUTHORITY,
        "thread_hash": _sha256(thread_id.encode())[:12],
        "session_snapshot_hash": snapshot_hash,
        "snapshot_id": _sha256(_canonical_json(snapshot_identity)),
        "pre_commit_head": pre_commit_head,
        "commit_mode": commit_mode,
        "expected_parent": expected_parent,
        "non_transcript_tree_hash": non_transcript_tree_hash,
        "capture_scope": capture_scope,
        "redactions": {
            "replacement_count": sum(redaction_counts.values()),
            "classes": dict(
                sorted(
                    (name, count)
                    for name, count in redaction_counts.items()
                    if count > 0
                )
            ),
        },
        "messages": sanitized,
    }
    body["canonical_payload_hash"] = _sha256(_canonical_json(body))
    return body


def _state_path(repo: Path) -> Path:
    return _git_dir(repo) / STATE_NAME


def _read_state(repo: Path) -> dict[str, str]:
    path = _state_path(repo)
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProvenanceError(f"cannot read capture state: {error}") from error
    if not isinstance(value, dict):
        raise ProvenanceError("capture state must be a JSON object")
    return value


def _write_state(repo: Path, value: dict[str, str]) -> None:
    path = _state_path(repo)
    temp = path.with_suffix(".tmp")
    try:
        temp.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _artifact_parts(path_text: str) -> tuple[str, ...]:
    relative = Path(path_text)
    if (
        not path_text.startswith(ARTIFACT_PREFIX)
        or relative.is_absolute()
        or ".." in relative.parts
    ):
        raise ProvenanceError("unsafe transcript artifact path")
    return relative.parts


def _directory_open_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


@contextmanager
def _open_artifact_parent(
    repo: Path, path_text: str, *, create_parents: bool
) -> Iterator[tuple[int, str]]:
    repo = _repo_root(repo)
    parts = _artifact_parts(path_text)
    descriptor = os.open(repo, _directory_open_flags())
    try:
        for component in parts[:-1]:
            try:
                next_descriptor = os.open(
                    component, _directory_open_flags(), dir_fd=descriptor
                )
            except FileNotFoundError:
                if not create_parents:
                    raise ProvenanceError(
                        "transcript artifact parent is missing"
                    ) from None
                try:
                    os.mkdir(component, mode=0o755, dir_fd=descriptor)
                except FileExistsError:
                    pass
                next_descriptor = os.open(
                    component, _directory_open_flags(), dir_fd=descriptor
                )
            except OSError as error:
                raise ProvenanceError(
                    f"transcript artifact directory is a symlink or non-directory: {error}"
                ) from error
            os.close(descriptor)
            descriptor = next_descriptor
        yield descriptor, parts[-1]
    finally:
        os.close(descriptor)


def _destination_metadata(parent_fd: int, name: str) -> os.stat_result | None:
    try:
        metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(metadata.st_mode):
        raise ProvenanceError("transcript artifact destination is a symlink")
    if not stat.S_ISREG(metadata.st_mode):
        raise ProvenanceError("transcript artifact destination is not a regular file")
    return metadata


def _artifact_exists(repo: Path, path_text: str) -> bool:
    try:
        with _open_artifact_parent(repo, path_text, create_parents=False) as (
            parent_fd,
            name,
        ):
            return _destination_metadata(parent_fd, name) is not None
    except ProvenanceError as error:
        if "parent is missing" in str(error):
            return False
        raise


def _artifact_parent_is_current(repo: Path, path_text: str, parent_fd: int) -> bool:
    try:
        with _open_artifact_parent(repo, path_text, create_parents=False) as (
            current_fd,
            _,
        ):
            current = os.fstat(current_fd)
            opened = os.fstat(parent_fd)
            return (current.st_dev, current.st_ino) == (opened.st_dev, opened.st_ino)
    except ProvenanceError:
        return False


def _artifact_race_hook(stage: str, repo: Path, path_text: str) -> None:
    """Test seam for deterministic parent-swap race injection."""
    del stage, repo, path_text


def _write_artifact(repo: Path, path_text: str, data: bytes) -> Path:
    repo = _repo_root(repo)
    with _open_artifact_parent(repo, path_text, create_parents=True) as (
        parent_fd,
        destination_name,
    ):
        if _destination_metadata(parent_fd, destination_name) is not None:
            raise ProvenanceError("transcript artifact destination already exists")
        temporary_name = f".{destination_name}.{secrets.token_hex(16)}.tmp"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = -1
        linked = False
        try:
            descriptor = os.open(temporary_name, flags, 0o600, dir_fd=parent_fd)
            view = memoryview(data)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError("short transcript artifact write")
                view = view[written:]
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            _artifact_race_hook("before-link", repo, path_text)
            os.link(
                temporary_name,
                destination_name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
                follow_symlinks=False,
            )
            linked = True
            if not _artifact_parent_is_current(repo, path_text, parent_fd):
                raise OSError("artifact parent changed during write")
            os.unlink(temporary_name, dir_fd=parent_fd)
            os.fsync(parent_fd)
            linked = False
            return repo / Path(path_text)
        except OSError as error:
            raise ProvenanceError(
                f"cannot write transcript artifact: {error}"
            ) from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if linked:
                try:
                    os.unlink(destination_name, dir_fd=parent_fd)
                except FileNotFoundError:
                    pass
            try:
                os.unlink(temporary_name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass


def _unlink_artifact(repo: Path, path_text: str) -> None:
    try:
        with _open_artifact_parent(repo, path_text, create_parents=False) as (
            parent_fd,
            name,
        ):
            if _destination_metadata(parent_fd, name) is not None:
                os.unlink(name, dir_fd=parent_fd)
    except ProvenanceError as error:
        if "parent is missing" not in str(error):
            raise


def _restore_head_artifact(repo: Path, path_text: str) -> None:
    blob = subprocess.run(
        ["git", "-C", str(repo), "show", f"HEAD:{path_text}"],
        capture_output=True,
        check=False,
    )
    if blob.returncode:
        raise ProvenanceError("cannot restore prior transcript artifact from HEAD")
    _unlink_artifact(repo, path_text)
    _write_artifact(repo, path_text, blob.stdout)
    _run_git(repo, "add", "--", path_text)


def _remove_previous_attempt(repo: Path, path_text: str) -> None:
    if not path_text.startswith(ARTIFACT_PREFIX):
        return
    staged = _run_git(repo, "diff", "--cached", "--name-only", "--", path_text)
    if staged == path_text:
        head_blob = subprocess.run(
            ["git", "-C", str(repo), "show", f"HEAD:{path_text}"],
            capture_output=True,
            check=False,
        )
        _run_git(
            repo,
            "rm",
            "-q",
            "-f",
            "--cached",
            "--ignore-unmatch",
            "--",
            path_text,
        )
        if head_blob.returncode == 0:
            _unlink_artifact(repo, path_text)
            _write_artifact(repo, path_text, head_blob.stdout)
            _run_git(repo, "add", "--", path_text)
        else:
            _unlink_artifact(repo, path_text)


def _head_trailer_path(repo: Path) -> str | None:
    try:
        message = _run_git(repo, "log", "-1", "--format=%B")
    except ProvenanceError:
        return None
    trailers = _parse_trailers(message)
    return trailers[0][0] if len(trailers) == 1 else None


def _current_head(repo: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _expected_parent(repo: Path, *, amend: bool) -> str:
    head = _current_head(repo)
    if head is None:
        return ZERO_OID
    if not amend:
        return head
    parents = _parents(repo, head)
    if len(parents) > 1:
        raise ProvenanceError("amending a merge commit is not supported")
    return parents[0] if parents else ZERO_OID


def _inventory_hash(entries: Iterable[tuple[bytes, bytes, bytes, bytes]]) -> str:
    retained = sorted(
        (
            (mode, object_type, object_id, path)
            for mode, object_type, object_id, path in entries
            if not path.startswith(ARTIFACT_PREFIX.encode())
        ),
        key=lambda item: item[3],
    )
    paths_are_legacy_safe = all(
        b"\0" not in path
        and b"\t" not in path
        and b"\r" not in path
        and b"\n" not in path
        and _is_utf8(path)
        for _, _, _, path in retained
    )
    if paths_are_legacy_safe:
        return _sha256(
            b"".join(
                mode + b" " + object_type + b" " + object_id + b"\t" + path + b"\n"
                for mode, object_type, object_id, path in retained
            )
        )
    data = bytearray(b"\0aria-codex-inventory-v2\0")
    for entry in retained:
        for field in entry:
            data.extend(len(field).to_bytes(8, "big"))
            data.extend(field)
    return _sha256(bytes(data))


def _is_utf8(value: bytes) -> bool:
    try:
        value.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _index_inventory_hash(repo: Path) -> str:
    output = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "--stage", "-z"],
        capture_output=True,
        check=False,
    )
    if output.returncode:
        raise ProvenanceError("cannot inspect the proposed Git index")
    entries: list[tuple[bytes, bytes, bytes, bytes]] = []
    for record in _nul_fields(output.stdout, context="Git index inventory"):
        try:
            metadata, raw_path = record.split(b"\t", 1)
            raw_mode, raw_oid, raw_stage = metadata.split(b" ", 2)
            raw_mode.decode("ascii")
            raw_oid.decode("ascii")
            stage = raw_stage.decode("ascii")
        except (ValueError, UnicodeDecodeError) as error:
            raise ProvenanceError("Git index inventory is malformed") from error
        if stage != "0":
            raise ProvenanceError("unmerged Git index entries are not supported")
        object_type = b"commit" if raw_mode == b"160000" else b"blob"
        entries.append((raw_mode, object_type, raw_oid, raw_path))
    return _inventory_hash(entries)


def _commit_inventory_hash(repo: Path, commit: str) -> str:
    output = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "-r", "-z", "--full-tree", commit],
        capture_output=True,
        check=False,
    )
    if output.returncode:
        raise ProvenanceError(f"cannot inspect commit tree for {commit}")
    entries: list[tuple[bytes, bytes, bytes, bytes]] = []
    for record in _nul_fields(output.stdout, context="Git commit inventory"):
        try:
            metadata, raw_path = record.split(b"\t", 1)
            raw_mode, raw_type, raw_oid = metadata.split(b" ", 2)
            raw_mode.decode("ascii")
            raw_type.decode("ascii")
            raw_oid.decode("ascii")
            entries.append((raw_mode, raw_type, raw_oid, raw_path))
        except (ValueError, UnicodeDecodeError) as error:
            raise ProvenanceError("Git commit inventory is malformed") from error
    return _inventory_hash(entries)


def _validate_nonce(invocation_nonce: str) -> None:
    if re.fullmatch(r"[0-9a-f]{64}", invocation_nonce) is None:
        raise ProvenanceError("invocation nonce must be 32 cryptographic bytes in hex")


def _require_matching_state(repo: Path, invocation_nonce: str) -> dict[str, str]:
    _validate_nonce(invocation_nonce)
    state = _read_state(repo)
    if not state or state.get("invocation_nonce") != invocation_nonce:
        raise ProvenanceError(
            "capture state is missing, stale, or belongs to another invocation"
        )
    return state


def _ensure_not_merging(repo: Path) -> None:
    merge_head = Path(
        _run_git(
            repo,
            "rev-parse",
            "--path-format=absolute",
            "--git-path",
            "MERGE_HEAD",
        )
    )
    if merge_head.exists():
        raise ProvenanceError(
            "Codex transcript capture is not supported during an active merge"
        )


def capture(
    repo: Path,
    thread_id: str,
    sessions_root: Path,
    *,
    invocation_nonce: str,
    scope_start: str,
    amend: bool = False,
) -> str:
    """Capture, write, and stage exactly one artifact for ``thread_id``."""
    repo = _repo_root(repo)
    _validate_nonce(invocation_nonce)
    _ensure_not_merging(repo)
    prior_state = _read_state(repo)
    if prior_state:
        if prior_state.get("invocation_nonce") != invocation_nonce:
            raise ProvenanceError("refusing to reuse stale capture state")
        previous = prior_state.get("artifact")
        if previous:
            _remove_previous_attempt(repo, previous)
        previous_prior = prior_state.get("amend_prior")
        if previous_prior:
            _restore_head_artifact(repo, previous_prior)
        _state_path(repo).unlink(missing_ok=True)
    prior: str | None = None
    if amend:
        prior = _head_trailer_path(repo)
    source = find_exact_session_path(thread_id, [sessions_root.resolve()])
    if source is None:
        raise ProvenanceError(
            f"no exact Codex session found for CODEX_THREAD_ID={thread_id}"
        )
    snapshot_path, snapshot = _snapshot_session(source, _common_dir(repo))
    try:
        state = extract_session(snapshot_path, [snapshot_path.parent], None)
    finally:
        snapshot_path.unlink(missing_ok=True)
    if state is None or state.session_id != thread_id:
        raise ProvenanceError(
            "snapshotted session metadata does not match CODEX_THREAD_ID"
        )
    messages, capture_scope = _select_capture_messages(
        dedupe_chat_messages(state.chat_messages),
        scope_start,
    )
    pre_commit_head = _current_head(repo)
    commit_mode = "amend" if amend else "commit"
    expected_parent = _expected_parent(repo, amend=amend)
    non_transcript_tree_hash = _index_inventory_hash(repo)
    payload = _artifact_payload(
        thread_id=thread_id,
        snapshot=snapshot,
        messages=messages,
        repo=repo,
        pre_commit_head=pre_commit_head,
        commit_mode=commit_mode,
        expected_parent=expected_parent,
        non_transcript_tree_hash=non_transcript_tree_hash,
        capture_scope=capture_scope,
    )
    if not state.session_timestamp:
        raise ProvenanceError("Codex session metadata has no timestamp")
    try:
        parsed = datetime.fromisoformat(state.session_timestamp.replace("Z", "+00:00"))
    except ValueError as error:
        raise ProvenanceError(
            "Codex session metadata has an invalid timestamp"
        ) from error
    snapshot16 = str(payload["snapshot_id"])[:16]
    artifact = f"{ARTIFACT_PREFIX}{parsed:%Y/%m}/ct1-{payload['thread_hash']}-{snapshot16}.json"
    data = _canonical_json(payload)
    _validate_payload(data, artifact)
    artifact_hash = _sha256(data)
    replacement_staged = False
    artifact_written = False
    prior_removed = False
    try:
        _write_artifact(repo, artifact, data)
        artifact_written = True
        try:
            _run_git(repo, "add", "--", artifact)
            replacement_staged = True
        except ProvenanceError:
            _unlink_artifact(repo, artifact)
            raise
        staged = subprocess.run(
            ["git", "-C", str(repo), "show", f":{artifact}"],
            capture_output=True,
            check=False,
        )
        if staged.returncode or staged.stdout != data:
            raise ProvenanceError("staged transcript artifact differs from capture")
        _validate_payload(staged.stdout, artifact)
        if prior and prior != artifact:
            _run_git(repo, "rm", "-q", "-f", "--", prior)
            prior_removed = True
        _write_state(
            repo,
            {
                "artifact": artifact,
                "artifact_hash": artifact_hash,
                "invocation_nonce": invocation_nonce,
                "commit_mode": commit_mode,
                "amend_prior": prior if amend and prior else "",
            },
        )
    except (OSError, ProvenanceError) as error:
        rollback_errors: list[str] = []
        if replacement_staged:
            removal = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "rm",
                    "-q",
                    "-f",
                    "--cached",
                    "--ignore-unmatch",
                    "--",
                    artifact,
                ],
                capture_output=True,
                check=False,
            )
            if removal.returncode:
                rollback_errors.append("replacement index removal failed")
        if artifact_written:
            try:
                _unlink_artifact(repo, artifact)
            except (OSError, ProvenanceError) as cleanup_error:
                rollback_errors.append(str(cleanup_error))
        if prior and (prior_removed or not _artifact_exists(repo, prior)):
            try:
                _restore_head_artifact(repo, prior)
            except ProvenanceError as restore_error:
                rollback_errors.append(str(restore_error))
        _state_path(repo).unlink(missing_ok=True)
        if rollback_errors:
            raise ProvenanceError(
                f"capture failed ({error}); rollback failed: {'; '.join(rollback_errors)}"
            ) from error
        if isinstance(error, ProvenanceError):
            raise
        raise ProvenanceError(f"capture failed: {error}") from error
    return artifact


def _parse_trailers(message: str) -> list[tuple[str, str]]:
    pattern = re.compile(
        r"^Codex-Transcript:\s+(\S+)\s+sha256=([0-9a-f]{64})\s*$", re.MULTILINE
    )
    return [(match.group(1), match.group(2)) for match in pattern.finditer(message)]


def _require_one_trailer(message: str) -> tuple[str, str]:
    lines = re.findall(r"^Codex-Transcript:.*$", message, flags=re.MULTILINE)
    trailers = _parse_trailers(message)
    if len(lines) != 1 or len(trailers) != 1:
        raise ProvenanceError(
            "a transcript-enabled commit requires exactly one valid Codex-Transcript trailer"
        )
    return trailers[0]


def prepare_message(repo: Path, message_path: Path, invocation_nonce: str) -> None:
    """Replace any transcript trailer with the current capture pointer."""
    state = _require_matching_state(repo, invocation_nonce)
    artifact = state.get("artifact")
    artifact_hash = state.get("artifact_hash")
    if not artifact or not artifact_hash:
        raise ProvenanceError("Codex commit has no captured transcript state")
    message = message_path.read_text(encoding="utf-8")
    message = re.sub(
        r"\n?^Codex-Transcript:.*$", "", message, flags=re.MULTILINE
    ).rstrip()
    message_path.write_text(
        f"{message}\n\n{TRAILER}: {artifact} sha256={artifact_hash}\n",
        encoding="utf-8",
    )


def _validate_payload(data: bytes, expected_path: str) -> dict[str, object]:
    payload = _load_json_without_duplicates(data)
    if payload.get("schema") != SCHEMA or payload.get("authority") != AUTHORITY:
        raise ProvenanceError("transcript artifact schema or authority is invalid")
    required = {
        "schema",
        "authority",
        "thread_hash",
        "session_snapshot_hash",
        "snapshot_id",
        "pre_commit_head",
        "commit_mode",
        "expected_parent",
        "non_transcript_tree_hash",
        "capture_scope",
        "redactions",
        "messages",
        "canonical_payload_hash",
    }
    if set(payload) != required:
        raise ProvenanceError("transcript artifact fields are invalid")
    if (
        not re.fullmatch(r"[0-9a-f]{12}", str(payload["thread_hash"]))
        or not re.fullmatch(r"[0-9a-f]{64}", str(payload["session_snapshot_hash"]))
        or not re.fullmatch(r"[0-9a-f]{64}", str(payload["snapshot_id"]))
    ):
        raise ProvenanceError("transcript artifact hashes are malformed")
    path_match = re.fullmatch(
        r"\.agents/memory/transcripts/commits/\d{4}/\d{2}/ct1-([0-9a-f]{12})-([0-9a-f]{16})\.json",
        expected_path,
    )
    if path_match is None or path_match.groups() != (
        payload["thread_hash"],
        str(payload["snapshot_id"])[:16],
    ):
        raise ProvenanceError("transcript artifact path does not match its hashes")
    pre_commit_head = payload["pre_commit_head"]
    if (
        pre_commit_head is not None
        and re.fullmatch(r"[0-9a-f]{40}", str(pre_commit_head)) is None
    ):
        raise ProvenanceError("pre-commit HEAD is malformed")
    if payload["commit_mode"] not in {"commit", "amend"}:
        raise ProvenanceError("commit mode is invalid")
    if re.fullmatch(r"[0-9a-f]{40}", str(payload["expected_parent"])) is None:
        raise ProvenanceError("expected commit parent is malformed")
    if re.fullmatch(r"[0-9a-f]{64}", str(payload["non_transcript_tree_hash"])) is None:
        raise ProvenanceError("non-transcript tree hash is malformed")
    capture_scope = payload["capture_scope"]
    if not isinstance(capture_scope, dict) or set(capture_scope) != {
        "kind",
        "start_timestamp",
    }:
        raise ProvenanceError("capture scope is invalid")
    if capture_scope.get("kind") != CAPTURE_SCOPE_KIND:
        raise ProvenanceError("capture scope kind is invalid")
    start_timestamp = capture_scope.get("start_timestamp")
    if not isinstance(start_timestamp, str):
        raise ProvenanceError("capture scope start timestamp is invalid")
    _, canonical_start = _canonical_timestamp(
        start_timestamp, context="capture scope start"
    )
    if start_timestamp != canonical_start:
        raise ProvenanceError("capture scope start timestamp is not canonical")
    expected_snapshot_id = _sha256(
        _canonical_json(
            {
                "session_snapshot_hash": payload["session_snapshot_hash"],
                "pre_commit_head": pre_commit_head,
                "commit_mode": payload["commit_mode"],
                "expected_parent": payload["expected_parent"],
                "non_transcript_tree_hash": payload["non_transcript_tree_hash"],
                "capture_scope": capture_scope,
            }
        )
    )
    if payload["snapshot_id"] != expected_snapshot_id:
        raise ProvenanceError("snapshot identity hash mismatch")
    redactions = payload["redactions"]
    if not isinstance(redactions, dict) or set(redactions) != {
        "replacement_count",
        "classes",
    }:
        raise ProvenanceError("redaction summary is invalid")
    classes = redactions["classes"]
    if not isinstance(classes, dict) or not all(
        isinstance(key, str)
        and key in ALLOWED_REDACTION_CLASSES
        and isinstance(value, int)
        and not isinstance(value, bool)
        and value > 0
        for key, value in classes.items()
    ):
        raise ProvenanceError("redaction classes are invalid")
    replacement_count = redactions["replacement_count"]
    if (
        not isinstance(replacement_count, int)
        or isinstance(replacement_count, bool)
        or replacement_count != sum(classes.values())
    ):
        raise ProvenanceError("redaction replacement count is invalid")
    messages = payload["messages"]
    if not isinstance(messages, list) or not messages:
        raise ProvenanceError("transcript artifact messages must be a non-empty list")
    for message in messages:
        if not isinstance(message, dict) or set(message) != {
            "role",
            "text",
            "message_hash",
        }:
            raise ProvenanceError("transcript message fields are invalid")
        text = message.get("text")
        if message.get("role") not in {"user", "assistant"} or not isinstance(
            text, str
        ):
            raise ProvenanceError("transcript message role or text is invalid")
        if message.get("message_hash") != _sha256(text.encode()):
            raise ProvenanceError("transcript message hash mismatch")
        if _is_injected(text):
            raise ProvenanceError(
                "transcript artifact contains injected runtime context"
            )
        _residual_scan(text)
    canonical_hash = payload.pop("canonical_payload_hash")
    if canonical_hash != _sha256(_canonical_json(payload)):
        raise ProvenanceError("transcript canonical payload hash mismatch")
    payload["canonical_payload_hash"] = canonical_hash
    canonical = _canonical_json(payload)
    if data != canonical:
        raise ProvenanceError("transcript artifact bytes are not canonical JSON")
    _residual_scan(canonical.decode("utf-8"), serialized_artifact=True)
    return payload


def validate_message(
    repo: Path,
    message_path: Path,
    *,
    invocation_nonce: str | None = None,
    require_state: bool = False,
) -> None:
    """Validate a trailer and its staged artifact without reading session storage."""
    message = message_path.read_text(encoding="utf-8")
    path, trailer_hash = _require_one_trailer(message)
    if require_state:
        if invocation_nonce is None:
            raise ProvenanceError("marked Codex commit requires an invocation nonce")
        state = _require_matching_state(repo, invocation_nonce)
        if state.get("artifact") != path or state.get("artifact_hash") != trailer_hash:
            raise ProvenanceError(
                "message trailer does not match the current invocation state"
            )
    if not path.startswith(ARTIFACT_PREFIX):
        raise ProvenanceError(
            "Codex-Transcript points outside the commit transcript directory"
        )
    data = subprocess.run(
        ["git", "-C", str(repo), "show", f":{path}"], capture_output=True, check=False
    )
    if data.returncode:
        raise ProvenanceError("Codex-Transcript artifact is not staged")
    if _sha256(data.stdout) != trailer_hash:
        raise ProvenanceError("Codex-Transcript trailer hash mismatch")
    payload = _validate_payload(data.stdout, path)
    if payload["non_transcript_tree_hash"] != _index_inventory_hash(repo):
        raise ProvenanceError("transcript artifact does not bind the proposed index")
    if payload["expected_parent"] != _expected_parent(
        repo, amend=payload["commit_mode"] == "amend"
    ):
        raise ProvenanceError("transcript artifact does not bind the proposed parent")
    staged = _nul_fields(
        _run_git_bytes(repo, "diff", "--cached", "--name-only", "-z"),
        context="Git staged-path output",
    )
    artifact_prefix = ARTIFACT_PREFIX.encode()
    staged_transcripts = {
        _transcript_path(item) for item in staged if item.startswith(artifact_prefix)
    }
    allowed = {path}
    amend = require_state and _read_state(repo).get("commit_mode") == "amend"
    if amend:
        previous = _head_trailer_path(repo)
        if previous:
            allowed.add(previous)
    if path not in staged_transcripts and not (
        amend and path == _head_trailer_path(repo)
    ):
        raise ProvenanceError("Codex-Transcript artifact is not part of this commit")
    if not staged_transcripts <= allowed:
        raise ProvenanceError("commit stages an unrelated transcript artifact")


def clear_state(repo: Path, invocation_nonce: str, *, cleanup_artifact: bool) -> None:
    """Clear only the matching invocation state, optionally removing its artifact."""
    state = _read_state(repo)
    if not state:
        return
    if state.get("invocation_nonce") != invocation_nonce:
        raise ProvenanceError("refusing to clear state from another invocation")
    if cleanup_artifact and state.get("artifact"):
        _remove_previous_attempt(repo, state["artifact"])
        amend_prior = state.get("amend_prior")
        if amend_prior:
            _restore_head_artifact(repo, amend_prior)
    _state_path(repo).unlink(missing_ok=True)


def _commit_message(repo: Path, commit: str) -> str:
    return _run_git(repo, "show", "-s", "--format=%B", commit)


def _parents(repo: Path, commit: str) -> list[str]:
    fields = _run_git(repo, "rev-list", "--parents", "-n", "1", commit).split()
    return fields[1:]


def _transcript_tree(repo: Path, commit: str) -> dict[str, str]:
    records = _nul_fields(
        _run_git_bytes(
            repo,
            "ls-tree",
            "-r",
            "-z",
            "--full-tree",
            commit,
            "--",
            ARTIFACT_PREFIX,
        ),
        context="Git transcript tree output",
    )
    result: dict[str, str] = {}
    for record in records:
        try:
            metadata, raw_path = record.split(b"\t", 1)
            object_id = metadata.split()[2].decode("ascii")
        except (IndexError, UnicodeDecodeError, ValueError) as error:
            raise ProvenanceError("Git transcript tree output is malformed") from error
        path = _transcript_path(raw_path)
        result[path] = object_id
    return result


def _validate_merge_commit(repo: Path, commit: str, parents: Sequence[str]) -> None:
    message = _commit_message(repo, commit)
    if re.search(r"^Codex-Transcript:.*$", message, flags=re.MULTILINE):
        raise ProvenanceError(
            f"merge commit {commit} may not author a transcript trailer"
        )
    merge_tree = _transcript_tree(repo, commit)
    parent_trees = [_transcript_tree(repo, parent) for parent in parents]
    inherited_paths = set().union(*(tree.keys() for tree in parent_trees))
    if set(merge_tree) != inherited_paths:
        raise ProvenanceError(
            f"merge commit {commit} created or deleted a transcript artifact"
        )
    for path in sorted(inherited_paths):
        inherited_ids = {tree[path] for tree in parent_trees if path in tree}
        if merge_tree[path] not in inherited_ids or any(
            path in tree and tree[path] != merge_tree[path] for tree in parent_trees
        ):
            raise ProvenanceError(
                f"merge commit {commit} modified transcript artifact {path}"
            )


def validate_range(repo: Path, base: str, head: str) -> None:
    """Validate transcript additions and pointers for every commit in a range."""
    if not base:
        head_parents = _parents(repo, head)
        base = head_parents[0] if head_parents else ZERO_OID
    if set(base) == {"0"}:
        commits = _run_git(repo, "rev-list", "--reverse", head).splitlines()
    else:
        commits = _run_git(
            repo, "rev-list", "--reverse", f"{base}..{head}"
        ).splitlines()
    for commit in commits:
        parents = _parents(repo, commit)
        if len(parents) > 1:
            _validate_merge_commit(repo, commit, parents)
            continue
        if parents:
            changes = _name_status_changes(
                repo,
                "diff",
                "--name-status",
                "--no-renames",
                parents[0],
                commit,
            )
        else:
            changes = _name_status_changes(
                repo,
                "diff-tree",
                "--root",
                "--no-commit-id",
                "--name-status",
                "--no-renames",
                "-r",
                commit,
            )
        artifact_prefix = ARTIFACT_PREFIX.encode()
        transcript_changes = [
            (status, _transcript_path(raw_path))
            for status, raw_paths in changes
            for raw_path in raw_paths
            if raw_path.startswith(artifact_prefix)
        ]
        commit_message = _commit_message(repo, commit)
        trailer_lines = re.findall(
            r"^Codex-Transcript:.*$", commit_message, flags=re.MULTILINE
        )
        trailers = _parse_trailers(commit_message)
        if not trailers and not transcript_changes:
            continue
        if any(status != "A" for status, _ in transcript_changes):
            raise ProvenanceError(
                f"commit {commit} may not modify or delete a transcript artifact"
            )
        if len(trailer_lines) != 1 or len(trailers) != 1:
            raise ProvenanceError(
                f"commit {commit} requires exactly one transcript trailer"
            )
        added = [path for status, path in transcript_changes if status == "A"]
        if len(added) != 1 or len(transcript_changes) != 1:
            raise ProvenanceError(
                f"commit {commit} must add exactly one transcript artifact and may not modify or delete one"
            )
        path, trailer_hash = trailers[0]
        if path != added[0]:
            raise ProvenanceError(
                f"commit {commit} trailer does not point to its added artifact"
            )
        result = subprocess.run(
            ["git", "-C", str(repo), "show", f"{commit}:{path}"],
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise ProvenanceError(f"commit {commit} transcript artifact is unreadable")
        data = result.stdout
        if _sha256(data) != trailer_hash:
            raise ProvenanceError(f"commit {commit} transcript trailer hash mismatch")
        payload = _validate_payload(data, path)
        actual_parent = parents[0] if parents else ZERO_OID
        if payload["expected_parent"] != actual_parent:
            raise ProvenanceError(
                f"commit {commit} transcript artifact was captured for a different parent"
            )
        if payload["non_transcript_tree_hash"] != _commit_inventory_hash(repo, commit):
            raise ProvenanceError(
                f"commit {commit} transcript artifact was captured for different content"
            )


def validate_commit_args(arguments: Sequence[str]) -> bool:
    """Validate the bounded non-path commit modes supported by the wrapper."""
    prohibited_long = (
        "--no-verify",
        "--only",
        "--include",
        "--interactive",
        "--patch",
        "--pathspec-from-file",
        "--pathspec-file-nul",
    )
    flags = {
        "--all",
        "--verbose",
        "--quiet",
        "--allow-empty",
        "--allow-empty-message",
        "--no-edit",
        "--dry-run",
        "--status",
        "--short",
        "--branch",
        "--porcelain",
        "--long",
        "--no-post-rewrite",
        "--signoff",
        "--reset-author",
        "-a",
        "-v",
        "-q",
        "-s",
    }
    value_options = {
        "--message",
        "--file",
        "--reuse-message",
        "--reedit-message",
        "--author",
        "--date",
        "--cleanup",
        "--fixup",
        "--squash",
        "--trailer",
        "--gpg-sign",
        "-m",
        "-F",
        "-C",
        "-c",
        "-S",
    }
    amend = False
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--":
            raise ProvenanceError("path-limited commits are not supported")
        if any(
            argument == option or argument.startswith(f"{option}=")
            for option in prohibited_long
        ):
            raise ProvenanceError(f"unsupported commit mode: {argument}")
        if argument == "--amend":
            amend = True
            index += 1
            continue
        if argument in flags:
            index += 1
            continue
        if argument in value_options:
            index += 2
            if index > len(arguments):
                raise ProvenanceError(f"missing value for commit option {argument}")
            continue
        if any(
            argument.startswith(f"{option}=")
            for option in value_options
            if option.startswith("--")
        ):
            index += 1
            continue
        if argument.startswith("-") and not argument.startswith("--"):
            cluster = argument[1:]
            if any(character in cluster for character in "noi"):
                raise ProvenanceError(f"unsupported commit mode: {argument}")
            value_position = next(
                (
                    cluster.find(character)
                    for character in "mFCcS"
                    if character in cluster
                ),
                -1,
            )
            if value_position >= 0 and value_position == len(cluster) - 1:
                index += 2
                if index > len(arguments):
                    raise ProvenanceError(f"missing value for commit option {argument}")
            elif value_position >= 0:
                index += 1
            elif set(cluster) <= set("avqs"):
                index += 1
            else:
                raise ProvenanceError(f"unsupported commit option: {argument}")
            continue
        raise ProvenanceError(
            f"bare commit pathspec or unsupported positional argument: {argument}"
        )
    return amend


def check_hooks(repo: Path) -> None:
    """Check the worktree-relative hook path and executable source hooks."""
    value = _run_git(repo, "config", "--local", "--get", "core.hooksPath")
    if value != "scripts/git_hooks":
        raise ProvenanceError("core.hooksPath must equal scripts/git_hooks")
    for name in ("pre-commit", "prepare-commit-msg", "commit-msg", "post-commit"):
        path = _repo_root(repo) / "scripts/git_hooks" / name
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ProvenanceError(f"hook source is missing or not executable: {path}")


def _main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    capture_parser = sub.add_parser("capture")
    capture_parser.add_argument("--repo", type=Path, default=Path.cwd())
    capture_parser.add_argument("--thread-id", required=True)
    capture_parser.add_argument("--scope-start", required=True)
    capture_parser.add_argument("--invocation-nonce", required=True)
    capture_parser.add_argument(
        "--sessions-root", type=Path, default=Path.home() / ".codex/sessions"
    )
    capture_parser.add_argument("--amend", action="store_true")
    prepare_parser = sub.add_parser("prepare-message")
    prepare_parser.add_argument("message", type=Path)
    prepare_parser.add_argument("--repo", type=Path, default=Path.cwd())
    prepare_parser.add_argument("--invocation-nonce", required=True)
    validate_parser = sub.add_parser("validate-message")
    validate_parser.add_argument("message", type=Path)
    validate_parser.add_argument("--repo", type=Path, default=Path.cwd())
    validate_parser.add_argument("--invocation-nonce")
    validate_parser.add_argument("--require-state", action="store_true")
    range_parser = sub.add_parser("validate-range")
    range_parser.add_argument("base")
    range_parser.add_argument("head")
    range_parser.add_argument("--repo", type=Path, default=Path.cwd())
    hooks_parser = sub.add_parser("check-hooks")
    hooks_parser.add_argument("--repo", type=Path, default=Path.cwd())
    clear_parser = sub.add_parser("clear-state")
    clear_parser.add_argument("--repo", type=Path, default=Path.cwd())
    clear_parser.add_argument("--invocation-nonce", required=True)
    clear_parser.add_argument("--cleanup-artifact", action="store_true")
    invocation_parser = sub.add_parser("validate-invocation")
    invocation_parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.command == "capture":
        print(
            capture(
                args.repo,
                args.thread_id,
                args.sessions_root,
                invocation_nonce=args.invocation_nonce,
                scope_start=args.scope_start,
                amend=args.amend,
            )
        )
    elif args.command == "prepare-message":
        prepare_message(args.repo, args.message, args.invocation_nonce)
    elif args.command == "validate-message":
        validate_message(
            args.repo,
            args.message,
            invocation_nonce=args.invocation_nonce,
            require_state=args.require_state,
        )
    elif args.command == "validate-range":
        validate_range(args.repo, args.base, args.head)
    elif args.command == "check-hooks":
        check_hooks(args.repo)
    elif args.command == "clear-state":
        clear_state(
            args.repo,
            args.invocation_nonce,
            cleanup_artifact=args.cleanup_artifact,
        )
    else:
        arguments = args.arguments
        if arguments and arguments[0] == "--":
            arguments = arguments[1:]
        print("amend" if validate_commit_args(arguments) else "commit")
    return 0


def main() -> int:
    try:
        return _main(sys.argv[1:])
    except ProvenanceError as error:
        print(f"transcript provenance error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
