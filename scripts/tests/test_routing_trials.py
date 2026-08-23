from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Mapping
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "scaffold"))

import run_routing_trials as trials  # noqa: E402
import trial_harness as harness  # noqa: E402

TEST_RUBRIC = {
    "id": "trial",
    "expected_owner_paths": ["AGENTS.md"],
    "required_outcomes": ["owner path"],
    "forbidden_outcomes": ["loaded path"],
}
EvidenceMutation = Callable[[dict[str, object]], object]
EvaluationMutation = Callable[[list[dict[str, object]]], object]


def _evaluation(
    kind: str,
    subject: str,
    status: str,
    basis: str,
    indices: list[int],
) -> dict[str, object]:
    return {
        "kind": kind,
        "subject": subject,
        "status": status,
        "basis": basis,
        "evidence_event_indices": indices,
    }


def _rubric_evaluations(
    *, required_status: str = "satisfied", forbidden_status: str = "not_observed"
) -> list[dict[str, object]]:
    return [
        _evaluation(
            "expected_owner_path", "AGENTS.md", "satisfied", "event_evidence", [0]
        ),
        _evaluation(
            "required_outcome", "owner path", required_status, "trial_response", []
        ),
        _evaluation(
            "forbidden_outcome", "loaded path", forbidden_status, "trial_response", []
        ),
    ]


