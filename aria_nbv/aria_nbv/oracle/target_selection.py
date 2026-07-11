r"""Oracle target-task sampling for ARIA-NBV.

`OracleTargetTaskSampler` builds the data-generation target-task pool from
oracle GT OBBs. It is the source for rollout labels and target-conditioned
supervision. First-pass task admission is intentionally limited to finite,
positive GT OBB geometry. Confidence and downstream headroom are audit fields,
not first-pass eligibility gates. Retired actor-selection projection and
support columns use their frozen zero sentinel in generated lineage.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TYPE_CHECKING

import torch
from efm3d.aria.aria_constants import ARIA_SNIPPET_T_WORLD_SNIPPET
from efm3d.aria.obb import ObbTW
from efm3d.aria.pose import PoseTW
from pydantic import Field
from torch import Tensor

from ..data_handling.efm_views import EfmSnippetView, VinSnippetView
from ..data_handling.offline.batch import CompactObbBlock
from ..targets import TargetDescriptor
from ..utils import TargetConfig
from ..utils.semantic_names import SemanticNameMap, normalize_semantic_name_map, semantic_class_name

if TYPE_CHECKING:
    from ..data_handling.offline.dataset import VinOfflineSample


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
    """Compatibility row for frozen rollout target and GT-audit columns.

    Oracle task generation fills this wide row before persistence. Candidate
    generation receives only `TargetDescriptor`; source indices, instance
    identity, GT match fields, invalidity, and retired audit sentinels must not
    cross that actor-safe boundary.
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
    """Selection score retained for lineage; oracle tasks use ``NaN``."""

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


class TargetTaskIdentityStatus(StrEnum):
    """Task-admission status for oracle target-task rows."""

    MATCHED = "matched"
    """The GT target has finite positive geometry and is admitted."""

    AMBIGUOUS = "ambiguous_identity"
    """Legacy persisted status retained for reason-code decoding."""

    UNMATCHED = "unmatched_identity"
    """Legacy persisted status retained for reason-code decoding."""

    INVALID_GEOMETRY = "invalid_geometry"
    """The target OBB has non-finite or non-positive geometry."""


class OracleTargetTaskSelectionPolicy(StrEnum):
    """Selection policies for admitted oracle target tasks."""

    UNIFORM_WITHOUT_REPLACEMENT = "uniform_without_replacement"
    """Seeded capped uniform sampling without replacement."""


