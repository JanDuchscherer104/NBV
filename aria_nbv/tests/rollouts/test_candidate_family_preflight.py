"""Exact tests for the applicability-adjusted candidate-family gate."""

from __future__ import annotations

import gc
import json
import pickle
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from typing import Any, get_type_hints

import numpy as np
import pytest
import torch
from efm3d.aria.camera import CameraTW
from efm3d.aria.pose import PoseTW

from aria_nbv.pose_generation.types import CandidateSamplingResult
from aria_nbv.rollouts.candidate_benchmark import (
    EVIDENCE_ASSEMBLY_REVISION,
    PROVENANCE_CORRECTION_REVISION,
    WRITER_CONFIG_IDENTITY_REVISION,
    CandidateBenchmark,
    CandidateFamilyCounts,
    CandidateFamilyPhaseAEvidence,
    CandidateFamilyPhaseAExpectation,
    CandidateFamilyPreflightConfig,
    CandidateFamilySelection,
    CandidatePoint,
    CandidatePopulationCoverage,
    CandidateSupportFailure,
    EvidenceTransformationKind,
    benchmark_from_sampling_result,
    benchmarks_from_reader,
    candidate_family_preflight_from_reader,
    canonical_generation_revision_hash,
    canonical_json_bytes,
    read_candidate_family_phase_a,
    reduce_candidate_family_preflight,
    reduce_candidate_records,
    reframe_candidate_benchmark_target_aligned,
    scientific_writer_config_sha256,
    select_candidate_family_shell,
    sha256_bytes,
    target_side_count_balance,
    write_candidate_family_phase_a,
)
from aria_nbv.rollouts.candidate_support_plotting import candidate_family_preflight_figures
from aria_nbv.rollouts.read_model import candidate_mixture_family_names

FAMILIES = ("forward_local", "target_bearing_local", "lateral_target_bypass")


def _generation_revision() -> dict[str, str]:
    revision = {
        "contract_revision": "candidate-family-phase-a-v2",
        "clean_commit": "a" * 40,
        "head_tree": "b" * 40,
        "uv_lock_sha256": "c" * 64,
        "content_bundle_hash": "d" * 64,
    }
    return {**revision, "revision_hash": canonical_generation_revision_hash(revision)}


