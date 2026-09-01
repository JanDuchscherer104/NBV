"""Composable authoring values for mixed candidate center and gaze groups."""

from __future__ import annotations

from math import isfinite
from typing import Annotated, Literal, Self, TypeAlias

from pydantic import Field, field_validator, model_validator

from ..utils import BaseConfig
from .types import CandidatePositionMode, SamplingStrategy, ViewDirectionMode

SampledCenterMode: TypeAlias = Literal[  # type: ignore[valid-type]
    CandidatePositionMode.UPPER_BOUND_FREE_SHELL,
    CandidatePositionMode.FORWARD_LOCAL,
    CandidatePositionMode.TARGET_BEARING_LOCAL,
    CandidatePositionMode.LATERAL_TARGET_BYPASS,
    CandidatePositionMode.LOCAL_REFINEMENT,
    CandidatePositionMode.REVISIT_BACKTRACK,
]
"""Center modes whose geometry is produced by the sampled-center kernel."""


class SampledCenterConfig(BaseConfig):
    """Configure one sampled candidate-center family in the proposal frame."""

    kind: Literal["sampled"] = "sampled"
    """Discriminator for sampled-center authoring; provenance uses ``mode``."""

    mode: SampledCenterMode
    """Semantic center family applied in the gravity-aligned proposal frame."""

    sampling_strategy: SamplingStrategy
    """Distribution used to draw proposal directions before family shaping."""

    min_radius_m: float = Field(ge=0.0)
    """Minimum sampled displacement from the reference center, in metres."""

    max_radius_m: float = Field(gt=0.0)
    """Maximum sampled displacement from the reference center, in metres."""

    min_elevation_deg: float = Field(ge=-90.0, le=90.0)
    """Lower world-horizontal elevation bound in degrees, inclusive."""

    max_elevation_deg: float = Field(ge=-90.0, le=90.0)
    """Upper world-horizontal elevation bound in degrees, inclusive."""

    azimuth_width_deg: float = Field(gt=0.0, le=360.0)
    """Full azimuth support width about proposal-frame forward, in degrees."""

    concentration: float = Field(ge=0.0)
    """Power-spherical concentration; ignored by uniform-sphere sampling."""

    @model_validator(mode="after")
    def _validate_support(self) -> Self:
        if self.min_radius_m > self.max_radius_m:
            raise ValueError("min_radius_m must not exceed max_radius_m")
        if self.min_elevation_deg > self.max_elevation_deg:
            raise ValueError("min_elevation_deg must not exceed max_elevation_deg")
        return self


class TargetOrbitCenterConfig(BaseConfig):
    """Configure bilateral target-relative centers at current horizontal standoff."""

    kind: Literal["target_orbit"] = "target_orbit"
    """Discriminator for target-orbit authoring; provenance is target orbit."""

    angles_deg: tuple[float, ...]
    """Ordered signed orbit angles in degrees; both target sides are required."""

    standoff_mode: Literal["current_horizontal"] = "current_horizontal"
    """Keep each center at the actor's current world-horizontal target radius."""

    @field_validator("angles_deg")
    @classmethod
    def _validate_angles(cls, angles: tuple[float, ...]) -> tuple[float, ...]:
        values = tuple(float(angle) for angle in angles)
        if not values:
            raise ValueError("angles_deg must not be empty")
        if any(not isfinite(angle) or abs(angle) >= 180.0 or abs(angle) < 1e-6 for angle in values):
            raise ValueError("angles_deg must contain finite nonzero angles with abs(angle) < 180")
        if not any(angle < 0.0 for angle in values) or not any(angle > 0.0 for angle in values):
            raise ValueError("angles_deg must cover both sides of the target")
        return values


CenterConfig = Annotated[
    SampledCenterConfig | TargetOrbitCenterConfig,
    Field(discriminator="kind"),
]
"""Discriminated center-family authoring accepted by mixed generation."""


