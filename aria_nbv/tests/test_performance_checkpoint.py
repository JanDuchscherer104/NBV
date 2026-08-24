"""Tests for the immutable performance-goal result bridge."""

# ruff: noqa: S101

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from aria_nbv.performance_checkpoint import ResultContractError, record_checkpoint


def _result(path: Path, *, status: str = "pass") -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "goal_slug": "startup-latency",
                "checkpoint_status": status,
                "summary": "p95 improved",
                "baseline_revision": "base123",
                "candidate_revision": "candidate456",
                "evaluator_fingerprint": "sha256:evaluator",
                "metrics": {"p95_ms": 12.5},
                "hard_gates": {"regression_tests": True},
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


def test_record_checkpoint_invokes_omx_with_digest_backed_evidence(tmp_path: Path) -> None:
    completed = __import__("subprocess").CompletedProcess([], 0, stdout="recorded", stderr="")
    with patch("aria_nbv.performance_checkpoint.subprocess.run", return_value=completed) as run:
        outcome = record_checkpoint(_result(tmp_path / "result.json"))

    command = run.call_args.args[0]
    assert command[:3] == ["omx", "performance-goal", "checkpoint"]
    assert command[command.index("--status") + 1] == "pass"
    assert outcome["omx_stdout"] == "recorded"
