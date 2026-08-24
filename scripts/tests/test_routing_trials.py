from __future__ import annotations

import json
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from threading import Event, Lock
from typing import Any
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "scaffold"))

import run_routing_trials as trials  # noqa: E402


def _complete_event_evidence() -> dict[str, object]:
    items = [
        {
            "event_index": 0,
            "event_type": "item.completed",
            "item_type": "command_execution",
            "command": "rg -n owner AGENTS.md",
            "status": "completed",
            "exit_code": 0,
        }
    ]
    payload = json.dumps(items, sort_keys=True, separators=(",", ":"))
    return {
        "bounds": {
            "max_items": trials.EVENT_EVIDENCE_MAX_ITEMS,
            "max_field_chars": trials.EVENT_EVIDENCE_MAX_FIELD_CHARS,
            "max_total_chars": trials.EVENT_EVIDENCE_MAX_TOTAL_CHARS,
        },
        "items": items,
        "payload_chars": len(payload),
        "malformed_lines": 0,
        "invalid_items": 0,
        "dropped_items": 0,
        "field_truncations": 0,
        "truncated": False,
        "read_error": False,
    }


def _event_reference(**overrides: object) -> dict[str, object]:
    reference: dict[str, object] = {
        "event_index": 0,
        "event_type": "item.completed",
        "item_type": "command_execution",
        "claim": "The trial read the owner guidance.",
    }
    reference.update(overrides)
    return reference


def _verdict(**overrides: object) -> dict[str, object]:
    verdict: dict[str, object] = {
        "trial_id": "trial",
        "verdict": "pass",
        "evidence": [_event_reference()],
        "missing_requirements": [],
        "forbidden_observations": [],
        "tested_commit": "tested",
        "rubric_commit": "rubric",
    }
    verdict.update(overrides)
    return verdict


def _validate_verdict(payload: object, event_evidence: object) -> tuple[bool, str]:
    return trials.validate_verdict(
        payload,
        trial_id="trial",
        tested_commit="tested",
        rubric_commit="rubric",
        event_evidence=event_evidence,
    )


def _run_verifier(
    report: dict[str, object], checkout: Path, trial_dir: Path
) -> dict[str, Any]:
    return trials.run_verifier(
        report=report,
        rubric={"trial": {"id": "trial"}},
        rubric_commit="rubric",
        checkout=checkout,
        trial_dir=trial_dir,
        model=None,
        effort=None,
        timeout_seconds=1,
    )


def _trial_report() -> dict[str, object]:
    return {
        "trial_id": "trial",
        "tested_commit": "tested",
        "rubric_commit": "rubric",
        "returncode": 0,
        "timed_out": False,
        "checkout_clean_before": True,
        "checkout_clean_after": True,
        "runtime": {},
        "execution": {
            "sandbox": trials.READ_ONLY_SANDBOX,
            "required_changed_path_prefixes": [],
            "typst_proof": None,
            "changed_paths": [],
        },
        "stream_capture": {
            "events": {
                "observed_bytes": 1,
                "maximum_bytes": trials.EVENT_EVIDENCE_MAX_RAW_STREAM_BYTES,
                "overflowed": False,
            },
            "stderr": {
                "observed_bytes": 0,
                "maximum_bytes": trials.TRIAL_STDERR_MAX_BYTES,
                "overflowed": False,
            },
        },
        "trial_response": trials.bound_trial_response({"outcome": "bounded"}),
        "event_evidence": _complete_event_evidence(),
    }


def test_prompt_and_rubric_ids_match_without_prompt_leakage() -> None:
    prompts = trials.load_prompts()
    assert set(prompts) == set(trials.load_rubric())
    assert set(trials.DEFAULT_TRIAL_IDS) <= set(prompts)
    for task in prompts.values():
        assert "expected_owner_paths" not in task
        assert "required_outcomes" not in task
        assert "forbidden_outcomes" not in task
        assert "mcp__" not in task


