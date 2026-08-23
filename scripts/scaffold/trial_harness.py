#!/usr/bin/env python3
"""Bounded, read-only mechanics shared by scaffold trial runners."""

from __future__ import annotations

import json
import hashlib
import getpass
import math
import os
import platform
import re
import subprocess
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Protocol, cast

ROOT = Path(__file__).resolve().parents[2]
VERIFIER_REPORT_MAX_BYTES = 1_048_576
EVENT_EVIDENCE_MAX_ITEMS = 512
EVENT_EVIDENCE_MAX_FIELD_CHARS = 2_048
EVENT_EVIDENCE_MAX_TOTAL_CHARS = VERIFIER_REPORT_MAX_BYTES // 2
EVENT_EVIDENCE_MAX_RAW_BYTES = 8_388_608
TRIAL_RESPONSE_MAX_CHARS = 16_384
_TRUNCATION_SUFFIX = "...<truncated>"
_EXECUTION_IDENTITY_FIELDS = {
    "command_execution": ("command",),
    "function_call": ("name",),
    "mcp_tool_call": ("server", "tool", "tool_name", "name"),
    "tool_call": ("tool", "tool_name", "name"),
    "web_search": ("query", "path"),
}
_GENERIC_EXECUTION_IDENTITY_FIELDS = (
    "command",
    "server",
    "tool",
    "tool_name",
    "name",
    "query",
    "path",
)
_EVIDENCE_FIELDS = (
    "command",
    "server",
    "tool",
    "tool_name",
    "name",
    "arguments",
    "args",
    "input",
    "query",
    "path",
    "cwd",
    "status",
    "exit_code",
    "error",
)
ADAPTER_METADATA_MAX_KEYS = 32
ADAPTER_METADATA_MAX_DEPTH = 4
ADAPTER_METADATA_MAX_ITEMS = 128
ADAPTER_METADATA_MAX_BYTES = 16_384
_RESERVED_ADAPTER_METADATA_KEYS = {
    "adjudication",
    "artifacts",
    "candidate",
    "checkout_clean_after",
    "checkout_clean_before",
    "elapsed_seconds",
    "event_evidence",
    "prompt_sha256",
    "returncode",
    "reviewer",
    "rubric_commit",
    "runtime",
    "started_unix",
    "tested_commit",
    "timed_out",
    "trial_id",
    "trial_response",
}


def run_git(*args: str, cwd: Path = ROOT) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def read_git_blob(commit: str, path: Path, *, root: Path = ROOT) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path.as_posix()}"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        raise ValueError(f"cannot read {path.as_posix()} at {commit}")
    return result.stdout


def attest_evaluator_fixtures(
    fixture_paths: tuple[Path, ...],
    *,
    tested_commit: str,
    rubric_commit: str,
    root: Path = ROOT,
) -> dict[Path, bytes]:
    fixtures: dict[Path, bytes] = {}
    for path in fixture_paths:
        rubric_bytes = read_git_blob(rubric_commit, path, root=root)
        tested_bytes = read_git_blob(tested_commit, path, root=root)
        if tested_bytes != rubric_bytes:
            raise ValueError(
                f"tested commit {tested_commit} differs from rubric commit "
                f"{rubric_commit} at {path.as_posix()}"
            )
        fixtures[path] = rubric_bytes
    return fixtures


def build_codex_command(
    *,
    checkout: Path,
    output_schema: Path,
    output_report: Path,
    model: str | None,
    effort: str | None,
) -> list[str]:
    command = [
        "codex",
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--json",
        "--output-schema",
        str(output_schema),
        "--output-last-message",
        str(output_report),
        "-C",
        str(checkout),
        "-c",
        'approval_policy="never"',
    ]
    if model:
        command.extend(["--model", model])
    if effort:
        command.extend(["-c", f'model_reasoning_effort="{effort}"'])
    command.append("-")
    return command


@contextmanager
def detached_worktree(
    commit: str, *, root: Path = ROOT, prefix: str = "aria-trial-"
) -> Iterator[Path]:
    """Yield an exact detached checkout and remove it even on failure."""
    with tempfile.TemporaryDirectory(prefix=prefix) as temporary:
        checkout = Path(temporary) / "checkout"
        run_git("worktree", "add", "--detach", str(checkout), commit, cwd=root)
        try:
            yield checkout
        finally:
            run_git("worktree", "remove", "--force", str(checkout), cwd=root)


