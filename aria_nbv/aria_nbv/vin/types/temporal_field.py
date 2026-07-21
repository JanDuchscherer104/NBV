"""Minimal historical-field token contract for model prototyping.

This module intentionally contains no field generation, persistence, fusion,
platform backend, Mojo, or Apple-Silicon implementation.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor


@dataclass(frozen=True, slots=True)
class TemporalFieldBatch:
    """Pooled local-field tokens with pose, time, and padding metadata."""

    features: Tensor
    t_world_field: Tensor
    time_s: Tensor
    valid: Tensor

    def __post_init__(self) -> None:
        if self.features.ndim != 3:
            raise ValueError(f"features must have shape [B,H,F], got {tuple(self.features.shape)}")
        batch, fields, _ = self.features.shape
        if fields == 0:
            raise ValueError("TemporalFieldBatch requires at least one padded or valid field")
        if self.t_world_field.shape != (batch, fields, 3, 4):
            raise ValueError("t_world_field must have shape [B,H,3,4]")
        if self.time_s.shape != (batch, fields) or self.valid.shape != (batch, fields):
            raise ValueError("time_s and valid must have shape [B,H]")
        if self.valid.dtype is not torch.bool:
            raise TypeError("valid must be a bool tensor")


__all__ = ["TemporalFieldBatch"]