def test_academic_authoring_trial_selection_is_a_small_disjoint_suite() -> None:
    assert trials.ACADEMIC_AUTHORING_TRIAL_IDS == (
        "academic-writing-related-work-synthesis",
        "typst-authoring-layout-repair",
        "scientific-review-frozen-claim",
        "thesis-claim-revision",
        "empirical-result-revision",
        "rollout-report-owner-not-writing-skill",
    )
    rubric = trials.load_rubric()
    assert set(trials.ACADEMIC_AUTHORING_TRIAL_IDS) <= set(rubric)


def test_academic_authoring_prompts_are_natural_and_cover_composed_edits() -> None:
    prompts = trials.load_prompts()
    rubric = trials.load_rubric()
    for trial_id in trials.ACADEMIC_AUTHORING_TRIAL_IDS:
        task = prompts[trial_id].lower()
        for leaked_route_word in (
            "academic-writing",
            "scientific-review",
            "typst-authoring",
            "accepted content",
            "handoff",
            "red-team",
        ):
            assert leaked_route_word not in task, trial_id
    for trial_id in ("thesis-claim-revision", "empirical-result-revision"):
        required = rubric[trial_id]["required_outcomes"]
        assert any("ordered route:" in outcome for outcome in required)
        assert any("active Typst source is changed" in outcome for outcome in required)
        assert any("compile and affected-page render proof" in outcome for outcome in required)


def test_academic_authoring_selector_runs_only_its_focused_suite() -> None:
    prompts = trials.load_prompts()
    args = type(
        "Args",
        (),
        {"all": False, "academic_authoring": True, "ids": None},
    )()
    assert trials.select_trial_ids(args, prompts) == trials.ACADEMIC_AUTHORING_TRIAL_IDS


def test_academic_authoring_selector_rejects_ambiguous_all_selection() -> None:
    args = type(
        "Args",
        (),
        {"all": True, "academic_authoring": True, "ids": None},
    )()
    with pytest.raises(ValueError, match="cannot be combined"):
        trials.select_trial_ids(args, trials.load_prompts())


def test_bounded_stream_capture_terminates_on_overflow() -> None:
    destination = BytesIO()
    overflow = Event()
    terminated: list[bool] = []

    trials._copy_bounded_stream(
        BytesIO(b"abcdef"),
        destination,
        maximum_bytes=4,
        overflow=overflow,
        on_overflow=lambda: terminated.append(True),
        lock=Lock(),
        written=[0],
    )

    assert destination.getvalue() == b"abcd"
    assert overflow.is_set()
    assert terminated == [True]


def test_codex_command_is_ephemeral_read_only_and_prompt_free(tmp_path: Path) -> None:
    command = trials._build_codex_command(
        checkout=tmp_path,
        output_schema=trials.REPORT_SCHEMA,
        output_report=tmp_path / "model.json",
        model="test-model",
        effort="high",
    )
    assert "--ephemeral" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert command[command.index("--output-schema") + 1] == str(trials.REPORT_SCHEMA)
    assert command[-1] == "-"
    assert "expected_owner_paths" not in " ".join(command)


def test_workspace_write_contract_requires_source_change_and_typst_proof() -> None:
    contract = trials.execution_contract(
        {
            "execution_mode": trials.WORKSPACE_WRITE_SANDBOX,
            "required_changed_path_prefixes": ["docs/typst/thesis/"],
            "typst_proof": True,
        }
    )
    assert contract["sandbox"] == trials.WORKSPACE_WRITE_SANDBOX
    with pytest.raises(ValueError, match="require a source path and Typst proof"):
        trials.execution_contract({"execution_mode": trials.WORKSPACE_WRITE_SANDBOX})


