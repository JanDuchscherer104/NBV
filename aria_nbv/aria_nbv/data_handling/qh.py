"""Framework-neutral joined data seam for finite-candidate ``Q_H`` training.

The module composes lazy rollout states with immutable, typed VIN actor rows.
It owns protocol-aware descriptor selection, exact lineage validation,
all-stage corpus admission, tensor conversion, deterministic padding, and the
single batch pin/transfer interface. Rollout storage interpretation remains in
:mod:`aria_nbv.rollouts.qh_reader`; DataLoader and distributed-sampler policy
belong to :mod:`aria_nbv.lightning.qh_datamodule`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import cached_property
from typing import Protocol

import numpy as np
import torch
from efm3d.aria.pose import PoseTW
from torch import Tensor
from torch.utils.data import Dataset

from ..rollouts import qh_reader as rollout_qh
from ..targets.protocol import TargetDescriptorProvenance, TargetInputProtocol, validate_target_protocol_admission
from ..utils import TargetConfig
from .offline.actor import VinActorSample, VinActorSource, VinActorSourceConfig
from .raw.views import VinSnippetView


@dataclass(frozen=True, slots=True)
class QhActorInputs:
    """Actor-visible tensors for one state or a padded batch of states.

    Candidate and history axes are compact for a sample and right-padded for a
    batch. Only `actor_action_mask` and `history_mask` define usable rows;
    padded ids are ``-1``. Candidate and history camera poses cross this
    interface only in the rollout-root frame used by the scorer; their
    world-frame storage copies remain audit data. No Oracle label, invalid
    reason, selection diagnostic, or selected-depth raster crosses this
    interface.
    """

    vin_snippet: VinSnippetView
    """Typed semidense points, valid lengths, and world-from-rig history."""

    root_pose_world: Tensor
    """``Tensor["12", float32]`` or ``Tensor["B 12", float32]`` world-from-rollout-root pose."""

    target_extents: Tensor
    """``Tensor["3", float32]`` or ``Tensor["B 3", float32]`` V0 OBB extents in metres."""

    target_pose_world_object: Tensor
    """``Tensor["12", float32]`` or ``Tensor["B 12", float32]`` V0 object pose in world frame."""

    candidate_row_id: Tensor
    """``Tensor["N_q", int64]`` or ``Tensor["B N_q", int64]`` stable ids; padding is ``-1``."""

    candidate_pose_relative_root: Tensor
    """``Tensor["N_q 12", float32]`` or ``Tensor["B N_q 12", float32]`` root-from-camera poses."""

    candidate_position_id: Tensor
    """``Tensor["N_q", int64]`` or ``Tensor["B N_q", int64]`` position-family ids; padding is ``-1``."""

    actor_action_mask: Tensor
    """``Tensor["N_q", bool]`` or ``Tensor["B N_q", bool]`` hard action mask; padding is false."""

    history_candidate_row_id: Tensor
    """``Tensor["H_t", int64]`` or ``Tensor["B H_t", int64]`` prior candidate ids; padding is ``-1``."""

    history_pose_relative_root: Tensor
    """``Tensor["H_t 12", float32]`` or ``Tensor["B H_t 12", float32]`` prior root-from-camera poses."""

    history_position_id: Tensor
    """``Tensor["H_t", int64]`` or ``Tensor["B H_t", int64]`` prior position-family ids; padding is ``-1``."""

    history_mask: Tensor
    """``Tensor["H_t", bool]`` or ``Tensor["B H_t", bool]`` history-presence mask; padding is false."""

    remaining_budget: Tensor
    """``Tensor["", int64]`` or ``Tensor["B", int64]`` remaining acquisition count."""


@dataclass(frozen=True, slots=True)
class QhTransition:
    """Selected-transition tensors and the exact row-level training gate."""

    selected_candidate_index: Tensor
    """``Tensor["", int64]`` or ``Tensor["B", int64]`` selected full-shell indices."""

    selected_candidate_row_id: Tensor
    """``Tensor["", int64]`` or ``Tensor["B", int64]`` selected stable candidate ids."""

    reward: Tensor
    """``Tensor["", float32]`` or ``Tensor["B", float32]`` selected target-root-gain rewards."""

    discount: Tensor
    """``Tensor["", float32]`` or ``Tensor["B", float32]`` gamma-or-zero TD discounts."""

    terminal: Tensor
    """``Tensor["", bool]`` or ``Tensor["B", bool]`` terminal flags."""

    row_train_mask: Tensor
    """``Tensor["", bool]`` or ``Tensor["B", bool]`` exact fitted-Q admission gate."""


@dataclass(frozen=True, slots=True)
class QhLineage:
    """Audit-only current and optional next rollout provenance."""

    current: rollout_qh.QhLineage
    """Exact persisted lineage for the current rollout state."""

    next: rollout_qh.QhLineage | None
    """Exact persisted lineage for the admitted successor, when present."""


@dataclass(frozen=True, slots=True)
class QhSample:
    """One transition-complete, actor-safe finite-candidate training sample."""

    current_actor: QhActorInputs
    """Current model input view."""

    next_actor: QhActorInputs | None
    """Admitted successor model input, absent exactly for terminal rows."""

    transition: QhTransition
    """Selected transition and row-level training gate."""

    lineage: QhLineage
    """Audit provenance excluded from model calls."""


class QhStageDataset(Protocol):
    """Static interface required for one admitted ``Q_H`` corpus stage.

    Admission consumes only compact metadata. It never calls
    :meth:`__getitem__`, so a caller can validate split and horizon contracts
    before any rollout matrix, candidate payload, or actor row is materialized.
    """

    scene_ids: frozenset[str]
    """Scene identifiers represented by this stage."""

    q_h_horizon: int
    """Positive residual horizon shared by every stage in one corpus."""

    provenance: dict[str, object]
    """JSON-serializable identity decoded during stage preflight."""

    def __len__(self) -> int:
        """Return the number of joined rollout states."""

    def __getitem__(self, index: int) -> QhSample:
        """Return one joined actor/transition sample."""


@dataclass(frozen=True, slots=True, init=False)
class QhCorpus:
    """Admitted train/validation/test datasets for one fitted-Q experiment.

    Use :meth:`admit` as the sole construction interface. It proves non-empty
    training data, a common positive horizon, and scene-disjoint configured
    stages before :mod:`pytorch_lightning` constructs a Trainer.
    """

    train: QhStageDataset
    """Required training stage."""

    val: QhStageDataset | None
    """Optional scene-disjoint validation stage."""

    test: QhStageDataset | None
    """Optional scene-disjoint held-out stage."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Reject construction that bypasses :meth:`admit`."""

        raise TypeError("QhCorpus must be constructed through QhCorpus.admit(...).")

    @classmethod
    def admit(
        cls,
        *,
        train: QhStageDataset,
        val: QhStageDataset | None = None,
        test: QhStageDataset | None = None,
    ) -> QhCorpus:
        """Validate all configured stages without materializing dataset rows."""

        stages = {
            name: dataset for name, dataset in (("train", train), ("val", val), ("test", test)) if dataset is not None
        }
        empty = [name for name, dataset in stages.items() if len(dataset) < 1]
        if empty:
            raise ValueError(f"Q_H configured corpus stages must contain at least one state: {empty}.")
        horizons = {name: dataset.q_h_horizon for name, dataset in stages.items()}
        invalid_horizons = {name: value for name, value in horizons.items() if not _is_positive_int(value)}
        if invalid_horizons:
            raise ValueError(f"Q_H corpus stages require positive integer horizons: {invalid_horizons}.")
        if len(set(horizons.values())) != 1:
            raise ValueError(f"Q_H corpus stage horizons disagree: {horizons}.")
        names = tuple(stages)
        for index, left in enumerate(names):
            for right in names[index + 1 :]:
                overlap = stages[left].scene_ids & stages[right].scene_ids
                if overlap:
                    raise ValueError(
                        f"Q_H {left}/{right} datasets overlap scenes {sorted(overlap)}; use scene-level splits."
                    )
        corpus = object.__new__(cls)
        object.__setattr__(corpus, "train", train)
        object.__setattr__(corpus, "val", val)
        object.__setattr__(corpus, "test", test)
        return corpus

    @property
    def q_h_horizon(self) -> int:
        """Return the horizon proven common across every configured stage."""

        return self.train.q_h_horizon

    @property
    def provenance(self) -> dict[str, object]:
        """Return compact preflighted provenance for every admitted stage."""

        return {
            name: None if dataset is None else dataset.provenance
            for name, dataset in (("train", self.train), ("val", self.val), ("test", self.test))
        }


