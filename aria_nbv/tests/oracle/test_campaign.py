"""Non-CUDA contract tests for the campaign orchestration owner."""

import json
import signal
import subprocess
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from aria_nbv.oracle.pipelines.campaign import (
    CampaignOutcome,
    CampaignProcessRunner,
    CampaignStatus,
    CampaignTimeoutError,
    CampaignWorkUnit,
    CudaRolloutCampaign,
    CudaRolloutCampaignConfig,
)
from aria_nbv.oracle.pipelines.rollout_dataset import RolloutDatasetWriterConfig
from aria_nbv.rollouts.qh_reader import QhRolloutReader
from aria_nbv.rollouts.shard_manifest import build_rollout_split_manifest_hash
from aria_nbv.rollouts.trace import TargetLineage
from aria_nbv.rollouts.zarr_store import (
    LINEAGE_TABLE,
    ROLLOUT_TABLE,
    ROLLOUT_ZARR_SCHEMA_VERSION,
    STEP_TABLE,
    write_rollout_zarr_store,
)
from aria_nbv.targets.descriptor import TargetDescriptor
from aria_nbv.targets.selection import ObservedTargetDescriptor
from aria_nbv.utils.fingerprints import stable_config_hash, stable_msgspec_hash
from tests.rollout_fixtures import build_rollout_records

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_config_factory_returns_campaign_target():
    config = CudaRolloutCampaignConfig()
    assert isinstance(config.setup_target(), CudaRolloutCampaign)


def test_reviewed_profile_components_and_worker_json(tmp_path):
    campaign = _campaign(tmp_path)
    expected = {
        "realistic_core_60": (("forward_local", 24), ("target_bearing_local", 24), ("lateral_target_bypass", 12)),
        "rich_local_60": (
            ("target_bearing_local", 18),
            ("forward_local", 18),
            ("lateral_target_bypass", 12),
            ("local_refinement", 6),
            ("revisit_backtrack", 6),
        ),
        "radial_backtrack_60": (
            ("radial_towards_target_bearing", 20),
            ("radial_away_target_bearing", 20),
            ("revisit_backtrack", 15),
            ("target_point_anchor", 5),
        ),
        "free_shell_upper_bound_60": (("upper_bound_free_shell", 60),),
    }
    for name, components in expected.items():
        assert campaign.profile_components(name) == components
        assert sum(n for _, n in components) == 60
    assert campaign.parse_worker_json('{"outcome":"skipped"}')["outcome"] == "skipped"
    assert (
        campaign.parse_worker_json('{"outcome":"insufficient_support","reason":"9<10"}')["outcome"]
        == "insufficient_support"
    )
    with pytest.raises(ValueError):
        campaign.parse_worker_json('{"outcome":"succeeded"}')


def test_all_profiles_adapt_into_real_writer_candidate_mixture(tmp_path):
    campaign = _campaign(tmp_path)
    writer = RolloutDatasetWriterConfig.from_toml(REPO_ROOT / ".configs/build_rollouts_v1_realistic.toml")
    # This test exercises the legacy in-memory adapter seam. Production worker
    # tests retain the canonical manifest and verify exact sample binding.
    writer = writer.model_copy(update={"source_manifest_path": None})
    expected_modes = {
        "forward_local": "forward_rig",
        "target_bearing_local": "target_point",
        "lateral_target_bypass": "target_point",
        "local_refinement": "radial_towards",
        "revisit_backtrack": "forward_rig",
        "radial_towards_target_bearing": "radial_towards",
        "radial_away_target_bearing": "radial_away",
        "target_point_anchor": "target_point",
        "upper_bound_free_shell": "radial_away",
    }
    expected_positions = {
        "forward_local": "forward_local",
        "target_bearing_local": "target_bearing_local",
        "lateral_target_bypass": "lateral_target_bypass",
        "local_refinement": "local_refinement",
        "revisit_backtrack": "revisit_backtrack",
        "radial_towards_target_bearing": "target_bearing_local",
        "radial_away_target_bearing": "target_bearing_local",
        "target_point_anchor": "target_bearing_local",
        "upper_bound_free_shell": "upper_bound_free_shell",
    }
    for profile in campaign.config.profiles:
        unit = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source").work_units[
            0
        ]
        unit = unit.__class__(
            unit.campaign_id,
            unit.sample_key,
            unit.target_id,
            profile.name,
            unit.work_unit_hash,
            unit.explicit_target_hash,
            unit.target_audit_hash,
            unit.source_row_index,
            unit.explicit_target_config,
            unit.source_row_payload,
        )
        adapted, _ = campaign.adapt_work_unit(unit, writer_config=writer, shard_entry=SimpleNamespace())
        components = adapted.candidate_mixture.components
        assert [(c.name, c.count, c.view_mode.value, c.position_mode.value) for c in components] == [
            (name, count, expected_modes[name], expected_positions[name]) for name, count in profile.components
        ]
        assert [r.name for r in adapted.recipes] == ["temperature_softmax_h8_t0.5"]
        assert [r.policy.selection_temperature for r in adapted.recipes] == [0.5]


def _campaign(tmp_path):
    base = CudaRolloutCampaignConfig(output_root=tmp_path)
    values = base.model_dump()
    values.update(expected_scene_count=2, paired_panel_scene_count=1, profiles=base.profiles)
    config = CudaRolloutCampaignConfig.model_construct(**values)
    return CudaRolloutCampaign(config)


def _append_pre_run_prefix(campaign, plan):
    for kind in ("source_selection", "plan_ready", "preflight_passed", "smoke_passed"):
        campaign.append_event(campaign._event(plan, kind))


def _append_campaign_started(campaign, plan):
    _append_pre_run_prefix(campaign, plan)
    campaign.append_event(campaign._event(plan, "campaign_started"))


def test_canonical_worker_argv_carries_writer_config_path():
    config = CudaRolloutCampaignConfig.from_toml(REPO_ROOT / ".configs/build_rollouts_v1_cuda_campaign.toml")
    campaign = config.setup_target()
    unit = CampaignWorkUnit("cuda-rollouts-v1", "sample", "target", "realistic_core_60", "unit")
    argv = campaign.worker_argv(Path("plan.json"), unit)
    assert "--writer-config-path" in argv
    assert ".configs/build_rollouts_v1_cuda_campaign_writer.toml" in argv

    writer = RolloutDatasetWriterConfig.from_toml(REPO_ROOT / config.writer_config_path)
    assert writer.max_samples == writer.source.limit == 100
    assert writer.source_manifest_path == REPO_ROOT / ".configs/rollout_campaign100_source_manifest.json"
    assert writer.source.store.store_dir.name == "vin_offline_rollout_campaign100_v8"
    assert writer.min_valid_root_candidates == 10
    assert {
        str(writer.source.map_location),
        str(writer.candidate_mixture.base.device),
        str(writer.target_scorer.depth.device),
        str(writer.target_scorer.depth.renderer.device),
    } == {"cuda"}


def test_canonical_campaign_freezes_accepted_rich_batch_profile():
    config = CudaRolloutCampaignConfig.from_toml(REPO_ROOT / ".configs/build_rollouts_v1_cuda_campaign.toml")
    writer = RolloutDatasetWriterConfig.from_toml(REPO_ROOT / config.writer_config_path)

    assert config.frozen_profile == "rich_local_60"
    assert writer.target_scorer.depth.renderer.max_views_per_batch == 4


@pytest.mark.parametrize("device", ["cpu", "mps", "xpu", "meta"])
def test_nested_non_cuda_device_is_rejected_before_campaign_files(tmp_path, device):
    campaign = _campaign(tmp_path)
    with pytest.raises(RuntimeError, match="device"):
        campaign.preflight(
            cuda_probe=lambda: SimpleNamespace(ok=True), nested_configs=[{"renderer": {"device": device}}]
        )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "nested",
    [
        {"source": {"map_location": "cpu"}},
        {"source": {"map_location": "mps"}},
        {"candidate_generation": {"collision_backend": "trimesh"}},
    ],
)
def test_nested_source_or_collision_backend_rejected_before_campaign_files(tmp_path, nested):
    campaign = _campaign(tmp_path)
    with pytest.raises(RuntimeError):
        campaign.preflight(cuda_probe=lambda: SimpleNamespace(ok=True), nested_configs=[nested])
    assert not list(tmp_path.iterdir())


def test_structured_cuda_probe_rejects_missing_pytorch3d_before_files(tmp_path):
    campaign = _campaign(tmp_path)
    probe = SimpleNamespace(ok=True, cuda_available=True, pytorch3d_available=False)
    with pytest.raises(RuntimeError, match="PyTorch3D"):
        campaign.preflight(cuda_probe=lambda: probe)
    assert not list(tmp_path.iterdir())


def test_bare_ok_probe_is_rejected_before_files(tmp_path):
    campaign = _campaign(tmp_path)
    with pytest.raises(RuntimeError, match="prove|availability"):
        campaign.preflight(cuda_probe=lambda: SimpleNamespace(ok=True))
    assert not list(tmp_path.iterdir())


def test_torch_cpu_device_object_is_rejected_before_files(tmp_path):
    torch = pytest.importorskip("torch")
    campaign = _campaign(tmp_path)
    with pytest.raises(RuntimeError, match="device"):
        campaign.preflight(
            cuda_probe=lambda: SimpleNamespace(ok=True), nested_configs=[{"device": torch.device("cpu")}]
        )
    assert not list(tmp_path.iterdir())


def test_explicit_target_payload_identity_mismatch_rejected_before_plan(tmp_path):
    campaign = _campaign(tmp_path)
    row = _row("s0", "k", "t")
    row.explicit_target_config["target_id"] = "different-target"
    with pytest.raises(ValueError, match="malformed explicit_target_config"):
        campaign.plan([row, _row("s1", "k1", "t1")], source_manifest_hash="source")


def test_explicit_target_iou_equal_threshold_is_not_admitted(tmp_path):
    campaign = _campaign(tmp_path)
    row = _row("s0", "k", "t")
    row.oriented_iou = 0.20
    row.admitted = False
    with pytest.raises(ValueError, match="expected 2 scenes"):
        campaign.plan([row, _row("s1", "k1", "t1")], source_manifest_hash="source")


