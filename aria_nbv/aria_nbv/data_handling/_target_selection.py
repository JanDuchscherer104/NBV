r"""Actor-visible target selection for target-conditioned ARIA-NBV.

This module implements the V1 `OBS-SEL / PRED-Q / GT-EVAL` target contract.
V1 resolves observed or predicted OBB records by actor-visible evidence only:
OBB confidence, clipped projected visible area, semidense support, EVL support,
and support deficit. GT OBBs are allowed only in explicit V0
sanity/upper-bound mode or after selection for label/evaluation matching.

The selector stores both actor-facing descriptors and oracle-side audit fields.
Target matching is accepted only when the best GT match passes configured IoU
or score thresholds and the top-1/top-2 gap is unambiguous. Unmatched,
ambiguous, empty-crop, or no-source cases are target-invalid states, not low
target-RRI examples.

Theory:
    Target handling is a three-stage contract. First, hard eligibility checks
    confidence, finite OBB geometry, clipped projected visibility policy, and
    effective actor-visible support. Second, an interest score ranks or samples
    eligible rows; the current baseline interest remains
    $S_e=p_e s_e^{\mathrm{vis}}s_e^{\mathrm{sup}}s_e^{\mathrm{def}}$ while
    stratified target sampling is deferred to scale audits. Third, GT matching
    is a deterministic oracle/evaluation association based on semantic
    compatibility, 3D IoU, and top-1/top-2 ambiguity. Support and visibility
    are eligibility/audit fields, not GT-match ranking multipliers.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TYPE_CHECKING

import torch
from efm3d.aria.aria_constants import ARIA_SNIPPET_T_WORLD_SNIPPET
from efm3d.aria.obb import ObbTW, obb_iou3d
from efm3d.aria.pose import PoseTW
from pydantic import Field
from torch import Tensor

from ..utils import TargetConfig
from ..utils.semantic_names import SemanticNameMap, normalize_semantic_name_map, semantic_class_name
from ..vin.types import EvlBackboneOutput
from .efm_views import EfmSnippetView, VinSnippetView
from .vin_oracle_types import CompactObbBlock

if TYPE_CHECKING:
    from ._offline_dataset import VinOfflineSample


class TargetSelectionPolicy(StrEnum):
    """Supported top-K target selection policies."""

    GREEDY_TOP_K = "greedy_top_k"
    TEMPERATURE_SOFTMAX_TOP_K = "temperature_softmax_top_k"


class TargetSourceMode(StrEnum):
    """Selector source protocol."""

    V1_ACTOR_VISIBLE = "v1_actor_visible"
    V0_GT_SANITY = "v0_gt_sanity"


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


@dataclass(frozen=True, slots=True)
class TargetCandidateRow:
    """One actor-visible target candidate and its oracle audit fields.

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
    snippet_id: str | None
    source: str
    source_index: int
    target_row_id: int
    target_id: str
    sem_id: int
    inst_id: int
    class_name: str
    confidence: float
    center_world: tuple[float, float, float]
    extents: tuple[float, float, float]
    pose_world_object: tuple[float, ...]
    relative_pose_reference_object: tuple[float, ...]
    projected_area_pixels: float
    projected_area_fraction: float
    semidense_support_count: int
    evl_support_count: int
    effective_support_count: float
    visibility_score: float
    support_score: float
    deficit_score: float
    score: float
    eligible: bool
    invalid_reason_bitset: int
    primary_invalid_reason: int
    selected_rank: int | None = None
    selection_probability: float | None = None
    selection_log_probability: float | None = None
    selection_entropy: float | None = None
    gt_label_valid: bool = False
    gt_target_row_id: int | None = None
    gt_target_id: str | None = None
    gt_match_iou: float | None = None
    gt_match_score: float | None = None
    gt_match_status: str = "not_requested"


