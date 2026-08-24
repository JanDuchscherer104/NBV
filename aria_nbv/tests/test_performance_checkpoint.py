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
    load_result_snapshot,
    log_wandb_result,
    record_checkpoint,
    result_sha256,
)


def _result(path: Path, *, status: str = "pass") -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "goal_slug": "startup-latency",
                "title": "Startup latency evaluator",
                "checkpoint_status": status,
                "summary": "p95 improved",
                "baseline_revision": "base123",
                "candidate_revision": "candidate456",
                "evaluator_fingerprint": "sha256:evaluator",
                "metrics": {"p95_ms": 12.5},
                "hard_gates": {"regression_tests": True},
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


def test_snapshot_digest_is_stable_after_source_replacement(tmp_path: Path) -> None:
    path = _result(tmp_path / "result.json")
    _, result_bytes = load_result_snapshot(path)
    path.write_text("{}", encoding="utf-8")

    assert result_sha256(result_bytes) != result_sha256(path.read_bytes())


def test_record_checkpoint_invokes_omx_with_digest_backed_evidence(tmp_path: Path) -> None:
    completed = __import__("subprocess").CompletedProcess([], 0, stdout="recorded", stderr="")
    with patch("aria_nbv.performance_checkpoint.subprocess.run", return_value=completed) as run:
        outcome = record_checkpoint(_result(tmp_path / "result.json"))

    command = run.call_args.args[0]
    assert command[:3] == ["omx", "performance-goal", "checkpoint"]
    assert command[command.index("--status") + 1] == "pass"
    assert run.call_args.kwargs["cwd"].name == "ARIA-NBV"
    assert outcome["omx_stdout"] == "recorded"


def test_record_checkpoint_mirrors_to_wandb_only_after_omx_accepts(tmp_path: Path) -> None:
    completed = __import__("subprocess").CompletedProcess([], 0, stdout="recorded", stderr="")
    events: list[str] = []

    def checkpoint(*args: object, **kwargs: object) -> object:
        events.append("omx")
        return completed

    def mirror(*args: object, **kwargs: object) -> str:
        events.append("wandb")
        return "wandb-run"

    with (
        patch("aria_nbv.performance_checkpoint.subprocess.run", side_effect=checkpoint),
        patch("aria_nbv.performance_checkpoint.log_wandb_result", side_effect=mirror),
    ):
        outcome = record_checkpoint(_result(tmp_path / "result.json"), wandb_config=WandbConfig())

    assert events == ["omx", "wandb"]
    assert outcome["wandb_run_id"] == "wandb-run"


def test_wandb_series_uses_acquisition_axis_and_scalar_summary(tmp_path: Path) -> None:
    result, result_bytes = load_result_snapshot(_result(tmp_path / "result.json"))
    run = MagicMock()
    run.id = "wandb-run"
    artifact = MagicMock()
    result_file = MagicMock()
    artifact.new_file.return_value.__enter__.return_value = result_file
    wandb = SimpleNamespace(init=MagicMock(return_value=run), Artifact=MagicMock(return_value=artifact))

    with patch.dict(sys.modules, {"wandb": wandb}):
        run_id = log_wandb_result(result, result_bytes, result_sha256(result_bytes), WandbConfig())

    assert run_id == "wandb-run"
    assert wandb.init.call_args.kwargs["name"] == "[senpai] Startup latency evaluator"
    assert wandb.init.call_args.kwargs["group"] == "senpai"
    assert run.define_metric.call_args_list[0].args == ("aria_autoresearch/acquisition_number",)
    assert run.define_metric.call_args_list[0].kwargs == {"hidden": True}
    assert run.define_metric.call_args_list[1].kwargs == {"step_metric": "aria_autoresearch/acquisition_number"}
    assert run.log.call_count == 2
    assert run.summary.update.call_args.args[0] == {"aria_autoresearch/p95_ms": 12.5}
