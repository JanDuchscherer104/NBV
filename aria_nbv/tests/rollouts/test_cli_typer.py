"""Typer CLI tests for rollout generation and shard inspection commands."""

# ruff: noqa: S101

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from aria_nbv.configs import PathConfig
from aria_nbv.oracle.pipelines import cli as rollout_cli
from aria_nbv.oracle.pipelines.campaign import CampaignOutcome, CudaRolloutCampaignConfig
from aria_nbv.oracle.pipelines.offline_vin import VinOfflineWriterConfig
from aria_nbv.utils import BaseConfig
from aria_nbv.utils.fingerprints import stable_config_hash, stable_msgspec_hash

runner = CliRunner()


def _fake_rollout_config(tmp_path: Path) -> Any:
    return SimpleNamespace(
        source=SimpleNamespace(store=SimpleNamespace(store_dir=tmp_path / "vin_offline")),
        store=SimpleNamespace(store_dir=tmp_path / "rollouts.zarr"),
        max_targets_per_sample=2,
        oracle_target_task_sampler=SimpleNamespace(max_targets_per_sample=2),
        candidate_mixture=SimpleNamespace(total_count=60),
        setup_target=lambda: SimpleNamespace(run=lambda **kwargs: None),
    )


def test_build_rollouts_dry_run_parses_config_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_source_manifest_command_builds_without_existing_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "writer.toml"
    config_path.write_text("max_samples = 1\n", encoding="utf-8")
    output_path = tmp_path / "source.json"
    source = SimpleNamespace(kind="source-fixture")
    captured: dict[str, Any] = {}
    manifest = SimpleNamespace(rows=(1, 2), split="train", source_manifest_hash="hash")
    monkeypatch.setattr(rollout_cli, "_source_config_from_writer_toml", lambda path: source)
    monkeypatch.setattr(
        rollout_cli,
        "write_rollout_source_manifest_from_config",
        lambda value, **kwargs: captured.update(source=value, **kwargs) or manifest,
    )

    result = runner.invoke(
        rollout_cli.source_manifest_app,
        ["--config-path", str(config_path), "--output-manifest", str(output_path)],
    )

    assert result.exit_code == 0
    assert captured == {"source": source, "manifest_path": output_path}
    assert "Planned Rollout Source Manifest" in result.output


def test_source_manifest_parser_accepts_writer_source_without_manifest(tmp_path: Path) -> None:
    config_path = tmp_path / "writer.toml"
    config_path.write_text(
        "[source]\nlimit = 1\n[source.store]\nstore_dir = 'local-store'\n",
        encoding="utf-8",
    )

    source = rollout_cli._source_config_from_writer_toml(config_path)

    assert source.limit == 1
    assert source.store.store_dir.name == "local-store"


def test_campaign100_v8_freezes_manifest_order_and_fresh_store_identity() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    config = tomllib.loads(
        (repo_root / ".configs/build_vin_offline_rollout_campaign100_v8.toml").read_text(encoding="utf-8")
    )
    manifest = json.loads((repo_root / ".configs/rollout_campaign100_source_manifest.json").read_text(encoding="utf-8"))
    rows = manifest["rows"]

    assert config["max_samples"] == 100
    sample_keys = [row["sample_key"] for row in rows]
    assert len(config["dataset"]["snippet_ids"]) == 100
    assert all(Path(path).suffix == ".tar" for path in config["dataset"]["snippet_ids"])
    assert config["dataset"]["snippet_key_filter"] == sample_keys
    assert config["dataset"]["scene_ids"] == [row["scene_id"] for row in rows]
    assert config["dataset"]["cache_meshes"] is False
    tar_paths = config["dataset"]["snippet_ids"]
    assert len(tar_paths) == len(sample_keys) == 100
    assert all(Path(tar).parts[-2] == row["scene_id"] for tar, row in zip(tar_paths, rows, strict=True))
    assert len(set(tar_paths)) == 100
    assert config["store"]["store_dir"] == "vin_offline_rollout_campaign100_v8_rebuilt"
    assert config["store"]["store_dir"] != "vin_offline_rollout_campaign100_v7"
    resolved = VinOfflineWriterConfig.from_toml(repo_root / ".configs/build_vin_offline_rollout_campaign100_v8.toml")
    assert len(resolved.dataset.tar_urls) == 100
    assert all(Path(tar).is_absolute() and Path(tar).is_file() for tar in resolved.dataset.tar_urls)
    assert len(resolved.dataset.snippet_key_filter) == 100
    assert [Path(tar).parts[-2] for tar in resolved.dataset.tar_urls] == [row["scene_id"] for row in rows]


