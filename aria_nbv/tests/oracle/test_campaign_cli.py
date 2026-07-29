from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from aria_nbv.oracle.pipelines import campaign_cli

runner = CliRunner()


def _config(tmp_path: Path) -> SimpleNamespace:
    inventory = SimpleNamespace(
        scenes=[SimpleNamespace(candidates=(1, 2)), SimpleNamespace(candidates=(3, 4))],
        selected_sample_keys=("sample-a", "sample-b"),
    )
    campaign = SimpleNamespace(
        planned_profiles_by_scene=lambda _inventory: {
            "scene-a": ("realistic_core_60", "rich_local_60"),
            "scene-b": ("realistic_core_60", "radial_backtrack_60"),
        },
        paired_panel_scene_ids=lambda _inventory: (),
        run=lambda: SimpleNamespace(
            reason="max_new_shards",
            new_shards=1,
            skipped_shards=0,
            failed_shards=0,
            failed_scenes=0,
            status_path=tmp_path / "status.json",
            progress_path=tmp_path / "progress.jsonl",
        ),
    )
    config = SimpleNamespace(
        campaign_id="fixture-campaign",
        seed=17,
        expected_scene_count=2,
        ase_efm_dir=tmp_path / "efm",
        ase_meshes_dir=tmp_path / "meshes",
        profiles={
            "realistic_core_60": object(),
            "rich_local_60": object(),
            "radial_backtrack_60": object(),
        },
        runtime=SimpleNamespace(
            max_new_shards=1,
            stop_after_minutes=10.0,
            keep_free_disk_gib=1.0,
            max_failed_units=3,
        ),
        collection_dir=tmp_path / "collection",
        output_root=tmp_path / "output",
        setup_target=lambda: campaign,
    )
    config._inventory = inventory
    return config


def test_plan_campaign_cli_reports_exact_work_units(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    config_path = tmp_path / "campaign.toml"
    config_path.write_text("campaign_id = 'fixture'\n", encoding="utf-8")
    monkeypatch.setattr(campaign_cli.RolloutCampaignConfig, "from_toml", lambda _path: config)
    monkeypatch.setattr(campaign_cli, "discover_ase_root_inventory", lambda **_kwargs: config._inventory)

    result = runner.invoke(campaign_cli.plan_app, ["--config-path", str(config_path)])

    assert result.exit_code == 0
    assert "fixture-campaign" in result.output
    assert "profile shards" in result.output
    assert "4" in result.output


def test_run_campaign_cli_dispatches_bounded_resume(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    config_path = tmp_path / "campaign.toml"
    config_path.write_text("campaign_id = 'fixture'\n", encoding="utf-8")
    monkeypatch.setattr(campaign_cli.RolloutCampaignConfig, "from_toml", lambda _path: config)

    result = runner.invoke(campaign_cli.run_app, ["--config-path", str(config_path)])

    assert result.exit_code == 0
    assert "max_new_shards" in result.output
    assert "new shards" in result.output


def test_run_campaign_cli_rejects_incomplete_scene_coverage(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    config.setup_target = lambda: SimpleNamespace(
        run=lambda: SimpleNamespace(
            reason="incomplete",
            new_shards=0,
            skipped_shards=0,
            failed_shards=0,
            failed_scenes=1,
            status_path=tmp_path / "status.json",
            progress_path=tmp_path / "progress.jsonl",
        )
    )
    config_path = tmp_path / "campaign.toml"
    config_path.write_text("campaign_id = 'fixture'\n", encoding="utf-8")
    monkeypatch.setattr(campaign_cli.RolloutCampaignConfig, "from_toml", lambda _path: config)

    result = runner.invoke(campaign_cli.run_app, ["--config-path", str(config_path)])

    assert result.exit_code != 0
    assert "failed_scenes=1" in result.output


def test_campaign_cli_help_exits_cleanly() -> None:
    assert runner.invoke(campaign_cli.plan_app, ["--help"]).exit_code == 0
    assert runner.invoke(campaign_cli.run_app, ["--help"]).exit_code == 0
    assert runner.invoke(campaign_cli.status_app, ["--help"]).exit_code == 0
