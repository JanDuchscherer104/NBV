from __future__ import annotations

import hashlib
from typing import cast

import pytest

from aria_nbv.rollouts.inspection import policy_effect_evidence
from aria_nbv.rollouts.scientific_audit import (
    AuditCohortSummary,
    AuditComparisonProtocol,
    AuditProvenance,
    AuditReadiness,
    AuditStatus,
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
    TreatmentConfigPath,
    ValidityAuditRow,
    ValidityPredicateContract,
    canonical_scientific_audit_bytes,
    named_sha256_context_hash,
    normalize_treatment_configs,
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _path_contract() -> ValidityPredicateContract:
    return ValidityPredicateContract.derive(
        predicate_kind="path",
        owner="motion-validator",
        name="max-step-v1",
        comparison_operator="<=",
        threshold=1.0,
        unit="m",
        frame="ARIA world",
        semantic_config_sha256=_sha("max-step-v1-config"),
    )


def _endpoint_row(
    *,
    scene: str,
    replicate: str,
    role: PolicySemanticRole,
    gain: float,
    root: str = "shared-root",
    normalized_setting: str = "shared",
    persisted_context: str | None = None,
    raw_asset: str = "shared-mesh",
    termination_reason: str = "fixed_horizon",
    blocked: bool = False,
    unit_suffix: str = "",
) -> EndpointAuditRow:
    treatment_id = f"{role.value}-treatment"
    configs = normalize_treatment_configs(
        {"policy": {"shared": normalized_setting, "treatment": treatment_id}},
        (TreatmentConfigPath(owner="policy", json_pointer="/treatment"),),
    )
    raw_assets = (NamedSha256(name="target_mesh", sha256=_sha(raw_asset)),)
    match = PolicyMatchIdentity.derive(
        treatment=PolicyTreatmentIdentity(
            semantic_role=role,
            treatment_id=treatment_id,
            model_checkpoint_sha256=(
                _sha(f"checkpoint:{role.value}")
                if role in {PolicySemanticRole.LEARNED_ONE_STEP, PolicySemanticRole.LEARNED_QH}
                else None
            ),
        ),
        configs=configs,
        root_action_set_sha256=_sha(root),
        persisted_context_sha256=_sha(persisted_context or f"{scene}:{replicate}:context"),
        raw_asset_context_sha256=named_sha256_context_hash(raw_assets),
    )
    if blocked:
        return EndpointAuditRow(
            unit_id=f"{scene}:{replicate}:{role.value}{unit_suffix}",
            stratum_id="endpoint",
            match_identity=match,
            rollout_row_id=0,
            scene_id=scene,
            rollout_id=f"rollout:{replicate}:{role.value}",
            source_sample_key=f"sample:{replicate}",
            source_store_sha256=None,
            split_manifest_sha256=None,
            raw_assets=raw_assets,
            target_id="target-1",
            pose_chain_sha256=_sha(f"downstream:{role.value}"),
            evaluation_status=RowEvaluationStatus.BLOCKED,
            delta_0=None,
            delta_h=None,
            endpoint_gain=None,
            comparator_gain=None,
            independent_comparator_gain=None,
            comparator_gamma=None,
            absolute_error=None,
            relative_error=None,
            equivalence_verdict=EquivalenceVerdict.BLOCKED,
            achieved_steps=None,
            budget=None,
            termination_reason=None,
            missing_reason="endpoint evaluator failed",
        )

    config = ScientificAuditConfig()
    delta_0 = 1.0
    delta_h = delta_0 - gain * (delta_0 + config.endpoint_epsilon)
    comparator = (delta_0 - delta_h) / max(delta_0, config.comparator_epsilon)
    early = termination_reason == "terminated_early"
    return EndpointAuditRow(
        unit_id=f"{scene}:{replicate}:{role.value}{unit_suffix}",
        stratum_id="endpoint",
        match_identity=match,
        rollout_row_id=0,
        scene_id=scene,
        rollout_id=f"rollout:{replicate}:{role.value}",
        source_sample_key=f"sample:{replicate}",
        source_store_sha256=_sha("source-store"),
        split_manifest_sha256=_sha("split-manifest"),
        raw_assets=raw_assets,
        target_id="target-1",
        pose_chain_sha256=_sha(f"downstream:{role.value}"),
        evaluation_status=RowEvaluationStatus.COMPLETE,
        delta_0=delta_0,
        delta_h=delta_h,
        endpoint_gain=gain,
        comparator_gain=comparator,
        independent_comparator_gain=comparator,
        comparator_gamma=1.0,
        absolute_error=0.0,
        relative_error=0.0,
        equivalence_verdict=EquivalenceVerdict.PASS,
        achieved_steps=1 if early else 3,
        budget=3,
        termination_reason=termination_reason,  # type: ignore[arg-type]
        missing_reason=None,
    )


def _artifact(
    rows: list[EndpointAuditRow],
    *,
    validity_count: int = 0,
    protocol: AuditComparisonProtocol = AuditComparisonProtocol.SAME_CONTRACT,
    status: AuditStatus = AuditStatus.PASS,
    readiness: AuditReadiness = AuditReadiness.CONFIRMATORY,
    mandatory_status: MandatoryCohortStatus = MandatoryCohortStatus.PASS,
    eta_q_min_headroom: float = 0.01,
) -> ScientificAuditArtifact:
    provenance = AuditProvenance(
        rollout_store_sha256=_sha("rollout-store"),
        source_store_sha256=_sha("source-store"),
        split_manifest_sha256=_sha("split-manifest"),
        raw_assets=(NamedSha256(name="campaign", sha256=_sha("campaign-assets")),),
        evaluator_id="independent-endpoint-v1",
        implementation_revision="git:test",
        resolved_config_sha256=_sha("resolved-config"),
    )
    endpoint_counts: dict[str, int] = {}
    for row in rows:
        endpoint_counts[row.cohort_id] = endpoint_counts.get(row.cohort_id, 0) + 1
    validity_cohort_id = rows[0].cohort_id if rows else _sha("validity-only-cohort")
    validity_rows = tuple(
        ValidityAuditRow(
            unit_id=f"validity-{index}",
            stratum_id="validity",
            cohort_id=validity_cohort_id,
            scene_id=rows[0].scene_id if rows else "scene-validity",
            rollout_id="rollout-validity",
            candidate_id=f"candidate-{index}",
            depth=0,
            candidate_family="shell",
            persisted_contract=_path_contract(),
            independent_contract=_path_contract(),
            persisted_valid=True,
            independent_valid=True,
            raw_measurement=0.5,
            signed_margin=0.5,
            evaluation_status=RowEvaluationStatus.COMPLETE,
            inclusion_probability=1.0,
            inverse_probability_weight=1.0,
        )
        for index in range(validity_count)
    )
    validity_counts = {validity_cohort_id: validity_count} if validity_count else {}
    summary_cohort_ids = sorted(set(endpoint_counts) | set(validity_counts))
    cohort_summaries = tuple(
        AuditCohortSummary(
            cohort_id=cohort_id,
            endpoint_row_count=endpoint_counts.get(cohort_id, 0),
            validity_row_count=validity_counts.get(cohort_id, 0),
            mandatory_status=mandatory_status,
            reason="test cohort gate",
        )
        for cohort_id in summary_cohort_ids
    )
    artifact = ScientificAuditArtifact.model_construct(
        status=status,
        readiness=readiness,
        comparison_protocol=protocol,
        config=ScientificAuditConfig(eta_q_min_headroom=eta_q_min_headroom),
        provenance=provenance,
        endpoint_rows=tuple(rows),
        validity_rows=validity_rows,
        cohort_summaries=cohort_summaries,
        bundle_sha256=_sha("bundle"),
    )
    digest = hashlib.sha256(canonical_scientific_audit_bytes(artifact)).hexdigest()
    return artifact.model_copy(update={"bundle_sha256": digest})


def _complete_policy_rows(
    scene: str,
    replicate: str,
    *,
    learned: float = 0.2,
    qh: float = 0.4,
    oracle_one: float = 0.3,
    oracle_look: float = 0.6,
) -> list[EndpointAuditRow]:
    return [
        _endpoint_row(
            scene=scene,
            replicate=replicate,
            role=PolicySemanticRole.LEARNED_ONE_STEP,
            gain=learned,
        ),
        _endpoint_row(scene=scene, replicate=replicate, role=PolicySemanticRole.LEARNED_QH, gain=qh),
        _endpoint_row(
            scene=scene,
            replicate=replicate,
            role=PolicySemanticRole.ORACLE_ONE_STEP,
            gain=oracle_one,
        ),
        _endpoint_row(
            scene=scene,
            replicate=replicate,
            role=PolicySemanticRole.ORACLE_LOOKAHEAD,
            gain=oracle_look,
        ),
    ]


def _summary(evidence: dict[str, object], contrast: str) -> dict[str, object]:
    summaries = evidence["summary_rows"]
    assert isinstance(summaries, list)
    return next(row for row in summaries if row["contrast"] == contrast)


def _evidence_rows(evidence: dict[str, object], key: str) -> list[dict[str, object]]:
    """Narrow one JSON-ready row collection for static test checks."""

    rows = evidence[key]
    assert isinstance(rows, list)
    return cast(list[dict[str, object]], rows)


def _evidence_mapping(evidence: dict[str, object], key: str) -> dict[str, object]:
    """Narrow one JSON-ready nested mapping for static test checks."""

    value = evidence[key]
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def test_exact_pairing_uses_shared_root_not_divergent_downstream_outcomes() -> None:
    rows = _complete_policy_rows("scene-1", "pair-1")
    assert len({row.pose_chain_sha256 for row in rows}) == 4

    evidence = policy_effect_evidence(_artifact(rows), bootstrap_samples=32)

    raw = _summary(evidence, "raw_qh")
    look = _summary(evidence, "delta_look")
    assert raw["pair_count"] == 1
    assert raw["scene_macro_mean"] == pytest.approx(0.2)
    assert look["scene_macro_mean"] == pytest.approx(0.3)


@pytest.mark.parametrize(
    ("root", "normalized_setting", "persisted_context", "raw_asset", "reason"),
    [
        ("different-root", "shared", None, "shared-mesh", "root_action_set_mismatch"),
        ("shared-root", "nonallowlisted-drift", None, "shared-mesh", "normalized_config_mismatch"),
        ("shared-root", "shared", "different-context", "shared-mesh", "persisted_context_mismatch"),
        ("shared-root", "shared", None, "different-mesh", "raw_asset_context_mismatch"),
    ],
)
def test_exact_identity_drift_blocks_instead_of_selecting_a_near_match(
    root: str,
    normalized_setting: str,
    persisted_context: str | None,
    raw_asset: str,
    reason: str,
) -> None:
    learned = _endpoint_row(
        scene="scene-1",
        replicate="pair-1",
        role=PolicySemanticRole.LEARNED_ONE_STEP,
        gain=0.2,
    )
    qh = _endpoint_row(
        scene="scene-1",
        replicate="pair-1",
        role=PolicySemanticRole.LEARNED_QH,
        gain=0.5,
        root=root,
        normalized_setting=normalized_setting,
        persisted_context=persisted_context,
        raw_asset=raw_asset,
    )

    evidence = policy_effect_evidence(_artifact([learned, qh]), bootstrap_samples=32)
    exclusions = _evidence_rows(evidence, "exclusion_rows")
    assert _summary(evidence, "raw_qh")["pair_count"] == 0
    assert reason in {row["reason"] for row in exclusions}


def test_missing_duplicate_checkpoint_and_source_rows_fail_closed() -> None:
    learned, qh, *_ = _complete_policy_rows("scene-1", "pair-1")
    duplicate_qh = qh.model_copy(update={"unit_id": f"{qh.unit_id}:duplicate"})
    treatment = learned.match_identity.treatment.model_copy(update={"model_checkpoint_sha256": None})
    missing_checkpoint = learned.model_copy(
        update={"match_identity": learned.match_identity.model_copy(update={"treatment": treatment})}
    )
    wrong_source = qh.model_copy(update={"source_store_sha256": _sha("wrong-source")})
    wrong_assets = qh.model_copy(update={"raw_assets": (NamedSha256(name="target_mesh", sha256=_sha("wrong-mesh")),)})

    duplicate = policy_effect_evidence(_artifact([learned, qh, duplicate_qh]), bootstrap_samples=32)
    missing = policy_effect_evidence(_artifact([qh]), bootstrap_samples=32)
    checkpoint = policy_effect_evidence(_artifact([missing_checkpoint, qh]), bootstrap_samples=32)
    source = policy_effect_evidence(_artifact([learned, wrong_source]), bootstrap_samples=32)
    assets = policy_effect_evidence(_artifact([learned, wrong_assets]), bootstrap_samples=32)

    assert _summary(duplicate, "raw_qh")["duplicate_role_count"] == 1
    assert _summary(missing, "raw_qh")["missing_role_count"] == 1
    assert "missing_checkpoint" in {row["reason"] for row in _evidence_rows(checkpoint, "exclusion_rows")}
    assert "source_store_mismatch" in {row["reason"] for row in _evidence_rows(source, "exclusion_rows")}
    assert "raw_asset_context_mismatch" in {row["reason"] for row in _evidence_rows(assets, "exclusion_rows")}


def test_scene_macro_equal_weights_scenes_not_pairs() -> None:
    rows = [
        *_complete_policy_rows("scene-a", "a1", learned=0.0, qh=0.5),
        *_complete_policy_rows("scene-a", "a2", learned=0.0, qh=0.5),
        *_complete_policy_rows("scene-b", "b1", learned=0.0, qh=0.99999999),
    ]

    evidence = policy_effect_evidence(_artifact(rows), bootstrap_samples=32)
    raw = _summary(evidence, "raw_qh")

    assert raw["pair_count"] == 3
    assert raw["scene_count"] == 2
    assert raw["scene_macro_mean"] == pytest.approx(0.75)
    assert raw["cluster_ci_low"] is None


@pytest.mark.parametrize("scene_count", [0, 1, 19, 20])
def test_scene_cluster_ci_gate_is_per_contrast_and_deterministic(scene_count: int) -> None:
    rows: list[EndpointAuditRow] = []
    for index in range(scene_count):
        rows.extend(
            _complete_policy_rows(
                f"scene-{index:02d}",
                f"pair-{index:02d}",
                learned=0.1,
                qh=0.2 + index / 100.0,
            )[:2]
        )
    artifact = _artifact(rows)

    first = policy_effect_evidence(artifact, bootstrap_samples=128, confidence=0.9, seed=17)
    second = policy_effect_evidence(artifact, bootstrap_samples=128, confidence=0.9, seed=17)
    summary = _summary(first, "raw_qh")

    assert first == second
    assert summary["estimable"] is (scene_count > 0)
    assert (summary["cluster_ci_low"] is not None) is (scene_count >= 20)
    assert summary["cluster_bootstrap_samples"] == (128 if scene_count >= 20 else 0)
    assert _summary(first, "delta_look")["cluster_ci_low"] is None


def test_eta_q_uses_audited_j_without_epsilon_and_retains_raw_qh_effect() -> None:
    rows: list[EndpointAuditRow] = []
    cases = (
        ("negative", 0.2, 0.4, 0.1, "eta_denominator_negative"),
        ("zero", 0.2, 0.4, 0.2, "eta_denominator_zero"),
        ("small", 0.2, 0.4, 0.205, "eta_denominator_below_threshold"),
        ("eligible", 0.2, 0.4, 0.6, None),
    )
    for replicate, learned, qh, look, _reason in cases:
        rows.extend(
            _complete_policy_rows(
                "scene-1",
                replicate,
                learned=learned,
                qh=qh,
                oracle_look=look,
            )
        )

    evidence = policy_effect_evidence(_artifact(rows, eta_q_min_headroom=0.01), bootstrap_samples=32)
    raw = _summary(evidence, "raw_qh")
    eta = _summary(evidence, "eta_q")
    reasons = {row["reason"] for row in _evidence_rows(evidence, "exclusion_rows") if row["contrast"] == "eta_q"}

    assert raw["pair_count"] == 4
    assert eta["pair_count"] == 1
    assert eta["scene_macro_mean"] == pytest.approx(0.5)
    assert {case[4] for case in cases if case[4] is not None}.issubset(reasons)
    denominator = _evidence_mapping(evidence, "headroom_denominator_summary")
    assert denominator["count"] == 4
    assert denominator["eligible_count"] == 1
    assert denominator["min"] == pytest.approx(-0.1)


def test_early_absorbing_endpoint_is_included_but_blocked_endpoint_is_excluded() -> None:
    learned = _endpoint_row(
        scene="scene-1",
        replicate="pair-1",
        role=PolicySemanticRole.LEARNED_ONE_STEP,
        gain=0.2,
        termination_reason="terminated_early",
    )
    qh = _endpoint_row(
        scene="scene-1",
        replicate="pair-1",
        role=PolicySemanticRole.LEARNED_QH,
        gain=0.5,
        termination_reason="terminated_early",
    )
    blocked = _endpoint_row(
        scene="scene-2",
        replicate="pair-2",
        role=PolicySemanticRole.LEARNED_QH,
        gain=0.0,
        blocked=True,
    )

    evidence = policy_effect_evidence(_artifact([learned, qh, blocked]), bootstrap_samples=32)

    assert _summary(evidence, "raw_qh")["pair_count"] == 1
    assert "blocked_endpoint" in {row["reason"] for row in _evidence_rows(evidence, "exclusion_rows")}


def test_validity_population_never_changes_endpoint_inference() -> None:
    rows = _complete_policy_rows("scene-1", "pair-1")

    without_validity = policy_effect_evidence(_artifact(rows), bootstrap_samples=32)
    with_validity = policy_effect_evidence(_artifact(rows, validity_count=100), bootstrap_samples=32)

    assert without_validity["pair_rows"] == with_validity["pair_rows"]
    assert without_validity["scene_rows"] == with_validity["scene_rows"]
    assert without_validity["summary_rows"] == with_validity["summary_rows"]
    assert with_validity["validity_row_count_ignored"] == 100


def test_characterization_protocol_has_no_effect_estimate() -> None:
    rows = _complete_policy_rows("scene-1", "pair-1")

    evidence = policy_effect_evidence(
        _artifact(rows, protocol=AuditComparisonProtocol.ROBUSTNESS_CHARACTERIZATION),
        bootstrap_samples=32,
    )

    assert _summary(evidence, "raw_qh")["estimable"] is False
    assert "comparison_protocol_mismatch" in {row["reason"] for row in _evidence_rows(evidence, "exclusion_rows")}


@pytest.mark.parametrize(
    ("status", "readiness", "reason"),
    [
        (AuditStatus.FAIL, AuditReadiness.BLOCKED, "artifact_status_not_pass"),
        (AuditStatus.PARTIAL, AuditReadiness.BLOCKED, "artifact_status_not_pass"),
        (AuditStatus.PASS, AuditReadiness.BLOCKED, "artifact_not_confirmatory"),
    ],
)
def test_nonconfirmatory_artifact_emits_blockers_but_no_effects(
    status: AuditStatus,
    readiness: AuditReadiness,
    reason: str,
) -> None:
    evidence = policy_effect_evidence(
        _artifact(_complete_policy_rows("scene-1", "pair-1"), status=status, readiness=readiness),
        bootstrap_samples=32,
    )

    assert evidence["pair_rows"] == []
    assert all(_summary(evidence, contrast)["estimable"] is False for contrast in ("raw_qh", "delta_look", "eta_q"))
    assert reason in {row["reason"] for row in _evidence_rows(evidence, "exclusion_rows")}


def test_failed_endpoint_equivalence_and_cohort_gate_block_effects() -> None:
    rows = _complete_policy_rows("scene-1", "pair-1")
    failed_qh = rows[1].model_copy(update={"equivalence_verdict": EquivalenceVerdict.FAIL})
    equivalence = policy_effect_evidence(_artifact([rows[0], failed_qh]), bootstrap_samples=32)
    cohort = policy_effect_evidence(
        _artifact(rows[:2], mandatory_status=MandatoryCohortStatus.FAIL),
        bootstrap_samples=32,
    )

    assert _summary(equivalence, "raw_qh")["pair_count"] == 0
    assert "endpoint_equivalence_not_pass" in {row["reason"] for row in _evidence_rows(equivalence, "exclusion_rows")}
    assert _summary(cohort, "raw_qh")["pair_count"] == 0
    assert "cohort_mandatory_not_pass" in {row["reason"] for row in _evidence_rows(cohort, "exclusion_rows")}


def test_eta_threshold_comes_only_from_artifact_config() -> None:
    rows = _complete_policy_rows("scene-1", "pair-1", learned=0.2, qh=0.4, oracle_look=0.25)

    blocked = policy_effect_evidence(_artifact(rows, eta_q_min_headroom=0.1), bootstrap_samples=32)
    eligible = policy_effect_evidence(_artifact(rows, eta_q_min_headroom=0.01), bootstrap_samples=32)

    assert _summary(blocked, "eta_q")["pair_count"] == 0
    assert _summary(eligible, "eta_q")["pair_count"] == 1
    assert eligible["eta_headroom_threshold"] == 0.01
    assert eligible["eta_headroom_threshold_provenance"] == "artifact.config.eta_q_min_headroom"


def test_pass_artifact_with_wrong_bundle_sha_is_rejected_before_reduction() -> None:
    artifact = _artifact(_complete_policy_rows("scene-1", "pair-1"))
    corrupted = artifact.model_copy(update={"bundle_sha256": _sha("wrong-bundle")})

    with pytest.raises(ValueError, match="bundle SHA-256 mismatch"):
        policy_effect_evidence(corrupted, bootstrap_samples=32)
