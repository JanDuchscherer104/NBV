"""Contract tests for the compact ``aria_nbv.oracle`` root API."""

from __future__ import annotations

import importlib.util

import aria_nbv.oracle as oracle
from aria_nbv.oracle.pipelines.scene_labels import OracleRriLabeler, OracleRriLabelerConfig, OracleRriSample


def test_oracle_root_exports_scorer_facades_only() -> None:
    """Prepared engines, evidence helpers, and task DTOs require leaf imports."""

    assert set(oracle.__all__) == {
        "SceneRriScorer",
        "SceneRriScorerConfig",
        "TargetRriScorer",
        "TargetRriScorerConfig",
    }
    assert not hasattr(oracle, "PreparedRriScorer")
    assert not hasattr(oracle, "RootEvalPointCloud")


def test_scene_label_pipeline_requires_its_owning_leaf() -> None:
    """Expose scene-label composition only from the Oracle pipeline leaf."""

    assert OracleRriLabelerConfig().target_type is OracleRriLabeler
    assert OracleRriSample.__module__ == "aria_nbv.oracle.pipelines.scene_labels"
    assert importlib.util.find_spec("aria_nbv.pipelines.oracle_rri_labeler") is None
