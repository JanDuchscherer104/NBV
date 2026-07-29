r"""Deterministic scientific-audit artifacts for stored rollout evidence.

This module owns the strict JSON side artifact that connects an independently
evaluated endpoint/validity audit to :mod:`aria_nbv.rollouts.inspection`. It
does not read or modify rollout Zarr stores and does not evaluate geometry.

Endpoint gain is recorded as

$$
J = \frac{\Delta_0 - \Delta_H}{\Delta_0 + \epsilon},
$$

where the errors come from an evaluator that reopens immutable source assets.
Comparator equivalence is a separate contract using the persisted root-gain
normalization

$$
G_H^{\mathrm{ind}} =
\frac{\Delta_0-\Delta_H}{\max(\Delta_0,10^{-12})},
$$

and comparing it to the persisted cumulative target-root gain.
Validity sampling uses deterministic hash priority within predeclared strata.
For stratum $h$, the artifact records population size $N_h$, audit size $n_h$,
inclusion probability $\pi_h=n_h/N_h$, and inverse-probability weight
$w_h=1/\pi_h$. These quantities characterize the audit design; candidate rows
are not independent scientific replicates.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from copy import deepcopy
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    StringConstraints,
    field_validator,
    model_validator,
)

SCIENTIFIC_AUDIT_SCHEMA_VERSION: Literal["stored-rollout-scientific-audit-v1"] = "stored-rollout-scientific-audit-v1"
SCIENTIFIC_AUDIT_ARTIFACT_ROLE: Literal["stored_rollout_scientific_audit"] = "stored_rollout_scientific_audit"
MIN_SCENES_FOR_CLUSTER_CI: Literal[20] = 20

Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]
PositiveFiniteFloat = Annotated[FiniteFloat, Field(gt=0.0)]
NonNegativeFiniteFloat = Annotated[FiniteFloat, Field(ge=0.0)]
Probability = Annotated[FiniteFloat, Field(gt=0.0, le=1.0)]


class AuditStatus(StrEnum):
    """Completeness and mandatory-gate status of one sealed audit."""

    PASS = "pass"
    FAIL = "fail"
    CHARACTERIZATION = "characterization"
    PARTIAL = "partial"


class AuditReadiness(StrEnum):
    """Permitted evidence use derived exactly from :class:`AuditStatus`."""

    CONFIRMATORY = "confirmatory"
    PILOT = "pilot"
    BLOCKED = "blocked"


class RowEvaluationStatus(StrEnum):
    """Whether an independently sampled row received a complete evaluation."""

    COMPLETE = "complete"
    BLOCKED = "blocked"


class EquivalenceVerdict(StrEnum):
    """Endpoint-comparator verdict under the artifact's frozen tolerances."""

    PASS = "pass"
    FAIL = "fail"
    BLOCKED = "blocked"


class MandatoryCohortStatus(StrEnum):
    """Fail-closed verdict for one predeclared scientific cohort."""

    PASS = "pass"
    FAIL = "fail"


class AuditComparisonProtocol(StrEnum):
    """Whether the independent evaluator preserves the persisted contract."""

    SAME_CONTRACT = "same_contract"
    ROBUSTNESS_CHARACTERIZATION = "robustness_characterization"