def _complete_event_evidence(
    items: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    if items is None:
        items = [
            {
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
        "rubric_evaluations": _rubric_evaluations(),
        "missing_requirements": [],
        "forbidden_observations": [],
        "tested_commit": "tested",
        "rubric_commit": "rubric",
    }
    verdict.update(overrides)
    return verdict


def _validate_verdict(
    payload: object,
    event_evidence: object,
    rubric: dict[str, Any] = TEST_RUBRIC,
    trial_response: object | None = None,
) -> tuple[bool, str]:
    return trials.validate_verdict(
        payload,
        trial_id="trial",
        tested_commit="tested",
        rubric_commit="rubric",
        rubric=rubric,
        event_evidence=event_evidence,
        trial_response=(
            trial_response
            if trial_response is not None
            else trials.bound_trial_response({"outcome": "bounded"})
        ),
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


def test_thesis_authoring_fixtures_are_exclusive_and_bound_unloaded_paths() -> None:
    expected = {
        "academic-writing-related-work-synthesis": "academic-writing",
        "typst-authoring-accepted-content-render": "typst-authoring",
        "scientific-review-empirical-validity": "scientific-review",
        "rollout-report-owner-not-writing-skill": "nearest code/report owner",
    }
    rubric = trials.load_rubric()
    assert set(trials.THESIS_AUTHORING_TRIAL_IDS) == set(expected)
    for trial_id, owner in expected.items():
        fixture = rubric[trial_id]
        required = fixture["required_outcomes"]
        forbidden = fixture["forbidden_outcomes"]
        assert f"exactly one exclusive leading owner: {owner}" in required
        assert any(" leads " in outcome for outcome in forbidden)
        assert any(
            "non-applicable path is loaded: " in outcome for outcome in forbidden
        )
        assert all(
            key not in fixture
            for key in ("exclusive_leading_owner", "required_unloaded_paths")
        )


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


def test_trial_and_verdict_schemas_are_strict() -> None:
    trial_schema = json.loads(trials.REPORT_SCHEMA.read_text(encoding="utf-8"))
    assert trial_schema["additionalProperties"] is False
    assert set(trial_schema["required"]) == set(trial_schema["properties"])
    serialized_trial = json.dumps(trial_schema)
    assert "expected_owner_paths" not in serialized_trial
    assert "forbidden_outcomes" not in serialized_trial

    verdict_schema = json.loads(trials.VERIFIER_SCHEMA.read_text(encoding="utf-8"))
    assert set(verdict_schema["required"]) == set(verdict_schema["properties"])
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
    evaluations = verdict_schema["properties"]["rubric_evaluations"]
    assert evaluations["minItems"] == 1
    assert evaluations["maxItems"] == trials.VERDICT_MAX_ITEMS
    evaluation_item = evaluations["items"]
    assert evaluation_item["additionalProperties"] is False
    assert set(evaluation_item["required"]) == {
        "kind",
        "subject",
        "status",
        "basis",
        "evidence_event_indices",
    }
    assert set(evaluation_item["properties"]["kind"]["enum"]) == {
        "expected_owner_path",
        "stable_skill_id",
        "expected_tool_ref",
        "forbidden_tool_ref",
        "required_outcome",
        "forbidden_outcome",
    }
    assert (
        evaluation_item["properties"]["evidence_event_indices"]["maxItems"]
        == trials.VERDICT_MAX_ITEMS
    )

    pending: list[object] = [verdict_schema]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            assert "uniqueItems" not in node
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)


def test_generic_rubric_constraints_cover_every_supported_fixture_field() -> None:
    rubric = {
        "expected_owner_paths": ["owner.py"],
        "stable_skill_ids": ["stable-skill"],
        "expected_tool_refs": ["mcp__server__expected"],
        "forbidden_tool_refs": ["mcp__server__forbidden"],
        "required_outcomes": ["required semantic result"],
        "forbidden_outcomes": ["forbidden semantic result"],
    }
    constraints, error = trials._rubric_constraints(rubric)
    assert error is None
    assert constraints == [
        ("expected_owner_path", "owner.py"),
        ("stable_skill_id", "stable-skill"),
        ("expected_tool_ref", "mcp__server__expected"),
        ("forbidden_tool_ref", "mcp__server__forbidden"),
        ("required_outcome", "required semantic result"),
        ("forbidden_outcome", "forbidden semantic result"),
    ]


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
    assert trials.trial_passed(
        {
            "returncode": 0,
            "checkout_clean_after": True,
            "event_evidence": mixed_evidence,
            "adjudication": {"passed": True},
        }
    )


def test_event_evidence_retains_started_execution_and_ignores_chatter(
    tmp_path: Path,
) -> None:
    events = tmp_path / "events.jsonl"
    forbidden_path = ".agents/skills/typst-authoring/SKILL.md"
    records = [
        {
            "type": "item.started",
            "item": {
                "type": "mcp_tool_call",
                "server": "codex_apps",
                "tool": "read_file",
                "arguments": {"path": forbidden_path},
                "status": "in_progress",
            },
        },
        {
            "type": "item.started",
            "item": {
                "type": "command_execution",
                "command": f"sed -n 1,80p {forbidden_path}",
                "path": forbidden_path,
                "status": "in_progress",
            },
        },
        {
            "type": "item.completed",
            "item": {"type": "agent_message", "text": "non-execution chatter"},
        },
        {"type": "turn.completed", "usage": {"input_tokens": 100}},
    ]
    events.write_text(
        "\n".join(json.dumps(record) for record in records),
        encoding="utf-8",
    )

    evidence = trials.extract_event_evidence(events)

    assert len(evidence["items"]) == 2
    assert [item["event_type"] for item in evidence["items"]] == [
        "item.started",
        "item.started",
    ]
    assert evidence["items"][0]["tool"] == "read_file"
    assert forbidden_path in evidence["items"][0]["arguments"]
    assert evidence["items"][1]["path"] == forbidden_path
    assert trials.validate_event_evidence(evidence)[0] is True
    assert (
        trials._matching_event_indices(
            evidence["items"], kind="expected_owner_path", subject=forbidden_path
        )
        == []
    )


def test_empty_started_web_search_placeholder_is_ignorable(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    events.write_text(
        json.dumps(
            {
                "type": "item.started",
                "item": {
                    "id": "exec-placeholder",
                    "type": "web_search",
                    "query": "",
                    "action": {"type": "other"},
                },
            }
        ),
        encoding="utf-8",
    )

    evidence = trials.extract_event_evidence(events)

    assert evidence["items"] == []
    assert evidence["invalid_items"] == 0


@pytest.mark.parametrize("item_type", ["function_call", "tool_call"])
def test_identityless_started_executable_call_remains_invalid(
    tmp_path: Path, item_type: str
) -> None:
    events = tmp_path / f"{item_type}.jsonl"
    events.write_text(
        json.dumps(
            {
                "type": "item.started",
                "item": {"id": "exec-missing-identity", "type": item_type},
            }
        ),
        encoding="utf-8",
    )

    evidence = trials.extract_event_evidence(events)

    assert evidence["items"] == []
    assert evidence["invalid_items"] == 1
    assert trials.validate_event_evidence(evidence)[0] is False


def test_event_evidence_bounds_all_fields_and_fails_closed_when_truncated(
    tmp_path: Path,
) -> None:
    events = tmp_path / "events.jsonl"
    long_text = "x" * (trials.EVENT_EVIDENCE_MAX_FIELD_CHARS * 2)
    records = [
        {
            "type": long_text,
            "command": long_text,
            "status": "completed",
            "exit_code": 0,
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


def test_event_evidence_streams_large_valid_codex_jsonl_without_chatter_counting(
    tmp_path: Path,
) -> None:
    events = tmp_path / "events.jsonl"
    chatter = {
        "type": "item.completed",
        "item": {"type": "agent_message", "text": "x" * 2_000},
    }
    commands = [
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": f"rg -n owner-{index} AGENTS.md",
                "status": "completed",
                "exit_code": 0,
            },
        }
        for index in range(252)
    ]
    records = [chatter] * 600 + commands
    events.write_text(
        "\n".join(json.dumps(record) for record in records),
        encoding="utf-8",
    )
    assert events.stat().st_size > 1_000_000

    evidence = trials.extract_event_evidence(events)

    assert len(evidence["items"]) == 252
    assert evidence["dropped_items"] == 0
    assert evidence["truncated"] is False
    assert trials.validate_event_evidence(evidence) == (
        True,
        "complete raw event evidence",
    )


def test_event_evidence_item_cap_is_complete_at_boundary(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    records = [
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": f"rg -n owner-{index} AGENTS.md",
                "status": "completed",
                "exit_code": 0,
            },
        }
        for index in range(trials.EVENT_EVIDENCE_MAX_ITEMS)
    ]
    events.write_text(
        "\n".join(json.dumps(record) for record in records),
        encoding="utf-8",
    )

    evidence = trials.extract_event_evidence(events)

    assert len(evidence["items"]) == trials.EVENT_EVIDENCE_MAX_ITEMS
    assert evidence["dropped_items"] == 0
    assert trials.validate_event_evidence(evidence)[0] is True


def test_event_evidence_rejects_oversized_raw_stream(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    command = json.dumps(
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "rg -n owner AGENTS.md",
                "status": "completed",
                "exit_code": 0,
            },
        }
    )
    chatter = json.dumps({"type": "turn.completed", "padding": "x" * 4_000})
    repetitions = trials.EVENT_EVIDENCE_MAX_RAW_BYTES // (len(chatter) + 1) + 1
    events.write_text(
        "\n".join([command, *([chatter] * repetitions)]),
        encoding="utf-8",
    )

    evidence = trials.extract_event_evidence(events)

    assert len(evidence["items"]) == 1
    assert evidence["dropped_items"] == 1
    assert evidence["truncated"] is True
    assert trials.validate_event_evidence(evidence)[0] is False


def test_harness_evidence_policy_allows_only_bounded_empty_execution_evidence(
    tmp_path: Path,
) -> None:
    empty_events = tmp_path / "empty.jsonl"
    empty_events.write_bytes(b"")
    empty_evidence = harness.extract_event_evidence(empty_events)

    assert empty_evidence["items"] == []
    assert empty_evidence["payload_chars"] == 2
    assert harness.validate_event_evidence(empty_evidence)[0] is False
    assert harness.validate_event_evidence(
        empty_evidence, require_execution_evidence=False
    ) == (True, "complete raw event evidence with no execution items")

    malformed_events = tmp_path / "malformed.jsonl"
    malformed_events.write_bytes(b"{not-json}\n")
    malformed_evidence = harness.extract_event_evidence(malformed_events)
    assert malformed_evidence["items"] == []
    assert malformed_evidence["malformed_lines"] == 1
    assert (
        harness.validate_event_evidence(
            malformed_evidence, require_execution_evidence=False
        )[0]
        is False
    )

    truncated_events = tmp_path / "truncated.jsonl"
    truncated_events.write_bytes(b"x" * (harness.EVENT_EVIDENCE_MAX_RAW_BYTES + 1))
    truncated_evidence = harness.extract_event_evidence(truncated_events)
    assert truncated_evidence["items"] == []
    assert truncated_evidence["dropped_items"] == 1
    assert truncated_evidence["truncated"] is True
    assert (
        harness.validate_event_evidence(
            truncated_evidence, require_execution_evidence=False
        )[0]
        is False
    )


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
    assert "exclusive_leading_owner" not in payload["instruction"]
    assert "required_unloaded_paths" not in payload["instruction"]
    assert "rubric_evaluations" in payload["instruction"]
    assert "representative relevant" in payload["instruction"]
    assert "all matching" not in payload["instruction"]
    for field in (
        "expected_owner_paths",
        "stable_skill_ids",
        "expected_tool_refs",
        "forbidden_tool_refs",
        "required_outcomes",
        "forbidden_outcomes",
    ):
        assert field in payload["instruction"]


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
    failed_evaluations = _rubric_evaluations(required_status="not_satisfied")
    assert _validate_verdict(
        _verdict(
            verdict="fail",
            rubric_evaluations=failed_evaluations,
            missing_requirements=["owner path"],
        ),
        evidence,
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
def test_pass_rejects_incomplete_raw_evidence(
    mutation: EvidenceMutation, reason: str
) -> None:
    evidence = mutation(_complete_event_evidence())
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


def test_verdict_accepts_repeated_event_index_for_distinct_grounded_claims() -> None:
    evidence = [
        _event_reference(claim="The trial read the owner guidance."),
        _event_reference(claim="The same command established the owner path."),
    ]
    assert _validate_verdict(
        _verdict(evidence=evidence), _complete_event_evidence()
    ) == (True, "pass")


def test_verdict_validation_rejects_malformed_payload() -> None:
    evidence = _complete_event_evidence()
    assert not _validate_verdict(None, evidence)[0]
    assert not _validate_verdict(_verdict(evidence=[]), evidence)[0]


def test_rubric_evaluations_fail_closed_for_omitted_and_observed_constraints() -> None:
    evidence = _complete_event_evidence()
    omitted_required = _verdict(
        rubric_evaluations=_rubric_evaluations()[1:],
    )
    assert not _validate_verdict(omitted_required, evidence)[0]

    observed_forbidden = _verdict(
        rubric_evaluations=_rubric_evaluations(forbidden_status="observed"),
        forbidden_observations=["loaded path"],
    )
    assert not _validate_verdict(observed_forbidden, evidence)[0]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda evaluations: (
            evaluations[:1]
            + [{**evaluations[1], "subject": "other path"}, evaluations[2]]
        ),
        lambda evaluations: [evaluations[0], evaluations[0], evaluations[2]],
        lambda evaluations: [
            {**evaluations[0], "evidence_event_indices": []},
            evaluations[1],
            evaluations[2],
        ],
        lambda evaluations: [
            {**evaluations[0], "evidence_event_indices": [1]},
            evaluations[1],
            evaluations[2],
        ],
        lambda evaluations: [
            {**evaluations[0], "evidence_event_indices": [0, 0]},
            evaluations[1],
            evaluations[2],
        ],
        lambda evaluations: [
            {**evaluations[0], "status": "observed"},
            evaluations[1],
            evaluations[2],
        ],
    ],
)
def test_rubric_evaluations_reject_bad_identity_status_or_bounds(
    mutation: EvaluationMutation,
) -> None:
    evaluations = mutation(_rubric_evaluations())
    assert not _validate_verdict(
        _verdict(rubric_evaluations=evaluations), _complete_event_evidence()
    )[0]


