from __future__ import annotations

import contextlib
import importlib
import json
import shutil
import subprocess
import sys
import time
from io import BytesIO
from itertools import pairwise
from pathlib import Path
from threading import Event, Lock
from typing import Any
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
ROUTING_PROXY_URL = "http://127.0.0.1:43123/v1"
sys.path.insert(0, str(ROOT / "scripts" / "scaffold"))
trials = importlib.import_module("run_routing_trials")


def _submission_gate_diagnostic() -> bytes:
    return (
        f"{trials.SUBMISSION_GATE_DIAGNOSTIC}\n"
        f"   ┌─ {trials.SUBMISSION_GATE_SOURCE}45:4\n"
    ).encode()


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


def _run_verifier(report: dict[str, object], trial_dir: Path) -> dict[str, Any]:
    # Unit tests mock process execution. Supply a stable mounted executable so
    # command construction stays portable on CI runners without Codex.
    real_which = trials.shutil.which
    broker_socket = trial_dir / "broker" / "proxy.sock"
    broker_socket.parent.mkdir(exist_ok=True)
    with (
        patch.object(
            trials.shutil,
            "which",
            side_effect=lambda name: (
                "/usr/bin/true" if name == "codex" else real_which(name)
            ),
        ),
        patch.object(
            trials,
            "broker_socket_relay",
            return_value=contextlib.nullcontext(broker_socket),
        ),
    ):
        return trials.run_verifier(
            report=report,
            rubric={"trial": {"id": "trial"}},
            rubric_commit="rubric",
            trial_dir=trial_dir,
            model=None,
            effort=None,
            proxy_url=ROUTING_PROXY_URL,
            timeout_seconds=1,
        )


def _bounded_process_result(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "returncode": 0,
        "timed_out": False,
        "output_overflow": False,
        "launch_error": False,
        "stream_capture": {
            "events": {
                "observed_bytes": 0,
                "maximum_bytes": trials.EVENT_EVIDENCE_MAX_RAW_STREAM_BYTES,
                "overflowed": False,
            },
            "stderr": {
                "observed_bytes": 0,
                "maximum_bytes": trials.TRIAL_STDERR_MAX_BYTES,
                "overflowed": False,
            },
        },
    }
    result.update(overrides)
    return result


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
            "baseline_head": "baseline",
            "head_after": "baseline",
            "required_changed_path_prefixes": [],
            "required_changed_paths": [],
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
        "trial_response_valid": True,
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
        "literature-research-source-screening",
        "literature-research-current-typst-api-near-miss",
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
        assert any(
            "compile and affected-page render proof" in outcome for outcome in required
        )


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


def test_verifier_process_receipt_fails_closed_on_output_overflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeProcess:
        def __init__(self) -> None:
            self.stdin = BytesIO()
            self.stdout = BytesIO(b"overflow")
            self.stderr = BytesIO()
            self.returncode = 0

        def wait(self, timeout: int | None = None) -> int:
            return self.returncode

        def poll(self) -> int:
            return self.returncode

        def terminate(self) -> None:
            self.returncode = 125

    monkeypatch.setattr(trials, "EVENT_EVIDENCE_MAX_RAW_STREAM_BYTES", 4)
    monkeypatch.setattr(trials, "TRIAL_STDERR_MAX_BYTES", 4)
    with patch.object(trials.subprocess, "Popen", return_value=FakeProcess()):
        result = trials._run_bounded_process(
            command=["codex", "exec"],
            prompt="route",
            cwd=tmp_path,
            events_path=tmp_path / "events.jsonl",
            stderr_path=tmp_path / "stderr.txt",
            timeout_seconds=1,
        )

    assert result["output_overflow"] is True
    assert result["stream_capture"]["events"]["overflowed"] is True  # type: ignore[index]


def test_bounded_process_kills_a_term_resistant_process_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(trials, "PROCESS_TERMINATE_GRACE_SECONDS", 0.1)
    started = time.monotonic()
    result = trials._run_bounded_process(
        command=["/bin/sh", "-c", "trap '' TERM; while :; do sleep 1; done"],
        prompt="",
        cwd=tmp_path,
        events_path=tmp_path / "events.jsonl",
        stderr_path=tmp_path / "stderr.txt",
        timeout_seconds=0.1,
    )

    assert result["timed_out"] is True
    assert result["returncode"] == 124
    assert time.monotonic() - started < 2


