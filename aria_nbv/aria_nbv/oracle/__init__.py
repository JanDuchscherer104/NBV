"""Privileged evidence preparation, scoring, and label-generation pipelines."""

from .scene_rri import SceneRriScorer, SceneRriScorerConfig

__all__ = ["SceneRriScorer", "SceneRriScorerConfig"]