def _truncate_evidence_field(
    value: Any,
) -> tuple[str | int | float | bool | None, bool]:
    if value is None or isinstance(value, (int, float, bool)):
        return value, False
    text = (
        value
        if isinstance(value, str)
        else json.dumps(value, sort_keys=True, separators=(",", ":"))
    )
    if len(text) <= EVENT_EVIDENCE_MAX_FIELD_CHARS:
        return text, False
    keep = EVENT_EVIDENCE_MAX_FIELD_CHARS - len(_TRUNCATION_SUFFIX)
    return text[:keep] + _TRUNCATION_SUFFIX, True


def _has_observed_identity(item_type: Any, source: dict[str, Any]) -> bool:
    if not isinstance(item_type, str):
        return False
    fields = _EXECUTION_IDENTITY_FIELDS.get(
        item_type, _GENERIC_EXECUTION_IDENTITY_FIELDS
    )
    return any(
        isinstance(value, str) and bool(value.strip())
        for value in (source.get(field) for field in fields)
    )


def _event_evidence_record(event: Any) -> tuple[dict[str, Any] | None, int, bool]:
    if not isinstance(event, dict):
        return None, 0, False
    item = event.get("item")
    source = item if isinstance(item, dict) else event
    item_type = source.get("type")
    if not isinstance(item_type, str):
        return None, 0, False
    present_fields = [field for field in _EVIDENCE_FIELDS if field in source]
    if not _has_observed_identity(item_type, source):
        empty_started_web_search = (
            event.get("type") == "item.started"
            and item_type == "web_search"
            and source.get("query") == ""
            and source.get("action") == {"type": "other"}
        )
        if empty_started_web_search:
            return None, 0, False
        return None, 0, item_type in _EXECUTION_IDENTITY_FIELDS
    if not isinstance(event.get("type"), str):
        return None, 0, False
    record: dict[str, Any] = {}
    record["event_type"], truncated = _truncate_evidence_field(event["type"])
    field_truncations = int(truncated)
    record["item_type"], truncated = _truncate_evidence_field(item_type)
    field_truncations += int(truncated)
    for evidence_field in present_fields:
        record[evidence_field], truncated = _truncate_evidence_field(
            source[evidence_field]
        )
        field_truncations += int(truncated)
    return record, field_truncations, False


def extract_event_evidence(path: Path) -> dict[str, Any]:
    """Extract only bounded execution evidence from Codex JSONL output."""
    items: list[dict[str, Any]] = []
    malformed_lines = invalid_items = dropped_items = field_truncations = 0
    payload_chars = 2
    read_error = False
    try:
        with path.open("rb") as stream:
            raw_bytes = 0
            while True:
                remaining = EVENT_EVIDENCE_MAX_RAW_BYTES - raw_bytes
                raw_line = stream.readline(remaining + 1)
                if not raw_line:
                    break
                if len(raw_line) > remaining:
                    dropped_items += 1
                    break
                raw_bytes += len(raw_line)
                try:
                    line = raw_line.decode("utf-8")
                    if not line.strip():
                        continue
                    event = json.loads(line)
                except (UnicodeError, json.JSONDecodeError):
                    malformed_lines += 1
                    continue
                record, truncated_fields, invalid = _event_evidence_record(event)
                field_truncations += truncated_fields
                invalid_items += int(invalid)
                if record is None:
                    continue
                serialized = json.dumps(record, sort_keys=True, separators=(",", ":"))
                item_chars = len(serialized) + int(bool(items))
                if (
                    len(items) >= EVENT_EVIDENCE_MAX_ITEMS
                    or payload_chars + item_chars > EVENT_EVIDENCE_MAX_TOTAL_CHARS
                ):
                    dropped_items += 1
                    continue
                items.append(record)
                payload_chars += item_chars
    except OSError:
        read_error = True
    while True:
        result = {
            "bounds": {
                "max_items": EVENT_EVIDENCE_MAX_ITEMS,
                "max_field_chars": EVENT_EVIDENCE_MAX_FIELD_CHARS,
                "max_total_chars": EVENT_EVIDENCE_MAX_TOTAL_CHARS,
            },
            "items": items,
            "payload_chars": payload_chars,
            "malformed_lines": malformed_lines,
            "invalid_items": invalid_items,
            "dropped_items": dropped_items,
            "field_truncations": field_truncations,
            "truncated": bool(dropped_items or field_truncations),
            "read_error": read_error,
        }
        if (
            len(json.dumps(result, sort_keys=True, separators=(",", ":")))
            <= EVENT_EVIDENCE_MAX_TOTAL_CHARS
            or not items
        ):
            return result
        items.pop()
        dropped_items += 1
        payload_chars = len(json.dumps(items, sort_keys=True, separators=(",", ":")))


