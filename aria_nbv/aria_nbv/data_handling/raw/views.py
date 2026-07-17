"""Typed, zero-copy views over EFM-formatted ATEK samples.

These classes mirror the style of `aria_nbv.data.views` but read the
keys produced by ``efm3d.dataset.efm_model_adaptor.load_atek_wds_dataset_as_efm``.
All properties surface rich shape/type information to make downstream use
explicit and safe.

The view layer defines which fields are actor-visible (`rgb`, calibrated poses,
semidense points, EVL/OBB predictions) and which are oracle/evaluation assets
(attached GT meshes and GT OBBs). It avoids copying large tensors so dataset
writers can attach mesh and snippet context without changing the immutable VIN
offline-cache rows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, replace
from inspect import cleandoc, getattr_static, getsource
from pprint import pformat
from typing import Any, Literal, TypedDict

import numpy as np
import torch
from efm3d.aria.aria_constants import (
    ARIA_CALIB,
    ARIA_DEPTH_TIME_NS,
    ARIA_DISTANCE_M,
    ARIA_FRAME_ID,
    ARIA_IMG,
    ARIA_IMG_TIME_NS,
    ARIA_OBB_FREQUENCY_HZ,
    ARIA_OBB_PADDED,
    ARIA_POINTS_DIST_STD,
    ARIA_POINTS_INV_DIST_STD,
    ARIA_POINTS_TIME_NS,
    ARIA_POINTS_VOL_MAX,
    ARIA_POINTS_VOL_MIN,
    ARIA_POINTS_WORLD,
    ARIA_POSE_T_WORLD_RIG,
    ARIA_POSE_TIME_NS,
)
from efm3d.aria.camera import CameraTW
from efm3d.aria.obb import ObbTW
from efm3d.aria.pose import PoseTW
from efm3d.aria.tensor_wrapper import TensorWrapper
from efm3d.utils.pointcloud import collapse_pointcloud_time
from torch import Tensor
from trimesh import Trimesh  # type: ignore[import-untyped]

from ...utils import summarize
from ..identifiers import compact_ase_atek_sample_id
from ..mesh_cache import MeshProcessSpec

_FIELD_DOC_CACHE: dict[type, dict[str, str]] = {}


def _extract_field_docs(cls: type) -> dict[str, str]:
    """Extract field docstrings from the dataclass source when available."""
    try:
        source = getsource(cls)
    except OSError:
        return {}
    source = cleandoc(source)
    pattern = re.compile(r"^\s*(\w+)\s*:[^\n]*\n\s*\"\"\"(.*?)\"\"\"", re.MULTILINE | re.DOTALL)
    return {name: cleandoc(doc) for name, doc in pattern.findall(source)}


def _get_field_doc(cls: type, field_name: str) -> str | None:
    """Look up a cached field docstring for the requested dataclass field."""
    docs = _FIELD_DOC_CACHE.get(cls)
    if docs is None:
        docs = _extract_field_docs(cls)
        _FIELD_DOC_CACHE[cls] = docs
    return docs.get(field_name)


def _repr(obj: Any, *, include_docstrings: bool) -> str:
    """Build a compact repr payload for view dataclasses."""
    items: dict[str, Any] = {}
    cls = obj.__class__
    for f in fields(obj):
        value = summarize(getattr(obj, f.name))
        if include_docstrings:
            doc = f.metadata.get("doc") if f.metadata else None
            if doc is None:
                doc = _get_field_doc(cls, f.name)
            items[f.name] = {"value": value, "doc": doc} if doc else {"value": value}
        else:
            items[f.name] = value
    return pformat(items, indent=2, width=100, compact=False)


class BaseView:
    """Base class for EFM view dataclasses with fast, optional docstring repr."""

    __repr_docstrings__: bool = False
    """Whether ``repr`` should include field docstrings."""

    def __repr__(self) -> str:  # pragma: no cover - formatting only
        """Return the compact repr for the current view object."""
        return _repr(self, include_docstrings=getattr(self, "__repr_docstrings__", False))

    def repr_with_docstrings(self) -> str:  # pragma: no cover - formatting only
        """Return a repr that includes field docstrings when available."""
        return _repr(self, include_docstrings=True)


# ---------------------------------------------------------------------------
# GT views (EFM-format)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class EfmGtCameraObbView(BaseView):
    """Per-camera oriented bounding boxes for a single timestamp (EFM schema)."""

    category_names: list[str]
    """Human-readable class labels (EFM43 set; see efm3d.qmd and glossary)."""
    category_ids: Tensor
    """Tensor['K'] semantic ids aligned with ``category_names``."""
    instance_ids: Tensor
    """Tensor['K'] instance ids consistent across cameras at this timestamp."""
    object_dimensions: Tensor
    """Tensor['K 3'] box side lengths (x, y, z) in metres."""
    ts_world_object: Tensor
    """Tensor['K 3 4'] world←object pose matrices per instance."""


CamerasDict = TypedDict(
    "CamerasDict",
    {"rgb": EfmGtCameraObbView, "slam-left": EfmGtCameraObbView, "slam-right": EfmGtCameraObbView},
)


@dataclass(slots=True)
class EfmGtTimestampView(BaseView):
    """EFM GT slice for one timestamp across cameras."""

    time_id: str
    """Timestamp identifier for this GT slice."""

    cameras: CamerasDict
    """Per-camera GT OBB views keyed by camera stream name."""


@dataclass(slots=True)
class EfmGTView(BaseView):
    """Ground-truth annotations (EFM schema) for a snippet."""

    raw: dict[str, Any]
    """Backing raw GT payload."""

    efm_gt: dict[str, EfmGtTimestampView]
    """Parsed timestamp-indexed GT views."""

    def __init__(self, raw: dict[str, Any]):
        """Parse nested EFM GT dictionaries into typed timestamp views."""
        self.raw = raw or {}
        efm_raw = self.raw.get("efm_gt") or {}
        parsed: dict[str, EfmGtTimestampView] = {}
        for ts_key, cams in efm_raw.items():
            if not isinstance(cams, dict):
                continue
            cam_views: dict[str, EfmGtCameraObbView] = {}
            for cam_id, cam_dict in cams.items():
                if not isinstance(cam_dict, dict):
                    continue
                cam_views[cam_id] = EfmGtCameraObbView(
                    category_names=cam_dict.get("category_names", []),
                    category_ids=cam_dict.get("category_ids"),  # type: ignore[arg-type]
                    instance_ids=cam_dict.get("instance_ids"),  # type: ignore[arg-type]
                    object_dimensions=cam_dict.get("object_dimensions"),  # type: ignore[arg-type]
                    ts_world_object=cam_dict.get("ts_world_object"),  # type: ignore[arg-type]
                )
            parsed[str(ts_key)] = EfmGtTimestampView(time_id=str(ts_key), cameras=cam_views)
        self.efm_gt = parsed

    @property
    def timestamps(self) -> list[str]:
        """Sorted list of efm_gt timestamp keys."""

        return sorted(self.efm_gt.keys())

    def cameras_at(self, ts: str | int) -> dict[str, EfmGtCameraObbView]:
        """Get per-camera OBB GT at a timestamp."""

        key = str(ts)
        if key not in self.efm_gt:
            raise KeyError(f"No efm_gt entry for timestamp {ts}")
        return self.efm_gt[key].cameras


@dataclass(slots=True)
class EfmCameraView(BaseView):
    """Zero-copy camera stream view in EFM schema (images, calibration, timing, optional depth)."""

    images: Tensor
    """``Tensor["F C H W", float32]`` normalized camera images in Aria LUF frame."""
    calib: CameraTW
    """Per-frame camera intrinsics/extrinsics (`CameraTW.tensor` shape ``(F,34)``)."""
    time_ns: Tensor
    """``Tensor["F", int64]`` device timestamps aligned to `images`."""
    frame_ids: Tensor
    """``Tensor["F", int64|float32]`` frame ids within the snippet."""
    distance_m: Tensor | None = None
    """Optional metric ray distances ``Tensor["F 1 H W", float32]``."""
    distance_time_ns: Tensor | None = None
    """Optional ``Tensor["F", int64]`` timestamps for ``distance_m``."""

    def to(self, device: str | torch.device, *, dtype: torch.dtype | None = None) -> "EfmCameraView":
        """Move the camera view tensors to the requested device and dtype."""
        target_device = torch.device(device)
        if self.images.device.type == target_device.type and dtype is None:
            return self  # no-op, keep zero-copy view
        return replace(
            self,
            images=self.images.to(device=target_device, dtype=dtype),
            calib=self.calib.to(device=target_device),  # type: ignore[arg-type]
            time_ns=self.time_ns.to(target_device),
            frame_ids=self.frame_ids.to(target_device),
            distance_m=None if self.distance_m is None else self.distance_m.to(device=target_device, dtype=dtype),
            distance_time_ns=None if self.distance_time_ns is None else self.distance_time_ns.to(target_device),
        )

    def get_fov(self) -> Tensor:
        """Tensor["F 2", float32] FOV in degrees (fov_x, fov_y) per frame."""
        size = self.calib.size  # (..., 2) = (F,2)
        focals = self.calib.f  # (..., 2)
        width = size[..., 0].to(dtype=torch.float32)
        height = size[..., 1].to(dtype=torch.float32)
        fx = focals[..., 0].to(dtype=torch.float32)
        fy = focals[..., 1].to(dtype=torch.float32)

        valid = (width > 0) & (height > 0) & (fx > 0) & (fy > 0)
        fov_x = torch.full_like(width, float("nan"))
        fov_y = torch.full_like(height, float("nan"))
        fov_x = torch.where(valid, torch.rad2deg(2 * torch.atan(width / (2 * fx))), fov_x)
        fov_y = torch.where(valid, torch.rad2deg(2 * torch.atan(height / (2 * fy))), fov_y)

        return torch.stack([fov_x, fov_y], dim=-1)

    @property
    def num_frames(self) -> int:
        """Return the number of frames in the camera stream."""
        return self.images.shape[0]

    def select_frame_indices(self, frame_indices: list[int] | None, *, default_last: bool) -> torch.Tensor:
        """Resolve user-provided frame indices, supporting negatives and defaults."""

        n_cam = self.num_frames
        if n_cam == 0:
            return torch.tensor([], device=self.time_ns.device, dtype=torch.long)
        if frame_indices is None or len(frame_indices) == 0:
            frame_indices = [0, n_cam - 1] if default_last and n_cam > 1 else [0]
        idx = torch.as_tensor(frame_indices, device=self.time_ns.device, dtype=torch.long)
        idx = torch.where(idx < 0, idx + n_cam, idx)
        return idx.clamp(0, n_cam - 1)

    def nearest_traj_indices(
        self,
        traj_ts_ns: torch.Tensor,
        frame_indices: list[int] | torch.Tensor | None = None,
        *,
        default_last: bool = True,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Return selected camera indices and nearest trajectory indices."""

        cam_idx = (
            frame_indices
            if isinstance(frame_indices, torch.Tensor)
            else self.select_frame_indices(frame_indices, default_last=default_last)
        )
        if cam_idx.numel() == 0 or traj_ts_ns.numel() == 0:
            empty = torch.tensor([], device=self.time_ns.device, dtype=torch.long)
            return cam_idx, empty

        cam_ts = self.time_ns.to(cam_idx.device)
        traj_ts = traj_ts_ns.to(cam_idx.device)
        cam_sel_ts = cam_ts[cam_idx]
        dt = (traj_ts.unsqueeze(1) - cam_sel_ts.unsqueeze(0)).abs()
        traj_idx = torch.argmin(dt, dim=0)
        return cam_idx, traj_idx


