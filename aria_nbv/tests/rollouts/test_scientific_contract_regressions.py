"""Adversarial regression contracts for immutable scientific rollout evidence."""

# ruff: noqa: S101

from __future__ import annotations

import hashlib
import math
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from aria_nbv.rollouts.inspection import (
    candidate_evidence_availability_rows,
    candidate_geometry_evidence_rows,
    discounted_rollout_return_rows,
    policy_effect_evidence,
)
from aria_nbv.rollouts.read_model import StoredEndpointComparator
from aria_nbv.rollouts.scientific_audit import (
    PolicySemanticRole,
    RowEvaluationStatus,
    ValidityAuditRow,
    ValidityPredicateContract,
)
from aria_nbv.rri_metrics.returns import summarize_target_rollout_metrics
from tests.rollouts.test_scientific_audit import _complete_payload
from tests.rollouts.test_scientific_inference import _artifact as _policy_artifact
from tests.rollouts.test_scientific_inference import _endpoint_row


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def test_gamma_one_selected_gains_telescope_to_endpoint_but_discounted_return_does_not() -> None:
    steps = [
        {"target_root_gain": 0.2, "target_pm_dist_before": 10.0, "target_pm_dist_after": 8.0},
        {"target_root_gain": 0.3, "target_pm_dist_before": 8.0, "target_pm_dist_after": 5.0},
    ]

    undiscounted = summarize_target_rollout_metrics(steps, gamma=1.0)
    discounted = summarize_target_rollout_metrics(steps, gamma=0.5)

    assert undiscounted.cumulative_return == pytest.approx(undiscounted.endpoint_gain)
    assert discounted.cumulative_return == pytest.approx(0.35)
    assert discounted.cumulative_return != pytest.approx(discounted.endpoint_gain)


def test_endpoint_comparator_rejects_discounted_gamma_as_equivalence_input() -> None:
    with pytest.raises(ValueError, match="gamma=1"):
        StoredEndpointComparator(gain=0.5, gamma=0.5)


def test_endpoint_tolerance_accepts_exact_boundary_and_rejects_larger_difference() -> None:
    absolute_tolerance = _complete_payload().config.absolute_tolerance

    at_boundary = _complete_payload(endpoint_comparator_offset=absolute_tolerance)
    beyond_boundary = _complete_payload(endpoint_comparator_offset=1e-4)

    assert at_boundary.endpoint_rows[0].equivalence_verdict.value == "pass"
    assert beyond_boundary.endpoint_rows[0].equivalence_verdict.value == "fail"


def test_missing_or_nonfinite_selected_gain_chain_never_produces_a_comparator_value() -> None:
    missing = discounted_rollout_return_rows(
        [
            {"rollout_row_id": 4, "step_index": 0, "selected_target_root_gain": 0.2},
            {"rollout_row_id": 4, "step_index": 1, "selected_target_root_gain": None},
        ],
        return_semantics="cumulative_target_root_gain",
        discount_gamma=1.0,
    )
    nonfinite = discounted_rollout_return_rows(
        [{"rollout_row_id": 5, "step_index": 0, "selected_target_root_gain": math.nan}],
        return_semantics="cumulative_target_root_gain",
        discount_gamma=1.0,
    )

    assert missing["rows"][0]["discounted_return"] is None
    assert nonfinite["rows"][0]["discounted_return"] is None


def test_policy_effects_require_the_same_predeclared_seed_or_replicate_context() -> None:
    learned = _endpoint_row(
        scene="scene-1",
        replicate="seed-101",
        role=PolicySemanticRole.LEARNED_ONE_STEP,
        gain=0.2,
    )
    qh = _endpoint_row(
        scene="scene-1",
        replicate="seed-202",
        role=PolicySemanticRole.LEARNED_QH,
        gain=0.5,
    )

    evidence = policy_effect_evidence(_policy_artifact([learned, qh]), bootstrap_samples=8)
    raw_qh = next(row for row in evidence["summary_rows"] if row["contrast"] == "raw_qh")

    assert raw_qh["pair_count"] == 0
    assert raw_qh["missing_role_count"] == 2
    assert raw_qh["exclusion_reason_counts"] == {"missing_role": 2}


