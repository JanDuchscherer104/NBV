"""Tests for target-input protocol admission."""

from __future__ import annotations

import pytest

from aria_nbv.oracle.pipelines.rollout_dataset import ExplicitRolloutTargetConfig
from aria_nbv.targets.protocol import (
    ORACLE_GT_TARGET_SOURCE,
    ActorVisibleTargetSource,
    TargetDescriptorProvenance,
    TargetInputProtocol,
    TargetLabelEvidence,
    target_label_is_trainable,
    validate_target_protocol_admission,
)
from aria_nbv.targets.selection import ObservedTargetDescriptor
from aria_nbv.utils.fingerprints import stable_msgspec_hash
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


def test_observed_descriptor_requires_registered_actor_visible_source() -> None:
    admitted = validate_target_protocol_admission(
        "v1_observed",
        target_source=ActorVisibleTargetSource.DETECTED_OBBS,
        descriptor_source=ActorVisibleTargetSource.DETECTED_OBBS,
        descriptor_provenance=TargetDescriptorProvenance.ACTOR_VISIBLE_DETECTOR,
    )

    assert admitted is TargetInputProtocol.V1_OBSERVED


@pytest.mark.parametrize("protocol", ["v1-observed", "v2_unknown"])
def test_legacy_and_unknown_protocols_are_training_rejected_with_rebuild_guidance(protocol: str) -> None:
    with pytest.raises(ValueError, match="audit-readable.*rebuild"):
        validate_target_protocol_admission(
            protocol,
            target_source=ActorVisibleTargetSource.DETECTED_OBBS,
            descriptor_source=ActorVisibleTargetSource.DETECTED_OBBS,
            descriptor_provenance=TargetDescriptorProvenance.ACTOR_VISIBLE_DETECTOR,
        )


@pytest.mark.parametrize(
    ("descriptor_source", "descriptor_provenance"),
    [
        (None, TargetDescriptorProvenance.ACTOR_VISIBLE_DETECTOR),
        ("another_source", TargetDescriptorProvenance.ACTOR_VISIBLE_DETECTOR),
        (ActorVisibleTargetSource.DETECTED_OBBS, None),
        (ActorVisibleTargetSource.DETECTED_OBBS, TargetDescriptorProvenance.ORACLE_GT),
    ],
)
def test_v1_rejects_missing_or_mismatched_descriptor_provenance(
    descriptor_source: str | None,
    descriptor_provenance: TargetDescriptorProvenance | None,
) -> None:
    with pytest.raises(ValueError, match="v1_observed.*rebuild"):
        validate_target_protocol_admission(
            TargetInputProtocol.V1_OBSERVED,
            target_source=ActorVisibleTargetSource.DETECTED_OBBS,
            descriptor_source=descriptor_source,
            descriptor_provenance=descriptor_provenance,
        )


def test_v1_rejects_unregistered_source_and_mismatched_predictor_provenance() -> None:
    with pytest.raises(ValueError, match="not registered as actor-visible"):
        validate_target_protocol_admission(
            TargetInputProtocol.V1_OBSERVED,
            target_source="unregistered_detector",
            descriptor_source="unregistered_detector",
            descriptor_provenance=TargetDescriptorProvenance.ACTOR_VISIBLE_DETECTOR,
        )

    with pytest.raises(ValueError, match="does not admit descriptor provenance"):
        validate_target_protocol_admission(
            TargetInputProtocol.V1_OBSERVED,
            target_source=ActorVisibleTargetSource.DETECTED_OBBS,
            descriptor_source=ActorVisibleTargetSource.DETECTED_OBBS,
            descriptor_provenance=TargetDescriptorProvenance.ACTOR_VISIBLE_PREDICTOR,
        )


def test_v1_label_mapping_requires_strict_admitted_match() -> None:
    actor = ObservedTargetDescriptor(
        sample_key="scene/snippet/0",
        source="detected_obbs",
        source_row=3,
        target_id="scene/snippet/0:detected:3:7",
        descriptor=None,
        confidence=0.9,
        inst_id=7,
    )
    explicit_hash = stable_msgspec_hash(
        {
            "sample_key": actor.sample_key,
            "target_id": actor.target_id,
            "detected_source_row": 3,
            "gt_match_row": 5,
            "gt_match_id": "gt-5",
            "oriented_iou": 0.6,
            "descriptor_hash": actor.descriptor_hash,
        }
    )
    explicit_target = ExplicitRolloutTargetConfig(
        sample_key=actor.sample_key,
        actor_descriptor=actor,
        detected_source_row=3,
        gt_match_row=5,
        gt_match_id="gt-5",
        oriented_iou=0.6,
        target_id=actor.target_id,
        explicit_target_hash=explicit_hash,
    )

    def evidence(**changes: object) -> TargetLabelEvidence:
        values: dict[str, object] = {
            "protocol": TargetInputProtocol.V1_OBSERVED,
            "target_source": "detected_obbs",
            "gt_match_status": "admitted",
            "matched_gt_target_row_id": 5,
            "matched_gt_target_id": "gt-5",
            "gt_match_iou": 0.6,
            "target_valid": True,
            "descriptor_source": "detected_obbs",
            "descriptor_provenance": TargetDescriptorProvenance.ACTOR_VISIBLE_DETECTOR,
            "descriptor_hash": actor.descriptor_hash,
            "explicit_target_hash": explicit_target.explicit_target_hash,
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
        {"descriptor_source": None},
        {"descriptor_provenance": None},
        {"descriptor_hash": "tampered"},
        {"explicit_target_hash": "tampered"},
        {"explicit_target_hash": "b" * 64},
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