@dataclass(slots=True)
class EfmTrajectoryView(BaseView):
    """World-frame rig trajectory aligned to snippet frames."""

    t_world_rig: PoseTW
    """Rig SE(3) poses per frame (world←rig)."""
    time_ns: Tensor
    """``Tensor["F", int64]`` pose timestamps."""
    gravity_in_world: Tensor
    """``Tensor["3", float32]`` gravity vector in world frame (aligned to [0,0,-9.81])."""

    @property
    def final_pose(self) -> PoseTW:
        """Final rig pose in snippet. world ← rig."""

        return PoseTW.from_matrix3x4(self.t_world_rig.matrix3x4[-1])

    def to(self, device: str | torch.device, *, dtype: torch.dtype | None = None) -> "EfmTrajectoryView":
        """Move the trajectory tensors to the requested device and dtype."""
        target_device = torch.device(device)
        if self.time_ns.device.type == target_device.type and dtype is None:
            return self
        return replace(
            self,
            t_world_rig=self.t_world_rig.to(device=target_device),  # type: ignore[arg-type]
            time_ns=self.time_ns.to(target_device),
            gravity_in_world=self.gravity_in_world.to(device=target_device, dtype=dtype),
        )


@dataclass(slots=True)
class EfmPointsView(BaseView):
    """Padded semi-dense SLAM point cloud view with per-frame metadata."""

    points_world: Tensor
    """``Tensor["F N 3", float32]`` padded world-frame SLAM points (meters)."""
    dist_std: Tensor
    """``Tensor["F N", float32]`` per-point distance std (depth uncertainty)."""
    inv_dist_std: Tensor
    """``Tensor["F N", float32]`` per-point inverse distance std."""
    time_ns: Tensor
    """``Tensor["F", int64]`` timestamps aligned to point slices."""
    volume_min: Tensor
    """``Tensor["3", float32]`` snippet AABB minimum in world coords."""
    volume_max: Tensor
    """``Tensor["3", float32]`` snippet AABB maximum in world coords."""
    lengths: Tensor
    """``Tensor["F", int64]`` true (unpadded) point counts per frame."""

    def to(self, device: str | torch.device, *, dtype: torch.dtype | None = None) -> "EfmPointsView":
        """Move the semidense point tensors to the requested device and dtype."""
        target_device = torch.device(device)
        if self.points_world.device.type == target_device.type and dtype is None:
            return self
        return replace(
            self,
            points_world=self.points_world.to(device=target_device, dtype=dtype),
            dist_std=self.dist_std.to(device=target_device, dtype=dtype),
            inv_dist_std=self.inv_dist_std.to(device=target_device, dtype=dtype),
            time_ns=self.time_ns.to(target_device),
            volume_min=self.volume_min.to(device=target_device, dtype=dtype),
            volume_max=self.volume_max.to(device=target_device, dtype=dtype),
            lengths=self.lengths.to(target_device),
        )

    def collapse_points(
        self,
        max_points: int | None = None,
        include_inv_dist_std: bool = False,
        include_obs_count: bool = False,
    ) -> Tensor:
        """Collapse points across time and optionally subsample.

        Args:
            max_points: Optional cap on the number of returned points.
            include_inv_dist_std: If True, append inverse depth std per point.
            include_obs_count: If True, append the number of snippet frames that
                observed each point (observation count).

        Returns:
            ``Tensor["K 3", float32]`` if no extra features are requested.
            ``Tensor["K 4", float32]`` if exactly one extra feature is requested
            (XYZ + inv_dist_std or XYZ + obs_count).
            ``Tensor["K 5", float32]`` if both extras are requested
            (XYZ + inv_dist_std + obs_count).
        """

        points = self.points_world
        if points.numel() == 0:
            extra_dim = int(include_inv_dist_std) + int(include_obs_count)
            return torch.zeros((0, 3 + extra_dim), dtype=points.dtype, device=points.device)

        lengths = self.lengths.to(device=points.device)
        max_len = points.shape[1]
        valid_mask = torch.arange(max_len, device=points.device).unsqueeze(0) < lengths.clamp_max(max_len).unsqueeze(-1)
        valid_mask &= torch.isfinite(points).all(dim=-1)

        if include_obs_count:
            points_flat = points[valid_mask]
            if points_flat.numel() == 0:
                extra_dim = int(include_inv_dist_std) + 1
                return torch.zeros((0, 3 + extra_dim), dtype=points.dtype, device=points.device)

            unique_points, inverse, counts = torch.unique(
                points_flat,
                dim=0,
                return_inverse=True,
                return_counts=True,
            )
            obs_count = counts.to(dtype=points.dtype)
            extras: list[Tensor] = []

            if include_inv_dist_std:
                inv_dist_std = self.inv_dist_std.to(device=points.device, dtype=points.dtype)
                inv_flat = inv_dist_std[valid_mask]
                inv_sum = torch.zeros(unique_points.shape[0], device=points.device, dtype=points.dtype)
                inv_sum.scatter_add_(0, inverse, inv_flat)
                inv_mean = inv_sum / obs_count.clamp_min(1.0)
                extras.append(inv_mean.unsqueeze(-1))

            extras.append(obs_count.unsqueeze(-1))
            points_out = unique_points
            if extras:
                points_out = torch.cat([points_out] + extras, dim=-1)

            if max_points is not None and points_out.shape[0] > max_points:
                idx = torch.randperm(points_out.shape[0], device=points_out.device)[:max_points]
                points_out = points_out[idx]
            return points_out

        if include_inv_dist_std:
            inv_dist_std = self.inv_dist_std.to(device=points.device, dtype=points.dtype)
            points_masked = torch.where(valid_mask.unsqueeze(-1), points, torch.nan)
            inv_masked = torch.where(valid_mask, inv_dist_std, torch.nan)
            points_flat = points_masked.reshape(-1, 3)
            inv_flat = inv_masked.reshape(-1, 1)
            finite = torch.isfinite(points_flat).all(dim=-1) & torch.isfinite(inv_flat).all(dim=-1)
            points_flat = points_flat[finite]
            inv_flat = inv_flat[finite]
            if points_flat.numel() == 0:
                return torch.zeros((0, 4), dtype=points.dtype, device=points.device)
            if max_points is not None and points_flat.shape[0] > max_points:
                idx = torch.randperm(points_flat.shape[0], device=points_flat.device)[:max_points]
                points_flat = points_flat[idx]
                inv_flat = inv_flat[idx]
            return torch.cat([points_flat, inv_flat], dim=-1)

        points_collapsed = collapse_pointcloud_time(
            torch.where(valid_mask.unsqueeze(-1), points, torch.nan),
        )
        if points_collapsed.numel() == 0:
            return torch.zeros((0, 3), dtype=points.dtype, device=points.device)

        if max_points is not None and points_collapsed.shape[0] > max_points:
            idx = torch.randperm(points_collapsed.shape[0], device=points_collapsed.device)[:max_points]
            points_collapsed = points_collapsed[idx]

        return points_collapsed

    def last_frame_points_np(self, max_points: int | None = None) -> np.ndarray:
        """Return points from the latest frame with valid points, subsampled if needed."""

        points = self.points_world
        lengths = self.lengths.to(device=points.device)
        if points.numel() == 0 or lengths.numel() == 0:
            return np.zeros((0, 3), dtype=np.float32)

        if torch.any(lengths > 0):
            last_idx = int(torch.nonzero(lengths > 0, as_tuple=False).max().item())
        else:
            return np.zeros((0, 3), dtype=np.float32)

        n_valid = min(int(lengths[last_idx].item()), points.shape[1])
        if n_valid == 0:
            return np.zeros((0, 3), dtype=np.float32)

        pts = points[last_idx, :n_valid]
        finite = torch.isfinite(pts).all(dim=-1)
        pts = pts[finite]
        if pts.numel() == 0:
            return np.zeros((0, 3), dtype=np.float32)

        if max_points is not None and pts.shape[0] > max_points:
            idx = torch.randperm(pts.shape[0], device=pts.device)[:max_points]
            pts = pts[idx]

        return pts.detach().cpu().numpy()


