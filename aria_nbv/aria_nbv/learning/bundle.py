r"""Actor/oracle-separated tensors for factorized scene-bundle RRI learning.

The actor bundle contains only evidence available at inference time. Oracle
utilities live in a separate supervision value so they cannot enter the model
forward path accidentally.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from jaxtyping import Bool, Float
from torch import Tensor


def _require_float(name: str, value: Tensor) -> None:
    if not torch.is_floating_point(value):
        raise TypeError(f"{name} must be a floating-point tensor")


def _require_bool(name: str, value: Tensor) -> None:
    if value.dtype is not torch.bool:
        raise TypeError(f"{name} must be a bool tensor")


@dataclass(frozen=True, slots=True)
class ActorSceneBundle:
    """Immutable actor-visible evidence for one batch of scene states.

    Poses are world-from-local rigid transforms. Targets are parallel
    single-target queries: neither their rows nor candidate rows imply a joint
    set objective.
    """

    scene_features: Float[Tensor, "B S F_scene"]
    """``Tensor["B S F_scene", float]`` historical actor-visible scene tokens."""

    t_world_scene: Float[Tensor, "B S 3 4"]
    """``Tensor["B S 3 4", float]`` world-from-scene-token poses."""

    scene_time_s: Float[Tensor, "B S"]
    """``Tensor["B S", float]`` scene-token timestamps in seconds."""

    scene_valid: Bool[Tensor, "B S"]
    """``Tensor["B S", bool]`` valid scene-token mask."""

    target_features: Float[Tensor, "B T F_target"]
    """``Tensor["B T F_target", float]`` independent target-query features."""

    t_world_target: Float[Tensor, "B T 3 4"]
    """``Tensor["B T 3 4", float]`` world-from-target-query poses."""

    target_valid: Bool[Tensor, "B T"]
    """``Tensor["B T", bool]`` valid target-query mask."""

    candidate_features: Float[Tensor, "B C F_candidate"]
    """``Tensor["B C F_candidate", float]`` independent candidate-view features."""

    t_world_candidate: Float[Tensor, "B C 3 4"]
    """``Tensor["B C 3 4", float]`` world-from-candidate-camera poses."""

    candidate_time_s: Float[Tensor, "B C"]
    """``Tensor["B C", float]`` candidate query times in seconds."""

    candidate_valid: Bool[Tensor, "B C"]
    """``Tensor["B C", bool]`` valid candidate-view mask."""

    pair_valid: Bool[Tensor, "B T C"]
    """``Tensor["B T C", bool]`` actor-known hard validity mask per query pair."""

    def __post_init__(self) -> None:
        """Validate ranks, shared axes, dtypes, devices, and pair masks."""

        if self.scene_features.ndim != 3 or self.target_features.ndim != 3 or self.candidate_features.ndim != 3:
            raise ValueError("scene, target, and candidate features must have shape [B,N,F]")
        batch, scenes, _ = self.scene_features.shape
        target_batch, targets, _ = self.target_features.shape
        candidate_batch, candidates, _ = self.candidate_features.shape
        if batch < 1 or min(scenes, targets, candidates) < 1:
            raise ValueError("ActorSceneBundle axes B, S, T, and C must be non-empty")
        if target_batch != batch or candidate_batch != batch:
            raise ValueError("scene, target, and candidate batch sizes must match")

        expected = {
            "t_world_scene": (batch, scenes, 3, 4),
            "scene_time_s": (batch, scenes),
            "scene_valid": (batch, scenes),
            "t_world_target": (batch, targets, 3, 4),
            "target_valid": (batch, targets),
            "t_world_candidate": (batch, candidates, 3, 4),
            "candidate_time_s": (batch, candidates),
            "candidate_valid": (batch, candidates),
            "pair_valid": (batch, targets, candidates),
        }
        for name, shape in expected.items():
            if getattr(self, name).shape != shape:
                raise ValueError(f"{name} must have shape {list(shape)}")

        float_names = (
            "scene_features",
            "t_world_scene",
            "scene_time_s",
            "target_features",
            "t_world_target",
            "candidate_features",
            "t_world_candidate",
            "candidate_time_s",
        )
        bool_names = ("scene_valid", "target_valid", "candidate_valid", "pair_valid")
        for name in float_names:
            _require_float(name, getattr(self, name))
        for name in bool_names:
            _require_bool(name, getattr(self, name))
        tensors = tuple(getattr(self, name) for name in (*float_names, *bool_names))
        if len({tensor.device for tensor in tensors}) != 1:
            raise ValueError("all ActorSceneBundle tensors must share one device")

        row_valid = self.target_valid[:, :, None] & self.candidate_valid[:, None, :]
        if torch.any(self.pair_valid & ~row_valid).item():
            raise ValueError("pair_valid cannot include an invalid target or candidate")


@dataclass(frozen=True, slots=True)
class SceneBundleSupervision:
    """Immutable oracle-only utility labels kept outside actor evidence."""

    utility: Float[Tensor, "B T C"]
    """``Tensor["B T C", float]`` oracle RRI or finite-horizon utility targets."""

    label_valid: Bool[Tensor, "B T C"]
    """``Tensor["B T C", bool]`` hard availability mask for oracle labels."""

    def __post_init__(self) -> None:
        """Validate the supervision cube without coupling it to actor data."""

        if self.utility.ndim != 3 or self.label_valid.shape != self.utility.shape:
            raise ValueError("utility and label_valid must have matching shape [B,T,C]")
        _require_float("utility", self.utility)
        _require_bool("label_valid", self.label_valid)
        if self.utility.device != self.label_valid.device:
            raise ValueError("utility and label_valid must share one device")


__all__ = ["ActorSceneBundle", "SceneBundleSupervision"]