def validate_event_evidence(
    evidence: Any, *, require_execution_evidence: bool = True
) -> tuple[bool, str]:
    required = {
        "bounds",
        "items",
        "payload_chars",
        "malformed_lines",
        "invalid_items",
        "dropped_items",
        "field_truncations",
        "truncated",
        "read_error",
    }
    if not isinstance(evidence, dict) or set(evidence) != required:
        return False, "raw event evidence is absent or malformed"
    bounds = {
        "max_items": EVENT_EVIDENCE_MAX_ITEMS,
        "max_field_chars": EVENT_EVIDENCE_MAX_FIELD_CHARS,
        "max_total_chars": EVENT_EVIDENCE_MAX_TOTAL_CHARS,
    }
    if evidence["bounds"] != bounds:
        return False, "raw event evidence bounds are invalid"
    counters = (
        "payload_chars",
        "malformed_lines",
        "invalid_items",
        "dropped_items",
        "field_truncations",
    )
    if any(
        isinstance(evidence[field], bool)
        or not isinstance(evidence[field], int)
        or evidence[field] < 0
        for field in counters
    ):
        return False, "raw event evidence counters are invalid"
    if not isinstance(evidence["read_error"], bool) or not isinstance(
        evidence["truncated"], bool
    ):
        return False, "raw event evidence flags are invalid"
    items = evidence["items"]
    if not isinstance(items, list):
        return False, "raw event evidence is empty"
    if require_execution_evidence and not items:
        return False, "raw event evidence is empty"
    if len(items) > EVENT_EVIDENCE_MAX_ITEMS:
        return False, "raw event evidence exceeds the item bound"
    allowed = {"event_type", "item_type", *_EVIDENCE_FIELDS}
    for item in items:
        if not isinstance(item, dict) or not {"event_type", "item_type"} <= set(item):
            return False, "raw event evidence item identity is malformed"
        if not set(item) <= allowed:
            return False, "raw event evidence item fields are malformed"
        for value in item.values():
            if not isinstance(value, (str, int, float, bool, type(None))):
                return False, "raw event evidence field type is malformed"
            if isinstance(value, str) and (
                len(value) > EVENT_EVIDENCE_MAX_FIELD_CHARS
                or value.endswith(_TRUNCATION_SUFFIX)
            ):
                return (
                    False,
                    "raw event evidence field exceeds its bound"
                    if len(value) > EVENT_EVIDENCE_MAX_FIELD_CHARS
                    else "raw event evidence contains a truncated field",
                )
        if (
            not isinstance(item["event_type"], str)
            or not item["event_type"]
            or not isinstance(item["item_type"], str)
            or not item["item_type"]
        ):
            return False, "raw event evidence item identity is malformed"
        if not _has_observed_identity(item["item_type"], item):
            return False, "raw event evidence item identity is missing"
    payload = json.dumps(items, sort_keys=True, separators=(",", ":"))
    if evidence["payload_chars"] != len(payload):
        return False, "raw event evidence payload length is inconsistent"
    if (
        len(json.dumps(evidence, sort_keys=True, separators=(",", ":")))
        > EVENT_EVIDENCE_MAX_TOTAL_CHARS
    ):
        return False, "raw event evidence exceeds the total bound"
    if (
        evidence["read_error"]
        or evidence["malformed_lines"]
        or evidence["invalid_items"]
        or evidence["dropped_items"]
        or evidence["field_truncations"]
        or evidence["truncated"]
    ):
        return False, "raw event evidence is incomplete"
    if not items:
        return True, "complete raw event evidence with no execution items"
    return True, "complete raw event evidence"