class _AuditModel(BaseModel):
    """Strict immutable base for byte-stable audit DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ScientificAuditConfig(_AuditModel):
    r"""Frozen numerical and inference gates for an independent audit.

    The endpoint equivalence verdict uses ``math.isclose`` with the persisted
    absolute and relative tolerances. Cluster intervals are eligible only at
    the predeclared scene threshold; lowering it after observing results would
    change the scientific contract.
    """

    endpoint_epsilon: PositiveFiniteFloat = 1e-8
    r"""Positive denominator stabilizer $\epsilon$ in independently evaluated $J$."""

    comparator_epsilon: PositiveFiniteFloat = 1e-12
    r"""Frozen clamp-min guard in persisted target-root-gain semantics."""

    absolute_tolerance: NonNegativeFiniteFloat = 1e-6
    """Absolute tolerance for recomputed versus persisted comparator gain."""

    relative_tolerance: NonNegativeFiniteFloat = 1e-5
    """Relative tolerance for recomputed versus persisted comparator gain."""

    eta_q_min_headroom: PositiveFiniteFloat = 0.01
    r"""Frozen minimum positive oracle headroom required to report $\eta_Q$.

    This threshold is fixed before endpoint evaluation. Exact matched units at
    or below it remain eligible for raw policy effects and denominator
    diagnostics, but never for the recovered-headroom ratio.
    """

    min_scenes_for_cluster_ci: Literal[20] = MIN_SCENES_FOR_CLUSTER_CI
    """Frozen minimum independent-scene count for cluster confidence intervals."""

    @field_validator("comparator_epsilon")
    @classmethod
    def _freeze_comparator_epsilon(cls, value: float) -> float:
        if value != 1e-12:
            raise ValueError("comparator_epsilon is frozen at 1e-12 by target-root-gain semantics.")
        return value


class NamedSha256(_AuditModel):
    """Stable name-to-content-hash association used for provenance."""

    name: NonEmptyStr
    """Unambiguous source, raw asset, policy role, or normalized config name."""

    sha256: Sha256Hex
    """Lowercase SHA-256 content digest."""


class PolicySemanticRole(StrEnum):
    """Predeclared scientific role of one rollout policy treatment."""

    LEARNED_ONE_STEP = "learned_one_step"
    LEARNED_QH = "learned_qh"
    ORACLE_ONE_STEP = "oracle_one_step"
    ORACLE_LOOKAHEAD = "oracle_lookahead"
    NON_LEARNED_BASELINE = "non_learned_baseline"


class PolicyTreatmentIdentity(_AuditModel):
    """Outcome-independent policy treatment and optional learned checkpoint."""

    semantic_role: PolicySemanticRole
    """Scientific role used to form predeclared policy contrasts."""

    treatment_id: NonEmptyStr
    """Stable treatment label; descriptive and excluded from exact matching."""

    model_checkpoint_sha256: Sha256Hex | None = None
    """Full learned-model checkpoint hash; absent only for non-learned roles."""

    @model_validator(mode="after")
    def _require_learned_checkpoint(self) -> PolicyTreatmentIdentity:
        learned = self.semantic_role in {
            PolicySemanticRole.LEARNED_ONE_STEP,
            PolicySemanticRole.LEARNED_QH,
        }
        if learned and self.model_checkpoint_sha256 is None:
            raise ValueError("Learned policy roles require model_checkpoint_sha256.")
        if not learned and self.model_checkpoint_sha256 is not None:
            raise ValueError("Non-learned policy roles must not provide model_checkpoint_sha256.")
        return self


class TreatmentConfigPath(_AuditModel):
    """One exact treatment-owned JSON Pointer removed before context matching."""

    owner: NonEmptyStr
    """Named resolved-config owner, such as ``candidate`` or ``policy``."""

    json_pointer: NonEmptyStr
    """RFC-6901-style absolute pointer to one explicitly allowed treatment field."""

    @field_validator("json_pointer")
    @classmethod
    def _validate_pointer(cls, value: str) -> str:
        if not value.startswith("/") or value == "/":
            raise ValueError("Treatment config paths must be non-root absolute JSON Pointers.")
        _decode_json_pointer(value)
        return value


class TreatmentNormalizedConfigIdentity(_AuditModel):
    """Raw provenance and treatment-normalized fingerprints for named configs.

    Raw fingerprints preserve provenance but never determine match eligibility.
    Eligibility uses :attr:`normalized_context_sha256`; removed values are
    isolated in :attr:`treatment_sha256` so the policy contrast remains explicit.
    """

    raw_fingerprints: tuple[NamedSha256, ...]
    """Per-owner hashes of the untouched resolved configurations."""

    normalized_fingerprints: tuple[NamedSha256, ...]
    """Per-owner hashes after removing exactly the treatment allowlist."""

    treatment_fingerprints: tuple[NamedSha256, ...]
    """Per-owner hashes of only the removed pointer/value mapping."""

    treatment_allowlist: tuple[TreatmentConfigPath, ...]
    """Sorted unique explicit treatment paths applied to every compared policy."""

    normalized_context_sha256: Sha256Hex
    """Hash of every named treatment-normalized configuration."""

    treatment_sha256: Sha256Hex
    """Hash of every removed treatment pointer and value."""

    @model_validator(mode="after")
    def _validate_owner_symmetry(self) -> TreatmentNormalizedConfigIdentity:
        groups = (self.raw_fingerprints, self.normalized_fingerprints, self.treatment_fingerprints)
        for group in groups:
            names = tuple(item.name for item in group)
            _require_unique(names, "config fingerprint owners")
            if names != tuple(sorted(names)):
                raise ValueError("Config fingerprint owners must be sorted.")
        owner_sets = tuple({item.name for item in group} for group in groups)
        if not owner_sets[0] or any(owner_set != owner_sets[0] for owner_set in owner_sets[1:]):
            raise ValueError("Raw, normalized, and treatment fingerprints require identical non-empty owner sets.")
        paths = tuple((item.owner, item.json_pointer) for item in self.treatment_allowlist)
        _require_unique(paths, "treatment allowlist paths")
        if paths != tuple(sorted(paths)):
            raise ValueError("Treatment allowlist paths must be sorted.")
        if any(item.owner not in owner_sets[0] for item in self.treatment_allowlist):
            raise ValueError("Treatment allowlist references an unknown config owner.")
        return self


class PolicyMatchIdentity(_AuditModel):
    """Frozen treatment plus exact non-treatment identity for one policy row.

    The exact match hash excludes raw config fingerprints, treatment values,
    the semantic role, learned checkpoint, and selected pose-chain outcome. It
    includes normalized config context, root action support, persisted source
    context, and independently reopened raw-asset context.

    Confirmatory construction must obtain ``persisted_context_sha256`` from
    :func:`aria_nbv.rollouts.read_model.persisted_pre_treatment_context_sha256`.
    The audit bridge recomputes that value. Treatment-normalized config context
    remains the typed output of :func:`normalize_treatment_configs` because the
    bridge intentionally does not decode configuration files independently.
    """

    treatment: PolicyTreatmentIdentity
    """Policy role and treatment identity excluded from the pairing key."""

    configs: TreatmentNormalizedConfigIdentity
    """Raw provenance and treatment-normalized resolved config identity."""

    root_action_set_sha256: Sha256Hex
    """Exact hash of the common pre-treatment root candidate table."""

    persisted_context_sha256: Sha256Hex
    """Hash of persisted source, target, protocol, seed, budget, and root context."""

    raw_asset_context_sha256: Sha256Hex
    """Hash of the full per-row independently reopened raw-asset identities."""

    exact_match_sha256: Sha256Hex
    """Derived pairing key over non-treatment context only."""

    @classmethod
    def derive(
        cls,
        *,
        treatment: PolicyTreatmentIdentity,
        configs: TreatmentNormalizedConfigIdentity,
        root_action_set_sha256: str,
        persisted_context_sha256: str,
        raw_asset_context_sha256: str,
    ) -> PolicyMatchIdentity:
        """Construct an identity and derive its exact non-treatment match hash."""

        payload = _policy_match_payload(
            configs=configs,
            root_action_set_sha256=root_action_set_sha256,
            persisted_context_sha256=persisted_context_sha256,
            raw_asset_context_sha256=raw_asset_context_sha256,
        )
        return cls(
            treatment=treatment,
            configs=configs,
            root_action_set_sha256=root_action_set_sha256,
            persisted_context_sha256=persisted_context_sha256,
            raw_asset_context_sha256=raw_asset_context_sha256,
            exact_match_sha256=_canonical_json_sha256(payload),
        )

    @model_validator(mode="after")
    def _validate_exact_hash(self) -> PolicyMatchIdentity:
        expected = _canonical_json_sha256(
            _policy_match_payload(
                configs=self.configs,
                root_action_set_sha256=self.root_action_set_sha256,
                persisted_context_sha256=self.persisted_context_sha256,
                raw_asset_context_sha256=self.raw_asset_context_sha256,
            )
        )
        if self.exact_match_sha256 != expected:
            raise ValueError("exact_match_sha256 does not match the frozen non-treatment identity.")
        return self


def normalize_treatment_configs(
    resolved_configs: Mapping[str, Any],
    treatment_allowlist: tuple[TreatmentConfigPath, ...],
) -> TreatmentNormalizedConfigIdentity:
    """Remove exactly allowed treatment fields from resolved JSON-like configs.

    Every pointer must exist. Unknown owners, undecodable values, duplicate or
    unsorted allowlist paths, and owner-set drift fail closed. The returned raw
    hashes are provenance only; exact matching uses the normalized context hash.
    """

    if not resolved_configs:
        raise ValueError("resolved_configs must contain at least one named owner.")
    owner_names = tuple(sorted(resolved_configs))
    if any(not isinstance(owner, str) or not owner for owner in owner_names):
        raise ValueError("Resolved config owners must be non-empty strings.")
    path_keys = tuple((item.owner, item.json_pointer) for item in treatment_allowlist)
    _require_unique(path_keys, "treatment allowlist paths")
    if path_keys != tuple(sorted(path_keys)):
        raise ValueError("Treatment allowlist paths must be sorted.")
    if any(item.owner not in resolved_configs for item in treatment_allowlist):
        raise ValueError("Treatment allowlist references an unknown config owner.")

    raw: dict[str, Any] = {}
    normalized: dict[str, Any] = {}
    removed: dict[str, dict[str, Any]] = {owner: {} for owner in owner_names}
    for owner in owner_names:
        value = deepcopy(resolved_configs[owner])
        _canonical_config_json_bytes(value)
        raw[owner] = value
        normalized[owner] = deepcopy(value)
    for path in treatment_allowlist:
        removed[path.owner][path.json_pointer] = _pop_json_pointer(
            normalized[path.owner],
            path.json_pointer,
        )

    def fingerprints(values: Mapping[str, Any]) -> tuple[NamedSha256, ...]:
        return tuple(NamedSha256(name=owner, sha256=_canonical_json_sha256(values[owner])) for owner in owner_names)

    return TreatmentNormalizedConfigIdentity(
        raw_fingerprints=fingerprints(raw),
        normalized_fingerprints=fingerprints(normalized),
        treatment_fingerprints=fingerprints(removed),
        treatment_allowlist=treatment_allowlist,
        normalized_context_sha256=_canonical_json_sha256(normalized),
        treatment_sha256=_canonical_json_sha256(removed),
    )


def named_sha256_context_hash(items: tuple[NamedSha256, ...]) -> str:
    """Hash a sorted unique set of named full content identities."""

    names = tuple(item.name for item in items)
    _require_unique(names, "named SHA-256 owners")
    if names != tuple(sorted(names)):
        raise ValueError("Named SHA-256 identities must be sorted.")
    return _canonical_json_sha256([item.model_dump(mode="json") for item in items])


class AuditProvenance(_AuditModel):
    """Immutable inputs and implementation identity used by the evaluator."""

    rollout_store_sha256: Sha256Hex
    """Manifest/content identity of the persisted rollout store."""

    source_store_sha256: Sha256Hex
    """Immutable VIN/source-store identity reopened by the evaluator."""

    split_manifest_sha256: Sha256Hex
    """Exact split-manifest identity governing admitted samples."""

    raw_assets: tuple[NamedSha256, ...]
    """Content hashes for meshes, target crops, and other independently reopened assets."""

    evaluator_id: NonEmptyStr
    """Stable evaluator implementation name."""

    implementation_revision: NonEmptyStr
    """Source revision of the independent evaluator."""

    resolved_config_sha256: Sha256Hex
    """Hash of the fully resolved evaluator and cohort configuration."""

    @model_validator(mode="after")
    def _reject_duplicate_named_hashes(self) -> AuditProvenance:
        _require_unique((item.name for item in self.raw_assets), "raw asset names")
        return self


class AuditStratumDimension(_AuditModel):
    """One named value participating in a deterministic stratum identity."""

    name: NonEmptyStr
    """Dimension name, such as ``scene_id``, ``depth``, or ``predicate_owner``."""

    value: NonEmptyStr
    """Canonical string value used before evaluator calls."""


class AuditStratum(_AuditModel):
    r"""Frozen sample allocation and analysis weight for one audit stratum.

    Theory:
        For population size $N_h$ and sample size $n_h$,
        $\pi_h=n_h/N_h$ and $w_h=1/\pi_h$. Failed sampled units are retained
        as blocked rows; they are never replaced by a lower hash priority.
    """

    stratum_id: NonEmptyStr
    """Stable identity referenced by sampled audit rows."""

    dimensions: tuple[AuditStratumDimension, ...]
    """Predeclared scene, depth, family, validity, reason, owner, and boundary values."""

    population_count: int = Field(ge=1)
    """Population count $N_h$ before independent evaluation."""

    audit_count: int = Field(ge=1)
    """Frozen selected count $n_h$, never increased to replace evaluator failures."""

    inclusion_probability: Probability
    r"""Inclusion probability $\pi_h=n_h/N_h$."""

    inverse_probability_weight: PositiveFiniteFloat
    r"""Analysis weight $w_h=1/\pi_h=N_h/n_h$."""

    @model_validator(mode="after")
    def _validate_sampling_equations(self) -> AuditStratum:
        if self.audit_count > self.population_count:
            raise ValueError("audit_count cannot exceed population_count.")
        _require_unique((item.name for item in self.dimensions), f"dimension names in {self.stratum_id!r}")
        expected_probability = self.audit_count / self.population_count
        if not math.isclose(self.inclusion_probability, expected_probability, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("inclusion_probability must equal audit_count / population_count.")
        expected_weight = self.population_count / self.audit_count
        if not math.isclose(self.inverse_probability_weight, expected_weight, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("inverse_probability_weight must equal population_count / audit_count.")
        return self


class AuditSamplingUnit(_AuditModel):
    """One population identity eligible for deterministic hash-priority sampling."""

    unit_id: NonEmptyStr
    """Globally unique endpoint or candidate-predicate identity."""

    stratum_id: NonEmptyStr
    """Predeclared stratum containing the unit."""


class FrozenAuditCohort(_AuditModel):
    """Pre-evaluation sample frozen by deterministic within-stratum hash priority."""

    seed: NonEmptyStr
    """Explicit sampling seed included in every priority digest."""

    cohort_sha256: Sha256Hex
    """Hash of the full population identities, allocations, dimensions, and seed."""

    population_count: int = Field(ge=1)
    """Total population count across strata."""

    audit_count: int = Field(ge=1)
    """Total selected audit count across strata."""

    strata: tuple[AuditStratum, ...]
    r"""All frozen strata with $N_h$, $n_h$, $\pi_h$, and $w_h$."""

    selected_unit_ids: tuple[NonEmptyStr, ...]
    """Selected identities in canonical stratum/hash-priority order."""

    @model_validator(mode="after")
    def _validate_totals(self) -> FrozenAuditCohort:
        if not self.strata:
            raise ValueError("A frozen audit cohort requires at least one stratum.")
        _require_unique((item.stratum_id for item in self.strata), "stratum IDs")
        _require_unique(self.selected_unit_ids, "selected audit unit IDs")
        if self.population_count != sum(item.population_count for item in self.strata):
            raise ValueError("population_count must equal the sum of stratum population counts.")
        if self.audit_count != sum(item.audit_count for item in self.strata):
            raise ValueError("audit_count must equal the sum of stratum audit counts.")
        if self.audit_count != len(self.selected_unit_ids):
            raise ValueError("audit_count must equal the number of selected_unit_ids.")
        return self


class EndpointAuditRow(_AuditModel):
    r"""Independent terminal-error audit for one fixed-budget rollout unit.

    Complete rows persist nonnegative independently evaluated $\Delta_0$ and
    $\Delta_H$, thesis endpoint gain $J$ with a ``+epsilon`` denominator, and
    a distinct clamp-min comparator recomputed from the same errors. The
    equivalence gate compares that recomputed comparator to the persisted
    undiscounted ($\gamma=1$) target-root return. Evaluator or source failures
    use ``blocked`` and a non-empty missing reason; they are not carried forward
    or silently dropped.
    """

    unit_id: NonEmptyStr
    """Identity selected in :class:`FrozenAuditCohort`."""

    stratum_id: NonEmptyStr
    """Sampling stratum controlling the unit's inclusion probability."""

    match_identity: PolicyMatchIdentity
    """Typed treatment and derived exact non-treatment pairing identity."""

    rollout_row_id: int = Field(ge=0)
    """Stable rollout-table row ID used for a safe live-store join."""

    scene_id: NonEmptyStr
    """Independent top-level sampling-unit identity."""

    rollout_id: NonEmptyStr
    """Persisted rollout identity."""

    source_sample_key: NonEmptyStr
    """Immutable source-row identity reopened by the evaluator."""

    source_store_sha256: Sha256Hex | None
    """Full immutable source-store manifest hash measured for this row."""

    split_manifest_sha256: Sha256Hex | None
    """Full ordered split-manifest hash measured for this row."""

    raw_assets: tuple[NamedSha256, ...]
    """Sorted per-row raw assets measured by the independent evaluator."""

    target_id: NonEmptyStr
    """Exact target-task identity."""

    pose_chain_sha256: Sha256Hex
    """Hash of the selected stored pose chain evaluated at the fixed budget."""

    evaluation_status: RowEvaluationStatus
    """Whether independent endpoint evaluation completed."""

    delta_0: NonNegativeFiniteFloat | None
    r"""Initial independent target reconstruction error $\Delta_0$."""

    delta_h: NonNegativeFiniteFloat | None
    r"""Terminal independent target reconstruction error $\Delta_H$."""

    endpoint_gain: FiniteFloat | None
    """Independently evaluated endpoint gain $J$."""

    comparator_gain: FiniteFloat | None
    """Persisted undiscounted telescoping root-normalized gain."""

    independent_comparator_gain: FiniteFloat | None
    r"""Comparator recomputed as $(\Delta_0-\Delta_H)/\max(\Delta_0,10^{-12})$."""

    comparator_gamma: FiniteFloat | None
    r"""Comparator discount; endpoint equivalence is defined only for $\gamma=1$."""

    absolute_error: NonNegativeFiniteFloat | None
    """Absolute difference between recomputed and persisted comparator gains."""

    relative_error: NonNegativeFiniteFloat | None
    """Comparator difference normalized by the larger magnitude or comparator epsilon."""

    equivalence_verdict: EquivalenceVerdict
    """Frozen-tolerance persisted-versus-independent comparator verdict."""

    achieved_steps: int | None = Field(default=None, ge=0)
    """Successfully evaluated acquisitions before the fixed budget ended."""

    budget: int | None = Field(default=None, ge=1)
    """Predeclared fixed acquisition budget."""

    termination_reason: Literal["fixed_horizon", "terminated_early"] | None = None
    """Complete fixed-budget or shorter absorbing termination state."""

    path_length_m: NonNegativeFiniteFloat | None = None
    """Selected trajectory length in metres."""

    evaluation_cost_s: NonNegativeFiniteFloat | None = None
    """Independent evaluation wall time in seconds when measured."""

    missing_reason: str | None = None
    """Required failure explanation for blocked evaluation; absent on complete rows."""

    @property
    def cohort_id(self) -> str:
        """Return the derived exact-match cohort identity used by reducers."""

        return self.match_identity.exact_match_sha256

    @property
    def effect_eligible(self) -> bool:
        """Whether this row may contribute to a paired endpoint effect."""

        return self.evaluation_status is RowEvaluationStatus.COMPLETE

    @model_validator(mode="after")
    def _validate_completion_shape(self) -> EndpointAuditRow:
        raw_asset_names = tuple(item.name for item in self.raw_assets)
        _require_unique(raw_asset_names, "endpoint raw asset names")
        if raw_asset_names != tuple(sorted(raw_asset_names)):
            raise ValueError("Endpoint raw assets must be sorted by name.")
        if (
            self.raw_assets
            and named_sha256_context_hash(self.raw_assets) != self.match_identity.raw_asset_context_sha256
        ):
            raise ValueError("Endpoint raw assets do not match match_identity.raw_asset_context_sha256.")
        required = (
            self.delta_0,
            self.delta_h,
            self.endpoint_gain,
            self.comparator_gain,
            self.independent_comparator_gain,
            self.comparator_gamma,
            self.absolute_error,
            self.relative_error,
            self.achieved_steps,
            self.budget,
        )
        if self.evaluation_status is RowEvaluationStatus.COMPLETE:
            if self.source_store_sha256 is None or self.split_manifest_sha256 is None:
                raise ValueError("Complete endpoint rows require full source and split identities.")
            if named_sha256_context_hash(self.raw_assets) != self.match_identity.raw_asset_context_sha256:
                raise ValueError("Complete endpoint raw assets must match the frozen raw-asset context.")
            if any(value is None for value in required):
                raise ValueError("Complete endpoint rows require every endpoint, comparator, and budget field.")
            if self.missing_reason is not None:
                raise ValueError("Complete endpoint rows cannot have missing_reason.")
            if self.equivalence_verdict is EquivalenceVerdict.BLOCKED:
                raise ValueError("Complete endpoint rows require pass or fail equivalence_verdict.")
            assert self.achieved_steps is not None and self.budget is not None
            if self.termination_reason is None:
                raise ValueError("Complete endpoint rows require an exact termination_reason.")
            if self.termination_reason == "fixed_horizon" and self.achieved_steps != self.budget:
                raise ValueError("fixed_horizon endpoint rows must achieve exactly budget steps.")
            if self.termination_reason == "terminated_early" and self.achieved_steps >= self.budget:
                raise ValueError("terminated_early endpoint rows must be shorter than budget.")
        else:
            if not self.missing_reason:
                raise ValueError("Blocked endpoint rows require missing_reason.")
            if self.equivalence_verdict is not EquivalenceVerdict.BLOCKED:
                raise ValueError("Blocked endpoint rows require blocked equivalence_verdict.")
        return self


