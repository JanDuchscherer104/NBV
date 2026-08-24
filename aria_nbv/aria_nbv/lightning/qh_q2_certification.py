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
inside the recursion. It is distinct from implementation-recursion parity,
which injects an exact one-step table and belongs in unit tests. Positive
oracle-lookahead headroom is also distinct and remains an independently owned
endpoint-policy prerequisite for claims about horizons above two.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Protocol

import torch
from torch import Tensor

from ..data_handling.qh_data import QhBatch, QhChain, collate_qh_chains
from ..rollouts.qh_reader import QhRolloutChainIdentity
from .qh_module import QhLightningModule

QH_EXACT_Q2_CERTIFICATION_SCHEMA_VERSION = "qh-exact-q2-certification-v1"
QH_EXACT_Q2_SELECTION_SEMANTICS = "balanced-hash-within-scene-target-support-strata-v1"
QH_CANDIDATE_BRANCH_BINS = (1, 4, 8, 16, 32, 64)


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
        minimum_exact_q2_rows: Smallest selected held-out support on which a
            learned-recursion conclusion is allowed.
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
    relative_tolerance: float
    minimum_exact_q2_rows: int = 1
    minimum_population_coverage: float = 0.95
    max_selected_chains: int = 4096
    max_chains_per_stratum: int = 64
    selection_seed: int = 0
    positive_headroom_threshold: float = 1e-8

    def __post_init__(self) -> None:
        """Reject meaningless or unbounded certification settings."""

        if not math.isfinite(self.absolute_tolerance) or self.absolute_tolerance < 0.0:
            raise ValueError("Q_H exact-Q2 absolute_tolerance must be finite and nonnegative.")
        if not math.isfinite(self.relative_tolerance) or self.relative_tolerance < 0.0:
            raise ValueError("Q_H exact-Q2 relative_tolerance must be finite and nonnegative.")
        if self.minimum_exact_q2_rows < 1:
            raise ValueError("Q_H exact-Q2 minimum_exact_q2_rows must be positive.")
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
    lower_representative: float
    upper_representative: float
    lower_edge: float
    upper_edge: float

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
    """Certify one frozen scorer against selected factual exact-``Q_2`` rows.

    The certifier first performs a metadata-only census through
    ``dataset.chain_identity``. It then materializes at most
    ``spec.max_selected_chains`` complete chains, preserving causal history and
    successor linkage while bounding actor-store and scorer work. Hard masks
    remain owned by :class:`QhLightningModule`; this class consumes its public
    admitted and exact-support tensors and never substitutes a learned
    feasibility decision.
    """

    def __init__(self, spec: QhExactQ2CertificationSpec) -> None:
        self.spec = spec

    def certify(
        self,
        *,
        module: QhLightningModule,
        dataset: _QhCertificationDataset,
        device: torch.device,
        decoder_support: QhDecoderSupport | None = None,
    ) -> dict[str, object]:
        """Return deterministic exact-``Q_2`` population evidence.

        Args:
            module: Frozen online/target scorer composition. The target copy
                must already contain the same selected bundle weights.
            dataset: Frozen held-out chain population with metadata-only chain
                identities and dense-valid fitted-Q supervision.
            device: Device used only for scorer and target computation.
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

        identities = [dataset.chain_identity(index) for index in range(len(dataset))]
        selected, census = self._select(identities)
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
                selected_chain_support.append(
                    {
                        "selection_rank": selection_rank,
                        "dataset_index": index,
                        "identity": asdict(identity),
                        "exact_q2_row_count": int(step_indices.numel()),
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
                    )
                )

        aggregate = _aggregate_rows(rows, minimum_rows=self.spec.minimum_exact_q2_rows)
        coverage_passed = float(census["selected_chain_fraction"]) >= self.spec.minimum_population_coverage
        decoder = _decoder_support_evidence(rows, decoder_support)
        support_strata = _support_stratum_aggregates(selected_chain_support)
        support_coverage_passed = all(int(row["exact_q2_row_count"]) > 0 for row in support_strata)
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
            "support_stratum_aggregates": support_strata,
            "support_coverage_passed": support_coverage_passed,
            "exact_q2_rows": rows,
            "aggregate": aggregate,
            "stratum_aggregates": _stratum_aggregates(rows),
            "decoder_support": decoder,
            "learned_recursion_passed": bool(
                coverage_passed and support_coverage_passed and aggregate["tolerance_passed"]
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
        depth = 0
        while len(allocated) < self.spec.max_selected_chains:
            added = False
            for key in sorted(capped):
                values = capped[key]
                if depth >= len(values):
                    continue
                _rank_hash, index, identity = values[depth]
                allocated.append((index, identity))
                added = True
                if len(allocated) == self.spec.max_selected_chains:
                    break
            if not added:
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
    ) -> list[dict[str, object]]:
        """Materialize finite row-level error and support evidence."""

        # QhBatch is kept structural here so the public module remains the only
        # target owner; these attributes are its typed batching contract.
        actor = batch.actor
        supervision = batch.supervision
        successor_backup_mask = batch.successor_backup_mask
        output: list[dict[str, object]] = []
        for step_tensor in step_indices:
            step = int(step_tensor.item())
            recursive = float(recursive_targets[0, step].item())
            exact = float(exact_targets[0, step].item())
            if not math.isfinite(recursive) or not math.isfinite(exact):
                raise ValueError("Q_H exact-Q2 certification encountered a non-finite target.")
            absolute_error = abs(recursive - exact)
            tolerance = self.spec.absolute_tolerance + self.spec.relative_tolerance * abs(exact)
            relative_error = absolute_error / max(abs(exact), torch.finfo(torch.float32).eps)
            current_width = int(actor.candidate_mask[0, step].sum().item())
            successor_width = int(successor_backup_mask[0, step].sum().item())
            selected_index = int(supervision.selected_index[0, step].item())
            immediate_reward = float(supervision.candidate_reward[0, step, selected_index].item())
            discount = float(supervision.discount[0, step].item())
            output.append(
                {
                    "dataset_index": dataset_index,
                    "selection_rank": selection_rank,
                    "store_index": identity.store_index,
                    "rollout_row_id": identity.rollout_row_id,
                    "source_sample_index": identity.source_sample_index,
                    "scene_id": identity.scene_id,
                    "target_row_id": identity.target_row_id,
                    "step_index": step,
                    "configured_horizon": identity.configured_horizon,
                    "requested_horizon": 2,
                    "candidate_config_hash": identity.candidate_config_hash,
                    "rollout_config_hash": identity.rollout_config_hash,
                    "selection_policy": identity.selection_policy,
                    "current_candidate_count": current_width,
                    "successor_backup_count": successor_width,
                    "candidate_branch_bin": _candidate_branch_bin(successor_width),
                    "selected_index": selected_index,
                    "immediate_reward": immediate_reward,
                    "discount": discount,
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
            "exact_q2_row_count": 0,
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
        "exact_q2_row_count": len(rows),
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
            "chains_with_exact_q2_count": sum(int(row["exact_q2_row_count"]) > 0 for row in values),
            "exact_q2_row_count": sum(int(row["exact_q2_row_count"]) for row in values),
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
        "exact_q2_row_count": count,
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
    "QhDecoderSupport",
    "QhExactQ2CertificationSpec",
    "QhExactQ2Certifier",
]
