"""Prepared-row and shard codecs for immutable VIN offline datasets.

This module owns the normalized rows and immutable shard writes used by the VIN
offline dataset. It provides:

- ``PreparedVinOfflineSample`` as the normalized in-memory row representation,
- helpers for turning oracle-label outputs into fixed numeric blocks plus
  optional lazy diagnostic record blocks, and
- shard flushing helpers reused by tests and alternate builders.

The writer stores training-critical tensors as fixed-size NumPy arrays for
Zarr-backed random access. Rich per-row msgspec records are opt-in diagnostics
because the numeric blocks are the canonical offline training contract.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import numpy as np
import torch
from efm3d.aria.aria_constants import ARIA_OBB_SEM_ID_TO_NAME

from ...utils.semantic_names import normalize_semantic_name_map
from ...vin.types import validate_free_input_provenance
from ..ase_efm.views import EfmSnippetView
from ..identifiers import compact_ase_atek_sample_id
from .format import (
    VinOfflineIndexRecord,
    VinOfflineShardSpec,
)
from .store import VinOfflineShardWriter
from .views import VinSnippetView

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from efm3d.aria.obb import ObbTW
    from efm3d.aria.pose import PoseTW
    from numpy.typing import DTypeLike, NDArray

    from ...pose_generation.types import CandidateSamplingResult
    from ...rendering.candidate_depth_renderer import CandidateDepths
    from ...rendering.candidate_pointclouds import CandidatePointClouds
    from ...rri_metrics.rri import RriResult
    from ...vin.types import EvlBackboneOutput, FreeInputProvenance

DEFAULT_BACKBONE_NUMERIC_KEEP_FIELDS: tuple[str, ...] = (
    "t_world_voxel",
    "voxel_extent",
    "occ_pr",
    "occ_input",
    "free_input",
    "counts",
    "cent_pr",
    "pts_world",
)
"""Default EVL fields materialized as numeric offline blocks."""

REQUIRED_COMPACT_EVL_NUMERIC_FIELDS: tuple[str, ...] = tuple(
    f"backbone.{name}" for name in DEFAULT_BACKBONE_NUMERIC_KEEP_FIELDS
)
"""Exact actor-visible root-EVL blocks required by VIN format version 11."""

COMPACT_EVL_DTYPES: dict[str, np.dtype[Any]] = {
    **{name: np.dtype(np.float32) for name in REQUIRED_COMPACT_EVL_NUMERIC_FIELDS if name != "backbone.counts"},
    "backbone.counts": np.dtype(np.int64),
}

DEFAULT_BACKBONE_PAYLOAD_KEEP_FIELDS: tuple[str, ...] = (
    "t_world_voxel",
    "voxel_extent",
    "free_input_provenance",
    "occ_pr",
    "cent_pr",
    "bbox_pr",
    "clas_pr",
    "cent_pr_nms",
    "obbs_pr_nms",
    "obb_pred",
    "obb_pred_viz",
    "obb_pred_sem_id_to_name",
    "obb_pred_probs_full",
    "obb_pred_probs_full_viz",
)
"""Default EVL fields materialized in rich diagnostic backbone payloads."""


def _split_membership_rank(sample_key: str) -> str:
    """Return the stable split-order rank for one sample key."""

    return hashlib.sha1(sample_key.encode("utf-8")).hexdigest()


def _default_sample_key(scene_id: str, snippet_id: str) -> str:
    """Build the default stable sample key for one snippet.

    Args:
        scene_id: ASE scene identifier.
        snippet_id: ASE snippet identifier.

    Returns:
        Stable sample key.
    """

    compact_snippet = compact_ase_atek_sample_id(snippet_id)
    if compact_snippet != snippet_id or compact_snippet.startswith("ASE_"):
        return compact_snippet
    scene = re.sub(r"[^0-9a-zA-Z._-]+", "_", scene_id).strip("_")
    snippet = re.sub(r"[^0-9a-zA-Z._-]+", "_", compact_snippet).strip("_")
    return f"{scene}::{snippet}"


def _to_numpy(
    value: torch.Tensor | NDArray[Any] | bool | int | float,
    *,
    dtype: DTypeLike | None = None,
) -> NDArray[Any]:
    """Convert a scalar or tensor-like value into a NumPy array.

    Args:
        value: Value to convert.
        dtype: Optional target dtype.

    Returns:
        Converted NumPy array.
    """

    if isinstance(value, np.ndarray):
        array = value
    elif isinstance(value, torch.Tensor):
        array = value.detach().cpu().numpy()
    else:
        array = np.asarray(value)
    if dtype is not None:
        array = array.astype(dtype, copy=False)
    return array


def _pose_to_numpy(pose: PoseTW) -> NDArray[Any]:
    """Convert a ``PoseTW`` into a CPU float32 NumPy array."""

    if pose._data is None:
        raise ValueError("PoseTW payload is empty; cannot persist pose block.")
    array = _to_numpy(pose._data, dtype=np.float32)
    if array.ndim == 3 and array.shape[0] == 1:
        return np.asarray(array[0])
    return array


def _pad_first_axis(
    array: NDArray[Any],
    *,
    target_len: int,
    fill_value: float | int | bool,
) -> NDArray[Any]:
    """Pad or truncate the first axis of an array.

    Args:
        array: Input array.
        target_len: Requested size along axis 0.
        fill_value: Padding value for short arrays.

    Returns:
        Array padded or truncated along the first axis.
    """

    if array.ndim == 0:
        return array
    current = int(array.shape[0])
    if current == target_len:
        return array
    if current > target_len:
        return array[:target_len]
    pad_shape = (target_len - current, *array.shape[1:])
    pad = np.full(pad_shape, fill_value, dtype=array.dtype)
    return np.concatenate([array, pad], axis=0)


def _stack_numeric_rows(block_name: str, rows: list[PreparedVinOfflineSample]) -> NDArray[Any]:
    """Stack a numeric block, padding variable first-axis payloads when needed."""

    exemplar = next(row.numeric_blocks[block_name] for row in rows if block_name in row.numeric_blocks)
    values = [row.numeric_blocks.get(block_name) for row in rows]
    present = [value for value in values if value is not None]
    if not present:
        raise ValueError(f"No rows materialized numeric block {block_name!r}.")
    shapes = [tuple(value.shape) for value in present]
    if all(shape == shapes[0] for shape in shapes):
        return np.stack([value if value is not None else np.zeros_like(exemplar) for value in values], axis=0)
    if exemplar.ndim == 0:
        raise ValueError(f"Cannot stack scalar block {block_name!r} with mismatched shapes {shapes}.")
    trailing = tuple(exemplar.shape[1:])
    if any(tuple(value.shape[1:]) != trailing for value in present):
        raise ValueError(f"Cannot stack block {block_name!r} with incompatible shapes {shapes}.")
    target_len = max(int(value.shape[0]) for value in present)
    if np.issubdtype(exemplar.dtype, np.floating):
        fill_value: float | int | bool = np.nan
    elif np.issubdtype(exemplar.dtype, np.integer):
        fill_value = -1
    elif np.issubdtype(exemplar.dtype, np.bool_):
        fill_value = False
    else:
        fill_value = 0
    stacked_values = [
        _pad_first_axis(
            value if value is not None else np.zeros_like(exemplar), target_len=target_len, fill_value=fill_value
        )
        for value in values
    ]
    return np.stack(stacked_values, axis=0)


def _camera_param_to_numpy(
    param: torch.Tensor | NDArray[Any] | bool | int | float, *, dtype: DTypeLike
) -> NDArray[Any]:
    """Convert one PyTorch3D camera parameter into a NumPy array."""

    array = _to_numpy(param, dtype=dtype)
    if array.ndim == 0:
        return array.reshape(1)
    return array


def _wrapper_to_numpy(value: ObbTW | torch.Tensor | None, *, dtype: DTypeLike) -> NDArray[Any] | None:
    """Convert an optional OBB wrapper or tensor to a NumPy array."""

    if value is None:
        return None
    if isinstance(value, torch.Tensor):
        return _to_numpy(value, dtype=dtype)
    if value._data is None:
        raise ValueError("ObbTW payload is empty; cannot persist detected OBB block.")
    return _to_numpy(value._data, dtype=dtype)


def _probabilities_to_numpy(values: torch.Tensor | Sequence[torch.Tensor] | None) -> NDArray[Any] | None:
    """Convert optional OBB probability payloads to a dense float array."""

    if values is None:
        return None
    if isinstance(values, torch.Tensor):
        return _to_numpy(values, dtype=np.float32)
    shapes = {tuple(item.shape) for item in values}
    if len(shapes) != 1:
        raise ValueError(f"Detected OBB probability tensors must share one shape, got {sorted(shapes)}.")
    return _to_numpy(torch.stack(list(values), dim=0), dtype=np.float32)


def _validate_candidate_vector(name: str, value: torch.Tensor, *, candidate_count: int) -> None:
    """Ensure one oracle vector is aligned with the rendered candidate table."""

    actual = int(value.reshape(-1).shape[0])
    if actual != candidate_count:
        raise ValueError(f"{name} length {actual} must match rendered candidate count {candidate_count}.")


def _validate_candidate_first_axis(
    name: str,
    value: torch.Tensor,
    *,
    candidate_count: int,
) -> None:
    """Ensure one candidate-major tensor starts with the rendered candidate count."""

    if value.ndim == 0:
        raise ValueError(f"{name} must have a candidate dimension.")
    actual = int(value.shape[0])
    if actual != candidate_count:
        raise ValueError(f"{name} first dimension {actual} must match rendered candidate count {candidate_count}.")


def _validate_candidate_label_alignment(
    *,
    candidate_count: int,
    candidates: CandidateSamplingResult | None,
    depths: CandidateDepths,
    rri: RriResult,
    candidate_pcs: CandidatePointClouds | None,
) -> None:
    """Fail fast when candidate-major oracle payloads are not in lockstep.

    The immutable offline store is a training contract: candidate poses, depth
    renders, point clouds, RRI labels, and optional diagnostic payloads must
    describe the same ordered candidate table. This guard catches shape and
    shell-index drift before an on-disk row can be materialized.
    """

    _validate_candidate_first_axis("oracle.depths", depths.depths, candidate_count=candidate_count)
    if tuple(depths.depths_valid_mask.shape) != tuple(depths.depths.shape):
        raise ValueError(
            "oracle.depths_valid_mask shape "
            f"{tuple(depths.depths_valid_mask.shape)} must match oracle.depths {tuple(depths.depths.shape)}.",
        )

    for field_name in (
        "rri",
        "pm_dist_before",
        "pm_dist_after",
        "pm_acc_before",
        "pm_comp_before",
        "pm_acc_after",
        "pm_comp_after",
    ):
        _validate_candidate_vector(f"oracle.{field_name}", getattr(rri, field_name), candidate_count=candidate_count)
    if rri.fscore_tau is not None:
        _validate_candidate_first_axis("oracle.fscore_tau", rri.fscore_tau, candidate_count=candidate_count)

    camera = depths.p3d_cameras
    for field_name in ("R", "T", "focal_length", "principal_point", "image_size"):
        _validate_candidate_first_axis(
            f"oracle.p3d.{field_name}",
            getattr(camera, field_name),
            candidate_count=candidate_count,
        )

    if candidate_pcs is not None:
        _validate_candidate_first_axis(
            "oracle.candidate_pcs.points",
            candidate_pcs.points,
            candidate_count=candidate_count,
        )
        _validate_candidate_vector(
            "oracle.candidate_pcs.lengths",
            candidate_pcs.lengths,
            candidate_count=candidate_count,
        )

    if candidates is None:
        return

    actual_indices = depths.candidate_indices.detach().to(device="cpu", dtype=torch.long).reshape(-1)
    expected_indices = candidates.candidate_shell_indices(device=torch.device("cpu"))
    if expected_indices.numel() < candidate_count:
        raise ValueError(
            "CandidateSamplingResult exposes fewer shell indices "
            f"({expected_indices.numel()}) than rendered candidates ({candidate_count}).",
        )
    if not torch.equal(actual_indices, expected_indices[:candidate_count]):
        raise ValueError(
            "CandidateDepths.candidate_indices must match the rendered prefix "
            "of CandidateSamplingResult.candidate_shell_indices().",
        )

    actual_poses = (
        cast(Callable[[], torch.Tensor], depths.poses.tensor)().detach().to(device="cpu", dtype=torch.float32)
    )
    expected_pose_wrapper = candidates.poses_world_cam(device=torch.device("cpu"))
    expected_poses = cast(Callable[[], torch.Tensor], expected_pose_wrapper.tensor)().detach().to(dtype=torch.float32)
    if expected_poses.shape[0] < candidate_count:
        raise ValueError(
            "CandidateSamplingResult exposes fewer world-camera poses "
            f"({expected_poses.shape[0]}) than rendered candidates ({candidate_count}).",
        )
    if actual_poses.shape != expected_poses[:candidate_count].shape:
        raise ValueError(
            "CandidateDepths.poses shape "
            f"{tuple(actual_poses.shape)} must match candidate poses {tuple(expected_poses[:candidate_count].shape)}.",
        )
    if not torch.allclose(actual_poses, expected_poses[:candidate_count], atol=1e-5, rtol=1e-5):
        raise ValueError("CandidateDepths.poses must align with CandidateSamplingResult.poses_world_cam().")


def _semantic_names_payload(
    value: Mapping[Any, Any] | Sequence[Any] | None,
) -> dict[int, str] | None:
    """Normalize semantic-name mappings for msgpack records."""

    return normalize_semantic_name_map(value)


def _keep_field(field_name: str, keep_fields: set[str] | None) -> bool:
    """Return whether a field should be materialized.

    Args:
        field_name: Dataclass or logical field name.
        keep_fields: Optional keep-list. ``None`` keeps all fields.

    Returns:
        Whether the requested field is enabled.
    """

    return keep_fields is None or field_name in keep_fields


@dataclass(slots=True)
class PreparedVinOfflineSample:
    """Normalized offline row before shard materialization.

    Attributes:
        sample_key: Stable sample key for the row.
        scene_id: ASE scene identifier.
        snippet_id: ASE snippet identifier.
        numeric_blocks: Fixed-size numeric blocks stored as Zarr arrays.
        record_blocks: Lazy diagnostic payloads stored as msgspec records.
    """

    sample_key: str
    """Stable sample key for the row."""

    scene_id: str
    """ASE scene identifier."""

    snippet_id: str
    """ASE snippet identifier."""

    free_input_provenance: FreeInputProvenance | None = None
    """Typed EVL free-input provenance for this row, when backbone is present."""

    numeric_blocks: dict[str, NDArray[Any]] = field(default_factory=dict)
    """Fixed-size numeric blocks stored per row."""

    record_blocks: dict[str, Any] = field(default_factory=dict)
    """Lazy per-row diagnostic payloads stored in msgspec-compatible form."""


def prepare_vin_offline_sample(
    *,
    scene_id: str,
    snippet_id: str,
    vin_snippet: VinSnippetView,
    candidates: CandidateSamplingResult | None,
    depths: CandidateDepths,
    rri: RriResult,
    candidate_pcs: CandidatePointClouds | None,
    backbone_out: EvlBackboneOutput | None,
    max_candidates: int,
    source_sample: EfmSnippetView | None = None,
    include_depths: bool = True,
    include_candidate_pcs: bool = True,
    include_backbone: bool = True,
    include_diagnostic_payloads: bool = False,
    include_gt_obbs: bool = True,
    include_detected_obbs: bool = True,
    include_trajectory_metadata: bool = True,
    backbone_numeric_keep_fields: set[str] | None = None,
    backbone_payload_keep_fields: set[str] | None = None,
    sample_key: str | None = None,
) -> PreparedVinOfflineSample:
    """Normalize one oracle-labelled snippet into offline row blocks.

    Args:
        scene_id: ASE scene identifier.
        snippet_id: ASE snippet identifier.
        vin_snippet: Canonical VIN snippet for the row.
        candidates: Optional candidate-sampling payload for diagnostics.
        depths: Candidate-depth payload aligned with the oracle labels.
        rri: Oracle metrics aligned with the rendered candidates.
        candidate_pcs: Optional candidate point clouds for diagnostics.
        backbone_out: Optional backbone outputs for training or diagnostics.
        source_sample: Optional raw EFM snippet used for compact GT modalities.
        max_candidates: Maximum number of candidates stored in fixed blocks.
        include_depths: Whether to materialize numeric depth blocks.
        include_candidate_pcs: Whether candidate point clouds may be written
            when rich diagnostic payloads are enabled.
        include_backbone: Whether to materialize backbone outputs.
        include_diagnostic_payloads: Whether to write rich msgpack records such
            as full depth DTOs, candidate DTOs, candidate point clouds, and
            full backbone payloads. Defaults off because numeric blocks are the
            canonical training contract.
        include_gt_obbs: Whether to persist compact GT OBB tensors from the raw snippet.
        include_detected_obbs: Whether to persist compact detected OBB tensors from the backbone.
        include_trajectory_metadata: Whether to persist trajectory timestamps and gravity.
        backbone_numeric_keep_fields: Optional EVL backbone field keep-list for
            fixed numeric blocks. ``None`` preserves legacy behavior by writing
            all supported numeric fields.
        backbone_payload_keep_fields: Optional EVL backbone field keep-list for
            rich diagnostic payloads. ``None`` preserves legacy behavior by
            serializing all available fields.
        sample_key: Optional explicit sample key.

    Returns:
        Prepared row ready for shard materialization.
    """

    candidate_poses = _pose_to_numpy(depths.poses)
    if candidate_poses.ndim != 2 or candidate_poses.shape[-1] != 12:
        raise ValueError("Candidate poses must have shape (N, 12).")
    candidate_count = int(candidate_poses.shape[0])
    if candidate_count <= 0:
        raise ValueError("Prepared offline samples require at least one candidate.")
    if candidate_count > int(max_candidates):
        raise ValueError(
            f"Candidate count {candidate_count} exceeds configured max_candidates={max_candidates}.",
        )

    reference_pose = _pose_to_numpy(depths.reference_pose)
    if reference_pose.ndim == 2 and reference_pose.shape[0] == 1:
        reference_pose = reference_pose[0]

    points_world = _to_numpy(vin_snippet.points_world, dtype=np.float32)
    lengths = _to_numpy(vin_snippet.lengths.reshape(-1), dtype=np.int64)
    t_world_rig = _pose_to_numpy(vin_snippet.t_world_rig)
    t_world_snippet = _pose_to_numpy(vin_snippet.t_world_snippet)

    camera = depths.p3d_cameras
    candidate_indices = _to_numpy(depths.candidate_indices.reshape(-1), dtype=np.int64)
    if candidate_indices.shape[0] != candidate_count:
        raise ValueError("CandidateDepths.candidate_indices must align with rendered candidates.")
    _validate_candidate_label_alignment(
        candidate_count=candidate_count,
        candidates=candidates,
        depths=depths,
        rri=rri,
        candidate_pcs=candidate_pcs,
    )

    numeric_blocks: dict[str, NDArray[Any]] = {
        "vin.points_world": points_world,
        "vin.lengths": lengths,
        "vin.t_world_rig": t_world_rig,
        "vin.t_world_snippet": t_world_snippet,
        "oracle.candidate_count": np.asarray(candidate_count, dtype=np.int64),
        "oracle.candidate_indices": _pad_first_axis(candidate_indices, target_len=max_candidates, fill_value=-1),
        "oracle.candidate_poses_world_cam": _pad_first_axis(
            candidate_poses.astype(np.float32, copy=False),
            target_len=max_candidates,
            fill_value=0.0,
        ),
        "vin.reference_pose_world_rig": reference_pose.astype(np.float32, copy=False),
        "oracle.rri": _pad_first_axis(
            _to_numpy(rri.rri.reshape(-1), dtype=np.float32), target_len=max_candidates, fill_value=np.nan
        ),
        "oracle.pm_dist_before": _pad_first_axis(
            _to_numpy(rri.pm_dist_before.reshape(-1), dtype=np.float32),
            target_len=max_candidates,
            fill_value=np.nan,
        ),
        "oracle.pm_dist_after": _pad_first_axis(
            _to_numpy(rri.pm_dist_after.reshape(-1), dtype=np.float32),
            target_len=max_candidates,
            fill_value=np.nan,
        ),
        "oracle.pm_acc_before": _pad_first_axis(
            _to_numpy(rri.pm_acc_before.reshape(-1), dtype=np.float32),
            target_len=max_candidates,
            fill_value=np.nan,
        ),
        "oracle.pm_comp_before": _pad_first_axis(
            _to_numpy(rri.pm_comp_before.reshape(-1), dtype=np.float32),
            target_len=max_candidates,
            fill_value=np.nan,
        ),
        "oracle.pm_acc_after": _pad_first_axis(
            _to_numpy(rri.pm_acc_after.reshape(-1), dtype=np.float32),
            target_len=max_candidates,
            fill_value=np.nan,
        ),
        "oracle.pm_comp_after": _pad_first_axis(
            _to_numpy(rri.pm_comp_after.reshape(-1), dtype=np.float32),
            target_len=max_candidates,
            fill_value=np.nan,
        ),
        "oracle.p3d.R": _pad_first_axis(
            _camera_param_to_numpy(camera.R, dtype=np.float32),
            target_len=max_candidates,
            fill_value=0.0,
        ),
        "oracle.p3d.T": _pad_first_axis(
            _camera_param_to_numpy(camera.T, dtype=np.float32),
            target_len=max_candidates,
            fill_value=0.0,
        ),
        "oracle.p3d.focal_length": _pad_first_axis(
            _camera_param_to_numpy(camera.focal_length, dtype=np.float32),
            target_len=max_candidates,
            fill_value=0.0,
        ),
        "oracle.p3d.principal_point": _pad_first_axis(
            _camera_param_to_numpy(camera.principal_point, dtype=np.float32),
            target_len=max_candidates,
            fill_value=0.0,
        ),
        "oracle.p3d.image_size": _pad_first_axis(
            _camera_param_to_numpy(camera.image_size, dtype=np.float32),
            target_len=max_candidates,
            fill_value=0.0,
        ),
        "oracle.p3d.in_ndc": np.asarray(
            bool(camera.in_ndc() if callable(camera.in_ndc) else camera.in_ndc), dtype=np.bool_
        ),
    }

    znear = getattr(camera, "znear", None)
    zfar = getattr(camera, "zfar", None)
    if znear is not None:
        numeric_blocks["oracle.p3d.znear"] = _to_numpy(znear, dtype=np.float32)
    if zfar is not None:
        numeric_blocks["oracle.p3d.zfar"] = _to_numpy(zfar, dtype=np.float32)

    if include_depths:
        depths_array = _to_numpy(depths.depths, dtype=np.float32)
        depths_mask = _to_numpy(depths.depths_valid_mask, dtype=np.bool_)
        numeric_blocks["oracle.depths"] = _pad_first_axis(depths_array, target_len=max_candidates, fill_value=0.0)
        numeric_blocks["oracle.depths_valid_mask"] = _pad_first_axis(
            depths_mask,
            target_len=max_candidates,
            fill_value=False,
        )

    if include_backbone and backbone_out is not None:
        if _keep_field("t_world_voxel", backbone_numeric_keep_fields):
            numeric_blocks["backbone.t_world_voxel"] = _pose_to_numpy(backbone_out.t_world_voxel).astype(
                np.float32, copy=False
            )
        if _keep_field("voxel_extent", backbone_numeric_keep_fields):
            numeric_blocks["backbone.voxel_extent"] = _to_numpy(backbone_out.voxel_extent, dtype=np.float32)
        for field_name, dtype in (
            ("occ_pr", np.float32),
            ("occ_input", np.float32),
            ("free_input", np.float32),
            ("counts", np.int64),
            ("cent_pr", np.float32),
            ("pts_world", np.float32),
        ):
            if not _keep_field(field_name, backbone_numeric_keep_fields):
                continue
            value = getattr(backbone_out, field_name, None)
            if value is not None:
                numeric_blocks[f"backbone.{field_name}"] = _to_numpy(value, dtype=dtype)

    if include_trajectory_metadata and source_sample is not None:
        trajectory = source_sample.trajectory
        numeric_blocks["vin.trajectory.time_ns"] = _to_numpy(trajectory.time_ns, dtype=np.int64)
        numeric_blocks["vin.trajectory.gravity_in_world"] = _to_numpy(trajectory.gravity_in_world, dtype=np.float32)

    if include_gt_obbs and source_sample is not None:
        gt_obbs = source_sample.obbs
        if gt_obbs is not None:
            if gt_obbs.obbs._data is None:
                raise ValueError("ObbTW payload is empty; cannot persist GT OBB block.")
            numeric_blocks["gt.obbs"] = _to_numpy(gt_obbs.obbs._data, dtype=np.float32)

    if include_detected_obbs and backbone_out is not None:
        detected_source = backbone_out.obb_pred_viz if backbone_out.obb_pred_viz is not None else backbone_out.obb_pred
        detected = _wrapper_to_numpy(detected_source, dtype=np.float32)
        if detected is not None:
            numeric_blocks["detected.obbs"] = detected
        probs_source = (
            backbone_out.obb_pred_probs_full_viz
            if backbone_out.obb_pred_probs_full_viz is not None
            else backbone_out.obb_pred_probs_full
        )
        probs = _probabilities_to_numpy(probs_source)
        if probs is not None:
            numeric_blocks["detected.obb_probs"] = probs

    record_blocks: dict[str, Any] = {}
    if include_diagnostic_payloads and include_depths:
        record_blocks["oracle.depths_payload"] = depths.to_serializable()
    if include_diagnostic_payloads and candidates is not None:
        record_blocks["oracle.candidates"] = candidates.to_serializable()
    if include_diagnostic_payloads and include_candidate_pcs and candidate_pcs is not None:
        record_blocks["oracle.candidate_pcs"] = candidate_pcs.to_serializable()
    if include_diagnostic_payloads and include_backbone and backbone_out is not None:
        record_blocks["backbone.payload"] = backbone_out.to_serializable(
            include_fields=backbone_payload_keep_fields,
        )
    if include_gt_obbs and source_sample is not None:
        sem_id_to_name = _semantic_names_payload(source_sample.efm.get(ARIA_OBB_SEM_ID_TO_NAME))
        if sem_id_to_name is not None:
            record_blocks["gt.obb_sem_id_to_name"] = sem_id_to_name
    if include_detected_obbs and backbone_out is not None and backbone_out.obb_pred_sem_id_to_name is not None:
        record_blocks["detected.obb_sem_id_to_name"] = _semantic_names_payload(backbone_out.obb_pred_sem_id_to_name)

    return PreparedVinOfflineSample(
        sample_key=compact_ase_atek_sample_id(sample_key)
        if sample_key is not None
        else _default_sample_key(scene_id, snippet_id),
        scene_id=scene_id,
        snippet_id=compact_ase_atek_sample_id(snippet_id),
        free_input_provenance=(
            validate_free_input_provenance(backbone_out.free_input_provenance)
            if include_backbone and backbone_out is not None
            else None
        ),
        numeric_blocks=numeric_blocks,
        record_blocks=record_blocks,
    )


def flush_prepared_samples_to_shard(
    *,
    shard_index: int,
    shard_dir: Path,
    rows: list[PreparedVinOfflineSample],
) -> tuple[VinOfflineShardSpec, list[VinOfflineIndexRecord]]:
    """Materialize a list of prepared rows into one immutable shard.

    Args:
        shard_index: Zero-based shard index.
        shard_dir: Destination shard directory.
        rows: Prepared sample rows.

    Returns:
        Shard descriptor plus local sample-index records.
    """

    if not rows:
        raise ValueError("Cannot flush an empty shard.")

    numeric_block_names = sorted({name for row in rows for name in row.numeric_blocks})
    backbone_names = {name for name in numeric_block_names if name.startswith("backbone.")}
    if backbone_names:
        provenance = {row.free_input_provenance for row in rows}
        if len(provenance) != 1 or None in provenance:
            raise ValueError(
                "VIN backbone rows require one known homogeneous free_input_provenance value; "
                f"got {sorted(provenance, key=str)}."
            )
        missing_fields = sorted(set(REQUIRED_COMPACT_EVL_NUMERIC_FIELDS) - backbone_names)
        unexpected_fields = sorted(backbone_names - set(REQUIRED_COMPACT_EVL_NUMERIC_FIELDS))
        if missing_fields or unexpected_fields:
            raise ValueError(
                "VIN version-10 compact EVL rows require exactly the eight canonical backbone blocks; "
                f"missing={missing_fields}, unexpected={unexpected_fields}."
            )
        for block_name in REQUIRED_COMPACT_EVL_NUMERIC_FIELDS:
            missing = [row.sample_key for row in rows if block_name not in row.numeric_blocks]
            if missing:
                raise ValueError(
                    f"Backbone block {block_name!r} must be present in every shard row; missing from {missing}."
                )
            values = [row.numeric_blocks[block_name] for row in rows]
            expected_dtype = values[0].dtype
            expected_shape = values[0].shape
            required_dtype = COMPACT_EVL_DTYPES[block_name]
            if expected_dtype != required_dtype:
                raise ValueError(
                    f"Backbone block {block_name!r} requires canonical dtype {required_dtype}, got {expected_dtype}."
                )
            if any(value.dtype != expected_dtype or value.shape != expected_shape for value in values[1:]):
                facts = [(str(value.dtype), tuple(value.shape)) for value in values]
                raise ValueError(f"Backbone block {block_name!r} has heterogeneous canonical dtype/row shape: {facts}.")

    shard_dir.mkdir(parents=True, exist_ok=True)
    shard_writer = VinOfflineShardWriter(shard_dir=shard_dir)
    block_specs: dict[str, Any] = {}
    for block_name in numeric_block_names:
        stacked = _stack_numeric_rows(block_name, rows)
        block_specs[block_name] = shard_writer.write_numeric_block(block_name, stacked)

    record_block_names = sorted({name for row in rows for name in row.record_blocks})
    for block_name in record_block_names:
        block_records = [row.record_blocks.get(block_name) for row in rows]
        if any(record is not None for record in block_records):
            block_specs[block_name] = shard_writer.write_record_block(block_name, block_records)

    shard_id = f"shard-{shard_index:06d}"
    relative_dir = str(Path("shards") / shard_id)
    shard_spec = VinOfflineShardSpec(
        shard_id=shard_id,
        relative_dir=relative_dir,
        row_start=0,
        num_rows=len(rows),
        blocks=block_specs,
    )
    index_records = [
        VinOfflineIndexRecord(
            sample_index=-1,
            sample_key=row.sample_key,
            scene_id=row.scene_id,
            snippet_id=row.snippet_id,
            split="all",
            shard_id=shard_id,
            row=local_row,
        )
        for local_row, row in enumerate(rows)
    ]
    return shard_spec, index_records


def assign_offline_splits(
    *,
    records: list[VinOfflineIndexRecord],
    val_fraction: float,
) -> dict[str, NDArray[Any]]:
    """Assign deterministic split membership to global sample indices.

    Args:
        records: Global sample-index records.
        val_fraction: Requested validation fraction.

    Returns:
        Mapping from split name to global sample-index arrays.
    """

    total = len(records)
    all_indices = np.arange(total, dtype=np.int64)
    if total == 0:
        return {"all": all_indices, "train": all_indices.copy(), "val": np.empty((0,), dtype=np.int64)}

    val_target = int(round(float(val_fraction) * total))
    val_target = max(0, min(total, val_target))
    val_members = set(
        sorted(
            range(total),
            key=lambda idx: (_split_membership_rank(records[idx].sample_key), records[idx].sample_key),
        )[:val_target]
    )
    val_indices = np.asarray([idx for idx in all_indices if int(idx) in val_members], dtype=np.int64)
    train_indices = np.asarray([idx for idx in all_indices if int(idx) not in val_members], dtype=np.int64)
    for idx, record in enumerate(records):
        record.sample_index = idx
        record.split = "val" if idx in val_members else "train"
    return {"all": all_indices, "train": train_indices, "val": val_indices}


__all__ = [
    "PreparedVinOfflineSample",
    "assign_offline_splits",
    "flush_prepared_samples_to_shard",
    "prepare_vin_offline_sample",
]
