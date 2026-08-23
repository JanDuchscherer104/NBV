from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
import sys
from io import BytesIO
from pathlib import Path
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
        "lifecycle": {
            "started_items": 1,
            "completed_items": 1,
            "unmatched_starts": 0,
            "unmatched_completions": 0,
            "duplicate_starts": 0,
            "duplicate_completions": 0,
            "terminal_completed": 1,
            "terminal_failed": 0,
            "error_events": 0,
        },
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
        "checkout_digest_expected": "a" * 64,
        "checkout_digest_before": "a" * 64,
        "checkout_digest_after": "a" * 64,
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


def test_trial_prompt_has_generic_protocol_and_only_fixture_task_is_specific() -> None:
    task = "Choose the owner."
    prompt = trials.build_trial_prompt(task)

    assert prompt.startswith(trials.TRIAL_EXECUTION_PROTOCOL)
    assert "concrete read-only ARIA-NBV routing trial" in prompt
    assert "focused, bounded evidence" in prompt
    assert "named real" in prompt
    assert "exact owner or owners" in prompt
    assert "precise scoped decision" in prompt
    assert "bounded read-only proof" in prompt
    assert "Do not mutate the checkout" in prompt
    assert "invented example" in prompt
    assert "does not provision optional navigation artifacts" in prompt
    assert "exact production sources" in prompt
    assert prompt.endswith("Task:\nChoose the owner.")
    for leaked_term in (
        "expected_owner_paths",
        "required_outcomes",
        "forbidden_outcomes",
        "expected outcome",
        "forbidden outcome",
        "candidate diff",
        "hidden rubric",
    ):
        assert leaked_term not in prompt.lower()


def test_evaluator_is_loaded_from_rubric_head_not_tested_corpus() -> None:
    source = inspect.getsource(trials.main)
    assert "read_git_blob(rubric_commit, path)" in source
    assert "attest_evaluator_fixtures" not in source


def test_pr1_routing_trials_are_frozen_and_non_proposal() -> None:
    ids = {
        "reviewed-intent-unsettled-external-skill",
        "scoped-spec-settles-graphify-bundle",
        "thesis-code-shared-contract",
        "helper-lowest-shared-domain-owner",
    }
    assert ids <= set(trials.load_prompts())
    rubric = trials.load_rubric()
    assert ids <= set(rubric)
    for trial_id in ids:
        serialized = json.dumps(rubric[trial_id], sort_keys=True)
        assert serialized
    for trial_id in (
        "reviewed-intent-unsettled-external-skill",
        "scoped-spec-settles-graphify-bundle",
    ):
        serialized = json.dumps(rubric[trial_id], sort_keys=True)
        assert "proposal" not in serialized.lower()


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
        assert items["maxLength"] == trials.VERDICT_MAX_FIELD_CHARS


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


