#!/usr/bin/env python3
"""Run bounded, read-only Codex routing trials against an exact Git head."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Event, Lock
from pathlib import Path
from typing import Any, BinaryIO, Callable

ROOT = Path(__file__).resolve().parents[2]
PROMPTS_RELATIVE = Path("scripts/scaffold/fixtures/routing_prompts.jsonl")
RUBRIC_RELATIVE = Path("scripts/scaffold/fixtures/routing.json")
REPORT_SCHEMA_RELATIVE = Path(
    "scripts/scaffold/fixtures/routing_trial_report.schema.json"
)
VERIFIER_SCHEMA_RELATIVE = Path("scripts/scaffold/fixtures/routing_verdict.schema.json")
PROMPTS_PATH = ROOT / PROMPTS_RELATIVE
RUBRIC_PATH = ROOT / RUBRIC_RELATIVE
REPORT_SCHEMA = ROOT / REPORT_SCHEMA_RELATIVE
VERIFIER_SCHEMA = ROOT / VERIFIER_SCHEMA_RELATIVE
EVALUATOR_FIXTURE_PATHS = (PROMPTS_RELATIVE, RUBRIC_RELATIVE)
EVENT_EVIDENCE_MAX_ITEMS = 64
EVENT_EVIDENCE_MAX_FIELD_CHARS = 2_048
EVENT_EVIDENCE_MAX_TOTAL_CHARS = 32_768
# Bound both a single JSONL record and the complete untrusted event stream.
# Codex can emit one large event containing tool output, but evidence extraction
# must not scan an unbounded stream just because every individual line fits.
EVENT_EVIDENCE_MAX_RAW_LINE_BYTES = 2_097_152
EVENT_EVIDENCE_MAX_RAW_STREAM_BYTES = 4_194_304
TRIAL_STDERR_MAX_BYTES = 1_048_576
TRIAL_RESPONSE_MAX_CHARS = 16_384
VERIFIER_REPORT_MAX_BYTES = 1_048_576
VERDICT_MAX_ITEMS = 64
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
DEFAULT_TRIAL_IDS = (
    "context7-graphify-api-change",
    "local-file-lookup",
    "context7-not-needed-target-rri-section",
    "package-contract-owner",
    "semantic-recall-reviewed-history",
    "concrete-failure",
    "durable-workpackage-completion",
    "oracle-evidence-construction",
    "oracle-private-scoring",
    "oracle-scene-rri-scoring",
    "oracle-target-rri-scoring",
    "oracle-label-dtos",
    "oracle-label-pipeline",
    "geometry-pose-generation",
    "geometry-rendering-camera",
    "geometry-vin-frame-contract",
    "zarr-rollout-storage-api",
    "zarr-offline-vin-storage-api",
)

ACADEMIC_AUTHORING_TRIAL_IDS = (
    "academic-writing-related-work-synthesis",
    "academic-writing-handoff-to-typst",
    "typst-authoring-accepted-content-render",
    "scientific-review-empirical-validity",
    "rollout-report-owner-not-writing-skill",
)


def _copy_bounded_stream(
    stream: BinaryIO,
    destination: BinaryIO,
    *,
    maximum_bytes: int,
    overflow: Event,
    on_overflow: Callable[[], None],
    lock: Any,
    written: list[int],
) -> None:
    """Copy one process stream under its byte bound and flag overflow."""
    while chunk := stream.read(64 * 1024):
        with lock:
            remaining = maximum_bytes - written[0]
            if remaining <= 0:
                overflow.set()
                on_overflow()
                return
            destination.write(chunk[:remaining])
            written[0] += min(len(chunk), remaining)
            if len(chunk) > remaining:
                overflow.set()
                on_overflow()
                return


def run_git(*args: str, cwd: Path = ROOT) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _source_bytes(source: bytes | Path) -> bytes:
    return source if isinstance(source, bytes) else source.read_bytes()


def load_prompts(source: bytes | Path = PROMPTS_PATH) -> dict[str, str]:
    prompts: dict[str, str] = {}
    text = _source_bytes(source).decode("utf-8")
    for line_number, line in enumerate(text.splitlines(), start=1):
        record = json.loads(line)
        if not isinstance(record, dict) or set(record) != {"id", "task"}:
            raise ValueError(f"prompt line {line_number}: expected only id and task")
        prompt_id = record["id"]
        task = record["task"]
        if not isinstance(prompt_id, str) or not isinstance(task, str):
            raise ValueError(f"prompt line {line_number}: id and task must be strings")
        if prompt_id in prompts:
            raise ValueError(f"prompt line {line_number}: duplicate id {prompt_id!r}")
        prompts[prompt_id] = task
    return prompts


def load_rubric(source: bytes | Path = RUBRIC_PATH) -> dict[str, dict[str, Any]]:
    data = json.loads(_source_bytes(source).decode("utf-8"))
    fixtures = data.get("fixtures")
    if not isinstance(fixtures, list):
        raise ValueError("rubric fixtures must be a list")
    rubric: dict[str, dict[str, Any]] = {}
    for fixture in fixtures:
        if not isinstance(fixture, dict) or not isinstance(fixture.get("id"), str):
            raise ValueError("every rubric fixture needs a string id")
        trial_id = fixture["id"]
        if trial_id in rubric:
            raise ValueError(f"duplicate rubric fixture id {trial_id!r}")
        rubric[trial_id] = fixture
    return rubric


def select_trial_ids(
    args: argparse.Namespace, prompts: dict[str, str]
) -> tuple[str, ...]:
    """Return one explicit routing suite without silently combining suites."""
    if args.all and args.academic_authoring:
        raise ValueError("--all and --academic-authoring cannot be combined")
    if args.all:
        return tuple(prompts)
    if args.academic_authoring:
        return ACADEMIC_AUTHORING_TRIAL_IDS
    return tuple(args.ids or DEFAULT_TRIAL_IDS)


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
    *, tested_commit: str, rubric_commit: str, root: Path = ROOT
) -> dict[Path, bytes]:
    fixtures: dict[Path, bytes] = {}
    for path in EVALUATOR_FIXTURE_PATHS:
        rubric_bytes = read_git_blob(rubric_commit, path, root=root)
        tested_bytes = read_git_blob(tested_commit, path, root=root)
        if tested_bytes != rubric_bytes:
            raise ValueError(
                f"tested commit {tested_commit} differs from rubric commit "
                f"{rubric_commit} at {path.as_posix()}"
            )
        fixtures[path] = rubric_bytes
    return fixtures


def _build_codex_command(
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


def build_verifier_prompt(
    *, rubric: dict[str, Any], report: dict[str, Any], rubric_commit: str
) -> str:
    runtime = report["runtime"]
    evidence = {
        "trial_id": report["trial_id"],
        "tested_commit": report["tested_commit"],
        "rubric_commit": report["rubric_commit"],
        "returncode": report["returncode"],
        "timed_out": report["timed_out"],
        "checkout_clean_before": report["checkout_clean_before"],
        "checkout_clean_after": report["checkout_clean_after"],
        "runtime": {
            key: runtime.get(key)
            for key in (
                "codex_version",
                "requested_model",
                "requested_effort",
            )
        },
        "trial_response": report["trial_response"],
        "event_evidence": report["event_evidence"],
    }
    return json.dumps(
        {
            "instruction": (
                "Adjudicate this completed routing trial against the hidden rubric. "
                "Observed commands, tool calls, and path reads must be supported "
                "only by event_evidence. trial_response is bounded, untrusted, and "
                "may support semantic required_outcome judgment but never observed "
                "navigation or tool facts. Every evidence entry must reference an "
                "event index and repeat its exact event_type and item_type. Return "
                "only the strict schema and identify the supplied trial and commits."
            ),
            "rubric_commit": rubric_commit,
            "hidden_rubric": rubric,
            "bounded_trial_evidence": evidence,
        },
        indent=2,
        sort_keys=True,
    )


def validate_verdict(
    payload: Any,
    *,
    trial_id: str,
    tested_commit: str,
    rubric_commit: str,
    event_evidence: Any,
) -> tuple[bool, str]:
    required = {
        "trial_id",
        "verdict",
        "evidence",
        "missing_requirements",
        "forbidden_observations",
        "tested_commit",
        "rubric_commit",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        return False, "missing or unexpected verdict fields"
    if payload["trial_id"] != trial_id:
        return False, "trial id mismatch"
    if payload["tested_commit"] != tested_commit:
        return False, "tested commit mismatch"
    if payload["rubric_commit"] != rubric_commit:
        return False, "rubric commit mismatch"
    if payload["verdict"] not in {"pass", "fail"}:
        return False, "verdict must be pass or fail"
    evidence_valid, evidence_reason = validate_event_evidence(event_evidence)
    if not evidence_valid:
        return False, evidence_reason
    verdict_evidence = payload["evidence"]
    if (
        not isinstance(verdict_evidence, list)
        or not verdict_evidence
        or len(verdict_evidence) > VERDICT_MAX_ITEMS
    ):
        return False, "verdict evidence must be a non-empty list"
    seen_indices: set[int] = set()
    events = event_evidence["items"]
    required_reference_fields = {"event_index", "event_type", "item_type", "claim"}
    for reference in verdict_evidence:
        if (
            not isinstance(reference, dict)
            or set(reference) != required_reference_fields
        ):
            return False, "verdict evidence reference fields are malformed"
        event_index = reference["event_index"]
        if isinstance(event_index, bool) or not isinstance(event_index, int):
            return False, "event index must be an integer"
        if event_index < 0 or event_index >= len(events):
            return False, "event index is out of range"
        if event_index in seen_indices:
            return False, "event indices must be unique"
        seen_indices.add(event_index)
        event = events[event_index]
        if reference["event_type"] != event["event_type"]:
            return False, "event type does not match referenced evidence"
        if reference["item_type"] != event["item_type"]:
            return False, "item type does not match referenced evidence"
        if (
            not isinstance(reference["claim"], str)
            or not reference["claim"]
            or len(reference["claim"]) > EVENT_EVIDENCE_MAX_FIELD_CHARS
        ):
            return False, "evidence claim must be a non-empty string"
    for field in ("missing_requirements", "forbidden_observations"):
        values = payload[field]
        if (
            not isinstance(values, list)
            or len(values) > VERDICT_MAX_ITEMS
            or not all(
                isinstance(item, str) and len(item) <= EVENT_EVIDENCE_MAX_FIELD_CHARS
                for item in values
            )
        ):
            return False, f"{field} must be a list of strings"
    if payload["verdict"] == "pass" and (
        payload["missing_requirements"] or payload["forbidden_observations"]
    ):
        return False, "pass verdict contains failures"
    return True, "pass" if payload["verdict"] == "pass" else "semantic fail"


def run_verifier(
    *,
    report: dict[str, Any],
    rubric: dict[str, Any],
    rubric_commit: str,
    checkout: Path,
    trial_dir: Path,
    model: str | None,
    effort: str | None,
    timeout_seconds: int,
) -> dict[str, Any]:
    verifier_report = trial_dir / "verifier-report.json"
    verifier_events = trial_dir / "verifier-events.jsonl"
    verifier_stderr = trial_dir / "verifier-stderr.txt"
    artifacts = {
        "events": verifier_events.name,
        "stderr": verifier_stderr.name,
        "report": verifier_report.name,
    }
    failure_reason: str | None = None
    if report.get("rubric_commit") != rubric_commit:
        failure_reason = "trial report rubric commit mismatch"
    else:
        evidence_valid, evidence_reason = validate_event_evidence(
            report.get("event_evidence")
        )
        if not evidence_valid:
            failure_reason = evidence_reason
    if failure_reason is not None:
        return {
            "passed": False,
            "reason": failure_reason,
            "timed_out": False,
            "returncode": 125,
            "verdict": None,
            "artifacts": artifacts,
        }
    command = _build_codex_command(
        checkout=checkout,
        output_schema=VERIFIER_SCHEMA,
        output_report=verifier_report,
        model=model,
        effort=effort,
    )
    timed_out = False
    returncode = 124
    with (
        verifier_events.open("w", encoding="utf-8") as events,
        verifier_stderr.open("w", encoding="utf-8") as stderr,
    ):
        try:
            result = subprocess.run(
                command,
                input=build_verifier_prompt(
                    rubric=rubric[report["trial_id"]],
                    report=report,
                    rubric_commit=rubric_commit,
                ),
                cwd=ROOT,
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
    verdict_read_error: str | None = None
    if not timed_out and verifier_report.is_file():
        try:
            with verifier_report.open("rb") as stream:
                raw_verdict = stream.read(VERIFIER_REPORT_MAX_BYTES + 1)
            if len(raw_verdict) > VERIFIER_REPORT_MAX_BYTES:
                verdict_read_error = "verifier report exceeds the byte bound"
            else:
                payload = json.loads(raw_verdict.decode("utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeError):
            verdict_read_error = "verifier report is unreadable or malformed"
    if returncode != 0 or timed_out:
        valid, reason = False, "verifier timed out or failed"
    elif verdict_read_error is not None:
        valid, reason = False, verdict_read_error
    else:
        valid, reason = validate_verdict(
            payload,
            trial_id=report["trial_id"],
            tested_commit=report["tested_commit"],
            rubric_commit=rubric_commit,
            event_evidence=report.get("event_evidence"),
        )
    if valid and payload["verdict"] != "pass":
        valid = False
    return {
        "passed": valid,
        "reason": reason,
        "timed_out": timed_out,
        "returncode": returncode,
        "verdict": payload,
        "artifacts": artifacts,
    }


def trial_passed(report: dict[str, Any]) -> bool:
    """Return whether one trial satisfies process, cleanliness, and adjudication."""
    evidence_valid, _ = validate_event_evidence(report.get("event_evidence"))
    return bool(
        report.get("returncode") == 0
        and report.get("checkout_clean_after")
        and not report.get("output_overflow", False)
        and evidence_valid
        and report.get("adjudication", {}).get("passed", False)
    )


def _truncate_evidence_field(
    value: Any,
) -> tuple[str | int | float | bool | None, bool]:
    if value is None or isinstance(value, (int, float, bool)):
        return value, False
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, sort_keys=True, separators=(",", ":"))
    if len(text) <= EVENT_EVIDENCE_MAX_FIELD_CHARS:
        return text, False
    keep = EVENT_EVIDENCE_MAX_FIELD_CHARS - len(_TRUNCATION_SUFFIX)
    return text[:keep] + _TRUNCATION_SUFFIX, True


def _has_observed_identity(item_type: Any, source: dict[str, Any]) -> bool:
    if not isinstance(item_type, str):
        return False
    identity_fields = _EXECUTION_IDENTITY_FIELDS.get(
        item_type, _GENERIC_EXECUTION_IDENTITY_FIELDS
    )
    return any(
        isinstance(value, str) and bool(value.strip())
        for value in (source.get(field) for field in identity_fields)
    )


def _event_evidence_record(
    event: Any,
) -> tuple[dict[str, Any] | None, int, bool]:
    if not isinstance(event, dict):
        return None, 0, False
    item = event.get("item")
    source = item if isinstance(item, dict) else event
    item_type = source.get("type")
    if not isinstance(item_type, str):
        return None, 0, False
    present_fields = [field for field in _EVIDENCE_FIELDS if field in source]
    if not _has_observed_identity(item_type, source):
        return None, 0, item_type in _EXECUTION_IDENTITY_FIELDS

    record: dict[str, Any] = {}
    if isinstance(event.get("type"), str):
        record["event_type"], truncated = _truncate_evidence_field(event["type"])
        field_truncations = int(truncated)
    else:
        return None, 0, False
    if isinstance(item_type, str):
        record["item_type"], truncated = _truncate_evidence_field(item_type)
        field_truncations += int(truncated)
    else:
        return None, 0, False
    for field in present_fields:
        bounded, truncated = _truncate_evidence_field(source[field])
        record[field] = bounded
        field_truncations += int(truncated)
    return record, field_truncations, False


def extract_event_evidence(path: Path) -> dict[str, Any]:
    """Extract deterministic execution evidence from a bounded raw stream."""
    items: list[dict[str, Any]] = []
    malformed_lines = 0
    invalid_items = 0
    dropped_items = 0
    field_truncations = 0
    payload_chars = 2  # JSON list brackets.
    read_error = False
    try:
        with path.open("rb") as stream:
            raw_bytes = 0
            while True:
                remaining = EVENT_EVIDENCE_MAX_RAW_STREAM_BYTES - raw_bytes
                if remaining <= 0:
                    if stream.read(1):
                        dropped_items += 1
                    break
                raw_line = stream.readline(
                    min(remaining, EVENT_EVIDENCE_MAX_RAW_LINE_BYTES) + 1
                )
                if not raw_line:
                    break
                if (
                    len(raw_line) > EVENT_EVIDENCE_MAX_RAW_LINE_BYTES
                    or len(raw_line) > remaining
                ):
                    dropped_items += 1
                    break
                raw_bytes += len(raw_line)
                try:
                    line = raw_line.decode("utf-8")
                except UnicodeError:
                    read_error = True
                    break
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
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
        indexed_items = [
            {**item, "event_index": index} for index, item in enumerate(items)
        ]
        indexed_payload = json.dumps(
            indexed_items, sort_keys=True, separators=(",", ":")
        )
        result = {
            "bounds": {
                "max_items": EVENT_EVIDENCE_MAX_ITEMS,
                "max_field_chars": EVENT_EVIDENCE_MAX_FIELD_CHARS,
                "max_total_chars": EVENT_EVIDENCE_MAX_TOTAL_CHARS,
            },
            "items": indexed_items,
            "payload_chars": len(indexed_payload),
            "malformed_lines": malformed_lines,
            "invalid_items": invalid_items,
            "dropped_items": dropped_items,
            "field_truncations": field_truncations,
            "truncated": bool(dropped_items or field_truncations),
            "read_error": read_error,
        }
        serialized_result = json.dumps(result, sort_keys=True, separators=(",", ":"))
        if len(serialized_result) <= EVENT_EVIDENCE_MAX_TOTAL_CHARS or not items:
            return result
        items.pop()
        dropped_items += 1
        payload_chars = len(json.dumps(items, sort_keys=True, separators=(",", ":")))


def validate_event_evidence(evidence: Any) -> tuple[bool, str]:
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
    expected_bounds = {
        "max_items": EVENT_EVIDENCE_MAX_ITEMS,
        "max_field_chars": EVENT_EVIDENCE_MAX_FIELD_CHARS,
        "max_total_chars": EVENT_EVIDENCE_MAX_TOTAL_CHARS,
    }
    if evidence["bounds"] != expected_bounds:
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
    if not isinstance(items, list) or not items:
        return False, "raw event evidence is empty"
    if len(items) > EVENT_EVIDENCE_MAX_ITEMS:
        return False, "raw event evidence exceeds the item bound"
    allowed_item_fields = {"event_index", "event_type", "item_type", *_EVIDENCE_FIELDS}
    for event_index, item in enumerate(items):
        if not isinstance(item, dict) or not {"event_type", "item_type"} <= set(item):
            return False, "raw event evidence item identity is malformed"
        if not set(item) <= allowed_item_fields:
            return False, "raw event evidence item fields are malformed"
        if item.get("event_index") != event_index:
            return False, "raw event evidence item index is malformed"
        for value in item.values():
            if not isinstance(value, (str, int, float, bool, type(None))):
                return False, "raw event evidence field type is malformed"
            if isinstance(value, str) and len(value) > EVENT_EVIDENCE_MAX_FIELD_CHARS:
                return False, "raw event evidence field exceeds its bound"
            if isinstance(value, str) and value.endswith(_TRUNCATION_SUFFIX):
                return False, "raw event evidence contains a truncated field"
        if not isinstance(item["event_type"], str) or not item["event_type"]:
            return False, "raw event evidence event type is malformed"
        if not isinstance(item["item_type"], str) or not item["item_type"]:
            return False, "raw event evidence item type is malformed"
        if not _has_observed_identity(item["item_type"], item):
            return False, "raw event evidence item identity is missing"
    payload = json.dumps(items, sort_keys=True, separators=(",", ":"))
    if evidence["payload_chars"] != len(payload):
        return False, "raw event evidence payload length is inconsistent"
    serialized = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
    if len(serialized) > EVENT_EVIDENCE_MAX_TOTAL_CHARS:
        return False, "raw event evidence exceeds the total bound"
    incomplete = (
        evidence["read_error"]
        or evidence["malformed_lines"]
        or evidence["invalid_items"]
        or evidence["dropped_items"]
        or evidence["field_truncations"]
        or evidence["truncated"]
    )
    if incomplete:
        return False, "raw event evidence is incomplete"
    return True, "complete raw event evidence"


def bound_trial_response(
    value: Any, *, force_truncated: bool = False
) -> dict[str, Any]:
    if isinstance(value, str):
        text = value
        response_format = "text"
    else:
        text = json.dumps(value, sort_keys=True, separators=(",", ":"))
        response_format = "json"
    truncated = force_truncated or len(text) > TRIAL_RESPONSE_MAX_CHARS
    if truncated:
        keep = TRIAL_RESPONSE_MAX_CHARS - len(_TRUNCATION_SUFFIX)
        text = text[:keep] + _TRUNCATION_SUFFIX
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
    force_truncated = len(raw) > TRIAL_RESPONSE_MAX_CHARS
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        return bound_trial_response({"unavailable": True})
    try:
        value: Any = json.loads(text)
    except json.JSONDecodeError:
        value = text
    return bound_trial_response(value, force_truncated=force_truncated)


def run_trial(
    *,
    trial_id: str,
    task: str,
    head: str,
    rubric_commit: str,
    checkout: Path,
    output_dir: Path,
    codex_version: str,
    model: str | None,
    effort: str | None,
    timeout_seconds: int,
) -> dict[str, Any]:
    trial_dir = output_dir / trial_id
    trial_dir.mkdir(parents=True, exist_ok=False)
    events_path = trial_dir / "events.jsonl"
    stderr_path = trial_dir / "stderr.txt"
    trial_response_path = trial_dir / "trial-response.json"
    final_report = trial_dir / "report.json"
    command = _build_codex_command(
        checkout=checkout,
        output_schema=REPORT_SCHEMA,
        output_report=trial_response_path,
        model=model,
        effort=effort,
    )
    clean_before = run_git("status", "--porcelain", cwd=checkout)
    started = time.time()
    output_overflow = Event()
    output_lock = Lock()
    event_bytes = [0]
    stderr_bytes = [0]
    with (
        events_path.open("wb") as events,
        stderr_path.open("wb") as stderr,
    ):
        try:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ.copy(),
            )
            assert process.stdin is not None
            assert process.stdout is not None
            assert process.stderr is not None
            process.stdin.write(task.encode("utf-8"))
            process.stdin.close()
            with ThreadPoolExecutor(max_workers=2) as executor:
                copies = (
                    executor.submit(
                        _copy_bounded_stream,
                        process.stdout,
                        events,
                        maximum_bytes=EVENT_EVIDENCE_MAX_RAW_STREAM_BYTES,
                        overflow=output_overflow,
                        on_overflow=process.terminate,
                        lock=output_lock,
                        written=event_bytes,
                    ),
                    executor.submit(
                        _copy_bounded_stream,
                        process.stderr,
                        stderr,
                        maximum_bytes=TRIAL_STDERR_MAX_BYTES,
                        overflow=output_overflow,
                        on_overflow=process.terminate,
                        lock=output_lock,
                        written=stderr_bytes,
                    ),
                )
                try:
                    returncode = process.wait(timeout=timeout_seconds)
                    timed_out = False
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait()
                    returncode = 124
                    timed_out = True
                if output_overflow.is_set() and process.poll() is None:
                    process.terminate()
                    process.wait()
                    returncode = 125
                for copy in copies:
                    copy.result()
        except subprocess.TimeoutExpired:
            returncode = 124
            timed_out = True
    clean_after = run_git("status", "--porcelain", cwd=checkout)
    runtime = {
        "codex_version": codex_version,
        "requested_model": model,
        "requested_effort": effort,
        "command_flags": command[1:-1],
    }
    report = {
        "trial_id": trial_id,
        "prompt_sha256": hashlib.sha256(task.encode()).hexdigest(),
        "tested_commit": head,
        "rubric_commit": rubric_commit,
        "runtime": runtime,
        "event_evidence": extract_event_evidence(events_path),
        "started_unix": started,
        "elapsed_seconds": time.time() - started,
        "returncode": returncode,
        "timed_out": timed_out,
        "output_overflow": output_overflow.is_set(),
        "checkout_clean_before": clean_before == "",
        "checkout_clean_after": clean_after == "",
        "artifacts": {
            "events": events_path.name,
            "stderr": stderr_path.name,
            "trial_response": trial_response_path.name,
        },
        "trial_response": read_trial_response(trial_response_path),
    }
    final_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--head", default="HEAD", help="Exact commit-ish to test.")
    parser.add_argument(
        "--id", action="append", dest="ids", help="Trial ID; repeat to select several."
    )
    parser.add_argument("--all", action="store_true", help="Run every frozen prompt.")
    parser.add_argument(
        "--academic-authoring",
        action="store_true",
        help="Run the focused academic-authoring routing suite.",
    )
    parser.add_argument("--list", action="store_true", help="List default trial IDs.")
    parser.add_argument(
        "--model", help="Explicit Codex model; otherwise inherit config."
    )
    parser.add_argument(
        "--effort", help="Explicit reasoning effort; otherwise inherit config."
    )
    parser.add_argument(
        "--jobs", type=int, default=1, help="Concurrent read-only trials."
    )
    parser.add_argument("--timeout", type=int, default=600, help="Seconds per trial.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tested_commit = run_git("rev-parse", args.head)
    rubric_commit = run_git("rev-parse", "HEAD")
    try:
        fixture_bytes = attest_evaluator_fixtures(
            tested_commit=tested_commit,
            rubric_commit=rubric_commit,
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error
    prompts = load_prompts(fixture_bytes[PROMPTS_RELATIVE])
    rubric = load_rubric(fixture_bytes[RUBRIC_RELATIVE])
    if set(prompts) != set(rubric):
        raise SystemExit("routing prompt and rubric ID sets differ")
    try:
        selected = select_trial_ids(args, prompts)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    unknown = sorted(set(selected) - set(prompts))
    if unknown:
        raise SystemExit(f"unknown trial IDs: {unknown}")
    if args.list:
        print("\n".join(selected))
        return 0
    if args.jobs < 1:
        raise SystemExit("--jobs must be positive")
    if run_git("status", "--porcelain"):
        raise SystemExit("commit the candidate before routing trials")

    short_head = tested_commit[:12]
    short_rubric = rubric_commit[:12]
    output_dir = (
        ROOT / ".agents" / "work" / "routing-trials" / f"{short_head}-{short_rubric}"
    )
    if output_dir.exists():
        raise SystemExit(f"trial output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    codex_version = subprocess.run(
        ["codex", "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    with tempfile.TemporaryDirectory(prefix=f"aria-routing-{short_head}-") as temp:
        checkout = Path(temp) / "checkout"
        run_git("worktree", "add", "--detach", str(checkout), tested_commit)
        try:
            reports: list[dict[str, Any]] = []
            with ThreadPoolExecutor(max_workers=args.jobs) as executor:
                futures = {
                    executor.submit(
                        run_trial,
                        trial_id=trial_id,
                        task=prompts[trial_id],
                        head=tested_commit,
                        rubric_commit=rubric_commit,
                        checkout=checkout,
                        output_dir=output_dir,
                        codex_version=codex_version,
                        model=args.model,
                        effort=args.effort,
                        timeout_seconds=args.timeout,
                    ): trial_id
                    for trial_id in selected
                }
                for future in as_completed(futures):
                    trial_id = futures[future]
                    report = future.result()
                    reports.append(report)
                    print(
                        f"{trial_id}: returncode={report['returncode']} "
                        f"clean={report['checkout_clean_after']}"
                    )
            for report in reports:
                adjudication = run_verifier(
                    report=report,
                    rubric=rubric,
                    rubric_commit=rubric_commit,
                    checkout=checkout,
                    trial_dir=output_dir / report["trial_id"],
                    model=args.model,
                    effort=args.effort,
                    timeout_seconds=args.timeout,
                )
                report["adjudication"] = adjudication
                (output_dir / report["trial_id"] / "report.json").write_text(
                    json.dumps(report, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                print(f"{report['trial_id']}: verdict={adjudication['reason']}")
        finally:
            run_git("worktree", "remove", "--force", str(checkout))

    index = {
        "tested_commit": tested_commit,
        "rubric_commit": rubric_commit,
        "codex_version": codex_version,
        "trial_ids": list(selected),
        "reports": [
            {
                "trial_id": report["trial_id"],
                "returncode": report["returncode"],
                "timed_out": report["timed_out"],
                "checkout_clean_after": report["checkout_clean_after"],
                "adjudicated": report.get("adjudication", {}).get("passed", False),
                "verdict": report.get("adjudication", {}).get("verdict"),
                "report": f"{report['trial_id']}/report.json",
            }
            for report in sorted(reports, key=lambda value: value["trial_id"])
        ],
    }
    (output_dir / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if all(trial_passed(report) for report in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