class NoViewJitterConfig(BaseConfig):
    """Represent a deterministic gaze with no residual orientation jitter."""

    kind: Literal["none"] = "none"
    """Discriminator whose generation meaning is exactly zero residual jitter."""


class BoxViewJitterConfig(BaseConfig):
    """Configure independent bounded local-camera yaw, pitch, and roll jitter."""

    kind: Literal["box"] = "box"
    """Discriminator for bounded local-camera angular support."""

    yaw_half_width_deg: float = Field(default=60.0, ge=0.0, le=180.0)
    """Symmetric local-camera yaw half-width in degrees; seminar default is 60."""

    pitch_half_width_deg: float = Field(default=30.0, ge=0.0, le=90.0)
    """Symmetric local-camera pitch half-width in degrees; seminar default is 30."""

    roll_half_width_deg: float = Field(default=0.0, ge=0.0, le=180.0)
    """Symmetric roll half-width about the sampled forward axis, in degrees."""

    @model_validator(mode="after")
    def _require_nonzero_support(self) -> Self:
        if self.yaw_half_width_deg == self.pitch_half_width_deg == self.roll_half_width_deg == 0.0:
            raise ValueError("zero box jitter is ambiguous; use NoViewJitterConfig")
        return self


class SphericalViewJitterConfig(BaseConfig):
    """Configure uncapped spherical forward-axis jitter plus bounded roll."""

    kind: Literal["spherical"] = "spherical"
    """Discriminator for uncapped spherical directional support."""

    distribution: SamplingStrategy
    """Sphere distribution used to sample the local-camera forward direction."""

    concentration: float = Field(ge=0.0)
    """Power-spherical concentration; ignored by uniform-sphere sampling."""

    roll_half_width_deg: float = Field(default=0.0, ge=0.0, le=180.0)
    """Symmetric roll half-width about the sampled forward axis, in degrees."""


ViewJitterConfig = Annotated[
    NoViewJitterConfig | BoxViewJitterConfig | SphericalViewJitterConfig,
    Field(discriminator="kind"),
]
"""Discriminated residual-orientation support for one gaze variant."""


class CandidateGazeConfig(BaseConfig):
    """Apply one named orientation family to every center in a component."""

    name: str = Field(min_length=1)
    """Variant name used only for later-gaze provenance and seed identity."""

    mode: ViewDirectionMode
    """Base camera orientation family applied before residual jitter."""

    jitter: ViewJitterConfig
    """Residual local-camera orientation support used during generation."""


class CandidateMixtureComponentConfig(BaseConfig):
    """Configure one center table and its ordered gaze variants."""

    name: str = Field(min_length=1)
    """Stable component name retained as provenance for the first gaze."""

    count: int = Field(gt=0)
    """Number of attempted centers sampled once before gaze expansion."""

    center: CenterConfig
    """Complete positional proposal configuration for the shared center table."""

    gazes: tuple[CandidateGazeConfig, ...]
    """Ordered gaze variants; row order is gaze-major within this component."""

    def _propagate_to_child(self, parent_field: str, child_config: BaseConfig) -> None:
        """Keep component and gaze provenance names independently authored."""

        if parent_field == "gazes" and isinstance(child_config, CandidateGazeConfig):
            return
        super()._propagate_to_child(parent_field, child_config)

    @model_validator(mode="after")
    def _validate_component(self) -> Self:
        if not self.gazes:
            raise ValueError("candidate component requires at least one gaze")
        names = tuple(gaze.name for gaze in self.gazes)
        if len(names) != len(set(names)):
            raise ValueError("candidate gaze names must be unique within a component")
        return self


__all__ = [
    "BoxViewJitterConfig",
    "CandidateGazeConfig",
    "CandidateMixtureComponentConfig",
    "CenterConfig",
    "NoViewJitterConfig",
    "SampledCenterConfig",
    "SampledCenterMode",
    "SphericalViewJitterConfig",
    "TargetOrbitCenterConfig",
    "ViewJitterConfig",
]
