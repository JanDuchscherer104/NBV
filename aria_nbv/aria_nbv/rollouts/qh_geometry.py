"""Independent selected-depth geometry contract DTO."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QhGeometryContract:
    """Persisted, immutable geometry facts for selected CF-GT depth."""

    projection_model: str
    linearization: str
    camera_pose: str
    depth_semantics: str
    focal_px: tuple[float, float]
    principal_point_px: tuple[float, float]
    image_size_hw: tuple[int, int]
    camera_axes: str
    camera_forward: str
    camera_handedness: str
    pixel_convention: str
    in_ndc: bool
    znear_m: float
    zfar_m: float
    invalid_fill_value: float
    dtype: str
    renderer: str
    source_role: str
    selected_identity: str
