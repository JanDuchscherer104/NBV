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
PRODUCTION_CORPUS_PATHS = (
    Path("AGENTS.md"),
    Path("Makefile"),
    Path(".agents/references/human_owner_intent.md"),
    Path(".agents/skills"),
    Path(".omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md"),
    Path("aria_nbv/AGENTS.md"),
    Path("aria_nbv/aria_nbv"),
    Path("aria_nbv/tests"),
    Path("docs/AGENTS.md"),
    Path("docs/typst/shared"),
    Path("docs/typst/thesis/sections"),
)
EVALUATOR_DERIVED_PREFIXES = (
    "scripts/scaffold/",
    "scripts/tests/",
    ".agents/memory/",
    ".agents/work/",
)
EVENT_EVIDENCE_MAX_ITEMS = 64
EVENT_EVIDENCE_MAX_FIELD_CHARS = 4_096
EVENT_EVIDENCE_MAX_TOTAL_CHARS = 32_768
EVENT_EVIDENCE_MAX_RAW_BYTES = 1_048_576
TRIAL_RESPONSE_MAX_CHARS = 16_384
VERIFIER_REPORT_MAX_BYTES = 1_048_576
VERDICT_MAX_ITEMS = 64
VERDICT_MAX_FIELD_CHARS = 2_048
_TRUNCATION_SUFFIX = "...<truncated>"
TRIAL_EXECUTION_PROTOCOL = (
    "This is a concrete read-only ARIA-NBV routing trial. Inspect the repository and "
    "demonstrate the route with focused, bounded evidence. Inspect the named real "
    "contract and its exact owner or owners; do not substitute an invented example. "
    "Describe the precise scoped decision and run or name a bounded read-only proof. "
    "Do not mutate the checkout; leave it clean. This source-order suite does "
    "not provision optional navigation artifacts; exact production sources are "
    "the only admissible evidence. The "
    "task below is the only task-specific input; do not infer evaluator guidance "
    "or candidate changes from it."
)
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


