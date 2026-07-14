"""Normalize visual capabilities and render provenance for Rerun inspection.

This module owns the stable inventory DTO, pre-recording required-layer checks,
and compact JSON metadata containing source sample identity, selection context,
resolved inspector config, and non-fatal visualization warnings. Inventory
flags describe availability, not actor/oracle semantic equivalence.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from aria_nbv.data_handling import VinOfflineSample, collect_offline_visual_inventory
from aria_nbv.data_handling.efm_dataset_utils import compact_ase_atek_identifiers, compact_ase_atek_sample_id

from ._config import RerunOfflineInspectorConfig


@dataclass(frozen=True, slots=True)
class OfflineVisualInventory:
    """Normalized visual-inventory flags required by the inspector."""

    has_semidense: bool = True
    """Whether semidense VIN points are available."""

    has_reference_pose: bool = True
    """Whether the oracle reference pose is available."""

    has_candidate_frusta: bool = True
    """Whether candidate poses are available for frustum logging."""

    has_candidate_validity: bool = False
    """Whether a validity mask is available for invalid-frustum logging."""

    has_candidate_points: bool = False
    """Whether candidate point clouds are materialized."""

    has_mesh: bool = False
    """Whether a GT mesh can be attached and logged."""

    has_gt_obbs: bool = False
    """Whether GT OBBs are available."""

    has_detected_obbs: bool = False
    """Whether detected OBBs are available."""

    has_trajectory: bool = False
    """Whether trajectory metadata is available."""

    has_candidate_depths: bool = False
    """Whether candidate depth maps are available."""

    has_rgb_keyframes: bool = False
    """Whether live RGB keyframes are available."""

    has_depth_keyframes: bool = False
    """Whether live depth keyframes are available."""

    source: str = "fallback_manifest"
    """Human-readable inventory source."""

    details: dict[str, Any] | None = None
    """Optional source-specific inventory details."""


def _read_bool(payload: Mapping[str, Any], *names: str, default: bool = False) -> bool:
    """Return the first boolean-like value found in ``payload``."""

    for name in names:
        if name in payload:
            return bool(payload[name])
    return default


def normalize_visual_inventory(value: Any) -> OfflineVisualInventory:
    """Normalize Worker-B or fallback inventory payloads into a stable shape.

    Args:
        value: Mapping, dataclass, or object exposing inventory-like attributes.

    Returns:
        Normalized inventory flags consumed by validation and logging.
    """

    if isinstance(value, OfflineVisualInventory):
        return value
    if hasattr(value, "__dataclass_fields__"):
        payload = asdict(value)
    elif isinstance(value, Mapping):
        payload = dict(value)
    else:
        names = (
            "has_semidense",
            "has_semidense_points",
            "semidense",
            "has_reference_pose",
            "reference_pose",
            "has_candidate_frusta",
            "candidate_frusta",
            "has_candidate_validity",
            "has_candidate_mask",
            "candidate_validity",
            "has_candidate_points",
            "has_candidate_pcs",
            "candidate_points",
            "has_mesh",
            "has_gt_mesh",
            "mesh",
            "has_gt_obbs",
            "gt_obbs",
            "has_detected_obbs",
            "detected_obbs",
            "has_trajectory",
            "trajectory",
            "has_depths",
            "has_candidate_depths",
            "has_rgb_keyframes",
            "has_depth_keyframes",
            "source",
            "details",
            "warnings",
            "errors",
            "metadata",
        )
        payload = {name: getattr(value, name) for name in names if hasattr(value, name)}

    details = _inventory_details(payload)
    return OfflineVisualInventory(
        has_semidense=_has_required_semidense(payload, details),
        has_reference_pose=_read_bool(payload, "has_reference_pose", "reference_pose", default=True),
        has_candidate_frusta=_read_bool(
            payload,
            "has_candidate_frusta",
            "candidate_frusta",
            "candidate_poses",
            default=True,
        ),
        has_candidate_validity=_read_bool(
            payload,
            "has_candidate_validity",
            "has_candidate_mask",
            "candidate_validity",
            default=False,
        ),
        has_candidate_points=_read_bool(
            payload,
            "has_candidate_points",
            "has_candidate_pcs",
            "candidate_points",
            "candidate_pcs",
            default=False,
        ),
        has_mesh=_read_bool(payload, "has_mesh", "has_gt_mesh", "mesh", "gt_mesh", default=False),
        has_gt_obbs=_read_bool(payload, "has_gt_obbs", "gt_obbs", default=False),
        has_detected_obbs=_read_bool(payload, "has_detected_obbs", "detected_obbs", default=False),
        has_trajectory=_read_bool(payload, "has_trajectory", "trajectory", default=False),
        has_candidate_depths=_read_bool(payload, "has_candidate_depths", "has_depths", default=False),
        has_rgb_keyframes=_read_bool(payload, "has_rgb_keyframes", default=False),
        has_depth_keyframes=_read_bool(payload, "has_depth_keyframes", default=False),
        source=str(payload.get("source", "external")),
        details=details or None,
    )


def _inventory_details(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Preserve Worker-B diagnostic detail fields in the normalized payload."""

    details: dict[str, Any] = {}
    raw_details = payload.get("details", {})
    if isinstance(raw_details, Mapping):
        details.update(dict(raw_details))
    if "has_semidense_points" in payload:
        details["candidate_pcs_has_semidense_points"] = bool(payload["has_semidense_points"])
    for name in ("warnings", "errors"):
        value = payload.get(name)
        if value is not None:
            details[name] = list(value) if isinstance(value, (list, tuple)) else [value]
    metadata = payload.get("metadata")
    if isinstance(metadata, Mapping):
        details["metadata"] = dict(metadata)
    elif metadata is not None:
        details["metadata"] = metadata
    return details