def test_materialized_snapshot_is_standalone_fixture_free_and_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "routing@example.invalid"], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "user.name", "Routing Test"], cwd=repo, check=True)
    (repo / "AGENTS.md").write_text("owner guidance\n", encoding="utf-8")
    executable = repo / "owner.sh"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    for relative_path, content in (
        (trials.PROMPTS_RELATIVE, '{"id":"trial","task":"first"}\n'),
        (trials.RUBRIC_RELATIVE, '{"fixtures":[{"id":"trial"}]}\n'),
    ):
        path = repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "tested"], cwd=repo, check=True)
    tested_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    source_graph = repo / "graphify-out" / "graph.json"
    source_graph.parent.mkdir()
    source_graph.write_text('{"nodes":[{"id":"root"}]}', encoding="utf-8")

    hook_dir = tmp_path / "global-hooks"
    hook_dir.mkdir()
    hook_marker = tmp_path / "hook-ran"
    hook = hook_dir / "pre-commit"
    hook.write_text(f"#!/bin/sh\ntouch {hook_marker}\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    global_config = tmp_path / "gitconfig"
    global_config.write_text(f"[core]\n\thooksPath = {hook_dir}\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))

    checkout = tmp_path / "checkout"
    git_calls: list[tuple[str, ...]] = []
    original_run_git = trials.run_git

    def recording_run_git(*args: str, **kwargs: object) -> str:
        git_calls.append(args)
        return original_run_git(*args, **kwargs)

    with (
        patch.object(trials, "run_git", side_effect=recording_run_git),
        patch.object(
            trials,
            "PRODUCTION_CORPUS_PATHS",
            (Path("AGENTS.md"), Path("owner.sh")),
        ),
    ):
        trials.materialize_trial_snapshot(
            tested_commit=tested_commit, checkout=checkout, root=repo
        )

    assert (checkout / "AGENTS.md").read_text(encoding="utf-8") == "owner guidance\n"
    assert ((checkout / "owner.sh").stat().st_mode & 0o777) == 0o755
    assert not (checkout / "graphify-out").exists()
    for relative_path in trials.EVALUATOR_FIXTURE_PATHS:
        assert not (checkout / relative_path).exists()
        assert (
            subprocess.run(
                ["git", "show", f"HEAD:{relative_path.as_posix()}"],
                cwd=checkout,
                check=False,
                capture_output=True,
            ).returncode
            != 0
        )
        assert (
            subprocess.run(
                ["git", "log", "--all", "--format=", "--", relative_path.as_posix()],
                cwd=checkout,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            == ""
        )
    assert (
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=checkout,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        == ""
    )
    assert not (checkout / ".git" / "objects" / "info" / "alternates").exists()
    assert not hook_marker.exists()
    assert not any(call[:3] == ("worktree", "remove", "--force") for call in git_calls)


def test_provision_trial_graph_runs_mixed_source_and_accepts_clean_graph(
    tmp_path: Path,
) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()

    def write_graph(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        graph = checkout / "graphify-out" / "graph.json"
        graph.parent.mkdir(exist_ok=True)
        graph.write_text(
            json.dumps(
                {
                    "nodes": [
                        {
                            "id": "owner",
                            "source_location": " ".join(
                                (
                                    ".agents/skills/agent-behavior/SKILL.md",
                                    ".agents/references/human_owner_intent.md",
                                    ".omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md",
                                )
                            ),
                        }
                    ],
                    "edges": [],
                }
            ),
            encoding="utf-8",
        )
        stdout = "graphify 0.9.48" if "--version" in command else "built"
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    with (
        patch.object(trials.subprocess, "run", side_effect=write_graph) as run,
        patch.object(trials, "run_git", return_value="") as run_git,
    ):
        trials.provision_trial_graph(checkout)

    expected_command = [
        "graphify",
        "extract",
        ".",
        "--no-cluster",
        "--out",
        ".",
    ]
    assert run.call_args_list[0].args == (expected_command,)
    assert run.call_args_list[1].args == (["graphify", "--version"],)
    run.assert_any_call(
        expected_command,
        cwd=checkout,
        check=False,
        capture_output=True,
        text=True,
    )
    assert not {"--deep", "--mode", "--model", "--semantic"} & set(expected_command)
    run_git.assert_called_once_with(
        "status", "--porcelain", "--untracked-files=no", cwd=checkout
    )


@pytest.mark.parametrize(
    ("graph_case", "reason"),
    [
        ("missing", "regular non-symlink"),
        ("symlink", "regular non-symlink"),
        ("malformed", "unreadable or malformed"),
        ("non-object", "object with nonempty nodes"),
        ("missing-nodes", "object with nonempty nodes"),
        ("empty-nodes", "object with nonempty nodes"),
    ],
)
def test_provision_trial_graph_rejects_invalid_graph(
    tmp_path: Path, graph_case: str, reason: str
) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()

    def write_invalid_graph(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        graph = checkout / "graphify-out" / "graph.json"
        if graph_case != "missing":
            graph.parent.mkdir()
        if graph_case == "symlink":
            target = checkout / "elsewhere.json"
            target.write_text('{"nodes":[{"id":"owner"}]}', encoding="utf-8")
            graph.symlink_to(target)
        elif graph_case == "malformed":
            graph.write_text("{", encoding="utf-8")
        elif graph_case == "non-object":
            graph.write_text("[]", encoding="utf-8")
        elif graph_case == "missing-nodes":
            graph.write_text("{}", encoding="utf-8")
        elif graph_case == "empty-nodes":
            graph.write_text('{"nodes":[]}', encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="built", stderr="")

    with (
        patch.object(trials.subprocess, "run", side_effect=write_invalid_graph),
        patch.object(trials, "run_git", return_value=""),
        pytest.raises(ValueError, match=reason),
    ):
        trials.provision_trial_graph(checkout)


def test_provision_trial_graph_fails_closed_on_nonzero_command(
    tmp_path: Path,
) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    result = subprocess.CompletedProcess([], 7, stdout="partial", stderr="failed")

    with (
        patch.object(trials.subprocess, "run", return_value=result),
        patch.object(trials, "run_git") as run_git,
        pytest.raises(ValueError, match="exit code 7"),
    ):
        trials.provision_trial_graph(checkout)

    run_git.assert_not_called()


def test_provision_trial_graph_rejects_dirty_snapshot(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()

    def write_graph(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        graph = checkout / "graphify-out" / "graph.json"
        graph.parent.mkdir()
        graph.write_text(
            '{"nodes":[{"id":"owner","source_location":".agents/skills/agent-behavior/SKILL.md .agents/references/human_owner_intent.md .omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md"}]}',
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="built", stderr="")

    with (
        patch.object(trials.subprocess, "run", side_effect=write_graph),
        patch.object(trials, "run_git", return_value="?? unexpected.txt"),
        pytest.raises(ValueError, match="dirtied the trial snapshot"),
    ):
        trials.provision_trial_graph(checkout)


def test_provision_trial_graph_rejects_evaluator_fixture_before_command(
    tmp_path: Path,
) -> None:
    checkout = tmp_path / "checkout"
    fixture = checkout / trials.PROMPTS_RELATIVE
    fixture.parent.mkdir(parents=True)
    fixture.write_text('{"id":"hidden"}', encoding="utf-8")

    with (
        patch.object(trials.subprocess, "run") as run,
        pytest.raises(ValueError, match="evaluator fixture remains"),
    ):
        trials.provision_trial_graph(checkout)

    run.assert_not_called()


def test_main_provisions_graph_after_snapshot_before_trials() -> None:
    source = inspect.getsource(trials.main)

    assert source.index("materialize_trial_snapshot(") < source.index("run_trial(")
    assert "provision_trial_graph(" not in source


def test_event_evidence_keeps_commands_tools_paths_and_omits_noise(
    tmp_path: Path,
) -> None:
    events = tmp_path / "events.jsonl"
    records = [
        {
            "type": "item.started",
            "item": {
                "id": "command-1",
                "type": "command_execution",
                "command": "rg -n owner AGENTS.md aria_nbv/AGENTS.md",
                "status": "in_progress",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "command-1",
                "type": "command_execution",
                "command": "rg -n owner AGENTS.md aria_nbv/AGENTS.md",
                "aggregated_output": "unbounded command output",
                "status": "completed",
                "exit_code": 0,
            },
        },
        {
            "type": "item.started",
            "item": {
                "id": "tool-1",
                "type": "mcp_tool_call",
                "tool": "context7_query_docs",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "tool-1",
                "type": "mcp_tool_call",
                "server": "codex_apps",
                "tool": "context7_query_docs",
                "arguments": {"libraryId": "/graphify-labs/graphify"},
                "result": "unbounded tool output",
                "status": "completed",
            },
        },
        {
            "type": "item.started",
            "item": {"id": "message-1", "type": "agent_message"},
        },
        {
            "type": "item.completed",
            "item": {
                "id": "message-1",
                "type": "agent_message",
                "text": "claimed tool call context7_query_docs",
            },
        },
        {
            "type": "turn.completed",
            "usage": {"input_tokens": 1000},
            "input": {"tool": "claimed_context7_call"},
        },
    ]
    lines = [json.dumps(record) for record in records]
    events.write_text("\n".join([lines[0], "{malformed", *lines[1:]]))

    evidence = trials.extract_event_evidence(events)

    assert evidence["malformed_lines"] == 1
    assert evidence["invalid_items"] == 0
    assert len(evidence["items"]) == 2
    command, tool = evidence["items"]
    assert [item["event_index"] for item in evidence["items"]] == [0, 1]
    assert command["command"] == "rg -n owner AGENTS.md aria_nbv/AGENTS.md"
    assert command["status"] == "completed"
    assert command["exit_code"] == 0
    assert all(item["event_type"] == "item.completed" for item in evidence["items"])
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
                lines[3],
            ]
        ),
        encoding="utf-8",
    )
    mixed_evidence = trials.extract_event_evidence(mixed)

    assert len(mixed_evidence["items"]) == 1
    assert mixed_evidence["invalid_items"] == 2
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
            "type": "item.started",
            "item": {
                "id": "command-2",
                "type": "command_execution",
                "command": "rg owner scripts/scaffold",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "command-2",
                "type": "command_execution",
                "command": long_text,
                "status": long_text,
                "arguments": long_text,
                "exit_code": 0,
            },
        },
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
    for field in ("command", "status", "arguments"):
        assert len(evidence["items"][0][field]) == trials.EVENT_EVIDENCE_MAX_FIELD_CHARS
    serialized = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
    assert len(serialized) <= trials.EVENT_EVIDENCE_MAX_TOTAL_CHARS
    assert trials.validate_event_evidence(evidence)[0] is False


def test_event_evidence_accepts_complete_2424_character_command(
    tmp_path: Path,
) -> None:
    events = tmp_path / "events.jsonl"
    command = "x" * 2_424
    events.write_text(
        "\n".join(
            json.dumps(record)
            for record in (
                {
                    "type": "item.started",
                    "item": {
                        "id": "command-1",
                        "type": "command_execution",
                        "command": command,
                    },
                },
                {
                    "type": "item.completed",
                    "item": {
                        "id": "command-1",
                        "type": "command_execution",
                        "command": command,
                        "status": "completed",
                        "exit_code": 0,
                    },
                },
                {"type": "turn.completed"},
            )
        ),
        encoding="utf-8",
    )

    evidence = trials.extract_event_evidence(events)

    assert evidence["items"][0]["command"] == command
    assert evidence["field_truncations"] == 0
    assert trials.validate_event_evidence(evidence) == (
        True,
        "complete raw event evidence",
    )


def test_event_evidence_rejects_command_truncated_above_4096(
    tmp_path: Path,
) -> None:
    events = tmp_path / "events.jsonl"
    command = "x" * (trials.EVENT_EVIDENCE_MAX_FIELD_CHARS + 1)
    events.write_text(
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": command,
                    "status": "completed",
                    "exit_code": 0,
                },
            }
        ),
        encoding="utf-8",
    )

    evidence = trials.extract_event_evidence(events)

    assert len(evidence["items"][0]["command"]) == 4_096
    assert evidence["field_truncations"] == 1
    assert evidence["truncated"] is True
    assert trials.validate_event_evidence(evidence)[0] is False