def test_forbidden_tool_ref_cannot_be_ignored() -> None:
    tool_ref = "mcp__codex_apps__context7_query_docs"
    rubric = {
        **TEST_RUBRIC,
        "forbidden_tool_refs": [tool_ref],
    }
    events = _complete_event_evidence(
        [
            {
                "event_type": "item.completed",
                "item_type": "mcp_tool_call",
                "server": "codex_apps",
                "tool": "context7_query_docs",
                "arguments": "AGENTS.md",
                "status": "completed",
            }
        ]
    )
    evaluations = [
        _evaluation(
            "expected_owner_path", "AGENTS.md", "satisfied", "event_evidence", [0]
        ),
        _evaluation(
            "forbidden_tool_ref", tool_ref, "not_observed", "event_evidence", []
        ),
        *_rubric_evaluations()[1:],
    ]
    verdict = _verdict(rubric_evaluations=evaluations)
    assert not _validate_verdict(verdict, events, rubric)[0]


def test_tool_constraint_accepts_representative_matching_citation() -> None:
    tool_ref = "mcp__codex_apps__context7_query_docs"
    rubric = {**TEST_RUBRIC, "expected_tool_refs": [tool_ref]}
    events = _complete_event_evidence(
        [
            {
                "event_type": "item.completed",
                "item_type": "command_execution",
                "command": "sed -n 1,80p AGENTS.md",
                "status": "completed",
                "exit_code": 0,
            },
            {
                "event_type": "item.started",
                "item_type": "mcp_tool_call",
                "server": "codex_apps",
                "tool": "context7_query_docs",
                "status": "in_progress",
            },
            {
                "event_type": "item.completed",
                "item_type": "mcp_tool_call",
                "server": "codex_apps",
                "tool": "context7_query_docs",
                "status": "completed",
            },
        ]
    )
    evaluations = [
        _evaluation(
            "expected_owner_path", "AGENTS.md", "satisfied", "event_evidence", [0]
        ),
        _evaluation("expected_tool_ref", tool_ref, "satisfied", "event_evidence", [2]),
        *_rubric_evaluations()[1:],
    ]

    assert _validate_verdict(
        _verdict(rubric_evaluations=evaluations), events, rubric
    ) == (True, "pass")


