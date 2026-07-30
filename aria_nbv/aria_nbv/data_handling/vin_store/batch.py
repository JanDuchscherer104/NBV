"""Shared VIN oracle batch records, masking, and collation utilities.

This module owns the training-facing boundary between actor-visible EFM/EVL
state and GT-mesh-derived candidate supervision. It provides compact OBB and
trajectory records plus :class:`VinOracleBatch`, whose candidate axis is
prefix-masked and whose collation keeps poses, cameras, RRI, and metric fields
aligned.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import torch
from efm3d.aria.pose import PoseTW
from pytorch3d.renderer.cameras import PerspectiveCameras
from torch import Tensor

from ...vin.types import EvlBackboneOutput
from ..ase_efm.views import EfmSnippetView
from .views import VinSnippetView, is_vin_snippet_view_instance

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(slots=True)
class CompactObbBlock:
    """Collatable numeric OBB payload used by training and diagnostics.

    ``obbs`` keeps the raw EFM ``ObbTW`` backing layout, not a simplified center
    size representation. The shape is ``(..., K, 34)``, where ``K`` is a padded box
    slot count. Valid boxes must be determined through
    `ObbTW(obbs).get_padding_mask()`.

    The last dimension follows the EFM layout:

    * `0:6`: object-frame 3D bounds `[xmin, xmax, ymin, ymax, zmin, zmax]`;
    * `6:10`, `10:14`, `14:18`: RGB, SLAM-left, and SLAM-right 2D boxes;
    * `18:30`: `PoseTW` object-to-world/object-to-snippet transform payload;
    * `30`, `31`, `32`, `33`: semantic id, instance id, confidence, movable.

    The tensor is stored as ``float32`` even for id-like columns; use ``ObbTW``
    properties such as ``sem_id``, ``inst_id``, ``prob``,
    ``bb3_center_world``, and ``bb3_diagonal`` when interpreting rows. The
    container is boundary-neutral: :attr:`VinOracleBatch.gt_obbs` is
    oracle/evaluation data, while :attr:`VinOracleBatch.detected_obbs` is
    actor-visible EVL evidence.
    """

    obbs: Tensor
    """``Tensor["... K 34", float32]`` padded boxes in the EFM ``ObbTW`` layout."""

    sem_id_to_name: dict[int, str] | None = None
    """Optional sparse semantic id to class-name map."""

    probs: Tensor | None = None
    """Optional ``Tensor["... K C", float32]`` class probabilities aligned to box rows."""


@dataclass(slots=True)
class CompactTrajectoryBlock:
    """Preserve MPS/EFM timing and gravity metadata beside VIN trajectory poses."""

    time_ns: Tensor | None = None
    """Optional ``Tensor["F", int64]`` Aria device-clock pose timestamps."""

    gravity_in_world: Tensor | None = None
    """Optional ``Tensor["3", float32]`` world-frame gravity in metres per second squared."""


@dataclass(slots=True)
class VinOracleBatch:
    """Single-snippet VIN training batch produced from an oracle label run.

    Attributes:
        efm_snippet_view: EFM snippet view or minimal VIN snippet (None when loading from cache).
        candidate_poses_world_cam: ``PoseTW["N 12"]`` or ``PoseTW["B N 12"]`` candidate poses as world←camera.
        reference_pose_world_rig: ``PoseTW["12"]`` or ``PoseTW["B 12"]`` reference pose as world←rig_reference.
        rri: ``Tensor["N", float32]`` or ``Tensor["B N", float32]`` oracle RRI per candidate.
        pm_dist_before: ``Tensor["N", float32]`` or ``Tensor["B N", float32]`` pre-view bidirectional error in square metres (broadcasted).
        pm_dist_after: ``Tensor["N", float32]`` or ``Tensor["B N", float32]`` post-view bidirectional error in square metres (per candidate).
        pm_acc_before: ``Tensor["N", float32]`` or ``Tensor["B N", float32]`` pre-view point-to-mesh error in square metres.
        pm_comp_before: ``Tensor["N", float32]`` or ``Tensor["B N", float32]`` pre-view mesh-to-point error in square metres.
        pm_acc_after: ``Tensor["N", float32]`` or ``Tensor["B N", float32]`` post-view point-to-mesh error in square metres.
        pm_comp_after: ``Tensor["N", float32]`` or ``Tensor["B N", float32]`` post-view mesh-to-point error in square metres.
        p3d_cameras: Actor-visible candidate calibration and world-to-view transforms, aligned with candidates.
        candidate_count: Number of valid candidates (scalar or batched vector). When
            absent, runtime code falls back to the full candidate width.
        scene_id: ASE scene id for diagnostics (string or list when batched).
        snippet_id: Snippet id (tar key/url stem) for diagnostics (string or list when batched).
        backbone_out: Optional cached EVL backbone outputs.

    Actor-visible inputs are the snippet view, candidate poses and PyTorch3D
    calibration/transforms, EVL backbone output, detected OBBs, and trajectory
    metadata. Candidate RRI/distance fields, mesh-derived renders, and GT OBBs
    are supervision/evaluation assets. ``candidate_count`` defines the valid
    prefix; padded candidates must be masked rather than interpreted as
    low-quality actions.
    """

    efm_snippet_view: EfmSnippetView | VinSnippetView | None
    """Optional actor-visible raw EFM view or compact MPS-derived VIN view."""
    candidate_poses_world_cam: PoseTW
    """``PoseTW["N 12"]`` or ``PoseTW["B N 12"]`` world←camera candidates."""

    reference_pose_world_rig: PoseTW
    """``PoseTW["12"]`` or ``PoseTW["B 12"]`` world←rig reference poses."""

    rri: Tensor
    """``Tensor["N", float32]`` or ``Tensor["B N", float32]`` dimensionless oracle RRI."""

    pm_dist_before: Tensor
    """``Tensor["N", float32]`` or ``Tensor["B N", float32]`` pre-view bidirectional error in square metres."""

    pm_dist_after: Tensor
    """``Tensor["N", float32]`` or ``Tensor["B N", float32]`` post-view bidirectional error in square metres."""

    pm_acc_before: Tensor
    """``Tensor["N", float32]`` or ``Tensor["B N", float32]`` pre-view point-to-mesh error in square metres."""

    pm_comp_before: Tensor
    """``Tensor["N", float32]`` or ``Tensor["B N", float32]`` pre-view mesh-to-point error in square metres."""

    pm_acc_after: Tensor
    """``Tensor["N", float32]`` or ``Tensor["B N", float32]`` post-view point-to-mesh error in square metres."""

    pm_comp_after: Tensor
    """``Tensor["N", float32]`` or ``Tensor["B N", float32]`` post-view mesh-to-point error in square metres."""

    scene_id: str | list[str]
    """Scene identifier or batched list of identifiers."""

    snippet_id: str | list[str]
    """Snippet identifier or batched list of identifiers."""

    p3d_cameras: PerspectiveCameras
    """Actor-visible calibration and world-to-view transforms aligned with candidates."""

    candidate_count: Tensor | None = None
    """``Tensor["", int64]`` or ``Tensor["B", int64]`` valid candidate-prefix lengths."""

    backbone_out: EvlBackboneOutput | None = None
    """Optional actor-visible EVL evidence tied to serialized source config.

    Offline manifests record resolved asset paths but no checkpoint-content
    hash, so callers must not treat this field as cryptographic provenance.
    """

    gt_obbs: CompactObbBlock | None = None
    """Optional ASE GT OBBs for label matching/evaluation, never actor-visible input."""

    detected_obbs: CompactObbBlock | None = None
    """Optional actor-visible EVL predicted/tracked OBB evidence."""

    trajectory: CompactTrajectoryBlock | None = None
    """Optional actor-visible MPS/EFM timing and world-frame gravity metadata."""

    def resolved_candidate_count(self, *, device: torch.device | None = None) -> Tensor:
        """Return clamped valid-prefix lengths as ``Tensor["", int64]`` or ``Tensor["B", int64]``."""

        poses = self.candidate_poses_world_cam.tensor()
        target_device = device or poses.device
        max_candidates = int(poses.shape[-2])
        counts = self.candidate_count
        if counts is None:
            if poses.ndim == 2:
                return torch.tensor(max_candidates, device=target_device, dtype=torch.int64)
            if poses.ndim == 3:
                return torch.full(
                    (int(poses.shape[0]),),
                    max_candidates,
                    device=target_device,
                    dtype=torch.int64,
                )
            raise ValueError("candidate_poses_world_cam must have shape (N,12) or (B,N,12).")

        counts = torch.as_tensor(counts, device=target_device, dtype=torch.int64)
        if poses.ndim == 2:
            if counts.numel() == 0:
                return torch.tensor(0, device=target_device, dtype=torch.int64)
            return counts.reshape(-1)[0].clamp(min=0, max=max_candidates)
        if poses.ndim != 3:
            raise ValueError("candidate_poses_world_cam must have shape (N,12) or (B,N,12).")

        batch_size = int(poses.shape[0])
        counts = counts.reshape(-1)
        if counts.numel() == 1:
            counts = counts.expand(batch_size)
        if counts.numel() != batch_size:
            raise ValueError(
                f"candidate_count must have 1 or {batch_size} elements, got {counts.numel()}.",
            )
        return counts.clamp(min=0, max=max_candidates)

    def candidate_valid_mask(self, *, device: torch.device | None = None) -> Tensor:
        """Return ``Tensor["N", bool]`` or ``Tensor["B N", bool]`` valid-prefix masks."""

        poses = self.candidate_poses_world_cam.tensor()
        counts = self.resolved_candidate_count(device=device)
        max_candidates = int(poses.shape[-2])
        arange = torch.arange(max_candidates, device=counts.device)
        if counts.ndim == 0:
            return arange < counts
        return arange.unsqueeze(0) < counts.unsqueeze(1)

    def shuffle_candidates(self, *, generator: torch.Generator | None = None) -> "VinOracleBatch":
        """Return a copy with candidate ordering randomly permuted.

        The permutation is applied consistently across candidate-specific fields:
        poses, oracle RRI targets, per-metric distances, and the corresponding
        PyTorch3D cameras. Non-candidate fields (snippet view, backbone outputs)
        are preserved.
        """
        poses = self.candidate_poses_world_cam.tensor()
        if poses.ndim == 2:
            batch_size = 1
            num_candidates = int(poses.shape[0])
            has_batch = False
        elif poses.ndim == 3:
            batch_size = int(poses.shape[0])
            num_candidates = int(poses.shape[1])
            has_batch = True
        else:
            raise ValueError("candidate_poses_world_cam must have shape (N,12) or (B,N,12).")

        counts = self.resolved_candidate_count(device=poses.device)
        if counts.ndim == 0:
            counts = counts.view(1)
        if num_candidates <= 1 or not torch.any(counts > 1):
            return self

        perm = torch.arange(num_candidates, device=poses.device).expand(batch_size, -1).clone()
        for row, count_tensor in enumerate(counts.tolist()):
            count = int(count_tensor)
            if count <= 1:
                continue
            perm[row, :count] = torch.randperm(count, device=poses.device, generator=generator)

        def _gather_candidate(data: Tensor) -> Tensor:
            if data.ndim == 2 and not has_batch:
                data_b = data.unsqueeze(0)
            elif data.ndim >= 2 and has_batch:
                data_b = data
            else:
                raise ValueError("Candidate tensors must have shape (N, ...) or (B, N, ...).")
            if data_b.shape[0] != batch_size or data_b.shape[1] != num_candidates:
                raise ValueError("Candidate tensor batch/length mismatch during shuffling.")
            expand_shape = (batch_size, num_candidates) + (1,) * (data_b.ndim - 2)
            index = perm.view(expand_shape).expand_as(data_b)
            gathered = torch.gather(data_b, dim=1, index=index)
            return gathered if has_batch else gathered.squeeze(0)

        def _gather_1d(values: Tensor) -> Tensor:
            if values.ndim == 1:
                data = values.unsqueeze(0)
                had_batch = False
            elif values.ndim == 2:
                data = values
                had_batch = True
            else:
                raise ValueError("Candidate labels must have shape (N,) or (B, N).")
            if data.shape[0] != batch_size or data.shape[1] != num_candidates:
                raise ValueError("Candidate label batch/length mismatch during shuffling.")
            gathered = torch.gather(data, dim=1, index=perm)
            return gathered if had_batch else gathered.squeeze(0)

        def _shuffle_camera_param(param: Tensor, *, name: str) -> Tensor:
            if param.shape[0] == 1:
                return param
            if param.shape[0] == num_candidates and batch_size == 1:
                data = param.unsqueeze(0)
                expand_shape = (batch_size, num_candidates) + (1,) * (data.ndim - 2)
                index = perm.view(expand_shape).expand_as(data)
                return torch.gather(data, dim=1, index=index).squeeze(0)
            if param.shape[0] == batch_size * num_candidates:
                data = param.reshape(batch_size, num_candidates, *param.shape[1:])
                expand_shape = (batch_size, num_candidates) + (1,) * (data.ndim - 2)
                index = perm.view(expand_shape).expand_as(data)
                gathered = torch.gather(data, dim=1, index=index)
                return gathered.reshape(batch_size * num_candidates, *param.shape[1:])
            raise ValueError(f"Camera param '{name}' has unsupported shape {tuple(param.shape)} for shuffling.")

        candidate_poses_world_cam = PoseTW(_gather_candidate(poses))
        rri = _gather_1d(self.rri)
        pm_dist_before = _gather_1d(self.pm_dist_before)
        pm_dist_after = _gather_1d(self.pm_dist_after)
        pm_acc_before = _gather_1d(self.pm_acc_before)
        pm_comp_before = _gather_1d(self.pm_comp_before)
        pm_acc_after = _gather_1d(self.pm_acc_after)
        pm_comp_after = _gather_1d(self.pm_comp_after)

        in_ndc = getattr(self.p3d_cameras, "in_ndc", False)
        if callable(in_ndc):
            in_ndc = in_ndc()
        znear = getattr(self.p3d_cameras, "znear", None)
        zfar = getattr(self.p3d_cameras, "zfar", None)
        cam_kwargs = {
            "device": self.p3d_cameras.R.device,
            "R": _shuffle_camera_param(self.p3d_cameras.R, name="R"),
            "T": _shuffle_camera_param(self.p3d_cameras.T, name="T"),
            "focal_length": _shuffle_camera_param(self.p3d_cameras.focal_length, name="focal_length"),
            "principal_point": _shuffle_camera_param(self.p3d_cameras.principal_point, name="principal_point"),
            "image_size": _shuffle_camera_param(self.p3d_cameras.image_size, name="image_size"),
            "in_ndc": bool(in_ndc),
        }
        if znear is not None:
            cam_kwargs["znear"] = znear
        if zfar is not None:
            cam_kwargs["zfar"] = zfar
        try:
            p3d_cameras = PerspectiveCameras(**cam_kwargs)
        except TypeError:
            cam_kwargs.pop("znear", None)
            cam_kwargs.pop("zfar", None)
            p3d_cameras = PerspectiveCameras(**cam_kwargs)
            if znear is not None:
                p3d_cameras.znear = znear
            if zfar is not None:
                p3d_cameras.zfar = zfar

        return VinOracleBatch(
            efm_snippet_view=self.efm_snippet_view,
            candidate_poses_world_cam=candidate_poses_world_cam,
            reference_pose_world_rig=self.reference_pose_world_rig,
            rri=rri,
            pm_dist_before=pm_dist_before,
            pm_dist_after=pm_dist_after,
            pm_acc_before=pm_acc_before,
            pm_comp_before=pm_comp_before,
            pm_acc_after=pm_acc_after,
            pm_comp_after=pm_comp_after,
            p3d_cameras=p3d_cameras,
            candidate_count=self.resolved_candidate_count(device=poses.device),
            scene_id=self.scene_id,
            snippet_id=self.snippet_id,
            backbone_out=self.backbone_out,
            gt_obbs=self.gt_obbs,
            detected_obbs=self.detected_obbs,
            trajectory=self.trajectory,
        )

    @classmethod
    def collate(cls, samples: list["VinOracleBatch"]) -> "VinOracleBatch":
        """Collate cached VIN batches by padding candidate sets to a shared length."""
        if not samples:
            raise ValueError("Empty batch passed to VinOracleBatch.collate.")

        snippet_views = [sample.efm_snippet_view for sample in samples]
        has_snippet = any(view is not None for view in snippet_views)
        if has_snippet:
            if any(view is None for view in snippet_views):
                raise ValueError(
                    "Mixed snippet views in batch; ensure include_efm_snippet is consistent.",
                )
            if not all(is_vin_snippet_view_instance(view) for view in snippet_views):
                raise NotImplementedError(
                    "Batching with full EfmSnippetView is not supported. Use VinSnippetView from the VIN offline store.",
                )

        candidate_widths = [int(sample.candidate_poses_world_cam.shape[-2]) for sample in samples]
        max_candidates = max(candidate_widths) if candidate_widths else 0
        if max_candidates <= 0:
            raise ValueError("Cannot batch empty candidate sets.")

        poses = torch.stack(
            [
                cls._pad_candidate_poses(sample.candidate_poses_world_cam, target_len=max_candidates)
                for sample in samples
            ],
            dim=0,
        )
        candidate_poses_world_cam = PoseTW(poses)

        reference_pose_world_rig = cls._stack_reference_poses(
            [sample.reference_pose_world_rig for sample in samples],
        )

        rri = torch.stack(
            [cls._pad_1d(sample.rri, target_len=max_candidates, pad_value=float("nan")) for sample in samples],
            dim=0,
        )
        pm_dist_before = torch.stack(
            [
                cls._pad_1d(sample.pm_dist_before, target_len=max_candidates, pad_value=float("nan"))
                for sample in samples
            ],
            dim=0,
        )
        pm_dist_after = torch.stack(
            [
                cls._pad_1d(sample.pm_dist_after, target_len=max_candidates, pad_value=float("nan"))
                for sample in samples
            ],
            dim=0,
        )
        pm_acc_before = torch.stack(
            [
                cls._pad_1d(sample.pm_acc_before, target_len=max_candidates, pad_value=float("nan"))
                for sample in samples
            ],
            dim=0,
        )
        pm_comp_before = torch.stack(
            [
                cls._pad_1d(sample.pm_comp_before, target_len=max_candidates, pad_value=float("nan"))
                for sample in samples
            ],
            dim=0,
        )
        pm_acc_after = torch.stack(
            [cls._pad_1d(sample.pm_acc_after, target_len=max_candidates, pad_value=float("nan")) for sample in samples],
            dim=0,
        )
        pm_comp_after = torch.stack(
            [
                cls._pad_1d(sample.pm_comp_after, target_len=max_candidates, pad_value=float("nan"))
                for sample in samples
            ],
            dim=0,
        )

        p3d_cameras = cls._stack_p3d_cameras(
            [sample.p3d_cameras for sample in samples],
            target_len=max_candidates,
        )

        scene_id = [sample.scene_id for sample in samples]
        snippet_id = [sample.snippet_id for sample in samples]

        backbone_out = None
        if any(sample.backbone_out is not None for sample in samples):
            if any(sample.backbone_out is None for sample in samples):
                raise ValueError("Cannot batch backbone outputs when some entries are missing.")
            backbone_out = cls._stack_backbone_outputs(
                [sample.backbone_out for sample in samples if sample.backbone_out is not None],
            )
        gt_obbs = cls._stack_optional_obbs([sample.gt_obbs for sample in samples], name="gt_obbs")
        detected_obbs = cls._stack_optional_obbs(
            [sample.detected_obbs for sample in samples],
            name="detected_obbs",
        )
        trajectory = cls._stack_optional_trajectory([sample.trajectory for sample in samples])
        vin_snippet = None
        if has_snippet:
            points_list = [view.points_world for view in snippet_views if view is not None]
            lengths_list = [view.lengths for view in snippet_views if view is not None]
            traj_list = [view.t_world_rig for view in snippet_views if view is not None]
            max_points = max(int(points.shape[0]) for points in points_list)
            max_frames = max(int(traj.shape[0]) for traj in traj_list)
            points_world = torch.stack(
                [cls._pad_points(points, target_len=max_points) for points in points_list],
                dim=0,
            )
            lengths = torch.stack(
                [
                    length.reshape(-1)[0]
                    if length.numel() > 0
                    else torch.tensor(0, device=points_world.device, dtype=torch.int64)
                    for length in lengths_list
                ],
                dim=0,
            ).to(device=points_world.device, dtype=torch.int64)
            t_world_rig = PoseTW(
                torch.stack(
                    [cls._pad_trajectory(traj, target_len=max_frames) for traj in traj_list],
                    dim=0,
                ),
            )
            vin_snippet = VinSnippetView(points_world=points_world, lengths=lengths, t_world_rig=t_world_rig)

        candidate_count = torch.stack(
            [
                sample.resolved_candidate_count(device=candidate_poses_world_cam.tensor().device).reshape(())
                for sample in samples
            ],
            dim=0,
        ).to(device=candidate_poses_world_cam.tensor().device, dtype=torch.int64)

        return cls(
            efm_snippet_view=vin_snippet,
            candidate_poses_world_cam=candidate_poses_world_cam,
            reference_pose_world_rig=reference_pose_world_rig,
            rri=rri,
            pm_dist_before=pm_dist_before,
            pm_dist_after=pm_dist_after,
            pm_acc_before=pm_acc_before,
            pm_comp_before=pm_comp_before,
            pm_acc_after=pm_acc_after,
            pm_comp_after=pm_comp_after,
            p3d_cameras=p3d_cameras,
            candidate_count=candidate_count,
            scene_id=scene_id,
            snippet_id=snippet_id,
            backbone_out=backbone_out,
            gt_obbs=gt_obbs,
            detected_obbs=detected_obbs,
            trajectory=trajectory,
        )

    @staticmethod
    def _pad_candidate_poses(poses: PoseTW, *, target_len: int) -> Tensor:
        """Pad or truncate candidate-pose tensors to ``target_len``."""
        data = poses.tensor()
        if data.ndim == 1:
            data = data.unsqueeze(0)
        if data.shape[-1] != 12:
            raise ValueError("candidate_poses_world_cam must have shape (N,12).")
        num = int(data.shape[0])
        if num == target_len:
            return data
        if num == 0:
            pad = PoseTW().tensor().expand(target_len, -1)
            return pad
        if num > target_len:
            return data[:target_len]
        pad = data[-1:].expand(target_len - num, -1).clone()
        return torch.cat([data, pad], dim=0)

    @staticmethod
    def _pad_points(points: Tensor, *, target_len: int) -> Tensor:
        """Pad or truncate a VIN point tensor to ``target_len`` rows."""
        if points.ndim == 3 and points.shape[0] == 1:
            points = points.squeeze(0)
        if points.ndim != 2:
            raise ValueError("points_world must have shape (K, D).")
        num = int(points.shape[0])
        if num == target_len:
            return points
        if num > target_len:
            return points[:target_len]
        pad = torch.full(
            (target_len - num, points.shape[1]),
            float("nan"),
            dtype=points.dtype,
            device=points.device,
        )
        return torch.cat([points, pad], dim=0)

    @staticmethod
    def _pad_trajectory(poses: PoseTW, *, target_len: int) -> Tensor:
        """Pad or truncate trajectory poses to ``target_len`` frames."""
        data = poses.tensor()
        if data.ndim == 3 and data.shape[0] == 1:
            data = data.squeeze(0)
        if data.ndim != 2 or data.shape[-1] != 12:
            raise ValueError("t_world_rig must have shape (F,12).")
        num = int(data.shape[0])
        if num == target_len:
            return data
        if num == 0:
            pad = PoseTW().tensor().expand(target_len, -1)
            return pad
        if num > target_len:
            return data[:target_len]
        pad = data[-1:].expand(target_len - num, -1).clone()
        return torch.cat([data, pad], dim=0)

    @staticmethod
    def _pad_1d(values: Tensor, *, target_len: int, pad_value: float) -> Tensor:
        """Pad or truncate a one-dimensional candidate field."""
        flat = values.reshape(-1)
        num = int(flat.shape[0])
        if num == target_len:
            return flat
        if num > target_len:
            return flat[:target_len]
        pad = torch.full(
            (target_len - num,),
            pad_value,
            dtype=flat.dtype,
            device=flat.device,
        )
        return torch.cat([flat, pad], dim=0)

    @staticmethod
    def _stack_reference_poses(poses: list[PoseTW]) -> PoseTW:
        """Stack reference poses into a batched ``PoseTW`` tensor."""
        tensors = []
        for pose in poses:
            data = pose.tensor()
            if data.ndim == 2:
                if data.shape[0] != 1:
                    raise ValueError("reference_pose_world_rig must have shape (12,) or (1,12).")
                data = data.squeeze(0)
            if data.ndim != 1:
                raise ValueError("reference_pose_world_rig must have shape (12,) or (1,12).")
            tensors.append(data)
        return PoseTW(torch.stack(tensors, dim=0))

    @staticmethod
    def _expand_camera_param(param: Tensor, *, target_len: int, name: str) -> Tensor:
        """Broadcast singleton camera parameters to the requested length."""
        if param.shape[0] == target_len:
            return param
        if param.shape[0] == 1:
            return param.expand(target_len, *param.shape[1:])
        raise ValueError(f"{name} batch size {param.shape[0]} does not match target_len={target_len}.")

    @staticmethod
    def _pad_camera_param(param: Tensor, *, target_len: int) -> Tensor:
        """Pad or truncate a camera parameter tensor to ``target_len`` rows."""
        if param.shape[0] == target_len:
            return param
        if param.shape[0] > target_len:
            return param[:target_len]
        pad = param[-1:].expand(target_len - param.shape[0], *param.shape[1:]).clone()
        return torch.cat([param, pad], dim=0)

    @classmethod
    def _stack_p3d_cameras(
        cls,
        cameras: list[PerspectiveCameras],
        *,
        target_len: int,
    ) -> PerspectiveCameras:
        """Stack padded per-sample camera batches into one flat batch."""
        if not cameras:
            raise ValueError("No cameras provided for collation.")

        in_ndc = getattr(cameras[0], "in_ndc", False)
        if callable(in_ndc):
            in_ndc = in_ndc()

        znear = getattr(cameras[0], "znear", None)
        zfar = getattr(cameras[0], "zfar", None)
        for cam in cameras[1:]:
            cam_in_ndc = getattr(cam, "in_ndc", False)
            if callable(cam_in_ndc):
                cam_in_ndc = cam_in_ndc()
            if bool(cam_in_ndc) != bool(in_ndc):
                raise ValueError("All PerspectiveCameras must agree on in_ndc for batching.")

        r_list: list[Tensor] = []
        t_list: list[Tensor] = []
        f_list: list[Tensor] = []
        pp_list: list[Tensor] = []
        im_list: list[Tensor] = []
        for cam in cameras:
            num = int(cam.R.shape[0])
            rot = cam.R
            trans = cam.T
            focal = cls._expand_camera_param(cam.focal_length, target_len=num, name="focal_length")
            principal = cls._expand_camera_param(cam.principal_point, target_len=num, name="principal_point")
            image_size = cls._expand_camera_param(cam.image_size, target_len=num, name="image_size")

            rot = cls._pad_camera_param(rot, target_len=target_len)
            trans = cls._pad_camera_param(trans, target_len=target_len)
            focal = cls._pad_camera_param(focal, target_len=target_len)
            principal = cls._pad_camera_param(principal, target_len=target_len)
            image_size = cls._pad_camera_param(image_size, target_len=target_len)

            r_list.append(rot)
            t_list.append(trans)
            f_list.append(focal)
            pp_list.append(principal)
            im_list.append(image_size)

        rot_all = torch.cat(r_list, dim=0)
        trans_all = torch.cat(t_list, dim=0)
        focal_all = torch.cat(f_list, dim=0)
        principal_all = torch.cat(pp_list, dim=0)
        image_all = torch.cat(im_list, dim=0)

        kwargs = {
            "device": rot_all.device,
            "R": rot_all,
            "T": trans_all,
            "focal_length": focal_all,
            "principal_point": principal_all,
            "image_size": image_all,
            "in_ndc": bool(in_ndc),
        }
        if znear is not None:
            kwargs["znear"] = znear
        if zfar is not None:
            kwargs["zfar"] = zfar
        try:
            return PerspectiveCameras(**kwargs)
        except TypeError:
            kwargs.pop("znear", None)
            kwargs.pop("zfar", None)
            cameras_out = PerspectiveCameras(**kwargs)
            if znear is not None:
                cameras_out.znear = znear
            if zfar is not None:
                cameras_out.zfar = zfar
            return cameras_out

    @classmethod
    def _stack_tensor_field(cls, values: list[Tensor | None], *, name: str) -> Tensor | None:
        """Stack a homogeneous optional tensor field across the batch."""
        if all(value is None for value in values):
            return None
        if any(value is None for value in values):
            raise ValueError(f"Cannot batch backbone field '{name}': missing values.")
        tensors = [value for value in values if value is not None]
        first = tensors[0]
        for tensor in tensors[1:]:
            if tensor.shape != first.shape:
                raise ValueError(f"Cannot batch backbone field '{name}': mismatched shapes.")
        if first.ndim > 1 and first.shape[0] == 1:
            return torch.cat(tensors, dim=0)
        return torch.stack(tensors, dim=0)

    @classmethod
    def _stack_tensor_dict(
        cls,
        values: list[dict[str, Tensor]],
        *,
        name: str,
    ) -> dict[str, Tensor]:
        """Stack a dictionary of tensor fields across the batch."""
        if all(len(value) == 0 for value in values):
            return {}
        keys = set(values[0].keys())
        for value in values[1:]:
            if set(value.keys()) != keys:
                raise ValueError(f"Cannot batch backbone field '{name}': mismatched dict keys.")
        stacked: dict[str, Tensor] = {}
        for key in keys:
            field = cls._stack_tensor_field([value[key] for value in values], name=f"{name}.{key}")
            if field is None:
                raise ValueError(f"Cannot batch backbone field '{name}.{key}': missing values.")
            stacked[key] = field
        return stacked

    @classmethod
    def _stack_optional_obbs(cls, values: list[CompactObbBlock | None], *, name: str) -> CompactObbBlock | None:
        """Stack compact numeric OBB payloads."""

        if all(value is None for value in values):
            return None
        if any(value is None for value in values):
            raise ValueError(f"Cannot batch {name}: missing values.")
        blocks = [value for value in values if value is not None]
        sem_names = [block.sem_id_to_name for block in blocks]
        if any(item is not None for item in sem_names):
            if any(item != sem_names[0] for item in sem_names[1:]):
                raise ValueError(f"{name}.sem_id_to_name must match across batch.")
            sem_id_to_name = sem_names[0]
        else:
            sem_id_to_name = None
        obbs = cls._stack_tensor_field([block.obbs for block in blocks], name=f"{name}.obbs")
        if obbs is None:
            raise ValueError(f"Cannot batch {name}: missing OBB tensor.")
        return CompactObbBlock(
            obbs=obbs,
            sem_id_to_name=sem_id_to_name,
            probs=cls._stack_tensor_field([block.probs for block in blocks], name=f"{name}.probs"),
        )

    @classmethod
    def _stack_optional_trajectory(
        cls,
        values: list[CompactTrajectoryBlock | None],
    ) -> CompactTrajectoryBlock | None:
        """Stack optional trajectory metadata."""

        if all(value is None for value in values):
            return None
        if any(value is None for value in values):
            raise ValueError("Cannot batch trajectory metadata: missing values.")
        trajectories = [value for value in values if value is not None]
        return CompactTrajectoryBlock(
            time_ns=cls._stack_tensor_field([item.time_ns for item in trajectories], name="trajectory.time_ns"),
            gravity_in_world=cls._stack_tensor_field(
                [item.gravity_in_world for item in trajectories],
                name="trajectory.gravity_in_world",
            ),
        )

    @classmethod
    def _stack_backbone_outputs(cls, outputs: list[EvlBackboneOutput]) -> EvlBackboneOutput:
        """Stack compatible cached backbone outputs across the batch."""
        if any(output is None for output in outputs):
            raise ValueError("Cannot batch backbone outputs when some entries are missing.")

        t_world_voxel = cls._stack_reference_poses([output.t_world_voxel for output in outputs])
        voxel_extent = cls._stack_tensor_field([output.voxel_extent for output in outputs], name="voxel_extent")
        if voxel_extent is None:
            raise ValueError("voxel_extent is required for VIN batching.")

        obb_fields = [
            ("obbs_pr_nms", [output.obbs_pr_nms for output in outputs]),
            ("obb_pred", [output.obb_pred for output in outputs]),
            ("obb_pred_viz", [output.obb_pred_viz for output in outputs]),
        ]
        for field_name, obb_values in obb_fields:
            if any(value is not None for value in obb_values):
                raise NotImplementedError(
                    f"Batching backbone field '{field_name}' is not supported yet. "
                    "Disable OBB outputs or set batch_size=None.",
                )

        list_fields = [
            ("obb_pred_probs_full", [output.obb_pred_probs_full for output in outputs]),
            ("obb_pred_probs_full_viz", [output.obb_pred_probs_full_viz for output in outputs]),
        ]
        for field_name, probability_values in list_fields:
            if any(value is not None for value in probability_values):
                raise NotImplementedError(
                    f"Batching backbone field '{field_name}' is not supported yet. "
                    "Disable OBB outputs or set batch_size=None.",
                )

        name_lists = [output.obb_pred_sem_id_to_name for output in outputs]
        if any(name is not None for name in name_lists):
            if any(name != name_lists[0] for name in name_lists[1:]):
                raise ValueError("obb_pred_sem_id_to_name must match across batch.")
            obb_pred_sem_id_to_name = name_lists[0]
        else:
            obb_pred_sem_id_to_name = None

        feat2d = cls._stack_tensor_dict([output.feat2d_upsampled for output in outputs], name="feat2d_upsampled")
        token2d = cls._stack_tensor_dict([output.token2d for output in outputs], name="token2d")

        return EvlBackboneOutput(
            t_world_voxel=t_world_voxel,
            voxel_extent=voxel_extent,
            voxel_feat=cls._stack_tensor_field([output.voxel_feat for output in outputs], name="voxel_feat"),
            occ_feat=cls._stack_tensor_field([output.occ_feat for output in outputs], name="occ_feat"),
            obb_feat=cls._stack_tensor_field([output.obb_feat for output in outputs], name="obb_feat"),
            occ_pr=cls._stack_tensor_field([output.occ_pr for output in outputs], name="occ_pr"),
            occ_input=cls._stack_tensor_field([output.occ_input for output in outputs], name="occ_input"),
            free_input=cls._stack_tensor_field([output.free_input for output in outputs], name="free_input"),
            counts=cls._stack_tensor_field([output.counts for output in outputs], name="counts"),
            counts_m=cls._stack_tensor_field([output.counts_m for output in outputs], name="counts_m"),
            voxel_select_t=cls._stack_tensor_field(
                [output.voxel_select_t for output in outputs], name="voxel_select_t"
            ),
            cent_pr=cls._stack_tensor_field([output.cent_pr for output in outputs], name="cent_pr"),
            bbox_pr=cls._stack_tensor_field([output.bbox_pr for output in outputs], name="bbox_pr"),
            clas_pr=cls._stack_tensor_field([output.clas_pr for output in outputs], name="clas_pr"),
            cent_pr_nms=cls._stack_tensor_field([output.cent_pr_nms for output in outputs], name="cent_pr_nms"),
            obbs_pr_nms=None,
            obb_pred=None,
            obb_pred_viz=None,
            obb_pred_sem_id_to_name=obb_pred_sem_id_to_name,
            obb_pred_probs_full=None,
            obb_pred_probs_full_viz=None,
            pts_world=cls._stack_tensor_field([output.pts_world for output in outputs], name="pts_world"),
            feat2d_upsampled=feat2d,
            token2d=token2d,
        )


@runtime_checkable
class VinOracleDatasetBase(Protocol):
    """Shared interface for datasets that yield `VinOracleBatch`."""

    is_map_style: bool
    """Whether the dataset is map-style (supports random access + batching)."""

    def __iter__(self) -> Iterator[VinOracleBatch]:
        """Iterate over VIN oracle batches."""


__all__ = [
    "CompactObbBlock",
    "CompactTrajectoryBlock",
    "VinOracleBatch",
    "VinOracleDatasetBase",
]
