"""Focused contract tests for campaign admission evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aria_nbv.oracle.pipelines.admission_evidence import read_campaign_admission_evidence
from aria_nbv.utils.fingerprints import stable_msgspec_hash


def _payload(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": "campaign-admission-audit-v2",
        "campaign_id": "campaign-test",
        "source_manifest_hash": "source-test",
        "admission_audit_hash": stable_msgspec_hash(rows),
        "rows": rows,
    }


def _row(**updates: object) -> dict[str, object]:
    row: dict[str, object] = {
        "sample_key": "sample-1",
        "scene_id": "scene-1",
        "target_id": "target-1",
        "reason": "admitted",
        "admitted": True,
        "oriented_iou": 0.8,
        "qualified_gt_match_count": 1,
        "gt_match_id": "gt-1",
        "detected_source_row": 0,
    }
    row.update(updates)
    return row


def test_read_admission_evidence_returns_deterministic_additive_rows(tmp_path: Path) -> None:
    rows = [
        _row(),
        _row(
            target_id="target-2",
            reason="below_iou_threshold",
            admitted=False,
            oriented_iou=0.2,
            qualified_gt_match_count=0,
            gt_match_id=None,
        ),
        _row(
            target_id="target-3",
            scene_id="scene-2",
            reason="wrong_class",
            admitted=False,
            oriented_iou=None,
            qualified_gt_match_count=0,
            gt_match_id=None,
        ),
    ]
    path = tmp_path / "admission-audit.json"
    path.write_text(json.dumps(_payload(rows)), encoding="utf-8")

    evidence = read_campaign_admission_evidence(
        path,
        expected_campaign_id="campaign-test",
        expected_source_manifest_hash="source-test",
    )

    assert evidence.observed_count == 3
    assert evidence.admitted_count == 1
    assert evidence.rejected_count == 2
    assert evidence.finite_iou_count == 2
    assert evidence.reason_rows == (
        {"admitted": True, "count": 1, "reason": "admitted"},
        {"admitted": False, "count": 1, "reason": "below_iou_threshold"},
        {"admitted": False, "count": 1, "reason": "wrong_class"},
    )
    assert evidence.scene_rows == (
        {"scene_id": "scene-1", "observed_count": 2, "admitted_count": 1, "admission_rate": 0.5},
        {"scene_id": "scene-2", "observed_count": 1, "admitted_count": 0, "admission_rate": 0.0},
    )


def test_duplicate_gt_rows_are_explicit_and_deterministic() -> None:
    rows = [
        _row(target_id="target-a"),
        _row(target_id="target-b"),
    ]
    evidence = read_campaign_admission_evidence(_payload(rows))

    assert evidence.duplicate_gt_rows == (
        {
            "sample_key": "sample-1",
            "gt_match_id": "gt-1",
            "scene_id": "scene-1",
            "matched_target_count": 2,
            "admitted_target_count": 2,
        },
    )


def test_legacy_v1_audit_remains_readable_and_exportable() -> None:
    payload = _payload([_row()])
    payload["schema_version"] = "campaign-admission-audit-v1"

    evidence = read_campaign_admission_evidence(payload)

    exported = evidence.to_jsonable()
    assert exported["counts"] == {
        "observed": 1,
        "admitted": 1,
        "rejected": 0,
        "finite_iou": 1,
        "same_class_scored": 1,
        "ambiguous": 0,
        "duplicate_gt_groups": 0,
        "zero_observation_samples": 0,
        "zero_observation_scenes": 0,
    }
    assert exported["rows"][0]["target_id"] == "target-1"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda payload: payload.update(admission_audit_hash="tampered"), "hash"),
        (lambda payload: payload["rows"][0].update(oriented_iou=1.1), "hash"),
        (lambda payload: payload["rows"][0].update(admitted=False), "hash"),
        (lambda payload: payload["rows"][0].update(admitted=True, reason="wrong_class"), "hash"),
        (lambda payload: payload.update(schema_version="campaign-admission-audit-v0"), "schema"),
    ],
)
def test_malformed_or_tampered_audit_fails_closed(change, message: str) -> None:
    payload = _payload([_row()])
    change(payload)
    with pytest.raises(ValueError, match=message):
        read_campaign_admission_evidence(payload)


def test_expected_identity_mismatch_fails_closed() -> None:
    with pytest.raises(ValueError, match="campaign identity"):
        read_campaign_admission_evidence(_payload([_row()]), expected_campaign_id="other")


def test_zero_observation_sample_sentinel_is_not_an_observed_target() -> None:
    rows = [
        _row(),
        {
            "sample_key": "sample-empty",
            "scene_id": "scene-empty",
            "target_id": "",
            "reason": "excluded_no_observed_target",
            "admitted": False,
            "oriented_iou": None,
            "qualified_gt_match_count": 0,
            "gt_match_id": None,
            "detected_source_row": None,
            "row_kind": "zero_observation_sample",
            "observed_target_count": 0,
        },
    ]
    evidence = read_campaign_admission_evidence(_payload(rows))

    assert evidence.observed_count == 1
    assert evidence.zero_observation_sample_count == 1
    assert evidence.zero_observation_scene_count == 1
    assert all(row["scene_id"] != "scene-empty" for row in evidence.scene_rows)
    assert evidence.to_jsonable()["counts"]["zero_observation_samples"] == 1


def test_writer_shaped_legacy_zero_observation_sentinel_is_inferred() -> None:
    sentinel = {
        "sample_key": "sample-empty",
        "scene_id": "scene-empty",
        "target_id": "",
        "reason": "excluded_no_observed_target",
        "admitted": False,
        "oriented_iou": None,
        "qualified_gt_match_count": 0,
        "gt_match_id": None,
        "detected_source_row": None,
        "observed_target_count": 0,
    }
    evidence = read_campaign_admission_evidence(_payload([sentinel]))

    assert evidence.observed_count == 0
    assert evidence.zero_observation_sample_count == 1


@pytest.mark.parametrize(
    "change",
    [
        lambda row: row.update(target_id="target-1"),
        lambda row: row.update(admitted=True),
        lambda row: row.update(reason="wrong_class"),
    ],
)
def test_partial_legacy_zero_observation_sentinel_fails_closed(change) -> None:
    row = {
        "sample_key": "sample-empty",
        "scene_id": "scene-empty",
        "target_id": "",
        "reason": "excluded_no_observed_target",
        "admitted": False,
        "oriented_iou": None,
        "qualified_gt_match_count": 0,
        "gt_match_id": None,
        "detected_source_row": None,
        "observed_target_count": 0,
    }
    change(row)
    with pytest.raises(ValueError):
        read_campaign_admission_evidence(_payload([row]))


def test_consistency_and_iou_checks_run_after_hash_validation() -> None:
    payload = _payload([_row(admitted=False, reason="wrong_class", oriented_iou=1.2)])
    with pytest.raises(ValueError, match=r"outside \[0, 1\]"):
        read_campaign_admission_evidence(payload)

    payload = _payload([_row(admitted=False, reason="admitted")])
    with pytest.raises(ValueError, match="admitted/reason"):
        read_campaign_admission_evidence(payload)


@pytest.mark.parametrize("iou", [0.0, 0.20])
def test_admitted_rows_require_strict_iou_above_point_two(iou: float) -> None:
    payload = _payload([_row(oriented_iou=iou)])

    with pytest.raises(ValueError, match="strictly greater than 0.20"):
        read_campaign_admission_evidence(payload)
