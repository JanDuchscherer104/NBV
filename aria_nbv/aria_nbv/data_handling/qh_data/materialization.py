r"""Typed rollout and VIN materialization for finite-candidate Q_H chains.

This internal module converts validated reader-owned NumPy payloads and VIN
evidence into frame-aware Q_H views. Dataset selection, source-identity joins,
and stage admission remain outside this owner.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import torch
from efm3d.aria.camera import CameraTW
from efm3d.aria.pose import PoseTW
from torch import Tensor

from ..vin_store.format import VinOfflineIndexRecord
from ..vin_store.store import VinOfflineStoreReader
from ..vin_store.views import VinSnippetView
from .batching import _gather_candidates, _pad
from .views import (
    QhActorTensors,
    QhAudit,
    QhChain,
    QhChainKey,
    QhSelectedObservationPrefix,
    QhSelectedObservationProtocol,
    QhStaticContext,
    QhSupervision,
)

if TYPE_CHECKING:
    from ...rollouts.qh_reader import _StoredChain


def _tensor_chain(
    stored: _StoredChain,
    snippet: VinSnippetView,
    *,
    static_context: QhStaticContext | None = None,
    selected_observation_protocol: QhSelectedObservationProtocol = "none",
    audit: QhAudit | None = None,
) -> QhChain:
    """Tensorize one stored chain and construct strictly causal selected-pose history.

    Candidate rows retain stored widths before batch collation.
    ``candidate_mask`` records materialization, ``action_mask`` is its
    actor-valid subset, and ``label_mask`` is the label-supported subset of
    actor validity. Selected indices are factual rollout-policy actions. At
    state ``s``, history slots ``0`` through ``s-1`` contain those earlier
    selected poses in chronological order and every slot from ``s`` onward is
    masked out. Stored remaining budget, TD discount, and terminal state are
    copied without learner-specific reinterpretation.

    Args:
        stored: Complete CPU/NumPy rollout chain with ``S`` states and
            variable candidate-row widths.
        snippet: Chain-constant immutable VIN actor observation.

    Returns:
        :class:`QhChain` with float32 pose/reward tensors, int64 action/budget
        tensors, bool support/terminal tensors, and strict causal history.
    """

    candidate_pose_tensor = _stack_rows(stored.candidate_pose_relative_root, 0, torch.float32)
    candidate_pose = PoseTW(candidate_pose_tensor)
    action_mask = _stack_rows(stored.action_mask, False, torch.bool)
    label_mask = _stack_rows(stored.label_mask, False, torch.bool)
    reward = _stack_rows(stored.candidate_reward, 0, torch.float32)
    target_rri = _stack_rows(stored.one_step_target_rri, float("nan"), torch.float32)
    target_rri = torch.where(label_mask, target_rri, torch.full_like(target_rri, float("nan")))
    selected = _from_numpy(stored.selected_index, torch.int64)
    steps, width = action_mask.shape
    _validate_selected_indices(stored, selected)
    candidate_mask = torch.zeros((steps, width), dtype=torch.bool)
    for row, values in enumerate(stored.candidate_pose_relative_root):
        candidate_mask[row, : values.shape[0]] = True
    if bool((label_mask & ~action_mask).any() or (action_mask & ~candidate_mask).any()):
        raise ValueError("Q_H masks must satisfy label_mask <= action_mask <= candidate_mask.")
    history_pose = torch.zeros((steps, steps, 12), dtype=torch.float32)
    history_mask = torch.zeros((steps, steps), dtype=torch.bool)
    selected_pose = _gather_candidates(candidate_pose_tensor, selected)
    for step in range(1, steps):
        history_pose[step, :step] = selected_pose[:step]
        history_mask[step, :step] = True
    root_pose = PoseTW(_from_numpy(stored.root_pose_world, torch.float32))
    target_pose = PoseTW(_from_numpy(stored.target_pose_world_object, torch.float32))
    history_pose_tw = PoseTW(history_pose)
    selected_observation_prefix = (
        _selected_observation_prefix(stored, history_pose_tw, history_mask)
        if selected_observation_protocol == "cf_gt"
        else None
    )
    if selected_observation_protocol == "cf_gt" and selected_observation_prefix is None:
        raise ValueError(
            "Q_H cf_gt selected-observation protocol requires aligned rendered depth; rebuild the rollout store with selected depth enabled."
        )
    return QhChain(
        actor=QhActorTensors(
            vin_snippet=snippet,
            root_pose_world=root_pose,
            target_pose_relative_root=root_pose.inverse().compose(target_pose),
            target_extents=_from_numpy(stored.target_extents, torch.float32),
            candidate_pose_relative_root=candidate_pose,
            candidate_mask=candidate_mask,
            action_mask=action_mask,
            history_pose_relative_root=history_pose_tw,
            history_mask=history_mask,
            horizon_remaining=_from_numpy(stored.horizon_remaining, torch.int64),
            step_mask=torch.ones(steps, dtype=torch.bool),
            static_context=static_context,
            selected_observation_prefix=selected_observation_prefix,
        ),
        supervision=QhSupervision(
            label_mask=label_mask,
            candidate_reward=reward,
            one_step_target_rri=target_rri,
            selected_index=selected,
            discount=_from_numpy(stored.discount, torch.float32),
            terminal=_from_numpy(stored.terminal, torch.bool),
        ),
        key=QhChainKey(
            store_index=stored.store_index,
            rollout_row_id=stored.rollout_row_id,
            source_sample_index=stored.source_ref.source_sample_index,
            scene_id=stored.source_ref.scene_id,
            target_row_id=stored.target_row_id,
            configured_horizon=stored.configured_horizon,
            candidate_width_min=stored.candidate_width_min,
            candidate_width_max=stored.candidate_width_max,
            candidate_config_hash=stored.candidate_config_hash,
            rollout_config_hash=stored.rollout_config_hash,
            selection_policy=stored.selection_policy,
        ),
        audit=audit,
    )


def _validate_selected_indices(stored: _StoredChain, selected: Tensor) -> None:
    """Reject factual selected ordinals before any pose or modality gather."""

    factual_widths = torch.tensor([len(row) for row in stored.candidate_pose_relative_root], dtype=selected.dtype)
    invalid = selected.lt(0) | selected.ge(factual_widths)
    if not bool(invalid.any()):
        return
    step = int(torch.nonzero(invalid, as_tuple=False)[0].item())
    value = int(selected[step])
    factual_width = len(stored.candidate_pose_relative_root[step])
    raise ValueError(
        "Q_H factual selected candidate index is out of range: "
        f"store_index={stored.store_index}, rollout_row_id={stored.rollout_row_id}, "
        f"step={step}, selected_index={value}, candidate_width={factual_width}."
    )


def _read_static_context(
    actor_reader: VinOfflineStoreReader,
    record: VinOfflineIndexRecord,
    snippet: VinSnippetView,
) -> QhStaticContext | None:
    """Read root EVL evidence through the VIN-store owner when materialized."""

    backbone = actor_reader.read_backbone_evidence(record, device="cpu")
    if backbone is None:
        return None
    names = (
        "backbone.t_world_voxel",
        "backbone.voxel_extent",
        "backbone.occ_pr",
        "backbone.occ_input",
        "backbone.free_input",
        "backbone.counts",
        "backbone.cent_pr",
        "backbone.pts_world",
    )
    raw_values = (
        backbone.t_world_voxel.tensor(),
        backbone.voxel_extent,
        backbone.occ_pr,
        backbone.occ_input,
        backbone.free_input,
        backbone.counts,
        backbone.cent_pr,
        backbone.pts_world,
    )
    values = tuple(
        None if value is None else _canonical_evl_tensor(name, value)
        for name, value in zip(names, raw_values, strict=True)
    )
    _validate_evl_geometry(names, values)
    return QhStaticContext(
        vin_snippet=snippet,
        t_world_voxel=None if values[0] is None else PoseTW(values[0]),
        voxel_extent=values[1],
        occ_pr=values[2],
        occ_input=values[3],
        free_input=values[4],
        counts=values[5],
        cent_pr=values[6],
        pts_world=values[7],
        evl_presence=torch.tensor([value is not None for value in values], dtype=torch.bool),
    )


def _selected_observation_prefix(
    stored: _StoredChain,
    history_pose: PoseTW,
    history_mask: Tensor,
) -> QhSelectedObservationPrefix | None:
    """Materialize a no-future-observation CF-GT prefix for each chain state."""

    payload = (
        stored.selected_depth_m,
        stored.selected_depth_valid_mask,
        stored.selected_depth_focal_px,
        stored.selected_depth_principal_point_px,
        stored.selected_depth_image_size_hw,
    )
    if all(value is None for value in payload):
        return None
    if any(value is None for value in payload):
        raise ValueError("Q_H selected CF-GT depth payload is incomplete; rebuild the rollout store.")
    depth, valid, focal, principal, image_size = payload
    assert isinstance(depth, np.ndarray)
    assert isinstance(valid, np.ndarray)
    assert isinstance(focal, np.ndarray)
    assert isinstance(principal, np.ndarray)
    assert isinstance(image_size, np.ndarray)
    if stored.selected_depth_renderer != "Pytorch3DDepthRenderer":
        raise ValueError("Q_H selected observation must retain CF-GT Pytorch3D renderer provenance.")
    steps, height, width = depth.shape
    prefix_depth = torch.zeros((steps, steps, height, width), dtype=torch.float16)
    prefix_valid = torch.zeros((steps, steps, height, width), dtype=torch.bool)
    cameras = _linear_camera_rows(focal, principal, image_size)
    prefix_camera = torch.zeros((steps, steps, cameras.tensor().shape[-1]), dtype=torch.float32)
    for state in range(1, steps):
        prefix_depth[state, :state] = _from_numpy(depth[:state], torch.float16)
        prefix_valid[state, :state] = _from_numpy(valid[:state], torch.bool)
        prefix_camera[state, :state] = cameras.tensor()[:state]
    return QhSelectedObservationPrefix(
        depth_m=prefix_depth,
        valid_mask=prefix_valid,
        camera=CameraTW(prefix_camera),
        camera_pose_relative_root=history_pose,
        prefix_mask=history_mask,
    )


def _linear_camera_rows(focal: np.ndarray, principal: np.ndarray, image_size_hw: np.ndarray) -> CameraTW:
    """Reconstruct linear cameras from persisted post-resize pinhole calibration rows."""

    if focal.shape != principal.shape or focal.ndim != 2 or focal.shape[1] != 2:
        raise ValueError("Q_H selected-depth focal and principal-point rows must both have shape (S,2).")
    if image_size_hw.shape != focal.shape:
        raise ValueError("Q_H selected-depth raster rows must align with focal and principal-point rows.")
    focal_tensor = _from_numpy(focal, torch.float32)
    principal_tensor = _from_numpy(principal, torch.float32)
    size_tensor = _from_numpy(image_size_hw, torch.float32)
    rows = int(focal.shape[0])
    zeros = torch.zeros((rows, 1), dtype=torch.float32)
    return CameraTW.from_parameters(
        width=size_tensor[:, 1:2],
        height=size_tensor[:, 0:1],
        fx=focal_tensor[:, 0:1],
        fy=focal_tensor[:, 1:2],
        cx=principal_tensor[:, 0:1],
        cy=principal_tensor[:, 1:2],
        gain=zeros,
        exposure_s=zeros,
        valid_radiusx=size_tensor[:, 1:2],
        valid_radiusy=size_tensor[:, 0:1],
        T_camera_rig=PoseTW().tensor().reshape(1, 12).expand(rows, -1),
        dist_params=torch.empty((rows, 0), dtype=torch.float32),
    )


def _audit_for(stored: _StoredChain, store_dir: Path) -> QhAudit:
    """Build CPU-only source and selected-depth provenance for explicit diagnostics."""

    return QhAudit(
        rollout_store_dir=str(store_dir),
        actor_store_version=stored.source_ref.actor_store_version,
        source_manifest_hash=stored.source_ref.source_manifest_hash,
        selected_depth_renderer=stored.selected_depth_renderer,
    )


_EVL_CANONICAL_RANKS = {
    "backbone.t_world_voxel": 1,
    "backbone.voxel_extent": 1,
    "backbone.occ_pr": 4,
    "backbone.occ_input": 4,
    "backbone.free_input": 4,
    "backbone.counts": 3,
    "backbone.cent_pr": 4,
    "backbone.pts_world": 2,
}


def _canonical_evl_shape(name: str, shape: tuple[int, ...]) -> tuple[int, ...]:
    """Remove only the optional singleton source axis and validate one EVL field shape."""

    expected_rank = _EVL_CANONICAL_RANKS[name]
    if len(shape) == expected_rank + 1:
        if shape[0] != 1:
            raise ValueError(f"Q_H {name} source batch axis must have size 1, got {shape}.")
        shape = shape[1:]
    if len(shape) != expected_rank or any(size < 1 for size in shape):
        raise ValueError(f"Q_H {name} has invalid canonical shape {shape}.")
    if name == "backbone.t_world_voxel" and shape != (12,):
        raise ValueError(f"Q_H {name} must end in the 12-value PoseTW layout, got {shape}.")
    if name == "backbone.voxel_extent" and shape != (6,):
        raise ValueError(f"Q_H {name} must contain six metric bounds, got {shape}.")
    if name in {"backbone.occ_pr", "backbone.occ_input", "backbone.free_input", "backbone.cent_pr"} and shape[0] != 1:
        raise ValueError(f"Q_H {name} must have one channel, got {shape}.")
    if name == "backbone.pts_world" and shape[-1] != 3:
        raise ValueError(f"Q_H {name} must contain XYZ points, got {shape}.")
    return shape


def _canonical_evl_tensor(name: str, value: Tensor) -> Tensor:
    """Return one canonical unbatched EVL tensor without squeezing semantic axes."""

    shape = tuple(value.shape)
    canonical = _canonical_evl_shape(name, shape)
    return value[0] if len(shape) == len(canonical) + 1 else value


def _validate_evl_geometry(names: tuple[str, ...], values: tuple[Tensor | None, ...]) -> None:
    """Require all available EVL grids and flattened centres to describe one voxel lattice."""

    fields = dict(zip(names, values, strict=True))
    spatial = {
        tuple(value.shape[-3:])
        for name, value in fields.items()
        if value is not None and name not in {"backbone.t_world_voxel", "backbone.voxel_extent", "backbone.pts_world"}
    }
    if len(spatial) > 1:
        raise ValueError(f"Q_H root EVL fields have incompatible voxel-grid shapes: {sorted(spatial)}.")
    points = fields["backbone.pts_world"]
    if spatial and points is not None:
        grid = next(iter(spatial))
        expected_points = int(np.prod(grid))
        if points.shape[0] != expected_points:
            raise ValueError(
                f"Q_H backbone.pts_world has {points.shape[0]} centres for voxel grid {grid} ({expected_points} expected)."
            )


def _evl_block_signature(actor_reader: VinOfflineStoreReader) -> tuple[tuple[str, str, tuple[int, ...]], ...]:
    """Build a canonical EVL shape/dtype signature from immutable shard metadata."""

    observed: dict[str, set[tuple[str, tuple[int, ...]]]] = {name: set() for name in _EVL_CANONICAL_RANKS}
    for shard in actor_reader.manifest.shards:
        for name in observed:
            spec = shard.blocks.get(name)
            if spec is None:
                raise ValueError(f"Q_H actor-store shard {shard.shard_id!r} is missing required EVL block {name!r}.")
            if spec.dtype is None or spec.shape is None or len(spec.shape) < 2:
                raise ValueError(f"Q_H {name} requires numeric shard shape and dtype metadata.")
            row_shape = _canonical_evl_shape(name, tuple(int(size) for size in spec.shape[1:]))
            observed[name].add((str(spec.dtype), row_shape))
    conflicting = {name: facts for name, facts in observed.items() if len(facts) > 1}
    if conflicting:
        raise ValueError(f"Q_H actor store has heterogeneous EVL block contracts: {conflicting}.")
    return tuple((name, dtype, shape) for name in sorted(observed) for dtype, shape in sorted(observed[name]))


def _from_numpy(value: np.ndarray, dtype: torch.dtype) -> Tensor:
    """Copy a NumPy array into an owned CPU tensor with the requested dtype.

    Args:
        value: NumPy payload whose shape is preserved.
        dtype: Destination PyTorch dtype required by the Q_H DTO contract.

    Returns:
        Owned CPU tensor that cannot alias rollout-reader NumPy storage.
    """

    return torch.from_numpy(np.array(value, copy=True)).to(dtype=dtype)


def _stack_rows(values: tuple[np.ndarray, ...], fill: int | float | bool, dtype: torch.dtype) -> Tensor:
    """Copy and pad variable-width NumPy rows into one owned tensor.

    Args:
        values: Non-empty tuple with common rank and variable leading width.
        fill: Padding value for the variable width.
        dtype: Destination dtype.

    Returns:
        Tensor with leading state axis and the maximum stored candidate width.
    """

    if not values:
        raise ValueError("Cannot stack empty Q_H rows.")
    return _pad([_from_numpy(value, dtype) for value in values], fill)


__all__: list[str] = []
