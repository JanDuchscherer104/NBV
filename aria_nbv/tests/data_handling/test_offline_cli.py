"""Typer CLI tests for immutable VIN offline-store creation."""

# ruff: noqa: S101

from __future__ import annotations

from types import SimpleNamespace

from typer.testing import CliRunner

from aria_nbv.oracle.pipelines import cli as pipeline_cli

runner = CliRunner()


def test_build_offline_dry_run_parses_config_path(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "offline.toml"
    config_path.write_text("store_dir = 'unused'\n", encoding="utf-8")
    fake_cfg = SimpleNamespace(store=SimpleNamespace(store_dir=tmp_path / "vin_offline"))
    monkeypatch.setattr(pipeline_cli, "VinOfflineWriterConfig", SimpleNamespace(from_toml=lambda path: fake_cfg))

    result = runner.invoke(pipeline_cli.offline_app, ["--config-path", str(config_path), "--dry-run"])

    assert result.exit_code == 0
    assert "Dry run complete" in result.output


def test_build_offline_help_exits_cleanly() -> None:
    result = runner.invoke(pipeline_cli.offline_app, ["--help"])

    assert result.exit_code == 0
    assert "--config-path" in result.output
