"""PyTorch3D camera adapters for VIN frustum diagnostic overlays.

The stable and experimental VIN plotting modules render candidate frusta using
`aria_nbv.utils.data_plotting.SnippetPlotBuilder`, which expects EFM-style
`CameraTW` and `PoseTW` inputs. This sidecar keeps that adapter code out of the
generic Plotly helper module while avoiding imports from higher-level plotting
entry points.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from efm3d.aria.camera import CameraTW
from efm3d.aria.pose import PoseTW
from pytorch3d.renderer.cameras import PerspectiveCameras  # type: ignore[import-untyped]

from ...utils.data_plotting import SnippetPlotBuilder


def _select_p3d_param(param: torch.Tensor | None, index: int) -> torch.Tensor | None:
    """Select one camera parameter row from a PyTorch3D camera batch.

    Singletons are broadcast to every requested index. Multi-camera tensors are
    clamped to the valid range because diagnostics prefer a best-effort overlay
    over failing the whole figure when the caller passes an out-of-range
    candidate index.
    """
    if param is None:
        return None
    if param.ndim == 1:
        return param
    if param.shape[0] == 1:
        return param[0]
    return param[min(max(index, 0), param.shape[0] - 1)]


def _camera_tw_from_p3d(cameras: PerspectiveCameras, index: int) -> CameraTW | None:
    """Convert one PyTorch3D camera's intrinsics to an EFM3D `CameraTW`.

    Returns ``None`` when the camera batch lacks focal length, principal point,
    or image size parameters compatible with a pinhole `CameraTW`.
    """
    if int(cameras.R.shape[0]) == 0:
        return None
    focal = _select_p3d_param(cameras.focal_length, index)
    principal = _select_p3d_param(cameras.principal_point, index)
    image_size = _select_p3d_param(cameras.image_size, index)
    if focal is None or principal is None or image_size is None:
        return None

    focal = focal.reshape(-1)
    principal = principal.reshape(-1)
    image_size = image_size.reshape(-1)
    if focal.numel() != 2 or principal.numel() != 2 or image_size.numel() != 2:
        return None

    height = image_size[0].reshape(1)
    width = image_size[1].reshape(1)
    params = torch.stack((focal[0], focal[1], principal[0], principal[1]), dim=0)

    return CameraTW.from_surreal(
        width=width,
        height=height,
        type_str="Pinhole",
        params=params,
    )


def _pose_from_p3d_camera(cameras: PerspectiveCameras, index: int) -> PoseTW | None:
    """Convert one PyTorch3D world-to-view camera transform to `PoseTW`.

    The returned pose is ``T_world_cam`` and is used only for visualization
    frusta, not for model-side pose features.
    """
    if int(cameras.R.shape[0]) == 0:
        return None
    rot = _select_p3d_param(cameras.R, index)
    trans = _select_p3d_param(cameras.T, index)
    if rot is None or trans is None:
        return None
    rot = rot.reshape(3, 3)
    trans = trans.reshape(3)
    t_wc = -(rot @ trans.unsqueeze(-1)).squeeze(-1)
    return PoseTW.from_Rt(rot, t_wc)


@dataclass(slots=True)
class _FrustumTrajectoryStub:
    """Minimal trajectory object consumed by `SnippetPlotBuilder` frustum code."""

    t_world_rig: PoseTW


@dataclass(slots=True)
class _FrustumSnippetStub:
    """Minimal snippet object consumed by `SnippetPlotBuilder` frustum code."""

    trajectory: _FrustumTrajectoryStub
    mesh: None = None
    semidense: None = None


def _frustum_builder_stub(
    pose_world_cam: PoseTW | None,
    *,
    title: str,
    height: int = 560,
) -> SnippetPlotBuilder | None:
    """Build a `SnippetPlotBuilder` around one candidate pose for overlays."""
    if pose_world_cam is None:
        return None
    snippet_stub = _FrustumSnippetStub(_FrustumTrajectoryStub(t_world_rig=pose_world_cam))
    return SnippetPlotBuilder.from_snippet(
        snippet_stub,  # type: ignore[arg-type]
        title=title,
        height=height,
    )


__all__ = [
    "_FrustumSnippetStub",
    "_FrustumTrajectoryStub",
    "_camera_tw_from_p3d",
    "_frustum_builder_stub",
    "_pose_from_p3d_camera",
    "_select_p3d_param",
]
