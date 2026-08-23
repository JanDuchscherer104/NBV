#!/usr/bin/env python3
"""Run bounded, read-only Codex routing trials against an exact Git head."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path
from typing import Any, Mapping, cast

from trial_harness import (
    EVENT_EVIDENCE_MAX_FIELD_CHARS as _harness_event_evidence_max_field_chars,
    EVENT_EVIDENCE_MAX_ITEMS as _harness_event_evidence_max_items,
    EVENT_EVIDENCE_MAX_RAW_BYTES as _harness_event_evidence_max_raw_bytes,
    EVENT_EVIDENCE_MAX_TOTAL_CHARS as _harness_event_evidence_max_total_chars,
    TRIAL_RESPONSE_MAX_CHARS as _harness_trial_response_max_chars,
    VERIFIER_REPORT_MAX_BYTES as _harness_verifier_report_max_bytes,
    attest_evaluator_fixtures as _harness_attest_evaluator_fixtures,
    bound_trial_response as _harness_bound_trial_response,
    build_codex_command as _harness_build_codex_command,
    extract_event_evidence as _harness_extract_event_evidence,
    read_git_blob as _harness_read_git_blob,
    read_trial_response as _harness_read_trial_response,
    run_git as _harness_run_git,
    SuiteSpec,
    SuiteIdentity,
    TrialCase,
    validate_event_evidence as _harness_validate_event_evidence,
    run_suite,
)

EVENT_EVIDENCE_MAX_FIELD_CHARS = _harness_event_evidence_max_field_chars
EVENT_EVIDENCE_MAX_ITEMS = _harness_event_evidence_max_items
EVENT_EVIDENCE_MAX_RAW_BYTES = _harness_event_evidence_max_raw_bytes
EVENT_EVIDENCE_MAX_TOTAL_CHARS = _harness_event_evidence_max_total_chars
TRIAL_RESPONSE_MAX_CHARS = _harness_trial_response_max_chars
VERIFIER_REPORT_MAX_BYTES = _harness_verifier_report_max_bytes

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
VERDICT_MAX_ITEMS = 64
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


def build_verifier_prompt(
    *, rubric: dict[str, Any], report: Mapping[str, Any], rubric_commit: str
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
    required_fields = {
        "expected_owner_paths",
        "required_outcomes",
        "forbidden_outcomes",
    }
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
        **{kind: {"satisfied", "not_satisfied"} for kind in POSITIVE_CONSTRAINT_KINDS},
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
        if (
            not isinstance(evaluation, dict)
            or set(evaluation) != required_evaluation_fields
        ):
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
            or any(
                isinstance(index, bool) or not isinstance(index, int)
                for index in indices
            )
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
                mentions = _matching_path_mention_indices(events, deterministic_subject)
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
                    return (
                        False,
                        "stable skill evaluation does not match event evidence",
                    )
            else:
                if indices:
                    return False, "trial-response evaluations cannot cite event indices"
                present = _contains_stable_id(trial_response["content"], subject)
                expected_status = "satisfied" if present else "not_satisfied"
                if status != expected_status:
                    return (
                        False,
                        "stable skill evaluation does not match trial response",
                    )
        elif basis == "event_evidence":
            if not indices:
                return (
                    False,
                    "semantic event-evidence evaluations require event indices",
                )
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


def trial_passed(report: Mapping[str, Any]) -> bool:
    """Return whether routing adjudication satisfies its domain rubric."""
    adjudication = report.get("adjudication")
    return isinstance(adjudication, Mapping) and adjudication.get("passed") is True


# Keep the old routing import-visible mechanics names as compatibility aliases.
run_git = _harness_run_git
read_git_blob = _harness_read_git_blob
_build_codex_command = _harness_build_codex_command
extract_event_evidence = _harness_extract_event_evidence
validate_event_evidence = _harness_validate_event_evidence
bound_trial_response = _harness_bound_trial_response
read_trial_response = _harness_read_trial_response


def attest_evaluator_fixtures(
    *, tested_commit: str, rubric_commit: str, root: Path = ROOT
) -> dict[Path, bytes]:
    return _harness_attest_evaluator_fixtures(
        EVALUATOR_FIXTURE_PATHS,
        tested_commit=tested_commit,
        rubric_commit=rubric_commit,
        root=root,
    )


class RoutingAdapter:
    """Keep routing fixture and verdict semantics behind the suite seam."""

    def load_fixtures(
        self, fixture_bytes: Mapping[Path, bytes]
    ) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
        prompts = load_prompts(fixture_bytes[PROMPTS_RELATIVE])
        rubric = load_rubric(fixture_bytes[RUBRIC_RELATIVE])
        return prompts, rubric

    def select_cases(
        self,
        fixtures: object,
        *,
        selected_ids: tuple[str, ...],
        all_cases: bool,
    ) -> tuple[TrialCase, ...]:
        prompts, rubric = cast(
            tuple[dict[str, str], dict[str, dict[str, Any]]], fixtures
        )
        if set(prompts) != set(rubric):
            raise ValueError("routing prompt and rubric ID sets differ")
        selected = tuple(prompts) if all_cases else selected_ids
        unknown = sorted(set(selected) - set(prompts))
        if unknown:
            raise ValueError(f"unknown trial IDs: {unknown}")
        return tuple(
            TrialCase(trial_id, (prompts[trial_id], rubric[trial_id]))
            for trial_id in selected
        )

    def build_trial_prompt(self, case: TrialCase) -> str:
        task, _ = cast(tuple[str, dict[str, Any]], case.context)
        return task

    def build_verifier_prompt(
        self, case: TrialCase, report: Mapping[str, Any], rubric_commit: str
    ) -> str:
        _, rubric = cast(tuple[str, dict[str, Any]], case.context)
        return build_verifier_prompt(
            rubric=rubric,
            report=report,
            rubric_commit=rubric_commit,
        )

    def validate_verdict(
        self,
        case: TrialCase,
        payload: object,
        report: Mapping[str, Any],
        rubric_commit: str,
    ) -> tuple[bool, str]:
        _, rubric = cast(tuple[str, dict[str, Any]], case.context)
        return validate_verdict(
            payload,
            trial_id=case.trial_id,
            tested_commit=report["tested_commit"],
            rubric_commit=rubric_commit,
            rubric=rubric,
            event_evidence=report.get("event_evidence"),
            trial_response=report.get("trial_response"),
        )

    def trial_passed(self, report: Mapping[str, Any]) -> bool:
        return trial_passed(report)


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
    spec = SuiteSpec(
        tested_ref=args.head,
        rubric_ref="HEAD",
        identity=SuiteIdentity(
            name="routing",
            dirty_root_message="commit the candidate before routing trials",
            worktree_prefix="aria-routing-",
        ),
        fixture_paths=EVALUATOR_FIXTURE_PATHS,
        output_root=ROOT / ".agents" / "work" / "routing-trials",
        trial_schema=REPORT_SCHEMA,
        verifier_schema=VERIFIER_SCHEMA,
        selected_ids=tuple(args.ids or DEFAULT_TRIAL_IDS),
        all_cases=args.all,
        list_only=args.list,
        model=args.model,
        effort=args.effort,
        jobs=args.jobs,
        timeout_seconds=args.timeout,
    )
    try:
        result = run_suite(spec, RoutingAdapter())
    except ValueError as error:
        raise SystemExit(str(error)) from error
    if result.listed_ids:
        print("\n".join(result.listed_ids))
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