def bound_trial_response(
    value: Any, *, force_truncated: bool = False
) -> dict[str, Any]:
    if isinstance(value, str):
        text, response_format = value, "text"
    else:
        text, response_format = (
            json.dumps(value, sort_keys=True, separators=(",", ":")),
            "json",
        )
    truncated = force_truncated or len(text) > TRIAL_RESPONSE_MAX_CHARS
    if truncated:
        text = (
            text[: TRIAL_RESPONSE_MAX_CHARS - len(_TRUNCATION_SUFFIX)]
            + _TRUNCATION_SUFFIX
        )
    return {
        "label": "untrusted_trial_response",
        "format": response_format,
        "content": text,
        "max_chars": TRIAL_RESPONSE_MAX_CHARS,
        "truncated": truncated,
    }


def read_trial_response(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            raw = stream.read(TRIAL_RESPONSE_MAX_CHARS + 1)
    except OSError:
        return bound_trial_response({"unavailable": True})
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        return bound_trial_response({"unavailable": True})
    try:
        value: Any = json.loads(text)
    except json.JSONDecodeError:
        value = text
    return bound_trial_response(
        value, force_truncated=len(raw) > TRIAL_RESPONSE_MAX_CHARS
    )


def run_bounded_verifier(
    *,
    command: list[str],
    prompt: str,
    report_path: Path,
    events_path: Path,
    stderr_path: Path,
    timeout_seconds: int,
    validator: Callable[[Any], tuple[bool, str]],
    root: Path = ROOT,
) -> dict[str, Any]:
    """Run a verifier and fail closed on process, encoding, or size errors."""
    timed_out = False
    returncode = 124
    with (
        events_path.open("w", encoding="utf-8") as events,
        stderr_path.open("w", encoding="utf-8") as stderr,
    ):
        try:
            result = subprocess.run(
                command,
                input=prompt,
                cwd=root,
                stdout=events,
                stderr=stderr,
                text=True,
                check=False,
                timeout=timeout_seconds,
                env=os.environ.copy(),
            )
            returncode = result.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
    payload: Any = None
    read_error: str | None = None
    if not timed_out:
        if not report_path.is_file():
            read_error = "verifier report is unreadable or malformed"
        else:
            try:
                with report_path.open("rb") as stream:
                    raw = stream.read(VERIFIER_REPORT_MAX_BYTES + 1)
                if len(raw) > VERIFIER_REPORT_MAX_BYTES:
                    read_error = "verifier report exceeds the byte bound"
                else:
                    payload = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, OSError, UnicodeError):
                read_error = "verifier report is unreadable or malformed"
    if timed_out or returncode != 0:
        valid, reason = False, "verifier timed out or failed"
    elif read_error is not None:
        valid, reason = False, read_error
    else:
        valid, reason = validator(payload)
    return {
        "passed": valid,
        "reason": reason,
        "timed_out": timed_out,
        "returncode": returncode,
        "verdict": payload,
    }


@dataclass(frozen=True)
class TrialCase:
    """One adapter-selected case with opaque adapter-owned context."""

    trial_id: str
    context: object
    candidate: CandidateProvenance | None = None
    adapter_metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class PrincipalIdentity:
    """Canonical typed principal identity used by authors and reviewers."""

    namespace: str
    subject: str

    def canonical(self) -> str:
        namespace = self.namespace.strip()
        subject = self.subject.strip()
        if not namespace or not subject or any(char.isspace() for char in namespace):
            raise ValueError("principal identity is malformed")
        if namespace == "host-user" and "@" not in subject:
            raise ValueError("host-user principal must retain host")
        return f"{namespace}:{subject}"

    def as_report(self) -> dict[str, str]:
        return {
            "canonical": self.canonical(),
            "namespace": self.namespace.strip(),
            "subject": self.subject.strip(),
        }


@dataclass(frozen=True)
class CandidateProvenance:
    """Exact candidate bytes, source locator, and typed author principal."""

    candidate_bytes: bytes
    author: PrincipalIdentity
    expected_sha256: str | None = None
    source_locator: str | None = None


