"""Lightning-side validation for VIN candidate scorer contracts.

:mod:`aria_nbv.vin.candidate_scorer` owns the architecture-neutral scorer protocol
and contract classifier. This sidecar owns the narrower training decision made
by :class:`aria_nbv.lightning.lit_module.VinLightningModule`: the existing Lightning
loss path can train CORAL/VinPrediction candidate scorers, while planned
target-conditioned descriptor scaffolds need their own objective wiring before
construction. Finite-horizon ``Q_H`` training is owned by the separate
scorer-independent Q_H Lightning module.
"""

from __future__ import annotations

from ..vin.candidate_scorer import (
    CandidateScorerConfig,
    CandidateScorerTrainingContract,
    candidate_scorer_training_contract,
)


def validate_vin_lightning_candidate_scorer_contract(
    config: CandidateScorerConfig,
) -> CandidateScorerTrainingContract:
    """Return the scorer contract or reject contracts unsupported by Lightning.

    Args:
        config: Candidate scorer config from `VinLightningModuleConfig.vin`.

    Returns:
        The scorer contract for accepted
        CORAL/:class:`aria_nbv.vin.types.VinPrediction`
        candidate scorers. Accepted predictions expose logits
        ``Tensor["B N_q K-1", float32]``, ordinal probabilities
        ``Tensor["B N_q K", float32]``, and expected scores
        ``Tensor["B N_q", float32]``.

    Raises:
        NotImplementedError: If ``config`` names a planned scorer family whose
            actor-visible target descriptor is not wired into
            :class:`aria_nbv.lightning.VinLightningModule`.

    Notes:
        The current scorer receives actor-visible snippet evidence and
        candidate geometry. Oracle RRI labels are consumed only by the
        Lightning loss after prediction; they are never scorer inputs.
    """

    scorer_contract = candidate_scorer_training_contract(config)
    if scorer_contract == "target_myopic_coral_scaffold":
        raise NotImplementedError(
            "VinLightningModule can train the target-conditioned myopic family "
            "only when it emits the CORAL/VinPrediction contract. The actor-visible "
            "target descriptor path is not implemented; use target_descriptor_dim=0 "
            "for the v3-backed myopic baseline.",
        )
    return scorer_contract


__all__ = ["validate_vin_lightning_candidate_scorer_contract"]
