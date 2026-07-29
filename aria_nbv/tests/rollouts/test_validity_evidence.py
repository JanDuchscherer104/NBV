from __future__ import annotations

from collections.abc import Iterable
from typing import cast

import pytest
from pydantic import ValidationError

from aria_nbv.rollouts.inspection import candidate_validity_evidence, validity_audit_evidence
from aria_nbv.rollouts.scientific_audit import (
    AuditCohortSummary,
    AuditComparisonProtocol,
    AuditReadiness,
    AuditSamplingUnit,
    AuditStatus,
    AuditStratumDimension,
    MandatoryCohortStatus,
    RowEvaluationStatus,
    ScientificAuditPayload,
    ValidityAuditRow,
    ValidityPredicateContract,
    freeze_hash_priority_cohort,
    seal_scientific_audit,
)
from aria_nbv.rollouts.trace import INVALID_REASON_CODES
from aria_nbv.rollouts.zarr_store import ROLLOUT_ZARR_SCHEMA_VERSION
from tests.rollouts.test_scientific_audit import _complete_payload


def _candidate(
    candidate_id: int,
    *,
    cohort: str = "cohort-a",
    scene: str = "scene-a",
    step: int = 0,
    actor: bool | None = True,
    oracle: bool | None = True,
    q_train: bool | None = True,
    selected: bool | None = False,
    reason_bitset: int | None = 1,
) -> dict[str, object]:
    return {
        "candidate_row_id": candidate_id,
        "generation_cohort_id": cohort,
        "policy": "policy",
        "horizon": 2,
        "acquisition_budget_steps": 2,
        "branch_factor": 1,
        "beam_width": 1,
        "temperature": 1.0,
        "candidate_config": f"candidate-{cohort}",
        "rollout_config": "rollout",
        "branch_schedule": "schedule",
        "rollout_row_id": 0 if scene == "scene-a" else 1,
        "step_row_id": step,
        "scene": scene,
        "strategy": "target",
        "position": "shell",
        "mixture": "mixed",
        "actor_action": actor,
        "oracle_label": oracle,
        "q_train": q_train,
        "selected": selected,
        "invalid_reason_bitset": reason_bitset,
        "target_rri": -1000.0,
    }


def _find(rows: Iterable[dict[str, object]], **expected: object) -> dict[str, object]:
    return next(row for row in rows if all(row.get(key) == value for key, value in expected.items()))


def _rows(value: object) -> list[dict[str, object]]:
    assert isinstance(value, list)
    return cast(list[dict[str, object]], value)


def _predicate_contract(kind: str, *, threshold: float = 1.0, semantic: str = "default") -> ValidityPredicateContract:
    from tests.rollouts.test_scientific_audit import _sha

    return ValidityPredicateContract.derive(
        predicate_kind=kind,  # type: ignore[arg-type]
        owner="motion_validator",
        name=f"{kind}:v1",
        comparison_operator="<=",
        threshold=threshold,
        unit="m",
        frame="ARIA world",
        semantic_config_sha256=_sha(f"{kind}:{threshold}:{semantic}"),
    )


def test_candidate_validity_conserves_counts_and_keeps_missing_stages_explicit() -> None:
    rows = [
        _candidate(0, selected=True),
        _candidate(
            1, actor=False, oracle=False, q_train=False, reason_bitset=1 << INVALID_REASON_CODES["POSE_OUT_OF_EXTENT"]
        ),
        _candidate(2, actor=None, oracle=None, q_train=None, selected=None, reason_bitset=None),
    ]
    rows[2]["strategy"] = None

    evidence = candidate_validity_evidence(rows)

    assert all(row["conserved"] for row in evidence["conservation_rows"])
    assert {row["observed_count"] for row in evidence["conservation_rows"]} == {3}
    assert _find(evidence["missing_stage_rows"], stage="proposal")["missing_count"] == 1
    assert _find(evidence["missing_stage_rows"], stage="oracle_label")["missing_count"] == 1
    assert _find(evidence["flow_rows"], target="missing_proposal")["count"] == 1
    assert _find(evidence["flow_rows"], target="selection_unavailable")["count"] == 1


