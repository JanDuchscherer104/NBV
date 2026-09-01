"""Composable authoring values for mixed candidate center and gaze groups."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Literal, Self, TypeAlias

from pydantic import Field, FiniteFloat, field_validator, model_validator

from ..utils import BaseConfig
from .types import CandidatePositionMode, SamplingStrategy, ViewDirectionMode

if TYPE_CHECKING:
    from .candidate_generation import CandidateViewGeneratorConfig

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


class UniformSphereConfig(BaseConfig):
    """Select area-uniform directional sampling without inert parameters."""

    model_config = BaseConfig.model_config | {"extra": "forbid"}
    propagation_exclude_fields = {"kind"}

    kind: Literal[SamplingStrategy.UNIFORM_SPHERE] = SamplingStrategy.UNIFORM_SPHERE


class PowerSphericalConfig(BaseConfig):
    """Select forward-biased power-spherical sampling."""

    model_config = BaseConfig.model_config | {"extra": "forbid"}
    propagation_exclude_fields = {"kind"}

    kind: Literal[SamplingStrategy.FORWARD_POWERSPHERICAL] = SamplingStrategy.FORWARD_POWERSPHERICAL
    concentration: NonNegativeFiniteFloat = 8.0


SphereDistributionConfig = Annotated[
    UniformSphereConfig | PowerSphericalConfig,
    Field(discriminator="kind"),
]


def sphere_distribution_from_legacy(
    strategy: SamplingStrategy,
    concentration: float,
) -> SphereDistributionConfig:
    """Validate retained flat distribution controls into one closed value."""

    if strategy is SamplingStrategy.UNIFORM_SPHERE:
        return UniformSphereConfig()
    return PowerSphericalConfig(concentration=concentration)


class SampledCenterConfig(BaseConfig):
    """Configure one sampled candidate-center family in the proposal frame."""

    kind: Literal["sampled"] = "sampled"
    """Discriminator for sampled-center authoring; provenance uses ``mode``."""

    mode: SampledCenterMode
    """Semantic center family applied in the gravity-aligned proposal frame."""

    distribution: SphereDistributionConfig = Field(default_factory=PowerSphericalConfig)
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

    @classmethod
    def from_legacy(
        cls,
        base: "CandidateViewGeneratorConfig",
        *,
        mode: SampledCenterMode,
        min_radius_m: float | None = None,
        max_radius_m: float | None = None,
    ) -> "SampledCenterConfig":
        """Validate retained flat center controls into one nested value."""

        return cls(
            mode=mode,
            distribution=sphere_distribution_from_legacy(base.sampling_strategy, base.kappa),
            min_radius_m=base.min_radius if min_radius_m is None else min_radius_m,
            max_radius_m=base.max_radius if max_radius_m is None else max_radius_m,
            min_elevation_deg=base.min_elev_deg,
            max_elevation_deg=base.max_elev_deg,
            azimuth_width_deg=base.delta_azimuth_deg,
        )

    @model_validator(mode="before")
    @classmethod
    def _migrate_flat_distribution(cls, value: Any) -> Any:
        """Canonicalize retained flat TOML fields into the distribution value."""

        if not isinstance(value, Mapping) or "distribution" in value or "sampling_strategy" not in value:
            return value
        migrated = dict(value)
        strategy = SamplingStrategy(migrated.pop("sampling_strategy"))
        concentration = float(migrated.pop("concentration", 8.0))
        migrated["distribution"] = sphere_distribution_from_legacy(strategy, concentration).model_dump()
        return migrated

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


class AngularBoxSupportConfig(BaseConfig):
    """Configure a target-relative azimuth/elevation support box."""

    support_kind: Literal["angular_box"] = "angular_box"
    """Discriminator for world-horizontal angular-box support."""

    azimuth_half_width_deg: float = Field(default=180.0, gt=0.0, le=180.0)
    """Signed half-width about the target-to-actor horizontal bearing, in degrees."""

    elevation_min_deg: float = Field(default=-90.0, ge=-90.0, le=90.0)
    """Minimum world-horizontal elevation in the target-aligned frame, in degrees."""

    elevation_max_deg: float = Field(default=90.0, ge=-90.0, le=90.0)
    """Maximum world-horizontal elevation in the target-aligned frame, in degrees."""

    @model_validator(mode="after")
    def _validate_elevation_order(self) -> Self:
        if self.elevation_min_deg > self.elevation_max_deg:
            raise ValueError("elevation_min_deg must not exceed elevation_max_deg")
        return self


class ActorFacingCapSupportConfig(BaseConfig):
    """Configure rotationally symmetric support about the target-to-actor ray."""

    support_kind: Literal["actor_facing_cap"] = "actor_facing_cap"
    """Discriminator for actor-facing spherical-cap support."""

    half_angle_deg: float = Field(gt=0.0, le=180.0)
    """Cone half-angle about the three-dimensional target-to-actor ray, in degrees."""


TargetShellSupportConfig = Annotated[
    AngularBoxSupportConfig | ActorFacingCapSupportConfig,
    Field(discriminator="support_kind"),
]
"""Discriminated directional support for target-centric shell centers."""


class TargetShellCenterConfig(BaseConfig):
    """Configure an opt-in target-centric spherical-shell center family."""

    kind: Literal["target_shell"] = "target_shell"
    """Discriminator for target-shell authoring; provenance is target shell."""

    radius_min_m: float = Field(gt=0.0)
    """Minimum target-to-candidate radius in metres; equal bounds are valid."""

    radius_max_m: float = Field(gt=0.0)
    """Maximum target-to-candidate radius in metres; equal bounds are valid."""

    support: TargetShellSupportConfig
    """Complete directional support; serialized identity contains only active fields."""

    @model_validator(mode="after")
    def _validate_support(self) -> Self:
        if self.radius_min_m > self.radius_max_m:
            raise ValueError("radius_min_m must not exceed radius_max_m")
        return self


CenterConfig = Annotated[
    SampledCenterConfig | TargetOrbitCenterConfig | TargetShellCenterConfig,
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

    distribution: SphereDistributionConfig
    """Closed sphere distribution used to sample the local-camera forward direction."""

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
                distribution=sphere_distribution_from_legacy(sampling_strategy, concentration),
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
    "ActorFacingCapSupportConfig",
    "AngularBoxSupportConfig",
    "BoxViewJitterConfig",
    "CandidateGazeConfig",
    "CandidateMixtureComponentConfig",
    "CenterConfig",
    "NoViewJitterConfig",
    "PowerSphericalConfig",
    "SampledCenterConfig",
    "SampledCenterMode",
    "SphericalViewJitterConfig",
    "SphereDistributionConfig",
    "TargetOrbitCenterConfig",
    "TargetShellCenterConfig",
    "TargetShellSupportConfig",
    "UniformSphereConfig",
    "ViewJitterConfig",
    "sphere_distribution_from_legacy",
]
