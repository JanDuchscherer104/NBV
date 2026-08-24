"""CLI tests for rollout-store inspection."""

# ruff: noqa: S101

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import zarr
from typer.testing import CliRunner

import aria_nbv.rollouts.info_cli as info_cli
from aria_nbv.rollouts.info_cli import app as rollouts_info_app
from aria_nbv.rollouts.info_cli import main as rollouts_info_main
from aria_nbv.rollouts.inspection import build_compact_statistics
from aria_nbv.rollouts.reporting import ANALYSIS_FACT_SIDECAR_VERSION, THESIS_REPORT_BUNDLE_VERSION
from aria_nbv.rollouts.zarr_store import (
    ROLLOUT_ZARR_SCHEMA_VERSION,
    RolloutZarrStoreReader,
    write_rollout_zarr_store,
)
from tests.rollout_fixtures import build_rollout_records

runner = CliRunner()


@pytest.mark.parametrize(
    ("flags", "expected_calls", "has_stats"),
    [
        ([], {"manifest": 1, "validation": 0, "statistics": 0}, False),
        (["--validate"], {"manifest": 1, "validation": 1, "statistics": 0}, False),
        (["--stats"], {"manifest": 1, "validation": 0, "statistics": 1}, True),
        (["--preflight"], {"manifest": 1, "validation": 1, "statistics": 1}, True),
    ],
)
def test_rollouts_info_preserves_demand_aligned_inspection_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    flags: list[str],
    expected_calls: dict[str, int],
    has_stats: bool,
) -> None:
    """CLI modes read only the manifest, validation, and statistics facets they demand."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr", build_rollout_records(horizon=2, num_samples=6, seed=101)
    )
    calls = dict.fromkeys(expected_calls, 0)
    original_manifest = RolloutZarrStoreReader.manifest
    original_validate = RolloutZarrStoreReader.validate
    original_statistics = build_compact_statistics

    def manifest(reader: Any) -> Any:
        calls["manifest"] += 1
        return original_manifest(reader)

    def validate(reader: Any) -> Any:
        calls["validation"] += 1
        return original_validate(reader)

    def statistics(reader: Any, *, manifest_payload: Any = None) -> Any:
        calls["statistics"] += 1
        return original_statistics(reader, manifest_payload=manifest_payload)

    monkeypatch.setattr(RolloutZarrStoreReader, "manifest", manifest)
    monkeypatch.setattr(RolloutZarrStoreReader, "validate", validate)
    monkeypatch.setattr("aria_nbv.rollouts.info_cli.build_compact_statistics", statistics)
    cli_result = runner.invoke(info_cli.app, ["--store", str(result.store_dir), "--json", *flags])

    assert cli_result.exit_code == 0
    payload = json.loads(cli_result.output)
    assert calls == expected_calls
    assert ("stats" in payload) is has_stats


def test_rollouts_info_json_unchanged_without_new_flags(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    records = build_rollout_records(horizon=1, num_samples=4, seed=1)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    capsys.readouterr()

    cli_result = runner.invoke(rollouts_info_app, ["--store", str(result.store_dir), "--json"])

    assert cli_result.exit_code == 0
    payload = json.loads(cli_result.output)
    assert payload["manifest"]["counts"]["rollouts"] == result.num_rollouts
    assert payload["manifest"]["counts"]["steps"] == result.num_steps
    assert "stats" not in payload


def test_rollouts_info_stats_reports_validity_and_selected_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    records = build_rollout_records(horizon=2, num_samples=6, seed=11)
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    capsys.readouterr()

    cli_result = runner.invoke(rollouts_info_app, ["--store", str(result.store_dir), "--stats", "--json"])

    assert cli_result.exit_code == 0
    payload = json.loads(cli_result.output)
    stats = payload["stats"]
    assert stats["candidate_validity"]["total"] == result.num_candidates
    assert stats["candidate_validity"]["valid"] > 0
    assert stats["candidate_validity"]["valid_per_step"]["count"] == result.num_steps
    assert stats["selected"]["total"] == result.num_steps
    assert stats["selected"]["path_length_m"]["count"] == result.num_rollouts
    assert stats["selected"]["strategy_counts"]
    assert stats["policy_counts"]


def test_rollouts_info_preflight_json_reports_go_no_go_sections(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    records = build_rollout_records(horizon=2, num_samples=6, seed=12)
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    capsys.readouterr()

    cli_result = runner.invoke(
        rollouts_info_app,
        ["--store", str(result.store_dir), "--preflight", "--profile", "smoke", "--json"],
    )

    assert cli_result.exit_code == 0
    payload = json.loads(cli_result.output)
    preflight = payload["preflight"]
    assert preflight["schema"]["expected"] == ROLLOUT_ZARR_SCHEMA_VERSION
    assert preflight["validation"]["ok"]
    assert "coverage" in preflight
    assert "validity" in preflight
    assert "rewards" in preflight
    assert "storage" in preflight
    assert isinstance(preflight["go"], bool)


def test_rollouts_info_preflight_production_fails_on_stale_schema(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    records = build_rollout_records(horizon=1, num_samples=4, seed=13)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    root = zarr.open_group(result.store_dir, mode="a")
    root.attrs["schema_version"] = "0.9-stale"
    capsys.readouterr()

    cli_result = runner.invoke(
        rollouts_info_app,
        ["--store", str(result.store_dir), "--preflight", "--profile", "production", "--json"],
    )

    assert cli_result.exit_code == 1
    payload = json.loads(cli_result.output)
    assert not payload["preflight"]["go"]
    assert "stale_schema:0.9-stale" in payload["preflight"]["blockers"]


def test_rollouts_info_random_index_respects_min_horizon(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    records = build_rollout_records(horizon=2, num_samples=4, seed=3)
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    capsys.readouterr()

    cli_result = runner.invoke(
        rollouts_info_app,
        ["--store", str(result.store_dir), "--random-index", "--min-horizon", "2", "--seed", "0"],
    )

    assert cli_result.exit_code == 0
    value = int(cli_result.output.strip())
    assert 0 <= value < result.num_rollouts


def test_rollouts_info_random_index_errors_when_no_rows_are_eligible(tmp_path: Path) -> None:
    records = build_rollout_records(horizon=1, num_samples=4, seed=5)
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)

    with pytest.raises(SystemExit) as exc_info:
        rollouts_info_main(["--store", str(result.store_dir), "--random-index", "--min-horizon", "2", "--seed", "0"])

    assert "No rollout rows found with horizon >= 2" in str(exc_info.value)


def test_rollouts_info_help_exits_cleanly() -> None:
    result = runner.invoke(rollouts_info_app, ["--help"], env={"COLUMNS": "200"})

    assert result.exit_code == 0
    assert "--stats" in result.output
    assert "--thesis-bundle-output" in result.output
    assert "--thesis-evidence-status" in result.output
    assert "--thesis-sidecar" in result.output


def test_rollouts_info_exports_deterministic_thesis_bundle_with_promoted_facts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    records = build_rollout_records(horizon=1, num_samples=4, seed=21)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    sidecar = tmp_path / "analysis.json"
    sidecar.write_text(
        json.dumps(
            {
                "schema_version": ANALYSIS_FACT_SIDECAR_VERSION,
                "bundle_role": "analysis_facts",
                "logical_name": "pilot-runtime",
                "status": "pilot",
                "facts": [
                    {
                        "store_id": result.manifest_sha256,
                        "key": "runtime.wall_time_s",
                        "value": 4.25,
                        "unit": "s",
                        "n": 1,
                        "aggregation": "total",
                        "provenance": "pilot/run-summary.json",
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    first_output = tmp_path / "first.json"
    second_output = tmp_path / "second.json"
    capsys.readouterr()

    first = runner.invoke(
        rollouts_info_app,
        [
            "--store",
            str(result.store_dir),
            "--thesis-bundle-output",
            str(first_output),
            "--thesis-evidence-status",
            "pilot",
            "--thesis-sidecar",
            str(sidecar),
            "--json",
        ],
    )
    second = runner.invoke(
        rollouts_info_app,
        [
            "--store",
            str(result.store_dir),
            "--thesis-bundle-output",
            str(second_output),
            "--thesis-evidence-status",
            "pilot",
            "--thesis-sidecar",
            str(sidecar),
            "--json",
        ],
    )

    assert first.exit_code == second.exit_code == 0
    first_payload = json.loads(first.output)
    second_payload = json.loads(second.output)
    first_bundle = first_output.read_bytes()
    assert first_bundle == second_output.read_bytes()
    digest = hashlib.sha256(first_bundle).hexdigest()
    assert first_payload["thesis_bundle"] == {
        "bundle_role": "evidence",
        "path": first_output.resolve().as_posix(),
        "schema_version": THESIS_REPORT_BUNDLE_VERSION,
        "sha256": digest,
    }
    assert second_payload["thesis_bundle"]["sha256"] == digest
    bundle = json.loads(first_bundle)
    assert bundle["bundle_role"] == "evidence"
    assert any(row["key"] == "runtime.wall_time_s" for row in bundle["tables"]["facts"]["rows"])
    assert str(tmp_path) not in json.dumps(bundle["tables"]["sidecars"])


def test_rollouts_info_text_reports_thesis_bundle_metadata(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=4, seed=22)[:1],
    )
    output = tmp_path / "report.json"
    capsys.readouterr()

    cli_result = runner.invoke(
        rollouts_info_app,
        [
            "--store",
            str(result.store_dir),
            "--thesis-bundle-output",
            str(output),
            "--thesis-evidence-status",
            "confirmatory",
        ],
    )

    assert cli_result.exit_code == 0
    assert "Thesis Evidence Bundle" in cli_result.output
    assert THESIS_REPORT_BUNDLE_VERSION in cli_result.output
    assert hashlib.sha256(output.read_bytes()).hexdigest() in cli_result.output


@pytest.mark.parametrize(
    "arguments",
    [
        ["--thesis-bundle-output", "report.json"],
        ["--thesis-evidence-status", "pilot"],
        ["--thesis-sidecar", "analysis.json"],
    ],
)
def test_rollouts_info_rejects_incomplete_thesis_export_options(tmp_path: Path, arguments: Any) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=4, seed=23)[:1],
    )

    cli_result = runner.invoke(rollouts_info_app, ["--store", str(result.store_dir), *arguments])

    assert cli_result.exit_code == 2