def test_bounded_process_stops_a_child_when_stdin_setup_fails(
    tmp_path: Path,
) -> None:
    class BrokenStdin(BytesIO):
        def write(self, data: bytes) -> int:
            raise BrokenPipeError

    class FakeProcess:
        def __init__(self) -> None:
            self.stdin = BrokenStdin()
            self.stdout = BytesIO()
            self.stderr = BytesIO()
            self.pid = 999_999
            self.returncode: int | None = None
            self.terminated = False

        def poll(self) -> int | None:
            return self.returncode

        def terminate(self) -> None:
            self.terminated = True
            self.returncode = 125

        def wait(self, timeout: int | None = None) -> int:
            assert self.returncode is not None
            return self.returncode

    process = FakeProcess()
    with patch.object(trials.subprocess, "Popen", return_value=process):
        result = trials._run_bounded_process(
            command=["codex", "exec"],
            prompt="route",
            cwd=tmp_path,
            events_path=tmp_path / "events.jsonl",
            stderr_path=tmp_path / "stderr.txt",
            timeout_seconds=1,
        )

    assert result["launch_error"] is True
    assert process.terminated is True


def test_codex_command_is_ephemeral_read_only_and_prompt_free(tmp_path: Path) -> None:
    command = trials._build_codex_command(
        checkout=tmp_path,
        output_schema=trials.REPORT_SCHEMA,
        model="test-model",
        effort="high",
        proxy_url=ROUTING_PROXY_URL,
    )
    assert "--ephemeral" in command
    assert "--ignore-user-config" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert command[command.index("--output-schema") + 1] == str(trials.REPORT_SCHEMA)
    assert command[-1] == "-"
    assert "expected_owner_paths" not in " ".join(command)
    provider_config = next(
        value
        for flag, value in pairwise(command)
        if flag == "-c" and "model_providers." in value
    )
    assert ROUTING_PROXY_URL in provider_config
    assert "requires_openai_auth=false" in provider_config


