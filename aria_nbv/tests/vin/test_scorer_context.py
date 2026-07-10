"""Tests for shared VIN scorer tensor-preparation helpers."""

# ruff: noqa: S101

import pytest
import torch
from efm3d.aria.pose import PoseTW

from aria_nbv.data_handling.raw import VinSnippetView
from aria_nbv.vin.scorer_context import (
    apply_vin_scorer_film,
    build_vin_scorer_scene_field,
    encode_trajectory_context,
)
from aria_nbv.vin.types import EvlBackboneOutput


class _DummyPerFrame:
    def __init__(self, pose_vec: torch.Tensor, pose_enc: torch.Tensor) -> None:
        self.pose_vec = pose_vec
        self.pose_enc = pose_enc


class _DummyTrajectoryOutput:
    def __init__(self, pose_vec: torch.Tensor, pose_enc: torch.Tensor, pooled: torch.Tensor | None) -> None:
        self.per_frame = _DummyPerFrame(pose_vec=pose_vec, pose_enc=pose_enc)
        self.pooled = pooled


class _RecordingTrajectoryEncoder:
    out_dim = 3

    def __init__(self, *, pooled: torch.Tensor | None = None) -> None:
        self.pooled = pooled
        self.last_poses: PoseTW | None = None

    def encode_poses(self, poses: PoseTW) -> _DummyTrajectoryOutput:
        self.last_poses = poses
        pose_vec = poses.t
        pose_enc = torch.cat([pose_vec, pose_vec[..., : self.out_dim]], dim=-1)
        pooled = self.pooled
        if pooled is None:
            pooled = pose_enc.mean(dim=1)
        return _DummyTrajectoryOutput(pose_vec=pose_vec, pose_enc=pose_enc, pooled=pooled)


def _make_backbone_out(*, free_input: torch.Tensor | None = None) -> EvlBackboneOutput:
    occ_pr = torch.tensor([[[[[0.2]], [[0.8]]]]], dtype=torch.float32)
    occ_input = torch.tensor([[[[[0.25]], [[0.75]]]]], dtype=torch.float32)
    cent_pr = torch.tensor([[[[[0.4]], [[0.6]]]]], dtype=torch.float32)
    counts = torch.tensor([[[[1.0]], [[3.0]]]], dtype=torch.float32)
    pts_world = torch.zeros((1, 2, 1, 1, 3), dtype=torch.float32)
    voxel_extent = torch.tensor([[-1.0, 1.0, -1.0, 1.0, -1.0, 1.0]], dtype=torch.float32)
    t_world_voxel = PoseTW.from_Rt(
        torch.eye(3, dtype=torch.float32).unsqueeze(0),
        torch.zeros((1, 3), dtype=torch.float32),
    )
    return EvlBackboneOutput(
        occ_feat=None,
        obb_feat=None,
        occ_pr=occ_pr,
        occ_input=occ_input,
        free_input=free_input,
        counts=counts,
        counts_m=None,
        cent_pr=cent_pr,
        pts_world=pts_world,
        t_world_voxel=t_world_voxel,
        voxel_extent=voxel_extent,
    )


def _make_reference_pose(batch_size: int) -> PoseTW:
    rot = torch.eye(3, dtype=torch.float32).repeat(batch_size, 1, 1)
    trans = torch.zeros((batch_size, 3), dtype=torch.float32)
    return PoseTW.from_Rt(rot, trans)


def _make_vin_snippet_with_traj(t_world_rig: PoseTW) -> VinSnippetView:
    return VinSnippetView(
        points_world=torch.zeros((0, 5), dtype=torch.float32),
        lengths=torch.tensor([0], dtype=torch.int64),
        t_world_rig=t_world_rig,
    )