@dataclass(frozen=True)
class ReviewerProvenance:
    """Trusted host-generated reviewer identity stamped by the harness."""

    principal: PrincipalIdentity
    host: str
    started_unix: float

    @property
    def reviewer_id(self) -> str:
        """Compatibility view of the canonical reviewer principal."""
        return self.principal.canonical()


@dataclass(frozen=True)
class SuiteIdentity:
    """Configured suite labels used for errors, worktrees, and reports."""

    name: str
    dirty_root_message: str
    worktree_prefix: str


@dataclass(frozen=True)
class SuiteSpec:
    """Immutable lifecycle inputs shared by bounded trial suites."""

    tested_ref: str
    rubric_ref: str
    identity: SuiteIdentity
    fixture_paths: tuple[Path, ...]
    output_root: Path
    trial_schema: Path
    verifier_schema: Path
    selected_ids: tuple[str, ...] = ()
    all_cases: bool = False
    list_only: bool = False
    model: str | None = None
    effort: str | None = None
    jobs: int = 1
    timeout_seconds: int = 600
    require_execution_evidence: bool = True
    require_candidate_provenance: bool = False
    root: Path = ROOT


@dataclass(frozen=True)
class SuiteResult:
    """Stable suite outcome, reports, and aggregate index."""

    exit_code: int
    reports: tuple[dict[str, Any], ...] = ()
    index: dict[str, Any] | None = None
    listed_ids: tuple[str, ...] = ()
    output_dir: Path | None = None


class SuiteAdapter(Protocol):
    """Routing/scientific policy supplied to :func:`run_suite`."""

    def load_fixtures(self, fixture_bytes: Mapping[Path, bytes]) -> object: ...

    def select_cases(
        self,
        fixtures: object,
        *,
        selected_ids: tuple[str, ...],
        all_cases: bool,
    ) -> tuple[TrialCase, ...]: ...

    def build_trial_prompt(self, case: TrialCase) -> str: ...

    def build_verifier_prompt(
        self, case: TrialCase, report: Mapping[str, Any], rubric_commit: str
    ) -> str: ...

    def validate_verdict(
        self,
        case: TrialCase,
        payload: object,
        report: Mapping[str, Any],
        rubric_commit: str,
    ) -> tuple[bool, str]: ...

    def trial_passed(self, report: Mapping[str, Any]) -> bool: ...