@pytest.mark.parametrize(
    "value",
    (
        "https://127.0.0.1:43123/v1",
        "http://localhost:43123/v1",
        "http://127.0.0.1:43123/v1?token=unsafe",
        "http://127.0.0.1/v1",
        'http://127.0.0.1:43123/v1"\nmodel_provider="unsafe',
    ),
)
def test_routing_trial_proxy_rejects_nonlocal_or_credential_urls(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(trials.ROUTING_TRIAL_PROXY_URL_ENV, value)

    with pytest.raises(ValueError, match="proxy URL"):
        trials.routing_trial_proxy_url()


def test_routing_trial_proxy_accepts_local_unauthenticated_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(trials.ROUTING_TRIAL_PROXY_URL_ENV, ROUTING_PROXY_URL)

    assert trials.routing_trial_proxy_url() == ROUTING_PROXY_URL


def test_routing_trial_proxy_is_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(trials.ROUTING_TRIAL_PROXY_URL_ENV, raising=False)

    with pytest.raises(ValueError, match=trials.ROUTING_TRIAL_PROXY_URL_ENV):
        trials.routing_trial_proxy_url()


def test_broker_socket_relay_fails_closed_without_socat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_which = trials.shutil.which
    monkeypatch.setattr(
        trials.shutil,
        "which",
        lambda name: None if name == "socat" else real_which(name),
    )

    with (
        pytest.raises(RuntimeError, match="require socat"),
        trials.broker_socket_relay(ROUTING_PROXY_URL),
    ):
        pass


def test_subject_sandbox_mounts_only_the_canonical_schema(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    command = trials._sandboxed_codex_command(
        # This is a portable command-shape test.  The Codex runtime mount has
        # its own Bubblewrap integration coverage below when both tools exist.
        codex_command=["/usr/bin/true"],
        checkout=checkout,
        broker_socket=tmp_path / "proxy.sock",
        schema_path=trials.REPORT_SCHEMA,
        sandbox=trials.READ_ONLY_SANDBOX,
    )

    assert str(trials.REPORT_SCHEMA) in command
    assert "/schema/routing_trial_report.schema.json" in command
    assert "/receipt" not in command
    assert "/codex-home/auth.json" not in command


@pytest.mark.skipif(shutil.which("bwrap") is None, reason="Bubblewrap is unavailable")
def test_subject_sandbox_hides_the_evaluator_root(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    evaluator_fixture = ROOT / trials.RUBRIC_RELATIVE
    command = trials._sandboxed_codex_command(
        codex_command=["/usr/bin/test", "!", "-e", str(evaluator_fixture)],
        checkout=checkout,
        broker_socket=tmp_path / "proxy.sock",
        schema_path=trials.REPORT_SCHEMA,
        sandbox=trials.READ_ONLY_SANDBOX,
    )
    subprocess.run(command, check=True)


@pytest.mark.skipif(shutil.which("bwrap") is None, reason="Bubblewrap is unavailable")
@pytest.mark.parametrize(
    ("schema_path", "sandbox_path"),
    (
        (trials.REPORT_SCHEMA, "/schema/routing_trial_report.schema.json"),
        (trials.VERIFIER_SCHEMA, "/schema/routing_verdict.schema.json"),
    ),
)
def test_subject_sandbox_mounts_each_schema_at_its_declared_path(
    tmp_path: Path, schema_path: Path, sandbox_path: str
) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    command = trials._sandboxed_codex_command(
        codex_command=["/usr/bin/test", "-f", sandbox_path],
        checkout=checkout,
        broker_socket=tmp_path / "proxy.sock",
        schema_path=schema_path,
        sandbox=trials.READ_ONLY_SANDBOX,
    )

    subprocess.run(command, check=True)


@pytest.mark.skipif(shutil.which("bwrap") is None, reason="Bubblewrap is unavailable")
def test_subject_sandbox_does_not_expose_codex_auth(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    command = trials._sandboxed_codex_command(
        codex_command=["/usr/bin/test", "!", "-e", "/codex-home/auth.json"],
        checkout=checkout,
        broker_socket=tmp_path / "proxy.sock",
        schema_path=trials.REPORT_SCHEMA,
        sandbox=trials.READ_ONLY_SANDBOX,
    )

    subprocess.run(command, check=True)


@pytest.mark.skipif(shutil.which("bwrap") is None, reason="Bubblewrap is unavailable")
def test_subject_sandbox_can_execute_codex_binary(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    command = trials._sandboxed_codex_command(
        codex_command=["codex", "--version"],
        checkout=checkout,
        broker_socket=tmp_path / "proxy.sock",
        schema_path=trials.REPORT_SCHEMA,
        sandbox=trials.READ_ONLY_SANDBOX,
    )

    sandboxed = subprocess.run(command, check=True, capture_output=True, text=True)
    host_version = subprocess.run(
        ["codex", "--version"], check=True, capture_output=True, text=True
    )

    assert sandboxed.stdout == host_version.stdout


def test_subject_sandbox_binds_only_the_resolved_codex_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home_bin = tmp_path / "home" / "bin"
    home_bin.mkdir(parents=True)
    executable = home_bin / "codex"
    executable.write_text("placeholder", encoding="utf-8")
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    monkeypatch.setattr(trials.shutil, "which", lambda name: str(executable))

    command = trials._sandboxed_codex_command(
        codex_command=["codex", "--version"],
        checkout=checkout,
        broker_socket=tmp_path / "proxy.sock",
        schema_path=trials.REPORT_SCHEMA,
        sandbox=trials.READ_ONLY_SANDBOX,
    )

    target_index = command.index("/opt/codex/codex")
    assert command[target_index - 1] == str(executable.resolve())
    assert command[target_index - 1] != str(home_bin.parent)


@pytest.mark.skipif(shutil.which("bwrap") is None, reason="Bubblewrap is unavailable")
def test_workspace_write_sandbox_keeps_git_index_read_only(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / "protected.txt").write_text("protected", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=checkout, check=True)
    subprocess.run(["git", "add", "protected.txt"], cwd=checkout, check=True)
    command = trials._sandboxed_codex_command(
        codex_command=[
            "/bin/sh",
            "-ec",
            "! git update-index --assume-unchanged protected.txt",
        ],
        checkout=checkout,
        broker_socket=tmp_path / "proxy.sock",
        schema_path=trials.REPORT_SCHEMA,
        sandbox=trials.WORKSPACE_WRITE_SANDBOX,
    )

    subprocess.run(command, check=True)

    assert subprocess.run(
        ["git", "ls-files", "-v", "protected.txt"],
        cwd=checkout,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.startswith("H ")


def test_event_receipt_requires_a_completed_agent_message(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    events.write_text(
        "\n".join(
            json.dumps(event)
            for event in (
                {
                    "type": "item.started",
                    "item": {"type": "agent_message", "text": "{}"},
                },
                {"type": "turn.completed"},
            )
        )
        + "\n",
        encoding="utf-8",
    )

    assert trials.read_last_agent_message(events) == (None, False)


def test_workspace_write_contract_requires_source_change_and_typst_proof() -> None:
    contract = trials.execution_contract(
        {
            "execution_mode": trials.WORKSPACE_WRITE_SANDBOX,
            "required_changed_path_prefixes": ["docs/typst/thesis/"],
            "typst_proof": True,
        }
    )
    assert contract["sandbox"] == trials.WORKSPACE_WRITE_SANDBOX
    with pytest.raises(
        ValueError, match="require active-source prefixes and Typst proof"
    ):
        trials.execution_contract({"execution_mode": trials.WORKSPACE_WRITE_SANDBOX})


def test_subject_checkout_removes_evaluator_fixtures_and_history(
    tmp_path: Path,
) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / "README.md").write_text("subject\n", encoding="utf-8")
    for relative_path in trials.EVALUATOR_FIXTURE_PATHS:
        path = checkout / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("evaluator\n", encoding="utf-8")
    (checkout / "scripts" / "tests").mkdir(parents=True)
    (checkout / "scripts" / "tests" / "routing.py").write_text(
        "evaluator\n", encoding="utf-8"
    )
    (checkout / ".agents" / "memory").mkdir(parents=True)
    (checkout / ".agents" / "memory" / "debrief.md").write_text(
        "evaluator\n", encoding="utf-8"
    )
    (checkout / ".omx").mkdir()
    (checkout / ".omx" / "review.md").write_text("evaluator\n", encoding="utf-8")
    (checkout / ".git").write_text("gitdir: ignored\n", encoding="utf-8")

    trials.prepare_subject_checkout(checkout)

    for relative_path in trials.EVALUATOR_EXCLUDED_PATHS:
        assert not (checkout / relative_path).exists()
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
    sibling = tmp_path / "sibling"
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
    (repository / ".gitignore").write_text(".ignored/\n", encoding="utf-8")
    subprocess.run(["git", "add", "--all"], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "subject"], cwd=repository, check=True)
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(checkout), "HEAD"],
        cwd=repository,
        check=True,
    )
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(sibling), "HEAD"],
        cwd=repository,
        check=True,
    )

    registration = trials._subject_worktree_admin_dir(checkout)
    trials.prepare_subject_checkout(checkout)
    baseline = trials.run_git("rev-parse", "HEAD", cwd=checkout)
    untracked = checkout / "docs" / "typst" / "thesis" / "untracked.typ"
    untracked.parent.mkdir(parents=True)
    untracked.write_text("#let proof = true\n", encoding="utf-8")
    assert untracked.relative_to(checkout).as_posix() in trials._changed_paths(
        checkout, baseline
    )
    ignored = checkout / ".ignored" / "trial.txt"
    ignored.parent.mkdir()
    ignored.write_text("ignored\n", encoding="utf-8")
    assert ignored.relative_to(checkout).as_posix() in trials._changed_paths(
        checkout, baseline
    )
    subprocess.run(["git", "add", "--all"], cwd=checkout, check=True)
    subprocess.run(["git", "commit", "-qm", "trial write"], cwd=checkout, check=True)
    assert untracked.relative_to(checkout).as_posix() in trials._changed_paths(
        checkout, baseline
    )
    trials.remove_subject_checkout(
        checkout,
        subject_root=tmp_path,
        worktree_admin_dir=registration,
        repository=repository,
    )

    assert not checkout.exists()
    registered = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert str(checkout) not in registered
    assert str(sibling) in registered
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(sibling)],
        cwd=repository,
        check=True,
    )


