"""Typer CLI tests for rollout generation and shard inspection commands."""

# ruff: noqa: S101

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from aria_nbv.oracle.pipelines import cli as rollout_cli
from aria_nbv.oracle.pipelines.campaign import CampaignOutcome, CudaRolloutCampaignConfig
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


def test_campaign_module_entrypoint_survives_missing_console_script() -> None:
    environment = os.environ.copy()
    environment["PATH"] = ""

    result = subprocess.run(
        [sys.executable, "-m", "aria_nbv.oracle.pipelines.cli", "--campaign", "--help"],
        capture_output=True,
        check=False,
        env=environment,
        text=True,
    )

    assert result.returncode == 0
    assert "nbv-rollout-campaign" in result.stdout


def test_campaign_status_json_delegates_to_presentation_free_reader(tmp_path, monkeypatch) -> None:
    class _Campaign:
        config = SimpleNamespace(campaign_id="test-campaign")
        progress_calls = 0

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
            self.progress_calls += 1
            return {
                "counts": {
                    "succeeded": 1,
                    "failed": 1,
                    "skipped": 0,
                    "insufficient_support": 0,
                    "timed_out": 0,
                    "pending": 0,
                },
                "active_pid": 4321,
                "active_process_group": 4321,
                "validated_artifacts": [{"work_unit_hash": "unit"}],
            }

    campaign = _Campaign()
    monkeypatch.setattr(rollout_cli, "_campaign", lambda _path: campaign)
    result = runner.invoke(rollout_cli.campaign_app, ["status", "--config-path", str(tmp_path / "cfg.toml"), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "completed_with_failures"
    assert payload["counts"]["failed"] == 1
    assert payload["active_pid"] == 4321
    assert payload["active_process_group"] == 4321
    assert payload["validated_artifacts"] == [{"work_unit_hash": "unit"}]
    assert campaign.progress_calls == 1


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


def test_campaign_plan_reports_preflight_failure_without_traceback(tmp_path, monkeypatch) -> None:
    class Campaign:
        config = SimpleNamespace(writer_config_path=None)

        def preflight(self, **_kwargs):
            raise RuntimeError("source-target preflight requires 100 scenes; found 5")

    monkeypatch.setattr(rollout_cli, "_campaign", lambda _path: Campaign())
    monkeypatch.setattr(rollout_cli, "_writer_config", lambda _campaign: None)

    result = runner.invoke(rollout_cli.campaign_app, ["plan", "--config-path", str(tmp_path / "cfg.toml")])

    assert result.exit_code == 2
    assert "source-target preflight requires 100 scenes; found 5" in result.output
    assert "Traceback" not in result.output


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
            calls.append("preflight")
            return SimpleNamespace(ok=True)

        def smoke_evidence(self, plan):
            return {"plan_hash": plan.plan_hash, "result": {"outcome": "succeeded", "validated": True}}

        def run(self, plan, **kwargs):
            calls.append((plan.plan_hash, kwargs))

    monkeypatch.setattr(rollout_cli, "_campaign", lambda _path: _Campaign())
    result = runner.invoke(rollout_cli.campaign_app, [command, "--config-path", "cfg.toml", "--plan-path", "plan.json"])
    assert result.exit_code == 0
    assert message in result.stdout
    assert len(calls) == 1
    assert "preflight" not in calls


def test_campaign_worker_binds_selected_unit_profile_hash(tmp_path, monkeypatch, capsys) -> None:
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
        outcome: str = "skipped"
        skipped: bool = True
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
    payload = json.loads(capsys.readouterr().out)
    assert payload["outcome"] == "skipped"
    assert payload["validated"] is True
    assert payload["leaf_evidence"]["success_path"] == "success"


def test_campaign_plan_reads_rows_from_manifest_envelope(tmp_path, monkeypatch) -> None:
    source = tmp_path / "source.json"
    source.write_text("{}\n")
    captured = {}
    reviewed_manifest = SimpleNamespace(to_jsonable=lambda: {"manifest": "canonical"})
    writer = SimpleNamespace(source_manifest_path=source, model_dump_jsonable=lambda: {"writer": "canonical"})

    class _Campaign:
        config = SimpleNamespace(campaign_id="campaign")

        def preflight(self, **_kwargs):
            return None

        def plan(self, rows, **kwargs):
            captured.update(rows=rows, kwargs=kwargs)
            return SimpleNamespace(
                plan_hash="plan",
                config_hash="config",
                writer_config_hash="writer",
                source_manifest_hash="source",
                admission_audit_hash="audit",
                work_units=(SimpleNamespace(),),
                to_jsonable=lambda: {"plan_hash": "plan"},
            )

        def audit_source_manifest(self, writer_config, manifest):
            captured.update(writer_config=writer_config, manifest=manifest)
            return [{"scene_id": "s0"}]

        def write_plan(self, plan, path=None):
            return path

        def write_admission_audit(self, rows, **kwargs):
            captured.update(admission_rows=rows, admission_kwargs=kwargs)
            return source

        def append_event(self, _event):
            return None

        def status(self, plan, *, stage):
            captured.update(status_plan=plan, status_stage=stage)
            return SimpleNamespace(
                state=stage,
                counts={**{outcome.value: 0 for outcome in CampaignOutcome}, "pending": 1},
                plan_hash=plan.plan_hash,
                updated_at="now",
                current_work_unit=None,
                current_target_id=None,
                current_profile=None,
                current_stage=stage,
                elapsed_seconds=0.0,
                latest_failure_reason=None,
                active_pid=None,
                active_process_group=None,
                validated_artifacts=[],
                campaign_id="campaign",
                config_hash="config",
            )

        def write_status(self, status):
            captured["status"] = status
            return None

        def progress_summary(self):
            return vars(captured["status"])

        def model_dump_jsonable(self):
            return {}

        utc_now = staticmethod(lambda: SimpleNamespace(isoformat=lambda: "now"))

    monkeypatch.setattr(rollout_cli, "_campaign", lambda _path: _Campaign())
    monkeypatch.setattr(rollout_cli, "_writer_config", lambda _campaign: writer)
    monkeypatch.setattr(rollout_cli, "read_rollout_source_manifest", lambda _path: reviewed_manifest)
    result = runner.invoke(
        rollout_cli.campaign_app, ["plan", "--config-path", "cfg.toml", "--source-manifest", str(source)]
    )
    assert result.exit_code == 0
    assert captured["rows"] == [{"scene_id": "s0"}]
    assert captured["writer_config"] is writer
    assert captured["manifest"] is reviewed_manifest
    assert captured["admission_rows"] == [{"scene_id": "s0"}]
    assert captured["admission_kwargs"]["expected_hash"] == "audit"
    assert captured["status_plan"].plan_hash == "plan"
    assert captured["status_stage"] == "planned"
    assert captured["status"].state == "planned"
    assert captured["status"].current_stage == "planned"
    assert captured["status"].campaign_id == "campaign"
    assert captured["status"].config_hash == "config"
    assert captured["status"].counts["pending"] == 1
    assert set(captured["status"].counts) == {outcome.value for outcome in CampaignOutcome}

    status_result = runner.invoke(rollout_cli.campaign_app, ["status", "--config-path", "cfg.toml", "--json"])
    assert status_result.exit_code == 0
    status_payload = json.loads(status_result.stdout)
    assert status_payload["state"] == "planned"
    assert status_payload["current_stage"] == "planned"


def test_canonical_campaign_root_and_smoke_plan_resolution(tmp_path, monkeypatch) -> None:
    config = CudaRolloutCampaignConfig.from_toml(
        Path(__file__).resolve().parents[3] / ".configs/build_rollouts_v1_cuda_campaign.toml"
    )
    assert config.output_root == Path(".campaign/cuda-rollouts-v1")

    output_root = tmp_path / "cuda-rollouts-v1"
    output_root.mkdir()
    plan_path = output_root / "plan.json"
    plan_path.write_text("{}\n", encoding="utf-8")
    seen = {}

    class _Campaign:
        config = SimpleNamespace(output_root=output_root, writer_config_path=None)

        def preflight(self, **kwargs):
            seen["preflight_plan_path"] = kwargs["plan_path"]

        def load_plan(self, path):
            seen["load_plan_path"] = path
            return SimpleNamespace()

        def smoke(self, plan, **kwargs):
            seen["smoke_plan_path"] = kwargs["plan_path"]

    monkeypatch.setattr(rollout_cli, "_campaign", lambda _path: _Campaign())
    config_path = tmp_path / "cfg.toml"
    config_path.write_text("campaign_id = 'test'\n", encoding="utf-8")
    result = runner.invoke(rollout_cli.campaign_app, ["smoke", "--config-path", str(config_path)])

    assert result.exit_code == 0
    assert seen == {
        "preflight_plan_path": plan_path,
        "load_plan_path": plan_path,
        "smoke_plan_path": plan_path,
    }
