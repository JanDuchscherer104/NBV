"""Exact tests for the applicability-adjusted candidate-family gate."""

from __future__ import annotations

import pytest
import torch
from efm3d.aria.camera import CameraTW
from efm3d.aria.pose import PoseTW

from aria_nbv.pose_generation.types import CandidateSamplingResult
from aria_nbv.rollouts.candidate_benchmark import (
    CandidateBenchmark,
    CandidateFamilyCounts,
    CandidateFamilyPreflightConfig,
    CandidatePoint,
    CandidateSupportFailure,
    benchmark_from_sampling_result,
    reduce_candidate_family_preflight,
)
from aria_nbv.rollouts.candidate_support_plotting import candidate_family_preflight_figures

FAMILIES = ("forward_local", "target_bearing_local", "lateral_target_bypass")


def _record(
    *,
    state: str,
    valid: tuple[int, int, int] = (5, 5, 5),
    selected: tuple[int, int, int] = (1, 1, 1),
    applicable: tuple[bool | None, bool | None, bool | None] = (True, True, True),
    gains: tuple[float, ...] = (),
) -> CandidateBenchmark:
    families = tuple(
        CandidateFamilyCounts(
            family=name,
            applicable=is_applicable,
            attempted=count,
            valid=count,
            selected=chosen,
            denominator=count,
            invalid_reason_bitsets=(0,),
            margins={"free_space_margin_m": 0.1},
        )
        for name, is_applicable, count, chosen in zip(FAMILIES, applicable, valid, selected, strict=True)
    )
    points = tuple(
        CandidatePoint(
            candidate_id=index,
            xyz=(float(index), 0.0, 0.0),
            family=FAMILIES[index % len(FAMILIES)],
            position=FAMILIES[index % len(FAMILIES)],
            actor_valid=True,
            selected=False,
            state_key=state,
            oracle_label=True,
            target_root_gain=gain,
        )
        for index, gain in enumerate(gains)
    )
    return CandidateBenchmark(
        state_key=state,
        scene_key=f"scene-{state}",
        families=families,
        candidate_ids=tuple(point.candidate_id for point in points),
        coordinates=tuple(point.xyz for point in points),
        points=points,
    )


def _config(width: int = 60, *, require_known_applicability: bool = True) -> CandidateFamilyPreflightConfig:
    return CandidateFamilyPreflightConfig(
        query_width=width,
        configured_families=FAMILIES,
        require_known_applicability=require_known_applicability,
    )


def test_root_threshold_resolves_and_persists_exact_boundary() -> None:
    assert _config(60).resolved_min_valid == 15
    rejected = reduce_candidate_family_preflight((_record(state="14", valid=(5, 5, 4)),), _config())
    admitted = reduce_candidate_family_preflight((_record(state="15"),), _config())
    assert CandidateSupportFailure.LOW_ROOT_SUPPORT in {blocker.code for blocker in rejected.blockers}
    assert CandidateSupportFailure.LOW_ROOT_SUPPORT not in {blocker.code for blocker in admitted.blockers}
    assert _config(40).resolved_min_valid == 12
    assert admitted.to_payload()["resolved_min_valid"] == 15


def test_family_floor_is_distinct_and_forward_cannot_fill_target_deficit() -> None:
    result = reduce_candidate_family_preflight(
        (_record(state="a", valid=(10, 3, 2), selected=(9, 1, 0)),),
        _config(),
    )
    codes = {blocker.code for blocker in result.blockers}
    assert CandidateSupportFailure.LOW_ROOT_SUPPORT not in codes
    assert CandidateSupportFailure.FAMILY_COLLAPSE in codes
    assert CandidateSupportFailure.LOW_TARGET_FAMILY_SUPPORT in codes


def test_inapplicable_is_visible_non_failing_but_unknown_fails_closed() -> None:
    inapplicable = reduce_candidate_family_preflight(
        (_record(state="na", selected=(1, 1, 0), applicable=(True, True, False)),), _config()
    )
    assert not any(blocker.family == "lateral_target_bypass" for blocker in inapplicable.blockers)
    unknown = reduce_candidate_family_preflight((_record(state="legacy", applicable=(True, None, True)),), _config())
    assert CandidateSupportFailure.UNKNOWN_FAMILY_APPLICABILITY in {blocker.code for blocker in unknown.blockers}


