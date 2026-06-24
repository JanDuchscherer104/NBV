"""Lightning-side validation for VIN candidate scorer contracts.

`aria_nbv.vin.candidate_scorer` owns the architecture-neutral scorer protocol
and contract classifier. This sidecar owns the narrower training decision made
by `aria_nbv.lightning.lit_module.VinLightningModule`: the existing Lightning
loss path can train CORAL/VinPrediction candidate scorers, while planned
target-conditioned descriptor and finite-horizon Q_H scaffolds need their own
objective wiring before construction.
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
        The scorer contract for accepted CORAL/VinPrediction candidate scorers.

    Raises:
        NotImplementedError: If ``config`` names a planned scorer family whose
            target descriptor or finite-horizon rollout objective is not wired
            into `VinLightningModule`.
    """

    scorer_contract = candidate_scorer_training_contract(config)
    if scorer_contract == "finite_horizon_q_scaffold":
        raise NotImplementedError(
            "VinLightningModule currently trains only the CORAL/VinPrediction "
            "candidate-scorer contract. MultiStepCandidateScorerConfig names "
            "the planned Q_H finite-horizon scorer, which needs a rollout "
            "objective, hard valid-action masks, and a dedicated Lightning module.",
        )
    if scorer_contract == "target_myopic_coral_scaffold":
        raise NotImplementedError(
            "VinLightningModule can train the target-conditioned myopic family "
            "only when it emits the CORAL/VinPrediction contract. The actor-visible "
            "target descriptor path is not implemented; use target_descriptor_dim=0 "
            "for the v3-backed myopic baseline.",
        )
    return scorer_contract


__all__ = ["validate_vin_lightning_candidate_scorer_contract"]
