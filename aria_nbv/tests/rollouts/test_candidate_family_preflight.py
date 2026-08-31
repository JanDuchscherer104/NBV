"""Exact tests for the applicability-adjusted candidate-family gate."""

from __future__ import annotations

import pickle
from dataclasses import replace
from pathlib import Path

import pytest
import torch
from efm3d.aria.camera import CameraTW
from efm3d.aria.pose import PoseTW

from aria_nbv.pose_generation.types import CandidateSamplingResult
from aria_nbv.rollouts.candidate_benchmark import (
    CandidateBenchmark,
    CandidateFamilyCounts,
    CandidateFamilyPhaseAEvidence,
    CandidateFamilyPhaseAExpectation,
    CandidateFamilyPreflightConfig,
    CandidateFamilySelection,
    CandidatePoint,
    CandidatePopulationCoverage,
    CandidateSupportFailure,
    benchmark_from_sampling_result,
    candidate_family_preflight_from_reader,
    read_candidate_family_phase_a,
    reduce_candidate_family_preflight,
    select_candidate_family_shell,
    write_candidate_family_phase_a,
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
    assert result.cells[2][1].support_failure == "target unavailable"


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


def test_preflight_funnel_supports_full_hundred_state_phase_a_population() -> None:
    result = reduce_candidate_family_preflight(
        tuple(_record(state=f"state-{index:03d}") for index in range(100)),
        _config(),
    )

    heatmap, funnel = candidate_family_preflight_figures(result)

    assert len(heatmap.data[0].y) == 100
    assert len(funnel.data) == 300


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


def test_margins_are_immutable_while_preflight_payload_is_pickleable() -> None:
    result = reduce_candidate_family_preflight((_record(state="immutable"),), _config())
    with pytest.raises(TypeError):
        result.cells[0][1].margins["free_space_margin_m"] = 2.0  # type: ignore[index]

    assert pickle.loads(pickle.dumps(result.to_payload())) == result.to_payload()


def test_family_selection_filters_the_existing_shell_without_recomputing() -> None:
    record = _record(state="select", gains=(0.0, 1.0, 2.0))

    selected = select_candidate_family_shell(
        (record,),
        CandidateFamilySelection("select", "target_bearing_local"),
    )

    assert len(selected) == 1
    assert [family.family for family in selected[0].families] == ["target_bearing_local"]
    assert {point.family for point in selected[0].points} == {"target_bearing_local"}


def test_phase_a_reader_validates_compact_content_source_policy_and_revision(tmp_path: Path) -> None:
    record = _record(state="phase-a", selected=(1, 2, 1))
    config = replace(_config(), expected_population_size=1)
    preflight = reduce_candidate_family_preflight(
        (record,),
        config,
        coverage=CandidatePopulationCoverage(1, 1, 1, 1, 1),
    )
    revision = {
        "contract_revision": "candidate-family-phase-a-v2",
        "clean_commit": "a" * 40,
        "head_tree": "b" * 40,
        "uv_lock_sha256": "c" * 64,
        "content_bundle_hash": "d" * 64,
        "revision_hash": "0123456789abcdef",
    }
    evidence = CandidateFamilyPhaseAEvidence(
        source_manifest_sha256="e" * 64,
        source_store_manifest_hash="f" * 16,
        source_cache_version="source-cache-v1",
        split_manifest_hash="split-v1",
        source_store_dir="source-store",
        writer_config_sha256="1" * 64,
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
        generation_revision_hash="0123456789abcdef",
    )
    path = write_candidate_family_phase_a(tmp_path / "phase-a.json", evidence)

    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
    assert read_candidate_family_phase_a(path, expected=expected).to_payload() == evidence.to_payload()

    tampered = path.read_text(encoding="utf-8").replace('"selected":2', '"selected":1', 1)
    path.write_text(tampered, encoding="utf-8")
    with pytest.raises(ValueError, match="content hash mismatch"):
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
        implementation_revision="a" * 40,
        generation_revision={
            "contract_revision": "candidate-family-phase-a-v2",
            "clean_commit": "a" * 40,
            "head_tree": "b" * 40,
            "uv_lock_sha256": "c" * 64,
            "content_bundle_hash": "d" * 64,
            "revision_hash": "0123456789abcdef",
        },
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
        generation_revision_hash="0123456789abcdef",
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
    monkeypatch.setattr(benchmark_module, "benchmarks_from_reader", lambda *_args, **_kwargs: (record,))

    class Reader:
        def __init__(self, policy: object) -> None:
            self.policy = policy

        def manifest(self) -> dict[str, object]:
            return {"manifest": {"generation": {"candidate_family_preflight": self.policy}}}

    persisted = candidate_family_preflight_from_reader(
        Reader(_config(60).to_payload()),
        require_known_applicability=True,
    )
    missing = candidate_family_preflight_from_reader(Reader(None), require_known_applicability=True)

    assert persisted.query_width == 60
    assert persisted.resolved_min_valid == 15
    assert CandidateSupportFailure.LOW_ROOT_SUPPORT in {blocker.code for blocker in persisted.blockers}
    assert CandidateSupportFailure.MISSING_PRODUCTION_PROVENANCE in {blocker.code for blocker in missing.blockers}
