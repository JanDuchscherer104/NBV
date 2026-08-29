"""Executable acceptance tests for the candidate-benchmark evidence seam."""

from __future__ import annotations

import json
import runpy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from aria_nbv.app.panels._stored_rollouts import candidate_generation, validity_support
from aria_nbv.rollouts.candidate_benchmark import (
    BINDING_KEYS,
    SCHEMA_ID,
    CandidateBenchmark,
    CandidateFamilyCounts,
    CandidatePoint,
    benchmarks_from_reader,
    candidate_support_metrics,
    circular_minimum_covering_span_deg,
    read_bundle,
    read_bundle_bytes,
    reduce_candidate_records,
    serialize_bundle_bytes,
    sha256_bytes,
    target_relative_orbit_span_deg,
    target_side_count_balance,
    write_bundle,
)
from aria_nbv.rollouts.candidate_support_plotting import candidate_support_figures
from aria_nbv.rollouts.reporting import candidate_benchmark_report_frames


def _support_point(candidate_id: int, xyz: tuple[float, float, float], **kwargs: Any) -> CandidatePoint:
    kwargs.setdefault("target_relative_xyz", xyz)
    return CandidatePoint(candidate_id, xyz, "target_orbit", "target_orbit", True, False, "state", **kwargs)


def test_circular_orbit_span_handles_branch_cut() -> None:
    assert circular_minimum_covering_span_deg((-179.0, 179.0)) == pytest.approx(2.0)


def test_target_side_and_orbit_metrics_are_translation_invariant() -> None:
    points = (
        _support_point(1, (1.0, 1.0, 0.0)),
        _support_point(2, (0.0, -1.0, 0.0)),
    )
    translated = (
        _support_point(1, (11.0, 6.0, 0.0), target_relative_xyz=(1.0, 1.0, 0.0)),
        _support_point(2, (10.0, 4.0, 0.0), target_relative_xyz=(0.0, -1.0, 0.0)),
    )
    assert target_side_count_balance(points) == pytest.approx(1.0)
    assert target_side_count_balance(translated) == pytest.approx(1.0)
    assert target_relative_orbit_span_deg(points) == pytest.approx(target_relative_orbit_span_deg(translated))


def test_candidate_support_metrics_preserves_unavailable_and_separates_cap_compliance() -> None:
    points = (
        _support_point(
            1,
            (1.0, 1.0, 0.0),
            view_jitter_yaw_deg=4.0,
            view_jitter_pitch_deg=2.0,
            view_jitter_is_bounded=True,
            view_jitter_azimuth_limit_deg=5.0,
            view_jitter_elevation_limit_deg=5.0,
        ),
        _support_point(
            2,
            (1.0, -1.0, 0.0),
            view_jitter_yaw_deg=40.0,
            view_jitter_pitch_deg=10.0,
            view_jitter_is_bounded=False,
            view_jitter_azimuth_limit_deg=0.0,
            view_jitter_elevation_limit_deg=0.0,
        ),
    )
    metrics = candidate_support_metrics(points, configured_families=("target_orbit",))
    assert metrics["actor_valid_fraction"] == pytest.approx(1.0)
    assert metrics["per_state_valid_support"] == 2
    assert metrics["zero_valid_family_state_rate"] == pytest.approx(0.0)
    assert metrics["target_side_positive_count"] == 1
    assert metrics["target_side_negative_count"] == 1
    assert metrics["target_side_neutral_count"] == 0
    assert metrics["target_side_balance_undefined"] == 0
    assert metrics["nonzero_jitter_fraction"] == pytest.approx(1.0)
    assert metrics["bounded_jitter_declaration_fraction"] == pytest.approx(0.5)
    assert metrics["bounded_jitter_cap_compliance_fraction"] == pytest.approx(1.0)
    assert metrics["uncapped_spherical_count"] == 1
    neutral = candidate_support_metrics((_support_point(3, (1.0, 0.0, 0.0)),))
    assert neutral["target_side_neutral_count"] == 1
    assert neutral["target_side_balance_undefined"] == 1
    assert neutral["target_side_count_balance"] is None
    assert candidate_support_metrics((), configured_families=None)["zero_valid_family_state_rate"] is None
    assert target_side_count_balance((_record().points[0],)) is None
    assert target_relative_orbit_span_deg((_record().points[0],)) is None