def test_nested_cuda_device_one_is_rejected_for_serial_worker(tmp_path):
    campaign = _campaign(tmp_path)
    with pytest.raises(RuntimeError, match="CUDA"):
        campaign.preflight(cuda_probe=lambda: SimpleNamespace(ok=True), nested_configs=[{"device": "cuda:1"}])
    assert not list(tmp_path.iterdir())


def test_unavailable_cuda_probe_fails_before_files_or_events(tmp_path):
    campaign = _campaign(tmp_path)
    with pytest.raises(RuntimeError, match="preflight"):
        campaign.preflight(cuda_probe=lambda: SimpleNamespace(ok=False))
    assert not list(tmp_path.iterdir())


def test_missing_pytorch3d_fails_before_files(monkeypatch, tmp_path):
    import builtins

    campaign = _campaign(tmp_path)
    original_import = builtins.__import__

    def reject_pytorch3d(name, *args, **kwargs):
        if name == "pytorch3d":
            raise ImportError("synthetic missing pytorch3d")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_pytorch3d)
    with pytest.raises(RuntimeError, match="PyTorch3D"):
        campaign.preflight()
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(("count", "reason"), [(9, "insufficient_root_support:9<10"), (10, None)])
def test_root_support_boundary_is_strict_and_does_not_reuse_root_shell(count, reason):
    writer = RolloutDatasetWriterConfig(min_valid_root_candidates=10).setup_target()
    assert writer.root_support_preflight(count) == reason


def test_recipe_suite_rejects_farthest_policy_and_order_drift():
    base = CudaRolloutCampaignConfig()
    profiles = [p.model_dump() for p in base.profiles]
    profiles[0]["recipes"][0] = {
        "name": "farthest_from_history",
        "policy": "farthest_from_history",
        "horizon": 5,
        "branch": 2,
        "beam": 2,
    }
    with pytest.raises(ValueError, match="recipe"):
        CudaRolloutCampaignConfig(profiles=profiles)


@pytest.mark.parametrize("recipe_mutation", [lambda recipes: [], lambda recipes: recipes[:-1]])
def test_recipe_suite_rejects_missing_or_empty_recipe_suite(recipe_mutation):
    profiles = [p.model_dump() for p in CudaRolloutCampaignConfig().profiles]
    profiles[0]["recipes"] = recipe_mutation(profiles[0]["recipes"])
    with pytest.raises(ValueError, match="recipe"):
        CudaRolloutCampaignConfig(profiles=profiles)


def test_recipe_suite_has_exact_policy_horizon_branch_beam_and_temperature():
    expected = [("temperature_softmax", 8, 1, 1, 1.0)]
    for profile in CudaRolloutCampaignConfig().profiles:
        assert [
            (r["policy"], r["horizon"], r["branch"], r["beam"], r.get("temperature", 1.0)) for r in profile.recipes
        ] == expected


def test_worker_json_rejects_unvalidated_success_and_preserves_non_success():
    assert CudaRolloutCampaign.parse_worker_json('{"outcome":"skipped"}')["outcome"] == "skipped"
    assert (
        CudaRolloutCampaign.parse_worker_json('{"outcome":"insufficient_support"}')["outcome"] == "insufficient_support"
    )
    with pytest.raises(ValueError, match="validated"):
        CudaRolloutCampaign.parse_worker_json('{"outcome":"succeeded","validated":false}')
    assert (
        CudaRolloutCampaign.parse_worker_json(
            'writer progress\nrenderer progress\n{"outcome":"succeeded","validated":true}\n'
        )["validated"]
        is True
    )


@pytest.mark.parametrize("outcome", ["skipped", "insufficient_support"])
def test_smoke_rejects_non_success_worker_outcomes(tmp_path, outcome):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    with pytest.raises(RuntimeError, match="structured succeeded"):
        campaign.smoke(plan, worker=lambda _unit: {"outcome": outcome})
    assert not (tmp_path / "smoke-evidence.json").exists()