@dataclass(slots=True)
class EfmObbView(BaseView):
    """Snippet-level oriented bounding boxes in the EFM `ObbTW` layout.

    `obbs` may be shaped `(T, K, 34)`, `(1, K, 34)`, or `(K, 34)` depending on
    the source. `K` is padded; padded rows are all `PAD_VAL` and must be removed
    with `ObbTW.get_padding_mask()` before ranking or matching targets.

    The `34` payload columns are the EFM OBB contract: object-frame 3D bounds,
    three 2D boxes, a 12-value pose, semantic id, instance id, confidence, and
    movable flag. Downstream target selection transforms the latest valid slice
    into world coordinates before constructing Oracle target tasks.
    """

    obbs: ObbTW
    """Padded oriented boxes in snippet frame or world frame, shape ``(..., K, 34)``."""
    hz: Tensor | None = None
    """Optional ``Tensor["1", int32]`` detection frequency."""


@dataclass(slots=True)
class EfmSnippetView(BaseView):
    """Typed wrapper over an EFM-formatted sample plus optional mesh."""

    efm: dict[str, Any]
    """Backing EFM sample dictionary (zero-copy)."""
    scene_id: str
    """ASE scene identifier (e.g., ``81283``)."""
    snippet_id: str
    """Snippet/shard identifier (e.g., ``shards-0000``)."""
    mesh: Trimesh | None = None
    """Optional GT mesh paired with this sample."""
    crop_bounds: tuple[torch.Tensor, torch.Tensor] | None = None
    """Optional `(min, max)` world-space AABB used for mesh cropping / occupancy."""

    mesh_verts: torch.Tensor | None = None
    """Optional cached mesh vertices tensor (float32, device-agnostic)."""
    mesh_faces: torch.Tensor | None = None
    """Optional cached mesh faces tensor (int64)."""
    mesh_cache_key: str | None = None
    """Stable key (spec hash) for shared mesh caches across components."""

    mesh_specs: MeshProcessSpec | None = None
    """Optional mesh processing specification used to derive attached mesh tensors."""

    @staticmethod
    def _parse_key_ids(sample_key: str) -> tuple[str, str]:
        """Parse scene/snippet identifiers from the cache sample key.

        Args:
            sample_key: Cache key like ``"AriaSyntheticEnvironment_82832_AtekDataSample_000056"``.

        Returns:
            Tuple of ``(scene_id, snippet_id)``.

        Raises:
            ValueError: If the key does not match the expected cache format.
        """
        match = re.match(r"^AriaSyntheticEnvironment_(\d+)_AtekDataSample_(\d+)$", sample_key)
        if not match:
            raise ValueError(f"Unsupported cache key format: {sample_key}")
        return match.group(1), compact_ase_atek_sample_id(sample_key)

    @staticmethod
    def _infer_cache_bounds(efm: dict[str, Any]) -> tuple[torch.Tensor, torch.Tensor] | None:
        """Infer AABB bounds for cache samples from stored volume metadata."""
        vol_min = None
        for key in (ARIA_POINTS_VOL_MIN, "points/vol_min", "scene/points/vol_min"):
            value = efm.get(key)
            if isinstance(value, torch.Tensor):
                vol_min = value
                break
        vol_max = None
        for key in (ARIA_POINTS_VOL_MAX, "points/vol_max", "scene/points/vol_max"):
            value = efm.get(key)
            if isinstance(value, torch.Tensor):
                vol_max = value
                break
        if not isinstance(vol_min, torch.Tensor) or not isinstance(vol_max, torch.Tensor):
            return None
        if vol_min.numel() != 3 or vol_max.numel() != 3:
            return None
        if not torch.isfinite(vol_min).all() or not torch.isfinite(vol_max).all():
            return None
        return vol_min.detach().cpu(), vol_max.detach().cpu()

    @classmethod
    def from_cache_efm(
        cls,
        efm: dict[str, Any],
        *,
        mesh: Trimesh | None = None,
        crop_bounds: tuple[torch.Tensor, torch.Tensor] | None = None,
        mesh_verts: torch.Tensor | None = None,
        mesh_faces: torch.Tensor | None = None,
        mesh_cache_key: str | None = None,
        mesh_specs: MeshProcessSpec | None = None,
    ) -> "EfmSnippetView":
        """Construct a snippet view from an offline-cache EFM dict.

        Args:
            efm: Raw cache sample dict that includes ``"__key__"``.
            mesh: Optional GT mesh to attach.
            crop_bounds: Optional world-space AABB override.
            mesh_verts: Optional cached mesh vertices.
            mesh_faces: Optional cached mesh faces.
            mesh_cache_key: Optional mesh cache key for shared caches.
            mesh_specs: Optional mesh processing spec.

        Returns:
            Parsed `EfmSnippetView` instance.
        """
        key = efm.get("__key__")
        if not isinstance(key, str):
            raise ValueError("Cache sample missing string '__key__'.")
        scene_id, snippet_id = cls._parse_key_ids(key)
        if crop_bounds is None:
            crop_bounds = cls._infer_cache_bounds(efm)
        return cls(
            efm=efm,
            scene_id=scene_id,
            snippet_id=snippet_id,
            mesh=mesh,
            crop_bounds=crop_bounds,
            mesh_verts=mesh_verts,
            mesh_faces=mesh_faces,
            mesh_cache_key=mesh_cache_key,
            mesh_specs=mesh_specs,
        )

    # ------------------------------------------------------------------
    # Cameras
    # ------------------------------------------------------------------
    def get_camera(self, prefix: Literal["rgb", "slaml", "slamr"]) -> EfmCameraView:
        """Return the requested camera stream view from the backing EFM dict."""
        idx = {"rgb": 0, "slaml": 1, "slamr": 2}[prefix]
        img_key = ARIA_IMG[idx]
        calib_key = ARIA_CALIB[idx]
        time_key = ARIA_IMG_TIME_NS[idx]
        frame_id_key = ARIA_FRAME_ID[idx]
        distance_key = ARIA_DISTANCE_M[idx]
        distance_time_key = ARIA_DEPTH_TIME_NS[idx]

        img = self.efm[img_key]
        calib: CameraTW = self.efm[calib_key]
        time_ns = self.efm[time_key]
        frame_ids = self.efm[frame_id_key]
        distance = self.efm.get(distance_key)
        distance_time_ns = self.efm.get(distance_time_key)

        return EfmCameraView(
            images=img,
            calib=calib,
            time_ns=time_ns,
            frame_ids=frame_ids,
            distance_m=distance,
            distance_time_ns=distance_time_ns,
        )

    @property
    def camera_rgb(self) -> EfmCameraView:
        """RGB stream (fisheye624, 240x240 in ASE preprocessing)."""

        return self.get_camera("rgb")

    @property
    def camera_slam_left(self) -> EfmCameraView:
        """Left SLAM mono stream (fisheye624, ~320x240)."""

        return self.get_camera("slaml")

    @property
    def camera_slam_right(self) -> EfmCameraView:
        """Right SLAM mono stream (fisheye624, ~320x240)."""

        return self.get_camera("slamr")

    # ------------------------------------------------------------------
    # Trajectory and semidense points
    # ------------------------------------------------------------------
    @property
    def trajectory(self) -> EfmTrajectoryView:
        """Rig trajectory (world←rig) aligned to snippet frames."""

        return EfmTrajectoryView(
            t_world_rig=self.efm[ARIA_POSE_T_WORLD_RIG],
            time_ns=self.efm[ARIA_POSE_TIME_NS],
            gravity_in_world=self.efm["pose/gravity_in_world"],
        )

    @property
    def semidense(self) -> EfmPointsView:
        """Semi-dense SLAM points (padded to fixed length)."""

        efm = self.efm
        points = efm[ARIA_POINTS_WORLD]
        lengths = efm.get("points/lengths")
        if lengths is None:
            lengths = torch.full(
                (points.shape[0],),
                points.shape[1],
                dtype=torch.int64,
                device=points.device,
            )
        return EfmPointsView(
            points_world=points,
            dist_std=efm[ARIA_POINTS_DIST_STD],
            inv_dist_std=efm[ARIA_POINTS_INV_DIST_STD],
            time_ns=efm[ARIA_POINTS_TIME_NS],
            volume_min=efm.get(ARIA_POINTS_VOL_MIN, efm.get("points/vol_min")),
            volume_max=efm.get(ARIA_POINTS_VOL_MAX, efm.get("points/vol_max")),
            lengths=lengths,
        )

    # ------------------------------------------------------------------
    # OBB / occupancy
    # ------------------------------------------------------------------
    @property
    def obbs(self) -> EfmObbView | None:
        """Snippet-level OBBs (if present)."""

        if "obbs/padded_snippet" not in self.efm:
            return None
        return EfmObbView(
            obbs=self.efm[ARIA_OBB_PADDED],
            hz=self.efm.get(ARIA_OBB_FREQUENCY_HZ),
        )

    # ------------------------------------------------------------------
    # Ground truth
    # ------------------------------------------------------------------
    @property
    def gt(self) -> EfmGTView:
        """Ground-truth dict ``gt_data`` (EFM OBBs per timestamp/camera)."""

        return EfmGTView(raw=self.efm.get("gt_data", {}))

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    @property
    def has_mesh(self) -> bool:
        """Return whether a ground-truth mesh is attached to the snippet."""
        return self.mesh is not None

    def get_occupancy_extend(self) -> torch.Tensor:
        """Return ``[xmin, xmax, ymin, ymax, zmin, zmax]`` AABB in world frame."""
        if self.crop_bounds is None:
            raise ValueError("EfmSnippetView.crop_bounds is missing; dataset should always populate it.")
        bounds_min, bounds_max = self.crop_bounds
        return torch.stack(
            [bounds_min[0], bounds_max[0], bounds_min[1], bounds_max[1], bounds_min[2], bounds_max[2]], dim=0
        )

    def to(self, device: str | torch.device, *, dtype: torch.dtype | None = None) -> "EfmSnippetView":
        """Shallow device move for heavy tensors."""

        target_device = torch.device(device)
        target_type = target_device.type
        if dtype is None and all(
            isinstance(v, Tensor)
            and v.device.type == target_type
            or isinstance(v, (PoseTW, CameraTW, TensorWrapper, ObbTW))
            for v in self.efm.values()
        ):
            return self

        moved: dict[str, Any] = {}
        for k, v in self.efm.items():
            if isinstance(v, Tensor):
                moved[k] = v.to(device=target_device, dtype=dtype)
            elif isinstance(v, (PoseTW, CameraTW, TensorWrapper, ObbTW)):
                moved[k] = v.to(device=target_device)  # type: ignore[arg-type]
            else:
                moved[k] = v
        cb = self.crop_bounds
        if cb is not None:
            cb = (cb[0].to(target_device), cb[1].to(target_device))
        mv = self.mesh_verts
        mf = self.mesh_faces
        if mv is not None:
            mv = mv.to(target_device)
        if mf is not None:
            mf = mf.to(target_device)
        return replace(
            self,
            efm=moved,
            mesh=self.mesh,
            crop_bounds=cb,
            mesh_verts=mv,
            mesh_faces=mf,
            mesh_cache_key=self.mesh_cache_key,
            mesh_specs=self.mesh_specs,
        )

    def prune_efm(
        self,
        keep_keys: set[str] | None,
        *,
        keep_prefixes: tuple[str, ...] = (),
    ) -> "EfmSnippetView":
        """Return a view with the EFM dict pruned to the requested keys.

        Args:
            keep_keys: Exact EFM keys to retain. ``None`` returns ``self`` unchanged.
            keep_prefixes: Optional prefixes; keys starting with any prefix are retained.
        """
        if keep_keys is None and not keep_prefixes:
            return self
        if keep_keys is None:
            keep_keys = set()
        pruned = {
            k: v for k, v in self.efm.items() if k in keep_keys or any(k.startswith(prefix) for prefix in keep_prefixes)
        }
        if "__key__" in self.efm:
            pruned["__key__"] = self.efm["__key__"]
        return replace(self, efm=pruned)

    def __repr__(self) -> str:  # pragma: no cover
        """Return a summary-focused repr for the snippet view."""
        base = {
            "scene": self.scene_id,
            "snippet": self.snippet_id,
            "cameras": {
                "rgb": summarize(self.efm.get("rgb/img")),
                "slaml": summarize(self.efm.get("slaml/img")),
                "slamr": summarize(self.efm.get("slamr/img")),
            },
            "trajectory": summarize(self.efm.get(ARIA_POSE_T_WORLD_RIG)),
            "semidense": summarize(self.efm.get(ARIA_POINTS_WORLD)),
            "obbs": summarize(self.efm.get(ARIA_OBB_PADDED)),
            "mesh": str(self.mesh) if self.mesh is not None else None,
            "crop_bounds": summarize(self.crop_bounds),
        }
        return pformat(base, indent=2, width=120, compact=False)


