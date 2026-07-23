"""Diagnostics for immutable VIN offline stores.

The helpers in this module inspect the current ``VinOfflineDataset`` storage
format directly for store, sample, RRI, geometry, backbone, memory, batch, and
raw-dataset coverage diagnostics.
"""

from __future__ import annotations

import math
import re
import tarfile
from collections.abc import Callable
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from efm3d.aria.pose import PoseTW

from ...configs import PathConfig
from ...configs.path_config import PROJECT_ROOT
from ..identifiers import compact_ase_atek_sample_id
from ..raw.views import is_efm_snippet_view_instance, is_vin_snippet_view_instance
from .batch import VinOracleBatch
from .format import VinOfflineIndexRecord, VinOfflineShardSpec
from .store import VinOfflineStoreConfig, VinOfflineStoreReader

RRI_COMPONENT_BLOCKS: tuple[str, ...] = (
    "oracle.pm_dist_before",
    "oracle.pm_dist_after",
    "oracle.pm_acc_before",
    "oracle.pm_acc_after",
    "oracle.pm_comp_before",
    "oracle.pm_comp_after",
)
"""Oracle RRI component blocks summarized by immutable-store diagnostics."""

POSE_CAMERA_BLOCKS: tuple[str, ...] = (
    "oracle.candidate_poses_world_cam",
    "oracle.reference_pose_world_rig",
    "oracle.p3d.R",
    "oracle.p3d.T",
    "oracle.p3d.focal_length",
    "oracle.p3d.principal_point",
    "oracle.p3d.image_size",
    "oracle.p3d.in_ndc",
    "oracle.p3d.znear",
    "oracle.p3d.zfar",
)
"""Pose and camera blocks used to estimate runtime memory."""


@dataclass(slots=True)
class NumericSummary:
    """Finite-value summary for one numeric diagnostic series."""

    count: int
    """Number of observed finite values."""

    minimum: float | None
    """Minimum finite value, or ``None`` when no finite values exist."""

    mean: float | None
    """Mean finite value, or ``None`` when no finite values exist."""

    maximum: float | None
    """Maximum finite value, or ``None`` when no finite values exist."""


@dataclass(slots=True)
class VinOfflineMemoryDiagnostic:
    """Estimated per-sample runtime memory for one offline-store component."""

    component: str
    """Component name such as ``"backbone"`` or ``"oracle_rri"``."""

    mean_mib: float
    """Mean estimated MiB across sampled rows."""

    median_mib: float
    """Median estimated MiB across sampled rows."""

    p95_mib: float
    """95th percentile estimated MiB across sampled rows."""


@dataclass(slots=True)
class VinOfflineBackboneDiagnostic:
    """Streaming numeric summary for one stored backbone field."""

    field: str
    """Backbone field name without the ``"backbone."`` prefix."""

    shape: list[int]
    """Per-row tensor shape."""

    numel: int
    """Number of elements per sampled row."""

    sampled_rows: int
    """Number of rows contributing to the summary."""

    count: int
    """Number of finite elements contributing to summary moments."""

    mean: float | None
    """Mean finite value."""

    std: float | None
    """Population standard deviation for finite values."""

    abs_mean: float | None
    """Mean absolute finite value."""

    nz_frac: float | None
    """Fraction of finite values whose absolute value is larger than ``1e-6``."""


@dataclass(slots=True)
class VinOfflineBlockDiagnostic:
    """Render-ready manifest summary for one stored offline block."""

    shard_id: str
    """Shard that declares the block."""

    name: str
    """Logical block name."""

    kind: str
    """Storage kind such as ``zarr_array`` or ``msgpack_indexed_records``."""

    dtype: str | None
    """Stored NumPy dtype for numeric blocks."""

    shape: list[int] | None
    """Stored array shape or record count."""

    optional: bool
    """Whether the block is optional."""

    estimated_bytes: int | None
    """Estimated numeric bytes, or ``None`` for non-numeric blocks."""


@dataclass(slots=True)
class VinOfflineSampleDiagnostic:
    """Per-row sanity summary for one sampled VIN offline record."""

    sample_index: int
    """Global sample index."""

    sample_key: str
    """Stable dataset sample key."""

    scene_id: str
    """ASE scene identifier."""

    snippet_id: str
    """ASE snippet identifier."""

    split: str
    """Dataset split membership."""

    shard_id: str
    """Shard that stores the row."""

    row: int
    """Shard-local row index."""

    candidate_count: int
    """Valid candidate count for the row."""

    rri: NumericSummary
    """Finite RRI summary for valid candidates."""

    vin_points: NumericSummary
    """VIN point-length summary for the row."""


@dataclass(slots=True)
class VinOfflineCoverageSceneDiagnostic:
    """Per-scene raw-dataset coverage against one immutable offline store."""

    scene_id: str
    """ASE scene identifier."""

    dataset_snippets: int
    """Number of raw-dataset snippets found in scanned tar headers."""

    store_snippets: int
    """Number of immutable-store snippets for the scene."""

    covered_snippets: int
    """Number of snippets present in both the raw dataset and the store."""

    missing_in_store: int
    """Raw-dataset snippets missing from the immutable store."""

    outside_dataset: int
    """Store snippets not found in the scanned raw-dataset tar headers."""

    coverage: float | None
    """Coverage ratio ``covered_snippets / dataset_snippets``."""