def test_build_vin_scorer_scene_field_uses_soft_unknown_contract() -> None:
    """Scorer fields should use ``unknown = 1 - counts_norm``."""
    out = _make_backbone_out()

    field_in, aux = build_vin_scorer_scene_field(
        out,
        scene_field_channels=["counts_norm", "unknown", "new_surface_prior"],
        model_name="VinModelV3",
    )

    counts = out.counts.to(dtype=torch.float32)  # type: ignore[union-attr]
    max_counts = counts.amax(dim=(-3, -2, -1), keepdim=True).clamp_min(1.0)
    expected_counts_norm = (torch.log1p(counts) / torch.log1p(max_counts)).unsqueeze(1)
    expected_unknown = 1.0 - expected_counts_norm
    assert torch.allclose(aux["counts_norm"], expected_counts_norm)
    assert torch.allclose(aux["unknown"], expected_unknown)
    assert not torch.allclose(aux["unknown"], 1.0 - aux["observed"])
    assert torch.allclose(aux["new_surface_prior"], expected_unknown * aux["occ_pr"])
    assert torch.allclose(field_in[:, 0], expected_counts_norm[:, 0])


def test_build_vin_scorer_scene_field_uses_raw_occ_input_fallback() -> None:
    """Absent free_input should fall back to observed * (1 - occ_input)."""
    out = _make_backbone_out()

    _field_in, aux = build_vin_scorer_scene_field(
        out,
        scene_field_channels=["free_input"],
        model_name="VinModelV3",
    )

    expected = aux["observed"] * (1.0 - aux["occ_input"])
    assert torch.allclose(aux["free_input"], expected)
    assert aux["free_input"].flatten().tolist() == pytest.approx([0.75, 0.25])


def test_build_vin_scorer_scene_field_preserves_free_input_and_channel_order() -> None:
    """Provided free-space evidence should be preserved and ordered as requested."""
    free_input = torch.tensor([[[[[0.1]], [[0.9]]]]], dtype=torch.float32)
    out = _make_backbone_out(free_input=free_input)

    field_in, aux = build_vin_scorer_scene_field(
        out,
        scene_field_channels=["cent_pr", "free_input", "occ_pr"],
        model_name="VinModelV3",
    )

    assert torch.allclose(aux["free_input"], free_input)
    assert torch.allclose(field_in[:, 0], aux["cent_pr"][:, 0])
    assert torch.allclose(field_in[:, 1], free_input[:, 0])
    assert torch.allclose(field_in[:, 2], aux["occ_pr"][:, 0])


def test_build_vin_scorer_scene_field_rejects_unknown_channel() -> None:
    """Invalid channel names should report the owning model config surface."""
    out = _make_backbone_out()

    with pytest.raises(ValueError, match=r"VinModelV3\.scene_field_channels"):
        build_vin_scorer_scene_field(
            out,
            scene_field_channels=["occ_pr", "not_a_channel"],
            model_name="VinModelV3",
        )


def test_apply_vin_scorer_film_uses_shared_formula() -> None:
    """FiLM helper should apply global * (1 + gamma) + beta."""
    global_feat = torch.ones((1, 2, 3), dtype=torch.float32)
    cond_feat = torch.tensor([[[2.0], [4.0]]], dtype=torch.float32)
    film = torch.nn.Linear(1, 6, bias=False)
    with torch.no_grad():
        film.weight.copy_(
            torch.tensor(
                [
                    [1.0],
                    [2.0],
                    [3.0],
                    [4.0],
                    [5.0],
                    [6.0],
                ],
                dtype=torch.float32,
            ),
        )

    out = apply_vin_scorer_film(global_feat, cond_feat, film=film, norm=None)
    film_out = film(cond_feat)
    gamma, beta = film_out.chunk(2, dim=-1)

    assert torch.allclose(out, global_feat * (1.0 + gamma) + beta)


def test_apply_vin_scorer_film_preserves_single_condition_broadcast() -> None:
    """A ``(B, 1, F)`` conditioning tensor should broadcast across candidates."""
    global_feat = torch.ones((2, 3, 2), dtype=torch.float32)
    cond_feat = torch.tensor([[[1.0]], [[3.0]]], dtype=torch.float32)
    film = torch.nn.Linear(1, 4, bias=False)
    with torch.no_grad():
        film.weight.fill_(1.0)

    out = apply_vin_scorer_film(global_feat, cond_feat, film=film, norm=None)

    assert out.shape == global_feat.shape
    assert torch.allclose(out[0], torch.full((3, 2), 3.0))
    assert torch.allclose(out[1], torch.full((3, 2), 7.0))


