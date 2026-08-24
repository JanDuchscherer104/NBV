"""Bounded population evidence for learned recursive exact-``Q_2`` controls."""

# ruff: noqa: S101

from __future__ import annotations

from dataclasses import replace

import pytest
import torch

from aria_nbv.lightning.qh_q2_certification import (
    QhDecoderSupport,
    QhExactQ2CertificationSpec,
    QhExactQ2Certifier,
)
from tests.lightning.test_qh_module import _ChainDataset, _module, _training_chain


def _dataset(count: int = 4) -> _ChainDataset:
    """Return complete dense-valid chains with explicit generation lineage."""

    chains = []
    for index in range(count):
        chain = _training_chain()
        chains.append(
            replace(
                chain,
                key=replace(
                    chain.key,
                    store_index=index % 2,
                    rollout_row_id=index,
                    source_sample_index=index,
                    scene_id=f"scene-{index % 2}",
                    target_row_id=index,
                    configured_horizon=2,
                    candidate_width_min=3,
                    candidate_width_max=3,
                    candidate_config_hash="candidate-v1",
                    rollout_config_hash="rollout-v1",
                    selection_policy="q_h",
                ),
            )
        )
    return _ChainDataset(chains, scene="held-out")


def test_exact_q2_certifier_is_bounded_deterministic_and_semantically_explicit() -> None:
    module = _module()
    module.online_scorer.next.data.copy_(torch.tensor([2.0, 0.0, 0.0, 0.0]))
    module.target_scorer.next.data.copy_(torch.tensor([2.0, 0.0, 0.0, 0.0]))
    spec = QhExactQ2CertificationSpec(
        absolute_tolerance=0.0,
        relative_tolerance=0.0,
        minimum_exact_q2_rows=2,
        minimum_population_coverage=0.5,
        max_selected_chains=2,
        max_chains_per_stratum=1,
        selection_seed=17,
    )
    certifier = QhExactQ2Certifier(spec)

    first = certifier.certify(module=module, dataset=_dataset(), device=torch.device("cpu"))
    second = certifier.certify(module=module, dataset=_dataset(), device=torch.device("cpu"))

    census = first["population_census"]
    assert census["population_chain_count"] == 4
    assert census["selected_chain_count"] == 2
    assert census["selected_chain_fraction"] == pytest.approx(0.5)
    assert census["near_exhaustive"] is False
    assert first["selected_chain_support"] == second["selected_chain_support"]
    assert first["aggregate"] == {
        "exact_q2_row_count": 2,
        "within_tolerance_count": 2,
        "within_tolerance_fraction": 1.0,
        "mean_absolute_error": 0.0,
        "root_mean_squared_error": 0.0,
        "max_absolute_error": 0.0,
        "max_relative_error": 0.0,
        "minimum_support_met": True,
        "tolerance_passed": True,
    }
    assert first["learned_recursion_passed"] is True
    assert sum(row["exact_q2_row_count"] for row in first["support_stratum_aggregates"]) == 2
    assert first["evidence_semantics"] == {
        "quantity": "learned_recursive_q2_target_error_against_factual_dense_successor_control",
        "implementation_recursion_parity": False,
        "endpoint_policy_evidence": False,
        "longer_horizon_claim": False,
    }
    assert {row["candidate_branch_bin"] for row in first["exact_q2_rows"]} == {"2-4"}


def test_exact_q2_certifier_reports_coral_support_saturation_separately() -> None:
    module = _module()
    evidence = QhExactQ2Certifier(
        QhExactQ2CertificationSpec(
            absolute_tolerance=100.0,
            relative_tolerance=0.0,
            minimum_population_coverage=1.0,
        )
    ).certify(
        module=module,
        dataset=_dataset(1),
        device=torch.device("cpu"),
        decoder_support=QhDecoderSupport(
            kind="coral",
            lower_representative=-1.0,
            upper_representative=1.0,
            lower_edge=-0.5,
            upper_edge=0.5,
        ),
    )

    support = evidence["decoder_support"]
    assert support["applicable"] is True
    assert support["exact_q2_row_count"] == 1
    assert support["above_representative_count"] == 1
    assert support["outside_representative_fraction"] == 1.0
    assert support["upper_outer_class_count"] == 1
    assert support["outer_class_fraction"] == 1.0


def test_exact_q2_certifier_rejects_an_entirely_unsupported_selected_stratum() -> None:
    supported = _dataset(1).chains[0]
    unsupported = _training_chain(bootstrap=False)
    unsupported = replace(
        unsupported,
        key=replace(
            unsupported.key,
            store_index=1,
            rollout_row_id=1,
            source_sample_index=1,
            scene_id="unsupported-scene",
            target_row_id=1,
            configured_horizon=2,
            candidate_width_min=3,
            candidate_width_max=3,
            candidate_config_hash="candidate-v1",
            rollout_config_hash="rollout-v1",
            selection_policy="q_h",
        ),
    )
    dataset = _ChainDataset([supported, unsupported], scene="held-out")
    module = _module()
    module.online_scorer.next.data.copy_(torch.tensor([2.0, 0.0, 0.0, 0.0]))
    module.target_scorer.next.data.copy_(torch.tensor([2.0, 0.0, 0.0, 0.0]))

    evidence = QhExactQ2Certifier(
        QhExactQ2CertificationSpec(
            absolute_tolerance=0.0,
            relative_tolerance=0.0,
            minimum_population_coverage=1.0,
        )
    ).certify(module=module, dataset=dataset, device=torch.device("cpu"))

    assert evidence["aggregate"]["tolerance_passed"] is True
    assert evidence["support_coverage_passed"] is False
    assert any(row["exact_q2_row_count"] == 0 for row in evidence["support_stratum_aggregates"])
    assert evidence["learned_recursion_passed"] is False


def test_exact_q2_certifier_fails_closed_on_incomplete_lineage() -> None:
    dataset = _dataset(1)
    dataset.chains[0] = replace(
        dataset.chains[0],
        key=replace(dataset.chains[0].key, candidate_config_hash=""),
    )

    with pytest.raises(ValueError, match="candidate_config_hash"):
        QhExactQ2Certifier(QhExactQ2CertificationSpec(absolute_tolerance=1e-5, relative_tolerance=1e-5)).certify(
            module=_module(), dataset=dataset, device=torch.device("cpu")
        )


@pytest.mark.parametrize(
    "update",
    [
        {"absolute_tolerance": -1.0},
        {"relative_tolerance": float("nan")},
        {"minimum_exact_q2_rows": 0},
        {"minimum_population_coverage": 0.0},
        {"max_selected_chains": 0},
        {"positive_headroom_threshold": 0.0},
    ],
)
def test_exact_q2_certification_spec_rejects_invalid_gates(update: dict[str, object]) -> None:
    arguments: dict[str, object] = {"absolute_tolerance": 0.0, "relative_tolerance": 0.0}
    arguments.update(update)
    with pytest.raises(ValueError):
        QhExactQ2CertificationSpec(**arguments)  # type: ignore[arg-type]
