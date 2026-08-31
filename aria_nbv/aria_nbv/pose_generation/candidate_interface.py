"""Final request/result interface for finite candidate generation."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from math import isfinite
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Protocol, cast

import torch
from efm3d.aria.camera import CameraTW
from efm3d.aria.pose import PoseTW

from ..geometry import PreparedMeshQuery
from ..geometry.point_mesh import tensor_identity_token
from ..targets import TargetDescriptor
from ..utils.canonical_binding import BindingEncodingRevision, canonical_binding_sha256
from .candidate_errors import CandidateAlignmentCorruptionError, CandidateRequestMismatchError
from .candidate_program import CandidateProgram, CompletionMode
from .sampling_keys import CandidateSamplingKey, CandidateSubstreamRevision
from .types import CandidateSamplingResult

if TYPE_CHECKING:
    import trimesh


def _efm_tensor(value: PoseTW | CameraTW) -> torch.Tensor:
    """Cross the untyped EFM wrapper boundary with a typed tensor result."""

    accessor: Callable[[], Any] = value.tensor
    return cast(torch.Tensor, accessor())


class GeometrySourceRole(StrEnum):
    """Scientific role of scene geometry used by hard admission."""

    ORACLE_ADMISSION = "oracle_admission"


class CriterionSourceRole(IntEnum):
    """Source class used to evaluate one admission criterion."""

    ACTOR_VISIBLE = 1
    ORACLE_ADMISSION = 2


class CriterionReasonCode(IntEnum):
    """Closed criterion-local admission outcomes."""

    UNAVAILABLE = -1
    PASSED = 0
    OUTSIDE_SUPPORT_ENVELOPE = 1
    MAX_STEP_DISTANCE_EXCEEDED = 2
    MAX_HEIGHT_DELTA_EXCEEDED = 3
    MAX_BACKWARD_STEP_EXCEEDED = 4
    MAX_YAW_DELTA_EXCEEDED = 5
    ENDPOINT_CLEARANCE_TOO_SMALL = 6
    PATH_CLEARANCE_TOO_SMALL = 7


class CriterionReasonRevision(StrEnum):
    """Owner/revision of criterion-local reason codes."""

    UNAVAILABLE_V1 = "unavailable_v1"
    CANDIDATE_ADMISSION_V1 = "candidate_admission_v1"


class CriterionSourceRoleRevision(StrEnum):
    """Owner/revision of criterion-local source-role codes."""

    UNAVAILABLE_V1 = "unavailable_v1"
    CANDIDATE_ADMISSION_V1 = "candidate_admission_v1"


class EvidenceAvailability(StrEnum):
    """Availability of a typed evidence axis."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class ActionOrderRevision(StrEnum):
    """Ordering rule used by scoreable action indices."""

    ORDERED_HARD_VALID_V1 = "ordered_hard_valid_v1"


class LegacyCandidateProjectionUnsupported(CandidateAlignmentCorruptionError):  # noqa: N818 - plan-owned typed gate name.
    """Raised when a candidate set cannot be represented by the V-only DTO."""


@dataclass(frozen=True, slots=True)
class _FixedValidProof:
    """Mutation receipts proving that ``action_indices`` is the generated V table."""

    admission_token: tuple[object, ...]
    action_token: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class _LegacyProjectionVariant:
    """One immutable compatibility mapping expanded only by the outward adapter."""

    candidate_family_id: str
    strategy_id: int
    component_name: str


@dataclass(frozen=True, slots=True)
class _LegacyProjectionGroup:
    """Group-level legacy identity without a second candidate-row table."""

    semantic_group_id: str
    position_id: int
    mixture_id: int
    sampler_probability: float
    variants: tuple[_LegacyProjectionVariant, ...]


@dataclass(frozen=True, slots=True)
class ActorTargetContext:
    """Actor-safe target instruction with composition-owned identity.

    Attributes:
        descriptor: Immutable actor-visible target geometry and semantics.
        protocol_version: Nonempty target-instruction protocol revision.
        descriptor_hash: Canonical SHA-256 binding of ``descriptor``.
        source_binding_hash: Composition-owned source/lineage binding.

    The composition root constructs this once; generation only consumes and
    receipt-validates it and performs no target reacquisition.
    """

    descriptor: TargetDescriptor
    protocol_version: str
    descriptor_hash: str
    source_binding_hash: str
    _actor_value_hash: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.descriptor_hash != canonical_binding_sha256(self.descriptor):
            raise CandidateRequestMismatchError("Actor target descriptor_hash does not match descriptor content.")
        if not self.protocol_version or not self.source_binding_hash:
            raise CandidateRequestMismatchError("Actor target protocol and source binding must be explicit.")
        object.__setattr__(
            self,
            "_actor_value_hash",
            canonical_binding_sha256((self.descriptor_hash, self.protocol_version, self.source_binding_hash)),
        )


