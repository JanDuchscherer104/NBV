"""Target-input protocol and training-admission contract.

This leaf keeps protocol spelling, target-source ownership, and descriptor
provenance validation together. Persisted rollout readers may display any raw
legacy value; callers cross this interface only when admitting new generation
or training data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

ORACLE_GT_TARGET_SOURCE = "gt_obbs_oracle"
"""Canonical source label for descriptors constructed from Oracle GT OBBs."""

STRICT_GT_IOU_THRESHOLD = 0.20
"""Strict lower bound for an unambiguous observed-target GT match."""


class TargetInputProtocol(StrEnum):
    """Canonical target-input protocols admitted by new configs and corpora."""

    V0_GT_INPUT = "v0_gt_input"
    """GT-derived target input for non-deployable Oracle experiments."""

    V1_OBSERVED = "v1_observed"
    """Actor-visible target input produced by an observed detector or predictor."""

    @property
    def is_actor_visible_target_protocol(self) -> bool:
        """Whether the protocol requires actor-visible target evidence."""

        return self is TargetInputProtocol.V1_OBSERVED


class TargetDescriptorProvenance(StrEnum):
    """How the descriptor supplied to the actor was constructed."""

    ORACLE_GT = "oracle_gt"
    """Descriptor constructed from privileged GT target geometry."""

    ACTOR_VISIBLE_DETECTOR = "actor_visible_detector"
    """Descriptor constructed from actor-visible detector output."""

    ACTOR_VISIBLE_PREDICTOR = "actor_visible_predictor"
    """Descriptor constructed from actor-visible predicted target state."""


class ActorVisibleTargetSource(StrEnum):
    """Canonical persisted source names admitted for observed targets."""

    DETECTED_OBBS = "detected_obbs"
    """Actor-visible OBB detections produced by the VIN source store."""


_ACTOR_VISIBLE_SOURCE_PROVENANCE = {
    ActorVisibleTargetSource.DETECTED_OBBS.value: frozenset({TargetDescriptorProvenance.ACTOR_VISIBLE_DETECTOR}),
}


@dataclass(frozen=True, slots=True)
class TargetLabelEvidence:
    """Persisted target facts used to admit oracle labels for training.

    The mapping deliberately keeps target-task validity separate from store
    provenance.  A caller must validate the latter independently before using
    this predicate for a training view.
    """

    protocol: TargetInputProtocol | str
    target_source: str | None
    gt_match_status: str | None
    matched_gt_target_row_id: int | None
    matched_gt_target_id: str | None
    gt_match_iou: float | None
    target_valid: bool
    descriptor_source: str | None = None
    descriptor_provenance: TargetDescriptorProvenance | str | None = None
    descriptor_hash: str | None = None
    explicit_target_hash: str | None = None


def target_label_is_trainable(evidence: TargetLabelEvidence) -> bool:
    """Return whether one target's GT evidence is trainable.

    V0 retains its historical row-based admission.  V1 requires the actor
    visible protocol, an exact ``admitted`` match with both stable identifiers,
    and a finite oriented IoU strictly above the campaign threshold.  Malformed
    evidence is rejected rather than interpreted as a weak label.
    """

    try:
        protocol = _canonical_protocol(evidence.protocol)
        if not bool(evidence.target_valid):
            return False
        row_id = evidence.matched_gt_target_row_id
        if row_id is None or int(row_id) < 0:
            return False
        if protocol is TargetInputProtocol.V0_GT_INPUT:
            return evidence.gt_match_status in {"matched", "v0_gt_input"}
        descriptor_source = evidence.descriptor_source
        if evidence.descriptor_provenance is None or not descriptor_source:
            return False
        validate_target_protocol_admission(
            protocol,
            target_source=evidence.target_source,
            descriptor_source=descriptor_source,
            descriptor_provenance=evidence.descriptor_provenance,
        )
        if not _is_hex_digest(evidence.descriptor_hash, length=64) or not _is_hex_digest(
            evidence.explicit_target_hash, length=16
        ):
            return False
        iou = evidence.gt_match_iou
        return bool(
            evidence.gt_match_status == "admitted"
            and bool(evidence.matched_gt_target_id)
            and iou is not None
            and math.isfinite(float(iou))
            and float(iou) > STRICT_GT_IOU_THRESHOLD
        )
    except (TypeError, ValueError):
        return False


def _is_hex_digest(value: str | None, *, length: int) -> bool:
    """Return whether a persisted identity proof has the requested hex shape."""

    if value is None or len(value) != length:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def validate_target_protocol_admission(
    protocol: TargetInputProtocol | str,
    *,
    target_source: str | None,
    descriptor_source: str | None = None,
    descriptor_provenance: TargetDescriptorProvenance | str | None = None,
) -> TargetInputProtocol:
    """Validate one target descriptor before generation or training admission.

    Args:
        protocol: Raw persisted value or canonical protocol.
        target_source: Source that selected the target task.
        descriptor_source: Source block that constructed the actor descriptor.
            V0 may omit this because its Oracle source is fixed; V1 must name it.
        descriptor_provenance: Construction class for the actor descriptor.
            V1 accepts only a provenance registered for ``target_source``.

    Returns:
        The canonical admitted protocol.

    Notes:
        Rejection never mutates persisted artifacts. Legacy and unknown strings
        remain available to audit readers but require corpus regeneration before
        use in training.
    """

    admitted_protocol = _canonical_protocol(protocol)
    provenance = _descriptor_provenance(descriptor_provenance)

    if admitted_protocol is TargetInputProtocol.V0_GT_INPUT:
        if target_source != ORACLE_GT_TARGET_SOURCE:
            raise ValueError(
                "v0_gt_input requires the Oracle GT target source; rebuild the corpus with "
                f"target_source={ORACLE_GT_TARGET_SOURCE!r}."
            )
        if descriptor_source not in {None, ORACLE_GT_TARGET_SOURCE}:
            raise ValueError(
                "v0_gt_input requires an Oracle GT descriptor source; rebuild the corpus with matching provenance."
            )
        if provenance not in {None, TargetDescriptorProvenance.ORACLE_GT}:
            raise ValueError(
                "v0_gt_input cannot claim actor-visible descriptor provenance; rebuild with Oracle GT provenance."
            )
        return admitted_protocol

    if target_source == ORACLE_GT_TARGET_SOURCE:
        raise ValueError(
            "v1_observed cannot use the Oracle GT target source; rebuild from an actor-visible detector or predictor."
        )
    if not target_source or descriptor_source != target_source:
        raise ValueError(
            "v1_observed requires matching non-empty target and descriptor sources; rebuild with explicit "
            "actor-visible descriptor provenance."
        )
    allowed_provenance = _ACTOR_VISIBLE_SOURCE_PROVENANCE.get(target_source)
    if allowed_provenance is None:
        raise ValueError(
            f"v1_observed target source {target_source!r} is not registered as actor-visible; "
            "rebuild from a canonical source."
        )
    if provenance not in allowed_provenance:
        raise ValueError(
            f"v1_observed source {target_source!r} does not admit descriptor provenance "
            f"{str(provenance)!r}; rebuild with matching actor-visible provenance."
        )
    return admitted_protocol


def _canonical_protocol(protocol: TargetInputProtocol | str) -> TargetInputProtocol:
    try:
        return TargetInputProtocol(protocol)
    except ValueError as error:
        raise ValueError(
            f"Target protocol {str(protocol)!r} is audit-readable but not training-admissible; "
            "rebuild with 'v0_gt_input' or 'v1_observed'."
        ) from error


def _descriptor_provenance(
    provenance: TargetDescriptorProvenance | str | None,
) -> TargetDescriptorProvenance | None:
    if provenance is None:
        return None
    try:
        return TargetDescriptorProvenance(provenance)
    except ValueError as error:
        raise ValueError(
            f"Descriptor provenance {str(provenance)!r} is not training-admissible; rebuild with an explicit "
            "Oracle GT, actor-visible detector, or actor-visible predictor source."
        ) from error