def _has_required_semidense(payload: Mapping[str, Any], details: Mapping[str, Any]) -> bool:
    """Resolve required VIN semidense availability without candidate-pc flags."""

    for name in ("has_semidense", "semidense", "vin_points"):
        if name in payload:
            return bool(payload[name])

    metadata = details.get("metadata")
    if isinstance(metadata, Mapping):
        valid_points = metadata.get("vin_snippet.valid_semidense_points")
        if valid_points is not None:
            return int(valid_points) > 0

    return True


def collect_visual_inventory(sample: VinOfflineSample) -> OfflineVisualInventory:
    """Collect and normalize the optional Worker-B visual inventory.

    The inspector uses the typed data-handling collector as the canonical
    inventory source.
    """

    return normalize_visual_inventory(collect_offline_visual_inventory(sample))


def validate_required_inventory(config: RerunOfflineInspectorConfig, inventory: OfflineVisualInventory) -> None:
    """Fail before Rerun initialization when required visual inputs are absent."""

    missing: list[str] = []
    if config.primitives.log_semidense and not inventory.has_semidense:
        missing.append("semidense VIN points")
    if config.primitives.log_reference_pose and not inventory.has_reference_pose:
        missing.append("reference pose")
    if (
        config.primitives.log_candidate_frusta
        or config.primitives.log_top_oracle_frustum
        or config.primitives.log_candidate_centers
    ) and not inventory.has_candidate_frusta:
        missing.append("candidate poses/frusta")
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(f"Rerun inspector inventory is missing required visual inputs: {joined}.")


def build_sample_metadata_document(
    *,
    config: RerunOfflineInspectorConfig,
    inventory: OfflineVisualInventory,
    selection: str,
    sample: VinOfflineSample,
    runtime_warnings: Sequence[str] | None = None,
) -> str:
    """Render a compact JSON metadata document for Rerun."""

    payload = {
        "sample": {
            "sample_key": compact_ase_atek_sample_id(sample.sample_key),
            "scene_id": sample.scene_id,
            "snippet_id": compact_ase_atek_sample_id(sample.snippet_id),
        },
        "selection": selection,
        "inventory": asdict(inventory),
        "runtime_warnings": list(runtime_warnings or ()),
        "config": config.model_dump_jsonable(),
    }
    return json.dumps(compact_ase_atek_identifiers(payload), indent=2, sort_keys=True)


__all__ = [
    "OfflineVisualInventory",
    "build_sample_metadata_document",
    "collect_visual_inventory",
    "normalize_visual_inventory",
    "validate_required_inventory",
]