def test_subject_checkout_removes_evaluator_fixtures_and_history(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    prompts = checkout / trials.PROMPTS_RELATIVE
    rubric = checkout / trials.RUBRIC_RELATIVE
    prompts.parent.mkdir(parents=True)
    (checkout / "README.md").write_text("subject\n", encoding="utf-8")
    prompts.write_text('{"id":"trial","task":"answer"}\n', encoding="utf-8")
    rubric.write_text('{"fixtures":[{"id":"trial","answer":"leaked"}]}\n', encoding="utf-8")
    (checkout / ".git").write_text("gitdir: ignored\n", encoding="utf-8")

    trials.prepare_subject_checkout(checkout)

    assert not prompts.exists()
    assert not rubric.exists()
    result = subprocess.run(
        ["git", "show", f"HEAD:{trials.RUBRIC_RELATIVE.as_posix()}"],
        cwd=checkout,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_detached_subject_worktree_is_pruned_after_isolation(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    checkout = tmp_path / "checkout"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(
        ["git", "config", "user.email", "routing@example.invalid"],
        cwd=repository,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Routing Test"], cwd=repository, check=True
    )
    for relative_path in trials.EVALUATOR_FIXTURE_PATHS:
        path = repository / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8")
    (repository / "README.md").write_text("subject\n", encoding="utf-8")
    subprocess.run(["git", "add", "--all"], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "subject"], cwd=repository, check=True)
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(checkout), "HEAD"],
        cwd=repository,
        check=True,
    )

    trials.prepare_subject_checkout(checkout)
    trials.remove_subject_checkout(checkout, repository=repository)

    assert not checkout.exists()
    registered = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert str(checkout) not in registered


def test_editable_trial_requires_changed_source_and_passing_proof() -> None:
    report = _trial_report()
    report["execution"] = {
        "sandbox": trials.WORKSPACE_WRITE_SANDBOX,
        "required_changed_path_prefixes": ["docs/typst/thesis/"],
        "changed_paths": ["docs/typst/thesis/sections/01-research-questions.typ"],
        "typst_proof": {"passed": True},
    }
    report["adjudication"] = {"passed": True}
    assert trials.trial_passed(report)
    report["execution"]["typst_proof"] = {"passed": False}  # type: ignore[index]
    assert not trials.trial_passed(report)


def test_stream_capture_requires_per_stream_bounded_receipts() -> None:
    report = _trial_report()
    assert trials.validate_stream_capture(report["stream_capture"])
    report["stream_capture"]["events"]["observed_bytes"] = (  # type: ignore[index]
        trials.EVENT_EVIDENCE_MAX_RAW_STREAM_BYTES + 1
    )
    assert not trials.validate_stream_capture(report["stream_capture"])


def test_trial_and_verdict_schemas_are_strict() -> None:
    trial_schema = json.loads(trials.REPORT_SCHEMA.read_text(encoding="utf-8"))
    assert trial_schema["additionalProperties"] is False
    assert set(trial_schema["required"]) == set(trial_schema["properties"])
    serialized_trial = json.dumps(trial_schema)
    assert "expected_owner_paths" not in serialized_trial
    assert "forbidden_outcomes" not in serialized_trial

    verdict_schema = json.loads(trials.VERIFIER_SCHEMA.read_text(encoding="utf-8"))
    evidence_item = verdict_schema["properties"]["evidence"]["items"]
    assert (
        verdict_schema["properties"]["evidence"]["maxItems"] == trials.VERDICT_MAX_ITEMS
    )
    assert evidence_item["additionalProperties"] is False
    assert set(evidence_item["required"]) == {
        "event_index",
        "event_type",
        "item_type",
        "claim",
    }
    for field in ("missing_requirements", "forbidden_observations"):
        items = verdict_schema["properties"][field]["items"]
        assert (
            verdict_schema["properties"][field]["maxItems"] == trials.VERDICT_MAX_ITEMS
        )
        assert items["maxLength"] == trials.EVENT_EVIDENCE_MAX_FIELD_CHARS


