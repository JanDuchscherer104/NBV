"""Actor-safe chain data for finite-candidate ``Q_H`` training.

The rollout reader owns storage interpretation and private source identity.
This module joins that identity to the immutable VIN actor store, derives the
actor/supervision masks, and pads heterogeneous chains without exposing
storage provenance to a scorer.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, fields, replace
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import torch
from efm3d.aria.pose import PoseTW
from pydantic import Field, field_validator
from torch import Tensor
from torch.utils.data import Dataset

from ..rollouts.qh_reader import QhDataContract, QhRolloutReader, _QhSourceRef
from ..rollouts.shard_manifest import build_rollout_split_manifest_hash
from ..utils import Stage, TargetConfig
from ..utils.fingerprints import stable_msgspec_hash
from .identifiers import compact_ase_atek_sample_id
from .offline.format import VinOfflineIndexRecord
from .offline.store import VinOfflineStoreConfig, VinOfflineStoreReader
from .raw.views import VinSnippetView

if TYPE_CHECKING:
    from ..rollouts.qh_reader import _StoredChain


@dataclass(frozen=True, slots=True)
class QhActorTensors:
    """Actor-visible tensors for one chain or one padded batch."""

    vin_snippet: VinSnippetView
    root_pose_world: Tensor
    target_pose_relative_root: Tensor
    target_extents: Tensor
    candidate_pose_relative_root: Tensor
    candidate_mask: Tensor
    action_mask: Tensor
    history_pose_relative_root: Tensor
    history_mask: Tensor
    horizon_remaining: Tensor
    step_mask: Tensor


@dataclass(frozen=True, slots=True)
class QhSupervision:
    """Oracle labels and factual selected transitions kept outside the actor."""

    label_mask: Tensor
    candidate_reward: Tensor
    selected_index: Tensor
    discount: Tensor
    terminal: Tensor


@dataclass(frozen=True, slots=True)
class QhChainKey:
    """Small CPU-only identity for one dataset item."""

    store_index: int
    rollout_row_id: int
    source_sample_index: int
    scene_id: str
    target_row_id: int


@dataclass(frozen=True, slots=True)
class QhChain:
    """One complete, non-empty rollout chain."""

    actor: QhActorTensors
    supervision: QhSupervision
    key: QhChainKey

    @property
    def num_steps(self) -> int:
        """Return the realized candidate-bearing state count."""

        return int(self.actor.step_mask.sum().item())


@dataclass(frozen=True, slots=True)
class QhBatch:
    """Padded ``[B,S,N,...]`` batch with centralized tensor transfer."""

    actor: QhActorTensors
    supervision: QhSupervision
    keys: tuple[QhChainKey, ...]

    @property
    def num_steps(self) -> Tensor:
        """Return each chain's realized state count as ``Tensor[B]``."""

        return self.actor.step_mask.sum(dim=-1)

    @property
    def selected_train_mask(self) -> Tensor:
        """Return selected rows with valid support and finite supervision."""

        selected = self.supervision.selected_index
        width = self.actor.candidate_mask.shape[-1]
        valid_index = selected.ge(0) & selected.lt(width)
        safe = selected.clamp(0, max(width - 1, 0))
        return (
            self.actor.step_mask
            & valid_index
            & _gather_candidates(self.actor.action_mask, safe)
            & _gather_candidates(self.supervision.label_mask, safe)
            & torch.isfinite(_gather_candidates(self.supervision.candidate_reward, safe))
            & torch.isfinite(self.supervision.discount)
        )

    @property
    def successor_backup_mask(self) -> Tensor:
        """Return shifted successor support used for availability and argmax."""

        support = self.actor.action_mask & self.supervision.label_mask
        shifted = torch.zeros_like(support)
        shifted[:, :-1] = support[:, 1:] & self.actor.step_mask[:, 1:, None]
        return shifted

    @property
    def successor_present(self) -> Tensor:
        """Return whether each transition has at least one supported successor."""

        return self.successor_backup_mask.any(dim=-1)

    @property
    def bootstrap_mask(self) -> Tensor:
        """Return selected rows eligible for a supported non-terminal backup."""

        return self.selected_train_mask & ~self.supervision.terminal & self.successor_present

    def pin_memory(self) -> QhBatch:
        """Pin all tensor fields while preserving CPU-only keys by identity."""

        return _transform_batch(self, Tensor.pin_memory)

    def to(self, device: str | torch.device, *, non_blocking: bool = True) -> QhBatch:
        """Move all tensor fields to ``device`` while leaving keys on the CPU."""

        return _transform_batch(self, lambda value: value.to(device=device, non_blocking=non_blocking))


