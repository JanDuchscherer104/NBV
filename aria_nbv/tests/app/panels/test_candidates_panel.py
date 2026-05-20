"""Tests for candidate panel diagnostics."""

# ruff: noqa: S101, D103, SLF001

import torch
from efm3d.aria import CameraTW
from efm3d.aria.pose import PoseTW

from aria_nbv.app.panels import candidates as candidates_panel
from aria_nbv.pose_generation.types import CandidateSamplingResult

ORTHO_TOL = 1e-6
ORTHO_ERR = 1e-3


def test_pose_orthonormality_stats_identity() -> None:
    pose = PoseTW.from_Rt(torch.eye(3), torch.zeros(3))
    stats = candidates_panel._pose_orthonormality_stats(pose)
    assert stats["orth_max"] < ORTHO_TOL
    assert stats["orth_mean"] < ORTHO_TOL
    assert stats["axis_norm_max"] < ORTHO_TOL
    assert abs(stats["det_mean"] - 1.0) < ORTHO_TOL


def test_pose_orthonormality_stats_detects_scale() -> None:
    r = torch.eye(3)
    r[0, 0] = 2.0
    pose = PoseTW.from_Rt(r, torch.zeros(3))
    stats = candidates_panel._pose_orthonormality_stats(pose)
    assert stats["orth_max"] > ORTHO_ERR
    assert stats["axis_norm_max"] > ORTHO_ERR
    assert stats["det_mean"] > 1.0


def _dummy_camera() -> CameraTW:
    return CameraTW.from_surreal(
        width=torch.tensor([64.0]),
        height=torch.tensor([64.0]),
        type_str="Pinhole",
        params=torch.tensor([[60.0, 60.0, 32.0, 32.0]]),
        gain=torch.zeros(1),
        exposure_s=torch.zeros(1),
        valid_radius=torch.tensor([64.0]),
        T_camera_rig=PoseTW.from_matrix3x4(torch.eye(3, 4).unsqueeze(0)),
    )


def _candidate_result_for_pose(pose: PoseTW) -> CandidateSamplingResult:
    return CandidateSamplingResult(
        views=_dummy_camera(),
        reference_pose=pose,
        mask_valid=torch.tensor([True]),
        masks={},
        shell_poses=pose,
    )


def test_candidate_panel_color_payloads_decode_full_shell_provenance() -> None:
    result = _candidate_result_for_pose(PoseTW.from_Rt(torch.eye(3), torch.zeros(3)))
    result.position_id = torch.tensor([1])
    result.strategy_id = torch.tensor([3])
    result.extras["target_distance_m"] = torch.tensor([2.5])

    position_values, position_label = candidates_panel._color_payload_np(result, "position_family")
    strategy_values, strategy_label = candidates_panel._color_payload_np(result, "strategy")
    target_values, target_label = candidates_panel._color_payload_np(result, "target_distance")

    assert position_label == "position_id"
    assert position_values.tolist() == [1.0]
    assert strategy_label == "strategy_id"
    assert strategy_values.tolist() == [3.0]
    assert target_label == "target_distance_m"
    assert target_values.tolist() == [2.5]
