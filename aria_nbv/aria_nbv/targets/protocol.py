"""Target-input protocol and training-admission contract.

This leaf keeps protocol spelling, target-source ownership, and descriptor
provenance validation together. Persisted rollout readers may display any raw
legacy value; callers cross this interface only when admitting new generation
or training data.
"""

from __future__ import annotations

from enum import StrEnum

ORACLE_GT_TARGET_SOURCE = "gt_obbs_oracle"
"""Canonical source label for descriptors constructed from Oracle GT OBBs."""


class TargetInputProtocol(StrEnum):
    """Canonical target-input protocols admitted by new configs and corpora."""

    V0_GT_INPUT = "v0_gt_input"
    """GT-derived target input for non-deployable Oracle experiments."""

    V1_OBSERVED = "v1_observed"
    """Actor-visible target input produced by an observed detector or predictor."""

    @property
    def is_deployable(self) -> bool:
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


_ACTOR_VISIBLE_PROVENANCE = frozenset(
    {
        TargetDescriptorProvenance.ACTOR_VISIBLE_DETECTOR,
        TargetDescriptorProvenance.ACTOR_VISIBLE_PREDICTOR,
    }
)


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
            V1 accepts only actor-visible detector or predictor provenance.

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
    if provenance not in _ACTOR_VISIBLE_PROVENANCE:
        raise ValueError(
            "v1_observed requires actor-visible detector or predictor descriptor provenance; rebuild the corpus."
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
