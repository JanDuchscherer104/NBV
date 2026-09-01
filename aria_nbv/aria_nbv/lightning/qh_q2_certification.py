r"""Bounded population certification for learned finite-horizon ``Q_2``.

This module evaluates a frozen scorer bundle against the factual dense-
successor two-step target already owned by
:meth:`aria_nbv.lightning.qh_module.QhLightningModule.compute_exact_q2_targets`.
It does not define another Bellman target, train a model, or perform endpoint
policy evaluation. Its narrow responsibility is to select a deterministic,
stratified, bounded subset of a frozen held-out corpus and quantify how closely
the learned recursive target

.. math::

   r_t + \gamma_t Q_{\bar\theta}(s_{t+1}, a^*, 1)

matches the factual finite-support control

.. math::

   r_t + \gamma_t \max_{a\in\mathcal A_{\mathrm{label}}(s_{t+1})}
   r_{t+1}(a).

The resulting error is model evidence: it measures the learned ``Q_1`` path
inside the recursion. Candidate and selected-action rows from one scene are
correlated observations, not independent replications. The certification
therefore aggregates the row ledger by
``(ordered_store_manifest_sha256, scene_id)`` and requires every selected unit
to pass. It is distinct from implementation-recursion parity, which injects an
exact one-step table and belongs in unit tests.
Positive oracle-lookahead headroom is also distinct and remains an
independently owned endpoint-policy prerequisite for claims above horizon two.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Literal, Protocol

import torch
from torch import Tensor

from ..data_handling.qh_data import QhBatch, QhChain, collate_qh_chains
from ..rollouts.qh_reader import QhRolloutChainIdentity
from .qh_module import QhLightningModule

QH_EXACT_Q2_CERTIFICATION_SCHEMA_VERSION = "qh-exact-q2-certification-v6"
QH_EXACT_Q2_SELECTION_SEMANTICS = "balanced-hash-within-scene-target-support-strata-v2"
QH_EXACT_Q2_INDEPENDENT_UNIT_SEMANTICS = "ordered-store-manifest-and-scene-v1"
QH_EXACT_Q2_INDEPENDENT_UNIT_AGGREGATION = "all_units_v1"
QH_CANDIDATE_BRANCH_BINS = (1, 4, 8, 16, 32, 64)
_FLOAT32_MAX = float(torch.finfo(torch.float32).max)


def _is_finite_float32(value: object) -> bool:
    """Return whether ``value`` can be represented as finite float32 evidence."""

    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and abs(value) <= _FLOAT32_MAX
    )


class _QhCertificationDataset(Protocol):
    """Small dataset seam required by :class:`QhExactQ2Certifier`."""

    def __len__(self) -> int: ...

    def __getitem__(self, index: int) -> QhChain: ...

    def chain_identity(self, index: int) -> QhRolloutChainIdentity: ...


@dataclass(frozen=True, slots=True)
class QhExactQ2CertificationSpec:
    """Frozen selection, support, and numeric gates for one certification run.

    Args:
        absolute_tolerance: Absolute fitted-target error admitted per exact
            ``Q_2`` row, in root-normalized return units.
        relative_tolerance: Additional tolerance proportional to the absolute
            exact target value. This is never used to divide near-zero targets.
        minimum_independent_units: Smallest number of selected scene-level
            units with exact evidence allowed to support promotion.
        minimum_exact_rows_per_independent_unit: Smallest exact factual
            selected-action support required within every selected unit.
        independent_unit_aggregation: Closed policy requiring every selected
            unit to pass its row support and numeric tolerances.
        minimum_population_coverage: Minimum fraction of census chains selected
            by the bounded stratified sampler. Coverage is over chain identity,
            not over unobserved eligible ``Q_2`` rows.
        max_selected_chains: Global materialization and scorer-call bound.
        max_chains_per_stratum: Per-stratum cap before balanced allocation.
        selection_seed: Integer mixed into deterministic identity hashes. It
            changes the selected evidence and is therefore receipt identity.
        positive_headroom_threshold: Minimum positive endpoint gain used only
            when summarizing the separately owned oracle-headroom diagnostic.
            It does not relax or tighten exact-``Q_2`` target agreement.

    Notes:
        The stratum freezes scene, target row, configured horizon, candidate-
        width bin, candidate generator, rollout recipe, and behavior policy.
        Candidate width is finite-table support; it is not a tree branch axis.
    """

    absolute_tolerance: float
    """Finite nonnegative absolute error allowance in additive return units."""

    relative_tolerance: float
    """Finite nonnegative allowance scaled by the absolute exact target."""

    minimum_independent_units: int
    """Required number of selected scene units with exact factual support."""

    minimum_exact_rows_per_independent_unit: int
    """Required factual selected-action exact rows within every selected unit."""

    independent_unit_aggregation: Literal["all_units_v1"]
    """Closed policy under which no pooled statistic may hide a failed unit."""

    minimum_population_coverage: float = 0.95
    """Minimum selected fraction of the metadata-visible chain population."""

    max_selected_chains: int = 4096
    """Global upper bound on chain materialization and scorer calls."""

    max_chains_per_stratum: int = 64
    """Per-stratum chain cap before balanced allocation."""

    selection_seed: int = 0
    """Seed mixed into deterministic chain-identity ranking."""

    positive_headroom_threshold: float = 1e-8
    """Separate oracle-headroom diagnostic threshold; never an error tolerance."""

    def __post_init__(self) -> None:
        """Reject meaningless or unbounded certification settings."""

        if not _is_finite_float32(self.absolute_tolerance) or self.absolute_tolerance < 0.0:
            raise ValueError("Q_H exact-Q2 absolute_tolerance must be finite and nonnegative.")
        if not _is_finite_float32(self.relative_tolerance) or self.relative_tolerance < 0.0:
            raise ValueError("Q_H exact-Q2 relative_tolerance must be finite and nonnegative.")
        if self.minimum_independent_units < 5:
            raise ValueError("Q_H exact-Q2 minimum_independent_units must be at least the frozen core floor of five.")
        if self.minimum_exact_rows_per_independent_unit < 1:
            raise ValueError("Q_H exact-Q2 minimum_exact_rows_per_independent_unit must be positive.")
        if self.independent_unit_aggregation != QH_EXACT_Q2_INDEPENDENT_UNIT_AGGREGATION:
            raise ValueError("Q_H exact-Q2 independent-unit aggregation is unsupported.")
        if not 0.0 < self.minimum_population_coverage <= 1.0:
            raise ValueError("Q_H exact-Q2 minimum_population_coverage must lie in (0, 1].")
        if self.max_selected_chains < 1 or self.max_chains_per_stratum < 1:
            raise ValueError("Q_H exact-Q2 chain-selection bounds must be positive.")
        if not math.isfinite(self.positive_headroom_threshold) or self.positive_headroom_threshold <= 0.0:
            raise ValueError("Q_H exact-Q2 positive_headroom_threshold must be finite and positive.")


@dataclass(frozen=True, slots=True)
class QhDecoderSupport:
    """Optional fixed scalar support exposed by an ordinal value decoder.

    Regression has no finite decoder support and passes ``None``. A CORAL
    caller supplies the lowest/highest class representatives and threshold
    edges so the receipt can distinguish decoded-value saturation from outer-
    class occupancy. These values diagnose support choice; they do not change
    Bellman targets or candidate ranking.
    """

    kind: str
    """Decoder family; V2 admits only ``"coral"`` on this finite-support path."""

    lower_representative: float
    """Lowest decoded continuous-Q representative."""

    upper_representative: float
    """Highest decoded continuous-Q representative."""

    lower_edge: float
    """Lowest ordinal label boundary."""

    upper_edge: float
    """Highest ordinal label boundary."""

    def __post_init__(self) -> None:
        values = (
            self.lower_representative,
            self.upper_representative,
            self.lower_edge,
            self.upper_edge,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Q_H decoder support values must be finite.")
        if self.kind != "coral":
            raise ValueError("Only the fixed-support CORAL decoder declares Q_H scalar support.")
        if self.lower_representative >= self.upper_representative:
            raise ValueError("Q_H decoder representatives must be strictly increasing.")
        if self.lower_edge > self.upper_edge:
            raise ValueError("Q_H decoder edge range must be ordered.")


class QhExactQ2Certifier:
    r"""Certify one frozen scorer against selected factual exact-``Q_2`` rows.

    The certifier first performs a metadata-only census through
    ``dataset.chain_identity``. It then materializes at most
    ``spec.max_selected_chains`` complete chains, preserving causal history and
    successor linkage while bounding actor-store and scorer work. Hard masks
    remain owned by :class:`QhLightningModule`; this class consumes its public
    admitted and exact-support tensors and never substitutes a learned
    feasibility decision.

    Theory:
        Rows within one scene share geometry, target-generation conditions,
        candidate policy, and rollout lineage. Treating them as independent
        would create pseudoreplication: increasing candidate or chain count
        could manufacture apparent evidence without increasing scene diversity.
        V2 therefore uses

        $$
        u=(\operatorname{sha256}(M_1,\ldots,M_K),\;\mathrm{scene\_id})
        $$

        as the independent unit, where the ordered manifest digest binds the
        complete store population. Row errors remain auditable, but promotion
        requires the predeclared minimum number of units and an ``all_units_v1``
        pass. Five units are a minimum diversity/admissibility floor, not a
        statistical-power or generalization guarantee.
    """

    def __init__(self, spec: QhExactQ2CertificationSpec) -> None:
        self.spec = spec

    def certify(
        self,
        *,
        module: QhLightningModule,
        dataset: _QhCertificationDataset,
        device: torch.device,
        ordered_store_manifest_sha256: str,
        decoder_support: QhDecoderSupport | None = None,
    ) -> dict[str, object]:
        """Return deterministic exact-``Q_2`` population evidence.

        Args:
            module: Frozen online/target scorer composition. The target copy
                must already contain the same selected bundle weights.
            dataset: Frozen held-out chain population with metadata-only chain
                identities and dense-valid fitted-Q supervision.
            device: Device used only for scorer and target computation.
            ordered_store_manifest_sha256: Digest of the ordered rollout-store
                manifest tuple bound by the evaluated bundle. Together with
                ``scene_id`` it defines one independent evidence unit.
            decoder_support: Fixed CORAL scalar support, or ``None`` for direct
                continuous regression.

        Returns:
            JSON-safe evidence containing population census, selected row
            ledger, per-stratum aggregates, tolerance results, and decoder-
            support diagnostics. ``learned_recursion_passed`` concerns the
            trained model; it is not an implementation-parity claim.

        Raises:
            ValueError: If corpus identity is incomplete, a materialized chain
                disagrees with its census identity, exact support escapes the
                learner's admitted support, or numeric evidence is non-finite.
        """

        _validate_sha256(ordered_store_manifest_sha256, name="ordered_store_manifest_sha256")
        identities = [dataset.chain_identity(index) for index in range(len(dataset))]
        selected, census = self._select(identities)
        census.update(_population_denominators(identities, ordered_store_manifest_sha256))
        module = module.to(device).eval()
        rows: list[dict[str, object]] = []
        selected_chain_support: list[dict[str, object]] = []
        with torch.inference_mode():
            for selection_rank, (index, identity) in enumerate(selected):
                chain = dataset[index]
                _validate_materialized_identity(chain, identity)
                batch = collate_qh_chains(
                    [chain],
                    objective_profile="qh_dense_valid_fitted_q_v1",
                ).to(device)
                _loss, recursive_targets, admitted = module.compute_fitted_q_loss(batch)
                exact_targets, exact_support = module.compute_exact_q2_targets(batch)
                if bool((exact_support & ~admitted).any()):
                    raise ValueError("Q_H exact-Q2 support must be a subset of fitted-Q admission.")
                step_indices = torch.nonzero(exact_support[0], as_tuple=False).flatten()
                chain_denominators = _chain_denominators(batch, exact_support)
                selected_chain_support.append(
                    {
                        "selection_rank": selection_rank,
                        "dataset_index": index,
                        "identity": asdict(identity),
                        "independent_unit": _independent_unit(
                            ordered_store_manifest_sha256,
                            identity.scene_id,
                        ),
                        **chain_denominators,
                    }
                )
                rows.extend(
                    self._row_evidence(
                        batch=batch,
                        identity=identity,
                        dataset_index=index,
                        selection_rank=selection_rank,
                        step_indices=step_indices,
                        recursive_targets=recursive_targets,
                        exact_targets=exact_targets,
                        ordered_store_manifest_sha256=ordered_store_manifest_sha256,
                    )
                )

        aggregate = _aggregate_rows(rows, minimum_rows=1)
        coverage_passed = float(census["selected_chain_fraction"]) >= self.spec.minimum_population_coverage
        decoder = _decoder_support_evidence(rows, decoder_support)
        support_strata = _support_stratum_aggregates(selected_chain_support)
        support_coverage_passed = all(
            int(row["factual_selected_action_exact_q2_row_count"]) > 0 for row in support_strata
        )
        independent_units = _independent_unit_aggregates(
            identities=identities,
            selected_chain_support=selected_chain_support,
            rows=rows,
            ordered_store_manifest_sha256=ordered_store_manifest_sha256,
            minimum_rows=self.spec.minimum_exact_rows_per_independent_unit,
        )
        independent_unit_gate = _independent_unit_gate(independent_units, self.spec)
        return {
            "schema_version": QH_EXACT_Q2_CERTIFICATION_SCHEMA_VERSION,
            "evidence_semantics": {
                "quantity": "learned_recursive_q2_target_error_against_factual_dense_successor_control",
                "implementation_recursion_parity": False,
                "endpoint_policy_evidence": False,
                "longer_horizon_claim": False,
            },
            "spec": asdict(self.spec),
            "population_census": census,
            "selection_coverage_passed": coverage_passed,
            "selected_chain_support": selected_chain_support,
            "evidence_denominators": _sum_chain_denominators(selected_chain_support),
            "support_stratum_aggregates": support_strata,
            "support_coverage_passed": support_coverage_passed,
            "factual_selected_action_exact_q2_rows": rows,
            "aggregate": aggregate,
            "stratum_aggregates": _stratum_aggregates(rows),
            "independent_unit_aggregates": independent_units,
            "independent_unit_gate": independent_unit_gate,
            "decoder_support": decoder,
            "learned_recursion_passed": bool(
                coverage_passed
                and support_coverage_passed
                and aggregate["tolerance_passed"]
                and independent_unit_gate["passed"]
            ),
        }

    def _select(
        self,
        identities: list[QhRolloutChainIdentity],
    ) -> tuple[list[tuple[int, QhRolloutChainIdentity]], dict[str, object]]:
        """Select balanced deterministic identities within closed strata."""

        if not identities:
            raise ValueError("Q_H exact-Q2 certification requires a non-empty held-out population.")
        grouped: dict[str, list[tuple[str, int, QhRolloutChainIdentity]]] = defaultdict(list)
        seen: set[tuple[int, int]] = set()
        for index, identity in enumerate(identities):
            _validate_identity(identity)
            key = (identity.store_index, identity.rollout_row_id)
            if key in seen:
                raise ValueError(f"Q_H exact-Q2 population repeats rollout identity {key}.")
            seen.add(key)
            stratum = _selection_stratum(identity)
            stratum_key = _canonical_json(stratum)
            rank_hash = hashlib.sha256(
                _canonical_json(
                    {
                        "selection_seed": self.spec.selection_seed,
                        "identity": asdict(identity),
                    }
                ).encode("utf-8")
            ).hexdigest()
            grouped[stratum_key].append((rank_hash, index, identity))

        capped = {key: sorted(values)[: self.spec.max_chains_per_stratum] for key, values in sorted(grouped.items())}
        allocated: list[tuple[int, QhRolloutChainIdentity]] = []
        selected_scenes: set[str] = set()
        depth = 0
        while len(allocated) < self.spec.max_selected_chains:
            wave: list[tuple[int, QhRolloutChainIdentity]] = []
            for key in sorted(capped):
                values = capped[key]
                if depth >= len(values):
                    continue
                _rank_hash, index, identity = values[depth]
                wave.append((index, identity))
            if not wave:
                break
            deferred: list[tuple[int, QhRolloutChainIdentity]] = []
            for index, identity in wave:
                if identity.scene_id in selected_scenes:
                    deferred.append((index, identity))
                    continue
                allocated.append((index, identity))
                selected_scenes.add(identity.scene_id)
                if len(allocated) == self.spec.max_selected_chains:
                    break
            if len(allocated) < self.spec.max_selected_chains:
                for index, identity in deferred:
                    allocated.append((index, identity))
                    if len(allocated) == self.spec.max_selected_chains:
                        break
            depth += 1
        selected_keys = {(identity.store_index, identity.rollout_row_id) for _index, identity in allocated}
        stratum_rows: list[dict[str, object]] = []
        for key, values in sorted(grouped.items()):
            selected_count = sum(
                (identity.store_index, identity.rollout_row_id) in selected_keys for _rank, _index, identity in values
            )
            stratum_rows.append(
                {
                    "stratum": json.loads(key),
                    "population_chain_count": len(values),
                    "selected_chain_count": selected_count,
                    "selected_chain_fraction": selected_count / len(values),
                }
            )
        selected_fraction = len(allocated) / len(identities)
        census = {
            "selection_semantics": QH_EXACT_Q2_SELECTION_SEMANTICS,
            "candidate_branch_bins": list(QH_CANDIDATE_BRANCH_BINS),
            "chains": [
                {
                    "dataset_index": index,
                    "identity": asdict(identity),
                }
                for index, identity in enumerate(identities)
            ],
            "population_chain_count": len(identities),
            "selected_chain_count": len(allocated),
            "selected_chain_fraction": selected_fraction,
            "near_exhaustive": len(allocated) == len(identities),
            "strata": stratum_rows,
        }
        return sorted(allocated), census

    def _row_evidence(
        self,
        *,
        batch: QhBatch,
        identity: QhRolloutChainIdentity,
        dataset_index: int,
        selection_rank: int,
        step_indices: Tensor,
        recursive_targets: Tensor,
        exact_targets: Tensor,
        ordered_store_manifest_sha256: str,
    ) -> list[dict[str, object]]:
        """Materialize finite row-level error and support evidence."""

        # QhBatch is kept structural here so the public module remains the only
        # target owner; these attributes are its typed batching contract.
        actor = batch.actor
        supervision = batch.supervision
        successor_action_mask = batch.successor_action_mask
        successor_backup_mask = batch.successor_backup_mask
        output: list[dict[str, object]] = []
        for step_tensor in step_indices:
            step = int(step_tensor.item())
            recursive = float(recursive_targets[0, step].item())
            exact = float(exact_targets[0, step].item())
            if not _is_finite_float32(recursive) or not _is_finite_float32(exact):
                raise ValueError("Q_H exact-Q2 certification encountered a non-finite target.")
            absolute_error = abs(recursive - exact)
            tolerance = self.spec.absolute_tolerance + self.spec.relative_tolerance * abs(exact)
            relative_error = absolute_error / max(abs(exact), torch.finfo(torch.float32).eps)
            if not all(_is_finite_float32(value) for value in (absolute_error, tolerance, relative_error)):
                raise ValueError("Q_H exact-Q2 error evidence must remain within the finite float32 domain.")
            current_width = int(actor.candidate_mask[0, step].sum().item())
            successor_action = successor_action_mask[0, step]
            successor_backup = successor_backup_mask[0, step]
            successor_action_width = int(successor_action.sum().item())
            successor_width = int(successor_backup.sum().item())
            selected_index = int(supervision.selected_index[0, step].item())
            current_action = actor.action_mask[0, step]
            current_label = supervision.label_mask[0, step]
            current_backup = current_action & current_label
            current_action_width = int(current_action.sum().item())
            current_label_width = int(current_label.sum().item())
            current_backup_width = int(current_backup.sum().item())
            current_indices = torch.nonzero(current_backup, as_tuple=False).flatten().tolist()
            if (
                current_action_width < 1
                or not torch.equal(current_backup, current_action)
                or selected_index < 0
                or selected_index >= current_width
                or not bool(current_backup[selected_index].item())
                or current_indices != sorted(set(current_indices))
            ):
                raise ValueError("Q_H exact-Q2 selected action must have complete hard-valid current-state support.")
            current_reward_ledger = [
                {
                    "candidate_index": index,
                    "reward": float(supervision.candidate_reward[0, step, index].item()),
                }
                for index in current_indices
            ]
            if len(current_reward_ledger) != current_backup_width or not all(
                _is_finite_float32(entry["reward"]) for entry in current_reward_ledger
            ):
                raise ValueError("Q_H exact-Q2 current reward ledger must contain finite float32 evidence.")
            immediate_reward = float(
                next(entry["reward"] for entry in current_reward_ledger if entry["candidate_index"] == selected_index)
            )
            discount = float(supervision.discount[0, step].item())
            terminal = bool(supervision.terminal[0, step].item())
            if terminal or step + 1 >= supervision.candidate_reward.shape[1]:
                raise ValueError("Q_H exact-Q2 row must have a factual nonterminal successor state.")
            successor_candidate_count = int(actor.candidate_mask[0, step + 1].sum().item())
            if not (
                identity.candidate_width_min <= current_width <= identity.candidate_width_max
                and identity.candidate_width_min <= successor_candidate_count <= identity.candidate_width_max
            ):
                raise ValueError("Q_H exact-Q2 materialized width is outside the declared candidate-width range.")
            if successor_action_width < 1 or not torch.equal(successor_backup, successor_action):
                raise ValueError("Q_H exact-Q2 row must bind every hard-valid successor reward.")
            successor_indices = torch.nonzero(successor_backup, as_tuple=False).flatten().tolist()
            if (
                len(successor_indices) != successor_width
                or successor_indices != sorted(set(successor_indices))
                or any(index < 0 or index >= successor_candidate_count for index in successor_indices)
            ):
                raise ValueError("Q_H exact-Q2 successor reward count is inconsistent with its support mask.")
            successor_reward_ledger = [
                {
                    "candidate_index": index,
                    "reward": float(supervision.candidate_reward[0, step + 1, index].item()),
                }
                for index in successor_indices
            ]
            if len(successor_reward_ledger) != successor_action_width or not all(
                _is_finite_float32(entry["reward"]) for entry in successor_reward_ledger
            ):
                raise ValueError("Q_H exact-Q2 successor reward ledger must contain finite float32 evidence.")
            successor_max_reward = max(float(entry["reward"]) for entry in successor_reward_ledger)
            transition_values = (immediate_reward, discount, successor_max_reward)
            if not all(_is_finite_float32(value) for value in transition_values) or discount < 0.0:
                raise ValueError("Q_H exact-Q2 transition evidence must be finite with nonnegative discount.")
            discounted_successor = discount * successor_max_reward
            derived_exact = immediate_reward + discounted_successor
            identity_scale = max(1.0, abs(immediate_reward), abs(discounted_successor), abs(exact))
            identity_tolerance = 8.0 * torch.finfo(torch.float32).eps * identity_scale
            transition_derivatives = (discounted_successor, derived_exact, identity_scale, identity_tolerance)
            if not all(_is_finite_float32(value) for value in transition_derivatives):
                raise ValueError("Q_H exact-Q2 transition arithmetic must remain within the finite float32 domain.")
            if abs(exact - derived_exact) > identity_tolerance:
                raise ValueError("Q_H exact-Q2 target is inconsistent with its factual transition evidence.")
            output.append(
                {
                    "dataset_index": dataset_index,
                    "selection_rank": selection_rank,
                    "store_index": identity.store_index,
                    "rollout_row_id": identity.rollout_row_id,
                    "source_sample_index": identity.source_sample_index,
                    "scene_id": identity.scene_id,
                    "ordered_store_manifest_sha256": ordered_store_manifest_sha256,
                    "independent_unit": _independent_unit(
                        ordered_store_manifest_sha256,
                        identity.scene_id,
                    ),
                    "target_row_id": identity.target_row_id,
                    "step_index": step,
                    "configured_horizon": identity.configured_horizon,
                    "requested_horizon": 2,
                    "candidate_config_hash": identity.candidate_config_hash,
                    "rollout_config_hash": identity.rollout_config_hash,
                    "selection_policy": identity.selection_policy,
                    "current_candidate_count": current_width,
                    "current_action_count": current_action_width,
                    "current_label_count": current_label_width,
                    "current_backup_count": current_backup_width,
                    "current_reward_ledger": current_reward_ledger,
                    "successor_action_count": successor_action_width,
                    "successor_candidate_count": successor_candidate_count,
                    "successor_backup_count": successor_width,
                    "candidate_branch_bin": _candidate_branch_bin(successor_width),
                    "selected_index": selected_index,
                    "immediate_reward": immediate_reward,
                    "discount": discount,
                    "terminal": terminal,
                    "successor_reward_ledger": successor_reward_ledger,
                    "successor_max_reward": successor_max_reward,
                    "recursive_target": recursive,
                    "exact_target": exact,
                    "absolute_error": absolute_error,
                    "relative_error": relative_error,
                    "tolerance": tolerance,
                    "within_tolerance": absolute_error <= tolerance,
                }
            )
        return output


def _validate_identity(identity: QhRolloutChainIdentity) -> None:
    """Require complete row-level generation identity before selection."""

    if identity.store_index < 0 or identity.rollout_row_id < 0 or identity.source_sample_index < 0:
        raise ValueError("Q_H exact-Q2 chain integer identities must be nonnegative.")
    if identity.target_row_id < 0 or identity.configured_horizon < 1:
        raise ValueError("Q_H exact-Q2 target identity and configured horizon must be valid.")
    if identity.candidate_width_min < 1 or identity.candidate_width_max < identity.candidate_width_min:
        raise ValueError("Q_H exact-Q2 candidate-width identity is invalid.")
    named = {
        "scene_id": identity.scene_id,
        "candidate_config_hash": identity.candidate_config_hash,
        "rollout_config_hash": identity.rollout_config_hash,
        "selection_policy": identity.selection_policy,
    }
    missing = [name for name, value in named.items() if not value]
    if missing:
        raise ValueError(f"Q_H exact-Q2 chain identity is missing {', '.join(missing)}.")


def _validate_materialized_identity(chain: QhChain, identity: QhRolloutChainIdentity) -> None:
    """Reject census/materialization drift before scorer evaluation."""

    key = chain.key
    actual = {
        "store_index": key.store_index,
        "rollout_row_id": key.rollout_row_id,
        "source_sample_index": key.source_sample_index,
        "scene_id": key.scene_id,
        "target_row_id": key.target_row_id,
        "configured_horizon": key.configured_horizon,
        "candidate_width_min": key.candidate_width_min,
        "candidate_width_max": key.candidate_width_max,
        "candidate_config_hash": key.candidate_config_hash,
        "rollout_config_hash": key.rollout_config_hash,
        "selection_policy": key.selection_policy,
    }
    if actual != asdict(identity):
        raise ValueError("Q_H exact-Q2 materialized chain identity drifted after population census.")


def _validate_sha256(value: str, *, name: str) -> None:
    """Require one lowercase hexadecimal SHA-256 identity."""

    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"Q_H exact-Q2 {name} must be a lowercase SHA-256 digest.")


def _independent_unit(ordered_store_manifest_sha256: str, scene_id: str) -> dict[str, str]:
    """Return the frozen scene-level independent-unit identity."""

    return {
        "ordered_store_manifest_sha256": ordered_store_manifest_sha256,
        "scene_id": scene_id,
    }


def _population_denominators(
    identities: list[QhRolloutChainIdentity],
    ordered_store_manifest_sha256: str,
) -> dict[str, int | str]:
    """Count metadata-visible corpus units without materializing scorer inputs."""

    scenes = {identity.scene_id for identity in identities}
    targets = {(ordered_store_manifest_sha256, identity.scene_id, identity.target_row_id) for identity in identities}
    return {
        "eligible_scene_count": len(scenes),
        "eligible_target_count": len(targets),
        "eligible_chain_count": len(identities),
        "independent_unit_count": len(scenes),
        "independent_unit_semantics": QH_EXACT_Q2_INDEPENDENT_UNIT_SEMANTICS,
    }


def _chain_denominators(batch: QhBatch, exact_support: Tensor) -> dict[str, int]:
    """Count the factual state-to-exact-row support ladder for one chain."""

    materialized_successor = torch.zeros_like(batch.actor.step_mask)
    materialized_successor[:, :-1] = batch.actor.candidate_mask[:, 1:].any(dim=-1) & batch.actor.step_mask[:, 1:]
    successor_action_mask = batch.successor_action_mask
    complete_successor_labels = successor_action_mask.any(dim=-1) & torch.eq(
        batch.successor_backup_mask,
        successor_action_mask,
    ).all(dim=-1)
    return {
        "factual_state_count": int(batch.actor.step_mask.sum().item()),
        "states_with_materialized_successors_count": int(materialized_successor.sum().item()),
        "states_with_complete_hard_valid_successor_labels_count": int(complete_successor_labels.sum().item()),
        "factual_selected_action_exact_q2_row_count": int(exact_support.sum().item()),
    }


def _sum_chain_denominators(rows: list[dict[str, object]]) -> dict[str, int]:
    """Sum selected-chain support without fabricating missing population states."""

    fields = (
        "factual_state_count",
        "states_with_materialized_successors_count",
        "states_with_complete_hard_valid_successor_labels_count",
        "factual_selected_action_exact_q2_row_count",
    )
    return {field: sum(int(row[field]) for row in rows) for field in fields}


def _independent_unit_aggregates(
    *,
    identities: list[QhRolloutChainIdentity],
    selected_chain_support: list[dict[str, object]],
    rows: list[dict[str, object]],
    ordered_store_manifest_sha256: str,
    minimum_rows: int,
) -> list[dict[str, object]]:
    """Aggregate selected evidence over every metadata-visible scene unit."""

    population: dict[str, list[QhRolloutChainIdentity]] = defaultdict(list)
    selected: dict[str, list[dict[str, object]]] = defaultdict(list)
    exact: dict[str, list[dict[str, object]]] = defaultdict(list)
    for identity in identities:
        unit = _independent_unit(ordered_store_manifest_sha256, identity.scene_id)
        population[_canonical_json(unit)].append(identity)
    for row in selected_chain_support:
        selected[_canonical_json(row["independent_unit"])].append(row)
    for row in rows:
        exact[_canonical_json(row["independent_unit"])].append(row)

    aggregates: list[dict[str, object]] = []
    for key, population_rows in sorted(population.items()):
        selected_rows = selected.get(key, [])
        exact_rows = exact.get(key, [])
        error = _aggregate_rows(exact_rows, minimum_rows=minimum_rows)
        admitted = bool(selected_rows)
        aggregates.append(
            {
                "independent_unit": json.loads(key),
                "population_chain_count": len(population_rows),
                "selected_chain_count": len(selected_rows),
                "admitted": admitted,
                **_sum_chain_denominators(selected_rows),
                "error": error,
                "unit_gate_passed": bool(admitted and error["tolerance_passed"]),
            }
        )
    return aggregates


def _independent_unit_gate(
    aggregates: list[dict[str, object]],
    spec: QhExactQ2CertificationSpec,
) -> dict[str, object]:
    """Apply the frozen all-selected-units promotion policy."""

    selected = [row for row in aggregates if bool(row["admitted"])]
    supported = [
        row
        for row in selected
        if int(row["factual_selected_action_exact_q2_row_count"]) >= spec.minimum_exact_rows_per_independent_unit
    ]
    passing = [row for row in selected if bool(row["unit_gate_passed"])]
    minimum_met = len(supported) >= spec.minimum_independent_units
    all_selected_passed = bool(selected) and len(passing) == len(selected)
    return {
        "independent_unit_semantics": QH_EXACT_Q2_INDEPENDENT_UNIT_SEMANTICS,
        "aggregation": spec.independent_unit_aggregation,
        "population_independent_unit_count": len(aggregates),
        "selected_independent_unit_count": len(selected),
        "supported_independent_unit_count": len(supported),
        "passing_independent_unit_count": len(passing),
        "minimum_independent_units": spec.minimum_independent_units,
        "minimum_exact_rows_per_independent_unit": spec.minimum_exact_rows_per_independent_unit,
        "minimum_independent_units_met": minimum_met,
        "all_selected_units_passed": all_selected_passed,
        "passed": bool(minimum_met and all_selected_passed),
    }


def _selection_stratum(identity: QhRolloutChainIdentity) -> dict[str, object]:
    """Return the versioned census stratum for one chain."""

    return {
        "scene_id": identity.scene_id,
        "store_index": identity.store_index,
        "target_row_id": identity.target_row_id,
        "configured_horizon": identity.configured_horizon,
        "candidate_branch_bin": _candidate_branch_bin(identity.candidate_width_max),
        "candidate_config_hash": identity.candidate_config_hash,
        "rollout_config_hash": identity.rollout_config_hash,
        "selection_policy": identity.selection_policy,
    }


def _candidate_branch_bin(width: int) -> str:
    """Map one positive finite-candidate width to a stable coarse bin."""

    if width < 1:
        raise ValueError("Q_H candidate branch width must be positive.")
    lower = 1
    for upper in QH_CANDIDATE_BRANCH_BINS:
        if width <= upper:
            return str(upper) if lower == upper else f"{lower}-{upper}"
        lower = upper + 1
    return f"{lower}+"


def _aggregate_rows(rows: list[dict[str, object]], *, minimum_rows: int) -> dict[str, object]:
    """Summarize learned-recursion error without hiding missing support."""

    if not rows:
        return {
            "factual_selected_action_exact_q2_row_count": 0,
            "within_tolerance_count": 0,
            "within_tolerance_fraction": None,
            "mean_absolute_error": None,
            "root_mean_squared_error": None,
            "max_absolute_error": None,
            "max_relative_error": None,
            "minimum_support_met": False,
            "tolerance_passed": False,
        }
    absolute = [float(row["absolute_error"]) for row in rows]
    relative = [float(row["relative_error"]) for row in rows]
    passed = sum(bool(row["within_tolerance"]) for row in rows)
    support_met = len(rows) >= minimum_rows
    return {
        "factual_selected_action_exact_q2_row_count": len(rows),
        "within_tolerance_count": passed,
        "within_tolerance_fraction": passed / len(rows),
        "mean_absolute_error": sum(absolute) / len(absolute),
        "root_mean_squared_error": math.sqrt(sum(value * value for value in absolute) / len(absolute)),
        "max_absolute_error": max(absolute),
        "max_relative_error": max(relative),
        "minimum_support_met": support_met,
        "tolerance_passed": support_met and passed == len(rows),
    }


def _stratum_aggregates(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Report errors for every observed scene/target/branch/support stratum."""

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        stratum = {
            field: row[field]
            for field in (
                "scene_id",
                "store_index",
                "target_row_id",
                "candidate_branch_bin",
                "candidate_config_hash",
                "rollout_config_hash",
                "selection_policy",
                "configured_horizon",
            )
        }
        grouped[_canonical_json(stratum)].append(row)
    return [
        {
            "stratum": json.loads(key),
            **_aggregate_rows(values, minimum_rows=1),
        }
        for key, values in sorted(grouped.items())
    ]


