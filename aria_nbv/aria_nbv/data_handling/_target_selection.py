r"""Oracle target-task sampling for ARIA-NBV.

`OracleTargetTaskSampler` builds the data-generation target-task pool from
oracle GT OBBs. It is the source for rollout labels and target-conditioned
supervision. Identity validity is a GT OBB IoU/ambiguity contract; projected
visibility, support, confidence, distance, and downstream headroom are audit
fields, not first-pass eligibility gates.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TYPE_CHECKING

import torch
from efm3d.aria.aria_constants import ARIA_SNIPPET_T_WORLD_SNIPPET
from efm3d.aria.obb import ObbTW, obb_iou3d
from efm3d.aria.pose import PoseTW
from pydantic import Field, field_validator
from torch import Tensor

from ..utils import TargetConfig
from ..utils.semantic_names import SemanticNameMap, normalize_semantic_name_map, semantic_class_name
from ..vin.types import EvlBackboneOutput
from .efm_views import EfmSnippetView, VinSnippetView
from .offline.batch import CompactObbBlock

if TYPE_CHECKING:
    from .offline.dataset import VinOfflineSample


TARGET_INVALID_REASON_CODES: dict[str, int] = {
    "VALID": 0,
    "NO_ACTOR_VISIBLE_SOURCE": 1,
    "GT_SOURCE_DISALLOWED": 2,
    "PADDED_OBB": 3,
    "OBB_NONFINITE": 4,
    "OBB_EXTENT_INVALID": 5,
    "CONFIDENCE_TOO_LOW": 6,
    "NO_PROJECTED_VISIBILITY": 7,
    "PROJECTED_AREA_TOO_SMALL": 8,
    "TARGET_SUPPORT_TOO_LOW": 9,
    "TARGET_GT_UNMATCHED": 10,
    "TARGET_GT_AMBIGUOUS": 11,
}
"""Version-1 target invalidity reason bit positions."""

TARGET_INVALID_REASON_VERSION = "target-selection-invalidity-v1"
"""Version label for `TARGET_INVALID_REASON_CODES`."""

ORACLE_TARGET_TASK_SOURCE = "gt_obbs_oracle"
"""Source label for oracle target-task rows sampled from GT OBBs."""


@dataclass(frozen=True, slots=True)
class TargetCandidateRow:
    """One rollout target candidate and its oracle audit fields.

    This is the row-level DTO for the OBS-SEL/PRED-Q/GT-EVAL boundary. The
    actor-visible part is derived from detected or predicted OBBs: class id,
    confidence, world-frame OBB center/extents/pose, support counts, visibility
    score, support score, deficit score, eligibility, and the final selection
    score. `pose_world_object` is an EFM `PoseTW` payload flattened to 12
    values. `relative_pose_reference_object` is
    `T_reference_world @ T_world_object`, also flattened to 12 values.

    `source_index` points back into the padded source OBB table after flattening
    valid rows; `target_row_id` is the selector-local dense row id. GT match
    fields are oracle/evaluation audit fields only. They are filled after
    actor-visible selection and must not be fed to actor policies in V1.
    """

    scene_id: str | None
    """Dataset scene identifier, or ``None`` when the source omits scene metadata."""

    snippet_id: str | None
    """Snippet identifier within `scene_id`, or ``None`` when unavailable."""

    source: str
    """OBB source name used to construct this row."""

    source_index: int
    """Row index in the source OBB table before padded rows are removed."""

    target_row_id: int
    """Dense selector-local row identifier persisted with target audit data."""

    target_id: str
    """Stable target identifier derived from snippet, source, semantic, and row identity."""

    sem_id: int
    """Semantic class identifier carried by the source OBB."""

    inst_id: int
    """Instance identifier carried by the source OBB."""

    class_name: str
    """Human-readable semantic class name, with a deterministic fallback for unknown ids."""

    confidence: float
    """OBB confidence retained for frozen lineage/audit columns."""

    center_world: tuple[float, float, float]
    """OBB center ``(x, y, z)`` in the world frame, metres."""

    extents: tuple[float, float, float]
    """Full OBB side lengths ``(x, y, z)`` in object axes, metres."""

    pose_world_object: tuple[float, ...]
    """Flattened 12-value EFM `PoseTW` transform from object to world frame."""

    relative_pose_reference_object: tuple[float, ...]
    """Flattened 12-value transform from object to the snippet reference frame."""

    projected_area_pixels: float
    """Largest clipped OBB projection area, square pixels."""

    projected_area_fraction: float
    """Projected area divided by the configured image-area normalizer."""

    semidense_support_count: int
    """Number of sampled semidense world points inside the scaled OBB."""

    evl_support_count: int
    """Number of positive EVL support points inside the scaled OBB."""

    effective_support_count: float
    """Semidense count plus the configured weight times the EVL count."""

    visibility_score: float
    """Projected-visibility audit factor, or a sentinel for oracle-selected tasks."""

    support_score: float
    """Support sufficiency audit factor, or a sentinel for oracle-selected tasks."""

    deficit_score: float
    """Unsaturated-support audit factor, or a sentinel for oracle-selected tasks."""

    score: float
    """Selection score retained for lineage; oracle tasks use identity IoU."""

    eligible: bool
    """Whether the row is valid for target-RRI labeling."""

    invalid_reason_bitset: int
    """Bitset of `TARGET_INVALID_REASON_CODES` values observed for this row."""

    primary_invalid_reason: int
    """Canonical numeric reason selected from `invalid_reason_bitset`."""

    selected_rank: int | None = None
    """Zero-based policy rank, or ``None`` when the row was not selected."""

    selection_probability: float | None = None
    """Conditional selection probability, or ``None`` before policy selection."""

    selection_log_probability: float | None = None
    """Natural logarithm of `selection_probability`, when defined."""

    selection_entropy: float | None = None
    """Policy entropy at the selection step, in nats, when stochastic selection is used."""

    gt_label_valid: bool = False
    """Whether post-selection oracle matching produced an unambiguous GT label."""

    gt_target_row_id: int | None = None
    """Matched GT OBB source row, or ``None`` when no valid match exists."""

    gt_target_id: str | None = None
    """Stable identifier of the matched GT target, or ``None`` when unmatched."""

    gt_match_iou: float | None = None
    """Sampled 3D IoU of the best GT match, or ``None`` when matching was unavailable."""

    gt_match_score: float | None = None
    """Geometry-only score of the best GT match, or ``None`` when unavailable."""

    gt_match_status: str = "not_requested"
    """Stable audit status describing whether and how GT matching completed."""


class TargetTaskIdentityStatus(StrEnum):
    """Identity-gate status for oracle target-task rows."""

    MATCHED = "matched"
    """The target passes geometry, IoU, and ambiguity thresholds."""

    AMBIGUOUS = "ambiguous_identity"
    """The best and second-best identity overlaps are insufficiently separated."""

    UNMATCHED = "unmatched_identity"
    """No valid identity overlap reaches the configured IoU threshold."""

    INVALID_GEOMETRY = "invalid_geometry"
    """The target OBB has non-finite or non-positive geometry."""


@dataclass(frozen=True, slots=True)
class OracleTargetTaskRow:
    """One oracle target-task row for rollout/data-generation labeling.

    The sampler creates these rows from GT OBBs, not from actor-visible target
    discovery. `identity_valid` is the first-pass task-pool gate: the source OBB
    must have finite positive geometry, pass `min_identity_iou`, and have a
    top-1/top-2 identity gap above `identity_ambiguity_gap`. Descriptor fields
    such as projected area, semidense/EVL support, and confidence are preserved
    as audit signals only and must not decide first-pass eligibility.

    Headroom fields are intentionally optional. Target tasks survive sampling
    even when later rollout evidence proves little or no recoverable target
    gain; headroom filtering belongs to downstream label/evaluation reports.
    """

    scene_id: str | None
    """Dataset scene identifier, or ``None`` when the source omits scene metadata."""

    snippet_id: str | None
    """Snippet identifier within `scene_id`, or ``None`` when unavailable."""

    source: str
    """Oracle OBB source name used to construct this target task."""

    source_index: int
    """Row index in the oracle GT OBB table before padded rows are removed."""

    target_row_id: int
    """Dense task-pool row identifier for this snippet."""

    target_id: str
    """Stable target identifier derived from snippet and GT object identity."""

    sem_id: int
    """Semantic class identifier carried by the GT OBB."""

    inst_id: int
    """Instance identifier carried by the GT OBB."""

    class_name: str
    """Human-readable semantic class name, with a deterministic fallback for unknown ids."""

    confidence: float
    """GT OBB confidence retained for audit; it does not gate task eligibility."""

    center_world: tuple[float, float, float]
    """GT OBB center ``(x, y, z)`` in the world frame, metres."""

    extents: tuple[float, float, float]
    """Full GT OBB side lengths ``(x, y, z)`` in object axes, metres."""

    pose_world_object: tuple[float, ...]
    """Flattened 12-value EFM `PoseTW` transform from object to world frame."""

    relative_pose_reference_object: tuple[float, ...]
    """Flattened 12-value transform from object to the snippet reference frame."""

    projected_area_pixels: float
    """Largest clipped OBB projection area, square pixels, retained for audit."""

    projected_area_fraction: float
    """Projected area divided by the configured image-area normalizer."""

    semidense_support_count: int
    """Number of sampled semidense world points inside the scaled GT OBB."""

    evl_support_count: int
    """Number of positive EVL support points inside the scaled GT OBB."""

    effective_support_count: float
    """Semidense count plus the configured weight times the EVL count."""

    identity_iou: float | None
    """Largest sampled 3D self-identity IoU, or ``None`` when geometry is invalid."""

    identity_second_iou: float | None
    """Second-largest identity IoU, or ``None`` when identity evaluation failed."""

    identity_ambiguity_gap: float | None
    """Difference between the largest and second-largest identity IoUs."""

    identity_status: str
    """Serialized `TargetTaskIdentityStatus` produced by the identity gate."""

    identity_valid: bool
    """Whether geometry, IoU, and ambiguity checks admit this task to sampling."""

    selected_rank: int | None = None
    """Zero-based rank in the seeded capped sample, or ``None`` when unselected."""

    selection_probability: float | None = None
    """Inclusion probability under uniform capped sampling, when selected."""

    selection_seed: int | None = None
    """Seed used to select this row, or ``None`` for an unseeded sample."""

    target_root_error: float | None = None
    """Root target reconstruction error supplied by downstream oracle scoring."""

    max_candidate_gain: float | None = None
    """Largest candidate target gain supplied by downstream oracle scoring."""

    headroom_band: str | None = None
    """Downstream headroom stratum, or ``None`` before oracle scoring."""


@dataclass(frozen=True, slots=True)
class OracleTargetTaskSweepCell:
    """Coverage count for one oracle identity-threshold cell."""

    min_identity_iou: float
    """Minimum best-match identity IoU applied in this audit cell."""

    identity_ambiguity_gap: float
    """Required top-1/top-2 identity IoU gap applied in this audit cell."""

    identity_valid_count: int
    """Number of task rows passing both thresholds."""

    identity_valid_fraction: float
    """Fraction of all task rows passing both thresholds, in ``[0, 1]``."""


@dataclass(frozen=True, slots=True)
class OracleTargetTaskSamplingResult:
    """Oracle target-task pool and seeded capped sample for one snippet."""

    rows: tuple[OracleTargetTaskRow, ...]
    """All non-padded GT OBB rows interpreted as candidate target tasks."""

    identity_valid_rows: tuple[OracleTargetTaskRow, ...]
    """Rows admitted by the configured geometry and identity gate."""

    selected_rows: tuple[OracleTargetTaskRow, ...]
    """Uniformly sampled identity-valid rows with sampling audit fields populated."""

    max_targets_per_sample: int
    """Configured upper bound on selected target tasks per snippet."""

    seed: int | None
    """Random seed used for capped sampling, or ``None`` for an unseeded generator."""

    source: str | None
    """Oracle OBB source name, or ``None`` when no GT source is available."""

    identity_iou_thresholds: tuple[float, ...]
    """IoU thresholds evaluated by `threshold_sweep`."""

    identity_ambiguity_gaps: tuple[float, ...]
    """Top-1/top-2 IoU gaps evaluated by `threshold_sweep`."""

    warnings: tuple[str, ...] = ()
    """Non-fatal source and sampling diagnostics."""

    def diagnostic_summary(self) -> dict[str, int | float]:
        """Return compact counts for target-task pool and sample audits."""

        summary: dict[str, int | float] = {
            "num_rows": len(self.rows),
            "num_identity_valid": len(self.identity_valid_rows),
            "num_selected": len(self.selected_rows),
            "num_ambiguous_identity": sum(
                row.identity_status == TargetTaskIdentityStatus.AMBIGUOUS.value for row in self.rows
            ),
            "num_invalid_geometry": sum(
                row.identity_status == TargetTaskIdentityStatus.INVALID_GEOMETRY.value for row in self.rows
            ),
            "num_missing_projection": sum(1 for row in self.rows if row.projected_area_pixels <= 0.0),
        }
        if self.rows:
            summary["mean_projected_area_pixels"] = sum(row.projected_area_pixels for row in self.rows) / float(
                len(self.rows)
            )
            summary["mean_effective_support_count"] = sum(row.effective_support_count for row in self.rows) / float(
                len(self.rows)
            )
        return summary

    def threshold_sweep(self) -> tuple[OracleTargetTaskSweepCell, ...]:
        """Report identity-valid coverage under configured threshold cells."""

        total = float(len(self.rows))
        cells: list[OracleTargetTaskSweepCell] = []
        for min_iou in self.identity_iou_thresholds:
            for gap in self.identity_ambiguity_gaps:
                count = sum(
                    1
                    for row in self.rows
                    if row.identity_iou is not None
                    and row.identity_ambiguity_gap is not None
                    and row.identity_iou >= min_iou
                    and row.identity_ambiguity_gap > gap
                    and row.identity_status != TargetTaskIdentityStatus.INVALID_GEOMETRY.value
                )
                cells.append(
                    OracleTargetTaskSweepCell(
                        min_identity_iou=float(min_iou),
                        identity_ambiguity_gap=float(gap),
                        identity_valid_count=int(count),
                        identity_valid_fraction=0.0 if total == 0.0 else float(count) / total,
                    )
                )
        return tuple(cells)


@dataclass(slots=True)
class _TargetSource:
    """Resolved OBB source block before target rows are built.

    `obbs` is still an EFM `ObbTW` padded tensor, commonly shaped `(1, K, 34)`
    for a single snippet. `_world_obbs_for_sample` selects the latest valid OBB
    slice, applies the snippet-to-world transform when present, and leaves
    padded rows in place until `_valid_obb_data_with_source_indices` records
    their source indices.
    """

    source: str
    """Name of the resolved detected, predicted, or GT OBB source."""

    obbs: ObbTW
    """Padded EFM `ObbTW` payload, typically shaped ``(1, K, 34)`` per snippet."""

    sem_id_to_name: SemanticNameMap | None = None
    """Optional semantic-id name mapping associated with `obbs`."""


class OracleTargetTaskSamplerConfig(TargetConfig["OracleTargetTaskSampler"]):
    """Configuration for `OracleTargetTaskSampler`."""

    @property
    def target_type(self) -> type["OracleTargetTaskSampler"]:
        """Factory target for `BaseConfig.setup_target`."""

        return OracleTargetTaskSampler

    max_targets_per_sample: int = Field(default=3, ge=1)
    """Maximum identity-valid GT target tasks sampled per snippet."""

    seed: int | None = 0
    """Seed for uniform capped sampling without replacement."""

    min_identity_iou: float = Field(default=0.25, ge=0.0, le=1.0)
    """Minimum self-identity IoU for an oracle target-task row."""

    identity_ambiguity_gap: float = Field(default=0.05, ge=0.0)
    """Required top-1/top-2 IoU gap for an unambiguous target identity."""

    identity_iou_samples: int = Field(default=8, ge=1)
    """Samples per dimension for EFM's sampled OBB IoU fallback."""

    identity_iou_thresholds: tuple[float, ...] = (0.1, 0.25, 0.5)
    """Diagnostic IoU thresholds reported by `threshold_sweep`."""

    identity_ambiguity_gaps: tuple[float, ...] = (0.0, 0.05, 0.1)
    """Diagnostic ambiguity gaps reported by `threshold_sweep`."""

    projected_area_normalizer_pixels: float = Field(default=240.0 * 240.0, gt=0.0)
    """Image-area normalizer used for projected-area audit fractions."""

    projected_area_image_width_px: float = Field(default=240.0, gt=0.0)
    """Image width used to clip projected OBB boxes for audit fields."""

    projected_area_image_height_px: float = Field(default=240.0, gt=0.0)
    """Image height used to clip projected OBB boxes for audit fields."""

    evl_support_weight: float = Field(default=1.0, ge=0.0)
    """Weight applied to EVL support points in audit support counts."""

    obb_support_scale: float = Field(default=1.0, gt=0.0)
    """OBB scale used when counting semidense/EVL support audit points."""

    max_support_points: int = Field(default=20000, ge=1)
    """Maximum support points inspected per snippet, using deterministic prefix truncation."""

    @field_validator("identity_iou_thresholds", "identity_ambiguity_gaps")
    @classmethod
    def _validate_threshold_tuple(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        if not value:
            raise ValueError("threshold tuple must contain at least one value")
        if any(not torch.isfinite(torch.tensor(float(item))) or float(item) < 0.0 for item in value):
            raise ValueError("threshold tuple values must be finite and non-negative")
        return tuple(float(item) for item in value)


class OracleTargetTaskSampler:
    """Sample oracle GT target tasks for rollout/data-generation labeling."""

    def __init__(self, config: OracleTargetTaskSamplerConfig) -> None:
        """Initialize the oracle sampler.

        Args:
            config: Identity thresholds, audit-field settings, and sampling cap.
        """

        self.config = config

    def sample(self, sample: "VinOfflineSample") -> OracleTargetTaskSamplingResult:
        """Build and uniformly sample the oracle target-task pool.

        Args:
            sample: VIN offline sample carrying ``gt_obbs`` and optional
                actor-visible audit sources.

        Returns:
            Full GT target-task table, identity-valid pool, and capped seeded
            sample. Support, projection, and later headroom fields are audit
            descriptors and do not filter first-pass target-task eligibility.
        """

        from .offline.dataset import VinOfflineSample

        if not isinstance(sample, VinOfflineSample):
            raise TypeError("OracleTargetTaskSampler expects VinOfflineSample input.")
        warnings: list[str] = []
        gt_block = _compact_obb_block(sample.gt_obbs)
        if gt_block is None:
            warnings.append("Oracle target-task sampling requested, but sample has no GT OBB block.")
            return OracleTargetTaskSamplingResult(
                rows=(),
                identity_valid_rows=(),
                selected_rows=(),
                max_targets_per_sample=self.config.max_targets_per_sample,
                seed=self.config.seed,
                source=None,
                identity_iou_thresholds=self.config.identity_iou_thresholds,
                identity_ambiguity_gaps=self.config.identity_ambiguity_gaps,
                warnings=tuple(warnings),
            )

        gt_world = _world_obbs_for_sample(gt_block[0], sample)
        rows = self._build_rows(sample, world_obbs=gt_world, sem_id_to_name=gt_block[1])
        identity_valid = tuple(row for row in rows if row.identity_valid)
        selected = self._sample_rows(identity_valid)
        selected_by_id = {row.target_id: row for row in selected}
        rows = tuple(selected_by_id.get(row.target_id, row) for row in rows)
        identity_valid = tuple(selected_by_id.get(row.target_id, row) for row in identity_valid)

        return OracleTargetTaskSamplingResult(
            rows=rows,
            identity_valid_rows=identity_valid,
            selected_rows=selected,
            max_targets_per_sample=self.config.max_targets_per_sample,
            seed=self.config.seed,
            source=ORACLE_TARGET_TASK_SOURCE,
            identity_iou_thresholds=self.config.identity_iou_thresholds,
            identity_ambiguity_gaps=self.config.identity_ambiguity_gaps,
            warnings=tuple(warnings),
        )

    def _build_rows(
        self,
        sample: "VinOfflineSample",
        *,
        world_obbs: ObbTW,
        sem_id_to_name: SemanticNameMap | None,
    ) -> tuple[OracleTargetTaskRow, ...]:
        valid_data, source_indices = _valid_obb_data_with_source_indices(world_obbs)
        if valid_data.numel() == 0:
            return ()
        gt_obbs = ObbTW(valid_data)
        semidense_points = _semidense_points(sample, max_points=self.config.max_support_points)
        evl_points, evl_counts = _evl_support_points(sample, max_points=self.config.max_support_points)
        reference_pose = _pose_on_device(_reference_pose_world_rig(sample), device=valid_data.device)
        scene_id = _first_scalar_string(sample.scene_id)
        snippet_id = _first_scalar_string(sample.snippet_id)

        rows: list[OracleTargetTaskRow] = []
        for row_index in range(int(gt_obbs.shape[0])):
            obb = ObbTW(gt_obbs._data[row_index])
            sem_id = int(obb.sem_id.reshape(-1)[0].item())
            inst_id = int(obb.inst_id.reshape(-1)[0].item())
            confidence = float(obb.prob.reshape(-1)[0].item())
            extents_t = obb.bb3_diagonal.detach().cpu().reshape(-1).to(dtype=torch.float32)
            center_t = obb.bb3_center_world.detach().cpu().reshape(-1).to(dtype=torch.float32)
            pose_world = obb.T_world_object.tensor().detach().cpu().reshape(-1).to(dtype=torch.float32)
            relative_pose = (reference_pose.inverse() @ obb.T_world_object).tensor().detach().cpu().reshape(-1)
            projected_area = _max_projected_area(obb, config=self.config)
            projected_fraction = projected_area / float(self.config.projected_area_normalizer_pixels)
            semidense_count = _points_inside_count(obb, semidense_points, scale=self.config.obb_support_scale)
            evl_count = _points_inside_count(
                obb,
                evl_points,
                scale=self.config.obb_support_scale,
                positive_counts=evl_counts,
            )
            effective_support = float(semidense_count) + float(self.config.evl_support_weight) * float(evl_count)
            identity = self._identity_gate(gt_obbs, row_index=row_index)
            source_index = int(source_indices[row_index])
            target_id = _target_id(
                scene_id=scene_id,
                snippet_id=snippet_id,
                source=ORACLE_TARGET_TASK_SOURCE,
                sem_id=sem_id,
                inst_id=inst_id,
                source_index=source_index,
            )
            rows.append(
                OracleTargetTaskRow(
                    scene_id=scene_id,
                    snippet_id=snippet_id,
                    source=ORACLE_TARGET_TASK_SOURCE,
                    source_index=source_index,
                    target_row_id=source_index,
                    target_id=target_id,
                    sem_id=sem_id,
                    inst_id=inst_id,
                    class_name=_class_name(sem_id, sem_id_to_name),
                    confidence=confidence,
                    center_world=_float_tuple(center_t, length=3),  # type: ignore[assignment]
                    extents=_float_tuple(extents_t, length=3),  # type: ignore[assignment]
                    pose_world_object=_float_tuple(pose_world),
                    relative_pose_reference_object=_float_tuple(relative_pose),
                    projected_area_pixels=float(projected_area),
                    projected_area_fraction=float(projected_fraction),
                    semidense_support_count=int(semidense_count),
                    evl_support_count=int(evl_count),
                    effective_support_count=float(effective_support),
                    identity_iou=identity[0],
                    identity_second_iou=identity[1],
                    identity_ambiguity_gap=identity[2],
                    identity_status=identity[3].value,
                    identity_valid=identity[3] == TargetTaskIdentityStatus.MATCHED,
                )
            )
        return tuple(rows)

    def _identity_gate(
        self,
        gt_obbs: ObbTW,
        *,
        row_index: int,
    ) -> tuple[float | None, float | None, float | None, TargetTaskIdentityStatus]:
        obb = ObbTW(gt_obbs._data[row_index].unsqueeze(0))
        if not _obb_geometry_valid(obb):
            return None, None, None, TargetTaskIdentityStatus.INVALID_GEOMETRY

        ious: list[float] = []
        for candidate_index in range(int(gt_obbs.shape[0])):
            candidate = ObbTW(gt_obbs._data[candidate_index].unsqueeze(0))
            if not _obb_geometry_valid(candidate):
                continue
            iou = _strict_obb_iou(obb, candidate, samples=self.config.identity_iou_samples)
            if iou is None:
                return None, None, None, TargetTaskIdentityStatus.UNMATCHED
            ious.append(iou)
        if not ious:
            return None, None, None, TargetTaskIdentityStatus.UNMATCHED

        ious.sort(reverse=True)
        best = float(ious[0])
        second = float(ious[1]) if len(ious) > 1 else 0.0
        gap = float(best - second)
        if best < self.config.min_identity_iou:
            return best, second, gap, TargetTaskIdentityStatus.UNMATCHED
        if gap <= self.config.identity_ambiguity_gap:
            return best, second, gap, TargetTaskIdentityStatus.AMBIGUOUS
        return best, second, gap, TargetTaskIdentityStatus.MATCHED

    def _sample_rows(self, rows: tuple[OracleTargetTaskRow, ...]) -> tuple[OracleTargetTaskRow, ...]:
        if not rows:
            return ()
        target_count = min(int(self.config.max_targets_per_sample), len(rows))
        generator = torch.Generator(device="cpu")
        if self.config.seed is not None:
            generator.manual_seed(int(self.config.seed))
        permutation = torch.randperm(len(rows), generator=generator).tolist()
        probability = float(target_count) / float(len(rows))
        selected: list[OracleTargetTaskRow] = []
        for rank, row_index in enumerate(permutation[:target_count]):
            selected.append(
                replace(
                    rows[int(row_index)],
                    selected_rank=rank,
                    selection_probability=probability,
                    selection_seed=self.config.seed,
                )
            )
        return tuple(selected)


def _compact_obb_block(value: CompactObbBlock | ObbTW | Tensor | None) -> tuple[ObbTW, SemanticNameMap | None] | None:
    if value is None:
        return None
    obbs = value.obbs if isinstance(value, CompactObbBlock) else value
    if obbs is None:
        return None
    sem_id_to_name = normalize_semantic_name_map(value.sem_id_to_name) if isinstance(value, CompactObbBlock) else None
    if isinstance(obbs, ObbTW):
        return obbs, sem_id_to_name
    return ObbTW(torch.as_tensor(obbs, dtype=torch.float32)), sem_id_to_name


def target_gt_obb_world(row: TargetCandidateRow, sample: "VinOfflineSample") -> ObbTW:
    """Resolve the matched GT target OBB in world coordinates.

    Args:
        row: Actor-visible target row after GT matching.
        sample: VIN offline sample carrying ``gt_obbs`` and snippet transform.

    Returns:
        A single-row `ObbTW` in world coordinates.

    Raises:
        ValueError: If the row is not label-valid or the matched GT row cannot
            be resolved.
    """

    if not row.gt_label_valid or row.gt_target_row_id is None:
        raise ValueError("Target row is not GT-label valid; refusing to build target RRI crop.")
    gt_block = _compact_obb_block(sample.gt_obbs)
    if gt_block is None:
        raise ValueError("Target RRI crop requires sample.gt_obbs.")
    gt_world = _world_obbs_for_sample(gt_block[0], sample)
    gt_data, gt_source_indices = _valid_obb_data_with_source_indices(gt_world)
    try:
        gt_index = gt_source_indices.index(int(row.gt_target_row_id))
    except ValueError as exc:
        raise ValueError(f"Matched GT target row {row.gt_target_row_id} is not present in sample.gt_obbs.") from exc
    return ObbTW(gt_data[gt_index].unsqueeze(0))


def _world_obbs_for_sample(obbs: ObbTW, sample: "VinOfflineSample") -> ObbTW:
    selected = _latest_valid_obb_slice(obbs)
    transform = _snippet_t_world_snippet(sample)
    if transform is None:
        return selected
    return selected.transform(transform)


def _latest_valid_obb_slice(obbs: ObbTW) -> ObbTW:
    data = obbs.tensor().detach().cpu().to(dtype=torch.float32)
    if data.ndim == 1:
        data = data.unsqueeze(0)
    if data.ndim == 2:
        return ObbTW(data)
    rows = data.reshape(-1, data.shape[-2], data.shape[-1])
    for index in range(rows.shape[0] - 1, -1, -1):
        candidate = ObbTW(rows[index])
        if bool((~candidate.get_padding_mask()).any().item()):
            return candidate
    return ObbTW(rows[-1])


def _valid_obb_data_with_source_indices(obbs: ObbTW) -> tuple[Tensor, list[int]]:
    data = obbs.tensor().detach().cpu().to(dtype=torch.float32)
    if data.ndim == 1:
        data = data.unsqueeze(0)
    flat = data.reshape(-1, data.shape[-1])
    flat_obbs = ObbTW(flat)
    valid = (~flat_obbs.get_padding_mask()).reshape(-1)
    source_indices = torch.nonzero(valid, as_tuple=False).reshape(-1).tolist()
    return flat[valid], [int(index) for index in source_indices]


def _sample_snippet_view(sample: "VinOfflineSample") -> EfmSnippetView | VinSnippetView:
    return sample.efm_snippet_view if sample.efm_snippet_view is not None else sample.vin_snippet


def _snippet_t_world_snippet(sample: "VinOfflineSample") -> PoseTW | None:
    snippet = _sample_snippet_view(sample)
    if isinstance(snippet, EfmSnippetView):
        value = snippet.efm.get(ARIA_SNIPPET_T_WORLD_SNIPPET)
        if isinstance(value, PoseTW):
            return PoseTW(value.tensor().reshape(-1, 12)[:1])
        if torch.is_tensor(value):
            return PoseTW(value.reshape(-1, 12)[:1])
    if isinstance(snippet, VinSnippetView):
        poses = snippet.t_world_rig.tensor().reshape(-1, 12)
        if poses.shape[0] > 0:
            return PoseTW(poses[:1])
    return None


def _reference_pose_world_rig(sample: "VinOfflineSample") -> PoseTW:
    return PoseTW(sample.oracle.reference_pose_world_rig.tensor().reshape(-1, 12)[:1])


def _pose_on_device(pose: PoseTW, *, device: torch.device) -> PoseTW:
    """Return ``pose`` on ``device`` so PoseTW composition does not mix devices."""

    return PoseTW(pose.tensor().detach().to(device=device))


def _semidense_points(sample: "VinOfflineSample", *, max_points: int) -> Tensor:
    snippet = _sample_snippet_view(sample)
    if isinstance(snippet, VinSnippetView):
        return _valid_prefix_points(snippet.points_world, snippet.lengths, max_points=max_points)
    if isinstance(snippet, EfmSnippetView):
        semidense = snippet.semidense
        points = semidense.points_world
        lengths = semidense.lengths.to(device=points.device)
        max_len = points.shape[1]
        mask = torch.arange(max_len, device=points.device).unsqueeze(0) < lengths.clamp_max(max_len).unsqueeze(-1)
        flat = points[..., :3][mask]
        finite = torch.isfinite(flat).all(dim=-1)
        return flat[finite][:max_points].detach().cpu().to(dtype=torch.float32)
    return torch.zeros((0, 3), dtype=torch.float32)


def _valid_prefix_points(points: Tensor, lengths: Tensor, *, max_points: int) -> Tensor:
    pts = points.detach().cpu().to(dtype=torch.float32)
    length = int(torch.as_tensor(lengths).reshape(-1)[0].item()) if torch.as_tensor(lengths).numel() else pts.shape[0]
    if pts.ndim != 2 or pts.shape[-1] < 3:
        return torch.zeros((0, 3), dtype=torch.float32)
    pts = pts[: max(0, min(length, pts.shape[0])), :3]
    finite = torch.isfinite(pts).all(dim=-1)
    return pts[finite][:max_points]


def _evl_support_points(sample: "VinOfflineSample", *, max_points: int) -> tuple[Tensor, Tensor | None]:
    backbone = sample.backbone_out
    if not isinstance(backbone, EvlBackboneOutput) or backbone.pts_world is None:
        return torch.zeros((0, 3), dtype=torch.float32), None
    points = backbone.pts_world.detach().cpu().to(dtype=torch.float32)
    if points.ndim == 3:
        points = points[0]
    points = points.reshape(-1, points.shape[-1])[:, :3]
    finite = torch.isfinite(points).all(dim=-1)
    counts = None
    if backbone.counts is not None:
        count_values = backbone.counts.detach().cpu().reshape(-1)
        if count_values.shape[0] == points.shape[0]:
            counts = count_values[finite][:max_points]
    return points[finite][:max_points], counts


def _points_inside_count(obb: ObbTW, points: Tensor, *, scale: float, positive_counts: Tensor | None = None) -> int:
    if points.numel() == 0:
        return 0
    inside = obb.points_inside_bb3(points.to(dtype=torch.float32), scale_obb=float(scale))
    if positive_counts is not None:
        inside = inside & (positive_counts.to(dtype=torch.float32) > 0)
    return int(inside.sum().item())


def _max_projected_area(obb: ObbTW, *, config: OracleTargetTaskSamplerConfig) -> float:
    areas: list[float] = []
    image_width = float(config.projected_area_image_width_px)
    image_height = float(config.projected_area_image_height_px)
    for camera_id in range(3):
        bb2 = obb.bb2(camera_id).detach().cpu().reshape(-1, 4).to(dtype=torch.float32)
        x1 = bb2[:, 0].clamp(min=0.0, max=image_width)
        x2 = bb2[:, 1].clamp(min=0.0, max=image_width)
        y1 = bb2[:, 2].clamp(min=0.0, max=image_height)
        y2 = bb2[:, 3].clamp(min=0.0, max=image_height)
        width = (x2 - x1).clamp_min(0)
        height = (y2 - y1).clamp_min(0)
        area = width * height
        if area.numel():
            areas.append(float(area.max().item()))
    return max(areas) if areas else 0.0


def _strict_obb_iou(pred: ObbTW, gt: ObbTW, *, samples: int) -> float | None:
    try:
        value = obb_iou3d(pred, gt, samp_per_dim=int(samples)).reshape(-1)[0]
    except Exception:
        return None
    if not bool(torch.isfinite(value).item()):
        return None
    return float(value.item())


def _obb_geometry_valid(obb: ObbTW) -> bool:
    data = obb.tensor().reshape(-1)
    extents = obb.bb3_diagonal.reshape(-1)
    return (
        bool(torch.isfinite(data).all().item())
        and bool(torch.isfinite(extents).all().item())
        and not bool((extents <= 0).any().item())
    )


def _class_name(sem_id: int, sem_id_to_name: SemanticNameMap | None) -> str:
    return semantic_class_name(sem_id, sem_id_to_name)


def _target_id(
    *,
    scene_id: str | None,
    snippet_id: str | None,
    source: str,
    sem_id: int,
    inst_id: int,
    source_index: int,
) -> str:
    return f"{scene_id or 'scene'}:{snippet_id or 'snippet'}:{source}:sem={sem_id}:inst={inst_id}:idx={source_index}"


def _first_scalar_string(value: str | list[str] | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return None if not value else str(value[0])
    return str(value)


def _float_tuple(values: Tensor, *, length: int | None = None) -> tuple[float, ...]:
    flat = values.detach().cpu().reshape(-1).to(dtype=torch.float32)
    if length is not None:
        flat = flat[:length]
    return tuple(float(value.item()) for value in flat)


__all__ = [
    "ORACLE_TARGET_TASK_SOURCE",
    "OracleTargetTaskRow",
    "OracleTargetTaskSampler",
    "OracleTargetTaskSamplerConfig",
    "OracleTargetTaskSamplingResult",
    "OracleTargetTaskSweepCell",
    "TARGET_INVALID_REASON_CODES",
    "TARGET_INVALID_REASON_VERSION",
    "TargetCandidateRow",
    "TargetTaskIdentityStatus",
    "target_gt_obb_world",
]
