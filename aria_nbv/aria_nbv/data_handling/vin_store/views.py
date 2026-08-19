"""Actor-visible DTOs owned by the immutable VIN-store boundary.

This module defines :class:`VinSnippetView` and its structural instance check.
It owns the compact tensors returned by VIN-store datasets; raw ASE/ATEK EFM
views and persistence or batching behavior remain in their dedicated modules.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from inspect import getattr_static

import torch
from efm3d.aria.pose import PoseTW
from torch import Tensor

from .._repr_support import _CompactReprMixin


@dataclass(slots=True, repr=False)
class VinSnippetView(_CompactReprMixin):
    """Minimal actor-visible snippet payload for VIN batching.

    Attributes:
        points_world: ``Tensor["K_pad 3+C", float32]`` collapsed semidense
            points. Base columns are XYZ; optional extras include inverse
            distance uncertainty and observation count. Rows after ``lengths``
            are NaN padding.
        lengths: ``Tensor["1", int64]`` or ``Tensor["B", int64]`` valid point
            counts for unbatched or batched payloads.
        t_world_rig: ``PoseTW["F 12"]`` historical world-from-rig poses.
    """

    points_world: Tensor
    """``Tensor["K_pad 3+C", float32]`` world-frame MPS points in metres; tail rows are NaN padding."""

    lengths: Tensor
    """``Tensor["1", int64]`` valid point-prefix length before fixed-width padding."""

    t_world_rig: PoseTW
    """``PoseTW["F 12"]`` MPS/EFM world-from-rig trajectory; translation is metres."""

    t_world_snippet: PoseTW
    """``PoseTW["1 12"]`` persisted world-from-snippet gauge; translation is metres."""

    def to(self, device: str | torch.device, *, dtype: torch.dtype | None = None) -> VinSnippetView:
        """Move the VIN snippet tensors to the requested device and dtype."""

        target_device = torch.device(device)
        return replace(
            self,
            points_world=self.points_world.to(device=target_device, dtype=dtype),
            lengths=self.lengths.to(target_device),
            t_world_rig=self.t_world_rig.to(device=target_device, dtype=dtype),  # type: ignore[arg-type]
            t_world_snippet=self.t_world_snippet.to(device=target_device, dtype=dtype),  # type: ignore[arg-type]
        )


def is_vin_snippet_view_instance(value: object) -> bool:
    """Return whether ``value`` exposes the structural VIN snippet interface."""

    try:
        getattr_static(value, "points_world")
        getattr_static(value, "lengths")
        getattr_static(value, "t_world_rig")
        getattr_static(value, "t_world_snippet")
    except AttributeError:
        return False
    return True


__all__ = ["VinSnippetView", "is_vin_snippet_view_instance"]
