"""Canonical target-relative, world-Z-up coordinate frames.

The frame follows the Aria/EFM LUF convention: its first axis points along the
horizontal origin-to-target bearing, its second axis points left, and its third
axis is world up.  Points may be normalized by the full origin-to-target
distance while horizontal standoff remains available for orbit construction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import ClassVar

import torch

from ..utils.frames import world_up_tensor


class TargetRelativeFrameError(ValueError):
    """Base error for invalid target-relative frame construction."""


class TargetRelativeFrameDegeneracyError(TargetRelativeFrameError):
    """Raised when the origin and target do not define a horizontal bearing."""


@dataclass(frozen=True, slots=True, init=False)
class TargetRelativeFrame:
    """Pure target-aligned frame shared by generation and evidence reducers.

    Args:
        origin_world: World-frame origin, ``Tensor["3", float]``.
        target_world: Actor-visible or persisted target centre in world frame,
            ``Tensor["3", float]``.
        basis_world_from_frame: Orthonormal columns ``(forward, left, up)`` as
            ``Tensor["3 3", float]``.
        horizontal_target_delta_world: Exact world-horizontal target delta,
            retained to avoid reconstructing parity-sensitive generation input.
        normalization_distance_m: Positive scalar used by normalized support
            projections. This is normally the full origin-to-target distance.
        horizontal_standoff_m: Positive horizontal origin-to-target distance.
        frame_identity: Composition-owned identity for the factual origin and
            target binding. Tensor identity is deliberately not hashed here.
    """

    SEMANTIC_VERSION: ClassVar[str] = "target-relative-z-up-v1"

    origin_world: torch.Tensor
    """Frame origin ``Tensor["3", float]`` in world metres."""

    target_world: torch.Tensor
    """Target centre ``Tensor["3", float]`` in world metres."""

    basis_world_from_frame: torch.Tensor
    """Right-handed ``Tensor["3 3", float]`` columns (forward, left, up)."""

    horizontal_target_delta_world: torch.Tensor
    """Exact horizontal origin-to-target ``Tensor["3", float]`` in world metres."""

    normalization_distance_m: torch.Tensor
    """Positive scalar ``Tensor["", float]`` support normalization in metres."""

    horizontal_standoff_m: torch.Tensor
    """Positive scalar ``Tensor["", float]`` horizontal standoff in metres."""

    frame_identity: str
    """Composition-owned identity for the factual origin/target binding."""

    def __init__(self) -> None:
        raise TypeError("Construct TargetRelativeFrame with from_origin_target().")

    @classmethod
    def _validated(
        cls,
        *,
        origin_world: torch.Tensor,
        target_world: torch.Tensor,
        basis_world_from_frame: torch.Tensor,
        horizontal_target_delta_world: torch.Tensor,
        normalization_distance_m: torch.Tensor,
        horizontal_standoff_m: torch.Tensor,
        frame_identity: str,
    ) -> TargetRelativeFrame:
        frame = object.__new__(cls)
        object.__setattr__(frame, "origin_world", origin_world)
        object.__setattr__(frame, "target_world", target_world)
        object.__setattr__(frame, "basis_world_from_frame", basis_world_from_frame)
        object.__setattr__(frame, "horizontal_target_delta_world", horizontal_target_delta_world)
        object.__setattr__(frame, "normalization_distance_m", normalization_distance_m)
        object.__setattr__(frame, "horizontal_standoff_m", horizontal_standoff_m)
        object.__setattr__(frame, "frame_identity", frame_identity)
        return frame

    @classmethod
    def from_origin_target(
        cls,
        origin_world: torch.Tensor,
        target_world: torch.Tensor,
        *,
        frame_identity: str,
        normalization_distance_m: torch.Tensor | float | None = None,
        epsilon: float = 1.0e-6,
    ) -> TargetRelativeFrame:
        """Construct a right-handed target-forward/left/world-up frame.

        The constructor preserves tensor device, dtype, and autograd history.
        Degenerate vertical or coincident baselines fail explicitly rather than
        selecting a fabricated horizontal axis.

        Args:
            origin_world ``Tensor["3", float]``: Frame origin in world metres.
            target_world ``Tensor["3", float]``: Target centre in world metres.
            frame_identity: Composition-owned origin/target binding identity.
            normalization_distance_m ``Tensor["", float] | float | None``:
                Optional positive support scale in metres. The full target
                distance is used when omitted.
            epsilon: Positive degeneracy tolerance in metres.

        Returns:
            Validated target-relative frame retaining tensor autograd history.

        Raises:
            TargetRelativeFrameError: If tensor axes, dtype, or identity are invalid.
            TargetRelativeFrameDegeneracyError: If the horizontal bearing or
                normalization distance is non-finite or degenerate.
        """

        if isinstance(epsilon, bool) or not isinstance(epsilon, (int, float)):
            raise TargetRelativeFrameError("Target-relative epsilon must be a finite positive real scalar.")
        epsilon = float(epsilon)
        if not math.isfinite(epsilon) or epsilon <= 0.0:
            raise TargetRelativeFrameError("Target-relative epsilon must be a finite positive real scalar.")
        if not isinstance(frame_identity, str) or not frame_identity.strip():
            raise TargetRelativeFrameError("Target-relative frame identity must be a nonempty string.")
        if origin_world.shape != (3,) or target_world.shape != (3,):
            raise TargetRelativeFrameError("Target-relative origin and target must have shape (3,).")
        if origin_world.device != target_world.device or origin_world.dtype != target_world.dtype:
            raise TargetRelativeFrameError("Target-relative origin and target must share device and dtype.")
        if not origin_world.dtype.is_floating_point:
            raise TargetRelativeFrameError("Target-relative origin and target must be floating point.")
        delta = target_world - origin_world
        up = world_up_tensor(device=delta.device, dtype=delta.dtype)
        horizontal = delta - (delta @ up) * up
        horizontal_standoff = torch.linalg.vector_norm(horizontal)
        forward = horizontal / horizontal_standoff
        left = torch.cross(up, forward, dim=0)
        basis = torch.stack((forward, left, up), dim=1)
        if normalization_distance_m is None:
            normalization = torch.linalg.vector_norm(delta)
        else:
            normalization = torch.as_tensor(
                normalization_distance_m,
                device=delta.device,
                dtype=delta.dtype,
            ).reshape(())
        valid = (
            torch.isfinite(delta).all()
            & torch.isfinite(normalization)
            & (horizontal_standoff > epsilon)
            & (normalization > epsilon)
        )
        if not bool(valid.item()):
            raise TargetRelativeFrameDegeneracyError(
                "Target-relative frame requires finite input, a nonzero horizontal bearing, "
                "and a positive normalization distance."
            )
        return cls._validated(
            origin_world=origin_world,
            target_world=target_world,
            basis_world_from_frame=basis,
            horizontal_target_delta_world=horizontal,
            normalization_distance_m=normalization,
            horizontal_standoff_m=horizontal_standoff,
            frame_identity=frame_identity,
        )

    @property
    def forward_world(self) -> torch.Tensor:
        """Return the horizontal target-forward unit axis."""

        return self.basis_world_from_frame[:, 0]

    @property
    def lateral_world(self) -> torch.Tensor:
        """Return the left-pointing lateral unit axis of the LUF frame."""

        return self.basis_world_from_frame[:, 1]

    @property
    def up_world(self) -> torch.Tensor:
        """Return the world-up unit axis."""

        return self.basis_world_from_frame[:, 2]

    def world_to_frame_vectors(self, vectors_world: torch.Tensor, *, normalize: bool = False) -> torch.Tensor:
        """Express world vectors on target-relative axes.

        Args:
            vectors_world ``Tensor["... 3", float]``: World-frame vectors.
            normalize: Divide by `normalization_distance_m` when true.

        Returns:
            ``Tensor["... 3", float]`` on target-forward/left/up axes.
        """

        vectors = vectors_world @ self.basis_world_from_frame
        return vectors / self.normalization_distance_m if normalize else vectors

    def frame_to_world_vectors(self, vectors_frame: torch.Tensor, *, normalized: bool = False) -> torch.Tensor:
        """Express target-relative vectors in world coordinates.

        Args:
            vectors_frame ``Tensor["... 3", float]``: Frame-axis vectors.
            normalized: Multiply by `normalization_distance_m` when true.

        Returns:
            ``Tensor["... 3", float]`` in world axes.
        """

        vectors = vectors_frame * self.normalization_distance_m if normalized else vectors_frame
        return vectors @ self.basis_world_from_frame.transpose(0, 1)

    def world_to_frame_points(self, points_world: torch.Tensor, *, normalize: bool = True) -> torch.Tensor:
        """Project world points relative to the frame origin.

        Args:
            points_world ``Tensor["... 3", float]``: World points in metres.
            normalize: Divide by `normalization_distance_m` when true.

        Returns:
            ``Tensor["... 3", float]`` on target-forward/left/up axes.
        """

        return self.world_to_frame_vectors(points_world - self.origin_world, normalize=normalize)

    def frame_to_world_points(self, points_frame: torch.Tensor, *, normalized: bool = True) -> torch.Tensor:
        """Invert :meth:`world_to_frame_points`.

        Args:
            points_frame ``Tensor["... 3", float]``: Target-relative points.
            normalized: Multiply by `normalization_distance_m` when true.

        Returns:
            ``Tensor["... 3", float]`` world points in metres.
        """

        return self.origin_world + self.frame_to_world_vectors(points_frame, normalized=normalized)

    def target_relative_points(self, points_world: torch.Tensor, *, normalize: bool = True) -> torch.Tensor:
        """Project points relative to the target centre on the same axes.

        Args:
            points_world ``Tensor["... 3", float]``: World points in metres.
            normalize: Divide by `normalization_distance_m` when true.

        Returns:
            ``Tensor["... 3", float]`` relative to the target centre.
        """

        return self.world_to_frame_vectors(points_world - self.target_world, normalize=normalize)


__all__ = [
    "TargetRelativeFrame",
    "TargetRelativeFrameDegeneracyError",
    "TargetRelativeFrameError",
]