def test_smoke_writes_structured_succeeded_evidence(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    selected = []
    result = campaign.smoke(
        plan,
        worker=lambda unit: selected.append(unit) or {"outcome": "succeeded", "validated": True},
    )
    evidence = json.loads((tmp_path / "smoke-evidence.json").read_text())
    assert result["validated"] is True
    assert selected == [plan.work_units[0]]
    assert evidence["plan_hash"] == plan.plan_hash
    assert evidence["result"] == result


def test_time_budget_blocks_after_promotion_and_resume_skips_completed_unit(tmp_path, monkeypatch):
    campaign = _campaign(tmp_path)
    monkeypatch.setattr(campaign, "_require_validated_terminal_shard", lambda *_args: {"validation": "passed"})
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    _append_pre_run_prefix(campaign, plan)
    ticks = iter([0.0, 0.0, 0.0, 2.0, 2.0, 2.0])
    campaign.clock = lambda: next(ticks, 2.0)
    calls = []
    first = campaign._run_claimed(
        plan,
        worker=lambda unit: calls.append(unit.work_unit_hash) or {"outcome": "succeeded", "validated": True},
        claim={"claim_hash": "first"},
        time_budget_seconds=1.0,
    )
    assert calls == [plan.work_units[0].work_unit_hash]
    assert first[0]["outcome"] == "succeeded"
    assert campaign.read_status(plan=plan).state == "blocked"
    assert campaign.read_status(plan=plan).bounded_error == "time budget exhausted"

    campaign.clock = lambda: 10.0
    resumed = campaign._run_claimed(
        plan,
        worker=lambda unit: calls.append(unit.work_unit_hash) or {"outcome": "succeeded", "validated": True},
        claim={"claim_hash": "second"},
    )
    assert calls == [plan.work_units[0].work_unit_hash, plan.work_units[1].work_unit_hash]
    assert [result["outcome"] for result in resumed] == ["succeeded", "succeeded"]


def test_campaign_status_round_trip_and_schema_rejection():
    from dataclasses import asdict

    status = CampaignStatus(
        "running",
        {**{outcome.value: 0 for outcome in CampaignOutcome}, "pending": 2},
        "plan",
        "now",
        current_stage="worker",
    )
    payload = json.loads(json.dumps(asdict(status)))
    assert CampaignStatus.from_jsonable(payload) == status
    payload["schema_version"] = "campaign-status-v0"
    with pytest.raises(ValueError, match="schema version"):
        CampaignStatus.from_jsonable(payload)


def test_read_status_rejects_stale_config_and_plan_identity(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    status = campaign.status(plan, [])
    path = campaign.write_status(status)
    payload = json.loads(path.read_text())
    payload["config_hash"] = "stale"
    path.write_text(json.dumps(payload) + "\n")
    with pytest.raises(ValueError, match="invalid campaign status"):
        campaign.read_status(plan=plan)

    path = campaign.write_status(status)
    other_plan = replace(plan, plan_hash="other")
    with pytest.raises(ValueError, match="invalid campaign status"):
        campaign.read_status(plan=other_plan)


@pytest.mark.parametrize(
    ("field", "tampered"),
    [
        ("current_target_id", "other-target"),
        ("current_profile", "other-profile"),
        ("current_stage", "promotion"),
        ("active_pid", 9999),
        ("active_process_group", 9999),
        ("active_started_at", "2099-01-01T00:00:00+00:00"),
    ],
)
def test_read_status_rejects_tampered_active_event_projection(tmp_path, field, tampered):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    unit = plan.work_units[0]
    _append_campaign_started(campaign, plan)
    campaign.append_event(campaign._event(plan, "target_profile", unit=unit, stage=unit.profile))
    campaign.append_event(campaign._event(plan, "root_preflight", unit=unit, stage="preflight"))
    started = campaign._event(plan, "unit_started", unit=unit, stage="worker", pid=4321, process_group=4321)
    campaign.append_event(started)
    path = campaign.write_status(
        campaign.status(
            plan,
            current_unit=unit,
            stage="worker",
            active_pid=started.pid,
            active_process_group=started.process_group,
            active_started_at=started.timestamp,
        )
    )
    payload = json.loads(path.read_text())
    payload[field] = tampered
    path.write_text(json.dumps(payload) + "\n")

    with pytest.raises(ValueError, match="invalid campaign status"):
        campaign.read_status(plan=plan)


def test_preflight_stage_uses_named_internal_subprocess(monkeypatch, tmp_path):
    calls = []

    class Runner:
        def run_stage(self, argv, **kwargs):
            calls.append((tuple(argv), kwargs["timeout"]))
            return 0, "", ""

    campaign = _campaign(tmp_path)
    campaign.process_runner = Runner()
    monkeypatch.setattr("aria_nbv.oracle.pipelines.campaign.sys.executable", "/python")
    campaign.preflight = lambda *args, **kwargs: None
    for stage in ("cuda-rasterizer-preflight", "source-target-preflight"):
        campaign.run_preflight_stage(
            ("/python", "-m", "aria_nbv.oracle.pipelines.cli", "--internal-preflight", stage), stage_name=stage
        )
    assert [call[0][-1] for call in calls] == ["cuda-rasterizer-preflight", "source-target-preflight"]
    assert all(timeout == 120 for _, timeout in calls)


def test_preflight_stage_reports_terminal_child_reason_without_traceback(tmp_path):
    class Runner:
        def run_stage(self, argv, **kwargs):
            del argv, kwargs
            return 1, b"", b"Traceback (most recent call last):\n  child frame\nRuntimeError: found only 5 scenes\n"

    campaign = _campaign(tmp_path)
    campaign.process_runner = Runner()

    with pytest.raises(RuntimeError, match="^found only 5 scenes$"):
        campaign.run_preflight_stage(("python", "probe"), stage_name="source-target-preflight")


def test_status_exposes_current_unit_profile_stage_and_failure_reason(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    status = campaign.status(
        plan,
        [{"outcome": "failed", "error": "timeout"}],
        current_unit=plan.work_units[0],
        stage="worker",
        elapsed_seconds=2.5,
    )
    assert status.current_work_unit == plan.work_units[0].work_unit_hash
    assert status.current_profile == plan.work_units[0].profile
    assert status.current_stage == "worker"
    assert status.latest_failure_reason == "timeout"


def test_status_separates_active_and_last_work_unit(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    active = campaign.status(plan, current_unit=plan.work_units[0], stage="worker")
    terminal = campaign.status(plan, current_unit=plan.work_units[0], stage="failed")
    assert active.current_work_unit == plan.work_units[0].work_unit_hash
    assert active.last_work_unit is None
    assert terminal.current_work_unit is None
    assert terminal.last_work_unit == plan.work_units[0].work_unit_hash


def test_status_preserves_last_terminal_identity_across_resume_and_completion(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    first, second = plan.work_units[:2]

    prestart = campaign.status(plan, stage="planned")
    assert prestart.current_work_unit is None
    assert prestart.last_work_unit is None

    _append_campaign_started(campaign, plan)
    campaign.write_status(campaign.status(plan, [{"outcome": "failed"}], current_unit=first, stage="failed"))
    resumed = campaign.status(plan, [{"outcome": "failed"}], current_unit=second, stage="worker")
    assert resumed.current_work_unit == second.work_unit_hash
    assert resumed.last_work_unit == first.work_unit_hash

    campaign.write_status(
        campaign.status(
            plan,
            [{"outcome": "failed"}, {"outcome": "insufficient_support"}],
            last_unit=second,
            stage="worker",
        )
    )
    completed = campaign.status(
        plan,
        [{"outcome": "failed"}] * (len(plan.work_units) - 1) + [{"outcome": "insufficient_support"}],
        stage="terminal",
    )
    assert completed.current_work_unit is None
    assert completed.last_work_unit == second.work_unit_hash


def test_status_rejects_negative_counts_and_divergent_event_counts(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    status = campaign.status(plan, stage="running")
    payload = asdict(status)
    payload["counts"]["pending"] = -1
    with pytest.raises(ValueError, match="non-negative"):
        CampaignStatus.from_jsonable(payload)
    _append_campaign_started(campaign, plan)
    campaign.append_event(campaign._event(plan, "unit_failed", unit=plan.work_units[0], outcome="failed"))
    payload = asdict(status)
    payload["counts"]["pending"] = 0
    campaign.write_status(CampaignStatus.from_jsonable(payload))
    with pytest.raises(ValueError, match="invalid campaign status"):
        campaign.read_status(plan=plan)


def _append_unit_events(campaign, plan, unit, outcome):
    campaign.append_event(campaign._event(plan, "target_profile", unit=unit, stage=unit.profile))
    campaign.append_event(campaign._event(plan, "root_preflight", unit=unit, stage="preflight"))
    campaign.append_event(campaign._event(plan, "unit_started", unit=unit, stage="worker"))
    campaign.append_event(campaign._event(plan, "recipe_worker", unit=unit, stage=unit.profile))
    if outcome == "insufficient_support":
        campaign.append_event(
            campaign._event(
                plan,
                "root_preflight_insufficient",
                unit=unit,
                outcome=outcome,
                stage="preflight",
            )
        )
    elif outcome in {"succeeded", "skipped"}:
        campaign.append_event(
            campaign._event(plan, "root_preflight_completed", unit=unit, outcome=outcome, stage="preflight")
        )
        campaign.append_event(
            campaign._event(plan, "recipe_stage_completed", unit=unit, outcome=outcome, stage=unit.profile)
        )
        campaign.append_event(
            campaign._event(
                plan,
                "unit_promoted" if outcome == "succeeded" else "unit_validated_skip",
                unit=unit,
                outcome=outcome,
                stage="promotion",
            )
        )
    campaign.append_event(campaign._event(plan, f"unit_{outcome}", unit=unit, outcome=outcome))


def test_read_status_accepts_planning_prefix_and_blocked_resume_lifecycle(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    _append_campaign_started(campaign, plan)
    _append_unit_events(campaign, plan, plan.work_units[0], "failed")
    campaign.append_event(campaign._event(plan, "campaign_blocked", outcome="blocked"))
    campaign.append_event(campaign._event(plan, "campaign_resumed"))
    results = []
    for unit in plan.work_units:
        outcome = "failed" if unit is not plan.work_units[-1] else "insufficient_support"
        _append_unit_events(campaign, plan, unit, outcome)
        results.append({"outcome": outcome})
    campaign.append_event(campaign._event(plan, "campaign_finished"))
    campaign.write_status(campaign.status(plan, results, stage="terminal", last_unit=plan.work_units[-1]))

    status = campaign.read_status(plan=plan)
    assert status.state == "completed_with_failures"
    assert status.counts["pending"] == 0
    assert status.last_work_unit == plan.work_units[-1].work_unit_hash


def test_public_status_lifecycle_rebuilds_exact_pre_run_state_from_events(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    campaign.append_event(campaign._event(plan, "source_selection"))
    campaign.append_event(campaign._event(plan, "plan_ready"))

    for state in ("planned", "preflight_passed", "smoke_passed"):
        campaign.write_status(campaign.status(plan, stage=state))
        assert campaign.read_status(plan=plan).state == state

    assert [event.kind for event in campaign.read_events(plan=plan)] == [
        "source_selection",
        "plan_ready",
        "preflight_passed",
        "smoke_passed",
    ]


def test_write_status_rejects_smoke_passed_to_planned_without_mutation(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    campaign.append_event(campaign._event(plan, "source_selection"))
    campaign.append_event(campaign._event(plan, "plan_ready"))
    campaign.write_status(campaign.status(plan, stage="planned"))
    campaign.write_status(campaign.status(plan, stage="preflight_passed"))
    status_path = campaign.write_status(campaign.status(plan, stage="smoke_passed"))
    events_path = tmp_path / "progress.jsonl"
    status_before = status_path.read_bytes()
    events_before = events_path.read_bytes()

    with pytest.raises(ValueError, match="smoke_passed.*planned"):
        campaign.write_status(campaign.status(plan, stage="planned"))

    assert status_path.read_bytes() == status_before
    assert events_path.read_bytes() == events_before


def test_read_status_rejects_pre_run_state_behind_canonical_events(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    campaign.append_event(campaign._event(plan, "source_selection"))
    campaign.append_event(campaign._event(plan, "plan_ready"))
    campaign.write_status(campaign.status(plan, stage="planned"))
    campaign.write_status(campaign.status(plan, stage="preflight_passed"))
    status_path = campaign.write_status(campaign.status(plan, stage="smoke_passed"))
    payload = json.loads(status_path.read_text())
    payload["state"] = "planned"
    status_path.write_text(json.dumps(payload) + "\n")

    with pytest.raises(ValueError, match="invalid campaign status"):
        campaign.read_status(plan=plan)


@pytest.mark.parametrize(
    ("state", "event_kinds"),
    [
        ("planned", ("source_selection", "plan_ready")),
        ("preflight_passed", ("source_selection", "plan_ready", "preflight_passed")),
        (
            "smoke_passed",
            ("source_selection", "plan_ready", "preflight_passed", "smoke_passed"),
        ),
    ],
)
def test_read_status_rebuilds_exact_pre_run_state_when_projection_is_missing(tmp_path, state, event_kinds):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    for kind in event_kinds:
        campaign.append_event(campaign._event(plan, kind))

    assert not (tmp_path / "status.json").exists()
    assert campaign.read_status(plan=plan).state == state


@pytest.mark.parametrize(
    "event_kinds",
    [
        ("campaign_started",),
        ("source_selection", "preflight_passed"),
        ("source_selection", "plan_ready", "smoke_passed"),
        ("source_selection", "plan_ready", "campaign_started"),
        ("source_selection", "plan_ready", "preflight_passed", "campaign_started"),
    ],
)
def test_read_status_rejects_incomplete_or_out_of_order_pre_run_prefix(tmp_path, event_kinds):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    for kind in event_kinds:
        campaign.append_event(campaign._event(plan, kind))

    with pytest.raises(ValueError, match="invalid campaign status"):
        campaign.read_status(plan=plan)


def test_read_status_accepts_complete_pre_run_prefix(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    _append_campaign_started(campaign, plan)

    assert campaign.read_status(plan=plan).state == "running"


@pytest.mark.parametrize(
    "events",
    [
        ("plan_ready",),
        ("campaign_started", "campaign_started"),
        ("campaign_started", "campaign_finished"),
    ],
)
def test_read_status_rejects_impossible_or_duplicate_campaign_boundaries(tmp_path, events):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    for kind in events:
        campaign.append_event(campaign._event(plan, kind))
    if events == ("plan_ready",):
        with pytest.raises(ValueError, match="running.*canonical event evidence"):
            campaign.write_status(campaign.status(plan, stage="running"))
        return
    campaign.write_status(campaign.status(plan, stage="running"))
    with pytest.raises(ValueError, match="invalid campaign status"):
        campaign.read_status(plan=plan)


@pytest.mark.parametrize("outcome", [outcome.value for outcome in CampaignOutcome if outcome.value != "pending"])
def test_read_status_rejects_unknown_work_unit_for_every_outcome(tmp_path, outcome):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    foreign = replace(plan.work_units[0], work_unit_hash="foreign")
    _append_campaign_started(campaign, plan)
    campaign.append_event(campaign._event(plan, f"unit_{outcome}", unit=foreign, outcome=outcome))
    campaign.write_status(campaign.status(plan, stage="running"))
    with pytest.raises(ValueError, match="invalid campaign status"):
        campaign.read_status(plan=plan)


def test_read_status_rejects_events_after_campaign_finish(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    _append_campaign_started(campaign, plan)
    for unit in plan.work_units:
        _append_unit_events(campaign, plan, unit, "failed")
    campaign.append_event(campaign._event(plan, "campaign_finished"))
    campaign.append_event(campaign._event(plan, "campaign_started"))
    campaign.write_status(campaign.status(plan, [{"outcome": "failed"}] * len(plan.work_units), stage="terminal"))
    with pytest.raises(ValueError, match="invalid campaign status"):
        campaign.read_status(plan=plan)


def test_read_status_rejects_duplicate_unit_terminal_boundary(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    unit = plan.work_units[0]
    _append_campaign_started(campaign, plan)
    _append_unit_events(campaign, plan, unit, "failed")
    campaign.append_event(campaign._event(plan, "unit_failed", unit=unit, outcome="failed"))
    campaign.write_status(campaign.status(plan, [{"outcome": "failed"}], current_unit=unit, stage="failed"))
    with pytest.raises(ValueError, match="invalid campaign status"):
        campaign.read_status(plan=plan)


@pytest.mark.parametrize("state", ["completed", "completed_with_failures"])
def test_write_status_rejects_direct_terminal_state_without_finish_event(tmp_path, state):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    _append_campaign_started(campaign, plan)
    status = replace(campaign.status(plan), state=state)

    with pytest.raises(ValueError, match=rf"{state}.*canonical event evidence"):
        campaign.write_status(status)

    assert not (tmp_path / "status.json").exists()


def test_read_status_rejects_nonblocked_state_after_campaign_blocked(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    _append_campaign_started(campaign, plan)
    campaign.append_event(campaign._event(plan, "campaign_blocked", outcome="blocked"))
    with pytest.raises(ValueError, match="blocked.*preflight_passed"):
        campaign.write_status(campaign.status(plan, stage="preflight_passed"))
    assert not (tmp_path / "status.json").exists()


@pytest.mark.parametrize("state", ["planned", "running", "blocked", "conflicted"])
def test_write_status_rejects_direct_event_backed_state_without_events(tmp_path, state):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    status = replace(campaign.status(plan), state=state)

    with pytest.raises(ValueError, match=rf"{state}.*canonical event evidence"):
        campaign.write_status(status)

    assert not (tmp_path / "status.json").exists()


@pytest.mark.parametrize("outcome", ["succeeded", "skipped"])
def test_terminal_success_and_skip_require_validated_shard_leaves(tmp_path, monkeypatch, outcome):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    _append_campaign_started(campaign, plan)
    for unit in plan.work_units:
        _append_unit_events(campaign, plan, unit, outcome)
    campaign.append_event(campaign._event(plan, "campaign_finished"))
    campaign.write_status(
        campaign.status(
            plan, [{"outcome": outcome}] * len(plan.work_units), stage="terminal", last_unit=plan.work_units[-1]
        )
    )
    monkeypatch.setattr(campaign, "shard_entry_for_unit", lambda _plan, _unit: SimpleNamespace())
    from aria_nbv.oracle.pipelines import shards as shard_module

    monkeypatch.setattr(shard_module, "read_validated_completed_shard", lambda *args, **kwargs: None)
    with pytest.raises(ValueError, match="invalid campaign status"):
        campaign.read_status(plan=plan)

    monkeypatch.setattr(
        shard_module,
        "read_validated_completed_shard",
        lambda *args, **kwargs: {"validation": "passed"},
    )
    assert campaign.read_status(plan=plan).state == "completed"


def test_status_does_not_invent_coordinator_worker_identity(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    status = campaign.status(plan, current_unit=plan.work_units[0], stage="worker")
    assert status.active_pid is None
    assert status.active_process_group is None


def test_process_runner_reports_child_identity_before_communicate(monkeypatch):
    class Process:
        pid = 4321
        returncode = 0

        def communicate(self, timeout=None):
            assert started
            return b"{}", b""

    started = []
    runner = CampaignProcessRunner()
    monkeypatch.setattr(runner, "start", lambda *args, **kwargs: Process())
    monkeypatch.setattr("aria_nbv.oracle.pipelines.campaign.os.getpgid", lambda _pid: 9876)
    runner.run(("worker",), timeout=1, on_started=lambda pid, pgid: started.append((pid, pgid)))
    assert started == [(4321, 9876)]


def test_child_start_event_and_status_share_active_timestamp(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    unit = plan.work_units[0]
    _append_campaign_started(campaign, plan)
    campaign.append_event(campaign._event(plan, "target_profile", unit=unit, stage=unit.profile))
    campaign.append_event(campaign._event(plan, "root_preflight", unit=unit, stage="preflight"))

    campaign._child_started_callback(
        plan,
        [],
        unit,
        started_at=0.0,
        started_at_iso="campaign-start",
        last_timeout=None,
    )(4321, 9876)

    started = campaign.read_events(plan=plan)[-1]
    status = campaign.read_status(plan=plan)
    assert status.active_pid == started.pid == 4321
    assert status.active_process_group == started.process_group == 9876
    assert status.active_started_at == started.timestamp


def test_process_runner_reports_missing_process_group(monkeypatch):
    class Process:
        pid = 4321
        returncode = 0

        def communicate(self, timeout=None):
            return b"{}", b""

    seen = []
    runner = CampaignProcessRunner()
    monkeypatch.setattr(runner, "start", lambda *args, **kwargs: Process())
    monkeypatch.setattr(
        "aria_nbv.oracle.pipelines.campaign.os.getpgid",
        lambda _pid: (_ for _ in ()).throw(ProcessLookupError),
    )
    runner.run(("worker",), timeout=1, on_started=lambda pid, pgid: seen.append((pid, pgid)))
    assert seen == [(4321, None)]


def test_process_runner_cleans_up_when_start_callback_fails(monkeypatch):
    class Process:
        pid = 4321
        returncode = 0

        def communicate(self, timeout=None):
            return b"{}", b""

        def wait(self, timeout=None):
            return 0

    runner = CampaignProcessRunner()
    process = Process()
    monkeypatch.setattr(runner, "start", lambda *args, **kwargs: process)
    monkeypatch.setattr("aria_nbv.oracle.pipelines.campaign.os.getpgid", lambda _pid: 9876)
    terminated = []
    monkeypatch.setattr(runner, "terminate_group", lambda proc: terminated.append(proc))
    with pytest.raises(RuntimeError):
        runner.run(("worker",), timeout=1, on_started=lambda *_: (_ for _ in ()).throw(RuntimeError("status")))
    assert terminated == [process]


def test_process_group_timeout_sends_term_waits_grace_then_kills(monkeypatch):
    calls = []

    class Process:
        pid = 42

        def wait(self, timeout=None):
            calls.append(("wait", timeout))
            raise subprocess.TimeoutExpired("worker", timeout)

    monkeypatch.setattr("aria_nbv.oracle.pipelines.campaign.os.getpgid", lambda pid: pid)
    monkeypatch.setattr(
        "aria_nbv.oracle.pipelines.campaign.os.killpg", lambda pgid, sig: calls.append(("kill", pgid, sig))
    )
    CampaignProcessRunner().terminate_group(Process(), grace_seconds=10)
    assert calls == [("kill", 42, signal.SIGTERM), ("wait", 10), ("kill", 42, signal.SIGKILL)]


def test_process_runner_drains_binary_pipes_and_records_timeout_identity(monkeypatch):
    calls = []
    communicate_calls = 0

    class Process:
        pid = 42
        returncode = None

        def communicate(self, timeout=None):
            nonlocal communicate_calls
            communicate_calls += 1
            calls.append(("communicate", timeout))
            if communicate_calls < 3:
                raise subprocess.TimeoutExpired("worker", timeout)
            return b"partial stdout", b"bounded stderr"

    runner = CampaignProcessRunner()
    runner.start = lambda *args, **kwargs: Process()
    monkeypatch.setattr("aria_nbv.oracle.pipelines.campaign.os.getpgid", lambda pid: pid)
    monkeypatch.setattr(
        "aria_nbv.oracle.pipelines.campaign.os.killpg", lambda pgid, sig: calls.append(("kill", pgid, sig))
    )
    with pytest.raises(CampaignTimeoutError) as raised:
        runner.run(("worker",), timeout=1, stdout=subprocess.PIPE, stderr=subprocess.PIPE, clock=lambda: 1.0)
    assert raised.value.process_group == 42
    assert raised.value.stderr_tail == "bounded stderr"
    assert raised.value.disposition == "term-grace-kill"
    assert ("kill", 42, signal.SIGTERM) in calls
    assert ("kill", 42, signal.SIGKILL) in calls


def test_run_claimed_records_failure_and_continues_to_next_unit(tmp_path, monkeypatch):
    campaign = _campaign(tmp_path)
    monkeypatch.setattr(campaign, "_require_validated_terminal_shard", lambda _plan, _unit: {"validation": "passed"})
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    _append_pre_run_prefix(campaign, plan)
    claim = {"claim_hash": "test"}
    calls = []

    def worker(unit):
        calls.append(unit.work_unit_hash)
        if len(calls) == 1:
            raise TimeoutError("synthetic timeout")
        return {"outcome": "skipped"}

    results = campaign._run_claimed(plan, worker=worker, claim=claim)
    assert len(calls) == len(plan.work_units)
    assert results[0]["outcome"] == "timed_out"
    assert results[1]["outcome"] == "skipped"
    kinds = [event.kind for event in campaign.read_events()]
    assert kinds[4:10] == [
        "campaign_started",
        "target_profile",
        "root_preflight",
        "unit_started",
        "recipe_worker",
        "unit_timed_out",
    ]
    assert kinds[-1] == "campaign_finished"
    assert kinds.count("unit_started") == len(plan.work_units)


def test_run_claimed_never_marks_unvalidated_skip_complete(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    _append_pre_run_prefix(campaign, plan)

    results = campaign._run_claimed(
        plan,
        worker=lambda _unit: {"outcome": "skipped"},
        claim={"claim_hash": "test"},
    )

    assert {result["outcome"] for result in results} == {"failed"}
    assert "unit_skipped" not in [event.kind for event in campaign.read_events()]
    assert campaign.read_status(plan=plan).state == "completed_with_failures"


def test_run_claimed_resume_rebuilds_counts_and_preserves_last_identity(tmp_path, monkeypatch):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    _append_pre_run_prefix(campaign, plan)
    monkeypatch.setattr(campaign, "_require_validated_terminal_shard", lambda _plan, _unit: {"validation": "passed"})

    first = campaign._run_claimed(
        plan,
        worker=lambda _unit: {"outcome": "succeeded", "validated": True},
        claim={"claim_hash": "first"},
        max_new_units=1,
    )
    blocked = campaign.read_status(plan=plan)
    assert len(first) == 1
    assert blocked.state == "blocked"
    assert blocked.counts["succeeded"] == 1
    assert blocked.last_work_unit == plan.work_units[0].work_unit_hash

    active = []

    def resume_worker(unit):
        status = campaign.read_status(plan=plan)
        active.append((status.current_work_unit, status.last_work_unit))
        return {"outcome": "insufficient_support", "reason": "synthetic support gap"}

    resumed = campaign._run_claimed(plan, worker=resume_worker, claim={"claim_hash": "second"})
    completed = campaign.read_status(plan=plan)
    assert len(resumed) == len(plan.work_units)
    assert completed.state == "completed"
    assert completed.counts["succeeded"] == 1
    assert completed.counts["insufficient_support"] == len(plan.work_units) - 1
    assert completed.counts["pending"] == 0
    assert len(active) == len(plan.work_units) - 1
    assert active[0] == (plan.work_units[1].work_unit_hash, plan.work_units[0].work_unit_hash)


@pytest.mark.parametrize("retry_outcome", ["failed", "timed_out", "insufficient_support"])
def test_run_claimed_resume_retries_every_nonvalidated_terminal_outcome(tmp_path, retry_outcome):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    first_unit = plan.work_units[0]
    _append_campaign_started(campaign, plan)
    for unit in plan.work_units:
        _append_unit_events(campaign, plan, unit, retry_outcome)
    campaign.append_event(campaign._event(plan, "campaign_finished"))
    retried = []

    def worker(unit):
        retried.append(unit.work_unit_hash)
        return {"outcome": "insufficient_support", "reason": "bounded"}

    resumed = campaign._run_claimed(plan, worker=worker, claim={"claim_hash": "second"})

    assert retried[0] == first_unit.work_unit_hash
    assert len(resumed) == len(plan.work_units)
    assert [event.kind for event in campaign.read_events(plan=plan)].count("campaign_resumed") == 1


def test_public_run_preserves_failed_terminal_identity_inside_first_retry_worker(tmp_path, monkeypatch):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    _append_campaign_started(campaign, plan)
    for unit in plan.work_units:
        _append_unit_events(campaign, plan, unit, "failed")
    campaign.append_event(campaign._event(plan, "campaign_finished"))
    campaign.write_status(
        campaign.status(
            plan,
            [{"outcome": "failed"}] * len(plan.work_units),
            stage="terminal",
            last_unit=plan.work_units[-1],
        )
    )
    assert campaign.read_status(plan=plan).state == "completed_with_failures"
    monkeypatch.setattr(campaign, "preflight", lambda *args, **kwargs: None)
    monkeypatch.setattr(campaign, "smoke_evidence", lambda _plan: None)
    active = []

    def retry_worker(unit):
        status = campaign.read_status(plan=plan)
        active.append((unit, status))
        raise RuntimeError("retry still fails")

    results = campaign.run(plan, worker=retry_worker)

    first_retry, first_status = active[0]
    assert first_status.state == "running"
    assert first_status.current_work_unit == first_retry.work_unit_hash
    assert first_status.last_work_unit == plan.work_units[-1].work_unit_hash
    assert {result["outcome"] for result in results} == {"failed"}
    assert campaign.read_status(plan=plan).state == "completed_with_failures"


def test_run_claimed_rejects_restart_when_every_terminal_unit_is_validated(tmp_path, monkeypatch):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    _append_campaign_started(campaign, plan)
    for unit in plan.work_units:
        _append_unit_events(campaign, plan, unit, "succeeded")
    campaign.append_event(campaign._event(plan, "campaign_finished"))
    monkeypatch.setattr(campaign, "_require_validated_terminal_shard", lambda _plan, _unit: {"validation": "passed"})

    with pytest.raises(ValueError, match="completed campaign cannot be resumed"):
        campaign._run_claimed(
            plan,
            worker=lambda _unit: {"outcome": "insufficient_support"},
            claim={"claim_hash": "restart"},
        )


def test_run_claimed_reconciles_interrupted_active_attempt_before_retry(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    interrupted = plan.work_units[0]
    _append_campaign_started(campaign, plan)
    campaign.append_event(campaign._event(plan, "target_profile", unit=interrupted, stage=interrupted.profile))
    retried = []

    campaign._run_claimed(
        plan,
        worker=lambda unit: (
            retried.append(unit.work_unit_hash) or {"outcome": "insufficient_support", "reason": "bounded"}
        ),
        claim={"claim_hash": "resume"},
    )

    assert retried[0] == interrupted.work_unit_hash
    assert "campaign_resumed" in [event.kind for event in campaign.read_events(plan=plan)]
    assert campaign.read_status(plan=plan).state == "completed"


@pytest.mark.parametrize("prior_resumes", [0, 1])
def test_public_run_rechecks_admission_before_resuming_interrupted_attempt(tmp_path, monkeypatch, prior_resumes):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    interrupted = plan.work_units[0]
    _append_campaign_started(campaign, plan)
    for _ in range(prior_resumes):
        campaign.append_event(campaign._event(plan, "campaign_resumed"))
    campaign.append_event(campaign._event(plan, "target_profile", unit=interrupted, stage=interrupted.profile))
    admission_checks = []
    monkeypatch.setattr(campaign, "preflight", lambda *args, **kwargs: admission_checks.append("preflight"))
    monkeypatch.setattr(campaign, "smoke_evidence", lambda _plan: admission_checks.append("smoke"))

    results = campaign.run(
        plan,
        worker=lambda _unit: {"outcome": "insufficient_support", "reason": "bounded"},
    )

    events = campaign.read_events(plan=plan)
    assert admission_checks == ["preflight", "smoke"]
    assert [event.kind for event in events].count("preflight_passed") == 1
    assert [event.kind for event in events].count("smoke_passed") == 1
    assert [event.kind for event in events].count("campaign_resumed") == prior_resumes + 1
    assert len(results) == len(plan.work_units)


@pytest.mark.parametrize(
    "prior_gates",
    [
        (),
        ("preflight_passed",),
        ("preflight_passed", "smoke_passed"),
    ],
)
def test_public_run_reuses_valid_pre_run_prefix(tmp_path, monkeypatch, prior_gates):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    for kind in ("source_selection", "plan_ready", *prior_gates):
        campaign.append_event(campaign._event(plan, kind))
    prior_state = prior_gates[-1] if prior_gates else "planned"
    campaign.write_status(campaign.status(plan, stage=prior_state))
    admission_checks = []
    monkeypatch.setattr(campaign, "preflight", lambda *args, **kwargs: admission_checks.append("preflight"))
    monkeypatch.setattr(campaign, "smoke_evidence", lambda _plan: admission_checks.append("smoke"))

    results = campaign.run(
        plan,
        worker=lambda _unit: {"outcome": "insufficient_support", "reason": "bounded"},
    )

    events = campaign.read_events(plan=plan)
    assert admission_checks == ["preflight", "smoke"]
    assert [event.kind for event in events[:5]] == [
        "source_selection",
        "plan_ready",
        "preflight_passed",
        "smoke_passed",
        "campaign_started",
    ]
    assert [event.kind for event in events].count("preflight_passed") == 1
    assert [event.kind for event in events].count("smoke_passed") == 1
    assert [event.kind for event in events].count("campaign_started") == 1
    assert len(results) == len(plan.work_units)


def test_run_claimed_persists_typed_timeout_and_continues(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    _append_pre_run_prefix(campaign, plan)
    calls = []

    def worker(unit):
        calls.append(unit.work_unit_hash)
        if len(calls) == 1:
            raise CampaignTimeoutError(
                "timed out",
                pid=42,
                process_group=42,
                elapsed_seconds=3600.0,
                stderr_tail="bounded stderr",
            )
        return {"outcome": "insufficient_support", "reason": "synthetic support gap"}

    campaign._run_claimed(plan, worker=worker, claim={"claim_hash": "test", "tmux_session": "campaign"})
    status = campaign.read_status(plan=plan)
    assert len(calls) == len(plan.work_units)
    assert status.last_timeout == {
        "work_unit_hash": plan.work_units[0].work_unit_hash,
        "stage": "worker",
        "pid": 42,
        "process_group": 42,
        "tmux_session": "campaign",
        "disposition": "term-grace-kill",
        "stderr_tail": "bounded stderr",
        "elapsed_seconds": 3600.0,
    }


def test_quarantine_staging_atomically_moves_timeout_and_is_collision_safe(tmp_path, monkeypatch):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    unit = plan.work_units[0]
    staging = tmp_path / "tmp" / unit.work_unit_hash
    staging.mkdir(parents=True)
    first = campaign.quarantine_staging(unit)
    assert first is not None and first.exists() and not staging.exists()
    staging.mkdir(parents=True)
    second = campaign.quarantine_staging(unit)
    assert second is not None and second.exists() and second != first
    assert not (tmp_path / "shards" / unit.work_unit_hash / "_SUCCESS.json").exists()


def test_event_reader_allows_only_truncated_final_line(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    path = tmp_path / "progress.jsonl"
    campaign.append_event(campaign._event(plan, "planned"), path)
    path.write_text(path.read_text() + '{"kind":"unit_started"', encoding="utf-8")
    assert [event.kind for event in campaign.read_events(path)] == ["planned"]
    path.write_text('{"kind":"planned"\n{"kind":', encoding="utf-8")
    with pytest.raises(ValueError, match="malformed event line"):
        campaign.read_events(path)


def test_event_reader_requires_identity_for_current_schema_but_accepts_legacy(tmp_path):
    campaign = _campaign(tmp_path)
    path = tmp_path / "progress.jsonl"
    path.write_text('{"kind":"planned","timestamp":"now","schema_version":"campaign-event-v1"}\n')
    with pytest.raises(ValueError, match="requires campaign, plan, and config identity"):
        campaign.read_events(path)
    path.write_text('{"kind":"planned","timestamp":"now"}\n')
    assert campaign.read_events(path)[0].kind == "planned"


@pytest.mark.parametrize("payload", [[], "event", None, 1])
def test_event_reader_rejects_non_object_json_lines(tmp_path, payload):
    campaign = _campaign(tmp_path)
    path = tmp_path / "progress.jsonl"
    path.write_text(json.dumps(payload) + "\n")

    with pytest.raises(ValueError, match="line 1 must be a JSON object"):
        campaign.read_events(path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("writer_config_hash", "foreign-writer"),
        ("source_manifest_hash", "foreign-source"),
        ("source_identity_hash", "foreign-source-identity"),
        ("target_id", "foreign-target"),
        ("profile", "foreign-profile"),
        ("profile_hash", "foreign-profile-hash"),
    ],
)
def test_event_reader_rejects_plan_binding_tampering(tmp_path, field, value):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    unit = plan.work_units[0]
    events = [
        asdict(campaign._event(plan, "campaign_started")),
        asdict(campaign._event(plan, "target_profile", unit=unit, stage=unit.profile)),
    ]
    events[-1][field] = value
    path = tmp_path / "progress.jsonl"
    path.write_text("".join(json.dumps(event) + "\n" for event in events))

    with pytest.raises(ValueError, match=field):
        campaign.read_events(path, plan=plan)


def test_read_status_rebuilds_running_stage_when_projection_is_missing(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    unit = plan.work_units[0]
    _append_campaign_started(campaign, plan)
    campaign.append_event(campaign._event(plan, "target_profile", unit=unit, stage=unit.profile))
    campaign.append_event(campaign._event(plan, "root_preflight", unit=unit, stage="preflight"))
    started = campaign._event(plan, "unit_started", unit=unit, stage="worker", pid=4321, process_group=4321)
    campaign.append_event(started)

    status = campaign.read_status(plan=plan)

    assert status.state == "running"
    assert status.plan_hash == plan.plan_hash
    assert status.current_work_unit == unit.work_unit_hash
    assert status.current_target_id == unit.target_id
    assert status.current_profile == unit.profile
    assert status.current_stage == "worker"
    assert status.active_pid == 4321
    assert status.active_process_group == 4321
    assert status.active_started_at == started.timestamp
    assert status.counts["pending"] == len(plan.work_units)


def test_read_status_fails_closed_when_missing_projection_rebuilds_as_not_started(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    campaign.append_event(campaign._event(plan, "source_selection"))

    with pytest.raises(ValueError, match="invalid campaign status"):
        campaign.read_status(plan=plan)


@pytest.mark.parametrize(
    "state",
    ["planned", "preflight_passed", "smoke_passed", "running", "blocked", "conflicted"],
)
def test_read_status_rejects_eventless_nonterminal_projection(tmp_path, state):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    status_path = tmp_path / "status.json"
    status_path.write_text(json.dumps(asdict(campaign.status(plan, stage=state))) + "\n")

    with pytest.raises(ValueError, match="invalid campaign status"):
        campaign.read_status(plan=plan)


def test_stale_smoke_evidence_is_rejected_without_overwriting(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    evidence = tmp_path / "smoke-evidence.json"
    evidence.write_text(
        '{"campaign_id":"cuda-rollouts-v1","plan_hash":"stale","config_hash":"x","work_unit_hash":"u"}\n'
    )
    before = evidence.read_text()
    with pytest.raises(RuntimeError, match="stale"):
        campaign.smoke_evidence(plan)
    assert evidence.read_text() == before


def test_legacy_v0_lineage_and_zarr_table_schema_remain_structurally_stable():
    assert TargetLineage().target_protocol_version is None
    assert TargetLineage().target_source is None
    assert ROLLOUT_ZARR_SCHEMA_VERSION
    assert tuple(field.name for field in ROLLOUT_TABLE.fields)[:5] == (
        "rollout_row_id",
        "rollout_id",
        "chain_id",
        "source_row_id",
        "root_pose_world",
    )
    assert tuple(field.name for field in LINEAGE_TABLE.fields) == (
        "rollout_row_id",
        "candidate_config_id",
        "oracle_config_id",
        "rollout_config_id",
        "model_checkpoint_id",
        "mesh_version_id",
        "branch_schedule_id",
        "target_protocol_version_id",
        "target_crop_policy_id",
        "reason_code_version_id",
        "selection_rng_state_hash_id",
    )
    assert tuple(field.name for field in STEP_TABLE.fields)[:4] == (
        "step_row_id",
        "rollout_row_id",
        "step_index",
        "selected_candidate_row_id",
    )


@pytest.mark.parametrize("horizon", (5, 8))
def test_qh_reader_retains_every_intermediate_trajectory_prefix(tmp_path, horizon):
    records = build_rollout_records(horizon=horizon, num_samples=6, seed=7)[:1]
    write_rollout_zarr_store(
        tmp_path / f"h{horizon}.zarr",
        records,
        discount_gamma=0.95,
        target_protocol_version="v0_gt_input",
        source_offline_store_version="7",
        split_manifest_hash="fixture-split-manifest",
    )
    chain = QhRolloutReader((tmp_path / f"h{horizon}.zarr",))[0]
    assert chain.horizon_remaining.tolist() == list(range(horizon, 0, -1))
    assert len(chain.candidate_pose_relative_root) == horizon


def test_status_counts_preserve_pending_and_insufficient_support_states(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    status = campaign.status(plan, [{"outcome": "insufficient_support"}, {"outcome": "pending"}])
    assert status.counts["insufficient_support"] == 1
    assert status.counts["pending"] == len(plan.work_units) - 1


@pytest.mark.parametrize(
    ("results", "state"),
    [
        ([], "not_started"),
        ([{"outcome": "pending"}], "running"),
        ([{"outcome": "succeeded"}], "completed"),
        ([{"outcome": "failed"}], "completed_with_failures"),
    ],
)
def test_status_reports_each_terminal_and_active_state(tmp_path, results, state):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    if state.startswith("completed"):
        results = results * len(plan.work_units)
    assert campaign.status(plan, results).state == state


@pytest.mark.parametrize(
    ("stage", "state"), [("worker", "running"), ("blocked", "blocked"), ("conflicted", "conflicted")]
)
def test_status_reports_active_and_bounded_states(tmp_path, stage, state):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    status = campaign.status(plan, stage=stage, bounded_error="bounded")
    assert status.state == state
    assert status.latest_failure_reason == "bounded"


def test_partial_status_counts_pending_units_and_typed_event_identity(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    status = campaign.status(plan, [{"outcome": "pending"}])
    assert status.state == "running"
    assert status.counts["pending"] == len(plan.work_units)
    event = campaign._event(
        plan,
        "root_preflight_insufficient",
        unit=plan.work_units[0],
        outcome="insufficient_support",
        detail="9 valid candidates",
        stage="preflight",
        elapsed_seconds=1.5,
    )
    path = campaign.append_event(event)
    loaded = campaign.read_events(path)[0]
    assert loaded.work_unit_hash == plan.work_units[0].work_unit_hash
    assert loaded.outcome == "insufficient_support"
    assert loaded.detail == "9 valid candidates"
    assert loaded.stage == "preflight"
    assert loaded.elapsed_seconds == 1.5


def test_progress_summary_distinguishes_planned_all_pending_and_partial(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    planned = campaign.progress_summary(plan)
    assert planned["counts"]["pending"] == len(plan.work_units)
    _append_campaign_started(campaign, plan)
    unit = plan.work_units[0]
    _append_unit_events(campaign, plan, unit, "insufficient_support")
    campaign.write_status(
        campaign.status(plan, [{"outcome": "insufficient_support"}], current_unit=unit, stage="insufficient_support")
    )
    partial = campaign.progress_summary(plan)
    assert partial["counts"]["insufficient"] == 1
    assert partial["counts"]["pending"] == len(plan.work_units) - 1


def test_progress_summary_artifacts_follow_plan_order_and_ignore_invalid_paths(tmp_path, monkeypatch):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    shards = tmp_path / "shards"
    shards.mkdir()
    for unit in plan.work_units:
        (shards / unit.work_unit_hash).mkdir()
    (shards / "unrelated").mkdir()
    units = tuple(
        replace(
            unit,
            source_row_payload={"source_manifest_hash": "source", "split": "train", "source_store_dir": "/tmp/source"},
        )
        for unit in plan.work_units
    )
    plan = replace(plan, work_units=units, writer_config_hash="planned-writer")
    entries = {unit.work_unit_hash: campaign.shard_entry_for_unit(plan, unit) for unit in plan.work_units}
    monkeypatch.setattr(campaign, "shard_entry_for_unit", lambda _plan, unit: entries[unit.work_unit_hash])
    from aria_nbv.oracle.pipelines import shards as shard_module

    seen_writer_hashes = []
    effective_writer = RolloutDatasetWriterConfig()
    effective_hash = stable_config_hash(effective_writer)
    monkeypatch.setattr(
        campaign,
        "_effective_writer_and_shard_entry",
        lambda _plan, unit: (effective_writer, entries[unit.work_unit_hash]),
    )

    def read(path, *, shard_entry, writer_config_hash=""):
        seen_writer_hashes.append(writer_config_hash)
        if path.name != plan.work_units[0].work_unit_hash:
            return None
        return {
            "store_path": str(path.resolve()),
            "owner_evidence": {"writer_config_hash": effective_hash},
            "success_evidence": {"owner_sha256": "owner", "rollout_manifest_sha256": "manifest"},
            "validation": "passed",
        }

    monkeypatch.setattr(shard_module, "read_validated_completed_shard", read)
    summary = campaign.progress_summary(plan)
    artifacts = summary["validated_artifacts"]
    assert [row["work_unit_hash"] for row in artifacts] == [plan.work_units[0].work_unit_hash]
    assert artifacts[0]["store_path"] == str((shards / plan.work_units[0].work_unit_hash).resolve())
    assert artifacts[0]["effective_writer_config_hash"] == effective_hash
    assert seen_writer_hashes == [effective_hash] * len(plan.work_units)
    assert "owner_evidence" not in artifacts[0]
    assert not any(row["work_unit_hash"] == "unrelated" for row in artifacts)


def test_effective_writer_hash_rebinds_base_writer_before_terminal_validation(tmp_path, monkeypatch):
    base_campaign = _campaign(tmp_path)
    config_values = base_campaign.config.model_dump()
    config_values["writer_config_path"] = REPO_ROOT / ".configs/build_rollouts_v1_cuda_campaign_writer.toml"
    config_values["profiles"] = base_campaign.config.profiles
    config = CudaRolloutCampaignConfig.model_construct(**config_values)
    campaign = CudaRolloutCampaign(config)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    unit = plan.work_units[0]
    unit = replace(unit, source_row_payload={"source_manifest_hash": "source", "split": "train"})
    adapted = RolloutDatasetWriterConfig()
    adapted = adapted.model_copy(update={"log_timing": True})
    base_entry = campaign.shard_entry_for_unit(plan, unit)
    effective_entry = replace(
        base_entry, split_manifest_hash="canonical", writer_config_hash=stable_config_hash(adapted)
    )
    monkeypatch.setattr(
        RolloutDatasetWriterConfig, "from_toml", classmethod(lambda cls, _path: RolloutDatasetWriterConfig())
    )
    monkeypatch.setattr(campaign, "shard_entry_for_unit", lambda _plan, _unit: base_entry)
    monkeypatch.setattr(campaign, "adapt_work_unit", lambda *_args, **_kwargs: (adapted, effective_entry))

    effective, entry = campaign._effective_writer_and_shard_entry(plan, unit)

    assert stable_config_hash(effective) == stable_config_hash(adapted)
    assert stable_config_hash(effective) != plan.writer_config_hash
    assert entry.split_manifest_hash == "canonical"
    assert entry.writer_config_hash == stable_config_hash(adapted)


def _row(scene: str, sample: str, target: str) -> SimpleNamespace:
    descriptor = TargetDescriptor(1, "object", (1.0,) * 12, (1.0, 1.0, 1.0), (1.0,) * 12)
    observed = ObservedTargetDescriptor(sample, "detected", 0, target, descriptor, 0.9, 1)
    explicit_hash = stable_msgspec_hash(
        {
            "sample_key": sample,
            "target_id": target,
            "detected_source_row": 0,
            "gt_match_row": 0,
            "gt_match_id": "gt",
            "oriented_iou": 0.5,
            "descriptor_hash": observed.descriptor_hash,
        }
    )
    return SimpleNamespace(
        scene_id=scene,
        sample_key=sample,
        target_id=target,
        admitted=True,
        reason="admitted",
        gt_match_count=1,
        oriented_iou=0.5,
        explicit_target_config={
            "sample_key": sample,
            "actor_descriptor": observed,
            "detected_source_row": 0,
            "gt_match_row": 0,
            "gt_match_id": "gt",
            "oriented_iou": 0.5,
            "target_id": target,
            "explicit_target_hash": explicit_hash,
        },
        source_store_dir="source",
    )


def test_plan_is_stable_and_assigns_profiles(tmp_path):
    campaign = _campaign(tmp_path)
    rows = [_row(f"s{i}", f"k{i}", f"t{i}") for i in range(2)]
    first = campaign.plan(rows, source_manifest_hash="source")
    second = campaign.plan(list(reversed(rows)), source_manifest_hash="source")
    assert first.plan_hash != second.plan_hash
    assert {u.profile for u in first.work_units} == {"realistic_core_60"}
    assert [u.temperature for u in first.work_units] == [0.5, 1.0]
    assert {u.scene_split for u in first.work_units} == {"train"}


def test_pilot_plan_has_two_profiles_and_four_temperatures(tmp_path):
    base = CudaRolloutCampaignConfig(output_root=tmp_path)
    values = base.model_dump()
    values.update(mode="pilot", expected_scene_count=6, pilot_scene_count=5, profiles=base.profiles)
    campaign = CudaRolloutCampaign(CudaRolloutCampaignConfig.model_construct(**values))
    rows = [_row(f"s{i}", f"k{i}", f"t{i}") for i in range(6)]
    plan = campaign.plan(rows, source_manifest_hash="source")
    assert len(plan.work_units) == 10
    assert {u.profile for u in plan.work_units} == {"realistic_core_60", "rich_local_60"}
    assert {u.temperatures for u in plan.work_units} == {(0.5, 1.0, 2.0, 4.0)}
    assert len({u.work_unit_hash for u in plan.work_units}) == 10


def test_pilot_adaptation_emits_four_ordered_myopic_recipes(tmp_path):
    base = _campaign(tmp_path)
    values = base.config.model_dump()
    values.update(mode="pilot", profiles=base.config.profiles)
    pilot = CudaRolloutCampaign(CudaRolloutCampaignConfig.model_construct(**values))
    plan = pilot.plan([_row("s0", "k0", "t0"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    writer = RolloutDatasetWriterConfig().model_copy(update={"source_manifest_path": None})
    adapted, _ = pilot.adapt_work_unit(
        plan.work_units[0],
        writer_config=writer,
        shard_entry=SimpleNamespace(),
        plan_hash=plan.plan_hash,
        profile_hash=plan.work_units[0].profile_hash,
    )
    assert [recipe.policy.selection_temperature for recipe in adapted.recipes] == [0.5, 1.0, 2.0, 4.0]
    assert [
        (recipe.policy.horizon, recipe.policy.branch_factor, recipe.policy.beam_width) for recipe in adapted.recipes
    ] == [
        (8, 1, 1),
    ] * 4
    broad = _campaign(tmp_path / "broad")
    broad_plan = broad.plan([_row("s0", "k0", "t0"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    broad_writer = RolloutDatasetWriterConfig().model_copy(update={"source_manifest_path": None})
    broad_adapted, _ = broad.adapt_work_unit(
        broad_plan.work_units[0],
        writer_config=broad_writer,
        shard_entry=SimpleNamespace(),
        plan_hash=broad_plan.plan_hash,
        profile_hash=broad_plan.work_units[0].profile_hash,
    )
    assert [recipe.policy.selection_temperature for recipe in broad_adapted.recipes] == [0.5]


def test_admission_audit_persists_full_rows_and_rejects_stale_overwrite(tmp_path):
    campaign = _campaign(tmp_path)
    rows = [
        {
            "scene_id": "s0",
            "sample_key": "k0",
            "target_id": "t0",
            "descriptor_hash": "descriptor",
            "gt_match_row": 7,
            "gt_match_id": "gt-7",
            "gt_match_count": 1,
            "oriented_iou": 0.8,
            "admitted": True,
            "reason": "admitted",
        }
    ]
    normalized_rows = json.loads(json.dumps(rows, sort_keys=True))
    expected_hash = stable_msgspec_hash(normalized_rows)

    path = campaign.write_admission_audit(
        rows,
        source_manifest_hash="source",
        expected_hash=expected_hash,
    )

    payload = json.loads(path.read_text())
    assert payload["admission_audit_hash"] == expected_hash
    assert payload["rows"] == rows
    stale = [{**rows[0], "target_id": "other"}]
    with pytest.raises(ValueError, match="different content"):
        campaign.write_admission_audit(
            stale,
            source_manifest_hash="source",
            expected_hash=stable_msgspec_hash(json.loads(json.dumps(stale, sort_keys=True))),
        )


def test_admission_audit_uses_the_plan_normalization(tmp_path):
    campaign = _campaign(tmp_path)
    rows = [_row("s0", "k0", "t0"), _row("s1", "k1", "t1")]
    plan = campaign.plan(rows, source_manifest_hash="source")

    path = campaign.write_admission_audit(
        rows,
        source_manifest_hash="source",
        expected_hash=plan.admission_audit_hash,
    )

    payload = json.loads(path.read_text())
    assert payload["admission_audit_hash"] == plan.admission_audit_hash
    assert len(payload["rows"]) == 2


def test_plan_hash_and_allocation_are_stable_and_source_change_rehashes(tmp_path):
    campaign = _campaign(tmp_path)
    rows = [_row("s0", "k", "t"), _row("s1", "k1", "t1")]
    first = campaign.plan(rows, source_manifest_hash="source")
    second = campaign.plan(rows, source_manifest_hash="source")
    changed = campaign.plan(rows, source_manifest_hash="changed")
    assert first.plan_hash == second.plan_hash
    assert first.work_units == second.work_units
    assert first.plan_hash != changed.plan_hash
    assert first.profile_hash == second.profile_hash


def test_plan_rejects_malformed_explicit_target(tmp_path):
    campaign = _campaign(tmp_path)
    row = _row("s0", "k0", "t0")
    row.explicit_target_config = {"target_id": "t0"}
    with pytest.raises(ValueError, match="malformed explicit_target_config"):
        campaign.plan([row, _row("s1", "k1", "t1")], source_manifest_hash="source")


@pytest.mark.parametrize(("reason", "count"), [("ambiguous_match", 1), ("admitted", 0), ("admitted", 2)])
def test_plan_rejects_noncanonical_admission_or_gt_count(tmp_path, reason, count):
    campaign = _campaign(tmp_path)
    row = _row("s0", "k0", "t0")
    row.reason, row.gt_match_count = reason, count
    with pytest.raises(ValueError):
        campaign.plan([row, _row("s1", "k1", "t1")], source_manifest_hash="source")


def test_plan_rejects_missing_gt_match_count(tmp_path):
    campaign = _campaign(tmp_path)
    row = _row("s0", "k0", "t0")
    delattr(row, "gt_match_count")
    with pytest.raises(ValueError, match="exactly one GT match"):
        campaign.plan([row, _row("s1", "k1", "t1")], source_manifest_hash="source")


def test_shard_entry_rejects_empty_profile_identity(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k0", "t0"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    unit = plan.work_units[0]
    empty = unit.__class__(**{**unit.__dict__, "profile_hash": ""}) if hasattr(unit, "__dict__") else unit
    if empty is unit:
        from dataclasses import replace

        empty = replace(unit, profile_hash="")
    with pytest.raises(ValueError, match="profile_hash"):
        campaign.shard_entry_for_unit(plan, empty)


def test_shard_entry_uses_canonical_one_row_split_hash(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k0", "t0"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    unit = replace(
        plan.work_units[0],
        source_row_payload={
            "sample_index": 7,
            "scene_id": "s0",
            "snippet_id": "k0",
            "split": "train",
            "source_shard_id": "source-0",
            "source_shard_row": 3,
            "source_manifest_hash": "vin-source",
        },
    )

    entry = campaign.shard_entry_for_unit(plan, unit)

    assert entry.split_manifest_hash == build_rollout_split_manifest_hash(
        source_manifest_hash="vin-source",
        split="train",
        records=[entry.rows[0].hash_record()],
    )


def test_shard_entry_rejects_missing_vin_source_manifest_lineage(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k0", "t0"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    unit = replace(plan.work_units[0], source_row_payload={"scene_id": "s0", "split": "train"})

    with pytest.raises(ValueError, match="VIN source_manifest_hash"):
        campaign.shard_entry_for_unit(plan, unit)


def test_plan_round_trip_and_immutable_write(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan(
        [_row(f"s{i}", f"k{i}", f"t{i}") for i in range(2)],
        source_manifest_hash="source",
    )
    path = campaign.write_plan(plan)
    assert campaign.load_plan(path) == plan
    with pytest.raises(ValueError):
        path.write_text("changed")
        campaign.write_plan(plan)


def test_run_rejects_foreign_campaign_or_unit_identity_before_files(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k0", "t0"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    foreign = plan.__class__(
        "foreign",
        plan.seed,
        plan.source_manifest_hash,
        plan.profile_hash,
        plan.work_units,
        plan.plan_hash,
        plan.config_hash,
        plan.writer_config_hash,
    )
    with pytest.raises(ValueError, match="identity"):
        campaign.run(
            foreign,
            worker=lambda _: {"outcome": "succeeded"},
            cuda_probe=lambda: {"cuda_available": True, "pytorch3d_available": True},
        )


def test_plan_runtime_digest_tampering_rejected_before_status_or_output(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan(
        [_row("s0", "k", "t"), _row("s1", "k1", "t1")],
        source_manifest_hash="source",
        writer_config_hash="writer-digest",
    )
    path = campaign.write_plan(plan)
    payload = json.loads(path.read_text())
    payload["writer_config_hash"] = "different-writer"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="plan hash mismatch"):
        campaign.load_plan(path)
    assert not (tmp_path / "status.json").exists()


def test_run_rejects_plan_writer_digest_before_claim_or_events(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan(
        [_row("s0", "k", "t"), _row("s1", "k1", "t1")],
        source_manifest_hash="source",
        writer_config_hash="required-writer",
    )
    with pytest.raises(ValueError, match="writer config hash"):
        campaign.run(
            plan,
            worker=lambda _unit: {"outcome": "skipped"},
            cuda_probe=lambda: SimpleNamespace(ok=True, cuda_available=True, pytorch3d_available=True, device="cuda:0"),
        )
    assert not (tmp_path / "run-claim.json").exists()
    assert not (tmp_path / "progress.jsonl").exists()


def test_run_rejects_source_selection_only_without_mutating_evidence(tmp_path, monkeypatch):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    events_path = campaign.append_event(campaign._event(plan, "source_selection"))
    status_path = campaign.write_status(campaign.status(plan))
    events_before = events_path.read_bytes()
    status_before = status_path.read_bytes()
    monkeypatch.setattr(campaign, "preflight", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(campaign, "smoke_evidence", lambda _plan: {"validated": True})

    with pytest.raises(ValueError, match="incomplete planning event prefix"):
        campaign.run(plan, worker=lambda _unit: {"outcome": "failed"})

    assert events_path.read_bytes() == events_before
    assert status_path.read_bytes() == status_before
    assert not (tmp_path / "run-claim.json").exists()


def test_run_requires_smoke_evidence_even_for_injected_worker(tmp_path, monkeypatch):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    called = []

    def smoke_evidence(_plan):
        called.append(True)
        raise RuntimeError("current passing smoke evidence is required")

    monkeypatch.setattr(campaign, "smoke_evidence", smoke_evidence)
    with pytest.raises(RuntimeError, match="smoke evidence"):
        campaign.run(
            plan,
            worker=lambda _unit: {"outcome": "skipped"},
            cuda_probe=lambda: SimpleNamespace(ok=True, cuda_available=True, pytorch3d_available=True, device="cuda:0"),
        )
    assert called == [True]


def test_direct_run_forwards_plan_and_writer_to_source_preflight(tmp_path, monkeypatch):
    campaign = _campaign(tmp_path)
    config = campaign.config.model_copy(update={"writer_config_path": tmp_path / "writer.toml"})
    campaign = CudaRolloutCampaign(config)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    captured = {}

    def preflight(*args, **kwargs):
        captured.update(args=args, kwargs=kwargs)
        return None

    monkeypatch.setattr(campaign, "preflight", preflight)
    monkeypatch.setattr(
        campaign,
        "smoke_evidence",
        lambda _plan: (_ for _ in ()).throw(RuntimeError("current passing smoke evidence is required")),
    )
    plan_path = tmp_path / "plan.json"
    with pytest.raises(RuntimeError, match="smoke evidence"):
        campaign.run(plan, worker=lambda _unit: {"outcome": "skipped"}, plan_path=plan_path)

    assert captured["kwargs"]["plan_path"] == plan_path
    assert captured["kwargs"]["writer_config_path"] == tmp_path / "writer.toml"


def test_competing_run_does_not_mutate_active_owner_status_or_events(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan([_row("s0", "k", "t"), _row("s1", "k1", "t1")], source_manifest_hash="source")
    _append_campaign_started(campaign, plan)
    owner_status = campaign.status(plan, stage="running")
    status_path = campaign.write_status(owner_status)
    before = status_path.read_bytes()
    events_path = tmp_path / "progress.jsonl"
    events_before = events_path.read_bytes()
    claim = campaign.acquire_claim(plan)

    with pytest.raises(RuntimeError, match="run claim exists"):
        campaign.run(
            plan,
            worker=lambda _unit: {"outcome": "skipped"},
            cuda_probe=lambda: {"cuda_available": True, "pytorch3d_available": True},
        )

    assert status_path.read_bytes() == before
    assert events_path.read_bytes() == events_before
    campaign.release_claim(plan, claim_hash=claim["claim_hash"])


def test_preflight_rejects_output_root_that_is_not_a_directory(tmp_path):
    output_root = tmp_path / "output"
    output_root.write_text("not a directory")
    config = _campaign(tmp_path).config.model_copy(update={"output_root": output_root})
    campaign = CudaRolloutCampaign(config)

    with pytest.raises(RuntimeError, match="not a directory"):
        campaign.preflight(lambda: {"cuda_available": True, "pytorch3d_available": True})


def test_stale_claim_requires_exact_hash_and_archives_acknowledged_claim(tmp_path, monkeypatch):
    path = tmp_path / "run-claim.json"
    path.write_text(json.dumps({"pid": 99999999, "claim_hash": "abc"}))
    monkeypatch.setattr(
        "aria_nbv.oracle.pipelines.campaign.os.kill", lambda *_args: (_ for _ in ()).throw(ProcessLookupError)
    )
    assert CudaRolloutCampaign.claim_is_stale(path)
    with pytest.raises(ValueError, match="hash mismatch"):
        CudaRolloutCampaign.acknowledge_stale_claim(path, "wrong")
    archive = CudaRolloutCampaign.acknowledge_stale_claim(path, "abc")
    assert archive.name == "run-claim.json.stale-abc"
    assert archive.exists() and not path.exists()


@pytest.mark.parametrize("scene_count", [99, 100, 101])
def test_plan_enforces_canonical_one_hundred_scene_gate(tmp_path, scene_count):
    campaign = CudaRolloutCampaign(CudaRolloutCampaignConfig(output_root=tmp_path))
    rows = [_row(f"scene-{i}", f"sample-{i}", f"target-{i}") for i in range(scene_count)]
    if scene_count == 100:
        assert campaign.plan(rows, source_manifest_hash="source").work_units
    else:
        with pytest.raises(ValueError, match="expected 100 scenes"):
            campaign.plan(rows, source_manifest_hash="source")


@pytest.mark.parametrize("iou", [float("nan"), float("inf"), float("-inf")])
def test_plan_rejects_nonfinite_iou_marked_admitted(tmp_path, iou):
    campaign = _campaign(tmp_path)
    rows = [_row("s0", "k", "t"), _row("s1", "k1", "t1")]
    rows[0].oriented_iou = iou
    with pytest.raises(ValueError, match="finite oriented_iou"):
        campaign.plan(rows, source_manifest_hash="source")


def test_events_flush_status_atomic_and_claim_release(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan(
        [_row(f"s{i}", f"k{i}", f"t{i}") for i in range(2)],
        source_manifest_hash="source",
    )
    campaign.append_event(campaign._event(plan, "source_selection"))
    status = campaign.status(plan)
    assert campaign.write_status(status).exists()
    claim = campaign.acquire_claim(plan)
    campaign.release_claim(plan, claim_hash=claim["claim_hash"])
    assert not (tmp_path / "run-claim.json").exists()


def test_watchdog_boundary_uses_monotonic_clock(tmp_path):
    ticks = iter([0.0, 120.0])
    base = CudaRolloutCampaignConfig(output_root=tmp_path)
    values = base.model_dump()
    values.update(expected_scene_count=1, profiles=base.profiles)
    config = CudaRolloutCampaignConfig.model_construct(**values)
    campaign = CudaRolloutCampaign(config, clock=lambda: next(ticks))
    unit = campaign.plan([_row("s", "k", "t")], source_manifest_hash="source").work_units[0]
    with pytest.raises(TimeoutError):
        campaign.run_with_watchdog(unit, lambda _: "done", timeout=120)


def test_work_unit_delegates_skip_to_shard_leaf(tmp_path):
    campaign = _campaign(tmp_path)
    unit = campaign.plan(
        [
            _row("s0", "k", "t"),
            _row("s1", "k1", "t1"),
        ],
        source_manifest_hash="source",
    ).work_units[0]
    calls = []

    def shard_runner(config, **kwargs):
        calls.append((config, kwargs))
        return SimpleNamespace(skipped=True)

    result = campaign.run_work_unit(
        unit,
        writer_config="writer",
        shard_entry="entry",
        output_tmp=tmp_path / "tmp",
        output_final=tmp_path / "final",
        shard_runner=shard_runner,
    )
    assert result.skipped is True
    assert calls and calls[0][1]["shard_entry"] == "entry"