@pytest.mark.parametrize("indices", [[], [0, 2]])
def test_tool_constraint_rejects_empty_or_unrelated_observed_citation(
    indices: list[int],
) -> None:
    tool_ref = "mcp__codex_apps__context7_query_docs"
    rubric = {**TEST_RUBRIC, "expected_tool_refs": [tool_ref]}
    events = _complete_event_evidence(
        [
            {
                "event_type": "item.completed",
                "item_type": "command_execution",
                "command": "sed -n 1,80p AGENTS.md",
                "status": "completed",
                "exit_code": 0,
            },
            {
                "event_type": "item.completed",
                "item_type": "mcp_tool_call",
                "server": "codex_apps",
                "tool": "context7_query_docs",
                "status": "completed",
            },
        ]
    )
    evaluations = [
        _evaluation(
            "expected_owner_path", "AGENTS.md", "satisfied", "event_evidence", [0]
        ),
        _evaluation(
            "expected_tool_ref", tool_ref, "satisfied", "event_evidence", indices
        ),
        *_rubric_evaluations()[1:],
    ]

    assert not _validate_verdict(
        _verdict(rubric_evaluations=evaluations), events, rubric
    )[0]


def test_absent_tool_constraint_requires_empty_citation() -> None:
    tool_ref = "mcp__codex_apps__context7_query_docs"
    rubric = {**TEST_RUBRIC, "expected_tool_refs": [tool_ref]}
    evaluations = [
        *_rubric_evaluations()[:1],
        _evaluation(
            "expected_tool_ref", tool_ref, "not_satisfied", "event_evidence", []
        ),
        *_rubric_evaluations()[1:],
    ]
    verdict = _verdict(
        verdict="fail",
        rubric_evaluations=evaluations,
        missing_requirements=[tool_ref],
    )

    assert _validate_verdict(verdict, _complete_event_evidence(), rubric) == (
        True,
        "semantic fail",
    )


def test_started_path_bearing_forbidden_tool_cannot_be_adjudicated_absent() -> None:
    tool_ref = "mcp__codex_apps__read_file"
    forbidden_path = ".agents/skills/typst-authoring/SKILL.md"
    rubric = {**TEST_RUBRIC, "forbidden_tool_refs": [tool_ref]}
    events = _complete_event_evidence(
        [
            {
                "event_type": "item.completed",
                "item_type": "command_execution",
                "command": "sed -n 1,80p AGENTS.md",
                "status": "completed",
                "exit_code": 0,
            },
            {
                "event_type": "item.started",
                "item_type": "mcp_tool_call",
                "server": "codex_apps",
                "tool": "read_file",
                "arguments": json.dumps({"path": forbidden_path}),
                "status": "in_progress",
            },
        ]
    )
    evaluations = [
        _evaluation(
            "expected_owner_path", "AGENTS.md", "satisfied", "event_evidence", [0]
        ),
        _evaluation(
            "forbidden_tool_ref", tool_ref, "not_observed", "event_evidence", []
        ),
        *_rubric_evaluations()[1:],
    ]

    assert not _validate_verdict(
        _verdict(rubric_evaluations=evaluations), events, rubric
    )[0]


@pytest.mark.parametrize("omitted_kind", ["expected_owner_path", "expected_tool_ref"])
def test_expected_owner_and_tool_constraints_cannot_be_omitted(
    omitted_kind: str,
) -> None:
    tool_ref = "mcp__codex_apps__context7_query_docs"
    rubric = {
        **TEST_RUBRIC,
        "expected_tool_refs": [tool_ref],
    }
    events = _complete_event_evidence(
        [
            {
                "event_type": "item.completed",
                "item_type": "command_execution",
                "command": "sed -n 1,80p AGENTS.md",
                "status": "completed",
                "exit_code": 0,
            },
            {
                "event_type": "item.completed",
                "item_type": "mcp_tool_call",
                "server": "codex_apps",
                "tool": "context7_query_docs",
                "status": "completed",
            },
        ]
    )
    evaluations = [
        _evaluation(
            "expected_owner_path", "AGENTS.md", "satisfied", "event_evidence", [0]
        ),
        _evaluation("expected_tool_ref", tool_ref, "satisfied", "event_evidence", [1]),
        *_rubric_evaluations()[1:],
    ]
    evaluations = [item for item in evaluations if item["kind"] != omitted_kind]
    assert not _validate_verdict(
        _verdict(rubric_evaluations=evaluations), events, rubric
    )[0]


def test_expected_owner_path_rejects_suffix_collision() -> None:
    owner_path = "owner/AGENTS.md"
    rubric = {**TEST_RUBRIC, "expected_owner_paths": [owner_path]}
    events = _complete_event_evidence(
        [
            {
                "event_type": "item.completed",
                "item_type": "command_execution",
                "command": "sed -n 1,80p owner/AGENTS.md.bak",
                "status": "completed",
                "exit_code": 0,
            }
        ]
    )
    evaluations = [
        _evaluation(
            "expected_owner_path",
            owner_path,
            "not_satisfied",
            "event_evidence",
            [],
        ),
        *_rubric_evaluations()[1:],
    ]
    verdict = _verdict(
        verdict="fail",
        rubric_evaluations=evaluations,
        missing_requirements=[owner_path],
    )
    assert _validate_verdict(verdict, events, rubric) == (True, "semantic fail")


def test_expected_owner_path_rejects_failed_read() -> None:
    owner_path = "owner/AGENTS.md"
    rubric = {**TEST_RUBRIC, "expected_owner_paths": [owner_path]}
    events = _complete_event_evidence(
        [
            {
                "event_type": "item.completed",
                "item_type": "command_execution",
                "command": f"sed -n 1,80p {owner_path}",
                "path": owner_path,
                "status": "failed",
                "exit_code": 1,
            }
        ]
    )
    evaluations = [
        _evaluation(
            "expected_owner_path",
            owner_path,
            "not_satisfied",
            "event_evidence",
            [],
        ),
        *_rubric_evaluations()[1:],
    ]
    verdict = _verdict(
        verdict="fail",
        rubric_evaluations=evaluations,
        missing_requirements=[owner_path],
    )
    assert _validate_verdict(verdict, events, rubric) == (True, "semantic fail")


def test_nested_shell_success_observes_exact_path() -> None:
    owner_path = "owner/AGENTS.md"
    event = {
        "command": f"/usr/bin/zsh -lc \"sed -n '1,80p' {owner_path}\"",
        "status": "completed",
        "exit_code": 0,
    }

    assert trials._is_successful_path_observation(event, owner_path) is True


