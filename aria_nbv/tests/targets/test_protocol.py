"""Tests for target-input protocol admission."""

from __future__ import annotations

import pytest

from aria_nbv.targets.protocol import (
    ORACLE_GT_TARGET_SOURCE,
    TargetDescriptorProvenance,
    TargetInputProtocol,
    TargetLabelEvidence,
    target_label_is_trainable,
    validate_target_protocol_admission,
)
from tests.rollout_fixtures import build_rollout_records


def test_canonical_target_protocol_values_are_closed() -> None:
    assert [protocol.value for protocol in TargetInputProtocol] == ["v0_gt_input", "v1_observed"]
    assert TargetInputProtocol.V0_GT_INPUT.is_deployable is False
    assert TargetInputProtocol.V1_OBSERVED.is_deployable is True


def test_oracle_gt_descriptor_is_admitted_only_for_v0() -> None:
    admitted = validate_target_protocol_admission(
        TargetInputProtocol.V0_GT_INPUT,
        target_source=ORACLE_GT_TARGET_SOURCE,
        descriptor_source=ORACLE_GT_TARGET_SOURCE,
        descriptor_provenance=TargetDescriptorProvenance.ORACLE_GT,
    )

    assert admitted is TargetInputProtocol.V0_GT_INPUT

    with pytest.raises(ValueError, match="v1_observed.*Oracle GT.*rebuild"):
        validate_target_protocol_admission(
            TargetInputProtocol.V1_OBSERVED,
            target_source=ORACLE_GT_TARGET_SOURCE,
            descriptor_source=ORACLE_GT_TARGET_SOURCE,
            descriptor_provenance=TargetDescriptorProvenance.ORACLE_GT,
        )


def test_canonical_rollout_fixture_lineage_is_training_admissible() -> None:
    lineage = build_rollout_records(horizon=1, num_samples=6, seed=3)[0].lineage.target

    admitted = validate_target_protocol_admission(
        lineage.target_protocol_version or "",
        target_source=lineage.target_source,
        descriptor_source=lineage.target_source,
        descriptor_provenance=TargetDescriptorProvenance.ORACLE_GT,
    )

    assert admitted is TargetInputProtocol.V0_GT_INPUT


@pytest.mark.parametrize(
    "provenance",
    [
        TargetDescriptorProvenance.ACTOR_VISIBLE_DETECTOR,
        TargetDescriptorProvenance.ACTOR_VISIBLE_PREDICTOR,
    ],
)
def test_observed_descriptor_requires_matching_actor_visible_provenance(
    provenance: TargetDescriptorProvenance,
) -> None:
    admitted = validate_target_protocol_admission(
        "v1_observed",
        target_source="vin_detected_obbs",
        descriptor_source="vin_detected_obbs",
        descriptor_provenance=provenance,
    )

    assert admitted is TargetInputProtocol.V1_OBSERVED


@pytest.mark.parametrize("protocol", ["v1-observed", "v2_unknown"])
def test_legacy_and_unknown_protocols_are_training_rejected_with_rebuild_guidance(protocol: str) -> None:
    with pytest.raises(ValueError, match="audit-readable.*rebuild"):
        validate_target_protocol_admission(
            protocol,
            target_source="vin_detected_obbs",
            descriptor_source="vin_detected_obbs",
            descriptor_provenance=TargetDescriptorProvenance.ACTOR_VISIBLE_DETECTOR,
        )


@pytest.mark.parametrize(
    ("descriptor_source", "descriptor_provenance"),
    [
        (None, TargetDescriptorProvenance.ACTOR_VISIBLE_DETECTOR),
        ("another_source", TargetDescriptorProvenance.ACTOR_VISIBLE_DETECTOR),
        ("vin_detected_obbs", None),
        ("vin_detected_obbs", TargetDescriptorProvenance.ORACLE_GT),
    ],
)
def test_v1_rejects_missing_or_mismatched_descriptor_provenance(
    descriptor_source: str | None,
    descriptor_provenance: TargetDescriptorProvenance | None,
) -> None:
    with pytest.raises(ValueError, match="v1_observed.*rebuild"):
        validate_target_protocol_admission(
            TargetInputProtocol.V1_OBSERVED,
            target_source="vin_detected_obbs",
            descriptor_source=descriptor_source,
            descriptor_provenance=descriptor_provenance,
        )


def test_v1_label_mapping_requires_strict_admitted_match() -> None:
    def evidence(**changes: object) -> TargetLabelEvidence:
        values: dict[str, object] = {
            "protocol": TargetInputProtocol.V1_OBSERVED,
            "target_source": "vin_detected_obbs",
            "gt_match_status": "admitted",
            "matched_gt_target_row_id": 3,
            "matched_gt_target_id": "gt-3",
            "gt_match_iou": 0.21,
            "target_valid": True,
        }
        values.update(changes)
        return TargetLabelEvidence(**values)

    assert target_label_is_trainable(evidence())
    for changes in (
        {"gt_match_status": "ambiguous"},
        {"gt_match_status": "unmatched_gt"},
        {"gt_match_status": "rejected"},
        {"gt_match_iou": 0.20},
        {"matched_gt_target_row_id": -1},
        {"matched_gt_target_id": ""},
        {"target_valid": False},
        {"target_source": ORACLE_GT_TARGET_SOURCE},
    ):
        assert not target_label_is_trainable(evidence(**changes))


def test_v0_label_mapping_preserves_legacy_row_admission() -> None:
    assert target_label_is_trainable(
        TargetLabelEvidence(
            protocol=TargetInputProtocol.V0_GT_INPUT,
            target_source=ORACLE_GT_TARGET_SOURCE,
            gt_match_status="matched",
            matched_gt_target_row_id=0,
            matched_gt_target_id=None,
            gt_match_iou=None,
            target_valid=True,
        )
    )
