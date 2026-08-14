"""Non-CUDA contract tests for the campaign orchestration owner."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from aria_nbv.oracle.pipelines.campaign import (
    CampaignEvent,
    CampaignOutcome,
    CampaignWorkUnit,
    CudaRolloutCampaign,
    CudaRolloutCampaignConfig,
)
from aria_nbv.oracle.pipelines.rollout_dataset import RolloutDatasetWriterConfig
from aria_nbv.targets.descriptor import TargetDescriptor
from aria_nbv.targets.selection import ObservedTargetDescriptor
from aria_nbv.utils.fingerprints import stable_msgspec_hash


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
    with pytest.raises(ValueError):
        campaign.parse_worker_json('{"outcome":"succeeded"}')


def test_all_profiles_adapt_into_real_writer_candidate_mixture(tmp_path):
    campaign = _campaign(tmp_path)
    writer = RolloutDatasetWriterConfig.from_toml(".configs/build_rollouts_v1_realistic.toml")
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
        assert [r.name for r in adapted.recipes] == [
            "random_valid_h5",
            "random_valid_h8",
            "oracle_greedy_h5",
            "oracle_greedy_h8",
            "temperature_softmax_h5_t2",
            "temperature_softmax_h8_t2",
        ]
        assert [r.policy.selection_temperature for r in adapted.recipes] == [1.0, 1.0, 1.0, 1.0, 2.0, 2.0]


def _campaign(tmp_path):
    base = CudaRolloutCampaignConfig(output_root=tmp_path)
    values = base.model_dump()
    values.update(expected_scene_count=2, paired_panel_scene_count=1, profiles=base.profiles)
    config = CudaRolloutCampaignConfig.model_construct(**values)
    return CudaRolloutCampaign(config)


def test_canonical_worker_argv_carries_writer_config_path():
    config = CudaRolloutCampaignConfig.from_toml(".configs/build_rollouts_v1_cuda_campaign.toml")
    campaign = config.setup_target()
    unit = CampaignWorkUnit("cuda-rollouts-v1", "sample", "target", "realistic_core_60", "unit")
    argv = campaign.worker_argv(Path("plan.json"), unit)
    assert "--writer-config-path" in argv
    assert ".configs/build_rollouts_v1_realistic.toml" in argv


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
    assert {u.profile for u in first.work_units} == {
        "realistic_core_60",
        "rich_local_60",
        "radial_backtrack_60",
        "free_shell_upper_bound_60",
    }


def test_plan_rejects_malformed_explicit_target(tmp_path):
    campaign = _campaign(tmp_path)
    row = _row("s0", "k0", "t0")
    row.explicit_target_config = {"target_id": "t0"}
    with pytest.raises(ValueError, match="malformed explicit_target_config"):
        campaign.plan([row, _row("s1", "k1", "t1")], source_manifest_hash="source")


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


def test_events_flush_status_atomic_and_claim_release(tmp_path):
    campaign = _campaign(tmp_path)
    plan = campaign.plan(
        [_row(f"s{i}", f"k{i}", f"t{i}") for i in range(2)],
        source_manifest_hash="source",
    )
    campaign.append_event(CampaignEvent("planned", timestamp="now"))
    status = campaign.status(plan, [CampaignOutcome.SUCCEEDED] * len(plan.work_units))
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