def test_nested_shell_rejects_path_suffix_collision() -> None:
    owner_path = "owner/AGENTS.md"
    event = {
        "command": f"/bin/bash -lc \"sed -n '1,80p' {owner_path}.bak\"",
        "status": "completed",
        "exit_code": 0,
    }

    assert trials._is_successful_path_observation(event, owner_path) is False


def test_nested_shell_rejects_malformed_payload() -> None:
    owner_path = "owner/AGENTS.md"
    event = {
        "command": f"/usr/bin/zsh -lc 'sed -n \"1,80p {owner_path}'",
        "status": "completed",
        "exit_code": 0,
    }

    assert trials._is_successful_path_observation(event, owner_path) is False


def test_path_evidence_accepts_started_and_completed_exact_mentions() -> None:
    owner_path = "owner/AGENTS.md"
    rubric = {**TEST_RUBRIC, "expected_owner_paths": [owner_path]}
    events = _complete_event_evidence(
        [
            {
                "event_type": "item.started",
                "item_type": "command_execution",
                "command": f"sed -n 1,80p {owner_path}",
                "status": "in_progress",
            },
            {
                "event_type": "item.completed",
                "item_type": "command_execution",
                "command": f"sed -n 1,80p {owner_path}",
                "status": "completed",
                "exit_code": 0,
            },
        ]
    )
    evaluations = [
        _evaluation(
            "expected_owner_path", owner_path, "satisfied", "event_evidence", [0, 1]
        ),
        *_rubric_evaluations()[1:],
    ]

    assert _validate_verdict(
        _verdict(
            evidence=[_event_reference(event_index=1)],
            rubric_evaluations=evaluations,
        ),
        events,
        rubric,
    ) == (True, "pass")


def test_path_evidence_accepts_omitted_duplicate_success() -> None:
    owner_path = "owner/AGENTS.md"
    rubric = {**TEST_RUBRIC, "expected_owner_paths": [owner_path]}
    events = _complete_event_evidence(
        [
            {
                "event_type": "item.started",
                "item_type": "command_execution",
                "command": f"sed -n 1,80p {owner_path}",
                "status": "in_progress",
            },
            {
                "event_type": "item.completed",
                "item_type": "command_execution",
                "command": f"sed -n 1,80p {owner_path}",
                "status": "completed",
                "exit_code": 0,
            },
            {
                "event_type": "item.completed",
                "item_type": "command_execution",
                "command": f"rg -n owner {owner_path}",
                "status": "completed",
                "exit_code": 0,
            },
        ]
    )
    evaluations = [
        _evaluation(
            "expected_owner_path", owner_path, "satisfied", "event_evidence", [0, 1]
        ),
        *_rubric_evaluations()[1:],
    ]

    assert _validate_verdict(
        _verdict(
            evidence=[_event_reference(event_index=1)],
            rubric_evaluations=evaluations,
        ),
        events,
        rubric,
    ) == (True, "pass")


@pytest.mark.parametrize("indices", [[0, 1, 2], [0]])
def test_path_evidence_rejects_unrelated_extra_or_omitted_success(
    indices: list[int],
) -> None:
    owner_path = "owner/AGENTS.md"
    rubric = {**TEST_RUBRIC, "expected_owner_paths": [owner_path]}
    events = _complete_event_evidence(
        [
            {
                "event_type": "item.started",
                "item_type": "command_execution",
                "command": f"sed -n 1,80p {owner_path}",
                "status": "in_progress",
            },
            {
                "event_type": "item.completed",
                "item_type": "command_execution",
                "command": f"sed -n 1,80p {owner_path}",
                "status": "completed",
                "exit_code": 0,
            },
            {
                "event_type": "item.completed",
                "item_type": "command_execution",
                "command": "sed -n 1,80p unrelated/AGENTS.md",
                "status": "completed",
                "exit_code": 0,
            },
        ]
    )
    evaluations = [
        _evaluation(
            "expected_owner_path", owner_path, "satisfied", "event_evidence", indices
        ),
        *_rubric_evaluations()[1:],
    ]

    assert not _validate_verdict(
        _verdict(
            evidence=[_event_reference(event_index=1)],
            rubric_evaluations=evaluations,
        ),
        events,
        rubric,
    )[0]


def test_canonical_forbidden_path_accepts_started_and_completed_mentions() -> None:
    path = ".agents/skills/typst-authoring/SKILL.md"
    subject = f"{trials.NON_APPLICABLE_PATH_PREFIX}{path}"
    rubric = {**TEST_RUBRIC, "forbidden_outcomes": [subject]}
    events = _complete_event_evidence(
        [
            {
                "event_type": "item.completed",
                "item_type": "command_execution",
                "command": "sed -n 1,80p AGENTS.md",
                "status": "completed",
                "exit_code": 0,
            },
            {
                "event_type": "item.started",
                "item_type": "command_execution",
                "command": f"sed -n 1,80p {path}",
                "status": "in_progress",
            },
            {
                "event_type": "item.completed",
                "item_type": "command_execution",
                "command": f"sed -n 1,80p {path}",
                "status": "completed",
                "exit_code": 0,
            },
        ]
    )
    evaluations = [
        _evaluation(
            "expected_owner_path", "AGENTS.md", "satisfied", "event_evidence", [0]
        ),
        _evaluation(
            "required_outcome", "owner path", "satisfied", "trial_response", []
        ),
        _evaluation("forbidden_outcome", subject, "observed", "event_evidence", [1, 2]),
    ]

    assert _validate_verdict(
        _verdict(
            verdict="fail",
            rubric_evaluations=evaluations,
            forbidden_observations=[subject],
        ),
        events,
        rubric,
    ) == (True, "semantic fail")