def _record(
    *,
    state: str,
    scene: str | None = None,
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
        scene_key=scene or f"scene-{state}",
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


def test_public_reducer_accepts_only_canonical_benchmark_records() -> None:
    hints = get_type_hints(reduce_candidate_family_preflight)
    assert hints["records"] == Iterable[CandidateBenchmark]

    canonical = _record(state="canonical")
    assert reduce_candidate_family_preflight((canonical,), _config()).cells

    class StructuralRecord:
        scene_key = canonical.scene_key
        state_key = canonical.state_key
        families = canonical.families

    structural_records: Any = (StructuralRecord(),)
    with pytest.raises(TypeError, match="CandidateBenchmark"):
        reduce_candidate_family_preflight(structural_records, _config())


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


def test_inapplicable_recorded_failure_remains_visible_but_nonblocking() -> None:
    record = _record(state="na", applicable=(True, True, False), selected=(1, 2, 0))
    lateral = record.families[2]
    record = CandidateBenchmark(
        state_key=record.state_key,
        scene_key=record.scene_key,
        families=(*record.families[:2], replace(lateral, support_failure="target unavailable")),
    )

    result = reduce_candidate_family_preflight((record,), _config())

    assert not any(blocker.family == "lateral_target_bypass" for blocker in result.blockers)
    assert result.cells[2][2].support_failure == "target unavailable"


def test_empty_population_fails_with_typed_coverage_blocker() -> None:
    result = reduce_candidate_family_preflight((), _config())

    assert result.go is False
    assert CandidateSupportFailure.MISSING_POPULATION_COVERAGE in {blocker.code for blocker in result.blockers}


def test_flat_gain_uses_exact_label_denominator_and_is_unavailable_without_oracle() -> None:
    passed = reduce_candidate_family_preflight((_record(state="pass", gains=(0.0, 0.2)),), _config())
    failed = reduce_candidate_family_preflight((_record(state="fail", gains=(0.1, 0.10001)),), _config())
    unavailable = reduce_candidate_family_preflight((_record(state="phase-a"),), _config())
    assert passed.flat_gain.available and passed.flat_gain.passed and passed.flat_gain.denominator == 2
    assert passed.flat_gain.eligible_state_denominator == 1
    assert failed.flat_gain.available and failed.flat_gain.passed is False and failed.flat_gain.denominator == 2
    assert CandidateSupportFailure.FLAT_GAIN in {blocker.code for blocker in failed.blockers}
    assert unavailable.flat_gain.available is False
    assert unavailable.flat_gain.passed is None
    assert unavailable.flat_gain.denominator == 0


def test_flat_gain_is_state_conditional_not_population_pooled() -> None:
    varied = _record(state="varied", gains=(0.0, 1.0))
    flat = _record(state="flat", gains=(100.0, 100.0))

    result = reduce_candidate_family_preflight((varied, flat), _config())

    assert result.flat_gain.denominator == 4
    assert result.flat_gain.eligible_state_denominator == 2
    assert result.flat_gain.observed_range == pytest.approx(0.0)
    assert any(
        blocker.code is CandidateSupportFailure.FLAT_GAIN and blocker.state_key == "flat" for blocker in result.blockers
    )


def test_preflight_figures_encode_applicability_and_all_three_stages() -> None:
    result = reduce_candidate_family_preflight(
        (_record(state="plot", applicable=(True, False, None)),),
        _config(require_known_applicability=False),
    )
    heatmap, funnel = candidate_family_preflight_figures(result)
    assert set(heatmap.data[0].text[0]) == {"20%", "N/A", "?"}
    assert len(heatmap.layout.shapes) == 5
    assert {trace.name for trace in funnel.data} == {"attempted", "valid", "selected"}
    assert heatmap.data[0].customdata[0][0][:3] == ["scene-plot", "plot", "forward_local"]


def test_preflight_funnel_supports_full_hundred_state_phase_a_population() -> None:
    result = reduce_candidate_family_preflight(
        tuple(_record(state=f"state-{index:03d}") for index in range(100)),
        _config(),
    )

    heatmap, funnel = candidate_family_preflight_figures(result)
    _, bounded_funnel = candidate_family_preflight_figures(
        result,
        funnel_identities={("scene-state-000", "state-000")},
    )

    assert len(heatmap.data[0].y) == 100
    assert len(funnel.data) == 300
    assert len(bounded_funnel.data) == 3


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
        target_center_world=(0.0, 2.0, 0.0),
    )
    forward, target = record.families
    assert (forward.attempted, forward.valid, forward.selected) == (1, 1, 1)
    assert (target.attempted, target.valid, target.selected) == (2, 0, 0)
    assert target.invalid_reason_bitsets
    assert target.first_failure in {"POSE_OUT_OF_EXTENT", "CLEARANCE_TOO_SMALL"}
    assert target.margins == pytest.approx({"free_space_margin_m": -0.2, "mesh_distance_m": 0.05})
    assert all(point.oracle_label is False and point.selected is False for point in record.points)