def test_mask_intersections_retain_all_cells_and_fail_invalid_implications() -> None:
    rows = [
        _candidate(0, actor=True, oracle=True, q_train=True, selected=True),
        _candidate(1, actor=False, oracle=False, q_train=True, selected=False),
        _candidate(2, actor=False, oracle=True, q_train=False, selected=True),
        _candidate(3, actor=True, oracle=None, q_train=False, selected=False),
    ]

    evidence = candidate_validity_evidence(rows)
    intersections = evidence["mask_intersection_rows"]

    assert len(intersections) == 17
    assert _find(intersections, actor_action=False, oracle_label=False, q_train=True, selected=False)["count"] == 1
    assert (
        _find(intersections, actor_action=True, oracle_label=None, q_train=False, selected=False)["available"] is False
    )
    q_actor = _find(evidence["invalid_implication_rows"], implication="q_train_implies_actor_valid")
    assert q_actor["violation_count"] == 1
    assert q_actor["unavailable_count"] == 0
    assert q_actor["status"] == "fail"
    assert (
        _find(evidence["invalid_implication_rows"], implication="selected_implies_actor_valid")["violation_count"] == 1
    )


def test_reason_bitset_intersections_preserve_every_reason_and_version() -> None:
    combined = (1 << INVALID_REASON_CODES["CLEARANCE_TOO_SMALL"]) | (
        1 << INVALID_REASON_CODES["PATH_SEGMENT_COLLISION"]
    )
    evidence = candidate_validity_evidence(
        [_candidate(0, actor=False, reason_bitset=combined), _candidate(1, actor=False, reason_bitset=combined)]
    )

    row = _find(
        evidence["reason_intersection_rows"],
        invalid_reason_bitset=combined,
        aggregation_level="cohort_scene_macro",
    )
    assert row["reason_names"] == ("CLEARANCE_TOO_SMALL", "PATH_SEGMENT_COLLISION")
    assert row["intersection_size"] == 2
    assert row["reason_version"] == "rollout-invalidity-v1"
    assert row["mean_state_fraction"] == 1.0


def test_conditional_coverage_macros_state_then_scene_not_candidate_mass() -> None:
    rows = [_candidate(index, scene="scene-a", step=0, actor=True, oracle=True) for index in range(10)]
    rows.extend(
        (
            _candidate(10, scene="scene-b", step=0, actor=False, oracle=False, q_train=False),
            _candidate(11, scene="scene-b", step=1, actor=False, oracle=False, q_train=False),
        )
    )

    evidence = candidate_validity_evidence(rows)
    actor = _find(
        evidence["conditional_availability_rows"],
        evidence="actor_valid_availability",
        family_dimension="all",
        aggregation_level="cohort_scene_macro",
    )
    oracle = _find(
        evidence["conditional_availability_rows"],
        evidence="oracle_label_coverage_among_actor_valid",
        family_dimension="all",
        aggregation_level="cohort_scene_macro",
    )

    assert actor["mean_state_fraction"] == pytest.approx(0.5)
    assert actor["scene_count"] == 2
    assert actor["state_count"] == 3
    assert oracle["mean_state_fraction"] == 1.0
    assert oracle["scene_count"] == 1
    assert oracle["undefined_state_count"] == 2


def test_candidate_validity_keeps_exact_cohorts_and_is_order_invariant() -> None:
    rows = [_candidate(index, cohort="a") for index in range(20_000)]
    rows.append(_candidate(20_000, cohort="b", actor=False, oracle=False, q_train=False))

    forward = candidate_validity_evidence(rows)
    reverse = candidate_validity_evidence(reversed(rows))

    assert forward == reverse
    assert {row["generation_cohort_id"] for row in forward["conservation_rows"]} == {"a", "b"}
    assert (
        sum(row["expected_count"] for row in forward["conservation_rows"] if row["transition"] == "sampled -> proposal")
        == 20_001
    )


