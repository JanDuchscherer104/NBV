"""Chain-native data plane for finite-candidate ``Q_H`` training.

One item is one persisted rollout chain. :class:`QhInputs` contains only actor
tensors; :class:`QhSupervision` holds Oracle labels and never enters the scorer.
V0 uses an Oracle-GT target OBB as an ablation input; V1 replaces it without weakening the boundary.
Collation pads time/candidate axes once; lineage stays immutable CPU-only audit data.
Storage belongs to :mod:`aria_nbv.rollouts.qh_reader`; loader policy belongs to
:mod:`aria_nbv.lightning.qh_datamodule`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, fields, replace
from functools import cached_property

import numpy as np
import torch
from efm3d.aria.pose import PoseTW
from pydantic import Field, field_validator
from torch import Tensor
from torch.utils.data import Dataset

from ..rollouts.qh_reader import QhRolloutReader, QhRolloutReaderConfig
from ..targets.protocol import TargetDescriptorProvenance, TargetInputProtocol, validate_target_protocol_admission
from ..utils import Stage, TargetConfig
from ..utils.fingerprints import stable_msgspec_hash
from .identifiers import compact_ase_atek_sample_id
from .offline.format import VinOfflineIndexRecord
from .offline.store import VinOfflineStoreConfig, VinOfflineStoreReader
from .raw.views import VinSnippetView


@dataclass(frozen=True, slots=True)
class QhChainLineage:
    """Exact CPU-scalar provenance for one persisted rollout chain."""

    source_row_id: int
    """Dense rollout-store source row id."""
    source_sample_index: int
    """Global immutable VIN sample index."""
    source_sample_key: str
    """Stable compact ASE/ATEK sample key."""
    source_shard_id: str
    """Immutable VIN shard id."""
    source_shard_row: int
    """Row within the immutable VIN shard."""
    scene_id: str
    """ASE scene id."""
    snippet_id: str
    """ATEK snippet id."""
    split: Stage
    """Immutable source split."""
    source_cache_version: str
    """Immutable VIN store-format version."""
    source_offline_store_manifest_hash: str
    """Hash of the complete VIN source manifest."""
    split_manifest_hash: str
    """Hash of the admitted split manifest."""
    mesh_version: str
    """Persisted mesh version, or an empty string when absent."""
    target_row_id: int
    """Dense target-table row id."""
    target_sem_id: int
    """Target semantic-category id."""
    target_inst_id: int
    """Target instance id."""
    target_protocol_version: str
    """Actor-visible target protocol version."""
    target_source: str
    """Persisted target descriptor source."""
    target_crop_policy: str
    """Persisted target crop policy, or an empty string."""
    schema_version: str
    """Rollout Zarr schema version."""
    reason_code_version: str
    """Invalid-reason vocabulary version."""
    return_semantics: str
    """Persisted finite-horizon return definition."""
    td_semantics: str
    """Persisted Bellman-tuple definition."""
    reward_metric: str
    """Scalar reward metric name."""
    discount_gamma: float
    """Corpus discount factor."""
    horizon: int
    """Candidate-bearing chain length."""
    rollout_row_id: int
    """Canonical persisted dataset-item key."""
    rollout_id: str
    """Stable rollout identifier."""
    chain_id: int
    """Persisted branch-chain identifier."""
    root_time_ns: int
    """Rollout-root timestamp in nanoseconds."""
    root_trajectory_index: int
    """Rollout-root trajectory index."""
    root_frame_index: int
    """Rollout-root frame index."""
    policy: str
    """Persisted rollout policy name."""
    branch_factor: int
    """Persisted rollout branch factor."""
    beam_width: int
    """Persisted beam width; ``-1`` means absent."""
    temperature: float
    """Persisted stochastic-policy temperature."""
    random_seed: int
    """Persisted random seed; ``-1`` means absent."""
    termination_reason: str
    """Persisted chain termination reason."""
    candidate_config_hash: str
    """Candidate-generation config hash."""
    oracle_config_hash: str
    """Privileged Oracle config hash."""
    rollout_config_hash: str
    """Rollout-policy config hash."""
    model_checkpoint_hash: str
    """Selection-model checkpoint hash, or an empty string."""
    branch_schedule_id: str
    """Branch-schedule id, or an empty string."""
    selection_rng_state_hash: str
    """Selection RNG-state hash, or an empty string."""


@dataclass(frozen=True, slots=True)
class QhInputs:
    """Actor-visible V0 tensors for one chain or padded ``[B,S,N]`` batch."""

    vin_snippet: VinSnippetView
    """Chain-constant semidense points, lengths, and world-from-rig history."""
    root_pose_world: Tensor
    """``Tensor["12", float32]`` or ``Tensor["B 12", float32]`` world-from-root pose."""
    target_extents: Tensor
    """``Tensor["3", float32]`` or ``Tensor["B 3", float32]`` Oracle-GT V0 OBB extents in metres."""
    target_pose_world_object: Tensor
    """``Tensor["12", float32]`` or ``Tensor["B 12", float32]`` Oracle-GT V0 world-from-object pose."""
    candidate_pose_relative_root: Tensor
    """``Tensor["S N 12", float32]`` or ``Tensor["B S N 12", float32]`` root-from-camera poses."""
    candidate_position_id: Tensor
    """``Tensor["S N", int64]`` or ``Tensor["B S N", int64]`` position ids; padding is ``-1``."""
    actor_action_mask: Tensor
    """``Tensor["S N", bool]`` or ``Tensor["B S N", bool]`` hard actor action mask."""
    previous_selected_pose_relative_root: Tensor
    """``Tensor["S 12", float32]`` or ``Tensor["B S 12", float32]`` right-shifted root-from-camera history."""
    previous_selected_position_id: Tensor
    """``Tensor["S", int64]`` or ``Tensor["B S", int64]`` right-shifted position ids."""
    previous_selected_mask: Tensor
    """``Tensor["S", bool]`` or ``Tensor["B S", bool]`` hard presence mask for shifted actor history."""
    remaining_budget: Tensor
    """``Tensor["S", int64]`` or ``Tensor["B S", int64]`` residual acquisition budget including this action."""
    step_mask: Tensor
    """``Tensor["S", bool]`` or ``Tensor["B S", bool]`` candidate-bearing state mask."""


@dataclass(frozen=True, slots=True)
class QhSupervision:
    """Dense Oracle labels and factual actions excluded from scorer inputs."""

    candidate_row_id: Tensor
    """``Tensor["S N", int64]`` or ``Tensor["B S N", int64]`` stable ids; padding is ``-1``."""
    q_train_mask: Tensor
    """``Tensor["S N", bool]`` or ``Tensor["B S N", bool]`` finite actor-valid Oracle mask."""
    invalid_reason_bitset: Tensor
    """``Tensor["S N", int64]`` or ``Tensor["B S N", int64]`` hard-invalid reason flags."""
    one_step_target_rri: Tensor
    """``Tensor["S N", float32]`` or ``Tensor["B S N", float32]`` diagnostic target RRI."""
    one_step_target_root_gain: Tensor
    """``Tensor["S N", float32]`` or ``Tensor["B S N", float32]`` immediate training reward."""
    selected_candidate_index: Tensor
    """``Tensor["S", int64]`` or ``Tensor["B S", int64]`` factual compact selected index."""
    discount: Tensor
    """``Tensor["S", float32]`` or ``Tensor["B S", float32]`` gamma-or-zero discount."""
    terminal: Tensor
    """``Tensor["S", bool]`` or ``Tensor["B S", bool]`` factual terminal flag."""
    row_train_mask: Tensor
    """``Tensor["S", bool]`` or ``Tensor["B S", bool]`` selected-transition loss gate."""

    @property
    def selected_candidate_row_id(self) -> Tensor:
        """Gather factual selected row ids from the dense candidate basis."""

        return _gather_candidates(self.candidate_row_id, self.selected_candidate_index)

    @property
    def selected_reward(self) -> Tensor:
        """Gather factual selected root-gain rewards from dense supervision."""

        return _gather_candidates(self.one_step_target_root_gain, self.selected_candidate_index)

    @property
    def selected_rri(self) -> Tensor:
        """Gather factual selected diagnostic RRI from dense supervision."""

        return _gather_candidates(self.one_step_target_rri, self.selected_candidate_index)


@dataclass(frozen=True, slots=True)
class QhRolloutChain:
    """One complete non-empty persisted rollout chain."""

    inputs: QhInputs
    """Actor-visible V0 tensor basis."""
    supervision: QhSupervision
    """Dense privileged labels and selected-transition facts."""
    lineage: QhChainLineage
    """CPU-only chain provenance."""


@dataclass(frozen=True, slots=True)
class QhBatch:
    """Padded ``[B,S,N,...]`` chain batch with explicit actor/GT separation."""

    inputs: QhInputs
    """Padded actor-visible model inputs."""
    supervision: QhSupervision
    """Padded privileged labels and selected-transition facts."""
    lineage: tuple[QhChainLineage, ...]
    """Per-chain CPU-only provenance, never passed to the model."""

    def assert_selected_rows_consistent(self) -> None:
        """Reject any admitted row inconsistent with dense candidate facts."""

        admitted = self.supervision.row_train_mask
        if not bool(admitted.any()):
            return
        selected = self.supervision.selected_candidate_index
        width = self.supervision.candidate_row_id.shape[-1]
        valid_index = selected.ge(0) & selected.lt(width)
        safe = selected.clamp(0, max(width - 1, 0))
        actor_valid = _gather_candidates(self.inputs.actor_action_mask, safe)
        valid = (
            valid_index
            & actor_valid
            & self.supervision.selected_candidate_row_id.ge(0)
            & torch.isfinite(self.supervision.selected_reward)
            & torch.isfinite(self.supervision.selected_rri)
            & torch.isfinite(self.supervision.discount)
        )
        if not bool(valid[admitted].all()):
            raise ValueError("Trainable selected Q_H row violates dense supervision or action admission.")

    def pin_memory(self) -> QhBatch:
        """Pin every tensor exactly once while preserving lineage by identity."""

        return _transform_batch(self, Tensor.pin_memory)

    def to(self, device: str | torch.device, *, non_blocking: bool = True) -> QhBatch:
        """Move every tensor to `device` while keeping lineage on the CPU."""

        return _transform_batch(self, lambda value: value.to(device=device, non_blocking=non_blocking))


class QhDatasetConfig(TargetConfig["QhDataset"]):
    """Configure complete rollout-chain and immutable VIN source readers."""

    rollout: QhRolloutReaderConfig
    """Homogeneous V0 rollout corpus."""
    actor: VinOfflineStoreConfig = Field(default_factory=VinOfflineStoreConfig)
    """Immutable VIN store read directly through its canonical reader."""
    split: Stage | None = None
    """Optional VIN split restriction; ``None`` admits every source record."""

    @field_validator("split", mode="before")
    @classmethod
    def _normalize_split(cls, value: Stage | str | None) -> Stage | None:
        if value is None or value == "all":
            return None
        return Stage.from_str(value)

    @property
    def target_type(self) -> type[QhDataset]:
        """Runtime dataset constructed by :meth:`setup_target`."""

        return QhDataset

    def setup_target(self) -> QhDataset:
        """Construct both lazy readers behind their owning configurations."""

        return QhDataset(
            rollout_reader=self.rollout.setup_target(),
            actor_reader=VinOfflineStoreReader(self.actor),
            split=self.split,
        )


class QhDataset(Dataset[QhRolloutChain]):
    """Join complete rollout chains to one chain-constant VIN actor snippet."""

    _REBUILD_GUIDANCE = "Rebuild the VIN offline store and rollout corpus from the same immutable source manifest."

    def __init__(
        self,
        *,
        rollout_reader: QhRolloutReader,
        actor_reader: VinOfflineStoreReader,
        split: Stage | None = None,
    ) -> None:
        self.rollout_reader = rollout_reader
        self.actor_reader = actor_reader
        self.split = split
        self._manifest_hash = stable_msgspec_hash(actor_reader.manifest)
        records = actor_reader.get_split_records(split)
        self._records = {record.sample_index: record for record in records}
        self._validate_source_lineage()

    def __len__(self) -> int:
        """Return the number of complete non-empty persisted chains."""

        return len(self.rollout_reader)

    def __getitem__(self, index: int) -> QhRolloutChain:
        """Read one chain and its chain-constant actor snippet exactly once."""

        stored = self.rollout_reader[index]
        lineage = QhChainLineage(*stored.lineage)
        protocol = validate_target_protocol_admission(
            lineage.target_protocol_version,
            target_source=lineage.target_source,
            descriptor_source=lineage.target_source,
            descriptor_provenance=TargetDescriptorProvenance.ORACLE_GT,
        )
        if protocol is not TargetInputProtocol.V0_GT_INPUT:
            raise ValueError("QhDataset currently materializes only v0_gt_input target descriptors.")
        record = self._record(lineage)
        snippet = self.actor_reader.read_actor_snippet(record, device="cpu")
        return _tensor_chain(stored, snippet, lineage)

    @cached_property
    def scene_ids(self) -> frozenset[str]:
        """Return preflighted scene ids without materializing chain payloads."""

        return self.rollout_reader.scene_ids

    @property
    def q_h_horizon(self) -> int:
        """Return the validated maximum candidate-bearing chain length."""

        return self.rollout_reader.q_h_horizon

    @property
    def provenance(self) -> dict[str, object]:
        """Return compact rollout and VIN source identity."""

        return {
            "rollout": self.rollout_reader.provenance,
            "actor": {
                "store_path": str(self.actor_reader.config.store_dir),
                "store_version": self.actor_reader.manifest.version,
                "manifest_hash": self._manifest_hash,
                "split": self.split,
                "row_count": len(self._records),
            },
        }

    def _validate_source_lineage(self) -> None:
        for lineage in self.rollout_reader.source_lineage:
            self._record(lineage)

    def _record(self, lineage: object) -> VinOfflineIndexRecord:
        sample_index = int(lineage.source_sample_index)
        try:
            record = self._records[sample_index]
        except KeyError as error:
            raise KeyError(
                f"VIN sample_index={sample_index} is absent from split {self.split!r}. {self._REBUILD_GUIDANCE}"
            ) from error
        actual = (
            record.sample_index,
            compact_ase_atek_sample_id(record.sample_key),
            record.shard_id,
            record.row,
            str(self.actor_reader.manifest.version),
            self._manifest_hash,
            record.scene_id,
            compact_ase_atek_sample_id(record.snippet_id),
            Stage.from_str(record.split),
        )
        expected = (
            sample_index,
            compact_ase_atek_sample_id(str(lineage.source_sample_key)),
            str(lineage.source_shard_id),
            int(lineage.source_shard_row),
            str(lineage.source_cache_version),
            str(lineage.source_offline_store_manifest_hash),
            str(lineage.scene_id),
            compact_ase_atek_sample_id(str(lineage.snippet_id)),
            lineage.split,
        )
        if actual != expected:
            raise ValueError(f"VIN source lineage does not match rollout chain. {self._REBUILD_GUIDANCE}")
        return record


def collate_qh_samples(samples: list[QhRolloutChain]) -> QhBatch:
    """Pad heterogeneous complete chains to one explicit ``[B,S,N,...]`` basis."""

    if not samples:
        raise ValueError("Cannot collate an empty Q_H chain list.")
    inputs = [sample.inputs for sample in samples]
    supervision = [sample.supervision for sample in samples]
    snippets = [value.vin_snippet for value in inputs]
    return QhBatch(
        inputs=QhInputs(
            vin_snippet=VinSnippetView(
                points_world=_pad([value.points_world for value in snippets], float("nan")),
                lengths=torch.stack([value.lengths for value in snippets]),
                t_world_rig=PoseTW(_pad([value.t_world_rig.tensor() for value in snippets], 0)),
            ),
            root_pose_world=torch.stack([value.root_pose_world for value in inputs]),
            target_extents=torch.stack([value.target_extents for value in inputs]),
            target_pose_world_object=torch.stack([value.target_pose_world_object for value in inputs]),
            candidate_pose_relative_root=_pad([value.candidate_pose_relative_root for value in inputs], 0),
            candidate_position_id=_pad([value.candidate_position_id for value in inputs], -1),
            actor_action_mask=_pad([value.actor_action_mask for value in inputs], False),
            previous_selected_pose_relative_root=_pad(
                [value.previous_selected_pose_relative_root for value in inputs], 0
            ),
            previous_selected_position_id=_pad([value.previous_selected_position_id for value in inputs], -1),
            previous_selected_mask=_pad([value.previous_selected_mask for value in inputs], False),
            remaining_budget=_pad([value.remaining_budget for value in inputs], 0),
            step_mask=_pad([value.step_mask for value in inputs], False),
        ),
        supervision=QhSupervision(
            candidate_row_id=_pad([value.candidate_row_id for value in supervision], -1),
            q_train_mask=_pad([value.q_train_mask for value in supervision], False),
            invalid_reason_bitset=_pad([value.invalid_reason_bitset for value in supervision], 0),
            one_step_target_rri=_pad([value.one_step_target_rri for value in supervision], 0),
            one_step_target_root_gain=_pad([value.one_step_target_root_gain for value in supervision], 0),
            selected_candidate_index=_pad([value.selected_candidate_index for value in supervision], -1),
            discount=_pad([value.discount for value in supervision], 0),
            terminal=_pad([value.terminal for value in supervision], True),
            row_train_mask=_pad([value.row_train_mask for value in supervision], False),
        ),
        lineage=tuple(sample.lineage for sample in samples),
    )


def _tensor_chain(stored: object, snippet: VinSnippetView, lineage: QhChainLineage) -> QhRolloutChain:
    candidate_pose = _stack_rows(stored.candidate_pose_relative_root, 0, torch.float32)
    position_id = _stack_rows(stored.candidate_position_id, -1, torch.int64)
    actor_mask = _stack_rows(stored.actor_action_mask, False, torch.bool)
    candidate_row_id = _stack_rows(stored.candidate_row_id, -1, torch.int64)
    q_train_mask = _stack_rows(stored.q_train_mask, False, torch.bool)
    invalid_reason = _stack_rows(stored.invalid_reason_bitset, 0, torch.int64)
    target_rri = _stack_rows(stored.one_step_target_rri, 0, torch.float32)
    target_gain = _stack_rows(stored.one_step_target_root_gain, 0, torch.float32)
    selected = _from_numpy(stored.selected_candidate_index, torch.int64)
    selected_pose = _gather_candidates(candidate_pose, selected)
    selected_position = _gather_candidates(position_id, selected)
    steps = selected.shape[0]
    previous_pose = torch.zeros_like(selected_pose)
    previous_position = torch.full_like(selected_position, -1)
    previous_mask = torch.zeros(steps, dtype=torch.bool)
    if steps > 1:
        previous_pose[1:] = selected_pose[:-1]
        previous_position[1:] = selected_position[:-1]
        previous_mask[1:] = True
    discount = _from_numpy(stored.discount, torch.float32)
    terminal = _from_numpy(stored.terminal, torch.bool)
    selected_q_mask = _gather_candidates(q_train_mask, selected)
    selected_actor_mask = _gather_candidates(actor_mask, selected)
    selected_rri = _gather_candidates(target_rri, selected)
    selected_gain = _gather_candidates(target_gain, selected)
    if not bool(torch.isfinite(target_rri[q_train_mask]).all() and torch.isfinite(target_gain[q_train_mask]).all()):
        raise ValueError("Q_H q_train_mask admits a candidate with non-finite supervision.")
    row_train = (
        selected_q_mask
        & selected_actor_mask
        & torch.isfinite(selected_rri)
        & torch.isfinite(selected_gain)
        & torch.isfinite(discount)
    )
    return QhRolloutChain(
        inputs=QhInputs(
            vin_snippet=snippet,
            root_pose_world=_from_numpy(stored.root_pose_world, torch.float32),
            target_extents=_from_numpy(stored.target_extents, torch.float32),
            target_pose_world_object=_from_numpy(stored.target_pose_world_object, torch.float32),
            candidate_pose_relative_root=candidate_pose,
            candidate_position_id=position_id,
            actor_action_mask=actor_mask,
            previous_selected_pose_relative_root=previous_pose,
            previous_selected_position_id=previous_position,
            previous_selected_mask=previous_mask,
            remaining_budget=_from_numpy(stored.remaining_budget, torch.int64),
            step_mask=torch.ones(steps, dtype=torch.bool),
        ),
        supervision=QhSupervision(
            candidate_row_id=candidate_row_id,
            q_train_mask=q_train_mask,
            invalid_reason_bitset=invalid_reason,
            one_step_target_rri=target_rri,
            one_step_target_root_gain=target_gain,
            selected_candidate_index=selected,
            discount=discount,
            terminal=terminal,
            row_train_mask=row_train,
        ),
        lineage=lineage,
    )


def _from_numpy(value: np.ndarray, dtype: torch.dtype) -> Tensor:
    return torch.from_numpy(np.array(value, copy=True)).to(dtype=dtype)


def _stack_rows(values: tuple[np.ndarray, ...], fill: int | float | bool, dtype: torch.dtype) -> Tensor:
    return _pad([_from_numpy(value, dtype) for value in values], fill)


def _pad(values: list[Tensor], fill: int | float | bool) -> Tensor:
    if not values:
        raise ValueError("Cannot pad an empty tensor list.")
    rank = values[0].ndim
    if any(value.ndim != rank for value in values):
        raise ValueError("Q_H tensors with different ranks cannot share one padded field.")
    maxima = tuple(max(value.shape[axis] for value in values) for axis in range(rank))
    output = torch.full((len(values), *maxima), fill, dtype=values[0].dtype)
    for row, value in enumerate(values):
        output[(row, *(slice(0, size) for size in value.shape))] = value
    return output


def _gather_candidates(values: Tensor, indices: Tensor) -> Tensor:
    safe = indices.clamp(0, max(values.shape[-1] - 1, 0))
    if values.ndim == indices.ndim + 1:
        return values.gather(-1, safe.unsqueeze(-1)).squeeze(-1)
    expanded = safe.unsqueeze(-1).unsqueeze(-1).expand(*safe.shape, 1, values.shape[-1])
    return values.gather(-2, expanded).squeeze(-2)


def _transform_batch(batch: QhBatch, transform: Callable[[Tensor], Tensor]) -> QhBatch:
    inputs = batch.inputs
    snippet = inputs.vin_snippet
    transformed_inputs = {
        field.name: transform(getattr(inputs, field.name)) for field in fields(QhInputs) if field.name != "vin_snippet"
    }
    transformed_supervision = {
        field.name: transform(getattr(batch.supervision, field.name)) for field in fields(QhSupervision)
    }
    return replace(
        batch,
        inputs=QhInputs(
            vin_snippet=VinSnippetView(
                points_world=transform(snippet.points_world),
                lengths=transform(snippet.lengths),
                t_world_rig=PoseTW(transform(snippet.t_world_rig.tensor())),
            ),
            **transformed_inputs,
        ),
        supervision=QhSupervision(**transformed_supervision),
    )


__all__ = [
    "QhRolloutChain",
    "QhChainLineage",
    "QhInputs",
    "QhSupervision",
    "QhBatch",
]