def test_subject_cleanup_rejects_a_path_outside_its_temporary_root(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="escapes its temporary directory"):
        trials.remove_subject_checkout(
            tmp_path / "outside",
            subject_root=tmp_path / "subjects",
            worktree_admin_dir=tmp_path / "registration",
            repository=tmp_path,
        )


def test_editable_trial_requires_changed_source_and_passing_proof() -> None:
    report = _trial_report()
    report["execution"] = {
        "sandbox": trials.WORKSPACE_WRITE_SANDBOX,
        "baseline_head": "baseline",
        "head_after": "baseline",
        "required_changed_path_prefixes": ["docs/typst/thesis/"],
        "required_changed_paths": [],
        "changed_paths": ["docs/typst/thesis/section.typ"],
        "final_diff": {"valid": True, "content": "diff --git a/main.typ b/main.typ"},
        "typst_proof": {"passed": True},
    }
    report["adjudication"] = {"passed": True}
    assert trials.trial_passed(report)
    report["execution"]["typst_proof"] = {"passed": False}  # type: ignore[index]
    assert not trials.trial_passed(report)


def test_editable_trial_requires_each_declared_exact_changed_path() -> None:
    report = _trial_report()
    report["execution"] = {
        "sandbox": trials.WORKSPACE_WRITE_SANDBOX,
        "baseline_head": "baseline",
        "head_after": "baseline",
        "required_changed_path_prefixes": ["docs/typst/thesis/"],
        "required_changed_paths": ["docs/typst/thesis/main.typ"],
        "changed_paths": ["docs/typst/thesis/section.typ"],
        "final_diff": {"valid": True, "content": "diff --git a/main.typ b/main.typ"},
        "typst_proof": {"passed": True},
    }
    report["adjudication"] = {"passed": True}

    assert not trials.trial_passed(report)
    report["execution"]["changed_paths"].append(  # type: ignore[index]
        "docs/typst/thesis/main.typ"
    )
    assert trials.trial_passed(report)