@dataclass(slots=True)
class VinSnippetView(BaseView):
    """Minimal snippet payload for VIN v2 batching.

    Attributes:
        points_world: ``Tensor["K (3+C)", float32]`` collapsed semidense points.
            Base columns are XYZ; optional extras include inv_dist_std and
            observation count (number of snippet frames that saw the point).
        lengths: ``Tensor["B"]`` or ``Tensor["1"]`` number of valid points in
            ``points_world`` (before padding).
        t_world_rig: ``PoseTW["F 12"]`` historical world←rig poses.
    """

    points_world: Tensor
    """Collapsed semidense point cloud with optional extra features."""
    lengths: Tensor
    """Number of valid points in ``points_world`` (before padding)."""
    t_world_rig: PoseTW
    """Trajectory poses (world←rig)."""

    def to(self, device: str | torch.device, *, dtype: torch.dtype | None = None) -> "VinSnippetView":
        """Move the VIN snippet tensors to the requested device and dtype."""
        target_device = torch.device(device)
        return replace(
            self,
            points_world=self.points_world.to(device=target_device, dtype=dtype),
            lengths=self.lengths.to(target_device),
            t_world_rig=self.t_world_rig.to(device=target_device, dtype=dtype),  # type: ignore[arg-type]
        )

    def __repr__(self) -> str:
        """Return the compact repr for the VIN snippet view."""
        return _repr(self, include_docstrings=getattr(self, "__repr_docstrings__", False))


def is_efm_snippet_view_instance(value: object) -> bool:
    """Return whether ``value`` behaves like an `EfmSnippetView`.

    The v2 stack accepts both the local data-handling view classes and legacy
    view objects that expose the same public attributes.
    """
    try:
        getattr_static(value, "efm")
        getattr_static(value, "trajectory")
        getattr_static(value, "semidense")
    except AttributeError:
        return False
    return True


def is_vin_snippet_view_instance(value: object) -> bool:
    """Return whether ``value`` behaves like a `VinSnippetView`."""
    try:
        getattr_static(value, "points_world")
        getattr_static(value, "lengths")
        getattr_static(value, "t_world_rig")
    except AttributeError:
        return False
    return True


__all__ = [
    "EfmCameraView",
    "EfmTrajectoryView",
    "EfmPointsView",
    "EfmObbView",
    "EfmGTView",
    "EfmGtTimestampView",
    "EfmGtCameraObbView",
    "EfmSnippetView",
    "VinSnippetView",
    "is_efm_snippet_view_instance",
    "is_vin_snippet_view_instance",
]