@dataclass(frozen=True, slots=True)
class TargetSelectionResult:
    """Ranked target table and selected top-K rows for one snippet.

    `rows` contains every non-padded candidate target that could be interpreted
    from the resolved actor-visible source. `ranked_rows` filters that table to
    eligible rows and sorts it by the configured selection score. `selected_rows`
    is the top-K or stochastic policy output used to condition candidate
    generation and target-RRI labeling.

    `source` records the resolved target source, for example `detected_obbs` or
    `backbone.obb_pred_viz`. In V1, GT OBBs can appear only in GT match fields;
    if GT was the selection source, `source_mode` must be `v0_gt_sanity`.
    """

    rows: tuple[TargetCandidateRow, ...]
    ranked_rows: tuple[TargetCandidateRow, ...]
    selected_rows: tuple[TargetCandidateRow, ...]
    k: int
    policy: str
    source_mode: str
    source: str | None
    seed: int | None
    temperature: float | None
    warnings: tuple[str, ...] = ()
    reason_code_version: str = TARGET_INVALID_REASON_VERSION

    def diagnostic_summary(self) -> dict[str, int | float]:
        """Return compact stratified counts for selector threshold audits."""

        summary: dict[str, int | float] = {
            "num_rows": len(self.rows),
            "num_ranked": len(self.ranked_rows),
            "num_selected": len(self.selected_rows),
            "num_gt_label_valid": sum(1 for row in self.selected_rows if row.gt_label_valid),
            "num_gt_unmatched": sum(1 for row in self.selected_rows if row.gt_match_status == "unmatched_gt"),
            "num_gt_ambiguous": sum("ambiguous" in row.gt_match_status for row in self.selected_rows),
            "num_duplicate_gt": sum(row.gt_match_status == "ambiguous_pred_to_gt" for row in self.selected_rows),
            "num_missing_projection": sum(1 for row in self.rows if row.projected_area_pixels <= 0.0),
        }
        if self.rows:
            summary["mean_confidence"] = sum(row.confidence for row in self.rows) / float(len(self.rows))
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
    obbs: ObbTW
    sem_id_to_name: SemanticNameMap | None = None


class TargetSelectorConfig(TargetConfig["ActorVisibleTargetSelector"]):
    """Configuration for `ActorVisibleTargetSelector`."""

    @property
    def target_type(self) -> type["ActorVisibleTargetSelector"]:
        """Factory target for `BaseConfig.setup_target`."""

        return ActorVisibleTargetSelector

    k: int = Field(default=3, ge=1)
    """Number of selected targets to materialize."""

    policy: TargetSelectionPolicy = TargetSelectionPolicy.GREEDY_TOP_K
    """Top-K policy applied after hard target eligibility masking."""

    source_mode: TargetSourceMode = TargetSourceMode.V1_ACTOR_VISIBLE
    """Whether to use V1 actor-visible sources or the V0 GT sanity source."""

    seed: int | None = 0
    """Seed for stochastic target selection policies."""

    temperature: float = Field(default=1.0, gt=0.0)
    """Softmax temperature for ``temperature_softmax_top_k``."""

    min_confidence: float = Field(default=0.2, ge=0.0)
    """Minimum observed/predicted OBB confidence for V1 eligibility."""

    min_projected_area_pixels: float = Field(default=16.0, gt=0.0)
    """Minimum clipped visible 2D area over RGB/SLAM OBB boxes."""

    require_projected_visibility: bool = False
    """Whether missing 2D OBB boxes hard-mask otherwise supported 3D target records."""

    projected_area_normalizer_pixels: float = Field(default=240.0 * 240.0, gt=0.0)
    """Image-area normalizer used for projected-area fractions."""

    projected_area_image_width_px: float = Field(default=240.0, gt=0.0)
    """Image width used to clip projected OBB boxes for visibility scoring."""

    projected_area_image_height_px: float = Field(default=240.0, gt=0.0)
    """Image height used to clip projected OBB boxes for visibility scoring."""

    projected_area_full_score_fraction: float = Field(default=0.05, gt=0.0)
    """Projected-area fraction that saturates the visibility score."""

    min_support_points: int = Field(default=3, ge=1)
    """Minimum effective semidense plus weighted EVL points inside the target OBB."""

    support_saturation_points: int = Field(default=128, ge=1)
    """Support count at which the deficit score reaches zero."""

    evl_support_weight: float = Field(default=1.0, ge=0.0)
    """Weight applied to EVL support points when computing effective support."""

    missing_projection_visibility_score: float = Field(default=0.35, ge=0.0, le=1.0)
    """Visibility multiplier for supported targets without any actor-visible 2D projection."""

    obb_support_scale: float = Field(default=1.0, gt=0.0)
    """OBB scale used when counting semidense/EVL points inside a target."""

    max_support_points: int = Field(default=20000, ge=1)
    """Maximum support points inspected per snippet, using deterministic prefix truncation."""

    match_gt: bool = True
    """Match selected V1 targets to GT OBBs after ranking when GT is available."""

    min_gt_iou: float = Field(default=0.1, ge=0.0)
    """Minimum sampled 3D OBB IoU for a GT target match."""

    min_gt_match_score: float = Field(default=0.05, ge=0.0)
    """Minimum geometry-only GT match score for V1 label acceptance."""

    gt_iou_samples: int = Field(default=8, ge=1)
    """Samples per dimension for EFM's sampled OBB IoU fallback."""

    gt_ambiguity_margin: float = Field(default=0.02, ge=0.0)
    """IoU margin below which competing GT matches are considered ambiguous."""


