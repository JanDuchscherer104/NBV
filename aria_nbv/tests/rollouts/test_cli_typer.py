"""Typer CLI tests for rollout generation and shard inspection commands."""

# ruff: noqa: S101

from __future__ import annotations

from types import SimpleNamespace

from typer.testing import CliRunner

from aria_nbv.oracle.pipelines import cli as rollout_cli

runner = CliRunner()


def _fake_rollout_config(tmp_path):
    return SimpleNamespace(
        source=SimpleNamespace(store=SimpleNamespace(store_dir=tmp_path / "vin_offline")),
        store=SimpleNamespace(store_dir=tmp_path / "rollouts.zarr"),
        target_selector=SimpleNamespace(k=2),
        candidate_mixture=SimpleNamespace(total_count=60),
        setup_target=lambda: SimpleNamespace(run=lambda **kwargs: None),
    )


def test_build_rollouts_dry_run_parses_config_path(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "rollouts.toml"
    config_path.write_text("max_samples = 1\n", encoding="utf-8")
    monkeypatch.setattr(
        rollout_cli,
        "RolloutDatasetWriterConfig",
        SimpleNamespace(from_toml=lambda path: _fake_rollout_config(tmp_path)),
    )

    result = runner.invoke(rollout_cli.build_app, ["--config-path", str(config_path), "--dry-run"])

    assert result.exit_code == 0
    assert "Dry run complete" in result.output


def test_build_rollouts_rejects_partial_shard_arguments(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "rollouts.toml"
    config_path.write_text("max_samples = 1\n", encoding="utf-8")
    monkeypatch.setattr(
        rollout_cli,
        "RolloutDatasetWriterConfig",
        SimpleNamespace(from_toml=lambda path: _fake_rollout_config(tmp_path)),
    )

    result = runner.invoke(
        rollout_cli.build_app,
        ["--config-path", str(config_path), "--shard-manifest", str(tmp_path / "shards.jsonl")],
    )

    assert result.exit_code == 2
    combined_output = result.output + result.stderr
    assert "must be" in combined_output
    assert "supplied together" in combined_output


def test_rollout_cli_help_exits_cleanly() -> None:
    assert runner.invoke(rollout_cli.build_app, ["--help"]).exit_code == 0
    assert runner.invoke(rollout_cli.plan_app, ["--help"]).exit_code == 0
    assert runner.invoke(rollout_cli.status_app, ["--help"]).exit_code == 0