@dataclass(frozen=True, slots=True)
class QhBatch:
    """Padded transition batch with explicit mixed-terminal presence masks."""

    current_actor: QhActorInputs
    """Padded current actor views."""

    next_actor: QhActorInputs | None
    """Padded successor actor views, absent only when the whole batch is terminal."""

    next_actor_present: Tensor
    """``Tensor["B", bool]`` identifying rows represented in `next_actor`."""

    transition: QhTransition
    """Batched selected-transition facts and row masks."""

    lineage: tuple[QhLineage, ...]
    """Per-row audit provenance, never passed to the model."""

    def assert_selected_rows_consistent(self) -> None:
        """Reject any admitted transition inconsistent with its actor row.

        For every row admitted by :attr:`QhTransition.row_train_mask`, the
        selected index must address the current candidate table, resolve to the
        persisted selected row id, remain actor-valid, and carry finite reward
        and discount values. This data-owned assertion is the single semantic
        boundary consumed before fitted-Q target construction.

        Raises:
            ValueError: If any admitted selected transition violates the
                index, row-id, actor-mask, reward, or discount contract.
        """

        admitted = self.transition.row_train_mask.bool()
        if not admitted.any():
            return
        selected = self.transition.selected_candidate_index.long()
        width = self.current_actor.candidate_row_id.shape[1]
        valid_index = selected.ge(0) & selected.lt(width)
        if not valid_index[admitted].all():
            raise ValueError("Trainable selected Q_H row has an out-of-range candidate index.")
        safe = selected.clamp(0, max(width - 1, 0)).unsqueeze(1)
        row_ids = self.current_actor.candidate_row_id.gather(1, safe).squeeze(1)
        actor_mask = self.current_actor.actor_action_mask.gather(1, safe).squeeze(1)
        valid = (
            row_ids.eq(self.transition.selected_candidate_row_id)
            & actor_mask.bool()
            & torch.isfinite(self.transition.reward)
            & torch.isfinite(self.transition.discount)
        )
        if not valid[admitted].all():
            raise ValueError("Trainable selected Q_H row violates row-id, mask, reward, or discount admission.")

    def pin_memory(self) -> QhBatch:
        """Pin every tensor-bearing field while retaining CPU audit lineage.

        This is the custom-batch contract used by PyTorch
        [memory pinning](https://docs.pytorch.org/docs/2.4/data.html#memory-pinning).
        Lineage is immutable Python/NumPy audit state and is intentionally
        returned by identity.
        """

        return _transform_batch(self, lambda value: value.pin_memory())

    def to(self, device: str | torch.device, *, non_blocking: bool = True) -> QhBatch:
        """Move all tensors to `device` and keep lineage on the CPU.

        `non_blocking=True` requests asynchronous copies from pinned host
        memory; PyTorch may fall back to a synchronous copy when the source or
        destination cannot support it.
        """

        return _transform_batch(
            self,
            lambda value: value.to(device=device, non_blocking=non_blocking),
        )