def _binding() -> dict[str, str]:
    return {
        key: (
            SCHEMA_ID
            if key == "schema_id"
            else "candidate_benchmark"
            if key == "evidence_class"
            else "complete"
            if key == "completion"
            else "1"
            if key == "implementation_revision"
            else sha256_bytes(key.encode())
        )
        for key in BINDING_KEYS
    }


def _record() -> CandidateBenchmark:
    points = (
        CandidatePoint(
            3,
            (0.1, 0.2, 0.3),
            "forward",
            "forward_local",
            True,
            False,
            "state-1",
            "cfg-a",
            "roll-a",
            "branch-a",
            view_direction_xyz=(1.0, 0.0, 0.0),
        ),
        CandidatePoint(
            4,
            (-0.2, 0.3, 0.4),
            "target",
            "target_bearing_local",
            True,
            True,
            "state-1",
            "cfg-b",
            "roll-a",
            "branch-b",
            view_direction_xyz=(0.0, -1.0, 0.0),
        ),
    )
    return CandidateBenchmark(
        "state-1",
        "scene-a",
        (CandidateFamilyCounts("forward", True, 2, 2, 1, 2), CandidateFamilyCounts("target", True, 1, 1, 1, 1)),
        timings_ms={"total_ms": 2.0},
        resources={"gpu_memory_mb": 4.0},
        candidate_ids=(3, 4),
        coordinates=((0.1, 0.2, 0.3), (-0.2, 0.3, 0.4)),
        lineage={"3": "cfg-a"},
        points=points,
    )


def test_candidate_support_jitter_plot_keeps_zero_cap_residuals_without_envelope() -> None:
    point = CandidatePoint(
        9,
        (0.1, 0.2, 0.3),
        "uniform",
        "uniform_sphere",
        True,
        False,
        "state",
        view_jitter_yaw_deg=95.0,
        view_jitter_pitch_deg=-45.0,
        view_jitter_is_bounded=False,
        view_jitter_azimuth_limit_deg=0.0,
        view_jitter_elevation_limit_deg=0.0,
    )
    record = CandidateBenchmark(
        "state",
        "scene",
        (CandidateFamilyCounts("uniform", True, 1, 1, 0, 1),),
        candidate_ids=(9,),
        coordinates=(point.xyz,),
        points=(point,),
    )
    jitter = candidate_support_figures((record,))[3]
    assert not jitter.layout.shapes
    assert list(jitter.layout.xaxis.range) == [-180.0, 180.0]
    assert list(jitter.layout.yaxis.range) == [-90.0, 90.0]
    assert 95.0 in tuple(jitter.data[0].x)
    assert [annotation.text for annotation in jitter.layout.annotations] == ["uncapped spherical support"]


def test_candidate_support_jitter_plot_retains_configured_bounded_envelope() -> None:
    point = CandidatePoint(
        10,
        (0.1, 0.2, 0.3),
        "target",
        "target_bearing_local",
        True,
        False,
        "state",
        view_jitter_yaw_deg=12.0,
        view_jitter_pitch_deg=-8.0,
        view_jitter_is_bounded=True,
        view_jitter_azimuth_limit_deg=60.0,
        view_jitter_elevation_limit_deg=30.0,
    )
    record = CandidateBenchmark(
        "state",
        "scene",
        (CandidateFamilyCounts("target", True, 1, 1, 0, 1),),
        candidate_ids=(10,),
        coordinates=(point.xyz,),
        points=(point,),
    )

    jitter = candidate_support_figures((record,))[3]

    assert len(jitter.layout.shapes) == 1
    envelope = jitter.layout.shapes[0]
    assert (envelope.x0, envelope.x1, envelope.y0, envelope.y1) == (-60.0, 60.0, -30.0, 30.0)
    assert envelope.line.dash == "dot"