@dataclass(slots=True)
class VinOfflineCoverageStats:
    """Raw-dataset coverage summary for one immutable VIN offline store."""

    store_dir: str
    """Absolute store directory inspected for coverage."""

    tar_shards_scanned: int
    """Number of raw dataset tar shards scanned."""

    dataset_scenes: int
    """Number of scenes found in scanned raw-dataset tar headers."""

    store_scenes: int
    """Number of scenes represented by the immutable store sample index."""

    dataset_snippets: int
    """Number of raw-dataset snippets found in scanned tar headers."""

    store_snippets: int
    """Number of immutable-store snippets."""

    covered_snippets: int
    """Number of snippets present in both the raw dataset and immutable store."""

    missing_in_store: int
    """Raw-dataset snippets missing from the immutable store."""

    outside_dataset: int
    """Immutable-store snippets outside the scanned raw-dataset tar headers."""

    coverage: float | None
    """Overall coverage ratio ``covered_snippets / dataset_snippets``."""

    per_scene: list[VinOfflineCoverageSceneDiagnostic] = field(default_factory=list)
    """Per-scene coverage rows."""

    missing_examples: list[tuple[str, str]] = field(default_factory=list)
    """Example ``(scene_id, snippet_id)`` pairs missing from the store."""

    outside_examples: list[tuple[str, str]] = field(default_factory=list)
    """Example store pairs outside the scanned raw dataset."""


@dataclass(slots=True)
class VinOfflineDatasetStats:
    """Store-level diagnostics for an immutable VIN offline dataset."""

    store_dir: str
    """Absolute store directory inspected for diagnostics."""

    version: int
    """Offline dataset format version from ``manifest.json``."""

    num_samples: int
    """Number of rows listed in ``sample_index.jsonl``."""

    sampled_samples: int
    """Number of rows scanned for per-sample statistics."""

    split_counts: dict[str, int]
    """Sample counts keyed by split name."""

    num_scenes: int
    """Number of unique scene IDs in the sample index."""

    num_snippets: int
    """Number of unique ``(scene_id, snippet_id)`` pairs."""

    materialized_blocks: dict[str, bool]
    """Optional block flags from the manifest."""

    candidate_count: NumericSummary
    """Distribution of valid candidate counts per sample."""

    rri: NumericSummary
    """Distribution of finite oracle RRI values across sampled candidates."""

    vin_points: NumericSummary
    """Distribution of VIN point lengths across sampled snippets."""

    numeric_bytes: int
    """Approximate bytes occupied by manifest-declared numeric shard blocks."""

    block_shapes: dict[str, list[int]] = field(default_factory=dict)
    """Stored numeric block shapes keyed by logical block name."""

    block_diagnostics: list[VinOfflineBlockDiagnostic] = field(default_factory=list)
    """Manifest-declared block diagnostics for Streamlit and CLI tables."""

    sample_summaries: list[VinOfflineSampleDiagnostic] = field(default_factory=list)
    """Per-row sanity summaries for sampled records."""

    candidate_count_values: list[float] = field(default_factory=list)
    """Sampled candidate-count values used for histograms."""

    rri_values: list[float] = field(default_factory=list)
    """Sampled finite oracle RRI values used for histograms."""

    vin_point_values: list[float] = field(default_factory=list)
    """Sampled VIN point lengths used for histograms."""

    rri_component_values: dict[str, list[float]] = field(default_factory=dict)
    """Sampled finite RRI component values keyed by component name."""

    rri_component_summaries: dict[str, NumericSummary] = field(default_factory=dict)
    """Finite-value summaries for RRI component values."""

    candidate_pose_values: dict[str, list[float]] = field(default_factory=dict)
    """Candidate pose diagnostics in the reference-rig frame."""

    candidate_pose_summaries: dict[str, NumericSummary] = field(default_factory=dict)
    """Finite-value summaries for candidate pose diagnostics."""

    memory_diagnostics: list[VinOfflineMemoryDiagnostic] = field(default_factory=list)
    """Estimated per-sample runtime memory summaries."""

    backbone_diagnostics: list[VinOfflineBackboneDiagnostic] = field(default_factory=list)
    """Streaming statistics for sampled backbone numeric fields."""

    batch_shapes: dict[str, str] = field(default_factory=dict)
    """Shape preview from one ``VinOracleBatch`` read path."""


def _finite_values(values: np.ndarray) -> list[float]:
    """Return finite values from a numeric array as Python floats."""

    flat = np.asarray(values).reshape(-1)
    finite = flat[np.isfinite(flat)]
    return [float(value) for value in finite]


def _summary(values: list[float]) -> NumericSummary:
    """Summarize finite numeric values."""

    if not values:
        return NumericSummary(count=0, minimum=None, mean=None, maximum=None)
    array = np.asarray(values, dtype=np.float64)
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        return NumericSummary(count=0, minimum=None, mean=None, maximum=None)
    return NumericSummary(
        count=int(finite.size),
        minimum=float(np.min(finite)),
        mean=float(np.mean(finite)),
        maximum=float(np.max(finite)),
    )


def _component_key(block_name: str) -> str:
    """Return a concise display key for one oracle component block."""

    return block_name.removeprefix("oracle.")