class QhDatasetConfig(TargetConfig["QhDataset"]):
    """Configure the lazy rollout reader and immutable VIN actor source."""

    rollout: rollout_qh.QhRolloutReaderConfig
    """Homogeneous V0 rollout corpus configuration."""

    actor: VinActorSourceConfig
    """Actor-only immutable VIN source configuration."""

    @property
    def target_type(self) -> type[QhDataset]:
        """Runtime dataset constructed by :meth:`setup_target`."""

        return QhDataset


class QhDataset(Dataset[QhSample]):
    """Join rollout transitions and immutable actor evidence by exact lineage.

    :class:`aria_nbv.rollouts.qh_reader.QhRolloutReader` supplies current and
    successor rollout facts; :class:`aria_nbv.data_handling.offline.actor.VinActorSource`
    supplies typed actor-visible observation evidence. Construction validates every
    compact source join before :meth:`__getitem__` can materialize a sample.
    Oracle diagnostics stay outside :class:`QhActorInputs`. Candidate-wide
    training masks are consumed here and reduced to the selected transition's
    scalar :attr:`QhTransition.row_train_mask`.
    """

    def __init__(
        self,
        config: QhDatasetConfig | None = None,
        *,
        rollout_reader: rollout_qh.QhRolloutReader | None = None,
        actor_source: VinActorSource | None = None,
    ) -> None:
        """Construct from a config or explicit adapters for focused tests.

        Exactly one construction form must be used. Dependencies are accepted
        rather than created when explicit adapters are supplied, keeping the
        dataset interface directly testable.
        """

        if config is not None:
            if rollout_reader is not None or actor_source is not None:
                raise ValueError("QhDataset accepts either config or explicit adapters, not both.")
            rollout_reader = config.rollout.setup_target()
            actor_source = config.actor.setup_target()
        if rollout_reader is None or actor_source is None:
            raise ValueError("QhDataset requires both a rollout reader and VIN actor source.")
        self.rollout_reader = rollout_reader
        self.actor_source = actor_source
        self._validate_source_lineage()

    def __len__(self) -> int:
        """Return the validated rollout-state count."""

        return len(self.rollout_reader)

    def __getitem__(self, index: int) -> QhSample:
        """Join one selected transition and optional successor to actor evidence.

        The returned :class:`QhSample` preserves exact candidate-row alignment.
        ``row_train_mask`` is true only when the selected index is in range,
        its candidate is admitted by ``q_train_mask``, and reward/discount are
        finite.
        """

        current = self.rollout_reader[index]
        current_actor = self._compose_actor(current)
        next_state = None
        next_actor = None
        if current.transition.next_state is not None:
            next_state = self.rollout_reader.read(current.transition.next_state)
            self._validate_transition_link(current, next_state)
            next_actor = self._compose_actor(next_state)

        selected = current.transition.selected_candidate_index
        selected_index_valid = 0 <= selected < current.supervision.q_train_mask.shape[0]
        row_train = bool(
            selected_index_valid
            and current.supervision.q_train_mask[selected]
            and np.isfinite(current.transition.reward)
            and np.isfinite(current.transition.discount)
        )
        return QhSample(
            current_actor=current_actor,
            next_actor=next_actor,
            transition=QhTransition(
                selected_candidate_index=torch.tensor(selected, dtype=torch.int64),
                selected_candidate_row_id=torch.tensor(
                    current.transition.selected_candidate_row_id,
                    dtype=torch.int64,
                ),
                reward=torch.tensor(current.transition.reward, dtype=torch.float32),
                discount=torch.tensor(current.transition.discount, dtype=torch.float32),
                terminal=torch.tensor(current.transition.terminal, dtype=torch.bool),
                row_train_mask=torch.tensor(row_train, dtype=torch.bool),
            ),
            lineage=QhLineage(current=current.lineage, next=None if next_state is None else next_state.lineage),
        )

    @cached_property
    def scene_ids(self) -> frozenset[str]:
        """Return scene ids for split-disjointness checks before loader creation."""

        return self.rollout_reader.scene_ids

    @property
    def q_h_horizon(self) -> int:
        """Return :attr:`QhRolloutReader.q_h_horizon` without reading samples."""

        return self.rollout_reader.q_h_horizon

    @property
    def provenance(self) -> dict[str, object]:
        """Return joined rollout and actor identities without loading a sample."""

        return {
            "rollout": self.rollout_reader.provenance,
            "actor": self.actor_source.provenance,
        }

    def _validate_source_lineage(self) -> None:
        """Validate every compact rollout/source join before any batch can load."""

        for lineage in self.rollout_reader.source_lineage:
            self._actor_source_index(lineage)

    def _compose_actor(self, state: rollout_qh.QhRolloutState) -> QhActorInputs:
        lineage = state.lineage
        protocol = validate_target_protocol_admission(
            lineage.target_protocol_version,
            target_source=lineage.target_source,
            descriptor_source=lineage.target_source,
            descriptor_provenance=TargetDescriptorProvenance.ORACLE_GT,
        )
        if protocol is not TargetInputProtocol.V0_GT_INPUT:
            raise ValueError("QhDataset currently materializes only v0_gt_input target descriptors.")

        source_index = self._actor_source_index(lineage)
        return _tensor_actor(
            self.actor_source[source_index],
            state.actor,
        )

    def _actor_source_index(self, lineage: rollout_qh.QhLineage | rollout_qh.QhSourceLineage) -> int:
        """Resolve and validate one compact rollout-to-source join."""

        source_index = self.actor_source.index_for_sample(lineage.source_sample_index)
        self.actor_source.validate_lineage(
            source_index,
            source_sample_index=lineage.source_sample_index,
            source_sample_key=lineage.source_sample_key,
            source_shard_id=lineage.source_shard_id,
            source_shard_row=lineage.source_shard_row,
            source_offline_store_version=lineage.source_cache_version,
            source_offline_store_manifest_hash=lineage.source_offline_store_manifest_hash,
            scene_id=lineage.scene_id,
            snippet_id=lineage.snippet_id,
            split=lineage.split,
        )
        return source_index

    @staticmethod
    def _validate_transition_link(
        current: rollout_qh.QhRolloutState,
        next_state: rollout_qh.QhRolloutState,
    ) -> None:
        expected = current.transition.next_state
        if expected != next_state.locator:
            raise ValueError("Q_H successor locator changed during dataset composition.")
        if (
            next_state.lineage.rollout_row_id != current.lineage.rollout_row_id
            or next_state.lineage.step_index != current.lineage.step_index + 1
            or next_state.lineage.source_sample_index != current.lineage.source_sample_index
        ):
            raise ValueError("Q_H successor crosses rollout, step, or source lineage.")