class ActorVisibleTargetSelector:
    """Select top-K target OBBs from actor-visible snippet evidence."""

    def __init__(self, config: TargetSelectorConfig) -> None:
        """Initialize the selector.

        Args:
            config: Selection thresholds, policy, and source mode.
        """

        self.config = config

    def select(self, sample: "VinOfflineSample") -> TargetSelectionResult:
        """Select top-K targets from a VIN offline sample.

        Args:
            sample: Object carrying ``detected_obbs`` or ``backbone_out`` for
                V1, plus optional ``gt_obbs`` for post-selection matching.

        Returns:
            Ranked target table and selected top-K rows.
        """

        from ._offline_dataset import VinOfflineSample

        if not isinstance(sample, VinOfflineSample):
            raise TypeError("ActorVisibleTargetSelector expects VinOfflineSample input.")
        warnings: list[str] = []
        source = self._resolve_source(sample, warnings=warnings)
        if source is None:
            return TargetSelectionResult(
                rows=(),
                ranked_rows=(),
                selected_rows=(),
                k=self.config.k,
                policy=self.config.policy.value,
                source_mode=self.config.source_mode.value,
                source=None,
                seed=self.config.seed,
                temperature=self._policy_temperature(),
                warnings=tuple(warnings),
            )

        world_obbs = _world_obbs_for_sample(source.obbs, sample)
        rows = self._build_rows(sample, source=source, world_obbs=world_obbs)
        ranked = tuple(sorted((row for row in rows if row.eligible), key=_ranking_key))
        selected = self._select_rows(ranked)
        selected = self._match_selected_to_gt(selected, sample=sample, pred_obbs_world=world_obbs)
        selected_by_id = {row.target_id: row for row in selected}
        rows = tuple(selected_by_id.get(row.target_id, row) for row in rows)
        ranked = tuple(selected_by_id.get(row.target_id, row) for row in ranked)

        return TargetSelectionResult(
            rows=rows,
            ranked_rows=ranked,
            selected_rows=selected,
            k=self.config.k,
            policy=self.config.policy.value,
            source_mode=self.config.source_mode.value,
            source=source.source,
            seed=self.config.seed,
            temperature=self._policy_temperature(),
            warnings=tuple(warnings),
        )

    def _resolve_source(self, sample: "VinOfflineSample", *, warnings: list[str]) -> _TargetSource | None:
        """Resolve the OBB source allowed by the selector mode.

        V0 sanity mode intentionally reads GT OBBs. V1 first prefers
        actor-visible detected OBBs, then EVL-predicted OBBs from the cached
        backbone output. GT OBBs are refused in V1 and only surfaced as a
        warning so they remain GT-EVAL labels, not OBS-SEL input.

        Args:
            sample: Data container exposing GT, detected, and backbone OBB
                sources.
            warnings: Mutable warning list propagated to the selection result.

        Returns:
            The resolved source block, or ``None`` when no permitted source is
            available.
        """

        if self.config.source_mode == TargetSourceMode.V0_GT_SANITY:
            gt = _compact_obb_block(sample.gt_obbs)
            if gt is None:
                warnings.append("V0 GT target selection requested, but sample has no GT OBB block.")
                return None
            return _TargetSource(source="gt_obbs_v0_sanity", obbs=gt[0], sem_id_to_name=gt[1])

        detected = _compact_obb_block(sample.detected_obbs)
        if detected is not None:
            return _TargetSource(source="detected_obbs", obbs=detected[0], sem_id_to_name=detected[1])

        backbone = sample.backbone_out
        if isinstance(backbone, EvlBackboneOutput):
            obb = backbone.obb_pred_viz if backbone.obb_pred_viz is not None else backbone.obb_pred
            if obb is not None:
                source_name = "backbone.obb_pred_viz" if backbone.obb_pred_viz is not None else "backbone.obb_pred"
                return _TargetSource(source=source_name, obbs=obb, sem_id_to_name=backbone.obb_pred_sem_id_to_name)

        if sample.gt_obbs is not None:
            warnings.append("V1 target selection refused GT OBBs because they are oracle-only labels/evaluation data.")
        warnings.append("No actor-visible detected/predicted OBB source was available for target selection.")
        return None

    def _build_rows(
        self,
        sample: "VinOfflineSample",
        *,
        source: _TargetSource,
        world_obbs: ObbTW,
    ) -> tuple[TargetCandidateRow, ...]:
        valid_data, source_indices = _valid_obb_data_with_source_indices(world_obbs)
        if valid_data.numel() == 0:
            return ()
        obbs = ObbTW(valid_data)
        semidense_points = _semidense_points(sample, max_points=self.config.max_support_points)
        evl_points, evl_counts = _evl_support_points(sample, max_points=self.config.max_support_points)
        reference_pose = _pose_on_device(_reference_pose_world_rig(sample), device=valid_data.device)
        scene_id = _first_scalar_string(sample.scene_id)
        snippet_id = _first_scalar_string(sample.snippet_id)

        rows: list[TargetCandidateRow] = []
        for row_index in range(int(obbs.shape[0])):
            obb = ObbTW(obbs._data[row_index])
            sem_id = int(obb.sem_id.reshape(-1)[0].item())
            inst_id = int(obb.inst_id.reshape(-1)[0].item())
            confidence = float(obb.prob.reshape(-1)[0].item())
            extents_t = obb.bb3_diagonal.detach().cpu().reshape(-1).to(dtype=torch.float32)
            center_t = obb.bb3_center_world.detach().cpu().reshape(-1).to(dtype=torch.float32)
            pose_world = obb.T_world_object.tensor().detach().cpu().reshape(-1).to(dtype=torch.float32)
            relative_pose = (reference_pose.inverse() @ obb.T_world_object).tensor().detach().cpu().reshape(-1)
            projected_area = _max_projected_area(obb, config=self.config)
            projected_fraction = projected_area / float(self.config.projected_area_normalizer_pixels)
            visibility_score = _visibility_score(
                projected_area=projected_area,
                projected_fraction=projected_fraction,
                config=self.config,
            )
            semidense_count = _points_inside_count(obb, semidense_points, scale=self.config.obb_support_scale)
            evl_count = _points_inside_count(
                obb,
                evl_points,
                scale=self.config.obb_support_scale,
                positive_counts=evl_counts,
            )
            effective_support = float(semidense_count) + float(self.config.evl_support_weight) * float(evl_count)
            support_score = max(0.0, min(float(effective_support / float(self.config.min_support_points)), 1.0))
            deficit_score = 1.0 - max(
                0.0, min(float(effective_support / float(self.config.support_saturation_points)), 1.0)
            )
            reason_bitset = _target_reason_bitset(
                obb=obb,
                confidence=confidence,
                projected_area=projected_area,
                effective_support=effective_support,
                config=self.config,
            )
            eligible = reason_bitset == (1 << TARGET_INVALID_REASON_CODES["VALID"])
            score = confidence * visibility_score * support_score * deficit_score if eligible else float("nan")
            source_index = int(source_indices[row_index])
            target_id = _target_id(
                scene_id=scene_id,
                snippet_id=snippet_id,
                source=source.source,
                sem_id=sem_id,
                inst_id=inst_id,
                source_index=source_index,
            )
            rows.append(
                TargetCandidateRow(
                    scene_id=scene_id,
                    snippet_id=snippet_id,
                    source=source.source,
                    source_index=source_index,
                    target_row_id=source_index,
                    target_id=target_id,
                    sem_id=sem_id,
                    inst_id=inst_id,
                    class_name=_class_name(sem_id, source.sem_id_to_name),
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
                    visibility_score=float(visibility_score),
                    support_score=float(support_score),
                    deficit_score=float(deficit_score),
                    score=float(score),
                    eligible=bool(eligible),
                    invalid_reason_bitset=int(reason_bitset),
                    primary_invalid_reason=_primary_reason(reason_bitset),
                )
            )
        return tuple(rows)

    def _select_rows(self, ranked_rows: tuple[TargetCandidateRow, ...]) -> tuple[TargetCandidateRow, ...]:
        if not ranked_rows:
            return ()
        if self.config.policy == TargetSelectionPolicy.GREEDY_TOP_K:
            return tuple(
                replace(row, selected_rank=rank, selection_probability=1.0, selection_log_probability=0.0)
                for rank, row in enumerate(ranked_rows[: self.config.k])
            )
        return self._sample_rows_without_replacement(ranked_rows)

    def _sample_rows_without_replacement(
        self, ranked_rows: tuple[TargetCandidateRow, ...]
    ) -> tuple[TargetCandidateRow, ...]:
        scores = torch.tensor([row.score for row in ranked_rows], dtype=torch.float32)
        remaining = torch.ones(scores.shape[0], dtype=torch.bool)
        selected: list[TargetCandidateRow] = []
        generator = torch.Generator(device="cpu")
        if self.config.seed is not None:
            generator.manual_seed(int(self.config.seed))

        for rank in range(min(self.config.k, len(ranked_rows))):
            logits = scores / float(self.config.temperature)
            masked_logits = torch.where(remaining, logits, torch.full_like(logits, float("-inf")))
            probabilities = torch.softmax(masked_logits, dim=0)
            entropy = -torch.sum(probabilities[remaining] * torch.log(probabilities[remaining].clamp_min(1e-12)))
            sampled = int(torch.multinomial(probabilities, 1, replacement=False, generator=generator).item())
            selected.append(
                replace(
                    ranked_rows[sampled],
                    selected_rank=rank,
                    selection_probability=float(probabilities[sampled].item()),
                    selection_log_probability=float(torch.log(probabilities[sampled].clamp_min(1e-12)).item()),
                    selection_entropy=float(entropy.item()),
                )
            )
            remaining[sampled] = False
            if not bool(remaining.any().item()):
                break
        return tuple(selected)

    def _match_selected_to_gt(
        self,
        selected_rows: tuple[TargetCandidateRow, ...],
        *,
        sample: "VinOfflineSample",
        pred_obbs_world: ObbTW,
    ) -> tuple[TargetCandidateRow, ...]:
        if not selected_rows:
            return ()
        if self.config.source_mode == TargetSourceMode.V0_GT_SANITY:
            return tuple(
                replace(
                    row,
                    gt_label_valid=True,
                    gt_target_row_id=row.target_row_id,
                    gt_target_id=row.target_id,
                    gt_match_iou=1.0,
                    gt_match_score=1.0,
                    gt_match_status="v0_gt_input",
                )
                for row in selected_rows
            )
        if not self.config.match_gt:
            return selected_rows
        gt_block = _compact_obb_block(sample.gt_obbs)
        if gt_block is None:
            return tuple(replace(row, gt_match_status="missing_gt") for row in selected_rows)

        gt_world = _world_obbs_for_sample(gt_block[0], sample)
        gt_data, gt_source_indices = _valid_obb_data_with_source_indices(gt_world)
        pred_data, pred_source_indices = _valid_obb_data_with_source_indices(pred_obbs_world)
        if gt_data.numel() == 0:
            return tuple(replace(row, gt_match_status="missing_gt") for row in selected_rows)

        gt_obbs = ObbTW(gt_data)
        pred_obbs = ObbTW(pred_data)
        pred_index_by_source = {int(source_index): index for index, source_index in enumerate(pred_source_indices)}
        matched: list[TargetCandidateRow] = []
        for row in selected_rows:
            pred_index = pred_index_by_source.get(row.source_index)
            if pred_index is None:
                matched.append(replace(row, gt_match_status="unmatched_gt"))
                continue
            pred = ObbTW(pred_obbs._data[pred_index].unsqueeze(0))
            candidate_matches: list[tuple[int, float, float]] = []
            for gt_index in range(int(gt_obbs.shape[0])):
                gt = ObbTW(gt_obbs._data[gt_index].unsqueeze(0))
                if int(gt.sem_id.reshape(-1)[0].item()) != row.sem_id:
                    continue
                iou = _safe_obb_iou(pred, gt, samples=self.config.gt_iou_samples)
                match_score = _gt_match_score(iou=iou)
                if iou >= self.config.min_gt_iou and match_score >= self.config.min_gt_match_score:
                    candidate_matches.append((gt_index, iou, match_score))
            candidate_matches.sort(key=lambda item: item[2], reverse=True)
            if not candidate_matches:
                matched.append(
                    replace(
                        row,
                        gt_label_valid=False,
                        gt_match_status="unmatched_gt",
                        invalid_reason_bitset=_target_failure_bitset(
                            row.invalid_reason_bitset,
                            TARGET_INVALID_REASON_CODES["TARGET_GT_UNMATCHED"],
                        ),
                        primary_invalid_reason=TARGET_INVALID_REASON_CODES["TARGET_GT_UNMATCHED"],
                    )
                )
                continue
            if len(candidate_matches) > 1 and (
                candidate_matches[0][2] - candidate_matches[1][2] <= self.config.gt_ambiguity_margin
            ):
                matched.append(
                    replace(
                        row,
                        gt_label_valid=False,
                        gt_match_iou=float(candidate_matches[0][1]),
                        gt_match_score=float(candidate_matches[0][2]),
                        gt_match_status="ambiguous_gt",
                        invalid_reason_bitset=_target_failure_bitset(
                            row.invalid_reason_bitset,
                            TARGET_INVALID_REASON_CODES["TARGET_GT_AMBIGUOUS"],
                        ),
                        primary_invalid_reason=TARGET_INVALID_REASON_CODES["TARGET_GT_AMBIGUOUS"],
                    )
                )
                continue
            gt_index, best_iou, best_match_score = candidate_matches[0]
            gt_source_index = int(gt_source_indices[gt_index])
            matched.append(
                replace(
                    row,
                    gt_label_valid=True,
                    gt_target_row_id=gt_source_index,
                    gt_target_id=_target_id(
                        scene_id=row.scene_id,
                        snippet_id=row.snippet_id,
                        source="gt_obbs",
                        sem_id=row.sem_id,
                        inst_id=int(gt_obbs.inst_id.reshape(-1)[gt_index].item()),
                        source_index=gt_source_index,
                    ),
                    gt_match_iou=float(best_iou),
                    gt_match_score=float(best_match_score),
                    gt_match_status="matched",
                )
            )

        return _mark_duplicate_gt_matches(tuple(matched))

    def _policy_temperature(self) -> float | None:
        return (
            float(self.config.temperature)
            if self.config.policy == TargetSelectionPolicy.TEMPERATURE_SOFTMAX_TOP_K
            else None
        )


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


