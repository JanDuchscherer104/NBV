r"""Scene-carrier modules for the finite-horizon :math:`Q_H` scorer.

A scene carrier maps actor-visible geometric evidence to one fixed-width state
feature per realized decision state.  It is deliberately narrower than the
complete scorer: it does not read candidates, targets, rewards, requested
horizon, remaining budget, labels, or authoritative action validity.  This
boundary keeps three scientific questions separable:

* which observations constitute the causal scene state;
* how that state is compressed into a shared state feature; and
* how a candidate later queries the resulting memory.

``QhRootMomentsSceneEncoder`` is the parameter-free ``root_moments_v1``
control.  Every configured root EVL channel contributes global mean, standard
deviation, minimum, and maximum.  Root semidense points contribute
coordinate-wise mean and standard deviation in the rollout-root frame plus
explicit presence and raw-capacity support.  Its exact
``Tensor["B F", float32]`` output preserves the pre-extraction scorer contract;
a later dynamic carrier must introduce its state axis explicitly rather than
hiding a semantic change in this refactor.

Global moments are intentionally lossy.  They discard topology, occlusion,
view direction, free-versus-unknown geometry, and selected-observation
updates.  The module is therefore a checkpoint-compatible control, not a
claim that root evidence is a sufficient Markov state.  Candidate-local point
or ray queries belong to a later relation module rather than being hidden in
this shared-carrier interface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypeAlias

import torch
from efm3d.aria.pose import PoseTW
from torch import Tensor, nn

if TYPE_CHECKING:
    from ...data_handling.qh_data import QhActorTensors

QhSceneChannel: TypeAlias = Literal["occ_pr", "occ_input", "free_input", "counts", "cent_pr"]
"""Persisted root-EVL channels admitted by ``root_moments_v1``."""


class QhRootMomentsSceneEncoder(nn.Module):
    r"""Encode immutable root evidence as global moments.

    For every configured scalar EVL field :math:`x_c`, the encoder records
    :math:`(\mu_c,\sigma_c,\min x_c,\max x_c)`.  Let
    :math:`T_{r\leftarrow w}` be root-from-world and :math:`p_k^w` a supported
    semidense point.  Root-frame points
    :math:`p_k^r=T_{r\leftarrow w}p_k^w` contribute coordinate-wise mean and
    population standard deviation.  Two final scalars distinguish no points
    from measured all-zero geometry: presence is
    :math:`1[|P|>0]`, while support is the supported-count divided by the
    batch-padded actor tensor's point-axis width.  That denominator is retained
    for checkpoint parity; it is batch-composition dependent and must not be
    interpreted as a per-chain sensor-density estimate.

    The resulting width is ``4 * len(scene_channels) + 8``.  Source tensors
    are detached because this carrier consumes persisted actor observations;
    it is not an end-to-end EFM3D training path.  Jointly translating the world
    points and root pose leaves the point moments invariant.  The evidence is
    immutable within one stored chain; scorer orchestration owns repetition
    over states and downstream candidate and step masks.
    """

    def __init__(self, *, scene_channels: tuple[QhSceneChannel, ...]) -> None:
        """Construct the parameter-free root-moments control.

        Args:
            scene_channels: Non-empty, unique, ordered root-EVL fields.  Order
                is representation identity because it fixes feature layout.

        Raises:
            ValueError: If the channel list is empty or contains duplicates.
        """

        super().__init__()
        if not scene_channels:
            raise ValueError("Q_H root-moments scene_channels must contain at least one field.")
        if len(set(scene_channels)) != len(scene_channels):
            raise ValueError("Q_H root-moments scene_channels must be unique and ordered.")
        self.scene_channels = scene_channels
        self.output_dim = 4 * len(scene_channels) + 8

    def forward(self, actor: QhActorTensors) -> Tensor:
        """Return ``Tensor[\"B F\", float32]`` root-scene features.

        ``B`` is taken from ``actor.step_mask`` and ``F == output_dim``.
        Missing configured EVL fields, non-finite source
        values, malformed point capacity, and non-finite active root poses fail
        closed instead of being encoded as ordinary zeros.
        """

        context = actor.static_context
        if context is None:
            raise ValueError("Q_H root-moments scene encoder requires compact root EVL context.")
        pooled = [self._pool_channel(getattr(context, name)) for name in self.scene_channels]

        points = actor.vin_snippet.points_world.detach().float()[..., :3]
        if points.ndim != 3:
            raise ValueError(f"Q_H batched semidense points must have shape (B,P,C), got {tuple(points.shape)}.")
        lengths = actor.vin_snippet.lengths.reshape(points.shape[0], -1)[:, 0].long()
        if bool((lengths < 0).any() or (lengths > points.shape[1]).any()):
            raise ValueError(f"Q_H semidense lengths must be in [0,{points.shape[1]}].")
        point_mask = torch.arange(points.shape[1], device=points.device).unsqueeze(0) < lengths.unsqueeze(1)
        point_mask &= torch.isfinite(points).all(dim=-1)

        root_active = actor.step_mask.any(dim=-1)
        root_values = actor.root_pose_world.tensor()
        root_finite = torch.isfinite(root_values).all(dim=-1)
        if bool((root_active & ~root_finite).any()):
            raise ValueError("Q_H active root poses must be finite.")
        identity = PoseTW().tensor().to(device=root_values.device, dtype=root_values.dtype).expand_as(root_values)
        root_from_world = PoseTW(torch.where(root_active.unsqueeze(-1), root_values, identity)).inverse()
        points_root = root_from_world.transform(points)

        safe_points = torch.where(point_mask.unsqueeze(-1), points_root, torch.zeros_like(points_root))
        valid_count = point_mask.sum(dim=1, keepdim=True)
        count = valid_count.clamp_min(1)
        mean = safe_points.sum(dim=1) / count
        centered = torch.where(
            point_mask.unsqueeze(-1),
            points_root - mean.unsqueeze(1),
            torch.zeros_like(points_root),
        )
        std = (centered.square().sum(dim=1) / count).sqrt()
        support = (valid_count.float() / max(points.shape[1], 1)).clamp(0.0, 1.0)
        present = valid_count.gt(0).float()
        return torch.cat((*pooled, mean, std, present, support), dim=-1)

    @staticmethod
    def _pool_channel(value: Tensor | None) -> Tensor:
        """Return mean, population deviation, minimum, and maximum per row."""

        if value is None:
            raise ValueError("Q_H root-moments scene encoder requires every configured root EVL field.")
        detached = value.detach().float()
        if detached.ndim < 2:
            raise ValueError(f"Q_H root EVL fields require a batch axis, got {tuple(detached.shape)}.")
        flat = detached.reshape(detached.shape[0], -1)
        if not bool(torch.isfinite(flat).all()):
            raise ValueError("Q_H root EVL fields must be finite.")
        return torch.stack(
            (
                flat.mean(dim=-1),
                flat.std(dim=-1, unbiased=False),
                flat.amin(dim=-1),
                flat.amax(dim=-1),
            ),
            dim=-1,
        )


__all__ = ["QhRootMomentsSceneEncoder", "QhSceneChannel"]