class ValidityPredicateContract(_AuditModel):
    """Canonical scalar validity-predicate identity for side-artifact comparison."""

    predicate_kind: Literal["state", "path", "combined_actor", "oracle_label"]
    """Separated validity role owned by this predicate."""

    owner: NonEmptyStr
    """Canonical implementation owner."""

    name: NonEmptyStr
    """Versioned predicate name."""

    comparison_operator: Literal["<", "<=", ">", ">=", "==", "!="]
    """Scalar comparison operator defining the decision boundary."""

    threshold: FiniteFloat
    """Predicate threshold in :attr:`unit`."""

    unit: NonEmptyStr
    """Physical or dimensionless measurement unit."""

    frame: NonEmptyStr
    """Coordinate or semantic frame in which the measurement is defined."""

    semantic_config_sha256: Sha256Hex
    """Hash of collision, threshold, and other predicate-semantic configuration."""

    identity_sha256: Sha256Hex
    """Canonical hash of every predicate-contract field except this hash."""

    @classmethod
    def derive(
        cls,
        *,
        predicate_kind: Literal["state", "path", "combined_actor", "oracle_label"],
        owner: str,
        name: str,
        comparison_operator: Literal["<", "<=", ">", ">=", "==", "!="],
        threshold: float,
        unit: str,
        frame: str,
        semantic_config_sha256: str,
    ) -> ValidityPredicateContract:
        """Construct a predicate descriptor and derive its canonical identity."""

        payload = {
            "predicate_kind": predicate_kind,
            "owner": owner,
            "name": name,
            "comparison_operator": comparison_operator,
            "threshold": threshold,
            "unit": unit,
            "frame": frame,
            "semantic_config_sha256": semantic_config_sha256,
        }
        return cls(**payload, identity_sha256=_canonical_json_sha256(payload))

    @model_validator(mode="after")
    def _validate_identity(self) -> ValidityPredicateContract:
        payload = self.model_dump(mode="python", exclude={"identity_sha256"})
        if self.identity_sha256 != _canonical_json_sha256(payload):
            raise ValueError("Validity predicate identity does not match its canonical contract fields.")
        return self