def test_event_evidence_rejects_oversized_raw_stream(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    events.write_bytes(b"x" * (trials.EVENT_EVIDENCE_MAX_RAW_BYTES + 1))

    evidence = trials.extract_event_evidence(events)

    assert evidence["items"] == []
    assert evidence["dropped_items"] == 1
    assert evidence["truncated"] is True
    assert trials.validate_event_evidence(evidence)[0] is False


@pytest.mark.parametrize(
    "terminal",
    [
        {"type": "turn.failed", "error": "failed"},
        {"type": "error", "message": "failed"},
        None,
    ],
)
def test_event_evidence_rejects_failed_or_missing_terminal_turn(
    tmp_path: Path, terminal: dict[str, object] | None
) -> None:
    records: list[dict[str, object]] = [
        {
            "type": "item.started",
            "item": {"id": "one", "type": "command_execution", "command": "rg owner"},
        },
        {
            "type": "item.completed",
            "item": {
                "id": "one",
                "type": "command_execution",
                "command": "rg owner",
                "status": "completed",
                "exit_code": 0,
            },
        },
    ]
    if terminal is not None:
        records.append(terminal)
    path = tmp_path / "events.jsonl"
    path.write_text(
        "\n".join(json.dumps(record) for record in records), encoding="utf-8"
    )

    valid, reason = trials.validate_event_evidence(trials.extract_event_evidence(path))

    assert valid is False
    assert "lifecycle" in reason


def test_event_evidence_rejects_unmatched_and_duplicate_item_lifecycle(
    tmp_path: Path,
) -> None:
    records = [
        {
            "type": "item.started",
            "item": {"id": "one", "type": "command_execution", "command": "rg owner"},
        },
        {
            "type": "item.started",
            "item": {"id": "one", "type": "command_execution", "command": "rg owner"},
        },
        {"type": "turn.completed"},
    ]
    path = tmp_path / "events.jsonl"
    path.write_text(
        "\n".join(json.dumps(record) for record in records), encoding="utf-8"
    )
    evidence = trials.extract_event_evidence(path)

    assert evidence["lifecycle"]["duplicate_starts"] == 1
    assert evidence["lifecycle"]["unmatched_starts"] == 1
    assert trials.validate_event_evidence(evidence)[0] is False


def test_bundle_manifest_excludes_mutable_index_and_attests_raw_artifacts(
    tmp_path: Path,
) -> None:
    (tmp_path / "trial").mkdir()
    (tmp_path / "trial" / "events.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "index.json").write_text("{}\n", encoding="utf-8")

    receipt = trials._write_bundle_manifest(tmp_path)
    manifest = json.loads((tmp_path / receipt["path"]).read_text(encoding="utf-8"))

    assert "trial/events.jsonl" in manifest["files"]
    assert "index.json" not in manifest["files"]
    assert receipt["sha256"] == trials._sha256_file(tmp_path / receipt["path"])


def test_event_evidence_parses_complete_stream_past_old_raw_bound(
    tmp_path: Path,
) -> None:
    events = tmp_path / "events.jsonl"
    records = [
        {
            "type": "item.started",
            "item": {
                "id": "command-1",
                "type": "command_execution",
                "command": "rg owner AGENTS.md --before-context 2",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "command-1",
                "type": "command_execution",
                "command": "rg owner AGENTS.md --before-context 2",
                "status": "completed",
                "exit_code": 0,
            },
        },
        {
            "type": "diagnostic",
            "aggregated_output": "x" * 70_000,
            "usage": {"input_tokens": 1000},
        },
        {
            "type": "item.started",
            "item": {
                "id": "command-2",
                "type": "command_execution",
                "command": "rg owner scripts/scaffold",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "command-2",
                "type": "command_execution",
                "command": "rg owner scripts/scaffold",
                "status": "completed",
                "exit_code": 0,
            },
        },
        {
            "type": "diagnostic",
            "aggregated_output": "y" * 70_000,
            "usage": {"input_tokens": 2000},
        },
        {
            "type": "turn.completed",
            "aggregated_output": "z" * 70_000,
            "usage": {"input_tokens": 3000},
        },
    ]
    events.write_text("\n".join(json.dumps(record) for record in records) + "\n")

    evidence = trials.extract_event_evidence(events)

    assert events.stat().st_size > 131_072
    assert events.stat().st_size <= trials.EVENT_EVIDENCE_MAX_RAW_BYTES
    assert [item["command"] for item in evidence["items"]] == [
        "rg owner AGENTS.md --before-context 2",
        "rg owner scripts/scaffold",
    ]
    assert evidence["dropped_items"] == 0
    assert evidence["truncated"] is False
    assert trials.validate_event_evidence(evidence)[0] is True


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


def test_verifier_prompt_defines_event_index_sequence() -> None:
    prompt = trials.build_verifier_prompt(
        rubric={"id": "trial"}, report=_trial_report(), rubric_commit="rubric"
    )

    instruction = json.loads(prompt)["instruction"]
    assert "copy the exact event_index from the retained item" in instruction
    assert "bounded_trial_evidence.event_evidence.items" in instruction
    assert "named real" in trials.TRIAL_EXECUTION_PROTOCOL
    assert "precise scoped decision" in trials.TRIAL_EXECUTION_PROTOCOL
    assert "Checkout mutation is forbidden" in instruction
    assert "clean checkout is required" in instruction


def test_run_trial_hashes_the_protocol_augmented_prompt(tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_run(*args: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return type("Result", (), {"returncode": 0})()

    with (
        patch.object(trials, "run_git", return_value=""),
        patch.object(trials.subprocess, "run", side_effect=fake_run),
    ):
        report = trials.run_trial(
            trial_id="trial",
            task="Choose the owner.",
            head="tested",
            rubric_commit="rubric",
            checkout=tmp_path / "checkout",
            output_dir=tmp_path / "output",
            codex_version="codex test",
            model=None,
            effort=None,
            timeout_seconds=1,
            checkout_digest_expected=trials._checkout_digest(tmp_path / "checkout"),
        )

    executed_prompt = captured["input"]
    assert executed_prompt == trials.build_trial_prompt("Choose the owner.")
    assert (
        report["prompt_sha256"] == hashlib.sha256(executed_prompt.encode()).hexdigest()
    )


def test_synthetic_event_evidence_uses_completed_ordinals_and_stays_bounded(
    tmp_path: Path,
) -> None:
    events = tmp_path / "events.jsonl"
    records: list[dict[str, object]] = []
    for ordinal in range(9):
        records.extend(
            [
                {
                    "type": "item.started",
                    "item": {
                        "id": f"command-{ordinal}",
                        "type": "command_execution",
                        "command": f"started-{ordinal}",
                    },
                },
                {
                    "type": "item.completed",
                    "item": {
                        "id": f"command-{ordinal}",
                        "type": "command_execution",
                        "command": f"completed-{ordinal}",
                        "status": "completed",
                        "exit_code": 0,
                    },
                },
            ]
        )
    records.append({"type": "turn.completed"})
    events.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8"
    )

    evidence = trials.extract_event_evidence(events)
    assert [item["command"] for item in evidence["items"]] == [
        f"completed-{ordinal}" for ordinal in range(9)
    ]
    assert [item["event_index"] for item in evidence["items"]] == list(range(9))
    verdict = _verdict(
        evidence=[
            _event_reference(event_index=4, claim="completed ordinal four"),
            _event_reference(event_index=8, claim="completed ordinal eight"),
        ]
    )
    assert trials.validate_event_evidence(evidence) == (
        True,
        "complete raw event evidence",
    )
    assert _validate_verdict(verdict, evidence) == (True, "pass")

    bounded_records = [
        {
            "type": "item.started",
            "item": {
                "type": "command_execution",
                "command": f"started-only-{ordinal}",
            },
        }
        for ordinal in range(65)
    ]
    bounded_records.extend(
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": f"completed-{ordinal}",
                "status": "completed",
                "exit_code": 0,
            },
        }
        for ordinal in range(64)
    )
    bounded_events = tmp_path / "bounded-events.jsonl"
    bounded_events.write_text(
        "\n".join(json.dumps(record) for record in bounded_records) + "\n",
        encoding="utf-8",
    )
    bounded_evidence = trials.extract_event_evidence(bounded_events)
    assert len(bounded_records) > trials.EVENT_EVIDENCE_MAX_ITEMS
    assert len(bounded_evidence["items"]) == trials.EVENT_EVIDENCE_MAX_ITEMS
    assert [item["event_index"] for item in bounded_evidence["items"]] == list(
        range(trials.EVENT_EVIDENCE_MAX_ITEMS)
    )
    assert trials.validate_event_evidence(bounded_evidence)[0] is False
    assert bounded_evidence["invalid_items"] > 0


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
        _verdict(forbidden_observations=["x" * (trials.VERDICT_MAX_FIELD_CHARS + 1)]),
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


@pytest.mark.parametrize("event_index", [True, "0", 1.0, 1, -1])
def test_event_evidence_rejects_invalid_or_mismatched_event_index(
    event_index: object,
) -> None:
    evidence = _complete_event_evidence()
    evidence["items"][0]["event_index"] = event_index  # type: ignore[index]
    evidence["payload_chars"] = len(
        json.dumps(evidence["items"], sort_keys=True, separators=(",", ":"))
    )

    assert trials.validate_event_evidence(evidence)[0] is False


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


def test_aggregate_rejects_clean_trial_with_failing_adjudication() -> None:
    report = {
        "returncode": 0,
        "checkout_clean_after": True,
        "adjudication": {"passed": False, "reason": "semantic fail"},
    }
    assert trials.trial_passed(report) is False
    report["adjudication"] = {"passed": True, "reason": "pass"}
    assert trials.trial_passed(report) is False


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
