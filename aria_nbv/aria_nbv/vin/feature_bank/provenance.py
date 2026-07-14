"""Actor-visible provenance checks for VIN point-feature banks.

The constants and validator in this module guard the actor/oracle boundary:
candidate scorers may consume logged actor-visible evidence, but must not see
GT, oracle, future-candidate, or counterfactual-rendered descriptors.

This module owns source-role allow/deny checks only. It does not prove that a
descriptor was produced by a particular model config or checkpoint; persistent
learned features still require content-addressed provenance from their owner.
"""

from __future__ import annotations

APPROVED_ACTOR_FEATURE_SOURCES = frozenset(
    {
        "semidense_geometry",
        "semidense_support",
        "efm3d_feat2d_upsampled",
        "efm3d_token2d",
        "efm3d_dino_point",
        "efm3d_evl_crop",
        "efm3d_voxel_feat",
        "efm3d_neck_occ_feat",
        "efm3d_neck_obb_feat",
        "cubercnn_proposal",
        "cubercnn_roi",
        "cubercnn_roi_descriptor",
    }
)

FORBIDDEN_ACTOR_FEATURE_SOURCES = frozenset(
    {
        "gt_mesh",
        "gt_obb_crop",
        "gt_semantic_identity",
        "oracle_rri",
        "all_candidate_rendered_depth",
        "unvisited_candidate_rgb",
        "unvisited_candidate_dino",
        "unvisited_candidate_evl",
        "unvisited_candidate_detector",
    }
)

FORBIDDEN_ACTOR_FEATURE_MARKERS = (
    "gt_",
    "oracle",
    "all_candidate",
    "unvisited",
    "future_candidate",
    "rendered_depth",
    "rendered_roi",
    "candidate_rgb",
    "candidate_dino",
    "candidate_evl",
    "candidate_detector",
)


def validate_actor_feature_provenance(
    *,
    feature_source: str,
    source_role: str = "actor_visible",
) -> None:
    """Validate that a feature source can be consumed by actor-side models.

    Args:
        feature_source: Stable source id such as ``"efm3d_feat2d_upsampled"``.
        source_role: Provenance role. Actor inputs currently accept only
            ``"actor_visible"``.

    Raises:
        ValueError: If the source is oracle/GT/counterfactual-only evidence.

    Notes:
        Validation is label-based. Passing this check does not authenticate a
        config, checkpoint, compression projection, or cached tensor payload.
    """
    if source_role != "actor_visible":
        msg = f"Actor feature banks require source_role='actor_visible', got {source_role!r}."
        raise ValueError(msg)
    normalized = _normalize_feature_source(feature_source)
    if normalized in FORBIDDEN_ACTOR_FEATURE_SOURCES:
        msg = f"{feature_source!r} is not an actor-visible feature source."
        raise ValueError(msg)
    if any(marker in normalized for marker in FORBIDDEN_ACTOR_FEATURE_MARKERS):
        msg = f"{feature_source!r} is not an actor-visible feature source."
        raise ValueError(msg)
    if normalized not in APPROVED_ACTOR_FEATURE_SOURCES:
        msg = f"{feature_source!r} is not an approved actor-visible feature source."
        raise ValueError(msg)


def _normalize_feature_source(feature_source: str) -> str:
    return feature_source.lower().replace("-", "_").replace("/", "_").replace(":", "_").replace(" ", "_")


__all__ = [
    "APPROVED_ACTOR_FEATURE_SOURCES",
    "FORBIDDEN_ACTOR_FEATURE_MARKERS",
    "FORBIDDEN_ACTOR_FEATURE_SOURCES",
    "validate_actor_feature_provenance",
]