def test_sampling_result_rotates_nonzero_rig_target_yaw_into_target_aligned_z_up() -> None:
    reference_rotation = torch.tensor(
        [[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        dtype=torch.float32,
    )
    world_offsets = torch.tensor([[-1.0, 2.0, 0.0], [1.0, 2.0, 0.0]])
    offsets_ref = world_offsets @ reference_rotation
    view_rotations = torch.stack(
        (
            torch.tensor([[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]),
            torch.tensor([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]]),
        )
    )
    result = CandidateSamplingResult(
        views=CameraTW.from_surreal(
            width=torch.tensor([64.0]),
            height=torch.tensor([64.0]),
            type_str="Pinhole",
            params=torch.tensor([[60.0, 60.0, 32.0, 32.0]]),
            gain=torch.zeros(1),
            exposure_s=torch.zeros(1),
            valid_radius=torch.full((1,), 64.0),
            T_camera_rig=PoseTW.from_matrix3x4(torch.eye(3, 4).reshape(1, 3, 4)),
        ),
        reference_pose=PoseTW.from_Rt(reference_rotation, torch.zeros(3)),
        mask_valid=torch.ones(2, dtype=torch.bool),
        masks={},
        shell_poses=PoseTW.from_Rt(view_rotations, world_offsets),
        shell_offsets_ref=offsets_ref,
        component_name=("target_bearing_local", "target_bearing_local"),
    )

    record = benchmark_from_sampling_result(
        result,
        scene_key="scene",
        state_key="yawed",
        family_positions={"target_bearing_local": "target_bearing_local"},
        target_center_world=(0.0, 2.0, 0.0),
    )

    assert np.allclose(record.coordinates, ((1.0, 0.5, 0.0), (1.0, -0.5, 0.0)))
    assert np.allclose(tuple(point.target_relative_xyz for point in record.points), ((0.0, 0.5, 0.0), (0.0, -0.5, 0.0)))
    assert np.allclose(tuple(point.view_direction_xyz for point in record.points), ((0.0, 1.0, 0.0), (0.0, -1.0, 0.0)))
    assert all(
        tuple(np.asarray(point.xyz) - np.asarray(point.target_relative_xyz)) == pytest.approx((1.0, 0.0, 0.0))
        for point in record.points
    )
    assert target_side_count_balance(record.points) == pytest.approx(1.0)


def test_authenticated_geometry_correction_preserves_support_and_rotates_all_vectors() -> None:
    record = CandidateBenchmark(
        scene_key="scene",
        state_key="legacy-reference-frame",
        families=(CandidateFamilyCounts("target_bearing_local", True, 2, 2, 2, 2),),
        candidate_ids=(0, 1),
        coordinates=((1.0, 0.0, -0.5), (1.0, 0.0, 0.5)),
        points=(
            CandidatePoint(
                candidate_id=0,
                xyz=(1.0, 0.0, -0.5),
                family="target_bearing_local",
                position="target_bearing_local",
                actor_valid=True,
                selected=False,
                state_key="legacy-reference-frame",
                target_relative_xyz=(0.0, 0.0, -0.5),
                view_direction_xyz=(0.0, 0.0, -1.0),
            ),
            CandidatePoint(
                candidate_id=1,
                xyz=(1.0, 0.0, 0.5),
                family="target_bearing_local",
                position="target_bearing_local",
                actor_valid=True,
                selected=False,
                state_key="legacy-reference-frame",
                target_relative_xyz=(0.0, 0.0, 0.5),
                view_direction_xyz=(0.0, 0.0, 1.0),
            ),
        ),
    )
    reference_rotation = ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))

    corrected = reframe_candidate_benchmark_target_aligned(
        record,
        reference_rotation_world_from_ref=reference_rotation,
    )

    assert corrected.families == record.families
    assert corrected.candidate_ids == record.candidate_ids
    assert np.allclose(corrected.coordinates, ((1.0, 0.5, 0.0), (1.0, -0.5, 0.0)))
    assert np.allclose(
        tuple(point.target_relative_xyz for point in corrected.points),
        ((0.0, 0.5, 0.0), (0.0, -0.5, 0.0)),
    )
    assert np.allclose(
        tuple(point.view_direction_xyz for point in corrected.points),
        ((0.0, 1.0, 0.0), (0.0, -1.0, 0.0)),
    )
    assert corrected.lineage["geometry_frame"] == "target_aligned_z_up"
    assert target_side_count_balance(corrected.points) == pytest.approx(1.0)