def run_git(*args: str, cwd: Path = ROOT) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot_manifest(checkout: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for path in sorted(checkout.rglob("*")):
        relative = path.relative_to(checkout)
        if relative.parts and relative.parts[0] in {".git", "graphify-out"}:
            continue
        if path.is_file() and not path.is_symlink():
            manifest[relative.as_posix()] = _sha256_file(path)
    return manifest


def _manifest_sha256(manifest: dict[str, str]) -> str:
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _checkout_digest(checkout: Path) -> str:
    manifest: dict[str, str] = {}
    for path in sorted(checkout.rglob("*")):
        relative = path.relative_to(checkout)
        if relative.parts and relative.parts[0] == ".git":
            continue
        if path.is_file() and not path.is_symlink():
            manifest[relative.as_posix()] = _sha256_file(path)
    return _manifest_sha256(manifest)


def _write_bundle_manifest(output_dir: Path) -> dict[str, Any]:
    files = {
        path.relative_to(output_dir).as_posix(): _sha256_file(path)
        for path in sorted(output_dir.rglob("*"))
        if path.is_file() and path.name not in {"bundle-manifest.json", "index.json"}
    }
    payload = {"algorithm": "sha256", "files": files}
    manifest_path = output_dir / "bundle-manifest.json"
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return {"path": manifest_path.name, "sha256": _sha256_file(manifest_path)}


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


def materialize_trial_snapshot(
    *, tested_commit: str, checkout: Path, root: Path = ROOT
) -> None:
    """Create a standalone clean snapshot from an explicit production allowlist."""
    checkout.mkdir(parents=True, exist_ok=False)
    listed = run_git(
        "ls-tree",
        "-r",
        "--full-tree",
        tested_commit,
        "--",
        *(path.as_posix() for path in PRODUCTION_CORPUS_PATHS),
        cwd=root,
    ).splitlines()
    if not listed:
        raise ValueError("production corpus allowlist selected no files")
    for entry in listed:
        mode, object_type, _object_id, relative_name = entry.split(None, 3)
        relative_name = relative_name.split("\t", 1)[-1]
        if relative_name.startswith(EVALUATOR_DERIVED_PREFIXES):
            raise ValueError(f"evaluator-derived path entered corpus: {relative_name}")
        target = checkout / relative_name
        if object_type != "blob":
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        blob = subprocess.run(
            ["git", "cat-file", "blob", _object_id],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
        target.write_bytes(blob)
        os.chmod(target, int(mode, 8))

    evaluator_needles: set[str] = set()
    for source in EVALUATOR_FIXTURE_PATHS:
        try:
            raw = read_git_blob("HEAD", source, root=root).decode("utf-8")
        except ValueError:
            continue
        records: list[Any]
        if source == PROMPTS_RELATIVE:
            records = [json.loads(line) for line in raw.splitlines() if line.strip()]
        else:
            payload = json.loads(raw)
            records = payload.get("fixtures", []) if isinstance(payload, dict) else []
        for record in records:
            if not isinstance(record, dict):
                continue
            for key in ("id", "task", "required_outcomes", "forbidden_outcomes"):
                value = record.get(key)
                values = value if isinstance(value, list) else [value]
                evaluator_needles.update(
                    item for item in values if isinstance(item, str) and len(item) >= 12
                )
    for path in checkout.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError:
            continue
        if any(needle in text for needle in evaluator_needles):
            raise ValueError(f"evaluator content entered production corpus: {path}")

    run_git("init", "--quiet", cwd=checkout)
    run_git("config", "user.email", "routing-snapshot@example.invalid", cwd=checkout)
    run_git("config", "user.name", "Routing Snapshot", cwd=checkout)
    run_git("add", "--all", cwd=checkout)
    run_git(
        "-c",
        "core.hooksPath=/dev/null",
        "commit",
        "--quiet",
        "-m",
        "materialize routing trial snapshot",
        cwd=checkout,
    )


def provision_trial_graph(checkout: Path) -> dict[str, str]:
    """Optionally attest mixed-source Graphify; the source-order suite does not call it."""
    remaining_fixtures = [
        path.as_posix()
        for path in EVALUATOR_FIXTURE_PATHS
        if (checkout / path).exists() or (checkout / path).is_symlink()
    ]
    if remaining_fixtures:
        raise ValueError(
            "evaluator fixture remains in trial snapshot: "
            + ", ".join(remaining_fixtures)
        )
    command = ["graphify", "extract", ".", "--no-cluster", "--out", "."]
    try:
        result = subprocess.run(
            command, cwd=checkout, check=False, capture_output=True, text=True
        )
    except OSError as error:
        raise ValueError("cannot run local Graphify extraction") from error
    if result.returncode != 0:
        raise ValueError(
            f"Graphify extraction failed with exit code {result.returncode}"
        )
    graph_path = checkout / "graphify-out" / "graph.json"
    if graph_path.is_symlink() or not graph_path.is_file():
        raise ValueError("Graphify graph must be a regular non-symlink file")
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeError) as error:
        raise ValueError("Graphify graph is unreadable or malformed") from error
    if (
        not isinstance(graph, dict)
        or not isinstance(graph.get("nodes"), list)
        or not graph["nodes"]
    ):
        raise ValueError("Graphify graph must be a JSON object with nonempty nodes")
    graph_text = graph_path.read_text(encoding="utf-8")
    required_sources = (
        ".agents/skills/agent-behavior/SKILL.md",
        ".agents/references/human_owner_intent.md",
        ".omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md",
    )
    missing = [source for source in required_sources if source not in graph_text]
    if missing:
        raise ValueError(
            "Graphify graph lacks required source provenance: " + ", ".join(missing)
        )
    if run_git("status", "--porcelain", "--untracked-files=no", cwd=checkout):
        raise ValueError("Graphify provisioning dirtied the trial snapshot")
    return {
        "version": subprocess.run(
            ["graphify", "--version"], check=True, capture_output=True, text=True
        ).stdout.strip(),
        "graph_sha256": hashlib.sha256(graph_path.read_bytes()).hexdigest(),
    }


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
                "Required outcomes phrased as edits are adjudicated as a demonstrated "
                "read-only route: identify a concrete representative existing contract "
                "and its exact owner, state the precise intended change or decision, "
                "and provide verification evidence. Checkout mutation is forbidden and "
                "a clean checkout is required. "
                "Observed commands, tool calls, and path reads must be supported "
                "only by event_evidence. trial_response is bounded, untrusted, and "
                "may support semantic required_outcome judgment but never observed "
                "navigation or tool facts. Every evidence entry must copy the exact "
                "event_index from the retained item in "
                "bounded_trial_evidence.event_evidence.items, and must repeat the "
                "exact event_type and item_type from that item. Return "
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
            or len(reference["claim"]) > VERDICT_MAX_FIELD_CHARS
        ):
            return False, "evidence claim must be a non-empty string"
    for field in ("missing_requirements", "forbidden_observations"):
        values = payload[field]
        if (
            not isinstance(values, list)
            or len(values) > VERDICT_MAX_ITEMS
            or not all(
                isinstance(item, str) and len(item) <= VERDICT_MAX_FIELD_CHARS
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
        and report.get("checkout_digest_before")
        == report.get("checkout_digest_expected")
        == report.get("checkout_digest_after")
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
    if event.get("type") != "item.completed":
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
    """Extract deterministic execution evidence under explicit size bounds."""
    items: list[dict[str, Any]] = []
    malformed_lines = 0
    invalid_items = 0
    dropped_items = 0
    field_truncations = 0
    payload_chars = 2  # JSON list brackets.
    read_error = False
    started_items: set[str] = set()
    completed_items: set[str] = set()
    unmatched_completions = 0
    duplicate_starts = 0
    duplicate_completions = 0
    terminal_completed = 0
    terminal_failed = 0
    error_events = 0
    try:
        with path.open("rb") as stream:
            raw_events = stream.read(EVENT_EVIDENCE_MAX_RAW_BYTES + 1)
        if len(raw_events) > EVENT_EVIDENCE_MAX_RAW_BYTES:
            bounded_events = raw_events[:EVENT_EVIDENCE_MAX_RAW_BYTES]
            # The bounded prefix is useful for diagnostics only. The unread
            # suffix makes the complete event stream unknown, even at a line
            # boundary, so mark the evidence incomplete unconditionally.
            lines = bounded_events.decode("utf-8").splitlines()
            dropped_items = 1
        else:
            lines = raw_events.decode("utf-8").splitlines()
    except (OSError, UnicodeError):
        lines = []
        read_error = True
    for line in lines:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            malformed_lines += 1
            continue
        if isinstance(event, dict):
            event_type = event.get("type")
            item = event.get("item")
            item_id = item.get("id") if isinstance(item, dict) else None
            item_type = item.get("type") if isinstance(item, dict) else None
            tracks_lifecycle = item_type in _EXECUTION_IDENTITY_FIELDS
            if event_type == "item.started" and tracks_lifecycle:
                if not isinstance(item_id, str) or not item_id:
                    invalid_items += 1
                elif item_id in started_items:
                    duplicate_starts += 1
                else:
                    started_items.add(item_id)
            elif event_type == "item.completed" and tracks_lifecycle:
                if not isinstance(item_id, str) or not item_id:
                    invalid_items += 1
                elif item_id in completed_items:
                    duplicate_completions += 1
                else:
                    completed_items.add(item_id)
                    unmatched_completions += int(item_id not in started_items)
            elif event_type == "turn.completed":
                terminal_completed += 1
            elif event_type == "turn.failed":
                terminal_failed += 1
            elif event_type == "error":
                error_events += 1
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
        record["event_index"] = len(items)
        serialized = json.dumps(record, sort_keys=True, separators=(",", ":"))
        item_chars = len(serialized) + int(bool(items))
        if payload_chars + item_chars > EVENT_EVIDENCE_MAX_TOTAL_CHARS:
            dropped_items += 1
            continue
        items.append(record)
        payload_chars += item_chars
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
            "lifecycle": {
                "started_items": len(started_items),
                "completed_items": len(completed_items),
                "unmatched_starts": len(started_items - completed_items),
                "unmatched_completions": unmatched_completions,
                "duplicate_starts": duplicate_starts,
                "duplicate_completions": duplicate_completions,
                "terminal_completed": terminal_completed,
                "terminal_failed": terminal_failed,
                "error_events": error_events,
            },
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
        "lifecycle",
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
    lifecycle = evidence["lifecycle"]
    lifecycle_fields = {
        "started_items",
        "completed_items",
        "unmatched_starts",
        "unmatched_completions",
        "duplicate_starts",
        "duplicate_completions",
        "terminal_completed",
        "terminal_failed",
        "error_events",
    }
    if (
        not isinstance(lifecycle, dict)
        or set(lifecycle) != lifecycle_fields
        or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in lifecycle.values()
        )
    ):
        return False, "raw event lifecycle is malformed"
    if lifecycle["started_items"] != lifecycle["completed_items"]:
        return False, "raw event lifecycle item counts differ"
    if any(
        lifecycle[field]
        for field in (
            "unmatched_starts",
            "unmatched_completions",
            "duplicate_starts",
            "duplicate_completions",
            "terminal_failed",
            "error_events",
        )
    ):
        return False, "raw event lifecycle is incomplete or contradictory"
    if lifecycle["terminal_completed"] != 1:
        return False, "raw event lifecycle needs exactly one completed turn"
    items = evidence["items"]
    if not isinstance(items, list) or not items:
        return False, "raw event evidence is empty"
    if len(items) > EVENT_EVIDENCE_MAX_ITEMS:
        return False, "raw event evidence exceeds the item bound"
    allowed_item_fields = {"event_index", "event_type", "item_type", *_EVIDENCE_FIELDS}
    for position, item in enumerate(items):
        if not isinstance(item, dict) or not {"event_type", "item_type"} <= set(item):
            return False, "raw event evidence item identity is malformed"
        if not set(item) <= allowed_item_fields:
            return False, "raw event evidence item fields are malformed"
        event_index = item.get("event_index")
        if isinstance(event_index, bool) or not isinstance(event_index, int):
            return False, "raw event evidence event index is malformed"
        if event_index != position:
            return False, "raw event evidence event index is inconsistent"
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
    run_id: str | None = None,
    checkout_digest_expected: str,
) -> dict[str, Any]:
    trial_dir = output_dir / (run_id or trial_id)
    trial_dir.mkdir(parents=True, exist_ok=False)
    events_path = trial_dir / "events.jsonl"
    stderr_path = trial_dir / "stderr.txt"
    trial_response_path = trial_dir / "trial-response.json"
    final_report = trial_dir / "report.json"
    execution_prompt = build_trial_prompt(task)
    command = _build_codex_command(
        checkout=checkout,
        output_schema=REPORT_SCHEMA,
        output_report=trial_response_path,
        model=model,
        effort=effort,
    )
    clean_before = run_git("status", "--porcelain", cwd=checkout)
    digest_before = _checkout_digest(checkout)
    started = time.time()
    with (
        events_path.open("w", encoding="utf-8") as events,
        stderr_path.open("w", encoding="utf-8") as stderr,
    ):
        try:
            result = subprocess.run(
                command,
                input=execution_prompt,
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
    digest_after = _checkout_digest(checkout)
    runtime = {
        "codex_version": codex_version,
        "requested_model": model,
        "requested_effort": effort,
        "command_flags": command[1:-1],
    }
    report = {
        "trial_id": trial_id,
        "prompt_sha256": hashlib.sha256(execution_prompt.encode()).hexdigest(),
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
        "checkout_digest_expected": checkout_digest_expected,
        "checkout_digest_before": digest_before,
        "checkout_digest_after": digest_after,
        "artifacts": {
            "events": events_path.name,
            "stderr": stderr_path.name,
            "trial_response": trial_response_path.name,
        },
        "trial_response": read_trial_response(trial_response_path),
    }
    final_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def build_trial_prompt(task: str) -> str:
    """Add the generic execution protocol to one fixture task."""
    return f"{TRIAL_EXECUTION_PROTOCOL}\n\nTask:\n{task}"


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
    parser.add_argument(
        "--repetitions", type=int, default=1, help="Matched repetitions per trial."
    )
    parser.add_argument(
        "--baseline-index", type=Path, help="Prior immutable index to compare."
    )
    parser.add_argument(
        "--treatment-path",
        action="append",
        default=[],
        help="Corpus path allowed to differ from the baseline; repeat as needed.",
    )
    parser.add_argument("--timeout", type=int, default=600, help="Seconds per trial.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tested_commit = run_git("rev-parse", args.head)
    rubric_commit = run_git("rev-parse", "HEAD")
    fixture_bytes = {
        path: read_git_blob(rubric_commit, path) for path in EVALUATOR_FIXTURE_PATHS
    }
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
    if not args.model or not args.effort:
        raise SystemExit("--model and --effort are required for reviewable trials")
    if args.jobs != 1:
        raise SystemExit("--jobs must be 1; every trial owns an isolated snapshot")
    if args.repetitions < 1:
        raise SystemExit("--repetitions must be positive")
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
    runner_sha256 = _sha256_file(ROOT / "scripts/scaffold/run_routing_trials.py")
    evaluation_config = {
        "codex_version": codex_version,
        "model": args.model,
        "effort": args.effort,
        "timeout_seconds": args.timeout,
        "jobs": args.jobs,
        "repetitions": args.repetitions,
        "runner_sha256": runner_sha256,
        "protocol_sha256": hashlib.sha256(
            TRIAL_EXECUTION_PROTOCOL.encode()
        ).hexdigest(),
        "prompts_sha256": hashlib.sha256(fixture_bytes[PROMPTS_RELATIVE]).hexdigest(),
        "rubric_sha256": hashlib.sha256(fixture_bytes[RUBRIC_RELATIVE]).hexdigest(),
        "report_schema_sha256": _sha256_file(REPORT_SCHEMA),
        "verifier_schema_sha256": _sha256_file(VERIFIER_SCHEMA),
        "production_corpus_paths": [
            path.as_posix() for path in PRODUCTION_CORPUS_PATHS
        ],
    }
    reports: list[dict[str, Any]] = []
    corpus_manifest: dict[str, str] | None = None
    for repetition in range(1, args.repetitions + 1):
        for trial_id in selected:
            with tempfile.TemporaryDirectory(
                prefix=f"aria-routing-{short_head}-"
            ) as temp:
                checkout = Path(temp) / "checkout"
                materialize_trial_snapshot(
                    tested_commit=tested_commit, checkout=checkout
                )
                current_manifest = _snapshot_manifest(checkout)
                if corpus_manifest is None:
                    corpus_manifest = current_manifest
                elif corpus_manifest != current_manifest:
                    raise SystemExit("isolated trial corpus manifests differ")
                checkout_digest_expected = _checkout_digest(checkout)
                run_id = f"{trial_id}__r{repetition}"
                report = run_trial(
                    trial_id=trial_id,
                    run_id=run_id,
                    task=prompts[trial_id],
                    head=tested_commit,
                    rubric_commit=rubric_commit,
                    checkout=checkout,
                    checkout_digest_expected=checkout_digest_expected,
                    output_dir=output_dir,
                    codex_version=codex_version,
                    model=args.model,
                    effort=args.effort,
                    timeout_seconds=args.timeout,
                )
                adjudication = run_verifier(
                    report=report,
                    rubric=rubric,
                    rubric_commit=rubric_commit,
                    checkout=checkout,
                    trial_dir=output_dir / run_id,
                    model=args.model,
                    effort=args.effort,
                    timeout_seconds=args.timeout,
                )
                report["adjudication"] = adjudication
                (output_dir / run_id / "report.json").write_text(
                    json.dumps(report, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                print(f"{report['trial_id']}: verdict={adjudication['reason']}")
                reports.append(report)

    index = {
        "tested_commit": tested_commit,
        "rubric_commit": rubric_commit,
        "codex_version": codex_version,
        "evaluation_config": evaluation_config,
        "corpus_manifest": corpus_manifest or {},
        "corpus_manifest_sha256": _manifest_sha256(corpus_manifest or {}),
        "trial_ids": list(selected),
        "reports": [
            {
                "trial_id": report["trial_id"],
                "returncode": report["returncode"],
                "timed_out": report["timed_out"],
                "checkout_clean_after": report["checkout_clean_after"],
                "adjudicated": report.get("adjudication", {}).get("passed", False),
                "verdict": report.get("adjudication", {}).get("verdict"),
                "report": f"{report['trial_id']}__r{position // len(selected) + 1}/report.json",
            }
            for position, report in enumerate(reports)
        ],
        "statistics": {
            trial_id: {
                "repetitions": args.repetitions,
                "passes": sum(
                    trial_passed(report)
                    for report in reports
                    if report["trial_id"] == trial_id
                ),
                "uncertainty": (
                    "single unseeded trajectory; no stability claim"
                    if args.repetitions == 1
                    else "unseeded repeated trajectories; report empirical pass rate"
                ),
            }
            for trial_id in selected
        },
    }
    if args.baseline_index:
        baseline = json.loads(args.baseline_index.read_text(encoding="utf-8"))
        if baseline.get("evaluation_config") != evaluation_config:
            raise SystemExit("baseline and candidate evaluation configurations differ")
        baseline_manifest = baseline.get("corpus_manifest")
        if not isinstance(baseline_manifest, dict):
            raise SystemExit("baseline corpus manifest is missing")
        changed_paths = sorted(
            path
            for path in set(baseline_manifest) | set(corpus_manifest or {})
            if baseline_manifest.get(path) != (corpus_manifest or {}).get(path)
        )
        allowed = set(args.treatment_path)
        if not changed_paths or not set(changed_paths) <= allowed:
            raise SystemExit(
                "corpus differences do not match declared treatment paths: "
                + ", ".join(changed_paths)
            )
        index["comparison"] = {
            "matched": True,
            "baseline_tested_commit": baseline.get("tested_commit"),
            "candidate_tested_commit": tested_commit,
            "treatment_paths": sorted(allowed),
            "changed_paths": changed_paths,
            "baseline_corpus_manifest_sha256": baseline.get("corpus_manifest_sha256"),
            "candidate_corpus_manifest_sha256": index["corpus_manifest_sha256"],
        }
    (output_dir / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    index["bundle"] = _write_bundle_manifest(output_dir)
    (output_dir / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0 if all(trial_passed(report) for report in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