def _collect_block_diagnostics(
    reader: VinOfflineStoreReader,
) -> tuple[int, dict[str, list[int]], list[VinOfflineBlockDiagnostic]]:
    """Collect manifest-declared block shapes and byte estimates."""

    total = 0
    block_shapes: dict[str, list[int]] = {}
    diagnostics: list[VinOfflineBlockDiagnostic] = []
    for shard in reader.manifest.shards:
        for block_name, spec in shard.blocks.items():
            shape = [int(dim) for dim in spec.shape] if spec.shape is not None else None
            estimated_bytes: int | None = None
            if spec.kind == "zarr_array" and shape is not None and spec.dtype is not None:
                block_shapes.setdefault(block_name, shape)
                estimated_bytes = int(np.prod(shape, dtype=np.int64)) * int(np.dtype(spec.dtype).itemsize)
                total += estimated_bytes
            diagnostics.append(
                VinOfflineBlockDiagnostic(
                    shard_id=shard.shard_id,
                    name=block_name,
                    kind=spec.kind,
                    dtype=spec.dtype,
                    shape=shape,
                    optional=bool(spec.optional),
                    estimated_bytes=estimated_bytes,
                ),
            )
    diagnostics.sort(key=lambda item: (item.shard_id, item.name))
    return total, block_shapes, diagnostics


def _shards_by_id(reader: VinOfflineStoreReader) -> dict[str, VinOfflineShardSpec]:
    """Return manifest shards keyed by shard id."""

    return {shard.shard_id: shard for shard in reader.manifest.shards}


def _has_record_block(
    *,
    shards: dict[str, VinOfflineShardSpec],
    record: VinOfflineIndexRecord,
    block_name: str,
) -> bool:
    """Return whether one record's shard declares a block."""

    shard = shards.get(record.shard_id)
    return bool(shard is not None and block_name in shard.blocks)


def _read_valid_vector(
    reader: VinOfflineStoreReader,
    record: VinOfflineIndexRecord,
    block_name: str,
    *,
    candidate_count: int,
) -> np.ndarray:
    """Read one candidate-aligned vector clipped to valid candidate rows."""

    return np.asarray(reader.read_numeric_block(record, block_name)).reshape(-1)[:candidate_count]