def _audit_artifact(
    specs: tuple[dict[str, object], ...],
    *,
    comparison_protocol: AuditComparisonProtocol = AuditComparisonProtocol.SAME_CONTRACT,
):
    base = _complete_payload()
    units = [AuditSamplingUnit(unit_id="endpoint-1", stratum_id="endpoint")]
    allocations: dict[str, int] = {"endpoint": 1}
    dimensions = {"endpoint": (AuditStratumDimension(name="row_kind", value="endpoint"),)}
    selected_by_stratum: dict[str, str] = {}
    for index, spec in enumerate(specs):
        stratum = f"validity-{index}"
        population = int(spec["population"])
        units.extend(
            AuditSamplingUnit(unit_id=f"{stratum}-population-{item}", stratum_id=stratum) for item in range(population)
        )
        allocations[stratum] = 1
        dimensions[stratum] = (AuditStratumDimension(name="predicate_kind", value=str(spec["kind"])),)
    cohort = freeze_hash_priority_cohort(tuple(units), allocations, seed="validity-evidence", dimensions=dimensions)
    for unit_id in cohort.selected_unit_ids:
        if unit_id != "endpoint-1":
            selected_by_stratum[
                next(
                    item.stratum_id
                    for item in cohort.strata
                    if unit_id in {candidate.unit_id for candidate in units if candidate.stratum_id == item.stratum_id}
                )
            ] = unit_id
    strata = {item.stratum_id: item for item in cohort.strata}
    validity_rows = []
    for index, spec in enumerate(specs):
        stratum_id = f"validity-{index}"
        stratum = strata[stratum_id]
        status = cast(RowEvaluationStatus, spec.get("status", RowEvaluationStatus.COMPLETE))
        validity_rows.append(
            ValidityAuditRow(
                unit_id=selected_by_stratum[stratum_id],
                stratum_id=stratum_id,
                cohort_id=base.endpoint_rows[0].match_identity.exact_match_sha256,
                scene_id=str(spec.get("scene", "scene-1")),
                rollout_id="rollout-1",
                candidate_id=f"candidate-{index}",
                depth=0,
                candidate_family="shell",
                persisted_contract=_predicate_contract(str(spec["kind"])),
                independent_contract=_predicate_contract(
                    str(spec["kind"]),
                    threshold=float(spec.get("independent_threshold", 1.0)),
                    semantic=str(spec.get("independent_semantic", "default")),
                ),
                persisted_valid=bool(spec["persisted"]),
                independent_valid=None if status is RowEvaluationStatus.BLOCKED else bool(spec["independent"]),
                raw_measurement=None if status is RowEvaluationStatus.BLOCKED else float(spec["measurement"]),
                signed_margin=None if status is RowEvaluationStatus.BLOCKED else 1.0 - float(spec["measurement"]),
                evaluation_status=status,
                missing_reason="label unavailable" if status is RowEvaluationStatus.BLOCKED else None,
                inclusion_probability=stratum.inclusion_probability,
                inverse_probability_weight=stratum.inverse_probability_weight,
            )
        )
    readiness = (
        AuditReadiness.CONFIRMATORY
        if comparison_protocol is AuditComparisonProtocol.SAME_CONTRACT
        and all(row.independent_valid is not None for row in validity_rows)
        else AuditReadiness.PILOT
        if comparison_protocol is AuditComparisonProtocol.ROBUSTNESS_CHARACTERIZATION
        and all(row.independent_valid is not None for row in validity_rows)
        else AuditReadiness.BLOCKED
    )
    status = {
        AuditReadiness.CONFIRMATORY: AuditStatus.PASS,
        AuditReadiness.PILOT: AuditStatus.CHARACTERIZATION,
        AuditReadiness.BLOCKED: AuditStatus.PARTIAL,
    }[readiness]
    payload = ScientificAuditPayload(
        **{
            **base.model_dump(mode="python"),
            "status": status,
            "readiness": readiness,
            "comparison_protocol": comparison_protocol,
            "cohort": cohort,
            "validity_rows": tuple(validity_rows),
            "cohort_summaries": (
                AuditCohortSummary(
                    cohort_id=base.endpoint_rows[0].match_identity.exact_match_sha256,
                    endpoint_row_count=1,
                    validity_row_count=len(validity_rows),
                    mandatory_status=MandatoryCohortStatus.PASS,
                    reason="Validity reducer fixture.",
                ),
            ),
            "observed_distinct_scenes": len({base.endpoint_rows[0].scene_id, *(row.scene_id for row in validity_rows)}),
            "cluster_ci_eligible": False,
            "cluster_ci_suppression_reason": "Below frozen scene threshold.",
        }
    )
    return seal_scientific_audit(payload)