def test_serialized_bundle_is_byte_stable_and_round_trips_with_binding() -> None:
    records = (_record(),)
    first = serialize_bundle_bytes(records, provenance=_binding())
    second = serialize_bundle_bytes(records, provenance=_binding())
    assert first == second
    loaded = read_bundle_bytes(first, expected_binding=_binding())
    actual, expected = loaded.records[0], records[0]
    assert (actual.scene_key, actual.state_key, actual.candidate_ids, actual.coordinates) == (
        expected.scene_key,
        expected.state_key,
        expected.candidate_ids,
        expected.coordinates,
    )
    assert [(point.candidate_id, tuple(point.xyz), point.family, point.selected) for point in actual.points] == [
        (point.candidate_id, tuple(point.xyz), point.family, point.selected) for point in expected.points
    ]
    assert actual.families == expected.families


@pytest.mark.parametrize("mutation", ["stale", "missing", "nonhex", "allzero"])
def test_reader_rejects_invalid_binding_provenance(tmp_path: Path, mutation: str) -> None:
    path = write_bundle(tmp_path / "bundle", (_record(),), provenance=_binding())
    manifest_path = path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if mutation == "stale":
        manifest["provenance"]["config_sha256"] = sha256_bytes(b"other")
    elif mutation == "missing":
        del manifest["provenance"]["config_sha256"]
    elif mutation == "nonhex":
        manifest["provenance"]["config_sha256"] = "x" * 64
    else:
        manifest["provenance"]["config_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        read_bundle(path, expected_binding=_binding())


def test_bundle_is_immutable_and_rejects_overwrite_or_unexpected_files(tmp_path: Path) -> None:
    path = write_bundle(tmp_path / "bundle", (_record(),), provenance=_binding())
    with pytest.raises(FileExistsError):
        write_bundle(path, (_record(),), provenance=_binding())
    with pytest.raises(TypeError):
        path_manifest = read_bundle(path, expected_binding=_binding()).manifest
        path_manifest["provenance"]["config_sha256"] = "x"
    (path / "extra.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected files"):
        read_bundle(path, expected_binding=_binding())


@pytest.mark.parametrize(
    "changes",
    [
        {"families": [{"family": "f", "applicable": "yes"}]},
        {"families": [{"family": "f", "applicable": True, "attempted": 2, "valid": 3}]},
        {"families": [{"family": "f", "applicable": True, "denominator": -1}]},
        {"geometry": []},
        {"candidate_ids": [1], "coordinates": []},
        {"coordinates": [[float("nan"), 0.0, 0.0]]},
        {"candidate_ids": [1], "coordinates": [[0.0, 0.0, 0.0]], "points": []},
    ],
)
def test_reducer_rejects_malformed_contract_fields(changes: dict[str, Any]) -> None:
    record: dict[str, Any] = {"scene_key": "scene-a", "state_key": "state-1", "families": [], "geometry": {}}
    record.update(changes)
    with pytest.raises((TypeError, ValueError)):
        reduce_candidate_records([record])


def test_reporting_frames_are_canonical_reader_projection(tmp_path: Path) -> None:
    path = write_bundle(tmp_path / "bundle", (_record(),), provenance=_binding())
    frames = candidate_benchmark_report_frames(path, expected_binding=_binding())
    actual = frames["records"].iloc[0].to_dict()
    expected = _record().to_record()
    for key in (
        "scene_key",
        "state_key",
        "families",
        "geometry",
        "diversity",
        "timings_ms",
        "resources",
        "provenance",
        "lineage",
    ):
        assert actual[key] == expected[key]
    assert actual["candidate_ids"] == expected["candidate_ids"]
    assert actual["coordinates"] == expected["coordinates"]
    assert set(frames["families"]["family"]) == {"forward", "target"}
    assert set(frames["points"]["candidate_id"]) == {3, 4}
    with pytest.raises(ValueError):
        candidate_benchmark_report_frames(path, expected_binding={})


def test_public_benchmark_figures_expose_six_named_groups_and_support_metadata() -> None:
    figures = candidate_generation._candidate_benchmark_figures((_record(),))
    assert [figure.layout.title.text for figure in figures] == [
        "Candidate family attempted → valid → selected funnel",
        "Candidate family survival",
        "Candidate support (target-normalized ground plane)",
        "Candidate support (target-normalized 3D)",
        "Candidate view jitter (bounded boxes and uncapped spherical support)",
        "Candidate benchmark resource and timing summary",
    ]
    assert all(trace.name for figure in figures for trace in figure.data)
    assert {str(trace.name).split(", ")[0] for trace in figures[2].data} == {
        "Factual expansion/root",
        "forward",
        "target",
    }
    assert {str(value) for value in figures[1].data[0].x} == {"forward", "target"}
    trace = figures[3].data[0]
    assert len(trace.x) == len(trace.y) == len(trace.z) == 2
    assert list(trace.customdata[:, 0]) == [3, 4]
    assert list(trace.customdata[:, 3]) == ["cfg-a", "cfg-b"]
    assert "candidate=%" in trace.hovertemplate and "lineage=%" in trace.hovertemplate
    assert list(figures[0].data[0].y) == [3, 3, 2]


def test_public_benchmark_ground_plot_option_adds_valid_camera_forward_arrows() -> None:
    figures = candidate_generation._candidate_benchmark_figures((_record(),), show_view_directions=True)

    assert len(figures[2].layout.annotations) == 2
    assert all(annotation.showarrow for annotation in figures[2].layout.annotations)
    first_arrow = figures[2].layout.annotations[0]
    assert (first_arrow.ax, first_arrow.ay) == pytest.approx((0.1, 0.2))
    assert (first_arrow.x, first_arrow.y) == pytest.approx((0.14, 0.2))


def test_benchmark_figure_bulk_projection_preserves_point_status_and_funnel_totals() -> None:
    additional = CandidateBenchmark(
        "state-2",
        "scene-a",
        (CandidateFamilyCounts("lateral", True, 5, 4, 0, 5),),
        candidate_ids=(5,),
        coordinates=((0.5, -0.4, 0.2),),
        points=(
            CandidatePoint(
                5,
                (0.5, -0.4, 0.2),
                "lateral",
                "lateral_target_bypass",
                False,
                False,
                "state-2",
                None,
                "roll-a",
                "branch-c",
            ),
        ),
    )

    figures = candidate_generation._candidate_benchmark_figures((_record(), additional))

    support = figures[3].data[0]
    assert list(support.x) == [0.1, -0.2, 0.5]
    assert list(support.customdata[:, 2]) == ["valid", "selected", "invalid"]
    assert list(support.customdata[:, 3]) == ["cfg-a", "cfg-b", "unavailable"]
    assert list(figures[0].data[0].y) == [8, 7, 2]


def test_benchmark_reader_filters_state_before_applying_candidate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    def row(candidate_id: int, rollout_id: int, step_id: int) -> dict[str, Any]:
        return {
            "scene": "scene-a",
            "rollout_row_id": rollout_id,
            "step_row_id": step_id,
            "mixture": "forward_component",
            "position": "forward_local",
            "candidate_row_id": candidate_id,
            "actor_action": True,
            "selected": False,
            "root_to_target_x_m": 1.0,
            "root_to_target_y_m": 0.0,
            "root_to_target_z_m": 0.0,
            "root_relative_x_m": float(candidate_id),
            "root_relative_y_m": 0.0,
            "root_relative_z_m": 0.0,
            "candidate_config": "cfg",
            "rollout_config": "roll",
            "branch_schedule": "branch",
        }

    rows = [row(1, 1, 1), row(2, 1, 1), row(3, 2, 2)]

    def audit(_reader: Any, **kwargs: Any) -> list[dict[str, Any]]:
        if "rollout_row_id" in kwargs:
            rows_for_state = [
                item
                for item in rows
                if item["rollout_row_id"] == kwargs["rollout_row_id"] and item["step_row_id"] == kwargs["step_row_id"]
            ]
        else:
            rows_for_state = rows
        return rows_for_state[: int(kwargs["limit"])]

    monkeypatch.setattr("aria_nbv.rollouts.inspection.candidate_audit_rows", audit)
    result = benchmarks_from_reader(object(), state_key="rollout:2/step:2", candidate_limit=1)
    assert len(result) == 1
    assert result[0].state_key == "rollout:2/step:2"
    assert result[0].candidate_ids == (3,)


def test_benchmark_reader_joins_canonical_projection_and_bounds_state_request(monkeypatch: pytest.MonkeyPatch) -> None:
    from aria_nbv.rollouts import inspection

    calls: list[dict[str, Any]] = []
    frame = SimpleNamespace(frame_id="frame", step_row_id=7, target_x=2.0, target_y=3.0, target_z=4.0)
    projected = SimpleNamespace(
        candidate_row_id=11,
        frame_id="frame",
        x=0.25,
        y=-0.5,
        z=0.75,
    )

    def projection(_reader: Any, **kwargs: Any) -> Any:
        calls.append(kwargs)
        return SimpleNamespace(points=(projected,), frames=(frame,))

    monkeypatch.setattr(inspection, "proposal_support_geometry", projection)
    monkeypatch.setattr(
        inspection,
        "candidate_audit_rows",
        lambda _reader, **kwargs: [
            {
                "scene": "scene",
                "rollout_row_id": 4,
                "step_row_id": 7,
                "mixture": "target_component",
                "position": "target_bearing_local",
                "candidate_row_id": 11,
                "actor_action": True,
                "selected": False,
                "candidate_config": "cfg",
                "rollout_config": "roll",
                "branch_schedule": "branch",
            }
        ],
    )
    result = benchmarks_from_reader(SimpleNamespace(root={}), state_key="rollout:4/step:7", candidate_limit=12)
    assert calls == [{"rollout_row_ids": (4,), "step_row_ids": (7,), "max_candidates": None}]
    point = result[0].points[0]
    assert point.xyz == (0.25, -0.5, 0.75)
    assert point.target_relative_xyz == (-1.75, -3.5, -3.25)


def test_benchmark_reader_retains_counts_when_state_projection_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aria_nbv.rollouts import inspection

    issue = SimpleNamespace(code="missing_target", rollout_row_id=4, step_row_id=None)
    monkeypatch.setattr(
        inspection,
        "proposal_support_geometry",
        lambda *_args, **_kwargs: SimpleNamespace(points=(), frames=(), issues=(issue,)),
    )
    monkeypatch.setattr(
        inspection,
        "candidate_audit_rows",
        lambda *_args, **_kwargs: [
            {
                "scene": "scene",
                "rollout_row_id": 4,
                "step_row_id": 7,
                "mixture": "target_component",
                "position": "target_bearing_local",
                "candidate_row_id": 11,
                "actor_action": True,
                "selected": False,
            }
        ],
    )

    result = benchmarks_from_reader(SimpleNamespace(root={}), state_key="rollout:4/step:7", candidate_limit=1)

    assert len(result) == 1
    assert result[0].families[0].attempted == 1
    assert result[0].families[0].valid == 1
    assert result[0].points == ()
    assert result[0].families[0].family == "target_component"
    assert result[0].lineage["family_identity"] == "mixture_component"
    assert result[0].lineage["proposal_support_unavailable_reason"] == "missing_target"
    figures = candidate_support_figures(result)
    for figure in figures[:2]:
        assert "proposal support unavailable: missing_target" in {
            annotation.text for annotation in figure.layout.annotations
        }
    panel_figures = candidate_generation._candidate_benchmark_figures(result)
    assert list(panel_figures[0].data[0].y) == [1, 1, 0]
    assert set(panel_figures[1].data[0].x) == {"target_component"}
    for figure in panel_figures[2:4]:
        assert "proposal support unavailable: missing_target" in {
            annotation.text for annotation in figure.layout.annotations
        }


def test_benchmark_reader_applies_small_state_limit_after_complete_shell_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aria_nbv.rollouts import inspection

    projected = tuple(
        SimpleNamespace(candidate_row_id=candidate_id, frame_id="frame", x=float(candidate_id), y=0.0, z=0.0)
        for candidate_id in (11, 12)
    )
    frame = SimpleNamespace(frame_id="frame", target_x=1.0, target_y=0.0, target_z=0.0)
    projection_calls: list[dict[str, Any]] = []

    def projection(_reader: Any, **kwargs: Any) -> Any:
        projection_calls.append(kwargs)
        return SimpleNamespace(points=projected, frames=(frame,), issues=())

    rows = [
        {
            "scene": "scene",
            "rollout_row_id": 4,
            "step_row_id": 7,
            "mixture": f"target_component_{candidate_id}",
            "position": "target_bearing_local",
            "candidate_row_id": candidate_id,
            "actor_action": True,
            "selected": False,
        }
        for candidate_id in (11, 12)
    ]
    monkeypatch.setattr(inspection, "proposal_support_geometry", projection)
    monkeypatch.setattr(
        inspection,
        "candidate_audit_rows",
        lambda *_args, **kwargs: rows[: int(kwargs["limit"])],
    )

    result = benchmarks_from_reader(SimpleNamespace(root={}), state_key="rollout:4/step:7", candidate_limit=1)

    assert projection_calls == [{"rollout_row_ids": (4,), "step_row_ids": (7,), "max_candidates": None}]
    assert result[0].candidate_ids == (11,)
    assert result[0].points[0].family == "target_component_11"
    assert result[0].points[0].position == "target_bearing_local"


def test_benchmark_reader_keeps_distinct_components_that_share_one_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aria_nbv.rollouts import inspection

    projected = tuple(
        SimpleNamespace(candidate_row_id=candidate_id, frame_id="frame", x=float(candidate_id), y=0.0, z=0.0)
        for candidate_id in (11, 12)
    )
    frame = SimpleNamespace(frame_id="frame", target_x=1.0, target_y=0.0, target_z=0.0)
    monkeypatch.setattr(
        inspection,
        "proposal_support_geometry",
        lambda *_args, **_kwargs: SimpleNamespace(points=projected, frames=(frame,), issues=()),
    )
    monkeypatch.setattr(
        inspection,
        "candidate_audit_rows",
        lambda *_args, **_kwargs: [
            {
                "scene": "scene",
                "rollout_row_id": 4,
                "step_row_id": 7,
                "mixture": family,
                "position": "target_bearing_local",
                "candidate_row_id": candidate_id,
                "actor_action": True,
                "selected": False,
            }
            for candidate_id, family in ((11, "radial_towards_target_bearing"), (12, "target_point_anchor"))
        ],
    )

    result = benchmarks_from_reader(SimpleNamespace(root={}), state_key="rollout:4/step:7", candidate_limit=2)

    assert [family.family for family in result[0].families] == [
        "radial_towards_target_bearing",
        "target_point_anchor",
    ]
    assert [point.family for point in result[0].points] == [
        "radial_towards_target_bearing",
        "target_point_anchor",
    ]
    assert {point.position for point in result[0].points} == {"target_bearing_local"}


def test_benchmark_reader_does_not_hide_real_projection_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    from aria_nbv.rollouts import inspection

    monkeypatch.setattr(
        inspection,
        "proposal_support_geometry",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("invalid target-aligned geometry")),
    )
    monkeypatch.setattr(
        inspection,
        "candidate_audit_rows",
        lambda *_args, **_kwargs: pytest.fail("audit fallback must not run"),
    )
    with pytest.raises(ValueError, match="invalid target-aligned geometry"):
        benchmarks_from_reader(SimpleNamespace(root={}), candidate_limit=12)