@dataclass(frozen=True, slots=True)
class CandidateConditioning:
    """Facts required to generate one spatial action from the current pose.

    Attributes:
        reference_pose_world: ``PoseTW`` world-from-rig transform with logical
            shape ``(12,)`` and floating dtype on the request device.
        action_duration_s: Optional positive action duration in seconds.

    Construction binds pose value and mutation receipts once. Warm generation
    validates metadata receipts without transferring pose values to the host.
    """

    reference_pose_world: PoseTW
    """World <- reference rig pose with logical shape ``(12,)``."""

    action_duration_s: float | None = None
    """Optional one-action duration in seconds."""

    _pose_identity: tuple[object, ...] = field(init=False, repr=False, compare=False)
    _pose_value_hash: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        pose_tensor = _efm_tensor(self.reference_pose_world)
        if not bool(torch.isfinite(pose_tensor).all().item()):
            raise CandidateRequestMismatchError("Candidate conditioning pose must be finite.")
        if self.action_duration_s is not None and (
            isinstance(self.action_duration_s, bool)
            or not isinstance(self.action_duration_s, (int, float))
            or not isfinite(float(self.action_duration_s))
            or self.action_duration_s <= 0.0
        ):
            raise CandidateRequestMismatchError("Candidate action_duration_s must be finite and positive.")
        token = tensor_identity_token(pose_tensor)
        if token is None:
            raise CandidateRequestMismatchError("Candidate conditioning pose must expose a mutation receipt.")
        object.__setattr__(self, "_pose_identity", token)
        object.__setattr__(self, "_pose_value_hash", canonical_binding_sha256(self.reference_pose_world))

    def validate_identity(self) -> None:
        """Validate the pose receipt without copying tensor values to the host."""

        if tensor_identity_token(_efm_tensor(self.reference_pose_world)) != self._pose_identity:
            raise CandidateRequestMismatchError("Candidate conditioning pose changed after binding.")


@dataclass(frozen=True, slots=True)
class PreparedCandidateScene:
    """Composition-bound scene facts and geometry-owner query state.

    Attributes:
        scene_identity: Composition-owned factual scene identity.
        source_binding_hash: Canonical source/lineage binding.
        mesh_identity: Stable mesh-content identity supplied by composition.
        gt_mesh: CPU trimesh source used by legacy-compatible backends.
        mesh_verts: World-frame mesh vertices ``Tensor["V 3", float]`` in metres.
        mesh_faces: Triangle indices ``Tensor["F 3", int64]``.
        prepared_mesh_query: Optional sole-owner prepared query matching the raw
            mesh tensors; generation reuses it and never reacquires it.
        occupancy_extent_world: World XYZ bounds ``Tensor["6", float]`` in metres.
        camera_calibration: Full calibrated ``CameraTW`` template.
        camera_calibration_hash: Canonical calibration value binding.
        geometry_source_role: Actor/Oracle role of the geometry evidence.
        device: Device shared by all tensor-valued scene facts.
        dtype: Floating dtype shared by vertices, extent, and calibration.

    The composition root owns construction and prepared-query lifecycle. Warm
    generation performs metadata/receipt validation only.
    """

    scene_identity: str
    source_binding_hash: str
    mesh_identity: str
    gt_mesh: trimesh.Trimesh
    mesh_verts: torch.Tensor
    mesh_faces: torch.Tensor
    prepared_mesh_query: PreparedMeshQuery | None
    occupancy_extent_world: torch.Tensor
    camera_calibration: CameraTW
    camera_calibration_hash: str
    geometry_source_role: GeometrySourceRole
    device: torch.device
    dtype: torch.dtype

    _calibration_identity: tuple[object, ...] = field(init=False, repr=False, compare=False)
    _extent_identity: tuple[object, ...] = field(init=False, repr=False, compare=False)
    _scene_value_hash: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.device, (str, torch.device)) or not isinstance(self.dtype, torch.dtype):
            raise CandidateRequestMismatchError("Prepared scene device and dtype must be declared Torch values.")
        try:
            resolved_device = torch.device(self.device)
        except (RuntimeError, TypeError, ValueError) as error:
            raise CandidateRequestMismatchError("Prepared scene device is invalid.") from error
        if resolved_device.type == "cuda" and resolved_device.index is None:
            resolved_device = torch.device("cuda", torch.cuda.current_device())
        object.__setattr__(self, "device", resolved_device)
        if not isinstance(self.geometry_source_role, GeometrySourceRole):
            raise CandidateRequestMismatchError("Prepared scene geometry_source_role is undeclared.")
        if not self.scene_identity or not self.source_binding_hash or not self.mesh_identity:
            raise CandidateRequestMismatchError("Prepared scene identities must be supplied by the composition owner.")
        if not self.dtype.is_floating_point:
            raise CandidateRequestMismatchError("Prepared scene dtype must be floating point.")
        if self.mesh_verts.ndim != 2 or self.mesh_verts.shape[1:] != (3,) or not self.mesh_verts.is_floating_point():
            raise CandidateRequestMismatchError("mesh_verts must be a floating-point (V, 3) tensor.")
        if self.mesh_faces.ndim != 2 or self.mesh_faces.shape[1:] != (3,) or self.mesh_faces.dtype is not torch.int64:
            raise CandidateRequestMismatchError("mesh_faces must be an int64 (F, 3) tensor.")
        if self.occupancy_extent_world.shape != (6,) or not self.occupancy_extent_world.is_floating_point():
            raise CandidateRequestMismatchError("occupancy_extent_world must contain six values.")
        calibration_tensor = _efm_tensor(self.camera_calibration)
        value_tensors = (self.mesh_verts, self.mesh_faces, self.occupancy_extent_world, calibration_tensor)
        if any(tensor.device != self.device for tensor in value_tensors):
            raise CandidateRequestMismatchError("Prepared scene tensors must reside on the declared device.")
        if self.mesh_verts.dtype != self.dtype or self.occupancy_extent_world.dtype != self.dtype:
            raise CandidateRequestMismatchError("Prepared scene floating tensors must use the declared dtype.")
        if calibration_tensor.dtype != self.dtype:
            raise CandidateRequestMismatchError("Prepared scene calibration must use the declared dtype.")
        if not bool(torch.isfinite(self.occupancy_extent_world).all().item()):
            raise CandidateRequestMismatchError("Prepared scene extent must be finite.")
        extent = self.occupancy_extent_world
        if not bool((extent[0::2] < extent[1::2]).all().item()):
            raise CandidateRequestMismatchError("Prepared scene extent minima must be below maxima.")
        if self.camera_calibration_hash != canonical_binding_sha256(self.camera_calibration):
            raise CandidateRequestMismatchError("camera_calibration_hash does not match calibration content.")
        if self.prepared_mesh_query is not None and not self.prepared_mesh_query.matches_request(
            self.mesh_verts,
            self.mesh_faces,
            device=self.device,
            dtype=self.dtype,
            mesh=self.gt_mesh,
        ):
            raise CandidateRequestMismatchError("Prepared mesh query does not match the bound raw mesh sources.")
        calibration_token = tensor_identity_token(calibration_tensor)
        extent_token = tensor_identity_token(self.occupancy_extent_world)
        if calibration_token is None or extent_token is None:
            raise CandidateRequestMismatchError("Prepared scene value tensors must expose mutation receipts.")
        object.__setattr__(self, "_calibration_identity", calibration_token)
        object.__setattr__(self, "_extent_identity", extent_token)
        object.__setattr__(
            self,
            "_scene_value_hash",
            canonical_binding_sha256(
                (
                    self.scene_identity,
                    self.source_binding_hash,
                    self.mesh_identity,
                    self.occupancy_extent_world,
                    self.camera_calibration_hash,
                    self.geometry_source_role,
                    self.device,
                    self.dtype,
                )
            ),
        )

    def validate_identity(self) -> None:
        """Validate scene/query receipts without host transfers or re-hashing values."""

        if tensor_identity_token(_efm_tensor(self.camera_calibration)) != self._calibration_identity:
            raise CandidateRequestMismatchError("Camera calibration changed after scene binding.")
        if tensor_identity_token(self.occupancy_extent_world) != self._extent_identity:
            raise CandidateRequestMismatchError("Occupancy extent changed after scene binding.")
        if self.prepared_mesh_query is not None and not self.prepared_mesh_query.matches_request(
            self.mesh_verts,
            self.mesh_faces,
            device=self.device,
            dtype=self.dtype,
            mesh=self.gt_mesh,
        ):
            raise CandidateRequestMismatchError("Prepared mesh query sources changed after scene binding.")


