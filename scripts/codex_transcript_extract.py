#!/usr/bin/env python3
"""Extract ARIA-NBV transcript evidence from local Codex session JSONL files.

The extractor keeps full raw Codex runtime transcripts out of repo memory. It
writes chat-only user/assistant transcript records, high-signal user-authored
records, and candidate distillates that LitKG can index through the existing
`.configs/litkg.toml` transcript source globs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterator, TextIO

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT_ROOT = REPO_ROOT
DEFAULT_CODEX_ROOT = Path.home() / ".codex" / "sessions"
RESTORED_CODEX_ROOT = (
    Path.home()
    / "Desktop"
    / "pre-essential-restore-20260425-234438"
    / ".codex"
    / "sessions"
)
TRANSCRIPT_ROOT = REPO_ROOT / ".agents" / "memory" / "transcripts"
PROJECT_MARKERS = ("ARIA-NBV", "aria-nbv", "aria_nbv", "/home/jd/repos/ARIA-NBV")
SCHEMA_VERSION = 1
STOPWORDS = {
    "a",
    "about",
    "after",
    "all",
    "also",
    "an",
    "and",
    "are",
    "as",
    "be",
    "by",
    "can",
    "current",
    "for",
    "from",
    "has",
    "have",
    "how",
    "in",
    "into",
    "is",
    "it",
    "its",
    "not",
    "of",
    "on",
    "or",
    "our",
    "should",
    "that",
    "the",
    "their",
    "this",
    "to",
    "under",
    "use",
    "uses",
    "using",
    "with",
}


@dataclass
class PendingQuestion:
    mode: str | None
    timestamp: str | None
    turn_id: str | None
    questions: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class SessionState:
    session_id: str | None = None
    session_timestamp: str | None = None
    cwd: str | None = None
    turn_id: str | None = None
    mode: str | None = None
    matched_by_cwd: bool = False
    matched_by_marker: bool = False
    chat_messages: list[dict[str, Any]] = field(default_factory=list)
    user_messages: list[dict[str, Any]] = field(default_factory=list)
    plan_answers: list[dict[str, Any]] = field(default_factory=list)
    pending_questions: dict[str, PendingQuestion] = field(default_factory=dict)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def is_under_path(path_text: str | None, root: Path) -> bool:
    if not path_text:
        return False
    try:
        path = Path(path_text).resolve()
        root = root.resolve()
        return path == root or root in path.parents
    except OSError:
        return False


def is_other_repo_checkout(path_text: str | None, project_root: Path) -> bool:
    if not path_text:
        return False
    try:
        path = Path(path_text).resolve()
        repos_root = Path.home() / "repos"
        if repos_root in path.parents and not is_under_path(path_text, project_root):
            return True
        parts = set(path.parts)
        if (
            ".codex" in parts
            and "worktrees" in parts
            and project_root.name not in parts
        ):
            return True
        return "prml-vslam" in parts
    except OSError:
        return False


def record_allowed_for_project(
    record: dict[str, Any],
    project_root: Path,
    *,
    session_marker_context: bool,
) -> bool:
    cwd = record.get("cwd")
    if is_under_path(str(cwd) if cwd else None, project_root):
        return True
    if is_other_repo_checkout(str(cwd) if cwd else None, project_root):
        return False
    return session_marker_context


def is_bootstrap_or_context_dump(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    first_line = stripped.splitlines()[0].strip()
    bootstrap_prefixes = (
        "# AGENTS.md instructions for ",
        "# Context from my IDE setup:",
        "<environment_context>",
        "<INSTRUCTIONS>",
    )
    if first_line.startswith(bootstrap_prefixes):
        return True
    if first_line == "# AGENTS.md instructions" or stripped.startswith(
        "<INSTRUCTIONS>"
    ):
        return True
    if "<INSTRUCTIONS>" in stripped[:500] and "Agent Guidance" in stripped[:1200]:
        return True
    return False


def jsonl_objects(path: Path) -> list[tuple[int, dict[str, Any]]]:
    objects: list[tuple[int, dict[str, Any]]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                objects.append((line_no, json.loads(line)))
            except json.JSONDecodeError:
                continue
    return objects


def content_text_from_message(payload: dict[str, Any]) -> str:
    chunks: list[str] = []
    for item in payload.get("content") or []:
        if isinstance(item, dict):
            text = item.get("text") or item.get("input_text") or ""
            if text:
                chunks.append(str(text))
    return "\n".join(chunks)


def session_root_label(path: Path, roots: list[Path]) -> tuple[str, str]:
    for index, root in enumerate(roots):
        try:
            rel = path.relative_to(root)
            label = "default" if root == DEFAULT_CODEX_ROOT else f"root_{index + 1}"
            if root == RESTORED_CODEX_ROOT:
                label = "restored_pre_20260425"
            return label, rel.as_posix()
        except ValueError:
            continue
    return "unknown", path.as_posix()


def build_source(
    path: Path,
    line_no: int,
    roots: list[Path],
) -> dict[str, Any]:
    root_label, relative_path = session_root_label(path, roots)
    return {
        "root": root_label,
        "session_path": relative_path,
        "line": line_no,
    }


def record_user_message(
    state: SessionState,
    *,
    text: str,
    timestamp: str | None,
    line_no: int,
    path: Path,
    roots: list[Path],
) -> None:
    if is_bootstrap_or_context_dump(text):
        return
    if any(marker in text for marker in PROJECT_MARKERS):
        state.matched_by_marker = True
    normalized = normalize_text(text)
    if not normalized:
        return
    state.user_messages.append(
        {
            "schema_version": SCHEMA_VERSION,
            "kind": "user_message",
            "timestamp": timestamp,
            "session_id": state.session_id,
            "session_timestamp": state.session_timestamp,
            "cwd": state.cwd,
            "turn_id": state.turn_id,
            "mode": state.mode,
            "text": text.strip(),
            "normalized_text": normalized,
            "content_hash": sha256_text(normalized),
            "source": build_source(path, line_no, roots),
        }
    )


def record_chat_message(
    state: SessionState,
    *,
    role: str,
    text: str,
    timestamp: str | None,
    line_no: int,
    path: Path,
    roots: list[Path],
    phase: str | None = None,
) -> None:
    if role not in {"user", "assistant"}:
        return
    if is_bootstrap_or_context_dump(text):
        return
    if any(marker in text for marker in PROJECT_MARKERS):
        state.matched_by_marker = True
    normalized = normalize_text(text)
    if not normalized:
        return
    state.chat_messages.append(
        {
            "schema_version": SCHEMA_VERSION,
            "kind": "chat_message",
            "role": role,
            "timestamp": timestamp,
            "session_id": state.session_id,
            "session_timestamp": state.session_timestamp,
            "cwd": state.cwd,
            "turn_id": state.turn_id,
            "mode": state.mode,
            "phase": phase,
            "text": text.strip(),
            "normalized_text": normalized,
            "content_hash": sha256_text(normalized),
            "source": build_source(path, line_no, roots),
        }
    )


def parse_request_questions(arguments: str) -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return {}

    questions: dict[str, dict[str, Any]] = {}
    for question in payload.get("questions") or []:
        if not isinstance(question, dict):
            continue
        question_id = str(question.get("id") or "").strip()
        if not question_id:
            continue
        questions[question_id] = {
            "id": question_id,
            "header": question.get("header"),
            "question": question.get("question"),
            "options": question.get("options") or [],
        }
    return questions


def record_plan_answers(
    state: SessionState,
    *,
    call_id: str,
    output: str,
    timestamp: str | None,
    line_no: int,
    path: Path,
    roots: list[Path],
) -> None:
    pending = state.pending_questions.get(call_id)
    if pending is None or pending.mode != "plan":
        return
    try:
        payload = json.loads(output or "{}")
    except json.JSONDecodeError:
        return
    answers = payload.get("answers")
    if not isinstance(answers, dict) or not answers:
        return

    for question_id, answer_payload in answers.items():
        answer_list: list[str] = []
        if isinstance(answer_payload, dict):
            answer_list = answer_payload.get("answers") or []
        if not answer_list:
            continue
        question = pending.questions.get(str(question_id), {"id": str(question_id)})
        state.plan_answers.append(
            {
                "schema_version": SCHEMA_VERSION,
                "kind": "plan_mode_answer",
                "timestamp": timestamp,
                "session_id": state.session_id,
                "session_timestamp": state.session_timestamp,
                "cwd": state.cwd,
                "turn_id": pending.turn_id or state.turn_id,
                "mode": "plan",
                "call_id": call_id,
                "question": question,
                "answers": [str(answer) for answer in answer_list],
                "content_hash": sha256_text(
                    normalize_text(
                        json.dumps({question_id: answer_list}, sort_keys=True)
                    )
                ),
                "source": build_source(path, line_no, roots),
            }
        )


def extract_session(
    path: Path, roots: list[Path], project_root: Path
) -> SessionState | None:
    objects = jsonl_objects(path)
    if not objects:
        return None

    state = SessionState()
    for line_no, obj in objects:
        obj_type = obj.get("type")
        payload = obj.get("payload") or {}
        timestamp = obj.get("timestamp")

        if obj_type == "session_meta":
            state.session_id = payload.get("id") or state.session_id
            state.session_timestamp = payload.get("timestamp") or timestamp
            state.cwd = payload.get("cwd") or state.cwd
            state.matched_by_cwd = state.matched_by_cwd or is_under_path(
                state.cwd, project_root
            )
            continue

        if obj_type == "turn_context":
            state.turn_id = payload.get("turn_id") or state.turn_id
            state.cwd = payload.get("cwd") or state.cwd
            mode_payload = payload.get("collaboration_mode") or {}
            state.mode = mode_payload.get("mode") or state.mode
            state.matched_by_cwd = state.matched_by_cwd or is_under_path(
                state.cwd, project_root
            )
            continue

        if obj_type == "event_msg":
            event_type = payload.get("type")
            if event_type == "task_started":
                state.turn_id = payload.get("turn_id") or state.turn_id
                state.mode = payload.get("collaboration_mode_kind") or state.mode
            elif event_type == "user_message":
                message = str(payload.get("message") or "")
                record_chat_message(
                    state,
                    role="user",
                    text=message,
                    timestamp=timestamp,
                    line_no=line_no,
                    path=path,
                    roots=roots,
                )
                record_user_message(
                    state,
                    text=message,
                    timestamp=timestamp,
                    line_no=line_no,
                    path=path,
                    roots=roots,
                )
            continue

        if obj_type != "response_item":
            continue

        payload_type = payload.get("type")
        if payload_type == "message" and payload.get("role") in {
            "user",
            "assistant",
        }:
            role = str(payload.get("role") or "")
            text = content_text_from_message(payload)
            record_chat_message(
                state,
                role=role,
                text=text,
                timestamp=timestamp,
                line_no=line_no,
                path=path,
                roots=roots,
                phase=payload.get("phase"),
            )
            if role == "user":
                record_user_message(
                    state,
                    text=text,
                    timestamp=timestamp,
                    line_no=line_no,
                    path=path,
                    roots=roots,
                )
            continue

        if (
            payload_type == "function_call"
            and payload.get("name") == "request_user_input"
        ):
            call_id = str(payload.get("call_id") or "")
            if call_id:
                state.pending_questions[call_id] = PendingQuestion(
                    mode=state.mode,
                    timestamp=timestamp,
                    turn_id=state.turn_id,
                    questions=parse_request_questions(
                        str(payload.get("arguments") or "")
                    ),
                )
            continue

        if payload_type == "function_call_output":
            call_id = str(payload.get("call_id") or "")
            record_plan_answers(
                state,
                call_id=call_id,
                output=str(payload.get("output") or ""),
                timestamp=timestamp,
                line_no=line_no,
                path=path,
                roots=roots,
            )

    state.chat_messages = [
        record
        for record in state.chat_messages
        if record_allowed_for_project(
            record,
            project_root,
            session_marker_context=state.matched_by_marker,
        )
    ]
    state.user_messages = [
        record
        for record in state.user_messages
        if record_allowed_for_project(
            record,
            project_root,
            session_marker_context=state.matched_by_marker,
        )
    ]
    state.plan_answers = [
        record
        for record in state.plan_answers
        if record_allowed_for_project(
            record,
            project_root,
            session_marker_context=state.matched_by_marker,
        )
    ]
    if not (state.matched_by_cwd or state.matched_by_marker):
        return None
    if not (state.chat_messages or state.user_messages or state.plan_answers):
        return None
    return state


def dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for record in sorted(
        records,
        key=lambda item: (
            str(item.get("timestamp") or ""),
            str((item.get("source") or {}).get("session_path") or ""),
            str((item.get("source") or {}).get("line") or ""),
        ),
    ):
        key = f"{record.get('kind')}:{record.get('content_hash')}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def dedupe_chat_messages(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for record in sorted(
        records,
        key=lambda item: (
            str(item.get("timestamp") or ""),
            str((item.get("source") or {}).get("session_path") or ""),
            str((item.get("source") or {}).get("line") or ""),
        ),
    ):
        key = ":".join(
            [
                str(record.get("kind") or ""),
                str(record.get("role") or ""),
                str(record.get("session_id") or ""),
                str(record.get("timestamp") or ""),
                str(record.get("content_hash") or ""),
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def answer_label(answer: str) -> str:
    return re.sub(r"\s*\(Recommended\)\s*$", "", answer).strip()


def classify_text(text: str, question_id: str = "") -> tuple[str, str, str]:
    lowered = f"{question_id} {text}".lower()
    if any(
        token in lowered for token in ("owner", "preference", "human", "tone", "style")
    ):
        return "human-owner preference", "candidate", "medium"
    if any(
        token in lowered
        for token in ("todo", "issue", "backlog", "implement", "fix", "add ")
    ):
        return "backlog/action item", "candidate", "medium"
    if any(
        token in lowered
        for token in ("api", "schema", "store", "format", "version", "test", "lint")
    ):
        return "technical decision", "candidate", "medium"
    if any(
        token in lowered
        for token in ("decision", "must", "should", "source", "canonical", "thesis")
    ):
        return "durable repo decision", "candidate", "medium"
    if question_id:
        return "working project decision", "candidate", "low"
    return "reject/noise", "reject", "low"


def distill_records(
    user_messages: list[dict[str, Any]],
    plan_answers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    distillates: list[dict[str, Any]] = []

    for record in plan_answers:
        question = record.get("question") or {}
        question_id = str(question.get("id") or "")
        answers = [answer_label(str(answer)) for answer in record.get("answers") or []]
        answer_text = "; ".join(answer for answer in answers if answer)
        prompt = str(question.get("question") or "").strip()
        category, status, confidence = classify_text(answer_text, question_id)
        distillates.append(
            {
                "schema_version": SCHEMA_VERSION,
                "kind": "candidate_decision",
                "status": status,
                "category": category,
                "confidence": confidence,
                "summary": f"Plan-mode answer `{question_id}` selected: {answer_text}",
                "prompt": prompt,
                "evidence_hashes": [record["content_hash"]],
                "source_records": [record["source"]],
                "promotion_target": promotion_target_for(category),
            }
        )

    for record in user_messages:
        normalized = str(record.get("normalized_text") or "")
        category, status, confidence = classify_text(normalized)
        if status == "reject" and len(normalized) > 160:
            continue
        summary = normalized[:240] + ("..." if len(normalized) > 240 else "")
        distillates.append(
            {
                "schema_version": SCHEMA_VERSION,
                "kind": "candidate_decision",
                "status": status,
                "category": category,
                "confidence": confidence,
                "summary": summary,
                "prompt": None,
                "evidence_hashes": [record["content_hash"]],
                "source_records": [record["source"]],
                "promotion_target": promotion_target_for(category),
            }
        )

    return dedupe_distillates(distillates)


def promotion_target_for(category: str) -> str | None:
    if category in {
        "durable repo decision",
        "technical decision",
        "working project decision",
    }:
        return None
    if category == "human-owner preference":
        return ".agents/references/human_owner_intent.md"
    if category == "backlog/action item":
        return ".agents/issues.toml|.agents/todos.toml|.agents/refactors.toml"
    return None


def dedupe_distillates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, tuple[str, ...]]] = set()
    deduped: list[dict[str, Any]] = []
    for record in records:
        key = (
            str(record.get("summary") or ""),
            tuple(str(item) for item in record.get("evidence_hashes") or []),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def significant_tokens(text: str) -> set[str]:
    tokens = {
        token
        for token in re.findall(r"[a-z0-9_][a-z0-9_\-]{2,}", text.lower())
        if token not in STOPWORDS
    }
    return tokens


def indexed_doc_chunks(text: str) -> list[tuple[str, set[str]]]:
    chunks: list[tuple[str, set[str]]] = []
    for raw_chunk in re.split(r"\n\s*(?:[-*]|\d+[.)]|\#\#)", text):
        chunk = normalize_text(raw_chunk)
        tokens = significant_tokens(chunk)
        if len(tokens) >= 3:
            chunks.append((chunk, tokens))
    return chunks


def best_chunk_overlap(
    text: str, chunks: list[tuple[str, set[str]]]
) -> tuple[float, str | None]:
    tokens = significant_tokens(text)
    if not tokens:
        return 0.0, None
    best_score = 0.0
    best_chunk: str | None = None
    denominator = min(len(tokens), 18)
    for chunk, chunk_tokens in chunks:
        score = len(tokens & chunk_tokens) / denominator
        if score > best_score:
            best_score = score
            best_chunk = chunk
    return best_score, best_chunk


def review_distillates(
    distillates: list[dict[str, Any]],
    *,
    legacy_decision_text: str,
    preference_text: str = "",
) -> list[dict[str, Any]]:
    """Mark candidate distillates with a conservative promotion review status.

    The review pass is intentionally lexical and conservative: it can identify
    candidates overlapping legacy migration evidence and candidates that still
    need owner review, but it never promotes transcript evidence to current truth.
    """

    legacy_decision_chunks = indexed_doc_chunks(legacy_decision_text)
    preference_chunks = indexed_doc_chunks(preference_text)
    reviewed: list[dict[str, Any]] = []

    for record in distillates:
        candidate = dict(record)
        review_text = " ".join(
            str(value or "")
            for value in (
                candidate.get("summary"),
                candidate.get("prompt"),
                candidate.get("category"),
            )
        )

        if candidate.get("status") == "reject":
            candidate.update(
                {
                    "review_status": "rejected_noise",
                    "review_reason": "classifier rejected this record as low-signal transcript noise",
                }
            )
            reviewed.append(candidate)
            continue

        is_preference = (
            candidate.get("promotion_target")
            == ".agents/references/human_owner_intent.md"
        )
        is_decision = candidate.get("category") in {
            "durable repo decision",
            "technical decision",
            "working project decision",
        }
        chunks = (
            preference_chunks
            if is_preference
            else legacy_decision_chunks
            if is_decision
            else []
        )
        overlap, matched_chunk = best_chunk_overlap(review_text, chunks)
        candidate["supporting_overlap"] = round(overlap, 3)
        if matched_chunk:
            candidate["supporting_match"] = matched_chunk[:280]

        if is_decision:
            candidate.update(
                {
                    "review_status": "needs_owner_review",
                    "review_reason": "compare transcript evidence with the source-order owner; legacy decision journals are migration evidence only",
                }
            )
        elif is_preference and overlap >= 0.55:
            candidate.update(
                {
                    "review_status": "already_reflected",
                    "review_reason": "lexical overlap with the human-owner preference surface is high enough for evidence-only indexing",
                }
            )
        elif is_preference:
            candidate.update(
                {
                    "review_status": "needs_preference_review",
                    "review_reason": "not clearly reflected in human-owner intent; inspect before promotion",
                }
            )
        elif candidate.get("promotion_target"):
            candidate.update(
                {
                    "review_status": "route_to_backlog_review",
                    "review_reason": "actionable-looking transcript evidence; add to agents DB only if current and not duplicate",
                }
            )
        else:
            candidate.update(
                {
                    "review_status": "evidence_only",
                    "review_reason": "retained as searchable transcript evidence, not a canonical decision",
                }
            )
        reviewed.append(candidate)

    return reviewed


def gather_records(
    roots: list[Path],
    project_root: Path,
) -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], Counter[str]
]:
    counter: Counter[str] = Counter()
    all_chat_messages: list[dict[str, Any]] = []
    all_user_messages: list[dict[str, Any]] = []
    all_plan_answers: list[dict[str, Any]] = []

    for root in roots:
        if not root.exists():
            counter["missing_roots"] += 1
            continue
        for path in sorted(root.rglob("*.jsonl")):
            counter["session_files_seen"] += 1
            state = extract_session(path, roots, project_root)
            if state is None:
                continue
            counter["candidate_sessions"] += 1
            if state.matched_by_cwd:
                counter["sessions_matched_by_cwd"] += 1
            if state.matched_by_marker:
                counter["sessions_matched_by_marker"] += 1
            if state.mode == "plan" or state.plan_answers:
                counter["sessions_with_plan_mode"] += 1
            all_chat_messages.extend(state.chat_messages)
            all_user_messages.extend(state.user_messages)
            all_plan_answers.extend(state.plan_answers)

    chat_messages = dedupe_chat_messages(all_chat_messages)
    user_messages = dedupe_records(all_user_messages)
    plan_answers = dedupe_records(all_plan_answers)
    counter["chat_messages_raw"] = len(all_chat_messages)
    counter["chat_messages_deduped"] = len(chat_messages)
    counter["user_messages_raw"] = len(all_user_messages)
    counter["user_messages_deduped"] = len(user_messages)
    counter["plan_answers_raw"] = len(all_plan_answers)
    counter["plan_answers_deduped"] = len(plan_answers)
    return chat_messages, user_messages, plan_answers, counter


def _open_directory_no_follow(path: Path) -> int:
    """Open an absolute directory path without following symlink components."""

    absolute = _absolute_without_symlink_resolution(path)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    current = os.open(absolute.anchor, flags)
    try:
        for part in absolute.parts[1:]:
            child = os.open(part, flags, dir_fd=current)
            os.close(current)
            current = child
    except BaseException:
        os.close(current)
        raise
    return current


@contextmanager
def atomic_text_writer(path: Path) -> Iterator[TextIO]:
    """Yield a private file and atomically replace ``path`` without symlink writes."""

    parent_fd = _open_directory_no_follow(path.parent)
    temporary_name = f".{path.name}.{secrets.token_hex(8)}.tmp"
    file_fd = -1
    temporary_exists = False
    try:
        file_fd = os.open(
            temporary_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        temporary_exists = True
        handle = os.fdopen(file_fd, "w", encoding="utf-8")
        file_fd = -1
        with handle:
            yield handle
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(
            temporary_name,
            path.name,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
        )
        temporary_exists = False
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        if temporary_exists:
            try:
                os.unlink(temporary_name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        os.close(parent_fd)


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with atomic_text_writer(path) as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def write_text(path: Path, content: str) -> None:
    with atomic_text_writer(path) as handle:
        handle.write(content)


def parse_batch_date(value: str) -> str:
    """Parse one canonical ISO calendar date for an output batch."""

    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "expected an ISO date in YYYY-MM-DD form"
        ) from exc
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError("expected an ISO date in YYYY-MM-DD form")
    return value


def _absolute_without_symlink_resolution(path: Path) -> Path:
    expanded = path.expanduser()
    return expanded if expanded.is_absolute() else Path.cwd() / expanded


def _reject_symlink_components(path: Path) -> None:
    absolute = _absolute_without_symlink_resolution(path)
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if current.is_symlink():
            raise ValueError(f"output path contains a symlink: {current}")


def validate_output_root(path: Path, *, repo_root: Path = REPO_ROOT) -> Path:
    """Resolve a safe output root and require in-repo output to be ignored."""

    _reject_symlink_components(path)
    resolved = _absolute_without_symlink_resolution(path).resolve(strict=False)
    repository = repo_root.resolve()
    try:
        relative = resolved.relative_to(repository)
    except ValueError:
        return resolved
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", "--no-index", "--", relative.as_posix()],
        cwd=repository,
        check=False,
        capture_output=True,
    )
    if ignored.returncode != 0:
        raise ValueError("in-repository transcript output root must be ignored by Git")
    return resolved


def prepare_output_paths(output_root: Path, batch: str) -> dict[str, Path]:
    """Create safe output directories and reject symlinked output files."""

    relative_files = {
        "chat": Path("raw") / batch / "chat_messages.jsonl",
        "user": Path("user") / batch / "user_messages.jsonl",
        "plans": Path("user") / batch / "plan_mode_answers.jsonl",
        "candidates": Path("distilled") / batch / "candidate_decisions.jsonl",
        "reviewed": Path("distilled") / batch / "reviewed_decisions.jsonl",
        "manifest": Path("distilled") / batch / "manifest.json",
    }
    paths = {name: output_root / relative for name, relative in relative_files.items()}
    for path in paths.values():
        resolved = path.resolve(strict=False)
        if output_root != resolved and output_root not in resolved.parents:
            raise ValueError(f"transcript output escapes its root: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        _reject_symlink_components(path)
        if path.exists() and not path.is_file():
            raise ValueError(f"transcript output is not a regular file: {path}")
    return paths


def output_path_label(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def default_roots() -> list[Path]:
    roots = [DEFAULT_CODEX_ROOT]
    if RESTORED_CODEX_ROOT.exists():
        roots.append(RESTORED_CODEX_ROOT)
    return roots


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sessions-root",
        action="append",
        type=Path,
        help="Codex sessions root. May be passed multiple times. Defaults to local Codex roots.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=DEFAULT_PROJECT_ROOT,
        help="Project root used for cwd matching.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=TRANSCRIPT_ROOT,
        help="Output root for raw, user, and distilled transcript JSONL.",
    )
    parser.add_argument(
        "--decisions-file",
        type=Path,
        default=REPO_ROOT
        / ".agents"
        / "memory"
        / "state"
        / "DECISIONS.md",  # Read-only migration evidence.
        help="Legacy decision journal used only as read-only migration evidence.",
    )
    parser.add_argument(
        "--preferences-file",
        type=Path,
        default=REPO_ROOT / ".agents" / "references" / "human_owner_intent.md",
        help="Human-owner preference file used to mark already-reflected preferences.",
    )
    parser.add_argument(
        "--date",
        type=parse_batch_date,
        default=date.today().isoformat(),
        help="Batch date used in output paths.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Explicitly write ignored transcript artifacts after printing counts.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print counts; do not write transcript artifacts.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    roots = [
        root.expanduser().resolve() for root in (args.sessions_root or default_roots())
    ]
    project_root = args.project_root.expanduser().resolve()
    chat_messages, user_messages, plan_answers, counter = gather_records(
        roots, project_root
    )
    distillates = distill_records(user_messages, plan_answers)
    legacy_decision_text = (
        args.decisions_file.read_text(encoding="utf-8")
        if args.decisions_file.exists()
        else ""
    )
    preference_text = (
        args.preferences_file.read_text(encoding="utf-8")
        if args.preferences_file.exists()
        else ""
    )
    reviewed_distillates = review_distillates(
        distillates,
        legacy_decision_text=legacy_decision_text,
        preference_text=preference_text,
    )
    counter["candidate_distillates"] = len(distillates)
    counter["candidate_distillates_promotable"] = sum(
        1 for item in distillates if item.get("status") == "candidate"
    )
    counter.update(
        {
            f"reviewed_{status}": count
            for status, count in Counter(
                str(item.get("review_status") or "unknown")
                for item in reviewed_distillates
            ).items()
        }
    )

    print(
        json.dumps(
            {"roots": [root.as_posix() for root in roots], "counts": counter}, indent=2
        )
    )

    if args.dry_run or not args.write:
        return 0

    batch = str(args.date)
    try:
        output_root = validate_output_root(args.output_root)
        outputs = prepare_output_paths(output_root, batch)
    except (OSError, ValueError) as exc:
        print(f"transcript output rejected: {exc}", file=sys.stderr)
        return 2
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "batch": batch,
        "roots": [root.as_posix() for root in roots],
        "project_root": project_root.as_posix(),
        "counts": dict(counter),
        "outputs": [
            output_path_label(outputs["chat"]),
            output_path_label(outputs["user"]),
            output_path_label(outputs["plans"]),
            output_path_label(outputs["candidates"]),
            output_path_label(outputs["reviewed"]),
        ],
    }
    try:
        write_jsonl(outputs["chat"], chat_messages)
        write_jsonl(outputs["user"], user_messages)
        write_jsonl(outputs["plans"], plan_answers)
        write_jsonl(outputs["candidates"], distillates)
        write_jsonl(outputs["reviewed"], reviewed_distillates)
        write_text(
            outputs["manifest"],
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        )
    except OSError as exc:
        print(f"transcript output rejected: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