def test_benchmark_reader_uses_native_state_filters_and_bounded_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def audit(_reader: Any, **kwargs: Any) -> list[dict[str, Any]]:
        calls.append(kwargs)
        return []

    monkeypatch.setattr("aria_nbv.rollouts.inspection.candidate_audit_rows", audit)
    assert benchmarks_from_reader(object(), state_key="rollout:7/step:3", candidate_limit=11) == ()
    assert calls == [{"rollout_row_id": 7, "step_row_id": 3, "limit": 11}]
    calls.clear()
    assert benchmarks_from_reader(object(), candidate_limit=11) == ()
    assert calls == [{"limit": 11}]
    calls.clear()
    assert benchmarks_from_reader(object(), state_key="not-a-state", candidate_limit=11) == ()
    assert calls == []


def test_empty_benchmark_figures_show_no_matching_or_resource_annotations() -> None:
    figures = candidate_generation._candidate_benchmark_figures(())
    assert len(figures) == 6
    assert [figure.layout.title.text for figure in figures] == [
        "Candidate family attempted → valid → selected funnel",
        "Candidate family survival",
        "Candidate support (target-normalized ground plane)",
        "Candidate support (target-normalized 3D)",
        "Candidate view jitter (bounded boxes and uncapped spherical support)",
        "Candidate benchmark resource and timing summary",
    ]
    for figure in figures[:5]:
        assert "No matching benchmark candidates" in {annotation.text for annotation in figure.layout.annotations}
    assert "unavailable: no persisted timing/resource facts" in {
        annotation.text for annotation in figures[5].layout.annotations
    }


