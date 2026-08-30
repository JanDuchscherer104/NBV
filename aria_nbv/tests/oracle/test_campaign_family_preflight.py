"""Campaign consumption of the canonical candidate-family gate."""

from __future__ import annotations

import pytest

from aria_nbv.oracle.pipelines.campaign import CudaRolloutCampaign, CudaRolloutCampaignConfig
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
