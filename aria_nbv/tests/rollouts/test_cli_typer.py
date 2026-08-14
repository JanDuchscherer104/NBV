"""Typer CLI tests for rollout generation and shard inspection commands."""

# ruff: noqa: S101

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from aria_nbv.oracle.pipelines import cli as rollout_cli
from aria_nbv.utils.fingerprints import stable_config_hash, stable_msgspec_hash

runner = CliRunner()


def _fake_rollout_config(tmp_path):
    return SimpleNamespace(
        source=SimpleNamespace(store=SimpleNamespace(store_dir=tmp_path / "vin_offline")),
        store=SimpleNamespace(store_dir=tmp_path / "rollouts.zarr"),
        max_targets_per_sample=2,
        oracle_target_task_sampler=SimpleNamespace(max_targets_per_sample=2),
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
    assert "gt_obbs_oracle" in result.output
    assert "target cap" in result.output


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


def test_campaign_status_json_delegates_to_presentation_free_reader(tmp_path, monkeypatch) -> None:
    class _Campaign:
        config = SimpleNamespace(campaign_id="test-campaign")

        def read_status(self):
            return SimpleNamespace(
                state="completed_with_failures",
                counts={
                    "succeeded": 1,
                    "failed": 1,
                    "skipped": 0,
                    "insufficient_support": 0,
                    "timed_out": 0,
                    "pending": 0,
                },
                plan_hash="plan",
                updated_at="now",
                current_work_unit="unit",
                current_target_id="target",
                current_profile="realistic_core_60",
                current_stage="worker",
                elapsed_seconds=3.0,
                latest_failure_reason="timeout",
            )

        def progress_summary(self):
            return {
                "counts": {
                    "succeeded": 1,
                    "failed": 1,
                    "skipped": 0,
                    "insufficient_support": 0,
                    "timed_out": 0,
                    "pending": 0,
                }
            }

    monkeypatch.setattr(rollout_cli, "_campaign", lambda _path: _Campaign())
    result = runner.invoke(rollout_cli.campaign_app, ["status", "--config-path", str(tmp_path / "cfg.toml"), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "completed_with_failures"
    assert payload["counts"]["failed"] == 1


def test_campaign_preflight_delegates_once(tmp_path, monkeypatch) -> None:
    calls = []

    class _Campaign:
        config = SimpleNamespace(writer_config_path=None)

        def preflight(self, **kwargs):
            calls.append("preflight")

    monkeypatch.setattr(rollout_cli, "_campaign", lambda _path: _Campaign())
    result = runner.invoke(rollout_cli.campaign_app, ["preflight", "--config-path", str(tmp_path / "cfg.toml")])
    assert result.exit_code == 0
    assert calls == ["preflight"]


@pytest.mark.parametrize(
    ("command", "message"), [("run", "campaign run complete"), ("resume", "campaign resume complete")]
)
def test_campaign_run_and_resume_delegate_once(tmp_path, monkeypatch, command, message) -> None:
    calls = []
    output_root = tmp_path / "campaign"
    output_root.mkdir()
    (output_root / "smoke-evidence.json").write_text('{"plan_hash":"plan"}\n')

    class _Campaign:
        config = SimpleNamespace(output_root=output_root, writer_config_path=None)

        def load_plan(self, path):
            return SimpleNamespace(plan_hash="plan")

        def preflight(self, *args, **kwargs):
            return SimpleNamespace(ok=True)

        def run(self, plan, **kwargs):
            calls.append((plan.plan_hash, kwargs))

    monkeypatch.setattr(rollout_cli, "_campaign", lambda _path: _Campaign())
    result = runner.invoke(rollout_cli.campaign_app, [command, "--config-path", "cfg.toml", "--plan-path", "plan.json"])
    assert result.exit_code == 0
    assert message in result.stdout
    assert len(calls) == 1


def test_campaign_worker_binds_selected_unit_profile_hash(tmp_path, monkeypatch) -> None:
    @dataclass(frozen=True)
    class _Entry:
        profile_hash: str = ""
        writer_config_hash: str = ""

    class _WriterConfig:
        def model_dump_jsonable(self):
            return {"writer": "canonical"}

    writer_cfg = _WriterConfig()
    writer_path = tmp_path / "writer.toml"
    writer_path.write_text("[writer]\n", encoding="utf-8")
    selected_profile_hash = "unit-profile-hash"
    plan_config_hash = stable_msgspec_hash({"campaign": "canonical"})
    writer_hash = stable_config_hash(writer_cfg)
    unit = SimpleNamespace(
        work_unit_hash="unit",
        profile_hash=selected_profile_hash,
        explicit_target_config=None,
    )
    plan = SimpleNamespace(
        plan_hash="plan",
        config_hash=plan_config_hash,
        writer_config_hash=writer_hash,
        work_units=(unit,),
        profile_hash="aggregate-profile-hash",
    )
    seen = {}

    class _Campaign:
        config = SimpleNamespace(
            output_root=tmp_path,
            writer_config_path=writer_path,
            model_dump_jsonable=lambda: {"campaign": "canonical"},
        )

        def load_plan(self, _path):
            return plan

        def shard_entry_for_unit(self, _plan, _unit):
            return _Entry()

        def adapt_work_unit(self, _unit, **kwargs):
            seen["profile_hash"] = kwargs["profile_hash"]
            return writer_cfg, replace(kwargs["shard_entry"], profile_hash=kwargs["profile_hash"])

        def preflight(self, **_kwargs):
            return None

    @dataclass(frozen=True)
    class _Result:
        outcome: str = "succeeded"
        skipped: bool = False
        success_path: Path = Path("success")
        owner_path: Path = Path("owner")

    monkeypatch.setattr(rollout_cli, "_campaign", lambda _path: _Campaign())
    monkeypatch.setattr(
        rollout_cli.RolloutDatasetWriterConfig,
        "from_toml",
        lambda _path: writer_cfg,
    )
    monkeypatch.setattr(
        rollout_cli,
        "run_rollout_shard",
        lambda _writer, *, shard_entry, **_kwargs: (
            seen.update(shard_profile_hash=shard_entry.profile_hash) or _Result()
        ),
    )

    rollout_cli.campaign_worker(
        config_path=tmp_path / "campaign.toml",
        plan_hash="plan",
        work_unit_hash="unit",
        plan_path=tmp_path / "plan.json",
    )

    assert seen == {"profile_hash": selected_profile_hash, "shard_profile_hash": selected_profile_hash}
