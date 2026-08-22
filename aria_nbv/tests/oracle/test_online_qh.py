"""Contract tests for online Q_H oracle collection seams."""

from dataclasses import replace
from pathlib import Path

import pytest
import torch
from efm3d.aria import CameraTW, PoseTW
from torch import nn

from aria_nbv.data_handling.qh_data import QhActorTensors
from aria_nbv.data_handling.qh_data.views import QhStaticContext, VinSnippetView
from aria_nbv.oracle.environment import (
    OracleDecisionContext,
    OracleQuery,
    StaleOracleDecisionContextError,
)
from aria_nbv.oracle.pipelines.online_qh import (
    OnlineQhRoundCounts,
    OnlineQhRoundRequest,
    OnlineQhRoundResult,
    _QhCandidateScoreAdapter,
)
from aria_nbv.pose_generation import CandidateSamplingResult
from aria_nbv.rollouts.replay.policy import RolloutPolicySpec
from aria_nbv.rollouts.replay.state import CounterfactualTrajectory
from aria_nbv.vin.qh_bundle import QhInferenceBundleRef


def _pose_rows(count: int) -> PoseTW:
    return PoseTW.from_matrix3x4(torch.eye(3, 4).repeat(count, 1, 1))


def _camera_rows(count: int) -> CameraTW:
    return CameraTW.from_surreal(
        width=torch.full((count,), 64.0),
        height=torch.full((count,), 64.0),
        type_str="Pinhole",
        params=torch.tensor([[60.0, 60.0, 32.0, 32.0]]).repeat(count, 1),
        gain=torch.zeros(count),
        exposure_s=torch.zeros(count),
        valid_radius=torch.full((count,), 64.0),
        T_camera_rig=PoseTW.from_matrix3x4(torch.eye(3, 4).repeat(count, 1, 1)),
    )


def _candidates() -> CandidateSamplingResult:
    return CandidateSamplingResult(
        views=_camera_rows(2),
        reference_pose=_pose_rows(1),
        mask_valid=torch.tensor([True, False, True]),
        masks={"hard_valid": torch.tensor([True, False, True])},
        shell_poses=_pose_rows(3),
    )


def _actor(candidates: CandidateSamplingResult) -> QhActorTensors:
    width = 3
    snippet = VinSnippetView(
        points_world=torch.zeros(1, 3),
        lengths=torch.tensor([1]),
        t_world_rig=_pose_rows(1),
        t_world_snippet=_pose_rows(1),
    )
    candidate_poses = _pose_rows(width).tensor().reshape(1, 1, width, 12)
    evl = torch.ones(1, 1, 1, 1)
    static = QhStaticContext(
        vin_snippet=snippet,
        t_world_voxel=_pose_rows(1),
        voxel_extent=torch.ones(6),
        occ_pr=evl,
        occ_input=evl,
        free_input=evl,
        counts=evl.long(),
        cent_pr=evl,
        pts_world=torch.zeros(1, 3),
        evl_presence=torch.ones(8, dtype=torch.bool),
    )
    return QhActorTensors(
        vin_snippet=snippet,
        root_pose_world=_pose_rows(1),
        target_pose_relative_root=_pose_rows(1),
        target_extents=torch.ones(3),
        candidate_pose_relative_root=PoseTW(candidate_poses),
        candidate_mask=torch.ones(1, width, dtype=torch.bool),
        action_mask=torch.tensor([[[True, False, True]]]),
        history_pose_relative_root=PoseTW(torch.zeros(1, 1, 12)),
        history_mask=torch.zeros(1, 1, dtype=torch.bool),
        horizon_remaining=torch.ones(1, dtype=torch.long),
        step_mask=torch.ones(1, 1, dtype=torch.bool),
        static_context=static,
    )


def _context() -> OracleDecisionContext:
    candidates = _candidates()
    return OracleDecisionContext.bind(
        episode_id="episode-1",
        trajectory=CounterfactualTrajectory(root_pose_world=_pose_rows(1)),
        candidates=candidates,
        actor=_actor(candidates),
    )


def test_decision_context_hash_is_stable_for_equivalent_payloads() -> None:
    left = _context()
    right = _context()

    assert (left.state_hash, left.table_hash, left.actor_hash) == (
        right.state_hash,
        right.table_hash,
        right.actor_hash,
    )


def test_decision_context_rejects_nested_actor_mutation() -> None:
    context = _context()
    context.actor.target_extents[0] = 2.0

    with pytest.raises(StaleOracleDecisionContextError, match="actor hash mismatch"):
        context.validate_integrity()