def collate_qh_samples(samples: list[QhSample]) -> QhBatch:
    """Collate transition samples with deterministic right padding.

    Candidate and history ids use ``-1`` sentinels, pose/features use zeros,
    and all associated masks use false. Mixed terminal batches receive an
    empty padded successor row plus ``next_actor_present=False``; an all-terminal
    batch keeps ``next_actor=None``. This is the ``collate_fn`` used by
    :class:`aria_nbv.lightning.qh_datamodule.QhDataModule` and PyTorch's
    [DataLoader](https://docs.pytorch.org/docs/stable/data.html#torch.utils.data.DataLoader).

    Args:
        samples: Non-empty list of transition-complete :class:`QhSample` rows.

    Returns:
        :class:`QhBatch` with batch axis ``B=len(samples)`` and independently
        padded current/successor candidate and history axes.
    """

    if not samples:
        raise ValueError("Cannot collate an empty Q_H sample list.")
    current_actor = _collate_actor([sample.current_actor for sample in samples])
    next_present = torch.tensor([sample.next_actor is not None for sample in samples], dtype=torch.bool)
    next_actor = None
    if bool(next_present.any()):
        exemplar = next(sample.next_actor for sample in samples if sample.next_actor is not None)
        assert exemplar is not None
        next_actor = _collate_actor(
            [sample.next_actor if sample.next_actor is not None else _empty_actor_like(exemplar) for sample in samples]
        )

    transition = QhTransition(
        selected_candidate_index=torch.stack([sample.transition.selected_candidate_index for sample in samples]),
        selected_candidate_row_id=torch.stack([sample.transition.selected_candidate_row_id for sample in samples]),
        reward=torch.stack([sample.transition.reward for sample in samples]),
        discount=torch.stack([sample.transition.discount for sample in samples]),
        terminal=torch.stack([sample.transition.terminal for sample in samples]),
        row_train_mask=torch.stack([sample.transition.row_train_mask for sample in samples]),
    )
    return QhBatch(
        current_actor=current_actor,
        next_actor=next_actor,
        next_actor_present=next_present,
        transition=transition,
        lineage=tuple(sample.lineage for sample in samples),
    )