class ValidityAuditRow(_AuditModel):
    r"""Independent same-contract verdict for one candidate-predicate sample.

    Persisted and independent validity are Boolean contract outcomes, never low
    reconstruction gains. ``signed_margin`` uses the persisted predicate's
    operator, threshold, units, and frame. Positive values lie on the valid
    side, negative values on the invalid side, and zero is the boundary whose
    verdict follows the declared strict or inclusive operator. Changing those
    semantics makes the artifact robustness characterization rather than
    correctness evidence.
    """

    unit_id: NonEmptyStr
    """Candidate-predicate identity selected before evaluator calls."""

    stratum_id: NonEmptyStr
    """Sampling stratum controlling inclusion probability and analysis weight."""

    cohort_id: NonEmptyStr
    """Exact scientific cohort identity."""

    scene_id: NonEmptyStr
    """Independent top-level sampling-unit identity."""

    rollout_id: NonEmptyStr
    """Persisted rollout containing the candidate."""

    candidate_id: NonEmptyStr
    """Stable candidate row identity within the rollout state."""

    depth: int = Field(ge=0)
    """Rollout-state depth at which the predicate was evaluated."""

    candidate_family: NonEmptyStr
    """Persisted generation family used in stratification."""

    persisted_contract: ValidityPredicateContract
    """Canonical descriptor of the persisted predicate being audited."""

    independent_contract: ValidityPredicateContract
    """Canonical descriptor actually applied by the independent evaluator."""

    persisted_valid: bool
    """Persisted mask/verdict being audited."""

    independent_valid: bool | None
    """Independent same-contract verdict, or ``None`` when evaluation failed."""

    raw_measurement: FiniteFloat | None
    """Independent raw predicate measurement in :attr:`unit`."""

    signed_margin: FiniteFloat | None
    """Signed boundary distance; zero validity follows the declared operator."""

    evaluation_status: RowEvaluationStatus
    """Whether independent predicate evaluation completed."""

    missing_reason: str | None = None
    """Required failure explanation for blocked rows; absent on complete rows."""

    inclusion_probability: Probability
    r"""Copied $\pi_h$ for self-contained weighted validity tables."""

    inverse_probability_weight: PositiveFiniteFloat
    r"""Copied $1/\pi_h$ analysis weight."""

    @property
    def predicate_kind(self) -> Literal["state", "path", "combined_actor", "oracle_label"]:
        """Return the persisted predicate role used for stratified reduction."""

        return self.persisted_contract.predicate_kind

    @property
    def predicate_owner(self) -> str:
        """Return the persisted predicate implementation owner."""

        return self.persisted_contract.owner

    @property
    def predicate_name(self) -> str:
        """Return the persisted versioned predicate name."""

        return self.persisted_contract.name

    @property
    def comparison_operator(self) -> str:
        """Return the independent evaluator's declared comparison operator."""

        return self.independent_contract.comparison_operator

    @property
    def threshold(self) -> float:
        """Return the independent evaluator's declared threshold."""

        return float(self.independent_contract.threshold)

    @property
    def unit(self) -> str:
        """Return the independent evaluator's declared measurement unit."""

        return self.independent_contract.unit

    @model_validator(mode="after")
    def _validate_completion_shape(self) -> ValidityAuditRow:
        if self.evaluation_status is RowEvaluationStatus.COMPLETE:
            if self.independent_valid is None or self.raw_measurement is None or self.signed_margin is None:
                raise ValueError("Complete validity rows require verdict, raw_measurement, and signed_margin.")
            if self.missing_reason is not None:
                raise ValueError("Complete validity rows cannot have missing_reason.")
            expected_valid, expected_margin = _predicate_outcome_and_margin(
                measurement=float(self.raw_measurement),
                threshold=float(self.threshold),
                operator=self.comparison_operator,
            )
            if self.independent_valid is not expected_valid:
                raise ValueError("Independent validity verdict must follow the declared predicate contract.")
            if not math.isclose(float(self.signed_margin), expected_margin, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError("signed_margin must be derived from raw_measurement, threshold, and operator.")
        else:
            if not self.missing_reason:
                raise ValueError("Blocked validity rows require missing_reason.")
            if self.independent_valid is not None:
                raise ValueError("Blocked validity rows cannot have an independent verdict.")
            if self.raw_measurement is not None or self.signed_margin is not None:
                raise ValueError("Blocked validity rows cannot infer measurements or signed margins.")
        return self


class AuditCohortSummary(_AuditModel):
    """Mandatory audit gate and row counts for one exact scientific cohort."""

    cohort_id: NonEmptyStr
    """Identity shared by endpoint and validity rows."""

    endpoint_row_count: int = Field(ge=0)
    """Number of endpoint audit rows in the cohort."""

    validity_row_count: int = Field(ge=0)
    """Number of candidate-predicate audit rows in the cohort."""

    mandatory_status: MandatoryCohortStatus
    """Predeclared PASS/FAIL outcome used by confirmatory readiness."""

    reason: NonEmptyStr
    """Human-readable justification for the mandatory cohort verdict."""


class ScientificAuditPayload(_AuditModel):
    """Unsealed deterministic scientific-audit content."""

    schema_version: Literal["stored-rollout-scientific-audit-v1"] = SCIENTIFIC_AUDIT_SCHEMA_VERSION
    """Exact reader/writer schema version; no rollout-Zarr version is changed."""

    artifact_role: Literal["stored_rollout_scientific_audit"] = SCIENTIFIC_AUDIT_ARTIFACT_ROLE
    """Stable role distinguishing this JSON side artifact from rollout stores."""

    status: AuditStatus
    """Exact completeness/gate status validated against every sampled row."""

    readiness: AuditReadiness
    """Evidence use implied exactly by :attr:`status`."""

    comparison_protocol: AuditComparisonProtocol
    """Same-contract audit or explicitly non-confirmatory robustness characterization."""

    config: ScientificAuditConfig
    """Frozen endpoint tolerances and scene-inference threshold."""

    provenance: AuditProvenance
    """Rollout, source, raw-asset, evaluator, revision, and config identities."""

    cohort: FrozenAuditCohort
    """Deterministic pre-evaluation population and sampled identities."""

    endpoint_rows: tuple[EndpointAuditRow, ...]
    """Independent endpoint audit rows; blocked sampled units remain explicit."""

    validity_rows: tuple[ValidityAuditRow, ...]
    """Independent state/path/admission/label validity rows with audit weights."""

    cohort_summaries: tuple[AuditCohortSummary, ...]
    """One mandatory PASS/FAIL summary per exact cohort represented by rows."""

    observed_distinct_scenes: int = Field(ge=0)
    """Distinct scenes represented by endpoint and validity audit rows."""

    cluster_ci_eligible: bool
    """Whether scene-cluster confidence intervals may be reported."""

    cluster_ci_suppression_reason: str | None
    """Stable reason emitted below the frozen scene threshold."""

    @model_validator(mode="after")
    def _validate_scientific_contract(self) -> ScientificAuditPayload:
        all_rows: tuple[EndpointAuditRow | ValidityAuditRow, ...] = (*self.endpoint_rows, *self.validity_rows)
        _require_unique((row.unit_id for row in all_rows), "audit row unit IDs")

        selected = set(self.cohort.selected_unit_ids)
        row_ids = {row.unit_id for row in all_rows}
        if not row_ids.issubset(selected):
            raise ValueError("Every audit row must reference a selected cohort unit ID.")

        strata = {stratum.stratum_id: stratum for stratum in self.cohort.strata}
        for row in all_rows:
            if row.stratum_id not in strata:
                raise ValueError(f"Audit row {row.unit_id!r} references an unknown stratum.")
        for row in self.validity_rows:
            stratum = strata[row.stratum_id]
            if not math.isclose(row.inclusion_probability, stratum.inclusion_probability, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError("Validity-row inclusion probability must match its frozen stratum.")
            if not math.isclose(
                row.inverse_probability_weight,
                stratum.inverse_probability_weight,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError("Validity-row inverse-probability weight must match its frozen stratum.")
        changed_contract_rows = tuple(
            row.unit_id
            for row in self.validity_rows
            if row.persisted_contract.identity_sha256 != row.independent_contract.identity_sha256
        )
        if changed_contract_rows and self.comparison_protocol is AuditComparisonProtocol.SAME_CONTRACT:
            raise ValueError(
                "SAME_CONTRACT validity audits require exact persisted/independent predicate identities; "
                f"changed rows: {', '.join(changed_contract_rows)}."
            )

        self._validate_endpoint_equations()
        self._validate_cohort_summaries()

        scene_count = len({row.scene_id for row in all_rows})
        if self.observed_distinct_scenes != scene_count:
            raise ValueError("observed_distinct_scenes must equal the distinct row scene count.")
        expected_ci = scene_count >= self.config.min_scenes_for_cluster_ci
        if self.cluster_ci_eligible is not expected_ci:
            raise ValueError("cluster_ci_eligible must follow min_scenes_for_cluster_ci exactly.")
        if expected_ci and self.cluster_ci_suppression_reason is not None:
            raise ValueError("Eligible cluster intervals cannot have a suppression reason.")
        if not expected_ci and not self.cluster_ci_suppression_reason:
            raise ValueError("Ineligible cluster intervals require a suppression reason.")

        incomplete = (
            row_ids != selected
            or not self.endpoint_rows
            or not self.validity_rows
            or any(row.evaluation_status is RowEvaluationStatus.BLOCKED for row in all_rows)
        )
        failed = any(row.equivalence_verdict is EquivalenceVerdict.FAIL for row in self.endpoint_rows) or any(
            summary.mandatory_status is MandatoryCohortStatus.FAIL for summary in self.cohort_summaries
        )
        if self.comparison_protocol is AuditComparisonProtocol.ROBUSTNESS_CHARACTERIZATION:
            expected_status = AuditStatus.PARTIAL if incomplete else AuditStatus.CHARACTERIZATION
        elif incomplete:
            expected_status = AuditStatus.PARTIAL
        elif failed:
            expected_status = AuditStatus.FAIL
        else:
            expected_status = AuditStatus.PASS
        expected_readiness = {
            AuditStatus.PASS: AuditReadiness.CONFIRMATORY,
            AuditStatus.CHARACTERIZATION: AuditReadiness.PILOT,
            AuditStatus.FAIL: AuditReadiness.BLOCKED,
            AuditStatus.PARTIAL: AuditReadiness.BLOCKED,
        }[expected_status]
        if self.status is not expected_status or self.readiness is not expected_readiness:
            raise ValueError(
                f"status/readiness must be {expected_status.value}/{expected_readiness.value} for this audit content."
            )
        return self

    def _validate_endpoint_equations(self) -> None:
        for row in self.endpoint_rows:
            if row.evaluation_status is RowEvaluationStatus.BLOCKED:
                continue
            assert row.delta_0 is not None
            assert row.delta_h is not None
            assert row.endpoint_gain is not None
            assert row.comparator_gain is not None
            assert row.independent_comparator_gain is not None
            assert row.comparator_gamma is not None
            assert row.absolute_error is not None
            assert row.relative_error is not None
            expected_gain = (row.delta_0 - row.delta_h) / (row.delta_0 + self.config.endpoint_epsilon)
            if not math.isclose(row.endpoint_gain, expected_gain, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError(f"Endpoint row {row.unit_id!r} has an inconsistent endpoint_gain.")
            expected_comparator = (row.delta_0 - row.delta_h) / max(row.delta_0, self.config.comparator_epsilon)
            if not math.isclose(
                row.independent_comparator_gain,
                expected_comparator,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError(f"Endpoint row {row.unit_id!r} has an inconsistent independent_comparator_gain.")
            if row.comparator_gamma != 1.0:
                raise ValueError("Endpoint equivalence comparator_gamma must equal 1.0.")
            expected_absolute = abs(row.independent_comparator_gain - row.comparator_gain)
            expected_relative = expected_absolute / max(
                abs(row.independent_comparator_gain),
                abs(row.comparator_gain),
                self.config.comparator_epsilon,
            )
            if not math.isclose(row.absolute_error, expected_absolute, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError(f"Endpoint row {row.unit_id!r} has an inconsistent absolute_error.")
            if not math.isclose(row.relative_error, expected_relative, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError(f"Endpoint row {row.unit_id!r} has an inconsistent relative_error.")
            expected_verdict = (
                EquivalenceVerdict.PASS
                if math.isclose(
                    row.independent_comparator_gain,
                    row.comparator_gain,
                    rel_tol=self.config.relative_tolerance,
                    abs_tol=self.config.absolute_tolerance,
                )
                else EquivalenceVerdict.FAIL
            )
            if row.equivalence_verdict is not expected_verdict:
                raise ValueError(f"Endpoint row {row.unit_id!r} has an inconsistent equivalence_verdict.")

    def _validate_cohort_summaries(self) -> None:
        _require_unique((summary.cohort_id for summary in self.cohort_summaries), "cohort summary IDs")
        cohort_ids = {row.cohort_id for row in self.endpoint_rows}
        cohort_ids.update(row.cohort_id for row in self.validity_rows)
        if {summary.cohort_id for summary in self.cohort_summaries} != cohort_ids:
            raise ValueError("cohort_summaries must cover exactly the cohort IDs represented by audit rows.")
        for summary in self.cohort_summaries:
            endpoint_count = sum(row.cohort_id == summary.cohort_id for row in self.endpoint_rows)
            validity_count = sum(row.cohort_id == summary.cohort_id for row in self.validity_rows)
            if summary.endpoint_row_count != endpoint_count or summary.validity_row_count != validity_count:
                raise ValueError(f"Cohort summary counts are inconsistent for {summary.cohort_id!r}.")


class ScientificAuditArtifact(ScientificAuditPayload):
    """Sealed audit payload with a SHA-256 over canonical unhashed JSON bytes."""

    bundle_sha256: Sha256Hex
    """SHA-256 of :func:`canonical_scientific_audit_bytes` excluding this field."""


def freeze_hash_priority_cohort(
    units: tuple[AuditSamplingUnit, ...],
    audit_counts: dict[str, int],
    *,
    seed: str,
    dimensions: dict[str, tuple[AuditStratumDimension, ...]] | None = None,
) -> FrozenAuditCohort:
    r"""Freeze a deterministic stratified audit sample before evaluator calls.

    Units are ranked within each stratum by SHA-256 of the seed, stratum ID,
    and unit ID. Only the first predeclared $n_h$ units are retained. The
    returned cohort records $N_h$, $n_h$, $\pi_h$, and $1/\pi_h$ and hashes the
    complete population plus allocation, not merely the selected sample.

    Args:
        units: Complete population identities and stratum assignments.
        audit_counts: Exact sample size $n_h$ for every represented stratum.
        seed: Non-empty frozen sampling seed.
        dimensions: Optional named dimensions for every represented stratum.

    Returns:
        Frozen cohort in canonical stratum/hash-priority order.
    """

    if not seed:
        raise ValueError("seed must be non-empty.")
    if not units:
        raise ValueError("units must contain at least one population identity.")
    _require_unique((unit.unit_id for unit in units), "population unit IDs")
    grouped: dict[str, list[AuditSamplingUnit]] = {}
    for unit in units:
        grouped.setdefault(unit.stratum_id, []).append(unit)
    if set(audit_counts) != set(grouped):
        raise ValueError("audit_counts must cover exactly the represented strata.")
    if dimensions is not None and set(dimensions) != set(grouped):
        raise ValueError("dimensions must cover exactly the represented strata.")

    selected: list[str] = []
    strata: list[AuditStratum] = []
    for stratum_id in sorted(grouped):
        population = grouped[stratum_id]
        audit_count = audit_counts[stratum_id]
        if (
            isinstance(audit_count, bool)
            or not isinstance(audit_count, int)
            or audit_count < 1
            or audit_count > len(population)
        ):
            raise ValueError(f"Invalid audit count {audit_count!r} for stratum {stratum_id!r}.")
        ordered = sorted(population, key=lambda unit: (_hash_priority(seed, unit), unit.unit_id))
        selected.extend(unit.unit_id for unit in ordered[:audit_count])
        probability = audit_count / len(population)
        strata.append(
            AuditStratum(
                stratum_id=stratum_id,
                dimensions=() if dimensions is None else dimensions[stratum_id],
                population_count=len(population),
                audit_count=audit_count,
                inclusion_probability=probability,
                inverse_probability_weight=1.0 / probability,
            )
        )

    cohort_payload = {
        "seed": seed,
        "units": sorted(
            (unit.model_dump(mode="json") for unit in units), key=lambda row: (row["stratum_id"], row["unit_id"])
        ),
        "audit_counts": {key: audit_counts[key] for key in sorted(audit_counts)},
        "dimensions": {
            key: [item.model_dump(mode="json") for item in (() if dimensions is None else dimensions[key])]
            for key in sorted(grouped)
        },
    }
    cohort_sha256 = hashlib.sha256(_canonical_json_bytes(cohort_payload)).hexdigest()
    return FrozenAuditCohort(
        seed=seed,
        cohort_sha256=cohort_sha256,
        population_count=len(units),
        audit_count=len(selected),
        strata=tuple(strata),
        selected_unit_ids=tuple(selected),
    )


def seal_scientific_audit(payload: ScientificAuditPayload) -> ScientificAuditArtifact:
    """Attach the SHA-256 of canonical payload bytes without mutating the payload."""

    digest = hashlib.sha256(canonical_scientific_audit_bytes(payload)).hexdigest()
    return ScientificAuditArtifact.model_validate({**payload.model_dump(mode="python"), "bundle_sha256": digest})


def canonical_scientific_audit_bytes(
    artifact: ScientificAuditPayload | ScientificAuditArtifact,
    *,
    include_bundle_sha256: bool = False,
) -> bytes:
    """Serialize an audit with sorted keys, strict finite numbers, and one newline.

    Args:
        artifact: Unsealed payload or sealed artifact.
        include_bundle_sha256: Include the seal field for persisted bytes. The
            digest itself is always computed with this set to ``False``.

    Returns:
        Canonical UTF-8 JSON bytes with a trailing newline.
    """

    payload = artifact.model_dump(mode="json")
    if not include_bundle_sha256:
        payload.pop("bundle_sha256", None)
    return _canonical_json_bytes(payload)


def verify_scientific_audit_sha256(artifact: ScientificAuditArtifact) -> None:
    """Raise when the sealed bundle hash does not match canonical payload bytes."""

    actual = hashlib.sha256(canonical_scientific_audit_bytes(artifact)).hexdigest()
    if actual != artifact.bundle_sha256:
        raise ValueError(f"Scientific audit bundle SHA-256 mismatch: expected {artifact.bundle_sha256}, got {actual}.")


def require_confirmatory_audit(artifact: ScientificAuditArtifact) -> None:
    """Reject any artifact that is absent from the exact confirmatory PASS state."""

    verify_scientific_audit_sha256(artifact)
    if artifact.status is not AuditStatus.PASS or artifact.readiness is not AuditReadiness.CONFIRMATORY:
        raise ValueError(
            f"Confirmatory evidence requires pass/confirmatory, got {artifact.status.value}/{artifact.readiness.value}."
        )


def write_scientific_audit(path: Path, payload: ScientificAuditPayload) -> ScientificAuditArtifact:
    """Seal and atomically write one canonical JSON side artifact outside Zarr."""

    artifact = seal_scientific_audit(payload)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(canonical_scientific_audit_bytes(artifact, include_bundle_sha256=True))
    temporary.replace(path)
    return artifact


def load_scientific_audit(path: Path, *, require_confirmatory: bool = False) -> ScientificAuditArtifact:
    """Load strict JSON, reject duplicate keys/nonfinite values, and verify its seal."""

    path = Path(path)
    raw = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_object_without_duplicate_keys,
        parse_constant=_reject_json_constant,
    )
    artifact = ScientificAuditArtifact.model_validate_json(_canonical_json_bytes(raw))
    verify_scientific_audit_sha256(artifact)
    if require_confirmatory:
        require_confirmatory_audit(artifact)
    return artifact


def _hash_priority(seed: str, unit: AuditSamplingUnit) -> bytes:
    return hashlib.sha256(f"{seed}\0{unit.stratum_id}\0{unit.unit_id}".encode()).digest()


def _predicate_outcome_and_margin(
    *,
    measurement: float,
    threshold: float,
    operator: str,
) -> tuple[bool, float]:
    """Evaluate one declared scalar predicate and its signed boundary margin."""

    if operator == "<":
        return measurement < threshold, threshold - measurement
    if operator == "<=":
        return measurement <= threshold, threshold - measurement
    if operator == ">":
        return measurement > threshold, measurement - threshold
    if operator == ">=":
        return measurement >= threshold, measurement - threshold
    if operator == "==":
        return measurement == threshold, -abs(measurement - threshold)
    if operator == "!=":
        return measurement != threshold, abs(measurement - threshold)
    raise ValueError(f"Unsupported predicate comparison operator {operator!r}.")


def _canonical_json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=True, allow_nan=False, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode("utf-8")


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key {key!r} in scientific audit artifact.")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> Any:
    raise ValueError(f"Nonfinite JSON constant {value!r} is forbidden in scientific audit artifacts.")


def _canonical_config_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("Resolved configs must contain only finite JSON-like values.") from exc


def _canonical_json_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_config_json_bytes(value)).hexdigest()


def _decode_json_pointer(pointer: str) -> tuple[str, ...]:
    tokens: list[str] = []
    for raw in pointer[1:].split("/"):
        index = 0
        decoded: list[str] = []
        while index < len(raw):
            if raw[index] != "~":
                decoded.append(raw[index])
                index += 1
                continue
            if index + 1 >= len(raw) or raw[index + 1] not in {"0", "1"}:
                raise ValueError(f"Invalid JSON Pointer escape in {pointer!r}.")
            decoded.append("~" if raw[index + 1] == "0" else "/")
            index += 2
        tokens.append("".join(decoded))
    return tuple(tokens)


def _pop_json_pointer(document: Any, pointer: str) -> Any:
    tokens = _decode_json_pointer(pointer)
    parent = document
    for token in tokens[:-1]:
        if isinstance(parent, dict):
            if token not in parent:
                raise ValueError(f"Treatment path {pointer!r} does not exist.")
            parent = parent[token]
        elif isinstance(parent, list):
            try:
                index = int(token)
            except ValueError as exc:
                raise ValueError(f"Treatment path {pointer!r} has a non-integer list index.") from exc
            if index < 0 or index >= len(parent):
                raise ValueError(f"Treatment path {pointer!r} does not exist.")
            parent = parent[index]
        else:
            raise ValueError(f"Treatment path {pointer!r} crosses a scalar value.")
    leaf = tokens[-1]
    if isinstance(parent, dict):
        if leaf not in parent:
            raise ValueError(f"Treatment path {pointer!r} does not exist.")
        return parent.pop(leaf)
    if isinstance(parent, list):
        try:
            index = int(leaf)
        except ValueError as exc:
            raise ValueError(f"Treatment path {pointer!r} has a non-integer list index.") from exc
        if index < 0 or index >= len(parent):
            raise ValueError(f"Treatment path {pointer!r} does not exist.")
        return parent.pop(index)
    raise ValueError(f"Treatment path {pointer!r} crosses a scalar value.")


def _policy_match_payload(
    *,
    configs: TreatmentNormalizedConfigIdentity,
    root_action_set_sha256: str,
    persisted_context_sha256: str,
    raw_asset_context_sha256: str,
) -> dict[str, Any]:
    return {
        "normalized_config_context_sha256": configs.normalized_context_sha256,
        "root_action_set_sha256": root_action_set_sha256,
        "persisted_context_sha256": persisted_context_sha256,
        "raw_asset_context_sha256": raw_asset_context_sha256,
    }


def _require_unique(values: Any, label: str) -> None:
    materialized = tuple(values)
    if len(set(materialized)) != len(materialized):
        raise ValueError(f"Duplicate {label} are forbidden.")


__all__ = [
    "MIN_SCENES_FOR_CLUSTER_CI",
    "SCIENTIFIC_AUDIT_ARTIFACT_ROLE",
    "SCIENTIFIC_AUDIT_SCHEMA_VERSION",
    "AuditCohortSummary",
    "AuditComparisonProtocol",
    "AuditProvenance",
    "AuditReadiness",
    "AuditSamplingUnit",
    "AuditStatus",
    "AuditStratum",
    "AuditStratumDimension",
    "EndpointAuditRow",
    "EquivalenceVerdict",
    "FrozenAuditCohort",
    "MandatoryCohortStatus",
    "NamedSha256",
    "PolicyMatchIdentity",
    "PolicySemanticRole",
    "PolicyTreatmentIdentity",
    "RowEvaluationStatus",
    "ScientificAuditArtifact",
    "ScientificAuditConfig",
    "ScientificAuditPayload",
    "ValidityAuditRow",
    "ValidityPredicateContract",
    "TreatmentConfigPath",
    "TreatmentNormalizedConfigIdentity",
    "canonical_scientific_audit_bytes",
    "freeze_hash_priority_cohort",
    "load_scientific_audit",
    "named_sha256_context_hash",
    "normalize_treatment_configs",
    "require_confirmatory_audit",
    "seal_scientific_audit",
    "verify_scientific_audit_sha256",
    "write_scientific_audit",
]