def _codex_version(*, root: Path) -> str:
    return subprocess.run(
        ["codex", "--version"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _runtime_provenance(
    *,
    spec: SuiteSpec,
    codex_version: str,
    command: list[str],
    started: float,
    reviewer: ReviewerProvenance,
) -> dict[str, Any]:
    runtime: dict[str, Any] = {
        "codex_version": codex_version,
        "requested_model": spec.model,
        "requested_effort": spec.effort,
        "command_flags": command[1:-1],
        "reviewer_id": reviewer.reviewer_id,
        "reviewer": reviewer.principal.as_report(),
        "reviewer_host": reviewer.host,
        "reviewer_started_unix": reviewer.started_unix,
    }
    return runtime


def _reviewer_provenance(*, started: float) -> ReviewerProvenance:
    host = platform.node().strip()
    user = getpass.getuser().strip()
    if not user or not host:
        raise ValueError("reviewer identity is malformed")
    return ReviewerProvenance(
        principal=PrincipalIdentity("host-user", f"{user}@{host}"),
        host=host,
        started_unix=started,
    )


def _validate_adapter_metadata(
    metadata: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if metadata is None:
        return None
    if not isinstance(metadata, Mapping):
        raise ValueError("adapter metadata must be a mapping")
    if len(metadata) > ADAPTER_METADATA_MAX_KEYS:
        raise ValueError("adapter metadata has too many keys")

    def visit(value: Any, *, depth: int) -> int:
        if depth > ADAPTER_METADATA_MAX_DEPTH:
            raise ValueError("adapter metadata exceeds depth bound")
        if value is None or isinstance(value, (str, bool, int)):
            return 1
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("adapter metadata contains a non-finite number")
            return 1
        if isinstance(value, dict):
            if len(value) > ADAPTER_METADATA_MAX_ITEMS:
                raise ValueError("adapter metadata has too many items")
            total = len(value)
            for key, child in value.items():
                if not isinstance(key, str) or key in _RESERVED_ADAPTER_METADATA_KEYS:
                    raise ValueError("adapter metadata contains a reserved key")
                total += visit(child, depth=depth + 1)
            return total
        if isinstance(value, list):
            if len(value) > ADAPTER_METADATA_MAX_ITEMS:
                raise ValueError("adapter metadata has too many items")
            return len(value) + sum(visit(child, depth=depth + 1) for child in value)
        raise ValueError("adapter metadata is not JSON-safe")

    visit(dict(metadata), depth=0)
    try:
        serialized = json.dumps(
            metadata, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
    except (TypeError, ValueError) as error:
        raise ValueError("adapter metadata is not JSON-safe") from error
    if len(serialized.encode("utf-8")) > ADAPTER_METADATA_MAX_BYTES:
        raise ValueError("adapter metadata exceeds its byte bound")
    return cast(dict[str, Any], json.loads(serialized))


def _candidate_report(
    candidate: CandidateProvenance | None,
    *,
    reviewer: ReviewerProvenance,
) -> dict[str, Any] | None:
    if candidate is None:
        return None
    author = candidate.author.as_report()
    if author["canonical"] == reviewer.reviewer_id:
        raise ValueError("candidate provenance identity is malformed")
    if (
        not isinstance(candidate.candidate_bytes, bytes)
        or not candidate.candidate_bytes
    ):
        raise ValueError("candidate bytes are empty or malformed")
    if candidate.source_locator is not None and not candidate.source_locator.strip():
        raise ValueError("candidate source locator is malformed")
    if candidate.expected_sha256 is not None and not re.fullmatch(
        r"[0-9a-f]{64}", candidate.expected_sha256
    ):
        raise ValueError("candidate provenance SHA-256 is malformed")
    candidate_sha256 = hashlib.sha256(candidate.candidate_bytes).hexdigest()
    if (
        candidate.expected_sha256 is not None
        and candidate.expected_sha256 != candidate_sha256
    ):
        raise ValueError("candidate provenance SHA-256 does not match exact bytes")
    report = {
        "candidate_sha256": candidate_sha256,
        "author": author,
    }
    if candidate.source_locator is not None:
        report["source_locator"] = candidate.source_locator.strip()
    return report


def _run_case(
    *,
    case: TrialCase,
    adapter: SuiteAdapter,
    spec: SuiteSpec,
    tested_commit: str,
    rubric_commit: str,
    checkout: Path,
    output_dir: Path,
    codex_version: str,
    reviewer: ReviewerProvenance,
) -> dict[str, Any]:
    trial_dir = output_dir / case.trial_id
    trial_dir.mkdir(parents=True, exist_ok=False)
    events_path = trial_dir / "events.jsonl"
    stderr_path = trial_dir / "stderr.txt"
    trial_response_path = trial_dir / "trial-response.json"
    report_path = trial_dir / "report.json"
    prompt = adapter.build_trial_prompt(case)
    command = build_codex_command(
        checkout=checkout,
        output_schema=spec.trial_schema,
        output_report=trial_response_path,
        model=spec.model,
        effort=spec.effort,
    )
    clean_before = run_git("status", "--porcelain", cwd=checkout)
    started = time.time()
    with (
        events_path.open("w", encoding="utf-8") as events,
        stderr_path.open("w", encoding="utf-8") as stderr,
    ):
        try:
            result = subprocess.run(
                command,
                input=prompt,
                cwd=spec.root,
                stdout=events,
                stderr=stderr,
                text=True,
                check=False,
                timeout=spec.timeout_seconds,
                env=os.environ.copy(),
            )
            returncode = result.returncode
            timed_out = False
        except subprocess.TimeoutExpired:
            returncode = 124
            timed_out = True
    clean_after = run_git("status", "--porcelain", cwd=checkout)
    report: dict[str, Any] = {
        "trial_id": case.trial_id,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "tested_commit": tested_commit,
        "rubric_commit": rubric_commit,
        "runtime": _runtime_provenance(
            spec=spec,
            codex_version=codex_version,
            command=command,
            started=started,
            reviewer=reviewer,
        ),
        "reviewer": {
            **reviewer.principal.as_report(),
            "host": reviewer.host,
            "started_unix": reviewer.started_unix,
        },
        "started_unix": started,
        "elapsed_seconds": time.time() - started,
        "returncode": returncode,
        "timed_out": timed_out,
        "checkout_clean_before": clean_before == "",
        "checkout_clean_after": clean_after == "",
        "artifacts": {
            "events": events_path.name,
            "stderr": stderr_path.name,
            "trial_response": trial_response_path.name,
        },
        "event_evidence": extract_event_evidence(events_path),
        "trial_response": read_trial_response(trial_response_path),
    }
    candidate_report = _candidate_report(case.candidate, reviewer=reviewer)
    if candidate_report is not None:
        report["candidate"] = candidate_report
    adapter_metadata = _validate_adapter_metadata(case.adapter_metadata)
    if adapter_metadata is not None:
        report["adapter_metadata"] = adapter_metadata
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def _run_case_verifier(
    *,
    case: TrialCase,
    adapter: SuiteAdapter,
    spec: SuiteSpec,
    rubric_commit: str,
    checkout: Path,
    trial_dir: Path,
    report: dict[str, Any],
) -> dict[str, Any]:
    verifier_report = trial_dir / "verifier-report.json"
    verifier_events = trial_dir / "verifier-events.jsonl"
    verifier_stderr = trial_dir / "verifier-stderr.txt"
    artifacts = {
        "events": verifier_events.name,
        "stderr": verifier_stderr.name,
        "report": verifier_report.name,
    }
    if report.get("rubric_commit") != rubric_commit:
        return {
            "passed": False,
            "reason": "trial report rubric commit mismatch",
            "timed_out": False,
            "returncode": 125,
            "verdict": None,
            "artifacts": artifacts,
        }
    evidence_valid, evidence_reason = validate_event_evidence(
        report.get("event_evidence"),
        require_execution_evidence=spec.require_execution_evidence,
    )
    if not evidence_valid:
        return {
            "passed": False,
            "reason": evidence_reason,
            "timed_out": False,
            "returncode": 125,
            "verdict": None,
            "artifacts": artifacts,
        }
    result = run_bounded_verifier(
        command=build_codex_command(
            checkout=checkout,
            output_schema=spec.verifier_schema,
            output_report=verifier_report,
            model=spec.model,
            effort=spec.effort,
        ),
        prompt=adapter.build_verifier_prompt(case, report, rubric_commit),
        report_path=verifier_report,
        events_path=verifier_events,
        stderr_path=verifier_stderr,
        timeout_seconds=spec.timeout_seconds,
        root=spec.root,
        validator=lambda payload: adapter.validate_verdict(
            case, payload, report, rubric_commit
        ),
    )
    result["artifacts"] = artifacts
    return result


def _mechanically_passed(report: Mapping[str, Any], *, spec: SuiteSpec) -> bool:
    """Apply lifecycle gates that adapters cannot override."""
    adjudication = report.get("adjudication")
    if not isinstance(adjudication, Mapping):
        return False
    evidence_valid, _ = validate_event_evidence(
        report.get("event_evidence"),
        require_execution_evidence=spec.require_execution_evidence,
    )
    return bool(
        report.get("returncode") == 0
        and report.get("timed_out") is False
        and report.get("checkout_clean_before") is True
        and report.get("checkout_clean_after") is True
        and evidence_valid
        and adjudication.get("passed") is True
        and adjudication.get("returncode") == 0
        and adjudication.get("timed_out") is False
    )


def run_suite(spec: SuiteSpec, adapter: SuiteAdapter) -> SuiteResult:
    """Run one exact, bounded suite through an adapter-owned policy seam."""
    tested_commit = run_git("rev-parse", spec.tested_ref, cwd=spec.root)
    rubric_commit = run_git("rev-parse", spec.rubric_ref, cwd=spec.root)
    fixture_bytes = attest_evaluator_fixtures(
        spec.fixture_paths,
        tested_commit=tested_commit,
        rubric_commit=rubric_commit,
        root=spec.root,
    )
    fixtures = adapter.load_fixtures(fixture_bytes)
    cases = adapter.select_cases(
        fixtures, selected_ids=spec.selected_ids, all_cases=spec.all_cases
    )
    listed_ids = tuple(case.trial_id for case in cases)
    if len(listed_ids) != len(set(listed_ids)):
        raise ValueError("trial IDs must be unique")
    if spec.list_only:
        return SuiteResult(exit_code=0, listed_ids=listed_ids)
    if spec.jobs < 1:
        raise ValueError("--jobs must be positive")
    if run_git("status", "--porcelain", cwd=spec.root):
        raise ValueError(spec.identity.dirty_root_message)
    short_head = tested_commit[:12]
    short_rubric = rubric_commit[:12]
    output_dir = spec.output_root / f"{short_head}-{short_rubric}"
    if output_dir.exists():
        raise ValueError(f"trial output already exists: {output_dir}")
    reviewer = _reviewer_provenance(started=time.time())
    for case in cases:
        if spec.require_candidate_provenance and case.candidate is None:
            raise ValueError("candidate provenance is required for every trial")
        _candidate_report(case.candidate, reviewer=reviewer)
        _validate_adapter_metadata(case.adapter_metadata)
    output_dir.mkdir(parents=True)
    codex_version = _codex_version(root=spec.root)
    reports: list[dict[str, Any]] = []
    with detached_worktree(
        tested_commit,
        root=spec.root,
        prefix=f"{spec.identity.worktree_prefix}{short_head}-",
    ) as checkout:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=spec.jobs) as executor:
            case_futures = {
                executor.submit(
                    _run_case,
                    case=case,
                    adapter=adapter,
                    spec=spec,
                    tested_commit=tested_commit,
                    rubric_commit=rubric_commit,
                    checkout=checkout,
                    output_dir=output_dir,
                    codex_version=codex_version,
                    reviewer=reviewer,
                ): case
                for case in cases
            }
            for future in as_completed(case_futures):
                report = future.result()
                reports.append(report)
                print(
                    f"{report['trial_id']}: returncode={report['returncode']} "
                    f"clean={report['checkout_clean_after']}"
                )
        case_by_id = {case.trial_id: case for case in cases}
        with ThreadPoolExecutor(max_workers=spec.jobs) as executor:
            verifier_futures = {
                executor.submit(
                    _run_case_verifier,
                    case=case_by_id[report["trial_id"]],
                    adapter=adapter,
                    spec=spec,
                    rubric_commit=rubric_commit,
                    checkout=checkout,
                    trial_dir=output_dir / report["trial_id"],
                    report=report,
                ): report
                for report in reports
            }
            for future in as_completed(verifier_futures):
                report = verifier_futures[future]
                report["adjudication"] = future.result()
                (output_dir / report["trial_id"] / "report.json").write_text(
                    json.dumps(report, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                print(
                    f"{report['trial_id']}: verdict={report['adjudication']['reason']}"
                )
    index = {
        "tested_commit": tested_commit,
        "rubric_commit": rubric_commit,
        "suite": spec.identity.name,
        "codex_version": codex_version,
        "reviewer_id": reviewer.reviewer_id,
        "reviewer": reviewer.principal.as_report(),
        "trial_ids": list(listed_ids),
        "reports": [
            {
                "trial_id": report["trial_id"],
                "returncode": report["returncode"],
                "timed_out": report["timed_out"],
                "checkout_clean_after": report["checkout_clean_after"],
                "adjudicated": report.get("adjudication", {}).get("passed", False),
                "verdict": report.get("adjudication", {}).get("verdict"),
                "report": f"{report['trial_id']}/report.json",
                **({"candidate": report["candidate"]} if "candidate" in report else {}),
                **(
                    {"adapter_metadata": report["adapter_metadata"]}
                    if "adapter_metadata" in report
                    else {}
                ),
            }
            for report in sorted(reports, key=lambda value: value["trial_id"])
        ],
    }
    (output_dir / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    mechanical_passed = all(
        _mechanically_passed(report, spec=spec) for report in reports
    )
    domain_passed = all(adapter.trial_passed(report) for report in reports)
    return SuiteResult(
        exit_code=0 if mechanical_passed and domain_passed else 1,
        reports=tuple(reports),
        index=index,
        output_dir=output_dir,
    )