def _tensor_actor(
    source: VinActorSample,
    state: rollout_qh.QhActorState,
) -> QhActorInputs:
    history_count = int(state.history_candidate_row_id.shape[0])
    return QhActorInputs(
        vin_snippet=source.snippet,
        root_pose_world=_from_numpy(state.root_pose_world, torch.float32),
        target_extents=_from_numpy(state.target_extents, torch.float32),
        target_pose_world_object=_from_numpy(state.target_pose_world_object, torch.float32),
        candidate_row_id=_from_numpy(state.candidate_row_id, torch.int64),
        candidate_pose_relative_root=_from_numpy(state.candidate_pose_relative_root, torch.float32),
        candidate_position_id=_from_numpy(state.candidate_position_id, torch.int64),
        actor_action_mask=_from_numpy(state.actor_action_mask, torch.bool),
        history_candidate_row_id=_from_numpy(state.history_candidate_row_id, torch.int64),
        history_pose_relative_root=_from_numpy(state.history_pose_relative_root, torch.float32),
        history_position_id=_from_numpy(state.history_position_id, torch.int64),
        history_mask=torch.ones(history_count, dtype=torch.bool),
        remaining_budget=torch.tensor(state.remaining_budget, dtype=torch.int64),
    )


def _from_numpy(value: np.ndarray, dtype: torch.dtype | None = None) -> Tensor:
    tensor = torch.from_numpy(np.array(value, copy=True))
    return tensor if dtype is None else tensor.to(dtype=dtype)


