"""Tests for reproducible rollout Rerun layer policies."""

# ruff: noqa: S101

from __future__ import annotations

import pytest

from aria_nbv.rerun_inspector import (
    RerunInspectorLayerState,
    RolloutLayerPreset,
    resolve_rollout_layer_config,
)


def test_visible_layer_must_be_included() -> None:
    with pytest.raises(ValueError, match="cannot be visible"):
        RerunInspectorLayerState(included=False, visible=True)


def test_candidate_debugging_preset_expands_all_named_layers() -> None:
    config = resolve_rollout_layer_config(RolloutLayerPreset.candidate_debugging)

    assert config.rollout_candidates.included
    assert config.rollout_candidates.visible
    assert config.invalid_candidates.included
    assert config.invalid_candidates.visible
    assert config.oracle_mesh_gt.included
    assert not config.oracle_mesh_gt.visible


def test_layer_overrides_are_merged_then_validated() -> None:
    config = resolve_rollout_layer_config(
        RolloutLayerPreset.scientific_context,
        {"invalid_candidates": {"included": False, "visible": False}},
    )

    assert not config.invalid_candidates.included
    assert not config.invalid_candidates.visible
    assert config.rollout_candidates.included

    with pytest.raises(ValueError, match="cannot be visible"):
        resolve_rollout_layer_config(
            RolloutLayerPreset.candidate_debugging,
            {"invalid_candidates": {"included": False}},
        )