@dataclass(frozen=True, slots=True)
class CandidateRequest:
    """Complete input to one score-independent generation operation.

    Attributes:
        program: Verified immutable candidate program.
        conditioning: Bound reference pose and optional action duration.
        scene: Prepared scene and sole geometry-query lifecycle owner.
        actor_target: Optional actor-visible target binding.
        random_key: Explicit sampling source, revision, and root seed.
        binding_encoding_revision: Canonical request encoding revision.
        request_binding_hash: SHA-256 binding of all semantic request facts.

    Use :meth:`bind` at composition. The generator calls metadata-only receipt
    validation and neither reconstructs configuration nor reacquires inputs.
    """

    program: CandidateProgram
    conditioning: CandidateConditioning
    scene: PreparedCandidateScene
    actor_target: ActorTargetContext | None
    random_key: CandidateSamplingKey
    binding_encoding_revision: BindingEncodingRevision
    request_binding_hash: str
    _program_identity: tuple[int, str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.program.validate()
        if self.program.candidate_program_hash != self.program.verified_hash():
            raise CandidateRequestMismatchError("Candidate program hash does not match literal program content.")
        if self.binding_encoding_revision is not BindingEncodingRevision.CANONICAL_SHA256_V1:
            raise CandidateRequestMismatchError("Candidate request binding revision is undeclared.")
        _validate_request_axes(self.conditioning, self.scene)
        _validate_sampling_compatibility(self.program, self.random_key)
        expected = _request_hash(
            self.binding_encoding_revision,
            self.program,
            self.conditioning,
            self.scene,
            self.actor_target,
            self.random_key,
        )
        if self.request_binding_hash != expected:
            raise CandidateRequestMismatchError("Candidate request binding does not match its typed facts.")
        object.__setattr__(
            self,
            "_program_identity",
            (id(self.program), self.program.candidate_program_hash),
        )

    @classmethod
    def bind(
        cls,
        *,
        program: CandidateProgram,
        conditioning: CandidateConditioning,
        scene: PreparedCandidateScene,
        actor_target: ActorTargetContext | None,
        random_key: CandidateSamplingKey,
    ) -> CandidateRequest:
        """Validate typed identities and bind one request canonically."""

        program.validate()
        if program.candidate_program_hash != program.verified_hash():
            raise CandidateRequestMismatchError("Candidate program hash does not match literal program content.")
        _validate_request_axes(conditioning, scene)
        _validate_sampling_compatibility(program, random_key)
        revision = BindingEncodingRevision.CANONICAL_SHA256_V1
        digest = _request_hash(revision, program, conditioning, scene, actor_target, random_key)
        return cls(program, conditioning, scene, actor_target, random_key, revision, digest)

    def validate_binding(self) -> None:
        """Cold diagnostic validation of every canonical binding."""

        self.program.validate()
        if self.program.candidate_program_hash != self.program.verified_hash():
            raise CandidateRequestMismatchError("Candidate program content changed after binding.")
        if self.actor_target is not None:
            self.actor_target.__post_init__()
        self.conditioning.validate_identity()
        self.scene.validate_identity()
        expected = _request_hash(
            self.binding_encoding_revision,
            self.program,
            self.conditioning,
            self.scene,
            self.actor_target,
            self.random_key,
        )
        if self.request_binding_hash != expected:
            raise CandidateRequestMismatchError("Candidate request binding changed after composition.")

    def validate_for_generate(self) -> None:
        """Validate mutation receipts without canonical encoding or host transfers."""

        self.program.validate()
        self.conditioning.validate_identity()
        self.scene.validate_identity()
        if (id(self.program), self.program.candidate_program_hash) != self._program_identity:
            raise CandidateRequestMismatchError("Candidate program identity changed after binding.")


@dataclass(frozen=True, slots=True)
class CandidateMeasurements:
    """Closed tensor-only proposal measurements aligned over ``N`` rows.

    Every present field is a device-aligned ``Tensor["N ..."]`` owned by the
    generator/admission boundary. Boolean ``*_mask`` fields encode factual
    applicability, evaluation, rejection, or visibility. Distance/clearance/
    step fields ending in ``_m`` use metres; angular fields ending in ``_rad``
    or ``_deg`` use radians or degrees; ``target_pixel_margin_px`` uses pixels.
    ``view_dirs_delta`` retains the shipped pose residual representation.
    Consumers treat absent tensors as unavailable and never reacquire geometry.
    """

    view_dirs_delta: torch.Tensor | None = None
    path_collision_applicable_mask: torch.Tensor | None = None
    path_collision_evaluated_mask: torch.Tensor | None = None
    path_collision_detected: torch.Tensor | None = None
    path_collision_mask: torch.Tensor | None = None
    path_collision_applicable: torch.Tensor | None = None
    path_collision_evaluated: torch.Tensor | None = None
    min_distance_to_mesh: torch.Tensor | None = None
    path_min_clearance_m: torch.Tensor | None = None
    motion_step_length_m: torch.Tensor | None = None
    motion_height_delta_m: torch.Tensor | None = None
    motion_backward_step_m: torch.Tensor | None = None
    motion_yaw_delta_rad: torch.Tensor | None = None
    motion_realism_reject_mask: torch.Tensor | None = None
    free_space_margin_m: torch.Tensor | None = None
    target_bearing_yaw_rad: torch.Tensor | None = None
    target_distance_m: torch.Tensor | None = None
    target_view_angle_deg: torch.Tensor | None = None
    target_pixel_margin_px: torch.Tensor | None = None
    target_in_fov_mask: torch.Tensor | None = None
    target_view_evaluated_mask: torch.Tensor | None = None

    def legacy_tensors(self) -> dict[str, torch.Tensor]:
        """Project present typed measurements to compatibility extra names."""

        return {name: value for name in self.__dataclass_fields__ if (value := getattr(self, name)) is not None}


@dataclass(frozen=True, slots=True)
class CandidateTable:
    """Canonical full attempted shell aligned over ``N`` rows.

    Attributes:
        world_poses: Attempted world-from-camera ``PoseTW`` table, logical
            ``Tensor["N 12", float]``.
        centers_world: Attempted camera centres ``Tensor["N 3", float]`` in world metres.
        gaze_directions_world: Unit gaze directions ``Tensor["N 3", float]`` in world axes.
        reference_pose_world: World-from-rig conditioning pose.
        sampling_pose_world: Optional world sampling-frame ``PoseTW``.
        camera_calibration: Full-N calibrated ``CameraTW`` table.
        shell_offsets_ref: Optional reference-frame offsets ``Tensor["N 3", float]`` in metres.
        semantic_group_id: N-row center-group identities.
        center_family_id: N-row positional-family identities.
        gaze_family_id: N-row gaze-family identities.
        candidate_family_id: N-row combined family identities.
        center_id: Shared-center lineage ``Tensor["N", int64]``.
        position_pair_id: Paired-position lineage ``Tensor["N", int64]``.
        gaze_variant_id: Ordered gaze variant ``Tensor["N", int64]``.
        attempt_round_id: Completion-round lineage ``Tensor["N", int64]``.
        draw_id: Within-center draw lineage ``Tensor["N", int64]``.
        proposal_key: N-row semantic sampling-path keys.
        proposal_probability: Proposal probabilities ``Tensor["N", float]``.
        view_residual_yaw_deg: Realized yaw residual ``Tensor["N", float]`` in degrees.
        view_residual_pitch_deg: Realized pitch residual ``Tensor["N", float]`` in degrees.
        view_jitter_is_bounded: Bounded-box support flag ``Tensor["N", bool]``.
        view_jitter_azimuth_limit_deg: Configured yaw envelope ``Tensor["N", float]`` in degrees.
        view_jitter_elevation_limit_deg: Configured pitch envelope ``Tensor["N", float]`` in degrees.
        target_anchor_world: Target anchors ``Tensor["N 3", float]`` in world metres.
        target_frame_identity: N-row target-frame binding identities.
        target_frame_availability: N-row typed target-frame availability.
        measurements: Closed optional N-aligned measurement table.

    Generation owns this immutable attempted-shell table. Selection, storage,
    metrics, and plotting consume it without resampling or geometry acquisition.
    """

    world_poses: PoseTW
    centers_world: torch.Tensor
    gaze_directions_world: torch.Tensor
    reference_pose_world: PoseTW
    sampling_pose_world: PoseTW | None
    camera_calibration: CameraTW
    shell_offsets_ref: torch.Tensor | None
    semantic_group_id: tuple[str, ...]
    center_family_id: tuple[str, ...]
    gaze_family_id: tuple[str, ...]
    candidate_family_id: tuple[str, ...]
    center_id: torch.Tensor
    position_pair_id: torch.Tensor
    gaze_variant_id: torch.Tensor
    attempt_round_id: torch.Tensor
    draw_id: torch.Tensor
    proposal_key: tuple[str, ...]
    proposal_probability: torch.Tensor
    view_residual_yaw_deg: torch.Tensor
    view_residual_pitch_deg: torch.Tensor
    view_jitter_is_bounded: torch.Tensor
    view_jitter_azimuth_limit_deg: torch.Tensor
    view_jitter_elevation_limit_deg: torch.Tensor
    target_anchor_world: torch.Tensor
    target_frame_identity: tuple[str, ...]
    target_frame_availability: tuple[EvidenceAvailability, ...]
    measurements: CandidateMeasurements

    def __post_init__(self) -> None:
        n = int(self.centers_world.shape[0])
        device = self.centers_world.device
        dtype = self.centers_world.dtype
        if self.centers_world.shape != (n, 3):
            raise CandidateAlignmentCorruptionError("Candidate centers must have shape (N, 3).")
        if _efm_tensor(self.world_poses).shape != (n, 12) or self.gaze_directions_world.shape != (n, 3):
            raise CandidateAlignmentCorruptionError("Candidate pose, center, and gaze tables must align over N.")
        if self.shell_offsets_ref is not None and self.shell_offsets_ref.shape != (n, 3):
            raise CandidateAlignmentCorruptionError("Candidate shell offsets must have shape (N, 3).")
        for values in (self.semantic_group_id, self.center_family_id, self.gaze_family_id, self.candidate_family_id):
            if len(values) != n:
                raise CandidateAlignmentCorruptionError("Candidate semantic identities must align over N.")
        if (
            len(self.proposal_key) != n
            or len(self.target_frame_identity) != n
            or len(self.target_frame_availability) != n
        ):
            raise CandidateAlignmentCorruptionError("Candidate proposal and target-frame identities must align over N.")
        for tensor in (
            self.center_id,
            self.position_pair_id,
            self.gaze_variant_id,
            self.attempt_round_id,
            self.draw_id,
        ):
            if tensor.shape != (n,) or tensor.dtype is not torch.int64:
                raise CandidateAlignmentCorruptionError("Candidate lineage tensors must be 1-D int64 and align over N.")
        for tensor in (
            self.proposal_probability,
            self.view_residual_yaw_deg,
            self.view_residual_pitch_deg,
            self.view_jitter_is_bounded,
            self.view_jitter_azimuth_limit_deg,
            self.view_jitter_elevation_limit_deg,
        ):
            if tensor.shape != (n,):
                raise CandidateAlignmentCorruptionError("Candidate proposal/jitter facts must align over N.")
        if self.view_jitter_is_bounded.dtype is not torch.bool:
            raise CandidateAlignmentCorruptionError("Candidate jitter boundedness must be boolean.")
        if self.target_anchor_world.shape != (n, 3):
            raise CandidateAlignmentCorruptionError("Candidate target anchors must have shape (N, 3).")
        if any(not isinstance(value, EvidenceAvailability) for value in self.target_frame_availability):
            raise CandidateAlignmentCorruptionError("Candidate target-frame availability must be typed.")
        for name, value in self.measurements.legacy_tensors().items():
            if value.ndim == 0 or value.shape[0] != n:
                raise CandidateAlignmentCorruptionError(f"Candidate measurement {name!r} must align over N.")
        aligned_tensors = (
            _efm_tensor(self.world_poses),
            _efm_tensor(self.reference_pose_world),
            _efm_tensor(self.camera_calibration),
            self.gaze_directions_world,
            self.target_anchor_world,
            self.proposal_probability,
            self.view_residual_yaw_deg,
            self.view_residual_pitch_deg,
            self.view_jitter_is_bounded,
            self.view_jitter_azimuth_limit_deg,
            self.view_jitter_elevation_limit_deg,
            self.center_id,
            self.position_pair_id,
            self.gaze_variant_id,
            self.attempt_round_id,
            self.draw_id,
            *self.measurements.legacy_tensors().values(),
        )
        if self.shell_offsets_ref is not None:
            aligned_tensors += (self.shell_offsets_ref,)
        if self.sampling_pose_world is not None:
            aligned_tensors += (_efm_tensor(self.sampling_pose_world),)
        if any(tensor.device != device for tensor in aligned_tensors):
            raise CandidateAlignmentCorruptionError("Candidate row tensors must share one device.")
        float_axes: tuple[torch.Tensor, ...] = (
            self.centers_world,
            _efm_tensor(self.world_poses),
            self.gaze_directions_world,
            self.target_anchor_world,
            self.proposal_probability,
            self.view_residual_yaw_deg,
            self.view_residual_pitch_deg,
            self.view_jitter_azimuth_limit_deg,
            self.view_jitter_elevation_limit_deg,
        )
        if self.shell_offsets_ref is not None:
            float_axes += (self.shell_offsets_ref,)
        if any(tensor.dtype != dtype for tensor in float_axes):
            raise CandidateAlignmentCorruptionError("Candidate floating row axes must share one dtype.")


@dataclass(frozen=True, slots=True)
class CriterionLocalEvidence:
    """Criterion-local facts populated together by the geometry admission owner.

    Attributes:
        applicable: Criterion applicability ``Tensor["N", bool]``.
        evaluated: Backend evaluation ``Tensor["N", bool]``; subset of applicable.
        passed: Local pass ``Tensor["N", bool]``; subset of evaluated.
        reason_code: Revisioned reason ``Tensor["N", int64]``.
        margin: Signed ``Tensor["N", float]`` in the criterion's single unit;
            positive is admissible and negative violates the boundary.
        source_role: Revisioned evidence-role ``Tensor["N", int64]``.
    """

    applicable: torch.Tensor
    evaluated: torch.Tensor
    passed: torch.Tensor
    reason_code: torch.Tensor
    margin: torch.Tensor
    source_role: torch.Tensor

    def __post_init__(self) -> None:
        n = self.passed.numel()
        for tensor in (self.applicable, self.evaluated, self.passed):
            if tensor.shape != (n,) or tensor.dtype is not torch.bool:
                raise CandidateAlignmentCorruptionError("Criterion boolean evidence must align over N.")
        if self.reason_code.shape != (n,) or self.reason_code.dtype is not torch.int64:
            raise CandidateAlignmentCorruptionError("Criterion reason codes must be aligned int64 values.")
        if self.margin.shape != (n,) or not self.margin.is_floating_point():
            raise CandidateAlignmentCorruptionError("Criterion margins must be aligned floating values.")
        if self.source_role.shape != (n,) or self.source_role.dtype is not torch.int64:
            raise CandidateAlignmentCorruptionError("Criterion source roles must be aligned int64 values.")
        device = self.passed.device
        if any(
            tensor.device != device
            for tensor in (self.applicable, self.evaluated, self.reason_code, self.margin, self.source_role)
        ):
            raise CandidateAlignmentCorruptionError("Criterion evidence must share one device.")


@dataclass(frozen=True, slots=True)
class CriterionEvidence:
    """Shipped cumulative validity plus optional criterion-local evidence.

    Attributes:
        criterion_id: Stable nonempty criterion identity.
        legacy_cumulative_valid: Shipped cumulative ``Tensor["N", bool]``.
        local: Typed local facts, or unavailable until their canonical owner runs.
        local_availability: Complete-row availability ``Tensor["N", bool]``.
        reason_revision: Closed reason-code semantic revision.
        source_role_revision: Closed source-role semantic revision.
    """

    criterion_id: str
    legacy_cumulative_valid: torch.Tensor
    local: CriterionLocalEvidence | None
    local_availability: torch.Tensor
    reason_revision: CriterionReasonRevision
    source_role_revision: CriterionSourceRoleRevision

    def __post_init__(self) -> None:
        if not self.criterion_id:
            raise CandidateAlignmentCorruptionError("Admission criterion identity must be nonempty.")
        if self.legacy_cumulative_valid.ndim != 1 or self.legacy_cumulative_valid.dtype is not torch.bool:
            raise CandidateAlignmentCorruptionError("Legacy cumulative criterion validity must be 1-D boolean.")
        if (
            self.local_availability.shape != self.legacy_cumulative_valid.shape
            or self.local_availability.dtype is not torch.bool
            or self.local_availability.device != self.legacy_cumulative_valid.device
        ):
            raise CandidateAlignmentCorruptionError("Criterion-local availability must be aligned boolean evidence.")
        if not isinstance(self.reason_revision, CriterionReasonRevision) or not isinstance(
            self.source_role_revision, CriterionSourceRoleRevision
        ):
            raise CandidateAlignmentCorruptionError("Criterion reason and source-role revisions must be typed.")
        if self.local is not None and self.local.passed.shape != self.legacy_cumulative_valid.shape:
            raise CandidateAlignmentCorruptionError("Criterion-local evidence must align with cumulative validity.")


@dataclass(frozen=True, slots=True)
class AdmissionEvidence:
    """Hard-admission evidence aligned over the attempted shell.

    Attributes:
        mask_valid: Final hard-valid action mask ``Tensor["N", bool]``.
        criteria: Ordered immutable cumulative and criterion-local evidence.

    Admission owns this table. Selection consumes ``mask_valid``; compatibility
    adapters may project cumulative masks but cannot reinterpret them.
    """

    mask_valid: torch.Tensor
    criteria: tuple[CriterionEvidence, ...]

    def __post_init__(self) -> None:
        n = self.mask_valid.numel()
        if self.mask_valid.ndim != 1 or self.mask_valid.dtype is not torch.bool:
            raise CandidateAlignmentCorruptionError("Admission mask_valid must be 1-D boolean.")
        if len({criterion.criterion_id for criterion in self.criteria}) != len(self.criteria):
            raise CandidateAlignmentCorruptionError("Admission criterion identities must be unique.")
        if any(criterion.legacy_cumulative_valid.shape != (n,) for criterion in self.criteria):
            raise CandidateAlignmentCorruptionError("Admission criteria must align over N.")
        if any(criterion.legacy_cumulative_valid.device != self.mask_valid.device for criterion in self.criteria):
            raise CandidateAlignmentCorruptionError("Admission evidence must share one device.")

    @property
    def rule_masks(self) -> Mapping[str, torch.Tensor]:
        """Project the typed criteria into the shipped cumulative mask mapping."""

        return MappingProxyType(
            {criterion.criterion_id: criterion.legacy_cumulative_valid for criterion in self.criteria}
        )


@dataclass(frozen=True, slots=True)
class CandidateCompletion:
    """Factual score-independent completion evidence.

    Attributes:
        mode: Closed completion algorithm.
        attempted_count: Full attempted row count ``N``.
        valid_count: Hard-valid row count ``V``.
    """

    mode: CompletionMode
    attempted_count: int
    valid_count: int


@dataclass(frozen=True, slots=True)
class CandidateSet:
    """Attempted shell, admission evidence, and scoreable action indices.

    Attributes:
        attempts: Canonical immutable N-row attempted table.
        admission: N-aligned hard-admission evidence.
        action_indices: Ordered scoreable rows ``Tensor["A", int64]`` on the
            attempted-table device; fixed-attempt compatibility requires ``A=V``.
        completion: Score-independent attempted/valid counts.
        candidate_program_hash: Bound literal-program identity.
        request_binding_hash: Bound request identity.
        candidate_substream_revision: Random-substream semantic revision.
        action_order_revision: Ordered-action projection revision.

    The generator constructs this once with a mutation receipt for the valid
    projection. Consumers select, store, inspect, or adapt it without mutation.
    """

    attempts: CandidateTable
    admission: AdmissionEvidence
    action_indices: torch.Tensor
    completion: CandidateCompletion
    candidate_program_hash: str
    request_binding_hash: str
    candidate_substream_revision: CandidateSubstreamRevision
    action_order_revision: ActionOrderRevision
    _valid_indices_cache: torch.Tensor | None = field(default=None, init=False, repr=False, compare=False)
    _fixed_valid_proof: _FixedValidProof | None = field(default=None, init=False, repr=False, compare=False)
    _legacy_projection_groups: tuple[_LegacyProjectionGroup, ...] = field(
        default=(), init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        n = int(self.attempts.centers_world.shape[0])
        if not isinstance(self.action_order_revision, ActionOrderRevision):
            raise CandidateAlignmentCorruptionError("Candidate action order revision is undeclared.")
        if self.admission.mask_valid.reshape(-1).numel() != n or self.completion.attempted_count != n:
            raise CandidateAlignmentCorruptionError("Candidate attempts, admission, and completion counts disagree.")
        if (
            self.action_indices.ndim != 1
            or self.action_indices.dtype is not torch.int64
            or self.action_indices.device != self.admission.mask_valid.device
        ):
            raise CandidateAlignmentCorruptionError(
                "Candidate action_indices must be 1-D int64 on the admission device."
            )
        if self.attempts.centers_world.device != self.admission.mask_valid.device:
            raise CandidateAlignmentCorruptionError("Candidate attempts and admission must share one device.")

    @classmethod
    def _from_fixed_valid(
        cls,
        attempts: CandidateTable,
        admission: AdmissionEvidence,
        completion_mode: CompletionMode,
        candidate_program_hash: str,
        request_binding_hash: str,
        candidate_substream_revision: CandidateSubstreamRevision,
        legacy_projection_groups: tuple[_LegacyProjectionGroup, ...] = (),
    ) -> CandidateSet:
        """Construct shipped ``A = V`` output and retain a no-copy validity proof."""

        with torch.inference_mode(False):
            valid_indices = torch.nonzero(admission.mask_valid, as_tuple=False).reshape(-1)
        admission_token = tensor_identity_token(admission.mask_valid)
        action_token = tensor_identity_token(valid_indices)
        if admission_token is None or action_token is None:
            raise CandidateAlignmentCorruptionError(
                "Fixed-valid output tensors require mutation receipts; versionless tensors fail closed."
            )
        group_ids = tuple(group.semantic_group_id for group in legacy_projection_groups)
        if len(set(group_ids)) != len(group_ids):
            raise CandidateAlignmentCorruptionError("Legacy projection group identities must be unique.")
        variant_ids = tuple(
            variant.candidate_family_id for group in legacy_projection_groups for variant in group.variants
        )
        if len(set(variant_ids)) != len(variant_ids):
            raise CandidateAlignmentCorruptionError("Legacy projection family identities must be unique.")
        completion = CandidateCompletion(completion_mode, admission.mask_valid.numel(), valid_indices.numel())
        result = cls(
            attempts,
            admission,
            valid_indices,
            completion,
            candidate_program_hash,
            request_binding_hash,
            candidate_substream_revision,
            ActionOrderRevision.ORDERED_HARD_VALID_V1,
        )
        object.__setattr__(result, "_valid_indices_cache", valid_indices)
        object.__setattr__(result, "_fixed_valid_proof", _FixedValidProof(admission_token, action_token))
        object.__setattr__(
            result,
            "_legacy_projection_groups",
            legacy_projection_groups,
        )
        return result

    def validate_semantics(self) -> None:
        """Run the cold content-level N/V/A diagnostic checks."""

        action = self.action_indices
        n = self.completion.attempted_count
        if action.numel() != torch.unique(action).numel() or bool(((action < 0) | (action >= n)).any().item()):
            raise CandidateAlignmentCorruptionError("Candidate action_indices must be unique indices into N.")
        if action.numel() and not bool(self.admission.mask_valid[action].all().item()):
            raise CandidateAlignmentCorruptionError("Candidate actions must be a subset of hard-valid rows.")

    def validate_fixed_valid_proof(self) -> None:
        """Verify the no-copy ``A = V`` proof using metadata-only receipts."""

        proof = self._fixed_valid_proof
        if proof is None:
            raise LegacyCandidateProjectionUnsupported("Legacy projection requires a fixed-valid generation proof.")
        if tensor_identity_token(self.admission.mask_valid) != proof.admission_token:
            raise CandidateAlignmentCorruptionError("Admission validity changed after generation.")
        if tensor_identity_token(self.action_indices) != proof.action_token:
            raise CandidateAlignmentCorruptionError("Candidate actions changed after generation.")

    @property
    def valid_indices(self) -> torch.Tensor:
        """Return ordered ``V`` indices derived only from hard validity."""

        proof = self._fixed_valid_proof
        if proof is not None and tensor_identity_token(self.admission.mask_valid) != proof.admission_token:
            raise CandidateAlignmentCorruptionError("Admission validity changed after generation.")
        cached = self._valid_indices_cache
        if cached is None:
            cached = torch.nonzero(self.admission.mask_valid, as_tuple=False).reshape(-1)
            object.__setattr__(self, "_valid_indices_cache", cached)
        return cached


class CandidateGenerator(Protocol):
    """Deep finite-candidate generation module."""

    def generate(self, request: CandidateRequest) -> CandidateSet:
        """Generate one immutable attempted shell and its valid/action projections."""


def candidate_set_to_legacy_result(candidate_set: CandidateSet) -> CandidateSamplingResult:
    """Materialize the shipped compact-V DTO when and only when ``A == V``."""

    candidate_set.validate_fixed_valid_proof()
    table = candidate_set.attempts
    camera_chunks: list[torch.Tensor] = []
    row_start = 0
    while row_start < len(table.candidate_family_id):
        family_id = table.candidate_family_id[row_start]
        row_end = row_start + 1
        while row_end < len(table.candidate_family_id) and table.candidate_family_id[row_end] == family_id:
            row_end += 1
        local_valid = candidate_set.admission.mask_valid[row_start:row_end]
        world_valid = PoseTW(_efm_tensor(table.world_poses)[row_start:row_end][local_valid])
        poses_ref_valid = table.reference_pose_world.inverse().compose(world_valid)
        template = _efm_tensor(table.camera_calibration)
        if template.ndim == 1:
            template = template.reshape(1, -1)
        valid_count = _efm_tensor(poses_ref_valid).shape[0]
        chunk = template.to(device=table.centers_world.device)[0].unsqueeze(0).expand(valid_count, -1).clone()
        chunk[:, CameraTW.T_CAM_RIG_IND] = _efm_tensor(poses_ref_valid.inverse())
        camera_chunks.append(chunk)
        row_start = row_end
    camera_data = torch.cat(camera_chunks)
    compatibility = candidate_set._legacy_projection_groups  # noqa: SLF001 - one-way adapter-owned mapping.
    extras: dict[str, Any] = table.measurements.legacy_tensors()
    extras.update(
        {
            "view_jitter_yaw_deg": table.view_residual_yaw_deg,
            "view_jitter_pitch_deg": table.view_residual_pitch_deg,
            "view_jitter_is_bounded": table.view_jitter_is_bounded,
            "view_jitter_azimuth_limit_deg": table.view_jitter_azimuth_limit_deg,
            "view_jitter_elevation_limit_deg": table.view_jitter_elevation_limit_deg,
        }
    )
    if not compatibility and "view_dirs_delta" in extras:
        extras["view_dirs_delta"] = PoseTW(cast(torch.Tensor, extras["view_dirs_delta"]))
    is_mixture = bool(compatibility)
    strategy_id: torch.Tensor | None = None
    position_id: torch.Tensor | None = None
    mixture_id: torch.Tensor | None = None
    sampler_probability: torch.Tensor | None = None
    component_name: tuple[str, ...] | None = None
    if is_mixture:
        group_by_id = {group.semantic_group_id: group for group in compatibility}
        variant_by_id = {variant.candidate_family_id: variant for group in compatibility for variant in group.variants}
        try:
            row_groups = tuple(group_by_id[group_id] for group_id in table.semantic_group_id)
            row_variants = tuple(variant_by_id[family_id] for family_id in table.candidate_family_id)
        except KeyError as error:
            raise CandidateAlignmentCorruptionError(
                "Canonical candidate identities lack a legacy projection mapping."
            ) from error
        device = table.centers_world.device
        strategy_id = torch.tensor([row.strategy_id for row in row_variants], device=device, dtype=torch.long)
        position_id = torch.tensor([row.position_id for row in row_groups], device=device, dtype=torch.long)
        mixture_id = torch.tensor([row.mixture_id for row in row_groups], device=device, dtype=torch.long)
        sampler_probability = torch.tensor(
            [row.sampler_probability for row in row_groups],
            device=device,
            dtype=table.centers_world.dtype,
        )
        component_name = tuple(row.component_name for row in row_variants)
    if is_mixture:
        extras["position_pair_id"] = table.position_pair_id
        extras["gaze_variant_id"] = table.gaze_variant_id
    return CandidateSamplingResult(
        views=CameraTW(camera_data),
        reference_pose=table.reference_pose_world,
        mask_valid=candidate_set.admission.mask_valid,
        masks=dict(candidate_set.admission.rule_masks),
        shell_poses=table.world_poses,
        shell_offsets_ref=table.shell_offsets_ref,
        sampling_pose=table.sampling_pose_world,
        strategy_id=strategy_id,
        position_id=position_id,
        mixture_id=mixture_id,
        sampler_probability=sampler_probability,
        component_name=component_name,
        position_pair_id=table.position_pair_id if is_mixture else None,
        gaze_variant_id=table.gaze_variant_id if is_mixture else None,
        extras=extras,
    )


def _request_hash(
    revision: BindingEncodingRevision,
    program: CandidateProgram,
    conditioning: CandidateConditioning,
    scene: PreparedCandidateScene,
    actor_target: ActorTargetContext | None,
    random_key: CandidateSamplingKey,
) -> str:
    return canonical_binding_sha256(
        (
            revision,
            program.candidate_program_hash,
            (conditioning._pose_value_hash, conditioning.action_duration_s),
            scene._scene_value_hash,
            None if actor_target is None else actor_target._actor_value_hash,
            random_key,
        )
    )


def _validate_request_axes(conditioning: CandidateConditioning, scene: PreparedCandidateScene) -> None:
    pose = _efm_tensor(conditioning.reference_pose_world)
    if pose.numel() != 12:
        raise CandidateRequestMismatchError("Candidate conditioning pose must contain one 12-value transform.")
    if pose.device != scene.device or pose.dtype != scene.dtype:
        raise CandidateRequestMismatchError("Candidate conditioning pose device/dtype must match the prepared scene.")


def _validate_sampling_compatibility(program: CandidateProgram, key: CandidateSamplingKey) -> None:
    groups = program.groups
    if key.source == "rollout_proposal":
        if any(not group.legacy_seed_component_name for group in groups):
            raise CandidateRequestMismatchError("Shipped rollout substreams require frozen legacy component names.")
        return
    if len(groups) == 1 and groups[0].legacy_direct_component_index is None:
        return
    if any(group.legacy_direct_component_index is None for group in groups):
        raise CandidateRequestMismatchError(
            "Shipped direct mixture substreams require frozen legacy component indices."
        )


__all__ = [
    "ActionOrderRevision",
    "ActorTargetContext",
    "AdmissionEvidence",
    "CandidateCompletion",
    "CandidateConditioning",
    "CandidateGenerator",
    "CandidateMeasurements",
    "CandidateRequest",
    "CandidateSet",
    "CandidateTable",
    "CriterionEvidence",
    "CriterionLocalEvidence",
    "CriterionReasonCode",
    "CriterionReasonRevision",
    "CriterionSourceRole",
    "CriterionSourceRoleRevision",
    "EvidenceAvailability",
    "GeometrySourceRole",
    "LegacyCandidateProjectionUnsupported",
    "PreparedCandidateScene",
    "candidate_set_to_legacy_result",
]