def test_benchmark_panel_dispatches_only_after_toggle_and_propagates_state_and_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, Any]] = []
    fake_records = (_record(),)
    benchmark_dispatch = iter((False, True))

    class Expander:
        def __enter__(self) -> "Expander":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

    fake_st = SimpleNamespace(
        subheader=lambda *_a, **_k: None,
        number_input=lambda label, **kwargs: 17 if label == "Candidate plot row limit" else 123,
        toggle=lambda label, **kwargs: (
            next(benchmark_dispatch) if label == "Build immutable candidate benchmark card" else False
        ),
        text_input=lambda *_a, **_k: "state-1",
        download_button=lambda *args, **_kwargs: calls.append(("download", args)),
        markdown=lambda *_a, **_k: None,
        caption=lambda *_a, **_k: None,
        warning=lambda *_a, **_k: None,
        dataframe=lambda *_a, **_k: None,
        expander=lambda *_a, **_k: Expander(),
    )
    monkeypatch.setattr(validity_support, "st", fake_st)
    monkeypatch.setattr(validity_support, "_render_candidate_provenance_flow", lambda *_a: None)
    monkeypatch.setattr(validity_support, "_render_plot", lambda figure, *_a: calls.append(("plot", figure)))
    monkeypatch.setattr(
        validity_support,
        "_candidate_benchmark_figures",
        lambda records, **kwargs: candidate_generation._candidate_benchmark_figures(records, **kwargs),
    )
    monkeypatch.setattr(validity_support, "_render_bounded_candidate_geometry", lambda *_a, **_k: None)

    class Session:
        def targets(self) -> list[Any]:
            return []

        def masks(self) -> list[Any]:
            return []

        def candidate_benchmark_records(self, **kwargs: Any) -> tuple[CandidateBenchmark, ...]:
            calls.append(("records", kwargs))
            return fake_records

        def candidate_benchmark_export(self, **kwargs: Any) -> bytes:
            calls.append(("export", kwargs))
            return serialize_bundle_bytes(fake_records, provenance=_binding())

    validity_support._render_targets_and_support(Session())
    assert not any(kind in {"records", "export"} for kind, _ in calls)
    validity_support._render_targets_and_support(Session())
    assert ("records", {"state_key": "state-1", "candidate_limit": 123}) in calls
    assert ("export", {"state_key": "state-1"}) in calls
    assert sum(kind == "plot" for kind, _ in calls) == 6
    assert sum(kind == "download" for kind, _ in calls) == 1