def test_loaded_forbidden_path_cannot_use_trial_response_basis() -> None:
    path = ".agents/skills/typst-authoring/SKILL.md"
    subject = f"{trials.NON_APPLICABLE_PATH_PREFIX}{path}"
    rubric = {
        **TEST_RUBRIC,
        "forbidden_outcomes": [subject],
    }
    events = _complete_event_evidence(
        [
            {
                "event_type": "item.completed",
                "item_type": "command_execution",
                "command": f"sed -n 1,80p AGENTS.md {path}",
                "status": "completed",
                "exit_code": 0,
            }
        ]
    )
    evaluations = [
        _evaluation(
            "expected_owner_path", "AGENTS.md", "satisfied", "event_evidence", [0]
        ),
        _evaluation(
            "required_outcome", "owner path", "satisfied", "trial_response", []
        ),
        _evaluation("forbidden_outcome", subject, "not_observed", "trial_response", []),
    ]
    verdict = _verdict(rubric_evaluations=evaluations)
    assert not _validate_verdict(verdict, events, rubric)[0]


def test_forbidden_path_rejects_suffix_collision() -> None:
    path = ".agents/skills/typst-authoring/SKILL.md"
    subject = f"{trials.NON_APPLICABLE_PATH_PREFIX}{path}"
    rubric = {**TEST_RUBRIC, "forbidden_outcomes": [subject]}
    events = _complete_event_evidence(
        [
            {
                "event_type": "item.completed",
                "item_type": "command_execution",
                "command": f"sed -n 1,80p AGENTS.md {path}.bak",
                "status": "completed",
                "exit_code": 0,
            }
        ]
    )
    evaluations = [
        _evaluation(
            "expected_owner_path", "AGENTS.md", "satisfied", "event_evidence", [0]
        ),
        _evaluation(
            "required_outcome", "owner path", "satisfied", "trial_response", []
        ),
        _evaluation("forbidden_outcome", subject, "not_observed", "event_evidence", []),
    ]
    assert _validate_verdict(
        _verdict(rubric_evaluations=evaluations), events, rubric
    ) == (True, "pass")


def test_forbidden_path_rejects_failed_exact_read() -> None:
    path = ".agents/skills/typst-authoring/SKILL.md"
    subject = f"{trials.NON_APPLICABLE_PATH_PREFIX}{path}"
    rubric = {**TEST_RUBRIC, "forbidden_outcomes": [subject]}
    events = _complete_event_evidence(
        [
            {
                "event_type": "item.completed",
                "item_type": "command_execution",
                "command": "sed -n 1,80p AGENTS.md",
                "status": "completed",
                "exit_code": 0,
            },
            {
                "event_type": "item.completed",
                "item_type": "command_execution",
                "command": f"sed -n 1,80p {path}",
                "path": path,
                "status": "failed",
                "exit_code": 1,
            },
        ]
    )
    evaluations = [
        _evaluation(
            "expected_owner_path", "AGENTS.md", "satisfied", "event_evidence", [0]
        ),
        _evaluation(
            "required_outcome", "owner path", "satisfied", "trial_response", []
        ),
        _evaluation("forbidden_outcome", subject, "not_observed", "event_evidence", []),
    ]
    assert _validate_verdict(
        _verdict(rubric_evaluations=evaluations), events, rubric
    ) == (True, "pass")


def test_exact_semantic_outcomes_allow_bounded_trial_response_without_indices() -> None:
    assert _validate_verdict(
        _verdict(),
        _complete_event_evidence(),
        TEST_RUBRIC,
        trial_response=trials.bound_trial_response({"result": "semantic assessment"}),
    ) == (True, "pass")


def test_routing_trial_passed_is_domain_adjudication_only() -> None:
    report = {
        "returncode": 0,
        "checkout_clean_after": True,
        "adjudication": {"passed": False, "reason": "semantic fail"},
    }
    assert trials.trial_passed(report) is False
    report["adjudication"] = {"passed": True, "reason": "pass"}
    assert trials.trial_passed(report) is True


def _run_bounded_verifier(
    report_path: Path,
    trial_dir: Path,
    validator: Callable[[object], tuple[bool, str]],
) -> dict[str, Any]:
    return harness.run_bounded_verifier(
        command=["codex", "-"],
        prompt="bounded prompt",
        report_path=report_path,
        events_path=trial_dir / "events.jsonl",
        stderr_path=trial_dir / "stderr.txt",
        timeout_seconds=1,
        validator=validator,
    )


