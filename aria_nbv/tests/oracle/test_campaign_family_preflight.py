"""Campaign consumption of the canonical candidate-family gate."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from aria_nbv.oracle.pipelines.campaign import CudaRolloutCampaign, CudaRolloutCampaignConfig
from aria_nbv.pose_generation.types import CandidatePositionMode, ViewDirectionMode
from aria_nbv.rollouts.candidate_benchmark import (
    CandidateBenchmark,
    CandidateFamilyCounts,
    CandidateFamilyPreflight,
    CandidateFamilyPreflightConfig,
    reduce_candidate_family_preflight,
)


def _passing_result() -> CandidateFamilyPreflight:
    record = CandidateBenchmark(
        state_key="state",
        scene_key="scene",
        families=(
            CandidateFamilyCounts("forward_local", True, 5, 5, 1, 5),
            CandidateFamilyCounts("target_bearing_local", True, 5, 5, 2, 5),
            CandidateFamilyCounts("lateral_target_bypass", True, 5, 5, 1, 5),
        ),
    )
    return reduce_candidate_family_preflight(
        (record,),
        CandidateFamilyPreflightConfig(
            query_width=60,
            configured_families=("forward_local", "target_bearing_local", "lateral_target_bypass"),
        ),
    )


def test_campaign_keeps_broad_generation_blocked_until_hash_bound_wp18(monkeypatch: pytest.MonkeyPatch) -> None:
    campaign = CudaRolloutCampaign(CudaRolloutCampaignConfig())
    result = _passing_result()
    assert result.go
    monkeypatch.setattr(CudaRolloutCampaign, "candidate_family_preflight", lambda _self, _reader: result)
    with pytest.raises(RuntimeError, match="pending_wp18"):
        campaign.admit_broad_generation(object(), final_prescale_artifact=None)
    admitted = campaign.admit_broad_generation(
        object(),
        final_prescale_artifact={"issue": 120, "go": True, "artifact_sha256": "a" * 64},
    )
    assert admitted is result


def test_phase_a_adapter_stops_before_oracle_scoring(monkeypatch: pytest.MonkeyPatch) -> None:
    import aria_nbv.data_handling.vin_store.dataset as dataset_module
    import aria_nbv.oracle.pipelines.campaign as campaign_module
    import aria_nbv.oracle.pipelines.rollout_dataset as rollout_dataset_module
    import aria_nbv.oracle.target_selection as target_selection_module

    class _Sample:
        sample_key = "sample"
        efm_snippet_view = SimpleNamespace(has_mesh=True)

    target = SimpleNamespace(
        target_id="target",
        descriptor=SimpleNamespace(center_world=(0.0, 0.0, 2.0)),
    )
    target_result = SimpleNamespace(selected_rows=(target,), rows=(target,), source="gt_obbs_oracle")
    generator = SimpleNamespace(generate_from_typed_sample=lambda *_args, **_kwargs: object())
    components = [
        SimpleNamespace(
            name="forward_local",
            position_mode=CandidatePositionMode.FORWARD_LOCAL,
            paired_view_mode=None,
        ),
        SimpleNamespace(
            name="target_bearing_local",
            position_mode=CandidatePositionMode.TARGET_BEARING_LOCAL,
            paired_view_mode=ViewDirectionMode.TARGET_POINT,
        ),
    ]
    mixture = SimpleNamespace(components=components, total_count=15, setup_target=lambda: generator)
    source_row = SimpleNamespace(sample_key="sample", scene_id="scene")
    writer = SimpleNamespace(
        source=SimpleNamespace(setup_target=lambda: [_Sample()]),
        sample_keys=None,
        oracle_target_task_sampler=object(),
        candidate_mixture=mixture,
        selected_source_manifest_rows=lambda _manifest: (source_row,),
        model_dump_jsonable=lambda: {"candidate_mixture": "fixture"},
    )
    manifest = SimpleNamespace(source_manifest_hash="a" * 16)
    record = CandidateBenchmark(
        state_key="source:sample/target:target",
        scene_key="scene",
        families=(
            CandidateFamilyCounts("forward_local", True, 8, 8, 8, 8),
            CandidateFamilyCounts("target_bearing_local", True, 7, 7, 7, 7),
            CandidateFamilyCounts("target_bearing_local__paired_target_point", True, 7, 7, 7, 7),
        ),
    )
    monkeypatch.setattr(dataset_module, "VinOfflineSample", _Sample)
    monkeypatch.setattr(
        target_selection_module,
        "OracleTargetTaskSampler",
        lambda _config: SimpleNamespace(sample=lambda _sample: target_result),
    )
    monkeypatch.setattr(rollout_dataset_module.RolloutDatasetWriter, "_apply_source_manifest", lambda *_a, **_k: None)
    monkeypatch.setattr(campaign_module, "benchmark_from_sampling_result", lambda *_a, **_k: record)
    evidence = CudaRolloutCampaign(CudaRolloutCampaignConfig()).candidate_family_phase_a(
        writer,
        manifest,
        source_manifest_sha256="c" * 64,
    )

    assert evidence.source_row_count == evidence.scene_count == evidence.target_state_count == 1
    assert evidence.source_store_manifest_hash == "a" * 16
    assert evidence.preflight.go
    assert evidence.preflight.flat_gain.available is False
    assert evidence.to_payload()["broad_generation_admitted"] is False