def test_decision_context_rejects_actor_candidate_alignment_drift() -> None:
    candidates = _candidates()
    actor = replace(_actor(candidates), action_mask=torch.tensor([[[True, True, True]]]))

    with pytest.raises(ValueError, match="action mask must equal"):
        OracleDecisionContext.bind(
            episode_id="episode-1",
            trajectory=CounterfactualTrajectory(root_pose_world=_pose_rows(1)),
            candidates=candidates,
            actor=actor,
        )


def test_decision_context_rejects_actor_candidate_pose_drift() -> None:
    candidates = _candidates()
    actor = _actor(candidates)
    pose_rows = actor.candidate_pose_relative_root.tensor().clone()
    pose_rows[0, 0, 1, -1] = 1.0
    actor = replace(actor, candidate_pose_relative_root=PoseTW(pose_rows))

    with pytest.raises(ValueError, match="candidate poses must equal"):
        OracleDecisionContext.bind(
            episode_id="episode-1",
            trajectory=CounterfactualTrajectory(root_pose_world=_pose_rows(1)),
            candidates=candidates,
            actor=actor,
        )


@pytest.mark.parametrize(
    ("mode", "shell_indices", "message"),
    [
        ("dense_valid", (0,), "must not declare"),
        ("subset", (), "non-empty"),
        ("selected_only", (0, 1), "exactly one"),
        ("subset", (1, 1), "unique"),
        ("subset", (-1,), "unique non-negative"),
    ],
)
def test_oracle_query_rejects_invalid_shell_index_policy(
    mode: str, shell_indices: tuple[int, ...], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        OracleQuery(mode, shell_indices)  # type: ignore[arg-type]


def test_oracle_query_accepts_dense_and_sparse_modes() -> None:
    assert OracleQuery("dense_valid") == OracleQuery("dense_valid", ())
    assert OracleQuery("subset", (2, 0)).shell_indices == (2, 0)
    assert OracleQuery("selected_only", (2,)).shell_indices == (2,)


def test_oracle_query_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="mode is unsupported"):
        OracleQuery("unknown")  # type: ignore[arg-type]


class _Scorer(nn.Module):
    def forward(self, actor: QhActorTensors) -> torch.Tensor:
        return torch.tensor([[[1.0, 2.0, 3.0]]], requires_grad=True)


def test_qh_candidate_score_adapter_returns_detached_values_in_full_shell_alignment() -> None:
    adapter = _QhCandidateScoreAdapter(_Scorer().eval(), behavior_model_hash="model", behavior_config_hash="config")

    scores = adapter(_context())

    assert torch.equal(scores.action_mask, torch.tensor([True, False, True]))
    assert torch.equal(scores.candidate_shell_indices, torch.tensor([0, 2]))
    assert torch.equal(scores.values, torch.tensor([1.0, 3.0]))
    assert not scores.values.requires_grad


def test_online_qh_round_request_rejects_invalid_budget_and_missing_manifest() -> None:
    bundle = QhInferenceBundleRef(Path("bundle"), "qh-inference-bundle-v1", "bundle-hash")
    policy = RolloutPolicySpec()

    with pytest.raises(ValueError, match="oracle_query_budget must be positive"):
        OnlineQhRoundRequest(bundle, Path("train.json"), 0, "proposal", policy, 0)
    with pytest.raises(ValueError, match="proposal-policy manifest"):
        OnlineQhRoundRequest(bundle, Path("train.json"), 0, "", policy, 1)
    with pytest.raises(ValueError, match="query_mode='dense_valid'"):
        OnlineQhRoundRequest(bundle, Path("train.json"), 0, "proposal", policy, 1, "subset")  # type: ignore[arg-type]


def test_online_qh_round_counts_reject_negative_counter() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        OnlineQhRoundCounts(proposed=-1, valid=0, queried=0, labeled=0, selected=0, persisted=0, rejected=0)


def test_online_qh_round_result_rejects_unknown_query_policy() -> None:
    counts = OnlineQhRoundCounts(proposed=1, valid=1, queried=1, labeled=1, selected=1, persisted=1, rejected=0)
    with pytest.raises(ValueError, match="oracle_query_policy_id='dense_valid_v1'"):
        OnlineQhRoundResult(
            shard_dir=Path("shard"),
            shard_manifest_sha256="shard",
            behavior_bundle_manifest_sha256="bundle",
            proposal_policy_manifest_sha256="proposal",
            oracle_query_policy_id="unknown",  # type: ignore[arg-type]
            selected_action_policy_sha256="selection",
            round_receipt_path=Path("receipt.json"),
            round_receipt_sha256="receipt",
            counts=counts,
        )
