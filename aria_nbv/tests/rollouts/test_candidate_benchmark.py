"""Tests for the immutable candidate benchmark interchange contract."""

import json
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

from aria_nbv.pose_generation import CandidateMixtureViewGeneratorConfig
from aria_nbv.pose_generation.config import CandidateGazeConfig, SampledCenterConfig
from aria_nbv.pose_generation.types import CandidatePositionMode, ViewDirectionMode
from aria_nbv.rollouts.candidate_benchmark import (
    BINDING_KEYS,
    MULTI_STORE_BINDING_ALGORITHM,
    SCHEMA_ID,
    CandidateFamilyCounts,
    aggregate_store_content_sha256,
    candidate_family_preflight_config_from_writer,
    canonical_json_bytes,
    read_bundle,
    reduce_candidate_records,
    write_bundle,
)


def _records() -> list[dict[str, object]]:
    return [
        {
            "scene_key": "scene-b",
            "state_key": "state-1",
            "families": [
                {"family": "forward", "applicable": True, "attempted": 4, "valid": 3, "selected": 1, "denominator": 4}
            ],
            "geometry": {"radius_mean_m": 1.0},
        },
    ]


def test_reducer_is_sorted_and_counts_are_bounded() -> None:
    result = reduce_candidate_records(_records())
    assert result[0].scene_key == "scene-b"
    assert result[0].families[0] == CandidateFamilyCounts("forward", True, 4, 3, 1, 4)


def test_canonical_json_is_order_independent() -> None:
    assert canonical_json_bytes({"b": 2, "a": 1}) == canonical_json_bytes({"a": 1, "b": 2})


def test_production_seminar_jitter_contract_is_unchanged() -> None:
    config = tomllib.loads((Path(__file__).parents[3] / ".configs/build_rollouts_v1_realistic.toml").read_text())
    mixture = config["candidate_mixture"]["base"]
    assert (mixture["view_max_azimuth_deg"], mixture["view_max_elevation_deg"], mixture["view_roll_jitter_deg"]) == (
        60.0,
        30.0,
        0.0,
    )


def test_candidate_preflight_projects_legacy_and_nested_components_identically() -> None:
    nested_mixture = CandidateMixtureViewGeneratorConfig.paired_center_gaze_family()
    legacy_components = tuple(
        SimpleNamespace(
            name=component.name,
            position_mode=component.center.mode,
            view_mode=component.gazes[0].mode,
            paired_view_mode=(
                SimpleNamespace(value=component.gazes[1].mode.value) if len(component.gazes) > 1 else None
            ),
        )
        for component in nested_mixture.components
    )
    legacy_writer = SimpleNamespace(
        candidate_mixture=SimpleNamespace(components=legacy_components, total_count=nested_mixture.total_count)
    )
    nested_writer = SimpleNamespace(candidate_mixture=nested_mixture)

    assert candidate_family_preflight_config_from_writer(
        legacy_writer
    ) == candidate_family_preflight_config_from_writer(nested_writer)


def test_candidate_preflight_marks_only_target_gaze_on_forward_center_target_aware() -> None:
    component = SimpleNamespace(
        name="forward_mixed_gaze",
        center=SampledCenterConfig(mode=CandidatePositionMode.FORWARD_LOCAL),
        gazes=(
            CandidateGazeConfig(name="primary", mode=ViewDirectionMode.FORWARD_RIG),
            CandidateGazeConfig(name="target", mode=ViewDirectionMode.TARGET_POINT),
        ),
    )
    writer = SimpleNamespace(candidate_mixture=SimpleNamespace(components=(component,), total_count=8))

    preflight = candidate_family_preflight_config_from_writer(writer)

    assert preflight.configured_families == ("forward_mixed_gaze", "forward_mixed_gaze__target")
    assert preflight.target_aware_families == ("forward_mixed_gaze__target",)


def test_bundle_requires_parquet_engine_or_round_trips(tmp_path: Path) -> None:
    provenance = {
        key: (
            "candidate_benchmark"
            if key == "evidence_class"
            else "complete"
            if key == "completion"
            else SCHEMA_ID
            if key == "schema_id"
            else "1"
            if key == "implementation_revision"
            else "1" * 64
        )
        for key in BINDING_KEYS
    }
    try:
        path = write_bundle(tmp_path / "bundle", _records(), provenance=provenance)
    except RuntimeError as exc:
        assert "Parquet engine" in str(exc)
        return
    loaded = read_bundle(path, expected_binding=provenance)
    assert loaded.manifest["record_count"] == 1
    assert loaded.records[0].scene_key == "scene-b"