def test_margins_are_immutable_while_preflight_payload_is_pickleable() -> None:
    result = reduce_candidate_family_preflight((_record(state="immutable"),), _config())
    with pytest.raises(TypeError):
        result.cells[0][2].margins["free_space_margin_m"] = 2.0  # type: ignore[index]

    assert pickle.loads(pickle.dumps(result.to_payload())) == result.to_payload()


def test_family_margins_reject_nonfinite_or_nonscalar_payloads() -> None:
    malformed_margins: tuple[Any, ...] = (
        {"nested": {"value": 1.0}},
        {"list": [1.0]},
        {"nan": float("nan")},
        {"positive_inf": float("inf")},
        {"negative_inf": float("-inf")},
        {"bool": True},
        {1: 1.0},
        {"": 1.0},
    )
    for margins in malformed_margins:
        with pytest.raises(ValueError, match="margin"):
            CandidateFamilyCounts("forward", True, 1, 1, 1, 1, margins=margins)


def test_family_selection_filters_the_existing_shell_without_recomputing() -> None:
    record = _record(state="select", gains=(0.0, 1.0, 2.0))

    selected = select_candidate_family_shell(
        (record,),
        CandidateFamilySelection("scene-select", "select", "target_bearing_local"),
    )

    assert len(selected) == 1
    assert [family.family for family in selected[0].families] == ["target_bearing_local"]
    assert {point.family for point in selected[0].points} == {"target_bearing_local"}


def test_scientific_writer_identity_ignores_acquisition_and_output_paths() -> None:
    def payload(root: str) -> dict[str, object]:
        return {
            "source_manifest_path": f"{root}/manifest.json",
            "source": {
                "paths": {"root": root},
                "store": {"paths": {"root": root}, "store_dir": f"{root}/source", "split": "train"},
            },
            "store": {"paths": {"root": root}, "store_dir": f"{root}/output", "discount_gamma": 1.0},
            "candidate_mixture": {"total_count": 60},
        }

    first = scientific_writer_config_sha256(payload("/checkout-a"), source_store_manifest_hash="a" * 16)
    second = scientific_writer_config_sha256(payload("/checkout-b"), source_store_manifest_hash="a" * 16)

    assert first == second
    assert first != scientific_writer_config_sha256(payload("/checkout-a"), source_store_manifest_hash="b" * 16)

    scientifically_changed = payload("/checkout-a")
    scientifically_changed["candidate_mixture"] = {"total_count": 61, "paths": {"penalty": 2.0}}
    assert first != scientific_writer_config_sha256(
        scientifically_changed,
        source_store_manifest_hash="a" * 16,
    )


def test_duplicate_state_keys_across_scenes_remain_distinct_end_to_end() -> None:
    records = (
        _record(state="shared", scene="scene-a", gains=(0.0, 0.0)),
        _record(state="shared", scene="scene-b", gains=(0.0, 1.0)),
    )

    result = reduce_candidate_family_preflight(records, _config())
    heatmap, _ = candidate_family_preflight_figures(result)
    selected = select_candidate_family_shell(
        records,
        CandidateFamilySelection("scene-b", "shared", "target_bearing_local"),
    )

    assert {(scene, state) for scene, state, _ in result.cells} == {
        ("scene-a", "shared"),
        ("scene-b", "shared"),
    }
    assert {(blocker.scene_key, blocker.state_key) for blocker in result.blockers if blocker.state_key} >= {
        ("scene-a", "shared"),
    }
    assert len(heatmap.data[0].y) == 2
    assert len(selected) == 1 and selected[0].scene_key == "scene-b"


def test_historical_single_root_identity_rejects_repeated_scene_state_until_future_provenance() -> None:
    record = _record(state="shared", scene="scene-a").to_record()

    with pytest.raises(ValueError, match="duplicate benchmark state key"):
        reduce_candidate_records([record, record])


