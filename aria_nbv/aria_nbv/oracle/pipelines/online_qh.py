"""Pipeline-local Q_H inference adapters and immutable round receipts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import torch

from ...data_handling.qh_data.batching import move_qh_actor_tensors
from ...rollouts.replay.policy import RolloutPolicySpec
from ...rollouts.replay.types import CandidateScores
from ...vin.qh_bundle import QhInferenceBundleRef, QhInferenceRuntime
from ..environment import OracleDecisionContext


class _QhCandidateScoreAdapter:
    """Project one bound actor context to the existing replay score contract."""

    def __init__(
        self,
        runtime: QhInferenceRuntime,
    ) -> None:
        if runtime.scorer.training:
            raise ValueError("Online Q_H collection requires a scorer in evaluation mode.")
        self.runtime = runtime
        self.behavior_model_hash = runtime.scorer_state_sha256
        self.behavior_config_hash = runtime.scorer_config_hash

    def __call__(self, context: OracleDecisionContext) -> CandidateScores:
        """Return detached compact scores aligned to the bound hard-valid rows."""

        actor = context.to_qh_actor()
        _validate_runtime_context(self.runtime, context)
        candidates = context.candidates
        if not bool(torch.as_tensor(candidates.mask_valid, dtype=torch.bool).any()):
            raise ValueError("Online Q_H scoring requires at least one hard-valid candidate row.")
        scorer_device = _module_device(self.runtime.scorer)
        actor = move_qh_actor_tensors(actor, scorer_device)
        with torch.inference_mode():
            values = self.runtime.scorer(actor)
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


def _module_device(module: torch.nn.Module) -> torch.device:
    """Return the device of one internally device-consistent scorer."""

    try:
        return next(module.parameters()).device
    except StopIteration:
        try:
            return next(module.buffers()).device
        except StopIteration:
            return torch.device("cpu")


def _validate_runtime_context(runtime: QhInferenceRuntime, context: OracleDecisionContext) -> None:
    """Reject a decision whose explicit inputs were not admitted by the bundle."""

    contract = context.input_contract
    mismatches: list[str] = []
    if runtime.actor_state_contract_hash != contract.actor_state_contract_hash:
        mismatches.append("actor_state_contract_hash")
    if runtime.learning_contract_hash != contract.learning_contract_hash:
        mismatches.append("learning_contract_hash")
    if runtime.target_protocol != str(contract.target_protocol):
        mismatches.append("target_protocol")
    if contract.candidate_config_hash not in runtime.candidate_config_hashes:
        mismatches.append("candidate_config_hash")
    if runtime.action_mask_semantics != contract.action_mask_semantics:
        mismatches.append("action_mask_semantics")
    if runtime.representation_semantics != contract.representation_semantics:
        mismatches.append("representation_semantics")
    if mismatches:
        raise ValueError(f"Q_H inference runtime rejects decision inputs: {', '.join(mismatches)} mismatch.")


@dataclass(frozen=True, slots=True)
class OnlineQhPopulationManifestRef:
    """Content-bound reference to the immutable collection population."""

    manifest_path: Path
    """Path to the exact JSON population manifest."""

    schema_version: str
    """Closed schema expected inside the manifest payload."""

    manifest_sha256: str
    """SHA-256 of the exact manifest bytes."""

    def __post_init__(self) -> None:
        if not self.schema_version or not _is_sha256(self.manifest_sha256):
            raise ValueError("Online Q_H population references require schema and content identities.")
        object.__setattr__(self, "manifest_path", self.manifest_path.expanduser().resolve())

    def read_verified(self) -> dict[str, Any]:
        """Read the manifest after verifying its exact bytes and declared schema."""

        payload_bytes = self.manifest_path.read_bytes()
        actual_sha256 = hashlib.sha256(payload_bytes).hexdigest()
        if actual_sha256 != self.manifest_sha256:
            raise ValueError("Online Q_H training population manifest content hash mismatch.")
        payload = json.loads(payload_bytes)
        if not isinstance(payload, dict):
            raise ValueError("Online Q_H training population manifest must contain a JSON object.")
        if payload.get("schema_version") != self.schema_version:
            raise ValueError("Online Q_H training population manifest schema mismatch.")
        return payload


@dataclass(frozen=True, slots=True)
class OnlineQhRoundRequest:
    """Frozen behavior and query policy for one synchronous collection round."""

    behavior_bundle: QhInferenceBundleRef
    """Verified immutable model used for every decision in the round."""

    training_population_manifest: OnlineQhPopulationManifestRef
    """Content-bound train-only scene/acquisition population manifest."""

    acquisition_round: int
    """Non-negative sequential round identifier."""

    proposal_policy_manifest_sha256: str
    """Candidate proposal-policy manifest identity, distinct from selection."""

    selection_policy: RolloutPolicySpec
    """Existing replay selection policy applied to Q_H scores."""

    oracle_query_budget: int
    """Positive hard-oracle candidate-row budget."""

    decision_cohort: Literal["oracle_upper_bound_v1", "deployment_v1"]
    """Explicit role of every decision collected in this round."""

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
        if self.decision_cohort not in {"oracle_upper_bound_v1", "deployment_v1"}:
            raise ValueError(f"Unsupported Online Q_H decision cohort {self.decision_cohort!r}.")

    def verify_training_population(self) -> dict[str, Any]:
        """Return the population only after exact content and schema verification."""

        return self.training_population_manifest.read_verified()


@dataclass(frozen=True, slots=True)
class OnlineQhRoundCounts:
    """Explicit non-derived counters for one collection round.

    ``proposed`` through ``labeled`` count candidate rows. ``selected`` and
    ``persisted`` count decision transitions, so no cross-unit inequality is
    inferred between ``labeled`` and ``selected``. ``rejected`` counts proposal
    tables that yield no transition because support is empty, labels are
    unavailable, or the episode terminates before selection.
    """

    proposed: int
    """All attempted candidate rows before hard validity."""

    valid: int
    """Hard-valid candidate rows presented to a selection policy."""

    queried: int
    """Candidate rows submitted to the hard oracle."""

    labeled: int
    """Candidate rows with admitted finite oracle labels."""

    selected: int
    """Decision transitions with one action selected from labeled support."""

    persisted: int
    """Transitions committed to the immutable shard."""

    rejected: int
    """Proposal tables rejected or terminated before an action is selected."""

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
        if self.valid > self.proposed:
            raise ValueError("Online Q_H round counts require valid <= proposed.")
        if self.queried > self.valid:
            raise ValueError("Online Q_H round counts require queried <= valid.")
        if self.labeled > self.queried:
            raise ValueError("Online Q_H round counts require labeled <= queried.")
        if self.persisted > self.selected:
            raise ValueError("Online Q_H round counts require persisted <= selected.")


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

    training_population_manifest_schema_version: str
    """Schema of the exact population manifest used by this round."""

    training_population_manifest_sha256: str
    """Content digest of the exact population manifest used by this round."""

    training_population_manifest_path: Path
    """Recorded path of the exact content-verified population manifest."""

    decision_cohort: Literal["oracle_upper_bound_v1", "deployment_v1"]
    """Explicit evaluation role of every decision in the promoted shard."""

    def __post_init__(self) -> None:
        hashes = (
            self.shard_manifest_sha256,
            self.behavior_bundle_manifest_sha256,
            self.proposal_policy_manifest_sha256,
            self.selected_action_policy_sha256,
            self.round_receipt_sha256,
            self.training_population_manifest_schema_version,
            self.training_population_manifest_sha256,
        )
        if any(not value for value in hashes):
            raise ValueError("Online Q_H round results require every shard, bundle, policy, and receipt hash.")
        if not _is_sha256(self.training_population_manifest_sha256):
            raise ValueError("Online Q_H round results require a valid training-population SHA-256 digest.")
        if self.oracle_query_policy_id != "dense_valid_v1":
            raise ValueError("Online Q_H MVP results require oracle_query_policy_id='dense_valid_v1'.")
        if self.decision_cohort not in {"oracle_upper_bound_v1", "deployment_v1"}:
            raise ValueError(f"Unsupported Online Q_H decision cohort {self.decision_cohort!r}.")


def _is_sha256(value: str) -> bool:
    """Return whether ``value`` is one lowercase or uppercase SHA-256 digest."""

    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


__all__ = [
    "OnlineQhPopulationManifestRef",
    "OnlineQhRoundCounts",
    "OnlineQhRoundRequest",
    "OnlineQhRoundResult",
]