def _collate_actor(actors: list[QhActorInputs]) -> QhActorInputs:
    snippets = [actor.vin_snippet for actor in actors]
    vin_snippet = VinSnippetView(
        points_world=_pad_nd([snippet.points_world for snippet in snippets], float("nan")),
        lengths=torch.stack([snippet.lengths for snippet in snippets]),
        t_world_rig=PoseTW(_pad_first_axis([snippet.t_world_rig.tensor() for snippet in snippets], 0)),
    )
    return QhActorInputs(
        vin_snippet=vin_snippet,
        root_pose_world=torch.stack([actor.root_pose_world for actor in actors]),
        target_extents=torch.stack([actor.target_extents for actor in actors]),
        target_pose_world_object=torch.stack([actor.target_pose_world_object for actor in actors]),
        candidate_row_id=_pad_first_axis([actor.candidate_row_id for actor in actors], -1),
        candidate_pose_relative_root=_pad_first_axis(
            [actor.candidate_pose_relative_root for actor in actors],
            0,
        ),
        candidate_position_id=_pad_first_axis([actor.candidate_position_id for actor in actors], -1),
        actor_action_mask=_pad_first_axis([actor.actor_action_mask for actor in actors], False),
        history_candidate_row_id=_pad_first_axis([actor.history_candidate_row_id for actor in actors], -1),
        history_pose_relative_root=_pad_first_axis(
            [actor.history_pose_relative_root for actor in actors],
            0,
        ),
        history_position_id=_pad_first_axis([actor.history_position_id for actor in actors], -1),
        history_mask=_pad_first_axis([actor.history_mask for actor in actors], False),
        remaining_budget=torch.stack([actor.remaining_budget for actor in actors]),
    )