def _normalise(vec: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    """Return unit vectors with stable zero handling."""

    return vec / vec.norm(dim=-1, keepdim=True).clamp_min(eps)


def _broadcast_ref_pose(
    ref_rot: torch.Tensor,
    ref_t: torch.Tensor,
    target_rot: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Broadcast one reference pose to candidate-pose leading dimensions."""

    if ref_rot.ndim == 2:
        ref_rot = ref_rot.unsqueeze(0)
    if ref_t.ndim == 1:
        ref_t = ref_t.unsqueeze(0)

    target_shape = target_rot.shape[:-2]
    ref_shape = ref_rot.shape[:-2]

    if len(ref_shape) < len(target_shape):
        pad = (1,) * (len(target_shape) - len(ref_shape))
        ref_rot = ref_rot.reshape(ref_shape + pad + (3, 3))
        ref_t = ref_t.reshape(ref_t.shape[:-1] + pad + (3,))
        ref_shape = ref_rot.shape[:-2]

    if len(ref_shape) != len(target_shape):
        raise ValueError(f"reference pose dims {ref_shape} are incompatible with target {target_shape}.")

    expanded_shape = []
    for ref_dim, target_dim in zip(ref_shape, target_shape, strict=True):
        if ref_dim not in (1, target_dim):
            raise ValueError(f"reference pose dims {ref_shape} are incompatible with target {target_shape}.")
        expanded_shape.append(target_dim if ref_dim == 1 else ref_dim)

    return ref_rot.expand(*expanded_shape, 3, 3), ref_t.expand(*expanded_shape, 3)


def _roll_about_forward(
    *,
    forward: torch.Tensor,
    up_cam: torch.Tensor,
    up_ref: torch.Tensor,
    eps: float = 1e-6,
) -> torch.Tensor:
    """Compute roll angle around the camera forward vector."""

    forward = _normalise(forward, eps=eps)
    up_cam = _normalise(up_cam, eps=eps)
    if up_ref.ndim == 1:
        up_ref = up_ref.view(1, 3).expand_as(forward)
    else:
        while up_ref.ndim < forward.ndim:
            up_ref = up_ref.unsqueeze(0)
        up_ref = up_ref.expand_as(forward)
    up_ref = _normalise(up_ref, eps=eps)

    left0 = torch.cross(up_ref, forward, dim=-1)
    left0_norm = left0.norm(dim=-1, keepdim=True)
    degenerate = left0_norm.squeeze(-1) < eps
    if degenerate.any():
        alt = torch.tensor([1.0, 0.0, 0.0], device=forward.device, dtype=forward.dtype).view(1, 3).expand_as(forward)
        alt = alt - (alt * forward).sum(dim=-1, keepdim=True) * forward
        alt_norm = alt.norm(dim=-1, keepdim=True)
        second = alt_norm.squeeze(-1) < eps
        if second.any():
            alt2 = (
                torch.tensor([0.0, 1.0, 0.0], device=forward.device, dtype=forward.dtype).view(1, 3).expand_as(forward)
            )
            alt2 = alt2 - (alt2 * forward).sum(dim=-1, keepdim=True) * forward
            alt[second] = alt2[second]
            alt_norm = alt.norm(dim=-1, keepdim=True)
        left0[degenerate] = alt[degenerate]
        left0_norm[degenerate] = alt_norm[degenerate]
    left0 = left0 / left0_norm.clamp_min(eps)

    up0 = _normalise(torch.cross(forward, left0, dim=-1), eps=eps)
    cosang = (up0 * up_cam).sum(dim=-1).clamp(-1.0, 1.0)
    angle = torch.acos(cosang)
    sign = torch.sign((left0 * up_cam).sum(dim=-1))
    return angle * sign


def _candidate_pose_values(
    *,
    candidate_poses: np.ndarray,
    reference_pose: np.ndarray,
) -> dict[str, list[float]]:
    """Return candidate-pose diagnostics in the reference-rig frame."""

    poses = PoseTW(torch.as_tensor(candidate_poses, dtype=torch.float32))
    ref = PoseTW(torch.as_tensor(reference_pose, dtype=torch.float32))

    r_wc = poses.R
    t_wc = poses.t
    r_wr = ref.R
    t_wr = ref.t
    r_wr, t_wr = _broadcast_ref_pose(r_wr, t_wr, r_wc)

    r_rw = r_wr.transpose(-1, -2)
    t_rw = -(r_rw @ t_wr.unsqueeze(-1)).squeeze(-1)
    r_rc = r_rw @ r_wc
    t_rc = t_rw + (r_rw @ t_wc.unsqueeze(-1)).squeeze(-1)

    t_flat = t_rc.reshape(-1, 3)
    r_flat = r_rc.reshape(-1, 3, 3)
    radius = torch.linalg.vector_norm(t_flat, dim=-1)
    azimuth = torch.rad2deg(torch.atan2(t_flat[:, 0], t_flat[:, 2]))
    elevation = torch.rad2deg(torch.atan2(t_flat[:, 1], torch.linalg.vector_norm(t_flat[:, [0, 2]], dim=-1) + 1e-8))

    forward = r_flat[:, :, 2]
    up = r_flat[:, :, 1]
    yaw = torch.rad2deg(torch.atan2(forward[:, 0], forward[:, 2]))
    pitch = torch.rad2deg(torch.asin(_normalise(forward)[:, 1].clamp(-1.0, 1.0)))
    up_ref = torch.tensor([0.0, 1.0, 0.0], device=forward.device, dtype=forward.dtype)
    roll = torch.rad2deg(_roll_about_forward(forward=forward, up_cam=up, up_ref=up_ref))

    trace = r_flat[:, 0, 0] + r_flat[:, 1, 1] + r_flat[:, 2, 2]
    cos_angle = ((trace - 1.0) * 0.5).clamp(-1.0, 1.0)
    rot_delta = torch.rad2deg(torch.acos(cos_angle))

    return {
        "offset_x": t_flat[:, 0].detach().cpu().tolist(),
        "offset_y": t_flat[:, 1].detach().cpu().tolist(),
        "offset_z": t_flat[:, 2].detach().cpu().tolist(),
        "radius_m": radius.detach().cpu().tolist(),
        "azimuth_deg": azimuth.detach().cpu().tolist(),
        "elevation_deg": elevation.detach().cpu().tolist(),
        "yaw_deg": yaw.detach().cpu().tolist(),
        "pitch_deg": pitch.detach().cpu().tolist(),
        "roll_deg": roll.detach().cpu().tolist(),
        "rotation_delta_deg": rot_delta.detach().cpu().tolist(),
    }


def _component_for_memory_block(block_name: str) -> str | None:
    """Map one numeric block to a runtime memory component."""

    if block_name.startswith("backbone."):
        return "backbone"
    if block_name.startswith("vin."):
        return "vin_snippet"
    if block_name in {"oracle.candidate_count", "oracle.rri", *RRI_COMPONENT_BLOCKS}:
        return "oracle_rri"
    if block_name in POSE_CAMERA_BLOCKS:
        return "pose_camera"
    if block_name.startswith("oracle."):
        return "other_numeric"
    return None


def _row_block_nbytes(spec_shape: list[int] | None, dtype: str | None) -> int:
    """Estimate one row's byte size from a manifest block spec."""

    if not spec_shape or dtype is None:
        return 0
    row_shape = spec_shape[1:] if len(spec_shape) > 1 else []
    item_count = 1 if not row_shape else int(np.prod(row_shape, dtype=np.int64))
    return item_count * int(np.dtype(dtype).itemsize)


def _memory_diagnostics(
    *,
    shards: dict[str, VinOfflineShardSpec],
    records: list[VinOfflineIndexRecord],
) -> list[VinOfflineMemoryDiagnostic]:
    """Estimate runtime memory components for sampled records from manifest shapes."""

    by_component: dict[str, list[int]] = {
        "backbone": [],
        "oracle_rri": [],
        "vin_snippet": [],
        "pose_camera": [],
        "other_numeric": [],
    }
    for record in records:
        shard = shards[record.shard_id]
        row_totals = dict.fromkeys(by_component, 0)
        for block_name, spec in shard.blocks.items():
            if spec.kind != "zarr_array":
                continue
            component = _component_for_memory_block(block_name)
            if component is None:
                continue
            shape = [int(dim) for dim in spec.shape] if spec.shape is not None else None
            row_totals[component] += _row_block_nbytes(shape, spec.dtype)
        for component, total in row_totals.items():
            if total > 0:
                by_component[component].append(total)

    rows: list[VinOfflineMemoryDiagnostic] = []
    total_values: list[int] = []
    for values in by_component.values():
        if not total_values:
            total_values = [0] * len(values)
        if len(values) > len(total_values):
            total_values.extend([0] * (len(values) - len(total_values)))
        for idx, value in enumerate(values):
            total_values[idx] += value

    def _append(component: str, values: list[int]) -> None:
        if not values:
            return
        arr = np.asarray(values, dtype=np.float64) / float(1024**2)
        rows.append(
            VinOfflineMemoryDiagnostic(
                component=component,
                mean_mib=float(np.mean(arr)),
                median_mib=float(np.median(arr)),
                p95_mib=float(np.percentile(arr, 95)),
            ),
        )

    for component in ("backbone", "oracle_rri", "vin_snippet", "pose_camera", "other_numeric"):
        _append(component, by_component[component])
    _append("total", total_values)
    return rows


@dataclass(slots=True)
class _BackboneAccumulator:
    """Streaming moment accumulator for one backbone field."""

    field: str
    shape: list[int]
    numel: int
    sampled_rows: int = 0
    count: int = 0
    total: float = 0.0
    total_sq: float = 0.0
    total_abs: float = 0.0
    nz_count: int = 0

    def update(self, values: np.ndarray) -> None:
        """Accumulate one row of finite tensor values."""

        array = np.asarray(values)
        if not self.shape:
            self.shape = [int(dim) for dim in array.shape]
            self.numel = int(array.size)
        self.sampled_rows += 1
        finite = array.reshape(-1)
        finite = finite[np.isfinite(finite)]
        if finite.size == 0:
            return
        finite64 = finite.astype(np.float64, copy=False)
        self.count += int(finite64.size)
        self.total += float(np.sum(finite64))
        self.total_sq += float(np.sum(finite64 * finite64))
        self.total_abs += float(np.sum(np.abs(finite64)))
        self.nz_count += int(np.count_nonzero(np.abs(finite64) > 1e-6))

    def finish(self) -> VinOfflineBackboneDiagnostic:
        """Return the final diagnostic row."""

        if self.count <= 0:
            return VinOfflineBackboneDiagnostic(
                field=self.field,
                shape=self.shape,
                numel=self.numel,
                sampled_rows=self.sampled_rows,
                count=0,
                mean=None,
                std=None,
                abs_mean=None,
                nz_frac=None,
            )
        mean = self.total / float(self.count)
        variance = max(0.0, self.total_sq / float(self.count) - mean * mean)
        return VinOfflineBackboneDiagnostic(
            field=self.field,
            shape=self.shape,
            numel=self.numel,
            sampled_rows=self.sampled_rows,
            count=self.count,
            mean=mean,
            std=math.sqrt(variance),
            abs_mean=self.total_abs / float(self.count),
            nz_frac=self.nz_count / float(self.count),
        )


def _collect_backbone_diagnostics(
    *,
    reader: VinOfflineStoreReader,
    shards: dict[str, VinOfflineShardSpec],
    records: list[VinOfflineIndexRecord],
) -> list[VinOfflineBackboneDiagnostic]:
    """Collect streaming stats for sampled backbone numeric blocks."""

    accumulators: dict[str, _BackboneAccumulator] = {}
    for record in records:
        shard = shards[record.shard_id]
        for block_name, spec in shard.blocks.items():
            if spec.kind != "zarr_array" or not block_name.startswith("backbone."):
                continue
            field = block_name.removeprefix("backbone.")
            values = np.asarray(reader.read_numeric_block(record, block_name))
            acc = accumulators.get(field)
            if acc is None:
                acc = _BackboneAccumulator(
                    field=field,
                    shape=[int(dim) for dim in values.shape],
                    numel=int(values.size),
                )
                accumulators[field] = acc
            acc.update(values)
    return sorted((acc.finish() for acc in accumulators.values()), key=lambda item: item.field)


def summarize_vin_batch_shapes(batch: VinOracleBatch) -> dict[str, str]:
    """Summarize model-facing VIN batch shapes for diagnostics and logging.

    Args:
        batch: Unbatched or collated immutable-store VIN batch.

    Returns:
        Exact string mapping for tensor, camera, snippet, backbone, OBB, and
        trajectory shapes exposed by the diagnostic surface.
    """

    def _shape(value: object) -> str:
        if torch.is_tensor(value):
            return str(tuple(value.shape))  # type: ignore[attr-defined]
        return str(type(value).__name__)

    poses = batch.candidate_poses_world_cam.tensor()
    out: dict[str, str] = {
        "candidate_poses_world_cam": str(tuple(poses.shape)),
        "reference_pose_world_rig": str(tuple(batch.reference_pose_world_rig.tensor().shape)),
        "rri": _shape(batch.rri),
        "pm_dist_before": _shape(batch.pm_dist_before),
        "pm_dist_after": _shape(batch.pm_dist_after),
        "pm_acc_before": _shape(batch.pm_acc_before),
        "pm_comp_before": _shape(batch.pm_comp_before),
        "pm_acc_after": _shape(batch.pm_acc_after),
        "pm_comp_after": _shape(batch.pm_comp_after),
        "p3d_cameras.R": _shape(batch.p3d_cameras.R),
        "p3d_cameras.T": _shape(batch.p3d_cameras.T),
        "p3d_cameras.focal_length": _shape(batch.p3d_cameras.focal_length),
        "p3d_cameras.principal_point": _shape(batch.p3d_cameras.principal_point),
        "p3d_cameras.image_size": _shape(batch.p3d_cameras.image_size),
        "candidate_count": _shape(batch.resolved_candidate_count(device=poses.device)),
    }
    batch_size = None
    num_candidates = None
    if poses.ndim == 2:
        batch_size = 1
        num_candidates = int(poses.shape[0])
    elif poses.ndim == 3:
        batch_size = int(poses.shape[0])
        num_candidates = int(poses.shape[1])
    if batch_size is not None and num_candidates is not None:
        cam_count = int(batch.p3d_cameras.R.shape[0])
        if cam_count == batch_size * num_candidates:
            out["p3d_cameras.batch_mode"] = "flat (B*N)"
            out["p3d_cameras.R_grouped"] = str((batch_size, num_candidates, 3, 3))
            out["p3d_cameras.T_grouped"] = str((batch_size, num_candidates, 3))
            out["p3d_cameras.focal_length_grouped"] = str((batch_size, num_candidates, 2))
            out["p3d_cameras.principal_point_grouped"] = str((batch_size, num_candidates, 2))
            out["p3d_cameras.image_size_grouped"] = str((batch_size, num_candidates, 2))

    if is_vin_snippet_view_instance(batch.efm_snippet_view):
        out["vin_snippet.points_world"] = _shape(batch.efm_snippet_view.points_world)
        out["vin_snippet.lengths"] = _shape(batch.efm_snippet_view.lengths)
        out["vin_snippet.t_world_rig"] = _shape(batch.efm_snippet_view.t_world_rig.tensor())
    elif is_efm_snippet_view_instance(batch.efm_snippet_view):
        out["efm_snippet_view"] = "EfmSnippetView"
    elif batch.efm_snippet_view is None:
        out["efm_snippet_view"] = "None"

    if batch.backbone_out is not None:
        if is_dataclass(batch.backbone_out):
            items = [(item.name, getattr(batch.backbone_out, item.name)) for item in fields(batch.backbone_out)]
        else:
            items = list(vars(batch.backbone_out).items())
        for name, value in items:
            if torch.is_tensor(value):
                out[f"backbone.{name}"] = _shape(value)
    else:
        out["backbone"] = "None"

    if batch.gt_obbs is not None:
        out["gt_obbs.obbs"] = _shape(batch.gt_obbs.obbs)
        if batch.gt_obbs.probs is not None:
            out["gt_obbs.probs"] = _shape(batch.gt_obbs.probs)
    if batch.detected_obbs is not None:
        out["detected_obbs.obbs"] = _shape(batch.detected_obbs.obbs)
        if batch.detected_obbs.probs is not None:
            out["detected_obbs.probs"] = _shape(batch.detected_obbs.probs)
    if batch.trajectory is not None:
        if batch.trajectory.time_ns is not None:
            out["trajectory.time_ns"] = _shape(batch.trajectory.time_ns)
        if batch.trajectory.gravity_in_world is not None:
            out["trajectory.gravity_in_world"] = _shape(batch.trajectory.gravity_in_world)

    return out


def _batch_shape_preview(store: VinOfflineStoreConfig) -> dict[str, str]:
    """Return one lean VIN-batch shape preview for the store."""

    from .dataset import VinOfflineDatasetConfig

    dataset = VinOfflineDatasetConfig(
        store=store,
        split=None,
        limit=1,
        load_candidates=False,
        load_depths=False,
        load_candidate_pcs=False,
        return_format="vin_batch",
        map_location=torch.device("cpu"),
    ).setup_target()
    if len(dataset) == 0:
        return {}
    return summarize_vin_batch_shapes(dataset[0])


def collect_vin_offline_dataset_stats(
    store: VinOfflineStoreConfig,
    *,
    max_samples: int | None = 512,
) -> VinOfflineDatasetStats:
    """Collect coverage, shape, RRI, and memory diagnostics for a VIN store.

    Args:
        store: Immutable VIN offline store to inspect.
        max_samples: Optional cap on rows scanned for per-sample tensor stats.
            ``None`` scans the whole store.

    Returns:
        Store-level diagnostics suitable for tests, CLI output, or Streamlit.
    """

    reader = VinOfflineStoreReader(store)
    records = reader.sample_index
    scan_records = records if max_samples is None else records[: max(0, int(max_samples))]
    shards = _shards_by_id(reader)

    split_counts: dict[str, int] = {}
    for record in records:
        split_counts[record.split] = split_counts.get(record.split, 0) + 1

    candidate_counts: list[float] = []
    rri_values: list[float] = []
    vin_lengths: list[float] = []
    component_values: dict[str, list[float]] = {_component_key(name): [] for name in RRI_COMPONENT_BLOCKS}
    pose_values: dict[str, list[float]] = {
        "offset_x": [],
        "offset_y": [],
        "offset_z": [],
        "radius_m": [],
        "azimuth_deg": [],
        "elevation_deg": [],
        "yaw_deg": [],
        "pitch_deg": [],
        "roll_deg": [],
        "rotation_delta_deg": [],
    }
    sample_summaries: list[VinOfflineSampleDiagnostic] = []

    for record in scan_records:
        candidate_count = int(reader.read_numeric_block(record, "oracle.candidate_count").reshape(()))
        candidate_count = max(candidate_count, 0)
        candidate_counts.append(float(candidate_count))

        rri = _read_valid_vector(reader, record, "oracle.rri", candidate_count=candidate_count)
        row_rri_values = _finite_values(rri)
        rri_values.extend(row_rri_values)

        for block_name in RRI_COMPONENT_BLOCKS:
            if not _has_record_block(shards=shards, record=record, block_name=block_name):
                continue
            values = _read_valid_vector(reader, record, block_name, candidate_count=candidate_count)
            component_values[_component_key(block_name)].extend(_finite_values(values))

        if _has_record_block(shards=shards, record=record, block_name="oracle.candidate_poses_world_cam"):
            candidate_poses = np.asarray(
                reader.read_numeric_block(record, "oracle.candidate_poses_world_cam"),
                dtype=np.float32,
            )[:candidate_count]
            reference_pose = np.asarray(reader.read_numeric_block(record, "oracle.reference_pose_world_rig"))
            if candidate_poses.size:
                row_pose_values = _candidate_pose_values(
                    candidate_poses=candidate_poses,
                    reference_pose=reference_pose,
                )
                for key, values in row_pose_values.items():
                    pose_values[key].extend(float(value) for value in values)

        lengths = np.asarray(reader.read_numeric_block(record, "vin.lengths")).reshape(-1)
        row_vin_lengths = _finite_values(lengths)
        vin_lengths.extend(row_vin_lengths)
        sample_summaries.append(
            VinOfflineSampleDiagnostic(
                sample_index=int(record.sample_index),
                sample_key=compact_ase_atek_sample_id(record.sample_key),
                scene_id=record.scene_id,
                snippet_id=compact_ase_atek_sample_id(record.snippet_id),
                split=record.split,
                shard_id=record.shard_id,
                row=int(record.row),
                candidate_count=candidate_count,
                rri=_summary(row_rri_values),
                vin_points=_summary(row_vin_lengths),
            ),
        )

    numeric_bytes, block_shapes, block_diagnostics = _collect_block_diagnostics(reader)
    component_summaries = {name: _summary(values) for name, values in component_values.items()}
    pose_summaries = {name: _summary(values) for name, values in pose_values.items()}
    return VinOfflineDatasetStats(
        store_dir=store.store_dir.expanduser().resolve().as_posix(),
        version=int(reader.manifest.version),
        num_samples=len(records),
        sampled_samples=len(scan_records),
        split_counts=split_counts,
        num_scenes=len({record.scene_id for record in records}),
        num_snippets=len({(record.scene_id, record.snippet_id) for record in records}),
        materialized_blocks={
            "backbone": bool(reader.manifest.materialized_blocks.backbone),
            "depths": bool(reader.manifest.materialized_blocks.depths),
            "candidate_pcs": bool(reader.manifest.materialized_blocks.candidate_pcs),
        },
        candidate_count=_summary(candidate_counts),
        rri=_summary(rri_values),
        vin_points=_summary(vin_lengths),
        numeric_bytes=int(numeric_bytes),
        block_shapes=block_shapes,
        block_diagnostics=block_diagnostics,
        sample_summaries=sample_summaries,
        candidate_count_values=candidate_counts,
        rri_values=rri_values,
        vin_point_values=vin_lengths,
        rri_component_values=component_values,
        rri_component_summaries=component_summaries,
        candidate_pose_values=pose_values,
        candidate_pose_summaries=pose_summaries,
        memory_diagnostics=_memory_diagnostics(shards=shards, records=scan_records),
        backbone_diagnostics=_collect_backbone_diagnostics(reader=reader, shards=shards, records=scan_records),
        batch_shapes=_batch_shape_preview(store),
    )


_ARIA_SAMPLE_RE = re.compile(r"^(?P<sample>AriaSyntheticEnvironment_(?P<scene>[^_]+)_AtekDataSample_[^./]+)")


def _pair_from_tar_member(name: str) -> tuple[str, str] | None:
    """Infer ``(scene_id, snippet_id)`` from one WebDataset tar member name."""

    path = Path(name)
    basename = path.name
    if not basename or basename.startswith("."):
        return None
    token = basename.split(".", 1)[0]
    match = _ARIA_SAMPLE_RE.match(token)
    if match:
        return match.group("scene"), compact_ase_atek_sample_id(match.group("sample"))
    if len(path.parts) >= 2:
        scene_id = path.parts[-2]
        if scene_id:
            return scene_id, token
    return None


def _resolve_coverage_tar_paths(
    dataset_config: dict[str, Any],
    *,
    max_tars: int | None,
) -> list[Path]:
    """Resolve raw EFM tar paths from a stored dataset config snapshot."""

    explicit_urls = [str(url) for url in dataset_config.get("tar_urls", []) if str(url)]
    resolved: list[Path] = []
    if explicit_urls:
        for url in explicit_urls:
            if any(ch in url for ch in "*?[]"):
                resolved.extend(sorted(Path().glob(url)))
            else:
                resolved.append(Path(url).expanduser())
    else:
        paths_payload = dataset_config.get("paths")
        atek_variant = str(dataset_config.get("atek_variant", "efm"))
        scene_ids = [str(scene_id) for scene_id in dataset_config.get("scene_ids", [])]
        if isinstance(paths_payload, dict):
            root = _resolve_manifest_path(paths_payload.get("root", PROJECT_ROOT), PROJECT_ROOT)
            data_root = _resolve_manifest_path(paths_payload.get("data_root", ".data"), root)
            base = data_root / f"ase_{atek_variant}"
        else:
            base = PathConfig().resolve_atek_data_dir(atek_variant)
        if scene_ids:
            for scene_id in scene_ids:
                resolved.extend(sorted((base / scene_id).glob("*.tar")))
        else:
            resolved.extend(sorted(base.glob("**/*.tar")))

    tar_paths = [path for path in resolved if path.is_file() and path.stat().st_size > 0]
    tar_paths = sorted(dict.fromkeys(path.resolve() for path in tar_paths))
    if max_tars is not None and int(max_tars) > 0:
        tar_paths = tar_paths[: int(max_tars)]
    return tar_paths


def _resolve_manifest_path(value: object, root: Path) -> Path:
    """Resolve a manifest path snapshot without mutating global path config."""

    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _scan_tar_pairs(
    tar_paths: list[Path],
    *,
    progress_cb: Callable[[int, int], None] | None = None,
) -> set[tuple[str, str]]:
    """Scan raw tar headers for dataset snippet pairs."""

    pairs: set[tuple[str, str]] = set()
    total = len(tar_paths)
    for index, tar_path in enumerate(tar_paths, start=1):
        with tarfile.open(tar_path, mode="r:*") as archive:
            for member in archive:
                pair = _pair_from_tar_member(member.name)
                if pair is not None:
                    pairs.add(pair)
        if progress_cb is not None:
            progress_cb(index, total)
    return pairs


def collect_vin_offline_dataset_coverage(
    store: VinOfflineStoreConfig,
    *,
    max_tars: int | None = None,
    progress_cb: Callable[[int, int], None] | None = None,
) -> VinOfflineCoverageStats:
    """Compare raw ASE tar-header coverage against an immutable VIN store.

    Args:
        store: Immutable VIN offline store to inspect.
        max_tars: Optional cap on raw tar shards scanned.
        progress_cb: Optional callback receiving ``(done, total)`` tar counts.

    Returns:
        Coverage summary for Streamlit and tests.
    """

    reader = VinOfflineStoreReader(store)
    dataset_config = dict(reader.manifest.source.get("dataset_config", {}))
    tar_paths = _resolve_coverage_tar_paths(dataset_config, max_tars=max_tars)
    dataset_pairs = _scan_tar_pairs(tar_paths, progress_cb=progress_cb)
    store_pairs = {(record.scene_id, compact_ase_atek_sample_id(record.snippet_id)) for record in reader.sample_index}

    covered = dataset_pairs & store_pairs
    missing = dataset_pairs - store_pairs
    outside = store_pairs - dataset_pairs
    scenes = sorted({scene for scene, _ in dataset_pairs | store_pairs})
    per_scene: list[VinOfflineCoverageSceneDiagnostic] = []
    for scene_id in scenes:
        dataset_scene = {pair for pair in dataset_pairs if pair[0] == scene_id}
        store_scene = {pair for pair in store_pairs if pair[0] == scene_id}
        covered_scene = dataset_scene & store_scene
        coverage = None if not dataset_scene else float(len(covered_scene) / len(dataset_scene))
        per_scene.append(
            VinOfflineCoverageSceneDiagnostic(
                scene_id=scene_id,
                dataset_snippets=len(dataset_scene),
                store_snippets=len(store_scene),
                covered_snippets=len(covered_scene),
                missing_in_store=len(dataset_scene - store_scene),
                outside_dataset=len(store_scene - dataset_scene),
                coverage=coverage,
            ),
        )

    coverage_ratio = None if not dataset_pairs else float(len(covered) / len(dataset_pairs))
    return VinOfflineCoverageStats(
        store_dir=store.store_dir.expanduser().resolve().as_posix(),
        tar_shards_scanned=len(tar_paths),
        dataset_scenes=len({scene for scene, _ in dataset_pairs}),
        store_scenes=len({scene for scene, _ in store_pairs}),
        dataset_snippets=len(dataset_pairs),
        store_snippets=len(store_pairs),
        covered_snippets=len(covered),
        missing_in_store=len(missing),
        outside_dataset=len(outside),
        coverage=coverage_ratio,
        per_scene=per_scene,
        missing_examples=sorted(missing)[:50],
        outside_examples=sorted(outside)[:50],
    )


__all__ = [
    "NumericSummary",
    "VinOfflineBackboneDiagnostic",
    "VinOfflineBlockDiagnostic",
    "VinOfflineCoverageSceneDiagnostic",
    "VinOfflineCoverageStats",
    "VinOfflineDatasetStats",
    "VinOfflineMemoryDiagnostic",
    "VinOfflineSampleDiagnostic",
    "collect_vin_offline_dataset_coverage",
    "collect_vin_offline_dataset_stats",
]