def test_encode_trajectory_context_missing_traj_returns_zero_feature() -> None:
    """Missing trajectory data should keep the prior zero-feature fallback."""
    encoder = _RecordingTrajectoryEncoder()

    traj_feat, traj_pose_vec, traj_pose_enc = encode_trajectory_context(
        traj_encoder=encoder,
        snippet=None,
        pose_world_rig_ref=_make_reference_pose(2),
        batch_size=2,
        device=torch.device("cpu"),
        dtype=torch.float32,
    )

    assert traj_feat is not None
    assert torch.allclose(traj_feat, torch.zeros((2, encoder.out_dim)))
    assert traj_pose_vec is None
    assert traj_pose_enc is None
    assert encoder.last_poses is None


def test_encode_trajectory_context_broadcasts_single_trajectory() -> None:
    """A single trajectory sequence should broadcast to all batch items."""
    encoder = _RecordingTrajectoryEncoder()
    t_world_rig = PoseTW.from_Rt(
        torch.eye(3, dtype=torch.float32).repeat(4, 1, 1),
        torch.zeros((4, 3), dtype=torch.float32),
    )
    snippet = _make_vin_snippet_with_traj(t_world_rig)

    traj_feat, traj_pose_vec, traj_pose_enc = encode_trajectory_context(
        traj_encoder=encoder,
        snippet=snippet,
        pose_world_rig_ref=_make_reference_pose(3),
        batch_size=3,
        device=torch.device("cpu"),
        dtype=torch.float32,
    )

    assert encoder.last_poses is not None
    assert encoder.last_poses.shape[:2] == (3, 4)
    assert traj_feat is not None
    assert traj_feat.shape[0] == 3
    assert traj_pose_vec is not None
    assert traj_pose_vec.shape[:2] == (3, 4)
    assert traj_pose_enc is not None
    assert traj_pose_enc.shape[:2] == (3, 4)


def test_encode_trajectory_context_rejects_mismatched_batch() -> None:
    """Non-broadcastable trajectory batches should keep the existing error."""
    encoder = _RecordingTrajectoryEncoder()
    t_world_rig = PoseTW.from_Rt(
        torch.eye(3, dtype=torch.float32).repeat(2, 4, 1, 1),
        torch.zeros((2, 4, 3), dtype=torch.float32),
    )
    snippet = _make_vin_snippet_with_traj(t_world_rig)

    with pytest.raises(ValueError, match="Trajectory batch size must match candidates"):
        encode_trajectory_context(
            traj_encoder=encoder,
            snippet=snippet,
            pose_world_rig_ref=_make_reference_pose(3),
            batch_size=3,
            device=torch.device("cpu"),
            dtype=torch.float32,
        )


def test_encode_trajectory_context_uses_reference_rig_frame() -> None:
    """Trajectory poses should be encoded after ``(T_w_ref)^-1 @ T_w_traj``."""
    encoder = _RecordingTrajectoryEncoder()
    reference = PoseTW.from_Rt(
        torch.eye(3, dtype=torch.float32).unsqueeze(0),
        torch.tensor([[1.0, 0.0, 0.0]], dtype=torch.float32),
    )
    t_world_rig = PoseTW.from_Rt(
        torch.eye(3, dtype=torch.float32).repeat(2, 1, 1),
        torch.tensor([[3.0, 0.0, 0.0], [5.0, 0.0, 0.0]], dtype=torch.float32),
    )
    snippet = _make_vin_snippet_with_traj(t_world_rig)

    encode_trajectory_context(
        traj_encoder=encoder,
        snippet=snippet,
        pose_world_rig_ref=reference,
        batch_size=1,
        device=torch.device("cpu"),
        dtype=torch.float32,
    )

    assert encoder.last_poses is not None
    assert torch.allclose(
        encoder.last_poses.t,
        torch.tensor([[[2.0, 0.0, 0.0], [4.0, 0.0, 0.0]]], dtype=torch.float32),
    )