def test_cross_commit_fixture_attestation_accepts_equal_and_rejects_drift(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "routing@example.invalid"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Routing Test"], cwd=repo, check=True)
    prompts = repo / trials.PROMPTS_RELATIVE
    rubric = repo / trials.RUBRIC_RELATIVE
    prompts.parent.mkdir(parents=True)
    prompts.write_text('{"id":"trial","task":"first"}\n', encoding="utf-8")
    rubric.write_text('{"fixtures":[{"id":"trial"}]}\n', encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "rubric"], cwd=repo, check=True)
    rubric_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    (repo / "candidate.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "candidate.py"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "candidate"], cwd=repo, check=True)
    matching_tested_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    fixture_bytes = trials.attest_evaluator_fixtures(
        tested_commit=matching_tested_commit,
        rubric_commit=rubric_commit,
        root=repo,
    )
    assert fixture_bytes[trials.PROMPTS_RELATIVE] == prompts.read_bytes()

    prompts.write_text('{"id":"trial","task":"second"}\n', encoding="utf-8")
    subprocess.run(["git", "add", str(trials.PROMPTS_RELATIVE)], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture drift"], cwd=repo, check=True)
    tested_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    with pytest.raises(ValueError, match="differs from rubric commit"):
        trials.attest_evaluator_fixtures(
            tested_commit=tested_commit,
            rubric_commit=rubric_commit,
            root=repo,
        )


def test_event_evidence_keeps_commands_tools_paths_and_omits_noise(
    tmp_path: Path,
) -> None:
    events = tmp_path / "events.jsonl"
    records = [
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "rg -n owner AGENTS.md aria_nbv/AGENTS.md",
                "aggregated_output": "unbounded command output",
                "status": "completed",
                "exit_code": 0,
            },
        },
        {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call",
                "server": "codex_apps",
                "tool": "context7_query_docs",
                "arguments": {"libraryId": "/graphify-labs/graphify"},
                "result": "unbounded tool output",
                "status": "completed",
            },
        },
        {
            "type": "turn.completed",
            "usage": {"input_tokens": 1000},
            "input": {"tool": "claimed_context7_call"},
        },
        {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": "claimed tool call context7_query_docs",
            },
        },
    ]
    lines = [json.dumps(record) for record in records]
    events.write_text("\n".join([lines[0], "{malformed", *lines[1:]]))

    evidence = trials.extract_event_evidence(events)

    assert evidence["malformed_lines"] == 1
    assert evidence["invalid_items"] == 0
    assert len(evidence["items"]) == 2
    command, tool = evidence["items"]
    assert command["command"] == "rg -n owner AGENTS.md aria_nbv/AGENTS.md"
    assert command["status"] == "completed"
    assert command["exit_code"] == 0
    assert tool["server"] == "codex_apps"
    assert tool["tool"] == "context7_query_docs"
    assert "/graphify-labs/graphify" in tool["arguments"]
    evidence_text = json.dumps(evidence)
    assert "aggregated_output" not in evidence_text
    assert "unbounded tool output" not in evidence_text
    assert "input_tokens" not in evidence_text
    assert "claimed_context7_call" not in evidence_text
    assert "claimed tool call" not in evidence_text
    assert trials.validate_event_evidence(evidence)[0] is False

    mixed = tmp_path / "mixed.jsonl"
    mixed.write_text(
        "\n".join(
            [
                lines[0],
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "status": "completed",
                            "exit_code": 0,
                        },
                    }
                ),
                lines[2],
            ]
        ),
        encoding="utf-8",
    )
    mixed_evidence = trials.extract_event_evidence(mixed)

    assert len(mixed_evidence["items"]) == 1
    assert mixed_evidence["invalid_items"] == 1
    assert not trials.validate_event_evidence(mixed_evidence)[0]
    assert not _validate_verdict(_verdict(), mixed_evidence)[0]
    assert not trials.trial_passed(
        {
            "returncode": 0,
            "checkout_clean_after": True,
            "event_evidence": mixed_evidence,
            "adjudication": {"passed": True},
        }
    )


