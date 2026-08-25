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
from dataclasses import dataclass, replace
from typing import Literal

import torch
from efm3d.aria.camera import CameraTW
from efm3d.aria.pose import PoseTW
from torch import Tensor

from ..vin_store.views import VinSnippetView
from .views import (
    QhActorTensors,
    QhAudit,
    QhChain,
    QhChainKey,
    QhSelectedObservationPrefix,
    QhStaticContext,
    QhSupervision,
    validate_selected_observation_prefix,
)

QhObjectiveProfile = Literal["legacy_selected_rows_v1", "qh_dense_valid_fitted_q_v1"]


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

    audits: tuple[QhAudit | None, ...]
    """Length-``B`` optional diagnostic records aligned with ``keys`` and preserved by identity during transfer."""

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
        safe = torch.where(valid_index, selected, torch.zeros_like(selected))
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

        return QhBatch(
            actor=move_qh_actor_tensors(self.actor, device, non_blocking=non_blocking),
            supervision=_transform_supervision(
                self.supervision, lambda value: value.to(device=device, non_blocking=non_blocking)
            ),
            keys=self.keys,
            audits=self.audits,
        )


def collate_qh_chains(
    chains: list[QhChain],
    *,
    objective_profile: QhObjectiveProfile = "legacy_selected_rows_v1",
) -> QhBatch:
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
        ``label_mask <= action_mask <= candidate_mask``. The dense-valid
        objective additionally canonicalizes both supervision tables to finite
        values exactly on realized actor-valid support and NaN elsewhere.
    """

    if not chains:
        raise ValueError("Cannot collate an empty Q_H chain list.")
    actors = [chain.actor for chain in chains]
    supervision = [chain.supervision for chain in chains]
    snippets = [actor.vin_snippet for actor in actors]
    vin_snippet = VinSnippetView(
        points_world=_pad([value.points_world for value in snippets], float("nan")),
        lengths=torch.stack([value.lengths for value in snippets]),
        t_world_rig=PoseTW(_pad([value.t_world_rig.tensor() for value in snippets], 0)),
        t_world_snippet=PoseTW(_pad([value.t_world_snippet.tensor() for value in snippets], 0)),
    )
    batch = QhBatch(
        actor=QhActorTensors(
            vin_snippet=vin_snippet,
            root_pose_world=PoseTW(torch.stack([value.root_pose_world.tensor() for value in actors])),
            target_pose_relative_root=PoseTW(
                torch.stack([value.target_pose_relative_root.tensor() for value in actors])
            ),
            target_extents=torch.stack([value.target_extents for value in actors]),
            candidate_pose_relative_root=PoseTW(
                _pad([value.candidate_pose_relative_root.tensor() for value in actors], 0)
            ),
            candidate_mask=_pad([value.candidate_mask for value in actors], False),
            action_mask=_pad([value.action_mask for value in actors], False),
            history_pose_relative_root=PoseTW(_pad([value.history_pose_relative_root.tensor() for value in actors], 0)),
            history_mask=_pad([value.history_mask for value in actors], False),
            horizon_remaining=_pad([value.horizon_remaining for value in actors], 0),
            step_mask=_pad([value.step_mask for value in actors], False),
            static_context=_collate_static_context(actors, vin_snippet),
            selected_observation_prefix=_collate_selected_prefix(actors),
        ),
        supervision=QhSupervision(
            label_mask=_pad([value.label_mask for value in supervision], False),
            candidate_reward=_pad([value.candidate_reward for value in supervision], 0),
            one_step_target_rri=_pad([value.one_step_target_rri for value in supervision], float("nan")),
            selected_index=_pad([value.selected_index for value in supervision], -1),
            discount=_pad([value.discount for value in supervision], 0),
            terminal=_pad([value.terminal for value in supervision], True),
        ),
        keys=tuple(chain.key for chain in chains),
        audits=tuple(chain.audit for chain in chains),
    )
    if bool((batch.supervision.label_mask & ~batch.actor.action_mask).any()):
        raise ValueError("Q_H label_mask must imply action_mask.")
    if bool((batch.actor.action_mask & ~batch.actor.candidate_mask).any()):
        raise ValueError("Q_H action_mask must imply candidate_mask.")
    if batch.actor.selected_observation_prefix is not None:
        validate_selected_observation_prefix(
            batch.actor.selected_observation_prefix,
            history_mask=batch.actor.history_mask,
            step_mask=batch.actor.step_mask,
        )
    if objective_profile not in {"legacy_selected_rows_v1", "qh_dense_valid_fitted_q_v1"}:
        raise ValueError(f"Q_H collation received unsupported objective_profile={objective_profile!r}.")
    if objective_profile == "qh_dense_valid_fitted_q_v1":
        return _canonicalize_dense_valid(batch)
    return batch


def _canonicalize_dense_valid(batch: QhBatch) -> QhBatch:
    """Validate and canonicalize the deployable dense-valid fitted-Q support."""

    expected = batch.actor.action_mask & batch.actor.step_mask.unsqueeze(-1)
    if not torch.equal(batch.supervision.label_mask, expected):
        raise ValueError("Dense-valid Q_H label_mask must equal action_mask on every realized step.")
    reward = batch.supervision.candidate_reward
    target_rri = batch.supervision.one_step_target_rri
    if not bool(torch.isfinite(reward[expected]).all()):
        raise ValueError("Dense-valid Q_H candidate_reward must be finite on exact actor-valid support.")
    if not bool(torch.isfinite(target_rri[expected]).all()):
        raise ValueError("Dense-valid Q_H one_step_target_rri must be finite on exact actor-valid support.")
    supervision = replace(
        batch.supervision,
        candidate_reward=torch.where(expected, reward, torch.full_like(reward, float("nan"))),
        one_step_target_rri=torch.where(expected, target_rri, torch.full_like(target_rri, float("nan"))),
    )
    return replace(batch, supervision=supervision)


def _collate_static_context(actors: list[QhActorTensors], vin_snippet: VinSnippetView) -> QhStaticContext | None:
    """Collate root EVL evidence when every chain carries the same typed modality pattern."""

    contexts = [actor.static_context for actor in actors]
    if not any(contexts):
        return None
    if any(context is None for context in contexts):
        raise ValueError("Q_H batches cannot mix rich root contexts with legacy diagnostic chains.")
    values = [context for context in contexts if context is not None]
    presence = torch.stack([context.evl_presence for context in values])

    def collate(name: str) -> Tensor | None:
        fields = [getattr(context, name) for context in values]
        if not any(field is not None for field in fields):
            return None
        if any(field is None for field in fields):
            raise ValueError(f"Q_H batches require one shared EVL availability pattern for {name!r}.")
        present = [field for field in fields if field is not None]
        _require_matching_shapes(present, name=f"root EVL field {name!r}")
        return torch.stack(present) if present else None

    return QhStaticContext(
        vin_snippet=vin_snippet,
        t_world_voxel=_collate_optional_pose([context.t_world_voxel for context in values], name="t_world_voxel"),
        voxel_extent=collate("voxel_extent"),
        occ_pr=collate("occ_pr"),
        occ_input=collate("occ_input"),
        free_input=collate("free_input"),
        counts=collate("counts"),
        cent_pr=collate("cent_pr"),
        pts_world=collate("pts_world"),
        evl_presence=presence,
    )


def _collate_selected_prefix(actors: list[QhActorTensors]) -> QhSelectedObservationPrefix | None:
    """Pad causal CF-GT prefixes without admitting a future observation."""

    prefixes = [actor.selected_observation_prefix for actor in actors]
    if not any(prefixes):
        return None
    if any(prefix is None for prefix in prefixes):
        raise ValueError("Q_H batches cannot mix selected CF-GT prefix chains with legacy diagnostic chains.")
    values = [prefix for prefix in prefixes if prefix is not None]
    if {prefix.source_protocol for prefix in values} != {"cf_gt"}:
        raise ValueError("Q_H selected-observation batches require one CF-GT source protocol.")
    depth_shapes = {tuple(prefix.depth_m.shape[-2:]) for prefix in values}
    if len(depth_shapes) != 1:
        raise ValueError(f"Q_H selected-observation batches require one raster geometry, got {sorted(depth_shapes)}.")
    return QhSelectedObservationPrefix(
        depth_m=_pad([value.depth_m for value in values], 0),
        valid_mask=_pad([value.valid_mask for value in values], False),
        camera=CameraTW(_pad([value.camera.tensor() for value in values], 0)),
        camera_pose_relative_root=PoseTW(_pad([value.camera_pose_relative_root.tensor() for value in values], 0)),
        prefix_mask=_pad([value.prefix_mask for value in values], False),
    )


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


def _require_matching_shapes(values: list[Tensor], *, name: str) -> None:
    """Reject spatially incompatible tensors before generic chain-axis padding."""

    shapes = {tuple(value.shape) for value in values}
    if len(shapes) != 1:
        raise ValueError(f"Q_H batches require one {name} shape, got {sorted(shapes)}.")


def _gather_candidates(values: Tensor, indices: Tensor) -> Tensor:
    """Gather one candidate per leading row from scalar or vector-valued tables.

    Args:
        values: ``Tensor["... N", dtype]`` scalar or
            ``Tensor["... N D", dtype]`` vector-valued candidate table.
        indices: ``Tensor["...", int64]`` candidate indices aligned with the
            leading axes of ``values``.

    Returns:
        ``Tensor["...", dtype]`` or ``Tensor["... D", dtype]`` selected rows.
    Raises:
        ValueError: If the candidate table and index tensor have an unsupported
            rank relationship, or an index is outside the candidate axis.
    """

    rank_delta = values.ndim - indices.ndim
    if rank_delta not in (1, 2):
        raise ValueError(
            "Q_H candidate gather requires scalar or vector candidate tables "
            f"with values.ndim == indices.ndim + 1 or +2; got values.ndim={values.ndim}, "
            f"indices.ndim={indices.ndim}."
        )
    candidate_axis = -1 if rank_delta == 1 else -2
    candidate_width = values.shape[candidate_axis]
    if candidate_width < 1:
        raise ValueError("Q_H candidate gather cannot select from an empty candidate axis.")
    invalid = indices.lt(0) | indices.ge(candidate_width)
    if bool(invalid.any()):
        first = tuple(int(value) for value in torch.nonzero(invalid, as_tuple=False)[0].tolist())
        value = int(indices[first])
        raise ValueError(
            "Q_H candidate gather received an out-of-range factual index "
            f"{value} for candidate width {candidate_width} at index position {first}."
        )
    if rank_delta == 1:
        return values.gather(-1, indices.unsqueeze(-1)).squeeze(-1)
    expanded = indices.unsqueeze(-1).unsqueeze(-1).expand(*indices.shape, 1, values.shape[-1])
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

    supervision = batch.supervision
    return QhBatch(
        actor=_transform_actor_tensors(batch.actor, transform),
        supervision=_transform_supervision(supervision, transform),
        keys=batch.keys,
        audits=batch.audits,
    )


def move_qh_actor_tensors(
    actor: QhActorTensors,
    device: str | torch.device,
    *,
    non_blocking: bool = True,
) -> QhActorTensors:
    """Move every nested actor tensor while retaining typed pose containers."""

    return _transform_actor_tensors(actor, lambda value: value.to(device=device, non_blocking=non_blocking))


def _transform_actor_tensors(actor: QhActorTensors, transform: Callable[[Tensor], Tensor]) -> QhActorTensors:
    """Apply one tensor transform recursively to the canonical actor DTO."""

    snippet = actor.vin_snippet
    transformed_snippet = VinSnippetView(
        points_world=transform(snippet.points_world),
        lengths=transform(snippet.lengths),
        t_world_rig=PoseTW(transform(snippet.t_world_rig.tensor())),
        t_world_snippet=PoseTW(transform(snippet.t_world_snippet.tensor())),
    )
    return QhActorTensors(
        vin_snippet=transformed_snippet,
        root_pose_world=PoseTW(transform(actor.root_pose_world.tensor())),
        target_pose_relative_root=PoseTW(transform(actor.target_pose_relative_root.tensor())),
        target_extents=transform(actor.target_extents),
        candidate_pose_relative_root=PoseTW(transform(actor.candidate_pose_relative_root.tensor())),
        candidate_mask=transform(actor.candidate_mask),
        action_mask=transform(actor.action_mask),
        history_pose_relative_root=PoseTW(transform(actor.history_pose_relative_root.tensor())),
        history_mask=transform(actor.history_mask),
        horizon_remaining=transform(actor.horizon_remaining),
        step_mask=transform(actor.step_mask),
        static_context=_transform_static_context(actor.static_context, transformed_snippet, transform),
        selected_observation_prefix=_transform_selected_prefix(actor.selected_observation_prefix, transform),
    )


def _transform_supervision(supervision: QhSupervision, transform: Callable[[Tensor], Tensor]) -> QhSupervision:
    """Apply one tensor transform to supervision without exposing it to actors."""

    return QhSupervision(
        label_mask=transform(supervision.label_mask),
        candidate_reward=transform(supervision.candidate_reward),
        one_step_target_rri=transform(supervision.one_step_target_rri),
        selected_index=transform(supervision.selected_index),
        discount=transform(supervision.discount),
        terminal=transform(supervision.terminal),
    )


def _transform_static_context(
    context: QhStaticContext | None,
    vin_snippet: VinSnippetView,
    transform: Callable[[Tensor], Tensor],
) -> QhStaticContext | None:
    """Move root EVL tensors while retaining explicit missing-modality values."""

    if context is None:
        return None
    return QhStaticContext(
        vin_snippet=vin_snippet,
        t_world_voxel=_transform_optional_pose(context.t_world_voxel, transform),
        voxel_extent=_transform_optional(context.voxel_extent, transform),
        occ_pr=_transform_optional(context.occ_pr, transform),
        occ_input=_transform_optional(context.occ_input, transform),
        free_input=_transform_optional(context.free_input, transform),
        counts=_transform_optional(context.counts, transform),
        cent_pr=_transform_optional(context.cent_pr, transform),
        pts_world=_transform_optional(context.pts_world, transform),
        evl_presence=transform(context.evl_presence),
    )


def _transform_selected_prefix(
    prefix: QhSelectedObservationPrefix | None,
    transform: Callable[[Tensor], Tensor],
) -> QhSelectedObservationPrefix | None:
    """Move every selected CF-GT actor tensor while preserving its source tag."""

    if prefix is None:
        return None
    return QhSelectedObservationPrefix(
        depth_m=transform(prefix.depth_m),
        valid_mask=transform(prefix.valid_mask),
        camera=CameraTW(transform(prefix.camera.tensor())),
        camera_pose_relative_root=PoseTW(transform(prefix.camera_pose_relative_root.tensor())),
        prefix_mask=transform(prefix.prefix_mask),
        source_protocol=prefix.source_protocol,
    )


def _transform_optional(value: Tensor | None, transform: Callable[[Tensor], Tensor]) -> Tensor | None:
    """Transform one present tensor without manufacturing absent modality data."""

    return None if value is None else transform(value)


def _collate_optional_pose(values: list[PoseTW | None], *, name: str) -> PoseTW | None:
    """Stack one optional pose field without erasing its frame-aware container."""

    if not any(value is not None for value in values):
        return None
    if any(value is None for value in values):
        raise ValueError(f"Q_H batches require one shared pose availability pattern for {name!r}.")
    return PoseTW(torch.stack([value.tensor() for value in values if value is not None]))


def _transform_optional_pose(value: PoseTW | None, transform: Callable[[Tensor], Tensor]) -> PoseTW | None:
    """Transform one present pose while retaining its frame-aware container."""

    return None if value is None else PoseTW(transform(value.tensor()))


__all__ = ["QhBatch", "collate_qh_chains", "move_qh_actor_tensors"]