def _empty_actor_like(actor: QhActorInputs) -> QhActorInputs:
    def empty(value: Tensor) -> Tensor:
        return value.new_empty((0, *value.shape[1:]))

    return replace(
        actor,
        vin_snippet=VinSnippetView(
            points_world=empty(actor.vin_snippet.points_world),
            lengths=torch.zeros_like(actor.vin_snippet.lengths),
            t_world_rig=PoseTW(empty(actor.vin_snippet.t_world_rig.tensor())),
        ),
        root_pose_world=torch.zeros_like(actor.root_pose_world),
        target_extents=torch.zeros_like(actor.target_extents),
        target_pose_world_object=torch.zeros_like(actor.target_pose_world_object),
        candidate_row_id=empty(actor.candidate_row_id),
        candidate_pose_relative_root=empty(actor.candidate_pose_relative_root),
        candidate_position_id=empty(actor.candidate_position_id),
        actor_action_mask=empty(actor.actor_action_mask),
        history_candidate_row_id=empty(actor.history_candidate_row_id),
        history_pose_relative_root=empty(actor.history_pose_relative_root),
        history_position_id=empty(actor.history_position_id),
        history_mask=empty(actor.history_mask),
        remaining_budget=torch.tensor(0, dtype=torch.int64),
    )


def _pad_first_axis(values: list[Tensor], fill: int | float | bool) -> Tensor:
    return _pad_nd(values, fill, only_first=True)


def _pad_nd(values: list[Tensor], fill: int | float | bool, *, only_first: bool = False) -> Tensor:
    if not values:
        raise ValueError("Cannot pad an empty tensor list.")
    ndim = values[0].ndim
    if any(value.ndim != ndim for value in values):
        raise ValueError("Q_H tensors with different ranks cannot share one padded field.")
    maxima = [max(value.shape[axis] for value in values) for axis in range(ndim)]
    if only_first:
        expected_tail = values[0].shape[1:]
        if any(value.shape[1:] != expected_tail for value in values[1:]):
            raise ValueError("Only the leading Q_H candidate/history axis may vary.")
        maxima[1:] = expected_tail
    output = torch.full((len(values), *maxima), fill, dtype=values[0].dtype)
    for row, value in enumerate(values):
        selection = (row, *(slice(0, size) for size in value.shape))
        output[selection] = value
    return output


def _transform_batch(batch: QhBatch, transform: Callable[[Tensor], Tensor]) -> QhBatch:
    """Apply one tensor transform while preserving the batch's lineage identity."""

    return replace(
        batch,
        current_actor=_transform_actor(batch.current_actor, transform),
        next_actor=None if batch.next_actor is None else _transform_actor(batch.next_actor, transform),
        next_actor_present=transform(batch.next_actor_present),
        transition=replace(
            batch.transition,
            selected_candidate_index=transform(batch.transition.selected_candidate_index),
            selected_candidate_row_id=transform(batch.transition.selected_candidate_row_id),
            reward=transform(batch.transition.reward),
            discount=transform(batch.transition.discount),
            terminal=transform(batch.transition.terminal),
            row_train_mask=transform(batch.transition.row_train_mask),
        ),
    )


def _transform_actor(actor: QhActorInputs, transform: Callable[[Tensor], Tensor]) -> QhActorInputs:
    """Apply a batch-owned transform to every actor tensor."""

    snippet = actor.vin_snippet
    return replace(
        actor,
        vin_snippet=VinSnippetView(
            points_world=transform(snippet.points_world),
            lengths=transform(snippet.lengths),
            t_world_rig=PoseTW(transform(snippet.t_world_rig.tensor())),
        ),
        root_pose_world=transform(actor.root_pose_world),
        target_extents=transform(actor.target_extents),
        target_pose_world_object=transform(actor.target_pose_world_object),
        candidate_row_id=transform(actor.candidate_row_id),
        candidate_pose_relative_root=transform(actor.candidate_pose_relative_root),
        candidate_position_id=transform(actor.candidate_position_id),
        actor_action_mask=transform(actor.actor_action_mask),
        history_candidate_row_id=transform(actor.history_candidate_row_id),
        history_pose_relative_root=transform(actor.history_pose_relative_root),
        history_position_id=transform(actor.history_position_id),
        history_mask=transform(actor.history_mask),
        remaining_budget=transform(actor.remaining_budget),
    )


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


__all__ = [
    "QhActorInputs",
    "QhBatch",
    "QhCorpus",
    "QhDataset",
    "QhDatasetConfig",
    "QhLineage",
    "QhSample",
    "QhStageDataset",
    "QhTransition",
    "collate_qh_samples",
]