def test_event_evidence_bounds_all_fields_and_fails_closed_when_truncated(
    tmp_path: Path,
) -> None:
    events = tmp_path / "events.jsonl"
    long_text = "x" * (trials.EVENT_EVIDENCE_MAX_FIELD_CHARS * 2)
    records = [
        {
            "type": long_text,
            "item": {
                "type": long_text,
                "command": long_text,
                "status": "completed",
                "exit_code": 0,
            },
        }
    ]
    records.extend(
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": f"rg owner path-{index}",
                "status": "completed",
                "exit_code": 0,
            },
        }
        for index in range(trials.EVENT_EVIDENCE_MAX_ITEMS + 6)
    )
    events.write_text("\n".join(json.dumps(record) for record in records))

    evidence = trials.extract_event_evidence(events)

    assert len(evidence["items"]) <= trials.EVENT_EVIDENCE_MAX_ITEMS
    assert evidence["field_truncations"] == 3
    assert evidence["dropped_items"] > 0
    assert evidence["truncated"] is True
    for field in ("event_type", "item_type", "command"):
        assert len(evidence["items"][0][field]) == trials.EVENT_EVIDENCE_MAX_FIELD_CHARS
    serialized = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
    assert len(serialized) <= trials.EVENT_EVIDENCE_MAX_TOTAL_CHARS
    assert trials.validate_event_evidence(evidence)[0] is False


def test_event_evidence_rejects_oversized_raw_stream(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    events.write_bytes(b"x" * (trials.EVENT_EVIDENCE_MAX_RAW_LINE_BYTES + 1))

    evidence = trials.extract_event_evidence(events)

    assert evidence["items"] == []
    assert evidence["dropped_items"] >= 1
    assert evidence["truncated"] is True
    assert trials.validate_event_evidence(evidence)[0] is False


def test_event_evidence_streams_large_jsonl_without_retaining_ignored_output(
    tmp_path: Path,
) -> None:
    events = tmp_path / "events.jsonl"
    records = [
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": f"rg owner path-{index}",
                "aggregated_output": "x" * 120_000,
                "status": "completed",
                "exit_code": 0,
            },
        }
        for index in range(20)
    ]
    events.write_text("\n".join(json.dumps(record) for record in records))

    evidence = trials.extract_event_evidence(events)

    assert events.stat().st_size < trials.EVENT_EVIDENCE_MAX_RAW_STREAM_BYTES
    assert len(evidence["items"]) == len(records)
    assert [item["event_index"] for item in evidence["items"]] == list(
        range(len(records))
    )
    assert evidence["truncated"] is False
    assert trials.validate_event_evidence(evidence)[0] is True


