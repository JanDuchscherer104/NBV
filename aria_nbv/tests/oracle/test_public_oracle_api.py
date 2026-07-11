"""Contract tests for the compact ``aria_nbv.oracle`` root API."""

from __future__ import annotations

import aria_nbv.oracle as oracle


def test_oracle_root_exports_scene_scorer_only() -> None:
    """Prepared engines, evidence helpers, and task DTOs require leaf imports."""

    assert set(oracle.__all__) == {"SceneRriScorer", "SceneRriScorerConfig"}
    assert not hasattr(oracle, "PreparedRriScorer")
    assert not hasattr(oracle, "RootEvalPointCloud")
