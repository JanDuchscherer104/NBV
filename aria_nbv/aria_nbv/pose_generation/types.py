r"""Type definitions for finite candidate pose generation.

Candidate generation separates the full sampled shell from the compact valid
table. The full shell carries invalidity masks, reason codes, strategy
provenance, and optional diagnostics; compact valid views are the actions an
actor or oracle selector may actually choose. Any dataset writer that trains a
finite-action value model must apply the valid mask before argmax, softmax,
loss targets, and bootstrap maximization.

Direction sampling happens on $\mathbb{S}^2$. Orientation encodings such as R6D
describe candidate pose rows; accumulated target visibility is a separate
actor-visible directional-memory feature, not an orientation representation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import torch
from efm3d.aria.camera import CameraTW
from efm3d.aria.pose import PoseTW

from ..targets import TargetDescriptor
from ..utils.typed_payloads import from_serializable, to_serializable

if TYPE_CHECKING:
    from trimesh import Trimesh  # type: ignore[import-untyped]

    from .candidate_generation import CandidateViewGeneratorConfig


class SamplingStrategy(StrEnum):
    r"""Angular sampling strategy for candidate directions on S^2.

    The strategy controls how unit directions on the sphere $\mathbb{S}^2$ are drawn for both:

    * positional sampling of candidate camera centers (see `pose_generation.samplers.PositionSampler`), and
    * optional view-direction jitter in the camera frame (see `pose_generation.orientations.OrientationBuilder`).
    """

    UNIFORM_SPHERE = "uniform_sphere"
    r"""
    Draw directions uniformly on $\mathbb{S}^2$ using a `HypersphericalUniform` distribution (constant
            density over the sphere; no directional prior).
    """
    FORWARD_POWERSPHERICAL = "forward_powerspherical"
    r"""
    Draw directions from a forward-biased Power Spherical distribution $\mathcal{PS}(\mu, \kappa)$ centered on
            the device forward axis with concentration ``kappa``. Larger $\kappa$ yields views clustered around
            the *mean direction*; $\kappa \rightarrow 0$ approaches the uniform sphere.
    """


class ViewDirectionMode(StrEnum):
    """Base orientation family applied after candidate centers are sampled.

    These modes decide where the camera optical axis points before local jitter:
    reuse the reference rig, look along the reference-candidate ray, look back
    toward the reference, or look at an actor-visible target point.
    """

    FORWARD_RIG = "forward_rig"
    RADIAL_AWAY = "radial_away"
    RADIAL_TOWARDS = "radial_towards"
    TARGET_POINT = "target_point"


class CandidatePositionMode(StrEnum):
    """Spatial prior used to turn raw sphere samples into candidate centers.

    `UPPER_BOUND_FREE_SHELL` is the broad ablation prior. The remaining modes
    bias the finite candidate set toward local continuity, target bearing,
    lateral bypass, short refinement, or controlled backtracking.
    """

    UPPER_BOUND_FREE_SHELL = "upper_bound_free_shell"
    FORWARD_LOCAL = "forward_local"
    TARGET_BEARING_LOCAL = "target_bearing_local"
    LATERAL_TARGET_BYPASS = "lateral_target_bypass"
    LOCAL_REFINEMENT = "local_refinement"
    REVISIT_BACKTRACK = "revisit_backtrack"


class CollisionBackend(StrEnum):
    """Backend for collision tests."""

    P3D = "pytorch3d"
    PYEMBREE = "pyembree"
    TRIMESH = "trimesh"


@dataclass
class CandidateGenerationRuntimeContext:
    """Runtime-only context for target-conditioned candidate generation.

    The context carries an actor-safe target descriptor. Missing target context
    is a configuration error for `TARGET_POINT` mixture components.
    """

    descriptor: TargetDescriptor | None = None
    """Sanitized target instruction shared by candidate-generation consumers."""

    @property
    def target_center_world(self) -> torch.Tensor | None:
        """Target center in world coordinates, shape ``(3,)``."""

        if self.descriptor is None:
            return None
        return self.descriptor.center_world_tensor()

    @property
    def target_id(self) -> str | None:
        """Stable target identifier for diagnostics."""

        return None if self.descriptor is None else self.descriptor.target_id


@dataclass
class CandidateContext:
    """Mutable full-shell state passed between sampling and pruning rules.

    `shell_poses`, `centers_world`, `shell_offsets_ref`, and `mask_valid` are
    aligned over the full candidate shell of size `N`, including candidates that
    later become invalid. Pruning rules must update `mask_valid` and may store
    same-shape diagnostic masks in `rule_masks`; they must not compact rows.

    `views` are not stored here because compact valid camera views are built
    only after pruning. This separation lets rollout writers preserve invalid
    candidates with reason codes while exposing only valid actions to policies.
    """

    cfg: "CandidateViewGeneratorConfig"
    reference_pose: PoseTW
    sampling_pose: PoseTW

    gt_mesh: Trimesh
    mesh_verts: torch.Tensor
    mesh_faces: torch.Tensor
    occupancy_extent: torch.Tensor
    camera_calib_template: CameraTW

    shell_poses: PoseTW
    centers_world: torch.Tensor
    shell_offsets_ref: torch.Tensor
    mask_valid: torch.Tensor

    rule_masks: dict[str, torch.Tensor] = field(default_factory=dict)
    debug: dict[str, Any] = field(default_factory=dict)

    def record_mask(self, name: str, mask: torch.Tensor) -> None:
        """Store a copy of the cumulative validity mask for diagnostics."""

        self.rule_masks[name] = mask.clone()

    def invalidate(self, reject_mask: torch.Tensor) -> None:
        """Apply a rejection mask (True = reject) to the current validity mask."""

        self.mask_valid = self.mask_valid & (~reject_mask)

    def mark_debug(self, key: str, value: torch.Tensor) -> None:
        """Attach debug tensors in a consistent shape (clone kept to avoid side-effects)."""

        self.debug[key] = value.clone()


@dataclass
class CandidateSamplingResult:
    """Immutable result of candidate sampling and rule-based pruning.

    `views` stores compact valid candidates for rendering and oracle/model
    scoring. `mask_valid`, `shell_poses`, provenance fields, and rule masks stay
    aligned with the full sampled shell of size `N`. Use
    `candidate_shell_indices()` whenever a compact row index must be joined back
    to full-shell lineage.

    Shapes:

    * `views.T_camera_rig`: compact valid candidate camera poses in reference
      coordinates, shape `(V, 12)`;
    * `shell_poses`: full-shell world<-camera `PoseTW` payload, shape
      `(N, 12)`;
    * `mask_valid`: full-shell actor-action mask, shape `(N,)`;
    * `strategy_id`, `position_id`, `mixture_id`, `sampler_probability`, and
      `component_name`: optional full-shell provenance arrays/tuples aligned
      with `mask_valid`.

    Invalid candidates remain in the full shell and must receive false training
    masks and NaN oracle labels rather than low RRI.
    """

    views: CameraTW
    """Compact valid candidate cameras; ``views.T_camera_rig`` is camera <- reference."""
    reference_pose: PoseTW
    """World <- physical reference rig pose used to express candidate extrinsics."""
    mask_valid: torch.Tensor
    masks: dict[str, torch.Tensor]
    shell_poses: PoseTW
    """cam2world poses for all sampled candidates (pre-pruning)."""
    shell_offsets_ref: torch.Tensor | None = None
    """Sampled offsets in the sampling frame for the full shell (pre-pruning)."""
    sampling_pose: PoseTW | None = None
    """World <- sampling pose used to draw centers, gravity-aligned when enabled."""
    strategy_id: torch.Tensor | None = None
    """Full-shell candidate strategy ids aligned with ``mask_valid``."""
    position_id: torch.Tensor | None = None
    """Full-shell position-family ids aligned with ``mask_valid``."""
    mixture_id: torch.Tensor | None = None
    """Full-shell mixture component ids aligned with ``mask_valid``."""
    sampler_probability: torch.Tensor | None = None
    """Full-shell sampler probabilities aligned with ``mask_valid``."""
    component_name: tuple[str, ...] | None = None
    """Optional per-shell component names aligned with ``mask_valid``."""
    extras: dict[str, Any] = field(default_factory=dict)

    def to_serializable(self) -> dict[str, Any]:
        """Serialize this result into a cache-friendly CPU payload."""

        return to_serializable(self)

    @classmethod
    def from_serializable(
        cls,
        payload: dict[str, Any],
        *,
        device: torch.device | None = None,
    ) -> "CandidateSamplingResult":
        """Reconstruct one result from a serialized payload.

        Args:
            payload: Serialized payload produced by `to_serializable`.
            device: Optional destination device for tensors and wrappers.

        Returns:
            Reconstructed candidate-sampling result.
        """

        return from_serializable(cls, payload, device=device)

    def poses_world_cam(self, *, device: torch.device | None = None) -> PoseTW:
        """World <- camera poses for **valid** candidates."""
        t_cam_ref = self.views.T_camera_rig.to(device=device)  # camera <- reference
        t_world_ref = self.reference_pose.to(t_cam_ref.device)  # world <- reference

        # Compose to world <- camera.
        return t_world_ref @ t_cam_ref.inverse()

    def candidate_shell_indices(self, *, device: torch.device | None = None) -> torch.Tensor:
        """Return full-shell indices aligned with ``views`` and labels.

        ``CandidateViewGenerator`` stores ``views`` as the compact valid-candidate
        table and keeps ``mask_valid``/``shell_poses`` as full-shell diagnostics.
        Some synthetic diagnostics use full-shell ``views`` directly. This helper
        accepts those two explicit layouts and rejects ambiguous combinations so
        candidate poses, depth renders, oracle labels, and serialized diagnostics
        cannot silently drift out of order.

        Args:
            device: Optional destination device for the returned indices.

        Returns:
            ``Tensor["N"]`` integer indices into the full sampled shell.

        Raises:
            ValueError: If ``views`` cannot be mapped unambiguously to the full
                candidate shell.
        """

        view_count = int(self.views.tensor().shape[0])
        target_device = device or self.views.tensor().device
        if self.mask_valid is None:
            return torch.arange(view_count, device=target_device, dtype=torch.long)

        valid_mask = self.mask_valid.to(device=target_device, dtype=torch.bool).reshape(-1)
        valid_indices = torch.nonzero(valid_mask, as_tuple=False).reshape(-1)
        if valid_indices.numel() == view_count:
            return valid_indices
        if valid_mask.numel() == view_count:
            return torch.arange(view_count, device=target_device, dtype=torch.long)

        raise ValueError(
            "Candidate views cannot be mapped to full-shell indices: "
            f"views={view_count}, valid_count={valid_indices.numel()}, mask_width={valid_mask.numel()}. "
            "Expected compact valid views or full-shell views.",
        )

    def get_offsets_and_dirs_ref(
        self,
        *,
        display_rotate: bool = False,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Offsets and forward directions in the **physical reference frame**.

        Args:
            display_rotate: If ``True``, apply the visual 90° CW yaw rotation
                (``rotate_yaw_cw90``) to match UI plots. Defaults to ``False`` so
                downstream geometry keeps physical Aria frames.

        Returns:
            Tuple ``(offsets, dirs)`` with shapes ``(N,3)`` each.
        """

        poses_cam_ref = self.views.T_camera_rig  # camera<-reference
        if display_rotate:
            from aria_nbv.utils import rotate_yaw_cw90

            poses_cam_ref = rotate_yaw_cw90(poses_cam_ref)

        offsets = poses_cam_ref.inverse().t.view(-1, 3)  # camera->reference
        z_cam = (
            torch.tensor([0.0, 0.0, 1.0], device=offsets.device, dtype=offsets.dtype)
            .view(1, 3)
            .expand(offsets.shape[0], 3)
        )
        dirs = poses_cam_ref.inverse().rotate(z_cam).view(-1, 3)
        dirs = dirs / (dirs.norm(dim=1, keepdim=True) + 1e-8)
        return offsets, dirs


__all__ = [
    "SamplingStrategy",
    "CandidatePositionMode",
    "CandidateGenerationRuntimeContext",
    "CollisionBackend",
    "ViewDirectionMode",
    "CandidateContext",
    "CandidateSamplingResult",
]