def test_phase_a_reader_validates_compact_content_source_policy_and_revision(tmp_path: Path) -> None:
    record = _record(state="phase-a", selected=(1, 2, 1))
    config = replace(_config(), expected_population_size=1)
    preflight = reduce_candidate_family_preflight(
        (record,),
        config,
        coverage=CandidatePopulationCoverage(1, 1, 1, 1, 1),
    )
    revision = _generation_revision()
    evidence = CandidateFamilyPhaseAEvidence(
        source_manifest_sha256="e" * 64,
        source_store_manifest_hash="f" * 16,
        source_cache_version="source-cache-v1",
        split_manifest_hash="split-v1",
        source_store_dir="source-store",
        writer_config_sha256="1" * 64,
        writer_config_identity_revision=WRITER_CONFIG_IDENTITY_REVISION,
        provenance_correction_revision=PROVENANCE_CORRECTION_REVISION,
        evidence_assembly_revision=EVIDENCE_ASSEMBLY_REVISION,
        predecessor_artifact_sha256=None,
        transformation_kind=EvidenceTransformationKind.ORIGINAL_GENERATION,
        implementation_revision="a" * 40,
        generation_revision=revision,
        runtime_identity={
            "python": "3.11.15",
            "torch": "2.7.1",
            "cuda": "12.8",
            "pytorch3d": "0.7.8",
            "gpu_name": "fixture",
            "gpu_capability": "8.9",
        },
        source_row_count=1,
        scene_count=1,
        target_state_count=1,
        excluded_source_rows={},
        records=(record,),
        preflight=preflight,
    )
    expected = CandidateFamilyPhaseAExpectation(
        source_manifest_sha256="e" * 64,
        source_store_manifest_hash="f" * 16,
        source_cache_version="source-cache-v1",
        split_manifest_hash="split-v1",
        source_store_dir="source-store",
        writer_config_sha256="1" * 64,
        generation_revision_hash=revision["revision_hash"],
    )
    path = write_candidate_family_phase_a(tmp_path / "phase-a.json", evidence)

    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
    assert read_candidate_family_phase_a(path, expected=expected).to_payload() == evidence.to_payload()

    tampered = path.read_text(encoding="utf-8").replace('"selected":2', '"selected":1', 1)
    path.write_text(tampered, encoding="utf-8")
    with pytest.raises(ValueError, match="content hash mismatch"):
        read_candidate_family_phase_a(path, expected=expected)


