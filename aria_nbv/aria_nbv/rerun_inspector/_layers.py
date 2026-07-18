"""Resolve reproducible layer policies for rollout Rerun inspection.

Layer presets are convenience inputs only. The resolver expands every preset
and override into :class:`RerunInspectorRolloutLayersConfig`, which is then
persisted in the per-launch TOML artifact consumed by the logger and blueprint.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from ._config import RerunInspectorLayerState, RerunInspectorRolloutLayersConfig


class RolloutLayerName(StrEnum):
    """Stable names for independently included and visible rollout layers."""

    actor_context = "actor_context"
    oracle_mesh_gt = "oracle_mesh_gt"
    target_overlay = "target_overlay"
    rollout_candidates = "rollout_candidates"
    invalid_candidates = "invalid_candidates"
    selected_path = "selected_path"
    selected_depth = "selected_depth"
    rgb_depth_context = "rgb_depth_context"
    scalar_plots = "scalar_plots"
    metadata = "metadata"


class RolloutLayerPreset(StrEnum):
    """Named scientific starting points for rollout inspection."""

    scientific_context = "Scientific context"
    target_protocol = "Target protocol"
    candidate_debugging = "Candidate debugging"
    minimal_selected_path = "Minimal selected path"


LayerOverride = RerunInspectorLayerState | Mapping[str, bool]


def resolve_rollout_layer_config(
    preset: RolloutLayerPreset | str = RolloutLayerPreset.scientific_context,
    overrides: Mapping[RolloutLayerName | str, LayerOverride] | None = None,
) -> RerunInspectorRolloutLayersConfig:
    """Expand a preset and optional per-layer overrides into explicit policy.

    Args:
        preset: Named starting policy. Enum values use the human-facing labels
            shown by the Streamlit inspector.
        overrides: Optional complete or partial ``included``/``visible`` values
            keyed by :class:`RolloutLayerName`. A visible-but-excluded override
            is rejected by :class:`RerunInspectorLayerState` validation.

    Returns:
        Fully resolved layer config suitable for deterministic TOML storage.
    """

    resolved_preset = RolloutLayerPreset(preset)
    payload = _PRESET_PAYLOADS[resolved_preset]
    config = RerunInspectorRolloutLayersConfig.model_validate(payload)
    if not overrides:
        return config
    updated = config.model_dump()
    valid_names = {member.value for member in RolloutLayerName}
    for raw_name, raw_override in overrides.items():
        name = str(raw_name)
        if name not in valid_names:
            raise ValueError(f"Unknown rollout Rerun layer: {name!r}.")
        base = dict(updated[name])
        override = (
            raw_override.model_dump() if isinstance(raw_override, RerunInspectorLayerState) else dict(raw_override)
        )
        unknown = set(override) - {"included", "visible"}
        if unknown:
            raise ValueError(f"Unknown state fields for rollout Rerun layer {name!r}: {sorted(unknown)}")
        base.update(override)
        updated[name] = base
    return RerunInspectorRolloutLayersConfig.model_validate(updated)


def _state(*, included: bool, visible: bool) -> dict[str, bool]:
    return {"included": included, "visible": visible}


_PRESET_PAYLOADS: dict[RolloutLayerPreset, dict[str, dict[str, bool]]] = {
    RolloutLayerPreset.scientific_context: {
        "actor_context": _state(included=True, visible=True),
        "oracle_mesh_gt": _state(included=True, visible=False),
        "target_overlay": _state(included=True, visible=True),
        "rollout_candidates": _state(included=True, visible=False),
        "invalid_candidates": _state(included=True, visible=False),
        "selected_path": _state(included=True, visible=True),
        "selected_depth": _state(included=True, visible=False),
        "rgb_depth_context": _state(included=False, visible=False),
        "scalar_plots": _state(included=True, visible=True),
        "metadata": _state(included=True, visible=True),
    },
    RolloutLayerPreset.target_protocol: {
        "actor_context": _state(included=True, visible=True),
        "oracle_mesh_gt": _state(included=True, visible=True),
        "target_overlay": _state(included=True, visible=True),
        "rollout_candidates": _state(included=False, visible=False),
        "invalid_candidates": _state(included=False, visible=False),
        "selected_path": _state(included=True, visible=True),
        "selected_depth": _state(included=True, visible=True),
        "rgb_depth_context": _state(included=True, visible=False),
        "scalar_plots": _state(included=False, visible=False),
        "metadata": _state(included=True, visible=True),
    },
    RolloutLayerPreset.candidate_debugging: {
        "actor_context": _state(included=True, visible=True),
        "oracle_mesh_gt": _state(included=True, visible=False),
        "target_overlay": _state(included=True, visible=True),
        "rollout_candidates": _state(included=True, visible=True),
        "invalid_candidates": _state(included=True, visible=True),
        "selected_path": _state(included=True, visible=True),
        "selected_depth": _state(included=True, visible=False),
        "rgb_depth_context": _state(included=False, visible=False),
        "scalar_plots": _state(included=True, visible=True),
        "metadata": _state(included=True, visible=True),
    },
    RolloutLayerPreset.minimal_selected_path: {
        "actor_context": _state(included=False, visible=False),
        "oracle_mesh_gt": _state(included=False, visible=False),
        "target_overlay": _state(included=True, visible=True),
        "rollout_candidates": _state(included=False, visible=False),
        "invalid_candidates": _state(included=False, visible=False),
        "selected_path": _state(included=True, visible=True),
        "selected_depth": _state(included=False, visible=False),
        "rgb_depth_context": _state(included=False, visible=False),
        "scalar_plots": _state(included=False, visible=False),
        "metadata": _state(included=True, visible=True),
    },
}


__all__ = [
    "LayerOverride",
    "RolloutLayerName",
    "RolloutLayerPreset",
    "resolve_rollout_layer_config",
]