@pytest.mark.parametrize("name", ["fixture-bundle", "partial"])
def test_invalid_bundle_rejected(tmp_path: Path, name: str) -> None:
    path = tmp_path / name
    path.mkdir()
    if name == "partial":
        (path / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        read_bundle(path, expected_binding={})


def test_committed_html_reports_canonical_bundle_counts() -> None:
    root = Path(__file__).parents[3] / "docs/contents/evidence/candidate_benchmark_wp01_smoke"
    manifest = json.loads((root / "manifest.json").read_text())
    bundle = read_bundle(root, expected_binding=manifest["provenance"])
    html = (root.parent / "candidate_benchmark_wp01_smoke.html").read_text()
    assert 'data-funnel-counts="960,503,16"' in html
    assert 'data-point-count="960"' in html
    assert '"customdata"' in html
    assert sum(len(record.points) for record in bundle.records) == 960


def test_committed_smoke_bundle_binds_both_promoted_store_seals() -> None:
    root = Path(__file__).parents[3] / "docs/contents/evidence"
    manifest = json.loads((root / "candidate_benchmark_wp01_smoke/manifest.json").read_text())
    metadata = json.loads((root / "candidate_benchmark_wp01_smoke_metadata.json").read_text())
    summary = json.loads((root / "candidate_benchmark_wp01_smoke.json").read_text())
    seals = {store["identity"]: store["rollout_store_content_sha256"] for store in metadata["stores"]}

    assert metadata["multi_store_binding"]["algorithm"] == MULTI_STORE_BINDING_ALGORITHM
    aggregate = aggregate_store_content_sha256(seals)
    assert aggregate == "5ee02217d1c49efa44a1296d11ba35e5f63ea563992bb4a3e7e921610b238677"
    assert manifest["provenance"]["store_content_sha256"] == aggregate
    assert metadata["multi_store_binding"]["store_content_sha256"] == aggregate
    assert summary["multi_store_binding"] == {
        "algorithm": MULTI_STORE_BINDING_ALGORITHM,
        "store_content_sha256": aggregate,
        "stores": seals,
    }


def test_dto_rejects_duplicate_or_misaligned_candidates() -> None:
    from aria_nbv.rollouts.candidate_benchmark import CandidateBenchmark, CandidatePoint

    point = CandidatePoint(1, (0.0, 0.0, 0.0), "forward", "forward", True, False, "s")
    with pytest.raises(ValueError):
        CandidateBenchmark(
            "s",
            "scene",
            (),
            candidate_ids=(1, 1),
            coordinates=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            points=(point, point),
        )


def test_benchmark_reader_keeps_selected_scan_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    import aria_nbv.rollouts.inspection as inspection

    calls: list[dict[str, object]] = []

    def fake_rows(reader: object, **kwargs: object) -> list[dict[str, object]]:
        calls.append(kwargs)
        return []

    monkeypatch.setattr(inspection, "candidate_audit_rows", fake_rows)
    from aria_nbv.rollouts.candidate_benchmark import benchmarks_from_reader

    assert benchmarks_from_reader(object(), state_key="rollout:9/step:17", candidate_limit=3) == ()
    assert calls == [{"rollout_row_id": 9, "step_row_id": 17, "limit": 3}]


def test_benchmark_reader_invalid_state_does_not_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    import aria_nbv.rollouts.inspection as inspection

    monkeypatch.setattr(inspection, "candidate_audit_rows", lambda *_args, **_kwargs: pytest.fail("scan"))
    from aria_nbv.rollouts.candidate_benchmark import benchmarks_from_reader

    assert benchmarks_from_reader(object(), state_key="not-a-state", candidate_limit=3) == ()


def test_reader_binding_changes_when_promoted_seal_changes(tmp_path: Path) -> None:
    from aria_nbv.rollouts.candidate_benchmark import benchmark_binding_from_reader

    class Reader:
        store_dir = tmp_path

        @staticmethod
        def manifest() -> dict[str, object]:
            return {"manifest": {"generation": {"writer_config": {}}, "source_coverage": {}}}

    import hashlib

    seal_hash = hashlib.sha256(b"persisted-content").hexdigest()
    (tmp_path / "_SUCCESS.json").write_text(json.dumps({"rollout_store_content_sha256": seal_hash}), encoding="utf-8")
    (tmp_path / "_owner.json").write_text(json.dumps({"rollout_store_content_sha256": seal_hash}), encoding="utf-8")
    benchmark_binding_from_reader(Reader())
    (tmp_path / "_owner.json").write_text(json.dumps({"rollout_store_content_sha256": "1" * 64}), encoding="utf-8")
    with pytest.raises(ValueError, match="disagree"):
        benchmark_binding_from_reader(Reader())


def test_unpromoted_reader_binding_changes_with_persisted_content(tmp_path: Path) -> None:
    from aria_nbv.rollouts.candidate_benchmark import benchmark_binding_from_reader

    class Reader:
        store_dir = tmp_path

        @staticmethod
        def manifest() -> dict[str, object]:
            return {"manifest": {"generation": {"writer_config": {}}, "source_coverage": {}}}

    payload = tmp_path / "candidates.bin"
    payload.write_bytes(b"first")
    first = benchmark_binding_from_reader(Reader())
    payload.write_bytes(b"second")
    second = benchmark_binding_from_reader(Reader())
    assert first["store_content_sha256"] != second["store_content_sha256"]