def test_flat_gain_uses_exact_label_denominator_and_is_unavailable_without_oracle() -> None:
    passed = reduce_candidate_family_preflight((_record(state="pass", gains=(0.0, 0.2)),), _config())
    failed = reduce_candidate_family_preflight((_record(state="fail", gains=(0.1, 0.10001)),), _config())
    unavailable = reduce_candidate_family_preflight((_record(state="phase-a"),), _config())
    assert passed.flat_gain.available and passed.flat_gain.passed and passed.flat_gain.denominator == 2
    assert failed.flat_gain.available and failed.flat_gain.passed is False and failed.flat_gain.denominator == 2
    assert CandidateSupportFailure.FLAT_GAIN in {blocker.code for blocker in failed.blockers}
    assert unavailable.flat_gain.available is False
    assert unavailable.flat_gain.passed is None
    assert unavailable.flat_gain.denominator == 0


def test_preflight_figures_encode_applicability_and_all_three_stages() -> None:
    result = reduce_candidate_family_preflight(
        (_record(state="plot", applicable=(True, False, None)),),
        _config(require_known_applicability=False),
    )
    heatmap, funnel = candidate_family_preflight_figures(result)
    assert set(heatmap.data[0].text[0]) == {"20%", "N/A", "?"}
    assert {trace.name for trace in funnel.data} == {"attempted", "valid", "selected"}


def test_sampling_result_reducer_preserves_full_shell_reasons_and_margins() -> None:
    shell_poses = PoseTW.from_Rt(
        torch.eye(3).repeat(3, 1, 1),
        torch.tensor([[0.0, 0.0, 1.0], [1.0, 0.0, 1.0], [0.0, 1.0, 1.0]]),
    )
    views = CameraTW.from_surreal(
        width=torch.tensor([64.0]),
        height=torch.tensor([64.0]),
        type_str="Pinhole",
        params=torch.tensor([[60.0, 60.0, 32.0, 32.0]]),
        gain=torch.zeros(1),
        exposure_s=torch.zeros(1),
        valid_radius=torch.full((1,), 64.0),
        T_camera_rig=PoseTW.from_matrix3x4(torch.eye(3, 4).reshape(1, 3, 4)),
    )
    result = CandidateSamplingResult(
        views=views,
        reference_pose=PoseTW.from_Rt(torch.eye(3), torch.zeros(3)),
        mask_valid=torch.tensor([True, False, False]),
        masks={
            "FreeSpaceRule": torch.tensor([True, False, True]),
            "MinDistanceToMeshRule": torch.tensor([True, False, False]),
        },
        shell_poses=shell_poses,
        shell_offsets_ref=shell_poses.t,
        component_name=("forward_local", "target_bearing_local", "target_bearing_local"),
        extras={
            "free_space_margin_m": torch.tensor([0.4, -0.2, 0.3]),
            "min_distance_to_mesh": torch.tensor([0.5, 0.1, 0.05]),
        },
    )
    record = benchmark_from_sampling_result(
        result,
        scene_key="scene",
        state_key="state",
        family_positions={"forward_local": "forward_local", "target_bearing_local": "target_bearing_local"},
        target_center_world=(0.0, 0.0, 2.0),
    )
    forward, target = record.families
    assert (forward.attempted, forward.valid, forward.selected) == (1, 1, 1)
    assert (target.attempted, target.valid, target.selected) == (2, 0, 0)
    assert target.invalid_reason_bitsets
    assert target.first_failure in {"POSE_OUT_OF_EXTENT", "CLEARANCE_TOO_SMALL"}
    assert target.margins == pytest.approx({"free_space_margin_m": -0.2, "mesh_distance_m": 0.05})
    assert all(point.oracle_label is False and point.selected is False for point in record.points)
