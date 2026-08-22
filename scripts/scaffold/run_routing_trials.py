#!/usr/bin/env python3
"""Run bounded, read-only Codex routing trials against an exact Git head."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

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
# Normal Codex trials currently produce roughly 1.2 MiB and 252 final execution
# records. These caps retain more than 2x item headroom while keeping normalized
# evidence to half of the verifier's 1 MiB bounded JSON budget.
VERIFIER_REPORT_MAX_BYTES = 1_048_576
EVENT_EVIDENCE_MAX_ITEMS = 512
EVENT_EVIDENCE_MAX_FIELD_CHARS = 2_048
EVENT_EVIDENCE_MAX_TOTAL_CHARS = VERIFIER_REPORT_MAX_BYTES // 2
EVENT_EVIDENCE_MAX_RAW_BYTES = 8_388_608
TRIAL_RESPONSE_MAX_CHARS = 16_384
VERDICT_MAX_ITEMS = 64
_TRUNCATION_SUFFIX = "...<truncated>"
RUBRIC_CONSTRAINT_FIELDS = (
    ("expected_owner_paths", "expected_owner_path"),
    ("stable_skill_ids", "stable_skill_id"),
    ("expected_tool_refs", "expected_tool_ref"),
    ("forbidden_tool_refs", "forbidden_tool_ref"),
    ("required_outcomes", "required_outcome"),
    ("forbidden_outcomes", "forbidden_outcome"),
)
POSITIVE_CONSTRAINT_KINDS = {
    "expected_owner_path",
    "stable_skill_id",
    "expected_tool_ref",
    "required_outcome",
}
NEGATIVE_CONSTRAINT_KINDS = {"forbidden_tool_ref", "forbidden_outcome"}
EVENT_ONLY_CONSTRAINT_KINDS = {
    "expected_owner_path",
    "expected_tool_ref",
    "forbidden_tool_ref",
}
NON_APPLICABLE_PATH_PREFIX = "non-applicable path is loaded: "
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
THESIS_AUTHORING_TRIAL_IDS = (
    "academic-writing-related-work-synthesis",
    "typst-authoring-accepted-content-render",
    "scientific-review-empirical-validity",
    "rollout-report-owner-not-writing-skill",
)


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
                "may support stable skill identity and genuinely semantic outcome "
                "judgments but never path, tool, or navigation facts. Return exactly "
                "one rubric_evaluations entry for every exact constraint in "
                "expected_owner_paths, stable_skill_ids, expected_tool_refs, "
                "forbidden_tool_refs, required_outcomes, and forbidden_outcomes. "
                "Preserve each exact subject and use its singular kind. Positive "
                "statuses are satisfied/not_satisfied; forbidden statuses are "
                "not_observed/observed. Owner paths and tool refs require "
                "event_evidence. Canonical 'non-applicable path is loaded: <path>' "
                "outcomes also require event_evidence. Observed path and tool "
                "constraints cite representative relevant bounded event indices; "
                "path citations include a successful proof and tool citations match "
                "the tool reference. Path/tool absences use empty indices because "
                "the validator proves absence from complete event evidence. Stable "
                "skill IDs and semantic outcomes may use the "
                "bounded trial_response with empty indices. Every evidence entry must reference an "
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


def _validate_trial_response(value: Any) -> tuple[bool, str]:
    required = {"label", "format", "content", "max_chars", "truncated"}
    if not isinstance(value, dict) or set(value) != required:
        return False, "trial response is absent or malformed"
    if value["label"] != "untrusted_trial_response":
        return False, "trial response label is invalid"
    if value["format"] not in {"text", "json"}:
        return False, "trial response format is invalid"
    if value["max_chars"] != TRIAL_RESPONSE_MAX_CHARS:
        return False, "trial response bound is invalid"
    if (
        not isinstance(value["content"], str)
        or len(value["content"]) > TRIAL_RESPONSE_MAX_CHARS
        or not isinstance(value["truncated"], bool)
    ):
        return False, "trial response content is invalid"
    return True, "bounded trial response"


def _rubric_constraints(
    rubric: Any,
) -> tuple[list[tuple[str, str]], str | None]:
    if not isinstance(rubric, dict):
        return [], "rubric is malformed"
    constraints: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    required_fields = {"expected_owner_paths", "required_outcomes", "forbidden_outcomes"}
    for field, kind in RUBRIC_CONSTRAINT_FIELDS:
        values = rubric.get(field, [] if field not in required_fields else None)
        if not isinstance(values, list) or not all(
            isinstance(subject, str)
            and bool(subject)
            and len(subject) <= EVENT_EVIDENCE_MAX_FIELD_CHARS
            for subject in values
        ):
            return [], f"rubric {field} is malformed"
        for subject in values:
            identity = (kind, subject)
            if identity in seen:
                return [], "rubric constraints must be unique"
            seen.add(identity)
            constraints.append(identity)
    if len(constraints) > VERDICT_MAX_ITEMS:
        return [], "rubric has too many constraints"
    return constraints, None


def _event_strings(event: dict[str, Any]) -> tuple[str, ...]:
    return tuple(value for value in event.values() if isinstance(value, str))


def _event_tool_refs(event: dict[str, Any]) -> set[str]:
    refs = {
        value
        for field in ("tool", "tool_name", "name")
        if isinstance((value := event.get(field)), str)
    }
    server = event.get("server")
    tool = event.get("tool") or event.get("tool_name") or event.get("name")
    if isinstance(server, str) and isinstance(tool, str):
        refs.add(f"mcp__{server}__{tool}")
        refs.add(f"mcp__{server}.{tool}")
    return refs


def _contains_stable_id(text: str, subject: str) -> bool:
    pattern = rf"(?<![A-Za-z0-9_-]){re.escape(subject)}(?![A-Za-z0-9_-])"
    return re.search(pattern, text) is not None


def _is_exact_path_mention(event: dict[str, Any], subject: str) -> bool:
    if event.get("path") == subject:
        return True
    command = event.get("command")
    if not isinstance(command, str):
        return False
    try:
        outer_tokens = shlex.split(command)
    except ValueError:
        return False
    if subject in outer_tokens:
        return True
    shell = outer_tokens[0].rsplit("/", 1)[-1] if outer_tokens else ""
    if shell not in {"bash", "zsh"}:
        return False
    try:
        option_index = outer_tokens.index("-lc")
        nested_command = outer_tokens[option_index + 1]
    except (ValueError, IndexError):
        return False
    try:
        return subject in shlex.split(nested_command)
    except ValueError:
        return False


def _is_successful_path_observation(event: dict[str, Any], subject: str) -> bool:
    if event.get("status") != "completed":
        return False
    exit_code = event.get("exit_code")
    if exit_code is not None and (
        isinstance(exit_code, bool) or not isinstance(exit_code, int) or exit_code != 0
    ):
        return False
    return _is_exact_path_mention(event, subject)


def _matching_path_mention_indices(
    events: list[dict[str, Any]], subject: str
) -> list[int]:
    return [
        index
        for index, event in enumerate(events)
        if _is_exact_path_mention(event, subject)
    ]


def _matching_event_indices(
    events: list[dict[str, Any]], *, kind: str, subject: str
) -> list[int]:
    matches: list[int] = []
    for index, event in enumerate(events):
        if kind in {"expected_owner_path", "forbidden_path"}:
            matched = _is_successful_path_observation(event, subject)
        elif kind in {"expected_tool_ref", "forbidden_tool_ref"}:
            matched = subject in _event_tool_refs(event)
        elif kind == "stable_skill_id":
            matched = any(
                _contains_stable_id(value, subject) for value in _event_strings(event)
            )
        else:
            matched = any(subject in value for value in _event_strings(event))
        if matched:
            matches.append(index)
    return matches


def validate_verdict(
    payload: Any,
    *,
    trial_id: str,
    tested_commit: str,
    rubric_commit: str,
    rubric: dict[str, Any],
    event_evidence: Any,
    trial_response: Any,
) -> tuple[bool, str]:
    required = {
        "trial_id",
        "verdict",
        "evidence",
        "rubric_evaluations",
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
    response_valid, response_reason = _validate_trial_response(trial_response)
    if not response_valid:
        return False, response_reason
    constraints, constraint_error = _rubric_constraints(rubric)
    if constraint_error is not None:
        return False, constraint_error
    rubric_evaluations = payload["rubric_evaluations"]
    if not isinstance(rubric_evaluations, list) or len(rubric_evaluations) != len(
        constraints
    ):
        return False, "rubric evaluations must match the rubric exactly"
    seen_evaluations: set[tuple[str, str]] = set()
    expected_constraint_set = set(constraints)
    events = event_evidence["items"]
    allowed_statuses = {
        **{
            kind: {"satisfied", "not_satisfied"}
            for kind in POSITIVE_CONSTRAINT_KINDS
        },
        **{kind: {"not_observed", "observed"} for kind in NEGATIVE_CONSTRAINT_KINDS},
    }
    for evaluation in rubric_evaluations:
        required_evaluation_fields = {
            "kind",
            "subject",
            "status",
            "basis",
            "evidence_event_indices",
        }
        if not isinstance(evaluation, dict) or set(evaluation) != required_evaluation_fields:
            return False, "rubric evaluation fields are malformed"
        kind = evaluation["kind"]
        subject = evaluation["subject"]
        if not isinstance(kind, str) or kind not in allowed_statuses:
            return False, "rubric evaluation kind is invalid"
        if (
            not isinstance(subject, str)
            or not subject
            or len(subject) > EVENT_EVIDENCE_MAX_FIELD_CHARS
        ):
            return False, "rubric evaluation subject is invalid"
        identity = (kind, subject)
        if identity not in expected_constraint_set:
            return False, "rubric evaluation is not in the rubric"
        if identity in seen_evaluations:
            return False, "rubric evaluations must be unique"
        seen_evaluations.add(identity)
        status = evaluation["status"]
        if not isinstance(status, str) or status not in allowed_statuses[kind]:
            return False, "rubric evaluation status is invalid for its kind"
        basis = evaluation["basis"]
        if not isinstance(basis, str) or basis not in {
            "event_evidence",
            "trial_response",
        }:
            return False, "rubric evaluation basis is invalid"
        indices = evaluation["evidence_event_indices"]
        if (
            not isinstance(indices, list)
            or len(indices) > VERDICT_MAX_ITEMS
            or any(isinstance(index, bool) or not isinstance(index, int) for index in indices)
            or len(set(indices)) != len(indices)
            or any(index < 0 or index >= len(events) for index in indices)
        ):
            return False, "rubric evaluation evidence indices are invalid"

        canonical_forbidden_path = (
            subject.removeprefix(NON_APPLICABLE_PATH_PREFIX)
            if kind == "forbidden_outcome"
            and subject.startswith(NON_APPLICABLE_PATH_PREFIX)
            else None
        )
        deterministic_kind = kind
        deterministic_subject = subject
        if canonical_forbidden_path is not None:
            deterministic_kind = "forbidden_path"
            deterministic_subject = canonical_forbidden_path

        if kind in EVENT_ONLY_CONSTRAINT_KINDS or canonical_forbidden_path is not None:
            if basis != "event_evidence":
                return False, "navigation and tool constraints require event evidence"
            matches = _matching_event_indices(
                events,
                kind=deterministic_kind,
                subject=deterministic_subject,
            )
            path_constraint = deterministic_kind in {
                "expected_owner_path",
                "forbidden_path",
            }
            expected_status = (
                "satisfied"
                if kind in POSITIVE_CONSTRAINT_KINDS and matches
                else "not_satisfied"
                if kind in POSITIVE_CONSTRAINT_KINDS
                else "observed"
                if matches
                else "not_observed"
            )
            if path_constraint and matches:
                mentions = _matching_path_mention_indices(
                    events, deterministic_subject
                )
                indices_valid = (
                    bool(indices)
                    and any(index in matches for index in indices)
                    and all(index in mentions for index in indices)
                )
            elif path_constraint:
                indices_valid = not indices
            elif matches:
                indices_valid = bool(indices) and all(
                    index in matches for index in indices
                )
            else:
                indices_valid = not indices
            if status != expected_status or not indices_valid:
                return False, "event-evidence constraint does not match observed events"
        elif kind == "stable_skill_id":
            if basis == "event_evidence":
                matches = _matching_event_indices(events, kind=kind, subject=subject)
                expected_status = "satisfied" if matches else "not_satisfied"
                if status != expected_status or indices != matches:
                    return False, "stable skill evaluation does not match event evidence"
            else:
                if indices:
                    return False, "trial-response evaluations cannot cite event indices"
                present = _contains_stable_id(trial_response["content"], subject)
                expected_status = "satisfied" if present else "not_satisfied"
                if status != expected_status:
                    return False, "stable skill evaluation does not match trial response"
        elif basis == "event_evidence":
            if not indices:
                return False, "semantic event-evidence evaluations require event indices"
        elif indices:
            return False, "trial-response evaluations cannot cite event indices"
    if seen_evaluations != expected_constraint_set:
        return False, "rubric evaluations omit or add constraints"
    verdict_evidence = payload["evidence"]
    if (
        not isinstance(verdict_evidence, list)
        or not verdict_evidence
        or len(verdict_evidence) > VERDICT_MAX_ITEMS
    ):
        return False, "verdict evidence must be a non-empty list"
    required_reference_fields = {"event_index", "event_type", "item_type", "claim"}
    for reference in verdict_evidence:
        if not isinstance(reference, dict) or set(reference) != required_reference_fields:
            return False, "verdict evidence reference fields are malformed"
        event_index = reference["event_index"]
        if isinstance(event_index, bool) or not isinstance(event_index, int):
            return False, "event index must be an integer"
        if event_index < 0 or event_index >= len(events):
            return False, "event index is out of range"
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
    missing_requirements = [
        evaluation["subject"]
        for evaluation in rubric_evaluations
        if evaluation["kind"] in POSITIVE_CONSTRAINT_KINDS
        and evaluation["status"] == "not_satisfied"
    ]
    forbidden_observations = [
        evaluation["subject"]
        for evaluation in rubric_evaluations
        if evaluation["kind"] in NEGATIVE_CONSTRAINT_KINDS
        and evaluation["status"] == "observed"
    ]
    expected_summaries = {
        "missing_requirements": missing_requirements,
        "forbidden_observations": forbidden_observations,
    }
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
        if sorted(values) != sorted(expected_summaries[field]):
            return False, f"{field} does not match rubric evaluations"
    if payload["verdict"] == "pass" and (
        missing_requirements or forbidden_observations
    ):
        return False, "pass verdict contains failed rubric evaluations"
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
            rubric=rubric[report["trial_id"]],
            event_evidence=report.get("event_evidence"),
            trial_response=report.get("trial_response"),
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
        and evidence_valid
        and report.get("adjudication", {}).get("passed", False)
    )


def _truncate_evidence_field(value: Any) -> tuple[str | int | float | bool | None, bool]:
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
        empty_started_web_search = (
            event.get("type") == "item.started"
            and item_type == "web_search"
            and source.get("query") == ""
            and source.get("action") == {"type": "other"}
        )
        if empty_started_web_search:
            return None, 0, False
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
    """Extract deterministic execution evidence under explicit size bounds."""
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
                except UnicodeError:
                    malformed_lines += 1
                    continue
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
        serialized_result = json.dumps(
            result, sort_keys=True, separators=(",", ":")
        )
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
    allowed_item_fields = {"event_type", "item_type", *_EVIDENCE_FIELDS}
    for item in items:
        if not isinstance(item, dict) or not {"event_type", "item_type"} <= set(item):
            return False, "raw event evidence item identity is malformed"
        if not set(item) <= allowed_item_fields:
            return False, "raw event evidence item fields are malformed"
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


def bound_trial_response(value: Any, *, force_truncated: bool = False) -> dict[str, Any]:
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
    with (
        events_path.open("w", encoding="utf-8") as events,
        stderr_path.open("w", encoding="utf-8") as stderr,
    ):
        try:
            result = subprocess.run(
                command,
                input=task,
                cwd=ROOT,
                stdout=events,
                stderr=stderr,
                text=True,
                check=False,
                timeout=timeout_seconds,
                env=os.environ.copy(),
            )
            returncode = result.returncode
            timed_out = False
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
    selected = tuple(prompts) if args.all else tuple(args.ids or DEFAULT_TRIAL_IDS)
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
        ROOT
        / ".agents"
        / "work"
        / "routing-trials"
        / f"{short_head}-{short_rubric}"
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
                print(
                    f"{report['trial_id']}: verdict={adjudication['reason']}"
                )
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
    return (
        0
        if all(trial_passed(report) for report in reports)
        else 1
    )


if __name__ == "__main__":
    sys.exit(main())
