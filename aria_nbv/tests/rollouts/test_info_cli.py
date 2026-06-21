"""CLI tests for rollout-store inspection."""

# ruff: noqa: S101

from __future__ import annotations

import json

import pytest
import zarr
from typer.testing import CliRunner

from aria_nbv.rollouts import ROLLOUT_ZARR_SCHEMA_VERSION, write_rollout_zarr_store
from aria_nbv.rollouts.info_cli import app as rollouts_info_app
from aria_nbv.rollouts.info_cli import main as rollouts_info_main
from tests.rollout_fixtures import build_rollout_records

runner = CliRunner()


def test_rollouts_info_json_unchanged_without_new_flags(tmp_path, capsys) -> None:
    records = build_rollout_records(horizon=1, num_samples=4, seed=1)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    capsys.readouterr()

    cli_result = runner.invoke(rollouts_info_app, ["--store", str(result.store_dir), "--json"])

    assert cli_result.exit_code == 0
    payload = json.loads(cli_result.output)
    assert payload["manifest"]["counts"]["rollouts"] == result.num_rollouts
    assert payload["manifest"]["counts"]["steps"] == result.num_steps
    assert "stats" not in payload


def test_rollouts_info_stats_reports_validity_and_selected_paths(tmp_path, capsys) -> None:
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


def test_rollouts_info_preflight_json_reports_go_no_go_sections(tmp_path, capsys) -> None:
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


def test_rollouts_info_preflight_production_fails_on_stale_schema(tmp_path, capsys) -> None:
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


def test_rollouts_info_random_index_respects_min_horizon(tmp_path, capsys) -> None:
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


def test_rollouts_info_random_index_errors_when_no_rows_are_eligible(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=4, seed=5)
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)

    with pytest.raises(SystemExit) as exc_info:
        rollouts_info_main(["--store", str(result.store_dir), "--random-index", "--min-horizon", "2", "--seed", "0"])

    assert "No rollout rows found with horizon >= 2" in str(exc_info.value)


def test_rollouts_info_help_exits_cleanly() -> None:
    result = runner.invoke(rollouts_info_app, ["--help"])

    assert result.exit_code == 0
    assert "--stats" in result.output