def test_production_seminar_jitter_and_committed_smoke_evidence_are_nonzero_and_named() -> None:
    import tomllib

    repo_root = Path(__file__).resolve().parents[3]
    config = tomllib.loads((repo_root / ".configs/build_rollouts_v1_realistic.toml").read_text())
    mixture = config["candidate_mixture"]["base"]
    assert (mixture["view_max_azimuth_deg"], mixture["view_max_elevation_deg"], mixture["view_roll_jitter_deg"]) == (
        60.0,
        30.0,
        0.0,
    )
    manifest = json.loads(
        (repo_root / "docs/contents/evidence/candidate_benchmark_wp01_smoke/manifest.json").read_text()
    )
    assert all(
        len(manifest["provenance"][key]) == 64 and set(manifest["provenance"][key]) != {"0"}
        for key in BINDING_KEYS
        if key.endswith("sha256")
    )
    figures = json.loads(
        (repo_root / "docs/contents/evidence/candidate_benchmark_wp01_smoke_figures.json").read_text()
    )["figures"]
    assert len(figures) == 4 and all(item["title"] for item in figures)


def test_target_orbit_evidence_bundle_is_portable_and_hash_bound() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    evidence = repo_root / "docs/contents/evidence/candidate_target_orbit_mvp"
    manifest = json.loads((evidence / "manifest.json").read_text())
    summary = json.loads((evidence / "summary.json").read_text())
    bound_paths = (
        (manifest["generator"]["path"], manifest["generator"]["sha256"]),
        (manifest["reducer"]["path"], manifest["reducer"]["sha256"]),
        (manifest["portable_evidence_input"]["path"], manifest["portable_evidence_input"]["sha256"]),
        (manifest["portable_evidence_input"]["summary_path"], manifest["portable_evidence_input"]["summary_sha256"]),
        (manifest["plot"]["path"], manifest["plot"]["sha256"]),
        (manifest["plot"]["interactive_path"], manifest["plot"]["source_html_sha256"]),
    )
    for relative, expected in bound_paths:
        assert sha256_bytes((repo_root / relative).read_bytes()) == expected
    assert len((evidence / "candidate-rows.jsonl").read_text().splitlines()) == 240
    assert {**summary["realistic_core"], "profile": "realistic_core"} == manifest["baseline"]
    assert {**summary["target_orbit_mvp"], "profile": "target_orbit_mvp"} == manifest["candidate"]


