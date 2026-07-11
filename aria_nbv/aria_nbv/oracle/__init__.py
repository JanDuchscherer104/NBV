"""Privileged evidence preparation, scoring, and label-generation pipelines."""

from .scene_rri import SceneRriScorer, SceneRriScorerConfig
from .target_rri import TargetRriScorer, TargetRriScorerConfig

__all__ = ["SceneRriScorer", "SceneRriScorerConfig", "TargetRriScorer", "TargetRriScorerConfig"]