def test_event_evidence_rejects_aggregate_raw_stream_overflow(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    record = {
        "type": "item.completed",
        "item": {
            "type": "command_execution",
            "command": "rg owner path",
            "status": "completed",
            "exit_code": 0,
        },
    }
    line = (json.dumps(record) + "\n").encode()
    events.write_bytes(
        line * (trials.EVENT_EVIDENCE_MAX_RAW_STREAM_BYTES // len(line) + 1)
    )

    evidence = trials.extract_event_evidence(events)

    assert events.stat().st_size > trials.EVENT_EVIDENCE_MAX_RAW_STREAM_BYTES
    assert evidence["dropped_items"] >= 1
    assert evidence["truncated"] is True
    assert trials.validate_event_evidence(evidence)[0] is False


def test_trial_response_is_bounded_and_never_observed_evidence() -> None:
    claimed = "claimed_tool_call" * trials.TRIAL_RESPONSE_MAX_CHARS
    trial_response = trials.bound_trial_response({"tool_calls": [claimed]})
    report = _trial_report()
    report["trial_response"] = trial_response
    report["runtime"] = {
        "codex_version": "codex 1.0",
        "event_types": [claimed],
        "observed_usage": [claimed],
    }
    prompt = trials.build_verifier_prompt(
        rubric={"id": "trial", "required_outcomes": ["owner path"]},
        report=report,
        rubric_commit="rubric",
    )
    payload = json.loads(prompt)
    bounded = payload["bounded_trial_evidence"]

    assert trial_response["label"] == "untrusted_trial_response"
    assert trial_response["truncated"] is True
    assert len(trial_response["content"]) == trials.TRIAL_RESPONSE_MAX_CHARS
    assert "model_report" not in bounded
    assert "event_types" not in bounded["runtime"]
    assert "observed_usage" not in bounded["runtime"]
    assert claimed not in json.dumps(bounded["event_evidence"])
    assert bounded["trial_response"]["label"] == "untrusted_trial_response"
    assert bounded["tested_commit"] == "tested"
    assert bounded["rubric_commit"] == "rubric"
    assert payload["rubric_commit"] == "rubric"


def test_read_trial_response_reads_bounded_stream_once(tmp_path: Path) -> None:
    class CountingBytesIO(BytesIO):
        def __init__(self, value: bytes) -> None:
            super().__init__(value)
            self.read_calls = 0

        def read(self, size: int | None = -1) -> bytes:
            self.read_calls += 1
            return super().read(size)

    stream = CountingBytesIO(b'{"outcome":"kept"}')
    with patch.object(Path, "open", return_value=stream):
        response = trials.read_trial_response(tmp_path / "trial-response.json")

    assert stream.read_calls == 1
    assert response["content"] == '{"outcome":"kept"}'
    assert response["truncated"] is False


def test_verdict_validation_covers_pass_semantic_fail_and_identity() -> None:
    evidence = _complete_event_evidence()
    assert _validate_verdict(_verdict(), evidence) == (True, "pass")
    assert _validate_verdict(
        _verdict(verdict="fail", missing_requirements=["owner"]), evidence
    ) == (True, "semantic fail")
    for mismatch in (
        {"tested_commit": "other"},
        {"rubric_commit": "other"},
        {"trial_id": "other"},
    ):
        assert not _validate_verdict(_verdict(**mismatch), evidence)[0]
    assert not _validate_verdict(
        _verdict(missing_requirements=["x"] * (trials.VERDICT_MAX_ITEMS + 1)),
        evidence,
    )[0]
    assert not _validate_verdict(
        _verdict(
            forbidden_observations=["x" * (trials.EVENT_EVIDENCE_MAX_FIELD_CHARS + 1)]
        ),
        evidence,
    )[0]


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda evidence: None, "absent or malformed"),
        (lambda evidence: {**evidence, "malformed_lines": 1}, "incomplete"),
        (lambda evidence: {**evidence, "dropped_items": 1}, "incomplete"),
        (
            lambda evidence: {
                **evidence,
                "field_truncations": 1,
                "truncated": True,
            },
            "incomplete",
        ),
        (lambda evidence: {**evidence, "read_error": True}, "incomplete"),
    ],
)
def test_pass_rejects_incomplete_raw_evidence(mutation: object, reason: str) -> None:
    evidence = mutation(_complete_event_evidence())  # type: ignore[operator]
    valid, actual_reason = _validate_verdict(_verdict(), evidence)
    assert valid is False
    assert reason in actual_reason


@pytest.mark.parametrize(
    "reference",
    [
        _event_reference(event_index=1),
        _event_reference(event_type="other"),
        _event_reference(item_type="other"),
        _event_reference(event_index=True),
        {"event_index": 0, "claim": "missing identities"},
    ],
)
def test_verdict_rejects_invalid_event_references(reference: object) -> None:
    assert not _validate_verdict(
        _verdict(evidence=[reference]), _complete_event_evidence()
    )[0]