def _max_projected_area(obb: ObbTW, *, config: TargetSelectorConfig) -> float:
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


def _visibility_score(
    *,
    projected_area: float,
    projected_fraction: float,
    config: TargetSelectorConfig,
) -> float:
    """Compute a smooth actor-visible projected-area score."""

    if projected_area <= 0.0:
        return 0.0 if config.require_projected_visibility else float(config.missing_projection_visibility_score)
    normalized = max(0.0, min(float(projected_fraction / config.projected_area_full_score_fraction), 1.0))
    return float(normalized * normalized * (3.0 - 2.0 * normalized))


def _gt_match_score(*, iou: float) -> float:
    """Return the geometry-only GT association score.

    Target support and projected visibility decide whether an actor-visible row
    is labelable and interesting. Once selected, GT association is kept as
    class-compatible 3D IoU so labelability failures are not conflated with
    geometric mismatch.
    """

    return float(max(0.0, iou))


def _target_reason_bitset(
    *,
    obb: ObbTW,
    confidence: float,
    projected_area: float,
    effective_support: float,
    config: TargetSelectorConfig,
) -> int:
    bitset = 0
    data = obb.tensor().reshape(-1)
    extents = obb.bb3_diagonal.reshape(-1)
    if not torch.isfinite(data).all():
        bitset |= 1 << TARGET_INVALID_REASON_CODES["OBB_NONFINITE"]
    if not torch.isfinite(extents).all() or bool((extents <= 0).any().item()):
        bitset |= 1 << TARGET_INVALID_REASON_CODES["OBB_EXTENT_INVALID"]
    if confidence < config.min_confidence:
        bitset |= 1 << TARGET_INVALID_REASON_CODES["CONFIDENCE_TOO_LOW"]
    if config.require_projected_visibility:
        if projected_area <= 0.0:
            bitset |= 1 << TARGET_INVALID_REASON_CODES["NO_PROJECTED_VISIBILITY"]
        if projected_area < config.min_projected_area_pixels:
            bitset |= 1 << TARGET_INVALID_REASON_CODES["PROJECTED_AREA_TOO_SMALL"]
    if effective_support < config.min_support_points:
        bitset |= 1 << TARGET_INVALID_REASON_CODES["TARGET_SUPPORT_TOO_LOW"]
    return (1 << TARGET_INVALID_REASON_CODES["VALID"]) if bitset == 0 else bitset


