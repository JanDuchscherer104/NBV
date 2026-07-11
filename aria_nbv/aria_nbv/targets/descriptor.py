"""Actor-safe target instruction DTOs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite

import torch


@dataclass(frozen=True, slots=True)
class TargetDescriptor:
    """Sanitized target instruction for target-conditioned candidate generation.

    The descriptor is a semantic task instruction. It may be GT-derived when an
    oracle specifies the task, but it does not carry GT source rows, matching
    diagnostics, crop state, labels, gains, invalidity, headroom, or persisted
    Zarr details.
    """

    sem_id: int
    """Semantic class identifier for the target."""

    class_name: str
    """Human-readable semantic class name."""

    pose_world_object: tuple[float, ...]
    """Flattened 12-value object-to-world pose."""

    extents_m: tuple[float, float, float]
    """Full object side lengths in metres."""

    relative_pose_reference_object: tuple[float, ...]
    """Flattened 12-value object pose in the snippet reference frame."""

    def __post_init__(self) -> None:
        if len(self.pose_world_object) != 12:
            raise ValueError("pose_world_object must contain 12 values.")
        if len(self.extents_m) != 3:
            raise ValueError("extents_m must contain 3 values.")
        if len(self.relative_pose_reference_object) != 12:
            raise ValueError("relative_pose_reference_object must contain 12 values.")
        geometry = (*self.pose_world_object, *self.extents_m, *self.relative_pose_reference_object)
        if not all(isfinite(float(value)) for value in geometry):
            raise ValueError("TargetDescriptor geometry must contain only finite values.")
        if any(float(value) <= 0.0 for value in self.extents_m):
            raise ValueError("extents_m must be positive full side lengths.")

    @property
    def center_world(self) -> tuple[float, float, float]:
        """Target center in world coordinates, metres."""

        pose = tuple(float(value) for value in self.pose_world_object)
        return (pose[9], pose[10], pose[11])

    def center_world_tensor(self, *, dtype: torch.dtype = torch.float32) -> torch.Tensor:
        """Return `center_world` as a 3-vector tensor."""

        return torch.tensor(self.center_world, dtype=dtype)

    @property
    def target_id(self) -> str:
        """Return a stable actor-safe diagnostic id derived from descriptor fields."""

        payload = json.dumps(
            {
                "class_name": self.class_name,
                "extents_m": self.extents_m,
                "pose_world_object": self.pose_world_object,
                "relative_pose_reference_object": self.relative_pose_reference_object,
                "sem_id": self.sem_id,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        return f"target-{sha256(payload.encode()).hexdigest()[:16]}"
