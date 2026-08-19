r"""Batch construction and tensor transfer for heterogeneous Q_H chains.

Collation pads time, candidate, history, and VIN point axes while preserving
the distinct meanings of materialization, actor validity, label support,
history validity, and realized steps. Derived masks remain factual views over
that stored support; fitted-Q admission stays outside this module.
This module owns padding, collation, derived support views, and recursive tensor
transfer for :class:`QhBatch`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import torch
from efm3d.aria.pose import PoseTW
from torch import Tensor

from ..vin_store.views import VinSnippetView
from .views import QhActorTensors, QhChain, QhChainKey, QhSupervision


@dataclass(frozen=True, slots=True)
class QhBatch:
    """Padded Q_H chain batch with centralized tensor transfer.

    ``B`` denotes chains, ``S`` padded rollout states, and ``N`` padded
    candidates. Candidate, action, label, history, and step masks retain their
    separate support meanings after collation. Tensor transfer and pinning
    recurse through actor and supervision fields while preserving CPU-only
    chain keys by identity.
    """

    actor: QhActorTensors
    """Actor-visible tensors with leading ``B`` and common state, candidate, history, point, and pose extents."""

    supervision: QhSupervision
    """Oracle label support and factual transition tensors padded exactly like ``actor`` state/candidate axes."""

    keys: tuple[QhChainKey, ...]
    """Length-``B`` CPU-only audit keys in input order; never transferred or exposed to the scorer."""

    @property
    def num_steps(self) -> Tensor:
        """Return ``Tensor["B", int64]`` realized-state counts from ``step_mask``."""

        return self.actor.step_mask.sum(dim=-1)

    @property
    def selected_train_mask(self) -> Tensor:
        """Return ``Tensor["B S", bool]`` selected rows with finite immediate-target support.

        A true row is realized, has an in-range factual selected index, is
        actor-valid and label-supported at that index, and has finite selected
        reward and TD discount. Successor and terminal conditions are separate.
        """

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
        """Return ``Tensor["B S N", bool]`` label-supported actions at each next state.

        Row ``s`` contains ``action_mask & label_mask`` from realized state
        ``s+1``; the final/padded rows are false. This mask is backup support,
        not a factual selected-action sequence.
        """

        support = self.actor.action_mask & self.supervision.label_mask
        shifted = torch.zeros_like(support)
        shifted[:, :-1] = support[:, 1:] & self.actor.step_mask[:, 1:, None]
        return shifted

    @property
    def successor_action_mask(self) -> Tensor:
        """Return ``Tensor["B S N", bool]`` actor-valid actions at each next state.

        Unlike :attr:`successor_backup_mask`, this factual boundary view does
        not require oracle label support.
        """

        shifted = torch.zeros_like(self.actor.action_mask)
        shifted[:, :-1] = self.actor.action_mask[:, 1:] & self.actor.step_mask[:, 1:, None]
        return shifted

    @property
    def actor_successor_present(self) -> Tensor:
        """Return ``Tensor["B S", bool]`` indicating any actor-valid next-state action.

        A false non-terminal row is a no-actor-successor boundary. It remains
        distinguishable from a row that has actor actions but no labels.
        """

        return self.successor_action_mask.any(dim=-1)

    @property
    def successor_present(self) -> Tensor:
        """Return ``Tensor["B S", bool]`` indicating any label-supported next-state action."""

        return self.successor_backup_mask.any(dim=-1)

    @property
    def bootstrap_mask(self) -> Tensor:
        """Return ``Tensor["B S", bool]`` rows eligible for a supported TD backup.

        Terminal rows and no-actor-successor boundaries remain immediate-reward
        cases in the fitted-Q learner. A non-terminal row with actor successors
        but no label-supported successor is deliberately absent here and must
        not silently become an immediate-reward target.
        """

        return self.selected_train_mask & ~self.supervision.terminal & self.successor_present

    def pin_memory(self) -> QhBatch:
        """Return a batch with every nested tensor pinned and the same CPU key tuple."""

        return _transform_batch(self, Tensor.pin_memory)

    def to(self, device: str | torch.device, *, non_blocking: bool = True) -> QhBatch:
        """Move every nested tensor to ``device`` while leaving audit keys on the CPU.

        Args:
            device: Destination accepted by :meth:`torch.Tensor.to`.
            non_blocking: Request asynchronous transfer where the source and
                destination support it.

        Returns:
            New batch with aligned actor and supervision tensors on ``device``.
        """

        return _transform_batch(self, lambda value: value.to(device=device, non_blocking=non_blocking))


def collate_qh_chains(chains: list[QhChain]) -> QhBatch:
    """Pad heterogeneous chain axes and validate factual mask implications.

    Args:
        chains: Non-empty complete chains in desired batch order. Each chain
            may have different state, candidate, VIN-point, and trajectory
            extents while preserving one fixed-task remaining-budget sequence.

    Returns:
        :class:`QhBatch` whose axes cover every input and whose keys retain
        input order. Boolean support padding is false; rewards, discounts, and
        poses use zero; selected indices use ``-1``; terminal padding is true;
        VIN point padding is NaN. Padding never creates actor-valid or
        label-supported entries, and validation enforces
        ``label_mask <= action_mask <= candidate_mask``.
    """

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
                t_world_snippet=PoseTW(_pad([value.t_world_snippet.tensor() for value in snippets], 0)),
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


def _pad(values: list[Tensor], fill: int | float | bool) -> Tensor:
    """Pad equal-rank CPU tensors to per-axis maxima without changing dtype.

    Args:
        values: Non-empty tensors with equal rank and arbitrary per-axis sizes.
        fill: Scalar used outside each source tensor's leading-origin slices.

    Returns:
        Tensor with leading batch axis and shape ``(len(values), *axis_maxima)``.
    """

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
    """Gather one candidate per leading row from scalar or vector-valued tables.

    Args:
        values: ``Tensor["... N", dtype]`` scalar or
            ``Tensor["... N D", dtype]`` vector-valued candidate table.
        indices: ``Tensor["...", int64]`` candidate indices aligned with the
            leading axes of ``values``.

    Returns:
        ``Tensor["...", dtype]`` or ``Tensor["... D", dtype]`` selected rows.
        Indices are clamped for memory-safe gathering only; callers must use
        factual masks to establish whether an index is valid.
    """

    safe = indices.clamp(0, max(values.shape[-1] - 1, 0))
    if values.ndim == indices.ndim + 1:
        return values.gather(-1, safe.unsqueeze(-1)).squeeze(-1)
    expanded = safe.unsqueeze(-1).unsqueeze(-1).expand(*safe.shape, 1, values.shape[-1])
    return values.gather(-2, expanded).squeeze(-2)


def _transform_batch(batch: QhBatch, transform: Callable[[Tensor], Tensor]) -> QhBatch:
    """Apply one tensor transform recursively while retaining CPU audit identity.

    Args:
        batch: Padded batch whose actor and supervision tensors stay aligned.
        transform: Tensor-only operation such as pinning or device transfer.

    Returns:
        New batch with every tensor transformed, ``PoseTW`` reconstructed from
        its transformed storage tensor, and ``keys`` preserved by identity.
    """

    actor = batch.actor
    snippet = actor.vin_snippet
    supervision = batch.supervision
    return QhBatch(
        actor=QhActorTensors(
            vin_snippet=VinSnippetView(
                points_world=transform(snippet.points_world),
                lengths=transform(snippet.lengths),
                t_world_rig=PoseTW(transform(snippet.t_world_rig.tensor())),
                t_world_snippet=PoseTW(transform(snippet.t_world_snippet.tensor())),
            ),
            root_pose_world=transform(actor.root_pose_world),
            target_pose_relative_root=transform(actor.target_pose_relative_root),
            target_extents=transform(actor.target_extents),
            candidate_pose_relative_root=transform(actor.candidate_pose_relative_root),
            candidate_mask=transform(actor.candidate_mask),
            action_mask=transform(actor.action_mask),
            history_pose_relative_root=transform(actor.history_pose_relative_root),
            history_mask=transform(actor.history_mask),
            horizon_remaining=transform(actor.horizon_remaining),
            step_mask=transform(actor.step_mask),
        ),
        supervision=QhSupervision(
            label_mask=transform(supervision.label_mask),
            candidate_reward=transform(supervision.candidate_reward),
            selected_index=transform(supervision.selected_index),
            discount=transform(supervision.discount),
            terminal=transform(supervision.terminal),
        ),
        keys=batch.keys,
    )


__all__ = ["QhBatch", "collate_qh_chains"]