def test_target_orbit_portable_reducer_retains_an_empty_expected_state() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    namespace = runpy.run_path(str(repo_root / "docs/contents/evidence/candidate_target_orbit_mvp/build_evidence.py"))
    summary = namespace["_profile_summary"](
        [],
        profile="realistic_core",
        expected_states=(("scene-empty", 0, 0),),
    )

    assert summary["actor_valid_fraction"] == pytest.approx(0.0)
    assert summary["family_state_pair_count"] == 3
    assert summary["family_zero_valid_state_count"] == 3
    assert summary["worst_state_valid_count"] == 0
    assert summary["oracle_opportunity_undefined_state_count"] == 1
    assert summary["oracle_opportunity_undefined_scene_count"] == 1


def test_target_orbit_portable_reducer_uses_canonical_support_metrics() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    namespace = runpy.run_path(str(repo_root / "docs/contents/evidence/candidate_target_orbit_mvp/build_evidence.py"))
    rows = namespace["_read_rows"]()
    state_rows = [row for row in rows if row["profile"] == "target_orbit_mvp" and row["scene"] == "889"]
    points = namespace["_candidate_points"](state_rows)
    canonical = candidate_support_metrics(
        points,
        configured_families=namespace["PROFILE_FAMILIES"]["target_orbit_mvp"],
        projected_target_centers=sum(row["target_center_in_calibrated_image"] is True for row in state_rows),
        total_target_centers=len(state_rows),
    )
    reduced = namespace["_state_metrics"](
        state_rows,
        namespace["PROFILE_FAMILIES"]["target_orbit_mvp"],
    )

    assert reduced["family_zero_rate"] == canonical["zero_valid_family_state_rate"]
    assert reduced["family_zero_count"] == canonical["zero_valid_family_count"]
    assert reduced["side_balance"] == canonical["target_side_count_balance"]
    assert reduced["orbit_span_deg"] == canonical["target_relative_orbit_span_deg"]
    assert reduced["projection_fraction"] == canonical["target_center_projection_fraction"]
    assert reduced["jitter_nonzero_fraction"] == canonical["nonzero_jitter_fraction"]


def test_target_orbit_shared_plot_gives_challenger_only_family_a_legend_entry() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    namespace = runpy.run_path(str(repo_root / "docs/contents/evidence/candidate_target_orbit_mvp/build_evidence.py"))
    figure = namespace["_candidate_plot"](namespace["_read_rows"](), show_view_directions=False)

    orbit_traces = [trace for trace in figure.data if str(trace.name).split(", ")[0] == "target_orbit"]
    assert orbit_traces
    assert any(trace.showlegend for trace in orbit_traces)
