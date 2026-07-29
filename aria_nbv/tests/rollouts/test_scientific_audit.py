from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from aria_nbv.rollouts.scientific_audit import (
    MIN_SCENES_FOR_CLUSTER_CI,
    AuditCohortSummary,
    AuditComparisonProtocol,
    AuditProvenance,
    AuditReadiness,
    AuditSamplingUnit,
    AuditStatus,
    AuditStratumDimension,
    EndpointAuditRow,
    EquivalenceVerdict,
    MandatoryCohortStatus,
    NamedSha256,
    PolicyMatchIdentity,
    PolicySemanticRole,
    PolicyTreatmentIdentity,
    RowEvaluationStatus,
    ScientificAuditArtifact,
    ScientificAuditConfig,
    ScientificAuditPayload,
    TreatmentConfigPath,
    ValidityAuditRow,
    ValidityPredicateContract,
    canonical_scientific_audit_bytes,
    freeze_hash_priority_cohort,
    load_scientific_audit,
    named_sha256_context_hash,
    normalize_treatment_configs,
    require_confirmatory_audit,
    seal_scientific_audit,
    verify_scientific_audit_sha256,
    write_scientific_audit,
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _predicate_contract(
    *,
    kind: str = "path",
    owner: str = "motion_validator",
    name: str = "max_step_m:v1",
    threshold: float = 0.25,
) -> ValidityPredicateContract:
    return ValidityPredicateContract.derive(
        predicate_kind=kind,  # type: ignore[arg-type]
        owner=owner,
        name=name,
        comparison_operator="<=",
        threshold=threshold,
        unit="m",
        frame="ARIA world",
        semantic_config_sha256=_sha(f"{kind}:{owner}:{name}:{threshold}"),
    )


def _match_identity(*, treatment: str = "oracle-1") -> tuple[PolicyMatchIdentity, tuple[NamedSha256, ...]]:
    raw_assets = (NamedSha256(name="target_mesh", sha256=_sha("target-mesh")),)
    configs = normalize_treatment_configs(
        {"policy": {"shared": {"budget": 3}, "treatment": treatment}},
        (TreatmentConfigPath(owner="policy", json_pointer="/treatment"),),
    )
    return (
        PolicyMatchIdentity.derive(
            treatment=PolicyTreatmentIdentity(
                semantic_role=PolicySemanticRole.ORACLE_ONE_STEP,
                treatment_id=treatment,
            ),
            configs=configs,
            root_action_set_sha256=_sha("root-actions"),
            persisted_context_sha256=_sha("persisted-context"),
            raw_asset_context_sha256=named_sha256_context_hash(raw_assets),
        ),
        raw_assets,
    )


def _cohort():
    units = (
        AuditSamplingUnit(unit_id="endpoint-1", stratum_id="endpoint"),
        AuditSamplingUnit(unit_id="validity-1", stratum_id="validity"),
    )
    return freeze_hash_priority_cohort(
        units,
        {"endpoint": 1, "validity": 1},
        seed="audit-seed-v1",
        dimensions={
            "endpoint": (AuditStratumDimension(name="scene_id", value="scene-1"),),
            "validity": (
                AuditStratumDimension(name="scene_id", value="scene-1"),
                AuditStratumDimension(name="predicate_owner", value="motion_validator"),
            ),
        },
    )


def _complete_payload(*, endpoint_comparator_offset: float = 0.0) -> ScientificAuditPayload:
    cohort = _cohort()
    config = ScientificAuditConfig()
    delta_0 = 10.0
    delta_h = 7.0
    endpoint_gain = (delta_0 - delta_h) / (delta_0 + config.endpoint_epsilon)
    independent_comparator_gain = (delta_0 - delta_h) / max(delta_0, config.comparator_epsilon)
    comparator_gain = independent_comparator_gain + endpoint_comparator_offset
    absolute_error = abs(independent_comparator_gain - comparator_gain)
    relative_error = absolute_error / max(
        abs(independent_comparator_gain), abs(comparator_gain), config.comparator_epsilon
    )
    verdict = (
        EquivalenceVerdict.PASS
        if math.isclose(
            independent_comparator_gain,
            comparator_gain,
            rel_tol=config.relative_tolerance,
            abs_tol=config.absolute_tolerance,
        )
        else EquivalenceVerdict.FAIL
    )
    status = AuditStatus.PASS if verdict is EquivalenceVerdict.PASS else AuditStatus.FAIL
    readiness = AuditReadiness.CONFIRMATORY if status is AuditStatus.PASS else AuditReadiness.BLOCKED
    match_identity, endpoint_raw_assets = _match_identity()
    endpoint = EndpointAuditRow(
        unit_id="endpoint-1",
        stratum_id="endpoint",
        match_identity=match_identity,
        rollout_row_id=7,
        scene_id="scene-1",
        rollout_id="rollout-1",
        source_sample_key="sample-1",
        source_store_sha256=_sha("source-store"),
        split_manifest_sha256=_sha("split-manifest"),
        raw_assets=endpoint_raw_assets,
        target_id="target-1",
        pose_chain_sha256=_sha("pose-chain"),
        evaluation_status=RowEvaluationStatus.COMPLETE,
        delta_0=delta_0,
        delta_h=delta_h,
        endpoint_gain=endpoint_gain,
        comparator_gain=comparator_gain,
        independent_comparator_gain=independent_comparator_gain,
        comparator_gamma=1.0,
        absolute_error=absolute_error,
        relative_error=relative_error,
        equivalence_verdict=verdict,
        achieved_steps=3,
        budget=3,
        termination_reason="fixed_horizon",
        path_length_m=1.5,
        evaluation_cost_s=2.0,
        missing_reason=None,
    )
    validity_stratum = next(item for item in cohort.strata if item.stratum_id == "validity")
    validity = ValidityAuditRow(
        unit_id="validity-1",
        stratum_id="validity",
        cohort_id=match_identity.exact_match_sha256,
        scene_id="scene-1",
        rollout_id="rollout-1",
        candidate_id="candidate-4",
        depth=0,
        candidate_family="shell",
        persisted_contract=_predicate_contract(),
        independent_contract=_predicate_contract(),
        persisted_valid=True,
        independent_valid=True,
        raw_measurement=0.2,
        signed_margin=0.05,
        evaluation_status=RowEvaluationStatus.COMPLETE,
        missing_reason=None,
        inclusion_probability=validity_stratum.inclusion_probability,
        inverse_probability_weight=validity_stratum.inverse_probability_weight,
    )
    return ScientificAuditPayload(
        status=status,
        readiness=readiness,
        comparison_protocol=AuditComparisonProtocol.SAME_CONTRACT,
        config=config,
        provenance=AuditProvenance(
            rollout_store_sha256=_sha("rollout-store"),
            source_store_sha256=_sha("source-store"),
            split_manifest_sha256=_sha("split-manifest"),
            raw_assets=(NamedSha256(name="mesh:target-1", sha256=_sha("mesh")),),
            evaluator_id="independent-target-reconstruction-v1",
            implementation_revision="git:0123456789abcdef",
            resolved_config_sha256=_sha("resolved-config"),
        ),
        cohort=cohort,
        endpoint_rows=(endpoint,),
        validity_rows=(validity,),
        cohort_summaries=(
            AuditCohortSummary(
                cohort_id=match_identity.exact_match_sha256,
                endpoint_row_count=1,
                validity_row_count=1,
                mandatory_status=(
                    MandatoryCohortStatus.PASS if verdict is EquivalenceVerdict.PASS else MandatoryCohortStatus.FAIL
                ),
                reason="All frozen audit gates evaluated.",
            ),
        ),
        observed_distinct_scenes=1,
        cluster_ci_eligible=False,
        cluster_ci_suppression_reason="Requires at least 20 independent scenes; observed 1.",
    )


def test_hash_priority_sampling_is_order_independent_and_records_design_weights() -> None:
    units = tuple(
        AuditSamplingUnit(unit_id=f"unit-{index}", stratum_id="near-boundary" if index < 4 else "interior")
        for index in range(8)
    )
    dimensions = {
        "near-boundary": (AuditStratumDimension(name="boundary_bin", value="near"),),
        "interior": (AuditStratumDimension(name="boundary_bin", value="interior"),),
    }

    first = freeze_hash_priority_cohort(
        units,
        {"near-boundary": 2, "interior": 1},
        seed="frozen-seed",
        dimensions=dimensions,
    )
    second = freeze_hash_priority_cohort(
        tuple(reversed(units)),
        {"interior": 1, "near-boundary": 2},
        seed="frozen-seed",
        dimensions=dimensions,
    )

    assert first == second
    assert first.population_count == 8
    assert first.audit_count == 3
    by_id = {stratum.stratum_id: stratum for stratum in first.strata}
    assert by_id["near-boundary"].population_count == 4
    assert by_id["near-boundary"].audit_count == 2
    assert by_id["near-boundary"].inclusion_probability == 0.5
    assert by_id["near-boundary"].inverse_probability_weight == 2.0
    assert by_id["interior"].inclusion_probability == 0.25
    assert by_id["interior"].inverse_probability_weight == 4.0


def test_treatment_normalization_matches_only_allowlisted_drift() -> None:
    allowlist = (TreatmentConfigPath(owner="policy", json_pointer="/selection/horizon"),)
    one_step = normalize_treatment_configs(
        {"candidate": {"radius_m": 1.0}, "policy": {"selection": {"horizon": 1}, "budget": 4}},
        allowlist,
    )
    lookahead = normalize_treatment_configs(
        {"candidate": {"radius_m": 1.0}, "policy": {"selection": {"horizon": 4}, "budget": 4}},
        allowlist,
    )

    assert one_step.normalized_context_sha256 == lookahead.normalized_context_sha256
    assert one_step.treatment_sha256 != lookahead.treatment_sha256
    assert one_step.raw_fingerprints != lookahead.raw_fingerprints

    common = {
        "root_action_set_sha256": _sha("root-actions"),
        "persisted_context_sha256": _sha("context"),
        "raw_asset_context_sha256": named_sha256_context_hash(()),
    }
    one_step_match = PolicyMatchIdentity.derive(
        treatment=PolicyTreatmentIdentity(
            semantic_role=PolicySemanticRole.ORACLE_ONE_STEP,
            treatment_id="oracle-1",
        ),
        configs=one_step,
        **common,
    )
    lookahead_match = PolicyMatchIdentity.derive(
        treatment=PolicyTreatmentIdentity(
            semantic_role=PolicySemanticRole.ORACLE_LOOKAHEAD,
            treatment_id="oracle-look",
        ),
        configs=lookahead,
        **common,
    )
    assert one_step_match.exact_match_sha256 == lookahead_match.exact_match_sha256
    assert one_step_match.treatment != lookahead_match.treatment

    nonallowlisted = normalize_treatment_configs(
        {"candidate": {"radius_m": 2.0}, "policy": {"selection": {"horizon": 4}, "budget": 4}},
        allowlist,
    )
    assert nonallowlisted.normalized_context_sha256 != lookahead.normalized_context_sha256


def test_treatment_normalization_fails_closed_on_missing_or_asymmetric_paths() -> None:
    with pytest.raises(ValueError, match="does not exist"):
        normalize_treatment_configs(
            {"policy": {"horizon": 1}},
            (TreatmentConfigPath(owner="policy", json_pointer="/missing"),),
        )
    with pytest.raises(ValueError, match="unknown config owner"):
        normalize_treatment_configs(
            {"policy": {"horizon": 1}},
            (TreatmentConfigPath(owner="candidate", json_pointer="/horizon"),),
        )
    with pytest.raises(ValueError, match="finite JSON-like"):
        normalize_treatment_configs({"policy": {"horizon": float("nan")}}, ())
    valid = normalize_treatment_configs({"policy": {"horizon": 1}}, ())
    asymmetric = valid.model_dump(mode="python")
    asymmetric["normalized_fingerprints"] = ()
    with pytest.raises(ValidationError, match="identical non-empty owner sets"):
        type(valid).model_validate(asymmetric)


def test_policy_treatment_requires_checkpoint_only_for_learned_roles() -> None:
    with pytest.raises(ValidationError, match="require model_checkpoint"):
        PolicyTreatmentIdentity(
            semantic_role=PolicySemanticRole.LEARNED_QH,
            treatment_id="qh",
        )
    learned = PolicyTreatmentIdentity(
        semantic_role=PolicySemanticRole.LEARNED_QH,
        treatment_id="qh",
        model_checkpoint_sha256=_sha("checkpoint"),
    )
    assert learned.model_checkpoint_sha256 == _sha("checkpoint")
    oracle = PolicyTreatmentIdentity(
        semantic_role=PolicySemanticRole.ORACLE_LOOKAHEAD,
        treatment_id="oracle-look",
    )
    assert oracle.model_checkpoint_sha256 is None
    with pytest.raises(ValidationError, match="must not provide model_checkpoint"):
        PolicyTreatmentIdentity(
            semantic_role=PolicySemanticRole.ORACLE_LOOKAHEAD,
            treatment_id="oracle-look",
            model_checkpoint_sha256=_sha("forged-oracle-checkpoint"),
        )


def test_hash_priority_sampling_rejects_duplicates_and_partial_allocations() -> None:
    duplicate = (
        AuditSamplingUnit(unit_id="same", stratum_id="a"),
        AuditSamplingUnit(unit_id="same", stratum_id="b"),
    )
    with pytest.raises(ValueError, match="Duplicate population unit IDs"):
        freeze_hash_priority_cohort(duplicate, {"a": 1, "b": 1}, seed="seed")

    units = (AuditSamplingUnit(unit_id="one", stratum_id="a"),)
    with pytest.raises(ValueError, match="cover exactly"):
        freeze_hash_priority_cohort(units, {}, seed="seed")
    with pytest.raises(ValueError, match="Invalid audit count 1.2"):
        freeze_hash_priority_cohort(units, {"a": 1.2}, seed="seed")


def test_frozen_numerical_contract_and_scene_gate() -> None:
    config = ScientificAuditConfig()

    assert config.endpoint_epsilon == 1e-8
    assert config.comparator_epsilon == 1e-12
    assert config.absolute_tolerance == 1e-6
    assert config.relative_tolerance == 1e-5
    assert config.eta_q_min_headroom == 0.01
    assert config.min_scenes_for_cluster_ci == MIN_SCENES_FOR_CLUSTER_CI == 20
    with pytest.raises(ValidationError):
        ScientificAuditConfig(min_scenes_for_cluster_ci=19)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ScientificAuditConfig(endpoint_epsilon=math.inf)
    with pytest.raises(ValidationError):
        ScientificAuditConfig(comparator_epsilon=1e-8)  # type: ignore[arg-type]
    for invalid in (0.0, -0.01, float("nan"), float("inf")):
        with pytest.raises(ValidationError):
            ScientificAuditConfig(eta_q_min_headroom=invalid)


def test_eta_q_headroom_gate_serializes_and_round_trips() -> None:
    config = ScientificAuditConfig(eta_q_min_headroom=0.025)

    encoded = config.model_dump_json()
    decoded = ScientificAuditConfig.model_validate_json(encoded)

    assert decoded == config
    assert decoded.eta_q_min_headroom == 0.025
    assert "eta_q_min_headroom" in encoded


def test_endpoint_equation_tolerance_and_exact_status_are_validated() -> None:
    passing = _complete_payload(endpoint_comparator_offset=5e-7)
    failing = _complete_payload(endpoint_comparator_offset=1e-3)

    assert passing.status is AuditStatus.PASS
    assert passing.endpoint_rows[0].equivalence_verdict is EquivalenceVerdict.PASS
    assert failing.status is AuditStatus.FAIL
    assert failing.endpoint_rows[0].equivalence_verdict is EquivalenceVerdict.FAIL

    invalid = passing.model_dump(mode="python")
    invalid["endpoint_rows"][0]["endpoint_gain"] = 0.9
    with pytest.raises(ValidationError, match="inconsistent endpoint_gain"):
        ScientificAuditPayload.model_validate(invalid)

    invalid_status = passing.model_dump(mode="python")
    invalid_status["status"] = AuditStatus.PARTIAL
    invalid_status["readiness"] = AuditReadiness.BLOCKED
    with pytest.raises(ValidationError, match="status/readiness"):
        ScientificAuditPayload.model_validate(invalid_status)


def test_endpoint_and_clamp_comparator_are_distinct_contracts() -> None:
    payload = _complete_payload()
    raw = payload.model_dump(mode="python")
    row = raw["endpoint_rows"][0]
    row.update(
        delta_0=0.0,
        delta_h=1.0,
        endpoint_gain=-1.0 / payload.config.endpoint_epsilon,
        independent_comparator_gain=-1.0 / payload.config.comparator_epsilon,
        comparator_gain=-1.0 / payload.config.comparator_epsilon,
        absolute_error=0.0,
        relative_error=0.0,
    )

    validated = ScientificAuditPayload.model_validate(raw)

    assert validated.endpoint_rows[0].endpoint_gain == -1e8
    assert validated.endpoint_rows[0].independent_comparator_gain == -1e12

    invalid = validated.model_dump(mode="python")
    invalid["endpoint_rows"][0]["independent_comparator_gain"] = 1.0
    with pytest.raises(ValidationError, match="inconsistent independent_comparator_gain"):
        ScientificAuditPayload.model_validate(invalid)


def test_endpoint_termination_vocabulary_and_budget_invariants_fail_closed() -> None:
    payload = _complete_payload()
    unknown = payload.model_dump(mode="python")
    unknown["endpoint_rows"][0]["termination_reason"] = "budget_exhausted"
    with pytest.raises(ValidationError):
        ScientificAuditPayload.model_validate(unknown)

    fixed_short = payload.model_dump(mode="python")
    fixed_short["endpoint_rows"][0]["achieved_steps"] = 2
    with pytest.raises(ValidationError, match="fixed_horizon"):
        ScientificAuditPayload.model_validate(fixed_short)

    early = payload.model_dump(mode="python")
    early["endpoint_rows"][0]["termination_reason"] = "terminated_early"
    early["endpoint_rows"][0]["achieved_steps"] = 0
    assert ScientificAuditPayload.model_validate(early).endpoint_rows[0].achieved_steps == 0

    early_full = payload.model_dump(mode="python")
    early_full["endpoint_rows"][0]["termination_reason"] = "terminated_early"
    with pytest.raises(ValidationError, match="shorter than budget"):
        ScientificAuditPayload.model_validate(early_full)


def test_partial_audit_remains_loadable_but_is_rejected_for_confirmatory_use() -> None:
    complete = _complete_payload()
    raw = complete.model_dump(mode="python")
    row = raw["validity_rows"][0]
    row.update(
        independent_valid=None,
        raw_measurement=None,
        signed_margin=None,
        evaluation_status=RowEvaluationStatus.BLOCKED,
        missing_reason="collision mesh was unavailable",
    )
    raw["status"] = AuditStatus.PARTIAL
    raw["readiness"] = AuditReadiness.BLOCKED
    partial = ScientificAuditPayload.model_validate(raw)
    artifact = seal_scientific_audit(partial)

    assert artifact.status is AuditStatus.PARTIAL
    with pytest.raises(ValueError, match="Confirmatory evidence requires"):
        require_confirmatory_audit(artifact)


def test_duplicate_rows_nonfinite_values_and_extra_fields_are_rejected() -> None:
    payload = _complete_payload()
    duplicate = payload.model_dump(mode="python")
    duplicate["endpoint_rows"] = (duplicate["endpoint_rows"][0], duplicate["endpoint_rows"][0])
    with pytest.raises(ValidationError, match="Duplicate audit row unit IDs"):
        ScientificAuditPayload.model_validate(duplicate)

    nonfinite = payload.model_dump(mode="python")
    nonfinite["endpoint_rows"][0]["delta_h"] = math.nan
    with pytest.raises(ValidationError):
        ScientificAuditPayload.model_validate(nonfinite)

    extra = payload.model_dump(mode="python")
    extra["unexpected"] = "not allowed"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ScientificAuditPayload.model_validate(extra)


def test_serialization_is_byte_stable_and_round_trips_with_verified_sha(tmp_path: Path) -> None:
    payload = _complete_payload()
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"

    first = write_scientific_audit(first_path, payload)
    second = write_scientific_audit(second_path, payload)
    loaded = load_scientific_audit(first_path, require_confirmatory=True)

    assert first == second == loaded
    assert first_path.read_bytes() == second_path.read_bytes()
    assert first_path.read_bytes() == canonical_scientific_audit_bytes(first, include_bundle_sha256=True)
    assert first.bundle_sha256 == hashlib.sha256(canonical_scientific_audit_bytes(payload)).hexdigest()


def test_loader_rejects_duplicate_json_keys_nonfinite_constants_and_hash_mismatch(tmp_path: Path) -> None:
    duplicate_path = tmp_path / "duplicate.json"
    duplicate_path.write_text('{"schema_version":"a","schema_version":"b"}', encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        load_scientific_audit(duplicate_path)

    nonfinite_path = tmp_path / "nonfinite.json"
    nonfinite_path.write_text('{"value":NaN}', encoding="utf-8")
    with pytest.raises(ValueError, match="Nonfinite JSON constant"):
        load_scientific_audit(nonfinite_path)

    artifact = seal_scientific_audit(_complete_payload())
    tampered = artifact.model_dump(mode="python")
    tampered["bundle_sha256"] = _sha("wrong")
    mismatched = ScientificAuditArtifact.model_validate(tampered)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_scientific_audit_sha256(mismatched)

    mismatch_path = tmp_path / "mismatch.json"
    mismatch_path.write_text(
        json.dumps(ScientificAuditArtifact.model_validate(tampered).model_dump(mode="json")), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        load_scientific_audit(mismatch_path)