def test_every_workspace_write_fixture_can_satisfy_its_terminal_contract() -> None:
    for trial_id, rubric in trials.load_rubric().items():
        contract = trials.execution_contract(rubric)
        if contract["sandbox"] != trials.WORKSPACE_WRITE_SANDBOX:
            continue
        changed_paths = {
            f"{prefix}fixture.typ"
            for prefix in contract["required_changed_path_prefixes"]
        }
        changed_paths.update(contract["required_changed_paths"])
        report = _trial_report()
        report["execution"] = {
            **contract,
            "baseline_head": "baseline",
            "head_after": "baseline",
            "changed_paths": sorted(changed_paths),
            "final_diff": {
                "valid": True,
                "content": "diff --git a/fixture.typ b/fixture.typ",
            },
            "typst_proof": {"passed": True},
        }
        report["adjudication"] = {"passed": True}

        assert trials.trial_passed(report), trial_id


def test_final_diff_evidence_is_host_generated_and_bounded(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    trial_dir = tmp_path / "trial"
    source = checkout / "docs" / "typst" / "thesis" / "section.typ"
    source.parent.mkdir(parents=True)
    source.write_text("before\n", encoding="utf-8")
    trial_dir.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=checkout, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=checkout,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=checkout, check=True)
    subprocess.run(["git", "add", "--all"], cwd=checkout, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=checkout, check=True)
    baseline = trials.run_git("rev-parse", "HEAD", cwd=checkout)
    source.write_text("after\n", encoding="utf-8")

    evidence = trials._final_diff_evidence(
        checkout,
        baseline,
        ("docs/typst/thesis/section.typ",),
        trial_dir,
    )

    assert evidence["valid"] is True
    assert "-before" in evidence["content"]
    assert "+after" in evidence["content"]
    assert len(evidence["content"].encode()) <= trials.FINAL_DIFF_MAX_BYTES


def test_trial_rejects_committed_or_out_of_scope_workspace_changes() -> None:
    report = _trial_report()
    report["execution"] = {
        "sandbox": trials.WORKSPACE_WRITE_SANDBOX,
        "baseline_head": "baseline",
        "head_after": "baseline",
        "required_changed_path_prefixes": ["docs/typst/thesis/"],
        "required_changed_paths": ["docs/typst/thesis/main.typ"],
        "changed_paths": ["docs/typst/thesis/main.typ"],
        "final_diff": {"valid": True, "content": "diff --git a/main.typ b/main.typ"},
        "typst_proof": {"passed": True},
    }
    report["adjudication"] = {"passed": True}
    assert trials.trial_passed(report)
    report["execution"]["head_after"] = "committed"  # type: ignore[index]
    assert not trials.trial_passed(report)
    report["execution"]["head_after"] = "baseline"  # type: ignore[index]
    report["execution"]["changed_paths"].append("notes.txt")  # type: ignore[index]
    assert not trials.trial_passed(report)