@pytest.mark.parametrize(
    ("paths", "expected_missing"),
    [
        (
            {"candidates/sampler_probability", "candidates/selection_logits"},
            (
                "candidates/behavior_probability",
                "candidates/evaluation_probability",
                "candidates/valid_action_table_identity",
            ),
        ),
        (
            {"candidates/behavior_probability"},
            ("candidates/evaluation_probability", "candidates/valid_action_table_identity"),
        ),
        (
            {"candidates/behavior_probability", "candidates/evaluation_probability"},
            ("candidates/valid_action_table_identity",),
        ),
        (
            {
                "candidates/behavior_probability",
                "candidates/evaluation_probability",
                "candidates/valid_action_table_identity",
            },
            (),
        ),
    ],
)
def test_candidate_support_blocks_ess_until_probability_and_action_table_semantics_are_validated(
    paths: set[str],
    expected_missing: tuple[str, ...],
) -> None:
    rows = candidate_evidence_availability_rows(SimpleNamespace(root=paths))

    ess = next(row for row in rows if row["evidence"] == "behavior/evaluation support and ESS")
    assert ess["available"] is False
    assert ess["required_fields"] == (
        "candidates/behavior_probability",
        "candidates/evaluation_probability",
        "candidates/valid_action_table_identity",
    )
    assert ess["missing_fields"] == expected_missing
    assert "ESS cannot be computed or proxied" in str(ess["detail"])
    assert "candidates/sampler_probability" not in ess["required_fields"]
    assert "candidates/selection_logits" not in ess["required_fields"]


@pytest.mark.parametrize(
    ("predicate_kind", "operator", "expected_valid"),
    [
        ("state", "<", False),
        ("path", "<=", True),
        ("combined_actor", ">", False),
        ("state", ">=", True),
    ],
)
def test_predicate_boundary_preserves_declared_strict_or_inclusive_semantics(
    predicate_kind: str,
    operator: str,
    expected_valid: bool,
) -> None:
    base = _complete_payload().validity_rows[0]
    contract = ValidityPredicateContract.derive(
        predicate_kind=predicate_kind,  # type: ignore[arg-type]
        owner=f"{predicate_kind}-validator",
        name="threshold-v1",
        comparison_operator=operator,  # type: ignore[arg-type]
        threshold=1.0,
        unit="m",
        frame="root-centered ARIA world (RIGHT_HAND_Z_UP)",
        semantic_config_sha256=_sha(f"{predicate_kind}:{operator}"),
    )

    row = ValidityAuditRow.model_validate(
        {
            **base.model_dump(mode="python"),
            "persisted_contract": contract,
            "independent_contract": contract,
            "persisted_valid": expected_valid,
            "independent_valid": expected_valid,
            "raw_measurement": 1.0,
            "signed_margin": 0.0,
            "evaluation_status": RowEvaluationStatus.COMPLETE,
            "missing_reason": None,
        }
    )

    assert row.independent_valid is expected_valid
    assert row.signed_margin == 0.0

    with pytest.raises(ValidationError, match="Independent validity verdict"):
        ValidityAuditRow.model_validate(
            {
                **row.model_dump(mode="python"),
                "independent_valid": not expected_valid,
            }
        )


def test_predicate_contract_rejects_metres_degrees_and_frame_drift_as_same_contract() -> None:
    base = _complete_payload().validity_rows[0]
    metres = base.persisted_contract
    degrees = ValidityPredicateContract.derive(
        predicate_kind="path",
        owner=metres.owner,
        name=metres.name,
        comparison_operator="<=",
        threshold=0.25,
        unit="deg",
        frame="camera yaw",
        semantic_config_sha256=_sha("degrees-not-metres"),
    )

    with pytest.raises(ValidationError, match="SAME_CONTRACT"):
        type(_complete_payload()).model_validate(
            {
                **_complete_payload().model_dump(mode="python"),
                "validity_rows": (
                    {
                        **base.model_dump(mode="python"),
                        "independent_contract": degrees,
                    },
                ),
            }
        )


def test_root_relative_geometry_is_invariant_to_shared_yaw_rotation_and_keeps_units_explicit() -> None:
    original = {
        "candidate_row_id": 11,
        "root_relative_x_m": 2.0,
        "root_relative_y_m": 1.0,
        "root_relative_z_m": 3.0,
        "root_to_target_x_m": 4.0,
        "root_to_target_y_m": 2.0,
    }
    rotated = {
        **original,
        "root_relative_x_m": -1.0,
        "root_relative_y_m": 2.0,
        "root_to_target_x_m": -2.0,
        "root_to_target_y_m": 4.0,
    }

    first, second = candidate_geometry_evidence_rows([original, rotated])

    assert second["root_radius_m"] == pytest.approx(first["root_radius_m"])
    assert second["root_elevation_deg"] == pytest.approx(first["root_elevation_deg"])
    assert second["target_normalized_forward"] == pytest.approx(first["target_normalized_forward"])
    assert second["target_normalized_lateral"] == pytest.approx(first["target_normalized_lateral"])
    assert second["root_azimuth_deg"] == pytest.approx(first["root_azimuth_deg"] + 90.0)
    assert {"root_radius_m", "root_azimuth_deg", "root_elevation_deg", "root_target_xy_distance_m"} <= set(first)