def test_current_backbone_configs_explicitly_select_derived_free_input() -> None:
    """The TOML parser must preserve fail-closed defaults and current overrides."""

    repo_root = Path(__file__).resolve().parents[3]
    current = (
        ".configs/build_vin_offline_81286.toml",
        ".configs/build_vin_offline_rerun_smoke_v7.toml",
        ".configs/build_vin_offline_rollout_campaign100_v10.toml",
    )
    for relative_path in current:
        config = VinOfflineWriterConfig.from_toml(repo_root / relative_path)
        assert config.include_backbone is True
        assert config.backbone is not None
        assert config.backbone.free_input_mode == "derived"

    historical = VinOfflineWriterConfig.from_toml(repo_root / ".configs/build_vin_offline_rollout_campaign100_v8.toml")
    assert historical.include_backbone is True
    assert historical.backbone is not None
    assert historical.backbone.free_input_mode == "native"


def test_internal_preflight_uses_current_writer_store_for_foreign_manifest_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writer_path = tmp_path / "writer.toml"
    writer_path.write_text("[source.store]\nstore_dir = 'local-store'\n", encoding="utf-8")
    (tmp_path / "local-store").mkdir()
    foreign_manifest = tmp_path / "foreign" / "source.json"
    foreign_manifest.parent.mkdir()
    fake_writer = SimpleNamespace(
        source_manifest_path=foreign_manifest,
        source=SimpleNamespace(store=SimpleNamespace(store_dir=tmp_path / "local-store")),
    )
    monkeypatch.setattr(rollout_cli, "RolloutDatasetWriterConfig", SimpleNamespace(from_toml=lambda _: fake_writer))
    monkeypatch.setattr(
        "aria_nbv.rollouts.shard_manifest.read_rollout_source_manifest",
        lambda _: SimpleNamespace(rows=(SimpleNamespace(scene_id="scene"),), source_store_dir="/old/checkout/store"),
    )

    assert (
        rollout_cli._internal_preflight(
            "source-target-preflight", writer_config_path=writer_path, expected_scene_count=1
        )
        == 0
    )