def test_typst_proof_renders_every_page_and_requires_png(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    trial_dir = tmp_path / "trial"
    checkout.mkdir()
    trial_dir.mkdir()
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[0] == "bwrap" and "compile" in command:
            (trial_dir / "thesis.pdf").write_bytes(b"pdf")
        elif command[0] == "pdfinfo":
            return subprocess.CompletedProcess(command, 0, stdout="Pages: 2\n")
        else:
            pages = trial_dir / "thesis-pages"
            pages.mkdir()
            (pages / "01.png").write_bytes(b"png")
            (pages / "02.png").write_bytes(b"png")
        return subprocess.CompletedProcess(command, 0)

    def fake_gate(**kwargs: object) -> dict[str, object]:
        command = kwargs["command"]
        stderr_path = kwargs["stderr_path"]
        assert isinstance(command, list)
        assert isinstance(stderr_path, Path)
        calls.append(command)
        stderr_path.write_bytes(_submission_gate_diagnostic())
        return {
            "returncode": 1,
            "timed_out": False,
            "output_overflow": False,
            "launch_error": False,
        }

    with (
        patch.object(trials.subprocess, "run", side_effect=fake_run),
        patch.object(trials, "_run_bounded_process", side_effect=fake_gate),
    ):
        proof = trials._typst_proof(checkout, trial_dir)

    assert proof["passed"] is True
    assert proof["artifacts"]["page_count"] == 2
    assert proof["artifacts"]["rendered_pages"] == ("01.png", "02.png")
    assert proof["submission_gate_returncode"] == 1
    assert proof["submission_gate"] == {
        "executed": True,
        "returncode": 1,
        "expected_diagnostic": True,
    }
    assert "--pages" not in calls[1]
    assert "aria-thesis-mode=submission" in calls[2]
    assert calls[0][0] == "bwrap"
    assert "--unshare-all" in calls[0]
    assert "--share-net" not in calls[0]


def test_typst_proof_does_not_render_when_compilation_fails(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    trial_dir = tmp_path / "trial"
    (checkout / "docs").mkdir(parents=True)
    trial_dir.mkdir()
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 1)

    with patch.object(trials.subprocess, "run", side_effect=fake_run):
        proof = trials._typst_proof(checkout, trial_dir)

    assert proof["passed"] is False
    assert proof["returncodes"] == [1]
    assert len(calls) == 1


@pytest.mark.parametrize(
    "gate_result, diagnostic",
    (
        (
            {
                "returncode": 124,
                "timed_out": True,
                "output_overflow": False,
                "launch_error": False,
            },
            _submission_gate_diagnostic(),
        ),
        (
            {
                "returncode": 1,
                "timed_out": False,
                "output_overflow": False,
                "launch_error": False,
            },
            (
                b"unrelated candidate failure: "
                + trials.SUBMISSION_GATE_DIAGNOSTIC.encode("utf-8")
            ),
        ),
        (
            {
                "returncode": 1,
                "timed_out": False,
                "output_overflow": False,
                "launch_error": False,
            },
            b"\xff" + _submission_gate_diagnostic(),
        ),
    ),
)
def test_typst_proof_requires_an_executed_expected_submission_gate(
    tmp_path: Path, gate_result: dict[str, object], diagnostic: bytes
) -> None:
    checkout = tmp_path / "checkout"
    trial_dir = tmp_path / "trial"
    checkout.mkdir()
    trial_dir.mkdir()

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        if command[0] == "bwrap" and "compile" in command:
            (trial_dir / "thesis.pdf").write_bytes(b"pdf")
        elif command[0] == "pdfinfo":
            return subprocess.CompletedProcess(command, 0, stdout="Pages: 1\n")
        else:
            pages = trial_dir / "thesis-pages"
            pages.mkdir(exist_ok=True)
            (pages / "01.png").write_bytes(b"png")
        return subprocess.CompletedProcess(command, 0)

    def fake_gate(**kwargs: object) -> dict[str, object]:
        stderr_path = kwargs["stderr_path"]
        assert isinstance(stderr_path, Path)
        stderr_path.write_bytes(diagnostic)
        return gate_result

    with (
        patch.object(trials.subprocess, "run", side_effect=fake_run),
        patch.object(trials, "_run_bounded_process", side_effect=fake_gate),
    ):
        proof = trials._typst_proof(checkout, trial_dir)

    assert proof["passed"] is False


@pytest.mark.skipif(
    shutil.which("bwrap") is None
    or shutil.which("typst") is None
    or shutil.which("pdfinfo") is None,
    reason="Bubblewrap, Typst, or Poppler is unavailable",
)
def test_typst_proof_executes_in_its_isolated_runtime(tmp_path: Path) -> None:
    proof = trials._typst_proof(ROOT, tmp_path)

    assert proof["passed"] is True


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
    assert len(evidence_item["oneOf"]) == 2
    assert set(evidence_item["oneOf"][0]["required"]) == {
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
    for relative_path in trials.EVALUATOR_FIXTURE_PATHS:
        if relative_path in {trials.PROMPTS_RELATIVE, trials.RUBRIC_RELATIVE}:
            continue
        path = repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8")
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

    trusted_renderer = repo / trials.TRUSTED_RENDER_SCRIPT_RELATIVE
    trusted_renderer.write_text("different renderer\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", str(trials.TRUSTED_RENDER_SCRIPT_RELATIVE)],
        cwd=repo,
        check=True,
    )
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

    unknown = tmp_path / "unknown.jsonl"
    unknown.write_text(
        json.dumps(
            {
                "type": "item.completed",
                "item": {"type": "future_tool", "operation": "new"},
            }
        ),
        encoding="utf-8",
    )

    unknown_evidence = trials.extract_event_evidence(unknown)
    assert unknown_evidence["invalid_items"] == 1
    assert not trials.validate_event_evidence(unknown_evidence)[0]

    protocol_drift = tmp_path / "protocol-drift.jsonl"
    protocol_drift.write_text(
        "\n".join(
            json.dumps(event)
            for event in (
                {
                    "type": "item.started",
                    "item": {
                        "type": "command_execution",
                        "command": "rg owner AGENTS.md",
                    },
                },
                {
                    "type": "item.completed",
                    "item": {"type": "future_tool", "name": "new-tool"},
                },
            )
        ),
        encoding="utf-8",
    )

    drift_evidence = trials.extract_event_evidence(protocol_drift)
    assert drift_evidence["items"] == []
    assert drift_evidence["invalid_items"] == 2
    assert not trials.validate_event_evidence(drift_evidence)[0]


def test_event_evidence_bounds_all_fields_and_fails_closed_when_truncated(
    tmp_path: Path,
) -> None:
    events = tmp_path / "events.jsonl"
    long_text = "x" * (trials.EVENT_EVIDENCE_MAX_FIELD_CHARS * 2)
    records = [
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
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
    assert evidence["field_truncations"] == 1
    assert evidence["dropped_items"] > 0
    assert evidence["truncated"] is True
    assert len(evidence["items"][0]["command"]) == trials.EVENT_EVIDENCE_MAX_FIELD_CHARS
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


def test_event_receipt_requires_a_terminal_turn(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    events.write_text(
        json.dumps(
            {"type": "item.completed", "item": {"type": "agent_message", "text": "{}"}}
        )
        + "\n",
        encoding="utf-8",
    )

    assert trials.read_last_agent_message(events) == (None, False)


@pytest.mark.parametrize(
    "activity",
    ("command_execution", "web_search", "file_change", "reasoning", "todo_list"),
)
def test_event_receipt_rejects_tool_activity_after_final_message(
    tmp_path: Path, activity: str
) -> None:
    events = tmp_path / "events.jsonl"
    events.write_text(
        "\n".join(
            json.dumps(event)
            for event in (
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": "{}"},
                },
                {
                    "type": "item.completed",
                    "item": {"type": activity, "command": "touch later"},
                },
                {"type": "turn.completed"},
            )
        )
        + "\n",
        encoding="utf-8",
    )

    assert trials.read_last_agent_message(events) == (None, False)


@pytest.mark.parametrize("late_event", ({"type": "error"}, {"type": "turn.started"}))
def test_event_receipt_rejects_late_top_level_activity(
    tmp_path: Path, late_event: dict[str, str]
) -> None:
    events = tmp_path / "events.jsonl"
    events.write_text(
        "\n".join(
            json.dumps(event)
            for event in (
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": "{}"},
                },
                late_event,
                {"type": "turn.completed"},
            )
        )
        + "\n",
        encoding="utf-8",
    )

    assert trials.read_last_agent_message(events) == (None, False)


def test_trial_response_validation_requires_the_canonical_schema() -> None:
    valid = {
        "loaded_guides": [".agents/skills/agent-behavior/SKILL.md"],
        "selected_skill": "agent-behavior",
        "opened_references": [],
        "tool_calls": [],
        "exact_owner": ".agents/skills/agent-behavior/SKILL.md",
        "handoff": None,
        "selected_verification": "pytest -q",
        "outcome": "complete",
    }
    assert trials.validate_trial_response(valid)
    assert not trials.validate_trial_response({**valid, "unexpected": "receipt"})
    assert not trials.validate_trial_response(valid, truncated=True)


def test_verifier_rejects_an_invalid_trial_response_before_execution(
    tmp_path: Path,
) -> None:
    report = _trial_report()
    report["trial_response_valid"] = False
    checkout = tmp_path / "checkout"
    trial_dir = tmp_path / "trial"
    checkout.mkdir()
    trial_dir.mkdir()

    with patch.object(trials, "_run_bounded_process") as run_process:
        result = _run_verifier(report, trial_dir)

    assert result["passed"] is False
    assert "canonical schema" in result["reason"]
    run_process.assert_not_called()


def test_verifier_uses_the_credentialless_sandbox(tmp_path: Path) -> None:
    report = _trial_report()
    checkout = tmp_path / "checkout"
    trial_dir = tmp_path / "trial"
    checkout.mkdir()
    trial_dir.mkdir()

    with patch.object(
        trials, "_run_bounded_process", return_value=_bounded_process_result()
    ) as run_process:
        _run_verifier(report, trial_dir)

    command = run_process.call_args.kwargs["command"]
    assert command[0] == "bwrap"
    assert "--ignore-user-config" in command
    assert "/codex-home/auth.json" not in command
    assert trials.SANDBOX_PROXY_URL in " ".join(command)
    assert ROUTING_PROXY_URL not in " ".join(command)
    assert "--share-net" not in command
    assert "/broker/proxy.sock" in " ".join(command)


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


def test_workspace_write_verdict_requires_a_host_final_diff_reference() -> None:
    final_diff = {"valid": True, "sha256": "a" * 64, "content": "diff"}
    payload = _verdict(
        evidence=[
            _event_reference(),
            {"kind": "final_diff", "sha256": "a" * 64, "claim": "source changed"},
        ]
    )
    assert trials.validate_verdict(
        payload,
        trial_id="trial",
        tested_commit="tested",
        rubric_commit="rubric",
        event_evidence=_complete_event_evidence(),
        final_diff=final_diff,
        require_final_diff=True,
    ) == (True, "pass")
    assert not trials.validate_verdict(
        _verdict(),
        trial_id="trial",
        tested_commit="tested",
        rubric_commit="rubric",
        event_evidence=_complete_event_evidence(),
        final_diff=final_diff,
        require_final_diff=True,
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

    def complete_with_verdict(verdict: dict[str, object]) -> object:
        def run_process(**kwargs: object) -> dict[str, object]:
            events_path = kwargs["events_path"]
            assert isinstance(events_path, Path)
            events_path.write_text(
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {"type": "agent_message", "text": json.dumps(verdict)},
                    }
                )
                + "\n"
                + json.dumps({"type": "turn.completed"})
                + "\n",
                encoding="utf-8",
            )
            return _bounded_process_result()

        return run_process

    with patch.object(
        trials, "_run_bounded_process", side_effect=complete_with_verdict(_verdict())
    ):
        passed = _run_verifier(report, trial_dir)
    assert passed["passed"] is True

    failing_verdict = _verdict(verdict="fail", missing_requirements=["owner"])
    with patch.object(
        trials,
        "_run_bounded_process",
        side_effect=complete_with_verdict(failing_verdict),
    ):
        failed = _run_verifier(report, trial_dir)
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

    def invalid_result(**kwargs: object) -> dict[str, object]:
        events_path = kwargs["events_path"]
        assert isinstance(events_path, Path)
        events_path.write_bytes(b"\xff")
        return _bounded_process_result()

    with patch.object(trials, "_run_bounded_process", side_effect=invalid_result):
        invalid_utf8 = _run_verifier(report, trial_dir)
    assert invalid_utf8["passed"] is False
    assert "unreadable" in invalid_utf8["reason"]

    def oversized_result(**kwargs: object) -> dict[str, object]:
        events_path = kwargs["events_path"]
        assert isinstance(events_path, Path)
        events_path.write_text(
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "type": "agent_message",
                        "text": "é" * (trials.VERIFIER_REPORT_MAX_BYTES // 2 + 1),
                    },
                }
            )
            + "\n"
            + json.dumps({"type": "turn.completed"}),
            encoding="utf-8",
        )
        return _bounded_process_result()

    with patch.object(trials, "_run_bounded_process", side_effect=oversized_result):
        oversized = _run_verifier(report, trial_dir)
    assert oversized["passed"] is False
    assert "byte bound" in oversized["reason"]

    def surrogate_result(**kwargs: object) -> dict[str, object]:
        events_path = kwargs["events_path"]
        assert isinstance(events_path, Path)
        events_path.write_text(
            '{"type":"item.completed","item":{"type":"agent_message","text":"\\ud800"}}\n'
            '{"type":"turn.completed"}\n',
            encoding="utf-8",
        )
        return _bounded_process_result()

    with patch.object(trials, "_run_bounded_process", side_effect=surrogate_result):
        surrogate = _run_verifier(report, trial_dir)
    assert surrogate["passed"] is False
    assert "unreadable" in surrogate["reason"]


