r"""Oracle target-task sampling for ARIA-NBV.

`OracleTargetTaskSampler` builds the data-generation target-task pool from
oracle GT OBBs. It is the source for rollout labels and target-conditioned
supervision. First-pass task admission is intentionally limited to finite,
positive GT OBB geometry. Confidence is retained for audit but does not gate
task admission. Persistence-only compatibility columns are encoded by the
rollout writer rather than carried by this domain DTO.
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

from ..data_handling.offline.batch import CompactObbBlock
from ..data_handling.raw.views import EfmSnippetView, VinSnippetView
from ..targets import TargetDescriptor
from ..targets.protocol import ORACLE_GT_TARGET_SOURCE
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

ORACLE_TARGET_TASK_SOURCE = ORACLE_GT_TARGET_SOURCE
"""Source label for oracle target-task rows sampled from GT OBBs."""


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
class OracleTargetTask:
    """One oracle target-task row for rollout/data-generation labeling.

    The sampler creates these rows from GT OBBs, not from actor-visible target
    discovery. `identity_status` records the first-pass task-pool gate: the
    source GT OBB must have finite positive geometry. `descriptor` composes the
    actor-safe semantic and geometric instruction. Privileged identity and
    confidence stay on the task. Persistence-only compatibility values are
    added later by the rollout writer and do not belong to this contract.
    """

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

    identity_status: str
    """Serialized `TargetTaskIdentityStatus` produced by the geometry gate."""

    selected_rank: int | None = None
    """Zero-based rank in the seeded capped sample, or ``None`` when unselected."""

    selection_probability: float | None = None
    """Inclusion probability under uniform capped sampling, when selected."""


@dataclass(frozen=True, slots=True)
class OracleTargetTaskSamplingResult:
    """Oracle target-task pool and seeded capped sample for one snippet."""

    rows: tuple[OracleTargetTask, ...]
    """All non-padded GT OBB rows interpreted as candidate target tasks."""

    selected_rows: tuple[OracleTargetTask, ...]
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
            "num_identity_valid": sum(
                row.identity_status == TargetTaskIdentityStatus.MATCHED.value for row in self.rows
            ),
            "num_selected": len(self.selected_rows),
            "num_invalid_geometry": sum(
                row.identity_status == TargetTaskIdentityStatus.INVALID_GEOMETRY.value for row in self.rows
            ),
        }
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
            sample. Confidence is retained for audit and does not filter
            first-pass target-task eligibility.
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
                selected_rows=(),
                max_targets_per_sample=self.config.max_targets_per_sample,
                seed=self.config.seed,
                source=None,
                warnings=tuple(warnings),
            )

        gt_world = _world_obbs_for_sample(gt_block[0], sample)
        rows = self._build_rows(sample, world_obbs=gt_world, sem_id_to_name=gt_block[1])
        identity_valid = tuple(row for row in rows if row.identity_status == TargetTaskIdentityStatus.MATCHED.value)
        selected = self._sample_rows(identity_valid)
        selected_by_id = {row.target_id: row for row in selected}
        rows = tuple(selected_by_id.get(row.target_id, row) for row in rows)
        identity_valid = tuple(selected_by_id.get(row.target_id, row) for row in identity_valid)

        return OracleTargetTaskSamplingResult(
            rows=rows,
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
    ) -> tuple[OracleTargetTask, ...]:
        valid_data, source_indices = _valid_obb_data_with_source_indices(world_obbs)
        if valid_data.numel() == 0:
            return ()
        gt_obbs = ObbTW(valid_data)
        reference_pose = _pose_on_device(_reference_pose_world_rig(sample), device=valid_data.device)
        scene_id = _first_scalar_string(sample.scene_id)
        snippet_id = _first_scalar_string(sample.snippet_id)

        rows: list[OracleTargetTask] = []
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
                OracleTargetTask(
                    source_index=source_index,
                    target_row_id=source_index,
                    target_id=target_id,
                    descriptor=descriptor,
                    inst_id=inst_id,
                    confidence=confidence,
                    identity_status=identity_status.value,
                )
            )
        return tuple(rows)

    def _sample_rows(self, rows: tuple[OracleTargetTask, ...]) -> tuple[OracleTargetTask, ...]:
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
        selected: list[OracleTargetTask] = []
        for rank, row_index in enumerate(permutation[:target_count]):
            selected.append(
                replace(
                    rows[int(row_index)],
                    selected_rank=rank,
                    selection_probability=probability,
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
    "OracleTargetTask",
    "OracleTargetTaskSampler",
    "OracleTargetTaskSamplerConfig",
    "OracleTargetTaskSelectionPolicy",
    "OracleTargetTaskSamplingResult",
    "TARGET_INVALID_REASON_CODES",
    "TARGET_INVALID_REASON_VERSION",
    "TargetTaskIdentityStatus",
]
