"""Tests for the immutable candidate benchmark interchange contract."""

import json
import tomllib
from pathlib import Path

import pytest

from aria_nbv.rollouts.candidate_benchmark import (
    BINDING_KEYS,
    CandidateFamilyCounts,
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
    assert (mixture["view_max_azimuth_deg"], mixture["view_max_elevation_deg"], mixture["view_roll_jitter_deg"]) == (60.0, 30.0, 0.0)


def test_bundle_requires_parquet_engine_or_round_trips(tmp_path: Path) -> None:
    provenance = {
        key: ("candidate_benchmark" if key == "evidence_class" else "complete" if key == "completion" else "aria-nbv-candidate-benchmark-v1" if key == "schema_id" else "1" if key == "implementation_revision" else "1" * 64)
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


def test_dto_rejects_duplicate_or_misaligned_candidates() -> None:
    from aria_nbv.rollouts.candidate_benchmark import CandidateBenchmark, CandidatePoint

    point = CandidatePoint(1, (0.0, 0.0, 0.0), "forward", "forward", True, False, "s")
    with pytest.raises(ValueError):
        CandidateBenchmark("s", "scene", (), candidate_ids=(1, 1), coordinates=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)), points=(point, point))