def _primary_reason(bitset: int) -> int:
    if bitset == (1 << TARGET_INVALID_REASON_CODES["VALID"]):
        return TARGET_INVALID_REASON_CODES["VALID"]
    for _name, bit in sorted(TARGET_INVALID_REASON_CODES.items(), key=lambda item: item[1]):
        if bit != TARGET_INVALID_REASON_CODES["VALID"] and bitset & (1 << bit):
            return bit
    return TARGET_INVALID_REASON_CODES["VALID"]


def _safe_obb_iou(pred: ObbTW, gt: ObbTW, *, samples: int) -> float:
    try:
        value = obb_iou3d(pred, gt, samp_per_dim=int(samples))
        return float(value.reshape(-1)[0].item())
    except Exception:
        pred_center = pred.bb3_center_world.reshape(-1, 3)[0]
        gt_center = gt.bb3_center_world.reshape(-1, 3)[0]
        pred_diag = torch.linalg.norm(pred.bb3_diagonal.reshape(-1, 3)[0]).clamp_min(1e-6)
        gt_diag = torch.linalg.norm(gt.bb3_diagonal.reshape(-1, 3)[0]).clamp_min(1e-6)
        return float((1.0 - torch.linalg.norm(pred_center - gt_center) / (pred_diag + gt_diag)).clamp(0.0, 1.0))