def test_phase_a_reader_recomputes_generation_revision_after_outer_rehash(tmp_path: Path) -> None:
    record = _record(state="revision", selected=(1, 2, 1))
    config = replace(_config(), expected_population_size=1)
    revision = _generation_revision()
    evidence = CandidateFamilyPhaseAEvidence(
        source_manifest_sha256="e" * 64,
        source_store_manifest_hash="f" * 16,
        source_cache_version="source-cache-v1",
        split_manifest_hash="split-v1",
        source_store_dir="source-store",
        writer_config_sha256="1" * 64,
        writer_config_identity_revision=WRITER_CONFIG_IDENTITY_REVISION,
        provenance_correction_revision=PROVENANCE_CORRECTION_REVISION,
        evidence_assembly_revision=EVIDENCE_ASSEMBLY_REVISION,
        predecessor_artifact_sha256=None,
        transformation_kind=EvidenceTransformationKind.ORIGINAL_GENERATION,
        implementation_revision="a" * 40,
        generation_revision=revision,
        runtime_identity={
            "python": "3.11.15",
            "torch": "2.7.1",
            "cuda": "12.8",
            "pytorch3d": "0.7.8",
            "gpu_name": "fixture",
            "gpu_capability": "8.9",
        },
        source_row_count=1,
        scene_count=1,
        target_state_count=1,
        excluded_source_rows={},
        records=(record,),
        preflight=reduce_candidate_family_preflight(
            (record,), config, coverage=CandidatePopulationCoverage(1, 1, 1, 1, 1)
        ),
    )
    path = write_candidate_family_phase_a(tmp_path / "phase-a.json", evidence)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("artifact_sha256")
    payload["generation_revision"]["head_tree"] = "9" * 40
    payload["artifact_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    path.write_bytes(canonical_json_bytes(payload) + b"\n")
    expected = CandidateFamilyPhaseAExpectation(
        "e" * 64, "f" * 16, "source-cache-v1", "split-v1", "source-store", "1" * 64, revision["revision_hash"]
    )

    with pytest.raises(ValueError, match="generation revision hash mismatch"):
        read_candidate_family_phase_a(path, expected=expected)


def test_phase_a_reader_preserves_authenticated_persisted_record_order(tmp_path: Path) -> None:
    records = (
        _record(state="z-last", valid=(5, 5, 5)),
        _record(state="a-first", valid=(5, 5, 5)),
    )
    config = replace(_config(), expected_population_size=2)
    coverage = CandidatePopulationCoverage(2, 2, 2, 2, 2)
    preflight = reduce_candidate_family_preflight(records, config, coverage=coverage)
    evidence = CandidateFamilyPhaseAEvidence(
        source_manifest_sha256="e" * 64,
        source_store_manifest_hash="f" * 16,
        source_cache_version="source-cache-v1",
        split_manifest_hash="split-v1",
        source_store_dir="source-store",
        writer_config_sha256="1" * 64,
        writer_config_identity_revision=WRITER_CONFIG_IDENTITY_REVISION,
        provenance_correction_revision=PROVENANCE_CORRECTION_REVISION,
        evidence_assembly_revision=EVIDENCE_ASSEMBLY_REVISION,
        predecessor_artifact_sha256=None,
        transformation_kind=EvidenceTransformationKind.ORIGINAL_GENERATION,
        implementation_revision="a" * 40,
        generation_revision=_generation_revision(),
        runtime_identity={
            "python": "3.11.15",
            "torch": "2.7.1",
            "cuda": "12.8",
            "pytorch3d": "0.7.8",
            "gpu_name": "fixture",
            "gpu_capability": "8.9",
        },
        source_row_count=2,
        scene_count=2,
        target_state_count=2,
        excluded_source_rows={},
        records=records,
        preflight=preflight,
    )
    expected = CandidateFamilyPhaseAExpectation(
        source_manifest_sha256="e" * 64,
        source_store_manifest_hash="f" * 16,
        source_cache_version="source-cache-v1",
        split_manifest_hash="split-v1",
        source_store_dir="source-store",
        writer_config_sha256="1" * 64,
        generation_revision_hash=_generation_revision()["revision_hash"],
    )

    restored = read_candidate_family_phase_a(
        write_candidate_family_phase_a(tmp_path / "phase-a.json", evidence),
        expected=expected,
    )

    assert tuple(record.state_key for record in restored.records) == ("z-last", "a-first")


def test_reader_uses_persisted_query_width_and_fails_closed_without_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aria_nbv.rollouts.candidate_benchmark as benchmark_module

    record = _record(state="reader", valid=(5, 5, 4))
    monkeypatch.setattr(benchmark_module, "_preflight_facts_from_reader", lambda *_args, **_kwargs: (record,))

    class Reader:
        def __init__(self, policy: object) -> None:
            self.policy = policy

        def manifest(self) -> dict[str, object]:
            return {"manifest": {"generation": {"candidate_family_preflight": self.policy}}}

    policy = replace(_config(60), flat_gain_tolerance=0.125)
    persisted = candidate_family_preflight_from_reader(Reader(policy.to_payload()))
    missing = candidate_family_preflight_from_reader(Reader(None))

    assert persisted.query_width == 60
    assert persisted.resolved_min_valid == 15
    assert persisted.config.to_payload() == policy.to_payload()
    assert persisted.flat_gain.tolerance == 0.125
    assert CandidateSupportFailure.LOW_ROOT_SUPPORT in {blocker.code for blocker in persisted.blockers}
    assert CandidateSupportFailure.MISSING_PRODUCTION_PROVENANCE in {blocker.code for blocker in missing.blockers}


def test_unconfigured_family_cannot_inflate_root_support() -> None:
    configured = _record(state="unknown", valid=(1, 1, 1), selected=(1, 1, 1))
    record = replace(
        configured,
        families=(*configured.families, CandidateFamilyCounts("forged", True, 100, 100, 100, 100)),
    )
    result = reduce_candidate_family_preflight((record,), _config(60))
    codes = {blocker.code for blocker in result.blockers}

    assert CandidateSupportFailure.UNCONFIGURED_FAMILY in codes
    assert CandidateSupportFailure.LOW_ROOT_SUPPORT in codes


def test_reader_preflight_does_not_materialize_geometry(monkeypatch: pytest.MonkeyPatch) -> None:
    from aria_nbv.rollouts import inspection

    policy = _config(1)

    class Reader:
        root = object()

        def manifest(self) -> dict[str, object]:
            return {"manifest": {"generation": {"candidate_family_preflight": policy.to_payload()}}}

    monkeypatch.setattr(
        inspection,
        "proposal_support_geometry",
        lambda *_args, **_kwargs: pytest.fail("complete preflight must not materialize geometry"),
    )

    def stream_rows(*_args: object, **kwargs: object) -> list[dict[str, object]]:
        row = {
            "scene": "scene",
            "rollout_row_id": 1,
            "step_row_id": 2,
            "mixture": "forward_local",
            "candidate_row_id": 0,
            "position": "forward_local",
            "actor_action": True,
            "compact_valid_index": 0,
            "selected": True,
        }
        callback = kwargs.get("row_callback")
        assert callable(callback)
        callback(row)
        return []

    monkeypatch.setattr(inspection, "candidate_audit_rows", stream_rows)

    result = candidate_family_preflight_from_reader(Reader())

    assert result.cells


def test_reader_preflight_preserves_paired_gaze_family_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    from aria_nbv.rollouts import inspection

    base = "target_bearing_local"
    paired = f"{base}__paired_forward_rig"
    policy = CandidateFamilyPreflightConfig(
        query_width=24,
        configured_families=(base, paired),
        target_aware_families=(base, paired),
        forward_family="forward_local",
    )

    class Reader:
        def manifest(self) -> dict[str, object]:
            return {
                "manifest": {
                    "generation": {
                        "candidate_family_preflight": policy.to_payload(),
                        "writer_config": {
                            "candidate_mixture": {"components": [{"name": base, "paired_view_mode": "forward_rig"}]}
                        },
                    }
                }
            }

    reader: Any = Reader()
    decoded = candidate_mixture_family_names(
        reader,
        np.asarray([0, 0], dtype=np.int32),
        np.asarray([0, 1], dtype=np.int8),
    )
    assert decoded.tolist() == [base, paired]

    def audit(_reader: object, **kwargs: object) -> list[dict[str, object]]:
        callback = kwargs.get("row_callback")
        assert callable(callback)
        for candidate_id in range(24):
            family = str(decoded[candidate_id % 2])
            callback(
                {
                    "scene": "scene",
                    "rollout_row_id": 1,
                    "step_row_id": 2,
                    "mixture": family,
                    "candidate_row_id": candidate_id,
                    "position": base,
                    "actor_action": True,
                    "compact_valid_index": candidate_id,
                    "selected": False,
                }
            )
        return []

    monkeypatch.setattr(inspection, "candidate_audit_rows", audit)
    result = candidate_family_preflight_from_reader(reader)

    assert [(cell.family, cell.attempted) for _, _, cell in result.cells] == [(base, 12), (paired, 12)]
    assert not any(
        blocker.code
        in {
            CandidateSupportFailure.UNKNOWN_FAMILY_APPLICABILITY,
            CandidateSupportFailure.FAMILY_COLLAPSE,
            CandidateSupportFailure.UNCONFIGURED_FAMILY,
        }
        for blocker in result.blockers
    )
    with pytest.raises(ValueError, match="missing canonical gaze-variant"):
        candidate_mixture_family_names(
            reader,
            np.asarray([0], dtype=np.int32),
            np.asarray([-1], dtype=np.int8),
        )


def test_lightweight_reader_is_constant_row_memory_and_matches_materialized_reduction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aria_nbv.rollouts import inspection

    policy = _config(60)

    class Reader:
        def manifest(self) -> dict[str, object]:
            return {
                "manifest": {
                    "generation": {
                        "candidate_family_preflight": policy.to_payload(),
                        "writer_config": {
                            "candidate_mixture": {"components": [{"name": family} for family in FAMILIES]}
                        },
                    }
                }
            }

    class TrackedRow(dict[str, object]):
        live = 0
        peak = 0

        def __init__(self, candidate_id: int) -> None:
            family = "unconfigured_family" if candidate_id == 59 else FAMILIES[candidate_id % len(FAMILIES)]
            actor_valid = candidate_id % 7 != 0
            super().__init__(
                scene="scene",
                rollout_row_id=1,
                step_row_id=2,
                mixture=family,
                candidate_row_id=candidate_id,
                position=family,
                actor_action=actor_valid,
                compact_valid_index=candidate_id if actor_valid and candidate_id % 5 else -1,
                selected=False,
                invalid_reason=None if actor_valid else ("collision" if candidate_id % 2 else "clearance"),
                invalid_reason_bitset=0 if actor_valid else candidate_id % 4,
                free_space_margin_m=0.01 * candidate_id,
                mesh_distance_m=0.02 * candidate_id,
                path_min_clearance_m=0.03 * candidate_id,
                target_pixel_margin_px=0.04 * candidate_id,
                refill_rounds=candidate_id % 2,
                fallback_used=bool(candidate_id % 2),
                support_failure="exhausted" if candidate_id == 59 else None,
                oracle_label=True,
                target_root_gain=float(candidate_id % 5),
                root_relative_x_m=0.0,
                root_relative_y_m=0.0,
                root_relative_z_m=0.0,
            )
            type(self).live += 1
            type(self).peak = max(type(self).peak, type(self).live)

        def __del__(self) -> None:
            type(self).live -= 1

    def audit(_reader: object, **kwargs: object) -> list[dict[str, object]]:
        callback = kwargs.get("row_callback")
        count = 20_000 if callable(callback) else 60
        if callable(callback):
            for candidate_id in range(count):
                callback(TrackedRow(candidate_id))
            return []
        rows: list[dict[str, object]] = [TrackedRow(candidate_id) for candidate_id in range(count)]
        return rows

    monkeypatch.setattr(inspection, "candidate_audit_rows", audit)
    streamed = candidate_family_preflight_from_reader(Reader())
    gc.collect()

    assert TrackedRow.live == 0
    assert TrackedRow.peak < 10
    assert sum(cell.attempted for _, _, cell in streamed.cells) == 19_999
    assert streamed.flat_gain.denominator == 20_000
    assert CandidateSupportFailure.UNCONFIGURED_FAMILY in {blocker.code for blocker in streamed.blockers}

    # Repeat with an identical bounded population through the materialized path.
    def bounded_audit(_reader: object, **kwargs: object) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = [TrackedRow(candidate_id) for candidate_id in range(60)]
        callback = kwargs.get("row_callback")
        if callable(callback):
            for row in rows:
                callback(row)
            return []
        return rows

    monkeypatch.setattr(inspection, "candidate_audit_rows", bounded_audit)
    streamed_bounded = candidate_family_preflight_from_reader(Reader())
    without_geometry = benchmarks_from_reader(Reader(), candidate_limit=None, include_geometry=False)
    with_geometry = benchmarks_from_reader(Reader(), candidate_limit=None, include_geometry=True)
    without_geometry_result = reduce_candidate_family_preflight(without_geometry, policy)
    with_geometry_result = reduce_candidate_family_preflight(with_geometry, policy)

    assert without_geometry[0].to_record()["oracle_target_root_gains"]
    assert without_geometry[0].families == with_geometry[0].families
    assert streamed_bounded.to_payload() == without_geometry_result.to_payload()
    assert streamed_bounded.to_payload() == with_geometry_result.to_payload()
