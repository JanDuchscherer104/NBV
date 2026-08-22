"""Pipeline-local Q_H inference adapters and immutable round receipts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import torch

from ...rollouts.replay.policy import RolloutPolicySpec
from ...rollouts.replay.types import CandidateScores
from ...vin.models.target_finite_horizon import TargetFiniteHorizonScorer
from ...vin.qh_bundle import QhInferenceBundleRef
from ..environment import OracleDecisionContext


class _QhCandidateScoreAdapter:
    """Project one bound actor context to the existing replay score contract."""

    def __init__(
        self,
        scorer: TargetFiniteHorizonScorer,
        *,
        behavior_model_hash: str,
        behavior_config_hash: str,
    ) -> None:
        if scorer.training:
            raise ValueError("Online Q_H collection requires a scorer in evaluation mode.")
        if not behavior_model_hash or not behavior_config_hash:
            raise ValueError("Online Q_H scoring requires non-empty behavior model and config hashes.")
        self.scorer = scorer
        self.behavior_model_hash = behavior_model_hash
        self.behavior_config_hash = behavior_config_hash

    def __call__(self, context: OracleDecisionContext) -> CandidateScores:
        """Return detached compact scores aligned to the bound hard-valid rows."""

        actor = context.to_qh_actor()
        candidates = context.candidates
        if not bool(torch.as_tensor(candidates.mask_valid, dtype=torch.bool).any()):
            raise ValueError("Online Q_H scoring requires at least one hard-valid candidate row.")
        with torch.inference_mode():
            values = self.scorer(actor)
        realized = torch.nonzero(actor.step_mask[0], as_tuple=False).reshape(-1)
        if realized.numel() == 0:
            raise ValueError("Online Q_H scoring requires one realized actor state.")
        state_index = int(realized[-1].item())
        action_mask = actor.action_mask[0, state_index]
        valid_values = values[0, state_index][action_mask]
        device = candidates.poses_world_cam().t.device
        dtype = candidates.poses_world_cam().t.dtype
        return CandidateScores.from_valid_values(
            valid_values.detach().to(device=device, dtype=dtype),
            name="target_finite_horizon_qh",
            candidates=candidates,
            device=device,
            dtype=dtype,
        )


@dataclass(frozen=True, slots=True)
class OnlineQhRoundRequest:
    """Frozen behavior and query policy for one synchronous collection round."""

    behavior_bundle: QhInferenceBundleRef
    """Verified immutable model used for every decision in the round."""

    training_population_manifest: Path
    """Train-only scene/acquisition population manifest."""

    acquisition_round: int
    """Non-negative sequential round identifier."""

    proposal_policy_manifest_sha256: str
    """Candidate proposal-policy manifest identity, distinct from selection."""

    selection_policy: RolloutPolicySpec
    """Existing replay selection policy applied to Q_H scores."""

    oracle_query_budget: int
    """Positive hard-oracle candidate-row budget."""

    query_mode: Literal["dense_valid"] = "dense_valid"
    """Closed MVP collection mode admitted to fitted-Q learning."""

    def __post_init__(self) -> None:
        if self.acquisition_round < 0:
            raise ValueError("Online Q_H acquisition_round must be non-negative.")
        if self.oracle_query_budget < 1:
            raise ValueError("Online Q_H oracle_query_budget must be positive.")
        if not self.proposal_policy_manifest_sha256:
            raise ValueError("Online Q_H rounds require proposal-policy manifest identity.")
        if self.query_mode != "dense_valid":
            raise ValueError("Online Q_H MVP rounds require query_mode='dense_valid'.")


@dataclass(frozen=True, slots=True)
class OnlineQhRoundCounts:
    """Explicit non-derived counters for one collection round."""

    proposed: int
    """All attempted candidate rows before hard validity."""

    valid: int
    """Hard-valid candidate rows presented to a selection policy."""

    queried: int
    """Candidate rows submitted to the hard oracle."""

    labeled: int
    """Candidate rows with admitted finite oracle labels."""

    selected: int
    """Actions selected for replay transitions."""

    persisted: int
    """Transitions committed to the immutable shard."""

    rejected: int
    """Explicitly rejected attempts or episodes."""

    def __post_init__(self) -> None:
        values = (
            self.proposed,
            self.valid,
            self.queried,
            self.labeled,
            self.selected,
            self.persisted,
            self.rejected,
        )
        if any(value < 0 for value in values):
            raise ValueError("Online Q_H round counts must be non-negative.")


@dataclass(frozen=True, slots=True)
class OnlineQhRoundResult:
    """Validated immutable shard and provenance receipt for one round."""

    shard_dir: Path
    """New immutable dense-valid rollout shard."""

    shard_manifest_sha256: str
    """Validated shard-manifest content identity."""

    behavior_bundle_manifest_sha256: str
    """Frozen behavior bundle used throughout collection."""

    proposal_policy_manifest_sha256: str
    """Candidate-proposal policy identity, separate from selection."""

    oracle_query_policy_id: Literal["dense_valid_v1"]
    """Closed hard-oracle query policy admitted to the MVP objective."""

    selected_action_policy_sha256: str
    """Existing replay selection-policy identity."""

    round_receipt_path: Path
    """Canonical collection receipt path."""

    round_receipt_sha256: str
    """Content hash of :attr:`round_receipt_path`."""

    counts: OnlineQhRoundCounts
    """Explicit collection counters; readers must not derive one from another."""

    def __post_init__(self) -> None:
        hashes = (
            self.shard_manifest_sha256,
            self.behavior_bundle_manifest_sha256,
            self.proposal_policy_manifest_sha256,
            self.selected_action_policy_sha256,
            self.round_receipt_sha256,
        )
        if any(not value for value in hashes):
            raise ValueError("Online Q_H round results require every shard, bundle, policy, and receipt hash.")
        if self.oracle_query_policy_id != "dense_valid_v1":
            raise ValueError("Online Q_H MVP results require oracle_query_policy_id='dense_valid_v1'.")


__all__ = ["OnlineQhRoundCounts", "OnlineQhRoundRequest", "OnlineQhRoundResult"]