@dataclass(frozen=True, slots=True)
class OracleTargetTaskRow:
    """One oracle target-task row for rollout/data-generation labeling.

    The sampler creates these rows from GT OBBs, not from actor-visible target
    discovery. `identity_valid` is the first-pass task-pool gate: the source GT
    OBB must have finite positive geometry. `descriptor` composes the
    actor-safe semantic and geometric instruction. Privileged identity and
    confidence stay on the task; retired projection/support columns remain
    frozen persistence sentinels and never decide eligibility.

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

    descriptor: TargetDescriptor
    """Actor-safe semantic and geometric target instruction."""

    inst_id: int
    """Instance identifier carried by the GT OBB."""

    confidence: float
    """GT OBB confidence retained for audit; it does not gate task eligibility."""

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
    """Deprecated identity score slot retained as ``None`` for lineage compatibility."""

    identity_second_iou: float | None
    """Deprecated identity score slot retained as ``None`` for lineage compatibility."""

    identity_ambiguity_gap: float | None
    """Deprecated identity score slot retained as ``None`` for lineage compatibility."""

    identity_status: str
    """Serialized `TargetTaskIdentityStatus` produced by the geometry gate."""

    identity_valid: bool
    """Whether finite positive geometry admits this task to sampling."""

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

    @property
    def sem_id(self) -> int:
        """Semantic class identifier from the actor-safe descriptor."""

        return self.descriptor.sem_id

    @property
    def class_name(self) -> str:
        """Human-readable semantic class name from the descriptor."""

        return self.descriptor.class_name

    @property
    def center_world(self) -> tuple[float, float, float]:
        """Descriptor target center in world coordinates, metres."""

        return self.descriptor.center_world

    @property
    def extents(self) -> tuple[float, float, float]:
        """Descriptor full side lengths in object axes, metres."""

        return self.descriptor.extents_m

    @property
    def pose_world_object(self) -> tuple[float, ...]:
        """Descriptor object-to-world pose as 12 flattened values."""

        return self.descriptor.pose_world_object

    @property
    def relative_pose_reference_object(self) -> tuple[float, ...]:
        """Descriptor object pose in the snippet reference frame."""

        return self.descriptor.relative_pose_reference_object


@dataclass(frozen=True, slots=True)
class OracleTargetTaskSamplingResult:
    """Oracle target-task pool and seeded capped sample for one snippet."""

    rows: tuple[OracleTargetTaskRow, ...]
    """All non-padded GT OBB rows interpreted as candidate target tasks."""

    identity_valid_rows: tuple[OracleTargetTaskRow, ...]
    """Rows admitted by finite positive GT geometry."""

    selected_rows: tuple[OracleTargetTaskRow, ...]
    """Uniformly sampled geometry-valid rows with sampling audit fields populated."""

    max_targets_per_sample: int
    """Configured upper bound on selected target tasks per snippet."""

    seed: int | None
    """Random seed used for capped sampling, or ``None`` for an unseeded generator."""

    source: str | None
    """Oracle OBB source name, or ``None`` when no GT source is available."""

    warnings: tuple[str, ...] = ()
    """Non-fatal source and sampling diagnostics."""

    def diagnostic_summary(self) -> dict[str, int | float]:
        """Return compact counts for target-task pool and sample audits."""

        summary: dict[str, int | float] = {
            "num_rows": len(self.rows),
            "num_identity_valid": len(self.identity_valid_rows),
            "num_selected": len(self.selected_rows),
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
    """Maximum geometry-valid GT target tasks sampled per snippet."""

    seed: int | None = 0
    """Seed for uniform capped sampling without replacement."""

    policy: OracleTargetTaskSelectionPolicy = OracleTargetTaskSelectionPolicy.UNIFORM_WITHOUT_REPLACEMENT
    """Policy used to select admitted GT target tasks."""


class OracleTargetTaskSampler:
    """Sample oracle GT target tasks for rollout/data-generation labeling."""

    def __init__(self, config: OracleTargetTaskSamplerConfig) -> None:
        """Initialize the oracle sampler.

        Args:
            config: Audit-field settings, selection policy, and sampling cap.
        """

        self.config = config

    def sample(self, sample: "VinOfflineSample") -> OracleTargetTaskSamplingResult:
        """Build and uniformly sample the oracle target-task pool.

        Args:
            sample: VIN offline sample carrying the privileged ``gt_obbs``
                task source.

        Returns:
            Full GT target-task table, geometry-valid pool, and capped seeded
            sample. Support, projection, and later headroom fields are audit
            descriptors and do not filter first-pass target-task eligibility.
        """

        from ..data_handling.offline.dataset import VinOfflineSample

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
            pose_world = obb.T_world_object.tensor().detach().cpu().reshape(-1).to(dtype=torch.float32)
            relative_pose = (reference_pose.inverse() @ obb.T_world_object).tensor().detach().cpu().reshape(-1)
            geometry_valid = _obb_geometry_valid(obb)
            identity_status = (
                TargetTaskIdentityStatus.MATCHED if geometry_valid else TargetTaskIdentityStatus.INVALID_GEOMETRY
            )
            source_index = int(source_indices[row_index])
            target_id = _target_id(
                scene_id=scene_id,
                snippet_id=snippet_id,
                source=ORACLE_TARGET_TASK_SOURCE,
                sem_id=sem_id,
                inst_id=inst_id,
                source_index=source_index,
            )
            descriptor = TargetDescriptor(
                sem_id=sem_id,
                class_name=_class_name(sem_id, sem_id_to_name),
                pose_world_object=_float_tuple(pose_world),
                extents_m=_float_tuple(extents_t, length=3),  # type: ignore[arg-type]
                relative_pose_reference_object=_float_tuple(relative_pose),
            )
            rows.append(
                OracleTargetTaskRow(
                    scene_id=scene_id,
                    snippet_id=snippet_id,
                    source=ORACLE_TARGET_TASK_SOURCE,
                    source_index=source_index,
                    target_row_id=source_index,
                    target_id=target_id,
                    descriptor=descriptor,
                    inst_id=inst_id,
                    confidence=confidence,
                    projected_area_pixels=0.0,
                    projected_area_fraction=0.0,
                    semidense_support_count=0,
                    evl_support_count=0,
                    effective_support_count=0.0,
                    identity_iou=None,
                    identity_second_iou=None,
                    identity_ambiguity_gap=None,
                    identity_status=identity_status.value,
                    identity_valid=identity_status == TargetTaskIdentityStatus.MATCHED,
                )
            )
        return tuple(rows)

    def _sample_rows(self, rows: tuple[OracleTargetTaskRow, ...]) -> tuple[OracleTargetTaskRow, ...]:
        if not rows:
            return ()
        if self.config.policy != OracleTargetTaskSelectionPolicy.UNIFORM_WITHOUT_REPLACEMENT:
            raise ValueError(f"Unsupported oracle target-task selection policy: {self.config.policy}")
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


def target_candidate_row_from_task(row: OracleTargetTaskRow) -> TargetCandidateRow:
    """Adapt a privileged task to the frozen rollout target-lineage DTO."""

    reason_bitset, primary_reason = _oracle_target_invalidity(row)
    gt_valid = row.identity_status == TargetTaskIdentityStatus.MATCHED.value
    return TargetCandidateRow(
        scene_id=row.scene_id,
        snippet_id=row.snippet_id,
        source=row.source,
        source_index=row.source_index,
        target_row_id=row.target_row_id,
        target_id=row.target_id,
        sem_id=row.sem_id,
        inst_id=row.inst_id,
        class_name=row.class_name,
        confidence=row.confidence,
        center_world=row.center_world,
        extents=row.extents,
        pose_world_object=row.pose_world_object,
        relative_pose_reference_object=row.relative_pose_reference_object,
        projected_area_pixels=row.projected_area_pixels,
        projected_area_fraction=row.projected_area_fraction,
        semidense_support_count=row.semidense_support_count,
        evl_support_count=row.evl_support_count,
        effective_support_count=row.effective_support_count,
        visibility_score=0.0,
        support_score=0.0,
        deficit_score=0.0,
        score=float("nan"),
        eligible=gt_valid,
        invalid_reason_bitset=reason_bitset,
        primary_invalid_reason=primary_reason,
        selected_rank=row.selected_rank,
        selection_probability=row.selection_probability,
        gt_label_valid=gt_valid,
        gt_target_row_id=row.source_index if gt_valid else None,
        gt_target_id=row.target_id if gt_valid else None,
        gt_match_iou=None,
        gt_match_score=None,
        gt_match_status="matched" if gt_valid else row.identity_status,
    )


def target_descriptor_from_candidate_row(row: TargetCandidateRow) -> TargetDescriptor:
    """Return the actor-safe descriptor portion of a privileged target row."""

    return TargetDescriptor(
        sem_id=row.sem_id,
        class_name=row.class_name,
        pose_world_object=row.pose_world_object,
        extents_m=row.extents,
        relative_pose_reference_object=row.relative_pose_reference_object,
    )


def _oracle_target_invalidity(row: OracleTargetTaskRow) -> tuple[int, int]:
    if row.identity_status == TargetTaskIdentityStatus.MATCHED.value:
        return 1 << TARGET_INVALID_REASON_CODES["VALID"], TARGET_INVALID_REASON_CODES["VALID"]
    if row.identity_status == TargetTaskIdentityStatus.AMBIGUOUS.value:
        reason = TARGET_INVALID_REASON_CODES["TARGET_GT_AMBIGUOUS"]
    elif row.identity_status == TargetTaskIdentityStatus.INVALID_GEOMETRY.value:
        reason = TARGET_INVALID_REASON_CODES["OBB_EXTENT_INVALID"]
    else:
        reason = TARGET_INVALID_REASON_CODES["TARGET_GT_UNMATCHED"]
    return 1 << reason, reason


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
    "OracleTargetTaskSelectionPolicy",
    "OracleTargetTaskSamplingResult",
    "TARGET_INVALID_REASON_CODES",
    "TARGET_INVALID_REASON_VERSION",
    "TargetCandidateRow",
    "TargetTaskIdentityStatus",
    "target_candidate_row_from_task",
    "target_descriptor_from_candidate_row",
]
