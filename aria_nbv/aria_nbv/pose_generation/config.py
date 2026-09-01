"""Composable authoring values for mixed candidate center and gaze groups."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal, Self, TypeAlias

from pydantic import Field, FiniteFloat, field_validator, model_validator

from ..utils import BaseConfig
from .types import CandidatePositionMode, SamplingStrategy, ViewDirectionMode

SampledCenterMode: TypeAlias = Literal[
    CandidatePositionMode.UPPER_BOUND_FREE_SHELL,
    CandidatePositionMode.FORWARD_LOCAL,
    CandidatePositionMode.TARGET_BEARING_LOCAL,
    CandidatePositionMode.LATERAL_TARGET_BYPASS,
    CandidatePositionMode.LOCAL_REFINEMENT,
    CandidatePositionMode.REVISIT_BACKTRACK,
]
"""Center modes whose geometry is produced by the sampled-center kernel."""


NonNegativeFiniteFloat = Annotated[FiniteFloat, Field(ge=0.0)]
PositiveFiniteFloat = Annotated[FiniteFloat, Field(gt=0.0)]
ElevationDeg = Annotated[FiniteFloat, Field(ge=-90.0, le=90.0)]
AzimuthWidthDeg = Annotated[FiniteFloat, Field(gt=0.0, le=360.0)]
YawHalfWidthDeg = Annotated[FiniteFloat, Field(ge=0.0, le=180.0)]
PitchHalfWidthDeg = Annotated[FiniteFloat, Field(ge=0.0, le=90.0)]
OrbitAngleDeg = Annotated[FiniteFloat, Field(gt=-180.0, lt=180.0)]


class SampledCenterConfig(BaseConfig):
    """Configure one sampled candidate-center family in the proposal frame."""

    kind: Literal["sampled"] = "sampled"
    """Discriminator for sampled-center authoring; provenance uses ``mode``."""

    mode: SampledCenterMode
    """Semantic center family applied in the gravity-aligned proposal frame."""

    sampling_strategy: SamplingStrategy = SamplingStrategy.FORWARD_POWERSPHERICAL
    """Distribution used to draw proposal directions before family shaping."""

    min_radius_m: NonNegativeFiniteFloat = 0.25
    """Minimum sampled displacement from the reference center, in metres."""

    max_radius_m: PositiveFiniteFloat = 1.25
    """Maximum sampled displacement from the reference center, in metres."""

    min_elevation_deg: ElevationDeg = -12.0
    """Lower world-horizontal elevation bound in degrees, inclusive."""

    max_elevation_deg: ElevationDeg = 18.0
    """Upper world-horizontal elevation bound in degrees, inclusive."""

    azimuth_width_deg: AzimuthWidthDeg = 120.0
    """Full azimuth support width about proposal-frame forward, in degrees."""

    concentration: NonNegativeFiniteFloat = 8.0
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

    angles_deg: tuple[OrbitAngleDeg, ...]
    """Ordered signed orbit angles in degrees; both target sides are required."""

    standoff_mode: Literal["current_horizontal"] = "current_horizontal"
    """Keep each center at the actor's current world-horizontal target radius."""

    @field_validator("angles_deg")
    @classmethod
    def _validate_angles(cls, angles: tuple[float, ...]) -> tuple[float, ...]:
        values = tuple(float(angle) for angle in angles)
        if not values:
            raise ValueError("angles_deg must not be empty")
        if any(abs(angle) < 1e-6 for angle in values):
            raise ValueError("angles_deg must contain nonzero angles")
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

    yaw_half_width_deg: YawHalfWidthDeg = 60.0
    """Symmetric local-camera yaw half-width in degrees; seminar default is 60."""

    pitch_half_width_deg: PitchHalfWidthDeg = 30.0
    """Symmetric local-camera pitch half-width in degrees; seminar default is 30."""

    roll_half_width_deg: YawHalfWidthDeg = 0.0
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

    concentration: NonNegativeFiniteFloat
    """Power-spherical concentration; ignored by uniform-sphere sampling."""

    roll_half_width_deg: YawHalfWidthDeg = 0.0
    """Symmetric roll half-width about the sampled forward axis, in degrees."""


ViewJitterConfig = Annotated[
    NoViewJitterConfig | BoxViewJitterConfig | SphericalViewJitterConfig,
    Field(discriminator="kind"),
]
"""Discriminated residual-orientation support for one gaze variant."""


class CandidateGazeConfig(BaseConfig):
    """Apply one named orientation family to every center in a component."""

    name: str = Field(default="primary", min_length=1)
    """Variant name used only for later-gaze provenance and seed identity."""

    mode: ViewDirectionMode
    """Base camera orientation family applied before residual jitter."""

    jitter: ViewJitterConfig = Field(default_factory=BoxViewJitterConfig)
    """Residual local-camera orientation support used during generation."""

    @classmethod
    def from_legacy(
        cls,
        *,
        mode: ViewDirectionMode,
        sampling_strategy: SamplingStrategy | None,
        concentration: float,
        yaw_half_width_deg: float,
        pitch_half_width_deg: float,
        roll_half_width_deg: float,
        name: str = "primary",
    ) -> "CandidateGazeConfig":
        """Validate the retained flat gaze controls into one nested value."""

        if yaw_half_width_deg > 0.0 or pitch_half_width_deg > 0.0:
            jitter: ViewJitterConfig = BoxViewJitterConfig(
                yaw_half_width_deg=yaw_half_width_deg,
                pitch_half_width_deg=pitch_half_width_deg,
                roll_half_width_deg=roll_half_width_deg,
            )
        elif sampling_strategy is not None:
            jitter = SphericalViewJitterConfig(
                distribution=sampling_strategy,
                concentration=concentration,
                roll_half_width_deg=roll_half_width_deg,
            )
        elif roll_half_width_deg > 0.0:
            jitter = BoxViewJitterConfig(
                yaw_half_width_deg=0.0,
                pitch_half_width_deg=0.0,
                roll_half_width_deg=roll_half_width_deg,
            )
        else:
            jitter = NoViewJitterConfig()
        return cls(name=name, mode=mode, jitter=jitter)


class CandidateMixtureComponentConfig(BaseConfig):
    """Configure one center table and its ordered gaze variants."""

    propagation_exclude_fields: ClassVar[set[str]] = {"name"}

    name: str = Field(min_length=1)
    """Stable component name retained as provenance for the first gaze."""

    count: int = Field(gt=0)
    """Number of attempted centers sampled once before gaze expansion."""

    center: CenterConfig
    """Complete positional proposal configuration for the shared center table."""

    gazes: tuple[CandidateGazeConfig, ...]
    """Ordered gaze variants; row order is gaze-major within this component."""

    @model_validator(mode="after")
    def _validate_component(self) -> Self:
        if not self.gazes:
            raise ValueError("candidate component requires at least one gaze")
        names = tuple(gaze.name for gaze in self.gazes)
        if len(names) != len(set(names)):
            raise ValueError("candidate gaze names must be unique within a component")
        return self

    def with_count(self, count: int) -> "CandidateMixtureComponentConfig":
        """Return a fully revalidated component with a replacement count."""

        return type(self).model_validate(self.model_dump() | {"count": count})


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