def test_weighted_confusion_and_boundary_bins_are_hand_calculated() -> None:
    artifact = _audit_artifact(
        (
            {"kind": "state", "population": 1, "persisted": True, "independent": True, "measurement": 0.9},
            {"kind": "state", "population": 3, "persisted": True, "independent": False, "measurement": 1.2},
            {"kind": "state", "population": 2, "persisted": False, "independent": True, "measurement": 0.95},
            {"kind": "path", "population": 4, "persisted": False, "independent": False, "measurement": 1.5},
            {"kind": "combined_actor", "population": 1, "persisted": True, "independent": True, "measurement": 1.0},
        )
    )

    evidence = validity_audit_evidence(artifact, boundary_edges=(-float("inf"), 0.0, 0.1, float("inf")))
    state = _find(_rows(evidence["confusion_rows"]), predicate_kind="state")

    assert state["weighted_true_positive"] == 1.0
    assert state["weighted_false_positive"] == 3.0
    assert state["weighted_false_negative"] == 2.0
    assert state["weighted_true_negative"] == 0.0
    assert state["weighted_population"] == 6.0
    assert state["weighted_agreement"] == pytest.approx(1 / 6)
    assert state["weighted_persisted_precision"] == pytest.approx(1 / 4)
    near_boundary = _find(
        _rows(evidence["boundary_rows"]),
        predicate_kind="state",
        boundary_bin_left=0.0,
        boundary_bin_right=0.1,
    )
    assert near_boundary["weighted_population"] == 3.0
    assert near_boundary["weighted_agreement"] == pytest.approx(1 / 3)
    boundary = _find(
        _rows(evidence["boundary_rows"]),
        predicate_kind="combined_actor",
        boundary_bin_left=0.0,
        boundary_bin_right=0.1,
    )
    assert boundary["weighted_agreement"] == 1.0


def test_missing_labels_are_unavailable_and_changed_contract_is_characterization() -> None:
    missing = _audit_artifact(
        (
            {
                "kind": "state",
                "population": 2,
                "persisted": False,
                "independent": False,
                "measurement": 1.5,
                "status": RowEvaluationStatus.BLOCKED,
            },
        )
    )
    missing_evidence = validity_audit_evidence(missing)
    state = _find(_rows(missing_evidence["confusion_rows"]), predicate_kind="state")
    assert state["available"] is False
    assert state["missing_label_count"] == 1
    assert state["unweighted_true_negative"] == 0
    assert state["weighted_population"] == 0.0
    assert _rows(missing_evidence["margin_rows"])[0]["signed_margin"] is None

    changed = _audit_artifact(
        ({"kind": "path", "population": 2, "persisted": True, "independent": True, "measurement": 0.5},),
        comparison_protocol=AuditComparisonProtocol.ROBUSTNESS_CHARACTERIZATION,
    )
    changed_evidence = validity_audit_evidence(changed)
    assert changed_evidence["same_contract_eligible"] is False
    assert changed_evidence["evidence_status"] == "characterization_only"
    assert "contract changed" in str(changed_evidence["fallback_reason"])
    assert _find(_rows(changed_evidence["confusion_rows"]), predicate_kind="path")["eligible"] is False


def test_signed_margin_requires_declared_raw_boundary_contract() -> None:
    base = _complete_payload().validity_rows[0]
    with pytest.raises(ValidationError, match="signed_margin must be derived"):
        ValidityAuditRow.model_validate({**base.model_dump(mode="python"), "signed_margin": 99.0})
    with pytest.raises(ValidationError, match="verdict must follow"):
        ValidityAuditRow.model_validate({**base.model_dump(mode="python"), "independent_valid": False})
    with pytest.raises(ValidationError, match="cannot infer"):
        ValidityAuditRow.model_validate(
            {
                **base.model_dump(mode="python"),
                "evaluation_status": RowEvaluationStatus.BLOCKED,
                "independent_valid": None,
                "missing_reason": "unavailable",
            }
        )


def test_validity_reducers_do_not_change_rollout_store_schema() -> None:
    assert ROLLOUT_ZARR_SCHEMA_VERSION == "1.0-target-rollout-core"