def test_bounded_verifier_delegates_semantics_and_fails_closed(
    tmp_path: Path,
) -> None:
    trial_dir = tmp_path / "trial"
    trial_dir.mkdir()
    report_path = trial_dir / "verifier-report.json"
    verdict = _verdict()

    def write_report(
        *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        report_path.write_text(json.dumps(verdict), encoding="utf-8")
        return subprocess.CompletedProcess(["codex"], 0)

    with patch("trial_harness.subprocess.run", side_effect=write_report):
        passed = _run_bounded_verifier(
            report_path,
            trial_dir,
            lambda payload: (payload == verdict, "adapter decision"),
        )
    assert passed["passed"] is True
    assert passed["reason"] == "adapter decision"

    report_path.write_bytes(b"\xff")
    with patch(
        "trial_harness.subprocess.run",
        return_value=subprocess.CompletedProcess(["codex"], 0),
    ):
        invalid_utf8 = _run_bounded_verifier(
            report_path, trial_dir, lambda payload: (True, "must not be used")
        )
    assert invalid_utf8["passed"] is False
    assert "unreadable" in invalid_utf8["reason"]

    report_path.write_bytes(b"x" * (trials.VERIFIER_REPORT_MAX_BYTES + 1))
    with patch(
        "trial_harness.subprocess.run",
        return_value=subprocess.CompletedProcess(["codex"], 0),
    ):
        oversized = _run_bounded_verifier(
            report_path, trial_dir, lambda payload: (True, "must not be used")
        )
    assert oversized["passed"] is False
    assert "byte bound" in oversized["reason"]

    report_path.unlink()
    with patch(
        "trial_harness.subprocess.run",
        return_value=subprocess.CompletedProcess(["codex"], 0),
    ):
        missing = _run_bounded_verifier(
            report_path, trial_dir, lambda payload: (True, "must not be used")
        )
    assert missing["passed"] is False

    with patch(
        "trial_harness.subprocess.run",
        side_effect=subprocess.TimeoutExpired(["codex"], 1),
    ):
        timeout = _run_bounded_verifier(
            report_path, trial_dir, lambda payload: (True, "must not be used")
        )
    assert timeout["passed"] is False
    assert timeout["timed_out"] is True


def test_shared_harness_fixture_attestation_and_detached_cleanup(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "harness@example.invalid"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Harness Test"], cwd=repo, check=True)
    fixture = Path("fixture.json")
    (repo / fixture).write_bytes(b'{"value":1}\n')
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "rubric"], cwd=repo, check=True)
    rubric_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    (repo / "candidate").write_text("candidate\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "candidate"], cwd=repo, check=True)
    tested_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert (
        harness.attest_evaluator_fixtures(
            (fixture,),
            tested_commit=tested_commit,
            rubric_commit=rubric_commit,
            root=repo,
        )[fixture]
        == b'{"value":1}\n'
    )
    with pytest.raises(RuntimeError):
        with harness.detached_worktree(tested_commit, root=repo) as checkout:
            assert "Not currently on any branch" in harness.run_git(
                "status", "--branch", cwd=checkout
            )
            raise RuntimeError("exercise finally")
    assert "checkout" not in harness.run_git("worktree", "list", cwd=repo)


def test_run_suite_owns_lifecycle_persistence_and_exit_aggregation(
    tmp_path: Path,
) -> None:
    class Adapter:
        def load_fixtures(self, fixture_bytes: Mapping[Path, bytes]) -> object:
            return None

        def select_cases(
            self, fixtures: object, *, selected_ids: tuple[str, ...], all_cases: bool
        ) -> tuple[harness.TrialCase, ...]:
            return (
                harness.TrialCase(
                    "case",
                    None,
                    candidate=harness.CandidateProvenance(
                        candidate_bytes=b"fixture\n",
                        author=harness.PrincipalIdentity("fixture-author", "author"),
                        expected_sha256=hashlib.sha256(b"fixture\n").hexdigest(),
                        source_locator="fixture.json",
                    ),
                    adapter_metadata={"category": "synthetic"},
                ),
            )

        def build_trial_prompt(self, case: harness.TrialCase) -> str:
            return "bounded prompt"

        def build_verifier_prompt(
            self,
            case: harness.TrialCase,
            report: Mapping[str, Any],
            rubric_commit: str,
        ) -> str:
            return "bounded verifier prompt"

        def validate_verdict(
            self,
            case: harness.TrialCase,
            payload: object,
            report: Mapping[str, Any],
            rubric_commit: str,
        ) -> tuple[bool, str]:
            return False, "semantic fail"

        def trial_passed(self, report: Mapping[str, Any]) -> bool:
            return True

    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "harness@example.invalid"], cwd=root, check=True
    )
    subprocess.run(["git", "config", "user.name", "Harness Test"], cwd=root, check=True)
    fixture = root / "fixture.json"
    fixture.write_text('{"candidate":"fixture"}\n', encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    output_root = tmp_path / "outputs"
    spec = harness.SuiteSpec(
        tested_ref=commit,
        rubric_ref=commit,
        identity=harness.SuiteIdentity(
            name="test",
            dirty_root_message="dirty",
            worktree_prefix="test-",
        ),
        fixture_paths=(Path("fixture.json"),),
        output_root=output_root,
        trial_schema=tmp_path / "trial-schema.json",
        verifier_schema=tmp_path / "verifier-schema.json",
        require_execution_evidence=False,
        require_candidate_provenance=True,
        root=root,
    )
    spec.trial_schema.write_text("{}", encoding="utf-8")
    spec.verifier_schema.write_text("{}", encoding="utf-8")
    codex_result = type("Result", (), {"returncode": 0, "stdout": "codex test\n"})()

    def fake_git(*args: str, cwd: Path) -> str:
        return commit if args[:2] == ("rev-parse", commit) else ""

    with (
        patch.object(harness, "run_git", side_effect=fake_git),
        patch("trial_harness.subprocess.run", return_value=codex_result),
    ):
        result = harness.run_suite(spec, Adapter())
    assert result.exit_code == 1
    assert result.output_dir is not None
    assert (result.output_dir / "case" / "report.json").is_file()
    assert (result.output_dir / "index.json").is_file()
    report = json.loads(
        (result.output_dir / "case" / "report.json").read_text(encoding="utf-8")
    )
    assert len(report["prompt_sha256"]) == 64
    assert "raw event evidence" not in report["adjudication"]["reason"]
    assert (
        report["candidate"]["candidate_sha256"]
        == hashlib.sha256(b"fixture\n").hexdigest()
    )
    assert report["candidate"]["source_locator"] == "fixture.json"
    assert report["candidate"]["author"]["canonical"] == "fixture-author:author"
    assert report["adapter_metadata"] == {"category": "synthetic"}
    assert "candidate_bytes" not in json.dumps(report)
    index = json.loads((result.output_dir / "index.json").read_text(encoding="utf-8"))
    assert index["reviewer"]["canonical"].startswith("host-user:")
    assert (
        index["reports"][0]["candidate"]["candidate_sha256"]
        == report["candidate"]["candidate_sha256"]
    )
    assert index["reports"][0]["adapter_metadata"] == {"category": "synthetic"}
    assert "candidate_bytes" not in json.dumps(index)
    assert report["runtime"]["reviewer_host"]
    with (
        patch.object(harness, "run_git", side_effect=fake_git),
        pytest.raises(ValueError, match="already exists"),
    ):
        harness.run_suite(spec, Adapter())
    assert "checkout" not in harness.run_git("worktree", "list", cwd=root)


def test_suite_rejects_duplicate_ids_before_output_creation(tmp_path: Path) -> None:
    class DuplicateAdapter:
        def load_fixtures(self, fixture_bytes: Mapping[Path, bytes]) -> object:
            return None

        def select_cases(
            self, fixtures: object, *, selected_ids: tuple[str, ...], all_cases: bool
        ) -> tuple[harness.TrialCase, ...]:
            return (
                harness.TrialCase("duplicate", None),
                harness.TrialCase("duplicate", None),
            )

        def build_trial_prompt(self, case: harness.TrialCase) -> str:
            return ""

        def build_verifier_prompt(
            self, case: harness.TrialCase, report: Mapping[str, Any], rubric_commit: str
        ) -> str:
            return ""

        def validate_verdict(
            self,
            case: harness.TrialCase,
            payload: object,
            report: Mapping[str, Any],
            rubric_commit: str,
        ) -> tuple[bool, str]:
            return False, ""

        def trial_passed(self, report: Mapping[str, Any]) -> bool:
            return False

    spec = harness.SuiteSpec(
        tested_ref="HEAD",
        rubric_ref="HEAD",
        identity=harness.SuiteIdentity("duplicate", "dirty", "duplicate-"),
        fixture_paths=(),
        output_root=tmp_path / "outputs",
        trial_schema=tmp_path / "trial.json",
        verifier_schema=tmp_path / "verifier.json",
        root=tmp_path,
    )
    with (
        patch.object(harness, "run_git", return_value="commit"),
        patch.object(harness, "attest_evaluator_fixtures", return_value={}),
        pytest.raises(ValueError, match="trial IDs must be unique"),
    ):
        harness.run_suite(spec, DuplicateAdapter())
    assert not spec.output_root.exists()


def test_candidate_provenance_rejects_malformed_sha_and_identity(
    tmp_path: Path,
) -> None:
    candidate_bytes = b"candidate"
    reviewer = harness.ReviewerProvenance(
        harness.PrincipalIdentity("host-user", "reviewer@host"), "host", 0.0
    )
    with pytest.raises(ValueError, match="SHA-256 is malformed"):
        harness._candidate_report(
            harness.CandidateProvenance(
                candidate_bytes,
                harness.PrincipalIdentity("fixture-author", "author"),
                expected_sha256="bad",
            ),
            reviewer=reviewer,
        )
    with pytest.raises(ValueError, match="identity is malformed"):
        harness._candidate_report(
            harness.CandidateProvenance(
                candidate_bytes,
                harness.PrincipalIdentity("host-user", "reviewer@host"),
            ),
            reviewer=reviewer,
        )
    with pytest.raises(ValueError, match="does not match exact bytes"):
        harness._candidate_report(
            harness.CandidateProvenance(
                candidate_bytes,
                harness.PrincipalIdentity("fixture-author", "author"),
                expected_sha256="0" * 64,
            ),
            reviewer=reviewer,
        )
    with pytest.raises(ValueError, match="empty or malformed"):
        harness._candidate_report(
            harness.CandidateProvenance(
                b"", harness.PrincipalIdentity("fixture-author", "author")
            ),
            reviewer=reviewer,
        )

    with pytest.raises(ValueError, match="must retain host"):
        harness._candidate_report(
            harness.CandidateProvenance(
                candidate_bytes,
                harness.PrincipalIdentity("host-user", "reviewer"),
            ),
            reviewer=reviewer,
        )
    distinct_author = harness._candidate_report(
        harness.CandidateProvenance(
            candidate_bytes,
            harness.PrincipalIdentity("fixture-author", "reviewer"),
        ),
        reviewer=reviewer,
    )
    assert distinct_author is not None
    assert distinct_author["author"]["canonical"] == "fixture-author:reviewer"


def test_adapter_metadata_is_bounded_json_safe_and_namespaced() -> None:
    with pytest.raises(ValueError, match="reserved key"):
        harness._validate_adapter_metadata({"returncode": 0})
    with pytest.raises(ValueError, match="not JSON-safe"):
        harness._validate_adapter_metadata({"value": object()})
    with pytest.raises(ValueError, match="too many keys"):
        harness._validate_adapter_metadata(
            {
                f"key-{index}": index
                for index in range(harness.ADAPTER_METADATA_MAX_KEYS + 1)
            }
        )
    with pytest.raises(ValueError, match="byte bound"):
        harness._validate_adapter_metadata(
            {"value": "x" * harness.ADAPTER_METADATA_MAX_BYTES}
        )
    with pytest.raises(ValueError, match="depth bound"):
        harness._validate_adapter_metadata(
            {"level": {"level": {"level": {"level": {"level": "too deep"}}}}}
        )


def test_suite_mechanical_gates_cannot_be_rescued_by_domain_adapter(
    tmp_path: Path,
) -> None:
    spec = harness.SuiteSpec(
        tested_ref="HEAD",
        rubric_ref="HEAD",
        identity=harness.SuiteIdentity("mechanical", "dirty", "mechanical-"),
        fixture_paths=(),
        output_root=tmp_path / "outputs",
        trial_schema=tmp_path / "trial.json",
        verifier_schema=tmp_path / "verifier.json",
    )
    base: dict[str, Any] = {
        "returncode": 0,
        "timed_out": False,
        "checkout_clean_before": True,
        "checkout_clean_after": True,
        "event_evidence": _complete_event_evidence(),
        "adjudication": {"passed": True, "returncode": 0, "timed_out": False},
    }
    assert harness._mechanically_passed(base, spec=spec) is True
    invalid_reports = [
        {**base, "returncode": 1},
        {**base, "checkout_clean_before": False},
        {**base, "timed_out": True},
        {**base, "event_evidence": {"malformed": True}},
        {
            **base,
            "adjudication": {"passed": False, "returncode": 0, "timed_out": False},
        },
    ]

    def adapter_trial_passed(report: Mapping[str, Any]) -> bool:
        return True

    assert all(
        not (
            harness._mechanically_passed(report, spec=spec)
            and adapter_trial_passed(report)
        )
        for report in invalid_reports
    )


def test_routing_main_delegates_lifecycle_to_run_suite() -> None:
    args = type(
        "Args",
        (),
        {
            "head": "candidate",
            "ids": ["case"],
            "all": False,
            "list": False,
            "model": "model",
            "effort": "high",
            "jobs": 2,
            "timeout": 3,
        },
    )()
    expected = harness.SuiteResult(exit_code=7)
    with (
        patch.object(trials, "parse_args", return_value=args),
        patch.object(trials, "run_suite", return_value=expected) as run,
    ):
        assert trials.main() == 7
    spec = run.call_args.args[0]
    assert isinstance(spec, harness.SuiteSpec)
    assert spec.tested_ref == "candidate"
    assert spec.jobs == 2
    assert spec.require_execution_evidence is True
    assert run.call_args.args[1].__class__ is trials.RoutingAdapter