class QhDatasetConfig(TargetConfig["QhDataset"]):
    """Configure rollout stores and their immutable VIN actor store."""

    rollout_store_dirs: tuple[Path, ...] = Field(min_length=1)
    actor: VinOfflineStoreConfig = Field(default_factory=VinOfflineStoreConfig)
    split: Stage | None = None

    @field_validator("split", mode="before")
    @classmethod
    def _normalize_split(cls, value: Stage | str | None) -> Stage | None:
        return None if value is None or value == "all" else Stage.from_str(value)

    @property
    def target_type(self) -> type[QhDataset]:
        """Return the configured runtime dataset type."""

        return QhDataset

    def setup_target(self) -> QhDataset:
        """Construct the rollout and actor readers."""

        return QhDataset(
            rollout_reader=QhRolloutReader(self.rollout_store_dirs),
            actor_reader=VinOfflineStoreReader(self.actor),
            split=self.split,
        )


class QhDataset(Dataset[QhChain]):
    """Join validated rollout chains to one actor snippet per chain."""

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
        self._records = {record.sample_index: record for record in actor_reader.get_split_records(split)}
        self._validate_source_refs()

    def __len__(self) -> int:
        """Return the number of complete chains."""

        return len(self.rollout_reader)

    def __getitem__(self, index: int) -> QhChain:
        """Read one chain and its chain-constant actor snippet exactly once."""

        stored = self.rollout_reader[index]
        record = self._record(stored.source_ref)
        snippet = self.actor_reader.read_actor_snippet(record, device="cpu")
        return _tensor_chain(stored, snippet)

    @cached_property
    def scenes(self) -> frozenset[str]:
        """Return preflighted scene ids."""

        return self.rollout_reader.scenes

    @property
    def max_horizon(self) -> int:
        """Return the largest realized chain length in the corpus."""

        return self.rollout_reader.max_horizon

    @property
    def contract(self) -> QhDataContract:
        """Return the horizon- and provenance-independent learning contract."""

        return self.rollout_reader.contract

    @property
    def provenance(self) -> dict[str, object]:
        """Return store identity for audit displays, never for batch admission."""

        return {
            "rollout": self.rollout_reader.provenance,
            "actor": {
                "store_path": str(self.actor_reader.config.store_dir),
                "store_version": str(self.actor_reader.manifest.version),
                "manifest_hash": self._manifest_hash,
                "split": self.split,
                "row_count": len(self._records),
            },
        }

    def _validate_source_refs(self) -> None:
        for source_ref in self.rollout_reader.source_refs:
            self._record(source_ref)
        groups: dict[tuple[str, Stage, str], list[_QhSourceRef]] = {}
        for source_ref in self.rollout_reader.source_refs:
            groups.setdefault(
                (source_ref.source_manifest_hash, source_ref.split, source_ref.split_manifest_hash), []
            ).append(source_ref)
        for (manifest_hash, split, expected), source_refs in groups.items():
            records = [self._record(source_ref) for source_ref in source_refs]
            actual = build_rollout_split_manifest_hash(
                source_manifest_hash=manifest_hash,
                split=split.value,
                records=[
                    {
                        "order": order,
                        "sample_index": record.sample_index,
                        "sample_key": record.sample_key,
                        "scene_id": record.scene_id,
                        "snippet_id": record.snippet_id,
                        "split": record.split,
                        "source_shard_id": record.shard_id,
                        "source_shard_row": record.row,
                    }
                    for order, record in enumerate(records)
                ],
            )
            if actual != expected:
                raise ValueError(f"VIN split manifest does not match rollout source identity. {self._REBUILD_GUIDANCE}")

    def _record(self, source_ref: _QhSourceRef) -> VinOfflineIndexRecord:
        try:
            record = self._records[source_ref.source_sample_index]
        except KeyError as error:
            raise KeyError(
                f"VIN sample_index={source_ref.source_sample_index} is absent from split {self.split!r}. "
                f"{self._REBUILD_GUIDANCE}"
            ) from error
        actual = (
            record.sample_index,
            compact_ase_atek_sample_id(record.sample_key),
            record.shard_id,
            record.row,
            record.scene_id,
            compact_ase_atek_sample_id(record.snippet_id),
            Stage.from_str(record.split),
            str(self.actor_reader.manifest.version),
            self._manifest_hash,
        )
        expected = (
            source_ref.source_sample_index,
            compact_ase_atek_sample_id(source_ref.source_sample_key),
            source_ref.source_shard_id,
            source_ref.source_shard_row,
            source_ref.scene_id,
            compact_ase_atek_sample_id(source_ref.snippet_id),
            source_ref.split,
            source_ref.actor_store_version,
            source_ref.source_manifest_hash,
        )
        if actual != expected:
            raise ValueError(f"VIN source identity does not match rollout chain. {self._REBUILD_GUIDANCE}")
        return record


