"""Tests for the immutable performance-goal result bridge."""

# ruff: noqa: S101

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from aria_nbv.configs.wandb_config import WandbConfig
from aria_nbv.performance_checkpoint import (
    ResultContractError,
    WandbPublication,
    load_result_snapshot,
    log_wandb_result,
    record_checkpoint,
    result_sha256,
)


def _result(path: Path, *, status: str = "pass") -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "goal_slug": "startup-latency",
                "iteration": 2,
                "title": "Startup latency evaluator",
                "checkpoint_status": status,
                "summary": "p95 improved",
                "hypothesis": "Caching imports reduces startup latency without changing output.",
                "baseline_revision": "base123",
                "candidate_revision": "candidate456",
                "evaluator_fingerprint": "sha256:evaluator",
                "research": {
                    "brief_sha256": "a" * 64,
                    "assignment_sha256": "b" * 64,
                    "sources": [
                        {
                            "kind": "local-code",
                            "locator": "aria_nbv/aria_nbv/cli.py:1",
                            "version": "base123",
                            "mechanism": "Import work dominates the measured startup path.",
                        }
                    ],
                },
                "metrics": {"p95_ms": 12.5},
                "hard_gates": {"regression_tests": True},
                "series_axis": "acquisition_number",
                "evidence_series": [
                    {"step": 1, "metrics": {"p95_ms": 14.0}},
                    {"step": 2, "metrics": {"p95_ms": 12.5}},
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_record_checkpoint_dry_run_validates_and_has_digest(tmp_path: Path) -> None:
    outcome = record_checkpoint(_result(tmp_path / "result.json"), dry_run=True)

    assert outcome["dry_run"] is True
    assert outcome["goal_slug"] == "startup-latency"
    assert len(outcome["result_sha256"]) == 64
    assert "candidate=candidate456" in outcome["evidence"]


def test_record_checkpoint_rejects_nonfinite_metric(tmp_path: Path) -> None:
    path = _result(tmp_path / "result.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["metrics"] = {"p95_ms": float("inf")}
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ResultContractError, match="finite number"):
        record_checkpoint(path, dry_run=True)


def test_record_checkpoint_requires_senpai_title(tmp_path: Path) -> None:
    path = _result(tmp_path / "result.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload["title"]
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ResultContractError, match="title"):
        record_checkpoint(path, dry_run=True)


def test_record_checkpoint_requires_research_phase_evidence(tmp_path: Path) -> None:
    path = _result(tmp_path / "result.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["research"]["sources"] = []
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ResultContractError, match="research.sources must not be empty"):
        record_checkpoint(path, dry_run=True)


def test_record_checkpoint_rejects_unversioned_research_source(tmp_path: Path) -> None:
    path = _result(tmp_path / "result.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["research"]["sources"][0]["version"] = ""
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ResultContractError, match=r"research.sources\[0\].version"):
        record_checkpoint(path, dry_run=True)


def test_record_checkpoint_rejects_invalid_research_digest(tmp_path: Path) -> None:
    path = _result(tmp_path / "result.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["research"]["brief_sha256"] = "not-a-digest"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ResultContractError, match="research.brief_sha256"):
        record_checkpoint(path, dry_run=True)


def test_record_checkpoint_rejects_pass_with_failed_hard_gate(tmp_path: Path) -> None:
    path = _result(tmp_path / "result.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["hard_gates"] = {"regression_tests": False}
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ResultContractError, match="hard gate failed"):
        record_checkpoint(path, dry_run=True)


def test_record_checkpoint_rejects_nonmonotonic_evidence_series(tmp_path: Path) -> None:
    path = _result(tmp_path / "result.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["evidence_series"][1]["step"] = 1
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ResultContractError, match="strictly increasing"):
        record_checkpoint(path, dry_run=True)


def test_record_checkpoint_rejects_sparse_evidence_series(tmp_path: Path) -> None:
    path = _result(tmp_path / "result.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["evidence_series"][1]["metrics"]["throughput"] = 10.0
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ResultContractError, match="same metric keys"):
        record_checkpoint(path, dry_run=True)


def test_snapshot_digest_is_stable_after_source_replacement(tmp_path: Path) -> None:
    path = _result(tmp_path / "result.json")
    _, result_bytes = load_result_snapshot(path)
    path.write_text("{}", encoding="utf-8")

    assert result_sha256(result_bytes) != result_sha256(path.read_bytes())


def test_record_checkpoint_invokes_omx_with_wandb_backed_evidence(tmp_path: Path) -> None:
    pending = __import__("subprocess").CompletedProcess([], 0, stdout="pending", stderr="")
    recorded = __import__("subprocess").CompletedProcess([], 0, stdout="recorded", stderr="")
    with (
        patch("aria_nbv.performance_checkpoint.subprocess.run", side_effect=[pending, recorded]) as run,
        patch(
            "aria_nbv.performance_checkpoint.log_wandb_result",
            return_value=WandbPublication(run_id="wandb-run", run_path="aria-nbv/aria-nbv/wandb-run"),
        ),
    ):
        outcome = record_checkpoint(_result(tmp_path / "result.json"), wandb_config=WandbConfig(offline=False))

    pending_command = run.call_args_list[0].args[0]
    final_command = run.call_args_list[1].args[0]
    assert pending_command[pending_command.index("--status") + 1] == "blocked"
    assert "wandb_publication=pending" in pending_command[pending_command.index("--evidence") + 1]
    assert final_command[final_command.index("--status") + 1] == "pass"
    assert "wandb_run=aria-nbv/aria-nbv/wandb-run" in final_command[final_command.index("--evidence") + 1]
    assert run.call_args_list[1].kwargs["cwd"].name == "ARIA-NBV"
    assert outcome["omx_stdout"] == "recorded"
    assert outcome["wandb_run_id"] == "wandb-run"
    assert outcome["wandb_run_path"] == "aria-nbv/aria-nbv/wandb-run"


def test_record_checkpoint_requires_wandb_configuration(tmp_path: Path) -> None:
    with pytest.raises(ResultContractError, match="require W&B configuration"):
        record_checkpoint(_result(tmp_path / "result.json"))


def test_record_checkpoint_keeps_omx_blocked_until_wandb_readback(tmp_path: Path) -> None:
    completed = __import__("subprocess").CompletedProcess([], 0, stdout="recorded", stderr="")
    events: list[str] = []

    def checkpoint(command: list[str], **kwargs: object) -> object:
        events.append(f"omx-{command[command.index('--status') + 1]}")
        return completed

    def mirror(*args: object, **kwargs: object) -> WandbPublication:
        events.append("wandb")
        return WandbPublication(run_id="wandb-run", run_path="aria-nbv/aria-nbv/wandb-run")

    with (
        patch("aria_nbv.performance_checkpoint.subprocess.run", side_effect=checkpoint),
        patch("aria_nbv.performance_checkpoint.log_wandb_result", side_effect=mirror),
    ):
        outcome = record_checkpoint(_result(tmp_path / "result.json"), wandb_config=WandbConfig(offline=False))

    assert events == ["omx-blocked", "wandb", "omx-pass"]
    assert outcome["wandb_run_id"] == "wandb-run"


def test_wandb_failure_leaves_omx_checkpoint_blocked(tmp_path: Path) -> None:
    completed = __import__("subprocess").CompletedProcess([], 0, stdout="pending", stderr="")
    with (
        patch("aria_nbv.performance_checkpoint.subprocess.run", return_value=completed) as run,
        patch("aria_nbv.performance_checkpoint.log_wandb_result", side_effect=RuntimeError("offline")),
        pytest.raises(RuntimeError, match="offline"),
    ):
        record_checkpoint(_result(tmp_path / "result.json"), wandb_config=WandbConfig(offline=False))

    assert run.call_count == 1
    command = run.call_args.args[0]
    assert command[command.index("--status") + 1] == "blocked"


@pytest.mark.parametrize(
    "sdk_run_path",
    [
        ("aria-nbv", "aria-nbv", "wandb-run"),
        "aria-nbv/aria-nbv/wandb-run",
    ],
)
def test_wandb_series_uses_acquisition_axis_and_scalar_summary(
    tmp_path: Path,
    sdk_run_path: str | tuple[str, str, str],
) -> None:
    result, result_bytes = load_result_snapshot(_result(tmp_path / "result.json"))
    run = MagicMock()
    run.id = "wandb-run"
    run.path = sdk_run_path
    artifact = MagicMock()
    result_file = MagicMock()
    artifact.new_file.return_value.__enter__.return_value = result_file
    published = SimpleNamespace(
        name="[senpai] Startup latency evaluator",
        group="senpai",
        tags=["senpai", "goal:startup-latency", "iteration:2", "status:pass"],
        config={
            "aria_autoresearch": {
                "goal_slug": "startup-latency",
                "iteration": 2,
                "checkpoint_status": "pass",
                "hypothesis": "Caching imports reduces startup latency without changing output.",
                "baseline_revision": "base123",
                "candidate_revision": "candidate456",
                "evaluator_fingerprint": "sha256:evaluator",
                "research_brief_sha256": "a" * 64,
                "assignment_sha256": "b" * 64,
                "research_source_count": 1,
                "result_sha256": result_sha256(result_bytes),
            }
        },
    )
    wandb = SimpleNamespace(
        init=MagicMock(return_value=run),
        Artifact=MagicMock(return_value=artifact),
        Api=MagicMock(return_value=SimpleNamespace(run=MagicMock(return_value=published))),
    )

    with patch.dict(sys.modules, {"wandb": wandb}):
        publication = log_wandb_result(
            result,
            result_bytes,
            result_sha256(result_bytes),
            WandbConfig(offline=False),
        )

    assert publication == WandbPublication(
        run_id="wandb-run",
        run_path="aria-nbv/aria-nbv/wandb-run",
    )
    assert wandb.init.call_args.kwargs["name"] == "[senpai] Startup latency evaluator"
    assert wandb.init.call_args.kwargs["group"] == "senpai"
    assert wandb.init.call_args.kwargs["tags"] == [
        "senpai",
        "goal:startup-latency",
        "iteration:2",
        "status:pass",
    ]
    assert run.define_metric.call_args_list[0].args == ("aria_autoresearch/acquisition_number",)
    assert run.define_metric.call_args_list[0].kwargs == {"hidden": True}
    assert run.define_metric.call_args_list[1].kwargs == {"step_metric": "aria_autoresearch/acquisition_number"}
    assert run.log.call_count == 2
    assert run.summary.update.call_args.args[0] == {"aria_autoresearch/p95_ms": 12.5}
    assert wandb.Api.return_value.run.call_args.args == ("aria-nbv/aria-nbv/wandb-run",)
