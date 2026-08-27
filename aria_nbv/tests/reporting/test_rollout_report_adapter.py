"""Rollout report-v1 wrapping contracts."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from aria_nbv.reporting._rollouts import _build_rollout_section, _RolloutEvidence, _S2StoreEvidence
from aria_nbv.reporting.config import ReportThemeConfig, RolloutReportSectionConfig, S2RolloutReportSectionConfig
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


def test_s2_section_freezes_shared_figures_support_and_named_values() -> None:
    evidence = _RolloutEvidence(
        identity=SourceIdentity("rollout", "rollout", "a" * 64, (("store_count", 1),)),
        frames={"facts": pd.DataFrame()},
        s2_stores=(
            _S2StoreEvidence(
                slot=1,
                store_id="b" * 64,
                path=Path("store.zarr"),
                azimuth_bins=8,
                elevation_bins=4,
                projection_limit=16,
                payload=_s2_payload(),
                payload_sha256="c" * 64,
            ),
        ),
    )
    section = S2RolloutReportSectionConfig(azimuth_bins=8, elevation_bins=4, projection_limit=16)

    results = _build_rollout_section(evidence, section, ReportThemeConfig(), requested_result_ids=None)

    assert tuple(figure.id for figure in results.figures) == (
        "s2.figure.s01.movement",
        "s2.figure.s01.view-direction",
        "s2.figure.s01.frustum",
    )
    assert all(figure.uses_webgl for figure in results.figures)
    assert all(figure.source_result_ids == ("s2.table.support",) for figure in results.figures)
    assert len(results.tables) == 1
    assert results.tables[0].rows[0][0:3] == ("s01", "b" * 64, "c" * 64)
    assert {quantity.id for quantity in results.quantities} == {
        "s2.quantity.s01.source-sample-count",
        "s2.quantity.s01.source-snippet-count",
        "s2.quantity.s01.source-scene-count",
        "s2.quantity.s01.target-count",
        "s2.quantity.s01.rollout-count",
        "s2.quantity.s01.selected-step-count",
        "s2.quantity.s01.movement-count",
        "s2.quantity.s01.view-direction-count",
        "s2.quantity.s01.frustum-count",
        "s2.quantity.s01.mean-frustum-solid-angle",
        "s2.quantity.s01.mean-proxy-surface-fraction",
        "s2.quantity.s01.union-proxy-surface-fraction",
    }


def test_s2_figure_request_keeps_its_support_table_dependency() -> None:
    evidence = _RolloutEvidence(
        identity=SourceIdentity("rollout", "rollout", "a" * 64, (("store_count", 1),)),
        frames={"facts": pd.DataFrame()},
        s2_stores=(
            _S2StoreEvidence(
                slot=1,
                store_id="b" * 64,
                path=Path("store.zarr"),
                azimuth_bins=8,
                elevation_bins=4,
                projection_limit=16,
                payload=_s2_payload(),
                payload_sha256="c" * 64,
            ),
        ),
    )
    section = S2RolloutReportSectionConfig(azimuth_bins=8, elevation_bins=4, projection_limit=16)

    results = _build_rollout_section(
        evidence,
        section,
        ReportThemeConfig(),
        requested_result_ids=frozenset({"s2.figure.s01.movement"}),
    )

    assert tuple(figure.id for figure in results.figures) == ("s2.figure.s01.movement",)
    assert tuple(table.id for table in results.tables) == ("s2.table.support",)


def _s2_payload() -> dict[str, object]:
    counts = np.zeros((4, 8), dtype=np.int64)
    counts[2, 4] = 1
    point = np.asarray([[1.0, 0.0, 0.0]], dtype=np.float32)
    provenance = np.asarray([7], dtype=np.int64)
    steps = np.asarray([0], dtype=np.int64)
    return {
        "movement_counts": counts,
        "view_direction_counts": counts,
        "frustum_counts": counts,
        "movement_projection": point,
        "movement_projection_normalized_lengths": np.asarray([0.5], dtype=np.float32),
        "movement_projection_rollout_row_ids": provenance,
        "movement_projection_step_indices": steps,
        "view_direction_projection": point,
        "view_direction_projection_rollout_row_ids": provenance,
        "view_direction_projection_step_indices": steps,
        "frustum_projection": point,
        "frustum_projection_rollout_row_ids": provenance,
        "frustum_projection_step_indices": steps,
        "source_sample_count": 1,
        "source_snippet_count": 1,
        "source_scene_count": 1,
        "target_count": 1,
        "rollout_count": 1,
        "store_rollout_count": 1,
        "selected_step_count": 1,
        "movement_count": 1,
        "view_direction_count": 1,
        "frustum_count": 1,
        "frustum_missing_calibration_count": 0,
        "movement_skipped_zero_count": 0,
        "frustum_mean_fov_solid_angle_sr": 2.5,
        "frustum_mean_target_surface_fraction_approx": 0.2,
        "frustum_union_target_surface_fraction_approx": 0.3,
        "issues": (),
    }