def collate_qh_chains(chains: list[QhChain]) -> QhBatch:
    """Pad heterogeneous time, candidate, history, and snippet axes."""

    if not chains:
        raise ValueError("Cannot collate an empty Q_H chain list.")
    actors = [chain.actor for chain in chains]
    supervision = [chain.supervision for chain in chains]
    snippets = [actor.vin_snippet for actor in actors]
    batch = QhBatch(
        actor=QhActorTensors(
            vin_snippet=VinSnippetView(
                points_world=_pad([value.points_world for value in snippets], float("nan")),
                lengths=torch.stack([value.lengths for value in snippets]),
                t_world_rig=PoseTW(_pad([value.t_world_rig.tensor() for value in snippets], 0)),
            ),
            root_pose_world=torch.stack([value.root_pose_world for value in actors]),
            target_pose_relative_root=torch.stack([value.target_pose_relative_root for value in actors]),
            target_extents=torch.stack([value.target_extents for value in actors]),
            candidate_pose_relative_root=_pad([value.candidate_pose_relative_root for value in actors], 0),
            candidate_mask=_pad([value.candidate_mask for value in actors], False),
            action_mask=_pad([value.action_mask for value in actors], False),
            history_pose_relative_root=_pad([value.history_pose_relative_root for value in actors], 0),
            history_mask=_pad([value.history_mask for value in actors], False),
            horizon_remaining=_pad([value.horizon_remaining for value in actors], 0),
            step_mask=_pad([value.step_mask for value in actors], False),
        ),
        supervision=QhSupervision(
            label_mask=_pad([value.label_mask for value in supervision], False),
            candidate_reward=_pad([value.candidate_reward for value in supervision], 0),
            selected_index=_pad([value.selected_index for value in supervision], -1),
            discount=_pad([value.discount for value in supervision], 0),
            terminal=_pad([value.terminal for value in supervision], True),
        ),
        keys=tuple(chain.key for chain in chains),
    )
    if bool((batch.supervision.label_mask & ~batch.actor.action_mask).any()):
        raise ValueError("Q_H label_mask must imply action_mask.")
    if bool((batch.actor.action_mask & ~batch.actor.candidate_mask).any()):
        raise ValueError("Q_H action_mask must imply candidate_mask.")
    return batch


def _tensor_chain(stored: _StoredChain, snippet: VinSnippetView) -> QhChain:
    candidate_pose = _stack_rows(stored.candidate_pose_relative_root, 0, torch.float32)
    action_mask = _stack_rows(stored.action_mask, False, torch.bool)
    label_mask = _stack_rows(stored.label_mask, False, torch.bool)
    reward = _stack_rows(stored.candidate_reward, 0, torch.float32)
    selected = _from_numpy(stored.selected_index, torch.int64)
    steps, width = action_mask.shape
    candidate_mask = torch.zeros((steps, width), dtype=torch.bool)
    for row, values in enumerate(stored.candidate_pose_relative_root):
        candidate_mask[row, : values.shape[0]] = True
    if bool((label_mask & ~action_mask).any() or (action_mask & ~candidate_mask).any()):
        raise ValueError("Q_H masks must satisfy label_mask <= action_mask <= candidate_mask.")
    history_pose = torch.zeros((steps, steps, 12), dtype=torch.float32)
    history_mask = torch.zeros((steps, steps), dtype=torch.bool)
    selected_pose = _gather_candidates(candidate_pose, selected)
    for step in range(1, steps):
        history_pose[step, :step] = selected_pose[:step]
        history_mask[step, :step] = True
    root_pose = PoseTW(_from_numpy(stored.root_pose_world, torch.float32))
    target_pose = PoseTW(_from_numpy(stored.target_pose_world_object, torch.float32))
    return QhChain(
        actor=QhActorTensors(
            vin_snippet=snippet,
            root_pose_world=root_pose.tensor(),
            target_pose_relative_root=root_pose.inverse().compose(target_pose).tensor(),
            target_extents=_from_numpy(stored.target_extents, torch.float32),
            candidate_pose_relative_root=candidate_pose,
            candidate_mask=candidate_mask,
            action_mask=action_mask,
            history_pose_relative_root=history_pose,
            history_mask=history_mask,
            horizon_remaining=_from_numpy(stored.horizon_remaining, torch.int64),
            step_mask=torch.ones(steps, dtype=torch.bool),
        ),
        supervision=QhSupervision(
            label_mask=label_mask,
            candidate_reward=reward,
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
        ),
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
    actor = batch.actor
    snippet = actor.vin_snippet
    transformed_actor = {
        field.name: transform(getattr(actor, field.name))
        for field in fields(QhActorTensors)
        if field.name != "vin_snippet"
    }
    transformed_supervision = {
        field.name: transform(getattr(batch.supervision, field.name)) for field in fields(QhSupervision)
    }
    return replace(
        batch,
        actor=QhActorTensors(
            vin_snippet=VinSnippetView(
                points_world=transform(snippet.points_world),
                lengths=transform(snippet.lengths),
                t_world_rig=PoseTW(transform(snippet.t_world_rig.tensor())),
            ),
            **transformed_actor,
        ),
        supervision=QhSupervision(**transformed_supervision),
    )


__all__ = ["QhBatch", "QhChain", "QhDataset", "QhDatasetConfig", "collate_qh_chains"]