def _mark_duplicate_gt_matches(rows: tuple[TargetCandidateRow, ...]) -> tuple[TargetCandidateRow, ...]:
    counts: dict[int, int] = {}
    for row in rows:
        if row.gt_label_valid and row.gt_target_row_id is not None:
            counts[row.gt_target_row_id] = counts.get(row.gt_target_row_id, 0) + 1
    output: list[TargetCandidateRow] = []
    for row in rows:
        if row.gt_label_valid and row.gt_target_row_id is not None and counts.get(row.gt_target_row_id, 0) > 1:
            output.append(
                replace(
                    row,
                    gt_label_valid=False,
                    gt_match_status="ambiguous_pred_to_gt",
                    invalid_reason_bitset=_target_failure_bitset(
                        row.invalid_reason_bitset,
                        TARGET_INVALID_REASON_CODES["TARGET_GT_AMBIGUOUS"],
                    ),
                    primary_invalid_reason=TARGET_INVALID_REASON_CODES["TARGET_GT_AMBIGUOUS"],
                )
            )
        else:
            output.append(row)
    return tuple(output)


def _target_failure_bitset(current: int, reason: int) -> int:
    valid = 1 << TARGET_INVALID_REASON_CODES["VALID"]
    return (int(current) & ~valid) | (1 << int(reason))


def _ranking_key(row: TargetCandidateRow) -> tuple[float, int, str]:
    return (-float(row.score), int(row.source_index), row.target_id)


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
    "ActorVisibleTargetSelector",
    "TARGET_INVALID_REASON_CODES",
    "TARGET_INVALID_REASON_VERSION",
    "TargetCandidateRow",
    "TargetSelectionPolicy",
    "TargetSelectionResult",
    "TargetSelectorConfig",
    "TargetSourceMode",
    "target_gt_obb_world",
]