def test_verdict_rejects_duplicate_event_references() -> None:
    reference = _event_reference()
    assert not _validate_verdict(
        _verdict(evidence=[reference, reference]), _complete_event_evidence()
    )[0]


def test_verdict_validation_rejects_malformed_payload() -> None:
    evidence = _complete_event_evidence()
    assert not _validate_verdict(None, evidence)[0]
    assert not _validate_verdict(_verdict(evidence=[]), evidence)[0]


def test_aggregate_requires_passing_adjudication() -> None:
    report = _trial_report()
    report["adjudication"] = {"passed": False, "reason": "semantic fail"}
    assert trials.trial_passed(report) is False
    report["adjudication"] = {"passed": True, "reason": "pass"}
    assert trials.trial_passed(report) is True


def test_run_verifier_pass_and_semantic_fail_without_live_model(tmp_path: Path) -> None:
    report = _trial_report()
    checkout = tmp_path / "checkout"
    trial_dir = tmp_path / "trial"
    checkout.mkdir()
    trial_dir.mkdir()

    def write_verdict(verdict: dict[str, object]) -> object:
        (trial_dir / "verifier-report.json").write_text(
            json.dumps(verdict), encoding="utf-8"
        )
        return type("Result", (), {"returncode": 0})()

    with patch.object(
        trials.subprocess,
        "run",
        side_effect=lambda *args, **kwargs: write_verdict(_verdict()),
    ):
        passed = _run_verifier(report, checkout, trial_dir)
    assert passed["passed"] is True

    failing_verdict = _verdict(verdict="fail", missing_requirements=["owner"])
    with patch.object(
        trials.subprocess,
        "run",
        side_effect=lambda *args, **kwargs: write_verdict(failing_verdict),
    ):
        failed = _run_verifier(report, checkout, trial_dir)
    assert failed["passed"] is False
    assert failed["reason"] == "semantic fail"


def test_run_verifier_rejects_invalid_utf8_and_oversized_reports(
    tmp_path: Path,
) -> None:
    report = _trial_report()
    checkout = tmp_path / "checkout"
    trial_dir = tmp_path / "trial"
    checkout.mkdir()
    trial_dir.mkdir()

    def write_invalid(*args: object, **kwargs: object) -> object:
        (trial_dir / "verifier-report.json").write_bytes(b"\xff")
        return type("Result", (), {"returncode": 0})()

    with patch.object(trials.subprocess, "run", side_effect=write_invalid):
        invalid_utf8 = _run_verifier(report, checkout, trial_dir)
    assert invalid_utf8["passed"] is False
    assert "unreadable" in invalid_utf8["reason"]

    def write_oversized(*args: object, **kwargs: object) -> object:
        (trial_dir / "verifier-report.json").write_bytes(
            b"x" * (trials.VERIFIER_REPORT_MAX_BYTES + 1)
        )
        return type("Result", (), {"returncode": 0})()

    with patch.object(trials.subprocess, "run", side_effect=write_oversized):
        oversized = _run_verifier(report, checkout, trial_dir)
    assert oversized["passed"] is False
    assert "byte bound" in oversized["reason"]


def test_run_verifier_missing_and_timeout_fail_closed(tmp_path: Path) -> None:
    report = _trial_report()
    checkout = tmp_path / "checkout"
    checkout.mkdir()

    missing_dir = tmp_path / "missing"
    missing_dir.mkdir()
    result = type("Result", (), {"returncode": 0})()
    with patch.object(trials.subprocess, "run", return_value=result):
        missing = _run_verifier(report, checkout, missing_dir)
    assert missing["passed"] is False

    timeout_dir = tmp_path / "timeout"
    timeout_dir.mkdir()
    with patch.object(
        trials.subprocess,
        "run",
        side_effect=trials.subprocess.TimeoutExpired("codex", 1),
    ):
        timeout = _run_verifier(report, checkout, timeout_dir)
    assert timeout["passed"] is False
    assert timeout["timed_out"] is True