def _support_stratum_aggregates(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Retain selected strata even when they expose no exact-``Q_2`` row."""

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        identity = QhRolloutChainIdentity(**row["identity"])
        grouped[_canonical_json(_selection_stratum(identity))].append(row)
    return [
        {
            "stratum": json.loads(key),
            "selected_chain_count": len(values),
            "chains_with_factual_selected_action_exact_q2_count": sum(
                int(row["factual_selected_action_exact_q2_row_count"]) > 0 for row in values
            ),
            "factual_selected_action_exact_q2_row_count": sum(
                int(row["factual_selected_action_exact_q2_row_count"]) for row in values
            ),
        }
        for key, values in sorted(grouped.items())
    ]


def _decoder_support_evidence(
    rows: list[dict[str, object]],
    support: QhDecoderSupport | None,
) -> dict[str, object]:
    """Separate fixed-support CORAL saturation from recursion error."""

    if support is None:
        return {"applicable": False, "kind": "regression"}
    exact = [float(row["exact_target"]) for row in rows]
    below = sum(value < support.lower_representative for value in exact)
    above = sum(value > support.upper_representative for value in exact)
    lower_outer = sum(value <= support.lower_edge for value in exact)
    upper_outer = sum(value > support.upper_edge for value in exact)
    count = len(exact)
    return {
        "applicable": True,
        **asdict(support),
        "factual_selected_action_exact_q2_row_count": count,
        "below_representative_count": below,
        "above_representative_count": above,
        "outside_representative_fraction": None if count == 0 else (below + above) / count,
        "lower_outer_class_count": lower_outer,
        "upper_outer_class_count": upper_outer,
        "outer_class_fraction": None if count == 0 else (lower_outer + upper_outer) / count,
    }


def _canonical_json(value: object) -> str:
    """Encode deterministic JSON used by strata and selection hashes."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


__all__ = [
    "QH_EXACT_Q2_CERTIFICATION_SCHEMA_VERSION",
    "QH_EXACT_Q2_INDEPENDENT_UNIT_AGGREGATION",
    "QH_EXACT_Q2_INDEPENDENT_UNIT_SEMANTICS",
    "QH_EXACT_Q2_SELECTION_SEMANTICS",
    "QhDecoderSupport",
    "QhExactQ2CertificationSpec",
    "QhExactQ2Certifier",
]
