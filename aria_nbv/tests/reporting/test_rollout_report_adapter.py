"""Rollout report-v1 wrapping contracts."""

from __future__ import annotations

import pandas as pd

from aria_nbv.reporting._rollouts import _build_rollout_section, _RolloutEvidence
from aria_nbv.reporting.config import ReportThemeConfig, RolloutReportSectionConfig
from aria_nbv.reporting.results import SourceIdentity


def test_rollout_facts_remain_store_qualified_in_snapshot_results() -> None:
    facts = pd.DataFrame(
        [
            {
                "store_id": "a",
                "key": "candidate_validity.fraction",
                "value": 0.5,
                "unit": "fraction",
                "n": 10,
                "aggregation": "fraction",
                "status": "pilot",
                "source": "manifest",
            },
            {
                "store_id": "b",
                "key": "candidate_validity.fraction",
                "value": 0.8,
                "unit": "fraction",
                "n": 20,
                "aggregation": "fraction",
                "status": "pilot",
                "source": "manifest",
            },
        ]
    )
    evidence = _RolloutEvidence(
        identity=SourceIdentity("rollout", "rollout", "a" * 64, (("store_count", 2),)),
        frames={"facts": facts},
    )
    section = RolloutReportSectionConfig(
        include_tables=("facts",),
        figure_fact_keys=("candidate_validity.fraction",),
    )

    results = _build_rollout_section(evidence, section, ReportThemeConfig(), requested_result_ids=None)

    assert tuple(quantity.value for quantity in results.quantities) == (0.5, 0.8)
    assert tuple(quantity.id for quantity in results.quantities) == (
        "rollout.quantity.a.candidate_validity.fraction",
        "rollout.quantity.b.candidate_validity.fraction",
    )
    assert len(results.figures) == 1
