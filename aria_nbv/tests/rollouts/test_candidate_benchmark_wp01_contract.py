"""Executable acceptance tests for the candidate-benchmark evidence seam."""

from __future__ import annotations

import json
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
    read_bundle,
    read_bundle_bytes,
    reduce_candidate_records,
    serialize_bundle_bytes,
    sha256_bytes,
    write_bundle,
)
from aria_nbv.rollouts.reporting import candidate_benchmark_report_frames


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
            3, (0.1, 0.2, 0.3), "forward", "forward_local", True, False, "state-1", "cfg-a", "roll-a", "branch-a"
        ),
        CandidatePoint(
            4, (-0.2, 0.3, 0.4), "target", "target_bearing_local", True, True, "state-1", "cfg-b", "roll-a", "branch-b"
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
        path_manifest["provenance"]["config_sha256"] = "x"  # type: ignore[index]
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


def test_public_benchmark_figures_expose_four_named_groups_and_support_metadata() -> None:
    figures = candidate_generation._candidate_benchmark_figures((_record(),))
    assert [figure.layout.title.text for figure in figures] == [
        "Candidate family attempted → valid → selected funnel",
        "Candidate support (target-normalized ground plane)",
        "Candidate support (target-normalized 3D)",
        "Candidate benchmark resource and timing summary",
    ]
    assert all(trace.name for figure in figures for trace in figure.data)
    assert {str(trace.name).split(", ")[0] for trace in figures[1].data} == {"forward", "target"}
    trace = figures[2].data[0]
    assert len(trace.x) == len(trace.y) == len(trace.z) == 2
    assert list(trace.customdata[:, 0]) == [3, 4]
    assert list(trace.customdata[:, 3]) == ["cfg-a", "cfg-b"]
    assert "candidate=%" in trace.hovertemplate and "lineage=%" in trace.hovertemplate
    assert list(figures[0].data[0].y) == [3, 3, 2]


def test_benchmark_reader_filters_state_before_applying_candidate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    def row(candidate_id: int, rollout_id: int, step_id: int) -> dict[str, Any]:
        return {
            "scene": "scene-a",
            "rollout_row_id": rollout_id,
            "step_row_id": step_id,
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
    assert len(figures) == 4
    assert [figure.layout.title.text for figure in figures] == [
        "Candidate family attempted → valid → selected funnel",
        "Candidate support (target-normalized ground plane)",
        "Candidate support (target-normalized 3D)",
        "Candidate benchmark resource and timing summary",
    ]
    for figure in figures[:3]:
        assert "No matching benchmark candidates" in {annotation.text for annotation in figure.layout.annotations}
    assert "unavailable: no persisted timing/resource facts" in {
        annotation.text for annotation in figures[3].layout.annotations
    }


def test_benchmark_panel_dispatches_only_after_toggle_and_propagates_state_and_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, Any]] = []
    fake_records = (_record(),)
    benchmark_dispatch = iter((False, True))

    class Expander:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

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
        lambda records: candidate_generation._candidate_benchmark_figures(records),
    )
    monkeypatch.setattr(validity_support, "_render_bounded_candidate_geometry", lambda *_a, **_k: None)

    class Session:
        def targets(self):
            return []

        def masks(self):
            return []

        def candidate_benchmark_records(self, **kwargs):
            calls.append(("records", kwargs))
            return fake_records

        def candidate_benchmark_export(self, **kwargs):
            calls.append(("export", kwargs))
            return serialize_bundle_bytes(fake_records, provenance=_binding())

    validity_support._render_targets_and_support(Session())
    assert not any(kind in {"records", "export"} for kind, _ in calls)
    validity_support._render_targets_and_support(Session())
    assert ("records", {"state_key": "state-1", "candidate_limit": 123}) in calls
    assert ("export", {"state_key": "state-1", "candidate_limit": 123}) in calls
    assert sum(kind == "plot" for kind, _ in calls) == 4
    assert sum(kind == "download" for kind, _ in calls) == 1


def test_production_seminar_jitter_and_committed_smoke_evidence_are_nonzero_and_named() -> None:
    import tomllib

    config = tomllib.loads(Path(".configs/build_rollouts_v1_realistic.toml").read_text())
    mixture = config["candidate_mixture"]["base"]
    assert (mixture["view_max_azimuth_deg"], mixture["view_max_elevation_deg"], mixture["view_roll_jitter_deg"]) == (
        60.0,
        30.0,
        0.0,
    )
    manifest = json.loads(Path("docs/contents/evidence/candidate_benchmark_wp01_smoke/manifest.json").read_text())
    assert all(
        len(manifest["provenance"][key]) == 64 and set(manifest["provenance"][key]) != {"0"}
        for key in BINDING_KEYS
        if key.endswith("sha256")
    )
    figures = json.loads(Path("docs/contents/evidence/candidate_benchmark_wp01_smoke_figures.json").read_text())[
        "figures"
    ]
    assert len(figures) == 4 and all(item["title"] for item in figures)
