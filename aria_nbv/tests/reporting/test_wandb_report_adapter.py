"""Exact W&B acquisition and canonical figure tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from aria_nbv.reporting import ScientificReportConfig, write_report_snapshot
from aria_nbv.reporting.config import (
    ReportSourcesConfig,
    WandbReportSectionConfig,
    WandbSourceConfig,
)


class _Run:
    def __init__(self, run_id: str, offset: float = 0.0, *, state: str = "finished") -> None:
        self.id = run_id
        self.name = f"run-{run_id}"
        self.state = state
        self.group = None
        self.job_type = None
        self.tags = ()
        self.created_at = "2026-08-26T00:00:00Z"
        self.summary = {"val/loss": 0.5 + offset}
        self.config = {"seed": int(offset)}
        self._rows = [
            {"trainer/global_step": 0, "val/loss": 1.0 + offset},
            {"trainer/global_step": 1, "val/loss": 0.5 + offset},
        ]
        self.history_calls = 0
        self.scan_calls = 0

    def history(self, keys: list[str] | None = None, samples: int | None = None) -> pd.DataFrame:
        self.history_calls += 1
        return pd.DataFrame(self._rows)

    def scan_history(self, keys: list[str] | None = None) -> list[dict[str, Any]]:
        self.scan_calls += 1
        return list(self._rows)


class _MutatingRun(_Run):
    def scan_history(self, keys: list[str] | None = None) -> list[dict[str, Any]]:
        rows = super().scan_history(keys=keys)
        self.summary["val/loss"] = 0.25
        return rows


class _Api:
    def __init__(self, runs: dict[str, _Run]) -> None:
        self.runs = runs
        self.calls: list[str] = []

    def run(self, path: str) -> _Run:
        self.calls.append(path)
        return self.runs[path.rsplit("/", 1)[-1]]


class _Renderer:
    def render(
        self,
        plotly_json: bytes,
        destination: Path,
        *,
        image_format: str,
        width: int,
        height: int,
        scale: float,
    ) -> None:
        destination.write_bytes(plotly_json)

    def fingerprint(self) -> dict[str, str]:
        return {"renderer": "fixture"}


def _config(*, status: str = "confirmatory") -> ScientificReportConfig:
    return ScientificReportConfig(
        evidence_status=status,
        sources=ReportSourcesConfig(
            wandb=WandbSourceConfig(
                entity="entity",
                project="project",
                run_ids=("b", "a"),
                history_keys=("trainer/global_step", "val/loss"),
                history_mode="complete" if status == "confirmatory" else "sampled",
            )
        ),
        sections=(WandbReportSectionConfig(id="training", metric="val/loss"),),
    )


def test_complete_histories_are_frozen_in_run_id_order() -> None:
    runs = {"a": _Run("a"), "b": _Run("b", 1.0)}
    api = _Api(runs)

    snapshot = _config().setup_target(wandb_api=api, root=Path(__file__).parents[3]).build()

    assert api.calls == ["entity/project/a", "entity/project/b"]
    assert all(run.scan_calls == 1 and run.history_calls == 0 for run in runs.values())
    assert snapshot.source_identities[0].provenance == (
        ("entity", "entity"),
        ("history_complete", True),
        ("history_mode", "complete"),
        ("project", "project"),
        ("run_count", 2),
    )


def test_confirmatory_run_must_be_finished() -> None:
    runs = {"a": _Run("a", state="running"), "b": _Run("b")}

    with pytest.raises(Exception, match="not finished"):
        _config().setup_target(wandb_api=_Api(runs), root=Path(__file__).parents[3]).build()


def test_export_of_previewed_snapshot_performs_zero_wandb_calls(tmp_path: Path) -> None:
    runs = {"a": _Run("a"), "b": _Run("b", 1.0)}
    api = _Api(runs)
    snapshot = _config().setup_target(wandb_api=api, root=Path(__file__).parents[3]).build()
    before = (tuple(api.calls), tuple((run.history_calls, run.scan_calls) for run in runs.values()))

    write_report_snapshot(snapshot, tmp_path / "report", renderer=_Renderer())

    after = (tuple(api.calls), tuple((run.history_calls, run.scan_calls) for run in runs.values()))
    assert after == before


def test_run_identity_change_during_acquisition_fails_closed() -> None:
    runs = {"a": _MutatingRun("a"), "b": _Run("b")}

    with pytest.raises(Exception, match="changed during acquisition"):
        _config().setup_target(wandb_api=_Api(runs), root=Path(__file__).parents[3]).build()