def test_campaign_preflight_writes_same_phase_a_evidence_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = tmp_path / "source.json"
    manifest_path.write_text('{"source":"fixture"}\n', encoding="utf-8")
    output_path = tmp_path / "phase-a.json"
    captured: dict[str, Any] = {}

    class _Evidence:
        preflight = SimpleNamespace(go=True)

        @staticmethod
        def to_payload() -> dict[str, Any]:
            return {"artifact_sha256": "a" * 64, "preflight": {"go": True}}

    campaign = SimpleNamespace(
        config=SimpleNamespace(writer_config_path=tmp_path / "writer.toml"),
        preflight=lambda **_kwargs: None,
        candidate_family_phase_a=lambda writer, manifest, **kwargs: (
            captured.update(writer=writer, manifest=manifest, **kwargs) or _Evidence()
        ),
    )
    writer = SimpleNamespace(source_manifest_path=manifest_path)
    manifest = SimpleNamespace(rows=(1,))
    monkeypatch.setattr(rollout_cli, "_campaign", lambda _path: campaign)
    monkeypatch.setattr(rollout_cli, "_writer_config", lambda _campaign: writer)
    monkeypatch.setattr(rollout_cli, "read_rollout_source_manifest", lambda _path: manifest)

    result = runner.invoke(
        rollout_cli.campaign_app,
        [
            "preflight",
            "--config-path",
            str(tmp_path / "campaign.toml"),
            "--family-phase-a-output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert json.loads(output_path.read_text(encoding="utf-8")) == _Evidence.to_payload()
    assert captured["writer"] is writer and captured["manifest"] is manifest
    assert len(captured["source_manifest_sha256"]) == 64
    assert "candidate family Phase-A go=true" in result.output


def test_build_rollouts_rejects_partial_shard_arguments(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_campaign_status_json_delegates_to_presentation_free_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Campaign:
        config = SimpleNamespace(campaign_id="test-campaign")
        progress_calls = 0

        def read_status(self) -> Any:
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

        def progress_summary(self) -> Any:
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
                "artifact_records": [{"work_unit_hash": "orphan", "status": "orphan"}],
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
    assert payload["artifact_records"] == [{"work_unit_hash": "orphan", "status": "orphan"}]
    assert campaign.progress_calls == 1


def test_campaign_preflight_delegates_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str | tuple[str, dict[str, Any]]] = []

    class _Campaign:
        config = SimpleNamespace(writer_config_path=None)

        def preflight(self, **kwargs: Any) -> None:
            calls.append("preflight")

    monkeypatch.setattr(rollout_cli, "_campaign", lambda _path: _Campaign())
    result = runner.invoke(rollout_cli.campaign_app, ["preflight", "--config-path", str(tmp_path / "cfg.toml")])
    assert result.exit_code == 0
    assert calls == ["preflight"]


def test_campaign_plan_reports_preflight_failure_without_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Campaign:
        config = SimpleNamespace(writer_config_path=None)

        def preflight(self, **_kwargs: Any) -> None:
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
def test_campaign_run_and_resume_delegate_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str, message: str
) -> None:
    calls: list[str | tuple[str, dict[str, Any]]] = []
    output_root = tmp_path / "campaign"
    output_root.mkdir()
    (output_root / "smoke-evidence.json").write_text('{"plan_hash":"plan"}\n')

    class _Campaign:
        config = SimpleNamespace(output_root=output_root, writer_config_path=None)

        def load_plan(self, path: Any) -> Any:
            return SimpleNamespace(plan_hash="plan")

        def preflight(self, *args: Any, **kwargs: Any) -> Any:
            calls.append("preflight")
            return SimpleNamespace(ok=True)

        def smoke_evidence(self, plan: Any) -> Any:
            return {"plan_hash": plan.plan_hash, "result": {"outcome": "succeeded", "validated": True}}

        def run(self, plan: Any, **kwargs: Any) -> None:
            calls.append((plan.plan_hash, kwargs))

    monkeypatch.setattr(rollout_cli, "_campaign", lambda _path: _Campaign())
    result = runner.invoke(rollout_cli.campaign_app, [command, "--config-path", "cfg.toml", "--plan-path", "plan.json"])
    assert result.exit_code == 0
    assert message in result.stdout
    assert len(calls) == 1
    assert "preflight" not in calls


def test_campaign_worker_binds_selected_unit_profile_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    @dataclass(frozen=True)
    class _Entry:
        profile_hash: str = ""
        writer_config_hash: str = ""

    class _WriterConfig(BaseConfig):
        writer: str = "canonical"

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

        def load_plan(self, _path: Any) -> Any:
            return plan

        def shard_entry_for_unit(self, _plan: Any, _unit: Any) -> Any:
            return _Entry()

        def adapt_work_unit(self, _unit: Any, **kwargs: Any) -> Any:
            seen["profile_hash"] = kwargs["profile_hash"]
            return writer_cfg, replace(kwargs["shard_entry"], profile_hash=kwargs["profile_hash"])

        def preflight(self, **_kwargs: Any) -> Any:
            return None

    @dataclass(frozen=True)
    class _Result:
        outcome: str = "skipped"
        skipped: bool = True
        success_path: Path = Path("success")
        owner_path: Path = Path("owner")

    monkeypatch.setattr(rollout_cli, "_campaign", lambda _path: _Campaign())
    monkeypatch.setattr(
        "aria_nbv.oracle.pipelines.cli.RolloutDatasetWriterConfig.from_toml",
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


def test_campaign_plan_reads_rows_from_manifest_envelope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source.json"
    source.write_text("{}\n")
    captured: dict[str, Any] = {}
    reviewed_manifest = SimpleNamespace(to_jsonable=lambda: {"manifest": "canonical"})
    writer = SimpleNamespace(source_manifest_path=source, model_dump_jsonable=lambda: {"writer": "canonical"})

    class _Campaign:
        config = SimpleNamespace(campaign_id="campaign")

        def preflight(self, **_kwargs: Any) -> Any:
            return None

        def plan(self, rows: Any, **kwargs: Any) -> Any:
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

        def audit_source_manifest(self, writer_config: Any, manifest: Any) -> Any:
            captured.update(writer_config=writer_config, manifest=manifest)
            return [{"scene_id": "s0"}]

        def write_plan(self, plan: Any, path: Any = None) -> Any:
            return path

        def write_admission_audit(self, rows: Any, **kwargs: Any) -> Any:
            captured.update(admission_rows=rows, admission_kwargs=kwargs)
            return source

        def append_event(self, _event: Any) -> Any:
            return None

        def read_events(self, **_kwargs: Any) -> Any:
            return []

        def status(self, plan: Any, *, stage: Any) -> Any:
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

        def write_status(self, status: Any) -> Any:
            captured["status"] = status
            return None

        def progress_summary(self) -> Any:
            return vars(captured["status"])

        def model_dump_jsonable(self) -> Any:
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


def test_canonical_campaign_root_and_smoke_plan_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = CudaRolloutCampaignConfig.from_toml(
        Path(__file__).resolve().parents[3] / ".configs/build_rollouts_v1_cuda_campaign.toml"
    )
    assert (
        config.output_root
        == (PathConfig().offline_cache_dir / "rollout_supervision" / "campaigns" / "cuda-rollouts-v1").resolve()
    )

    output_root = tmp_path / "cuda-rollouts-v1"
    output_root.mkdir()
    plan_path = output_root / "plan.json"
    plan_path.write_text("{}\n", encoding="utf-8")
    seen = {}

    class _Campaign:
        config = SimpleNamespace(output_root=output_root, writer_config_path=None)

        def preflight(self, **kwargs: Any) -> None:
            seen["preflight_plan_path"] = kwargs["plan_path"]

        def load_plan(self, path: Any) -> Any:
            seen["load_plan_path"] = path
            return SimpleNamespace()

        def smoke(self, plan: Any, **kwargs: Any) -> None:
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