def test_run_verifier_missing_and_timeout_fail_closed(tmp_path: Path) -> None:
    report = _trial_report()
    checkout = tmp_path / "checkout"
    checkout.mkdir()

    missing_dir = tmp_path / "missing"
    missing_dir.mkdir()
    with patch.object(
        trials, "_run_bounded_process", return_value=_bounded_process_result()
    ):
        missing = _run_verifier(report, missing_dir)
    assert missing["passed"] is False

    timeout_dir = tmp_path / "timeout"
    timeout_dir.mkdir()
    with patch.object(
        trials,
        "_run_bounded_process",
        return_value=_bounded_process_result(returncode=124, timed_out=True),
    ):
        timeout = _run_verifier(report, timeout_dir)
    assert timeout["passed"] is False
    assert timeout["timed_out"] is True


def test_run_verifier_ignores_a_preexisting_subject_receipt(tmp_path: Path) -> None:
    report = _trial_report()
    checkout = tmp_path / "checkout"
    trial_dir = tmp_path / "trial"
    checkout.mkdir()
    trial_dir.mkdir()
    receipt_dir = trial_dir / "verifier-receipt"
    receipt_dir.mkdir()
    (receipt_dir / "verifier-report.json").write_text(
        json.dumps(_verdict()), encoding="utf-8"
    )

    with patch.object(
        trials, "_run_bounded_process", return_value=_bounded_process_result()
    ):
        result = _run_verifier(report, trial_dir)

    assert result["passed"] is False
    assert result["verdict"] is None
    assert (receipt_dir / "verifier-report.json").exists()
