"""Selected-transition fitted Double-Q training for finite-candidate rollouts.

:class:`QhLightningModule` owns Bellman target construction, exact row
admission, distributed loss normalization, optimization, and hard target-network
synchronization. Actor-only feature construction belongs to
:mod:`aria_nbv.vin.models.target_finite_horizon`; transition loading and padding
belong to :mod:`aria_nbv.lightning.qh_data`.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytorch_lightning as pl
import torch
from jaxtyping import Float
from pydantic import Field
from torch import Tensor, nn
from torch.nn import functional
from torch.optim import Optimizer

from ..utils import TargetConfig
from ..vin.models.target_finite_horizon import MultiStepCandidateScorerConfig
from .optimizers import AdamWConfig
from .qh_data import QhBatch


class QhLightningModuleConfig(TargetConfig["QhLightningModule"]):
    """Configure the finite-horizon scorer, loss, optimizer, and target sync."""

    scorer: MultiStepCandidateScorerConfig = Field(default_factory=MultiStepCandidateScorerConfig)
    """Actor-only finite-candidate value scorer."""

    optimizer: AdamWConfig = Field(default_factory=AdamWConfig)
    """AdamW settings applied only to online-scorer parameters."""

    huber_delta: float = Field(default=1.0, gt=0.0)
    """Positive transition point for the selected-action Huber loss."""

    target_sync_interval: int = Field(default=100, ge=1)
    """Hard target-copy cadence measured in completed optimizer updates."""

    @property
    def target_type(self) -> type["QhLightningModule"]:
        """Runtime module constructed by :meth:`setup_target`."""

        return QhLightningModule


class QhLightningModule(pl.LightningModule):
    r"""Train finite-shell values from persisted selected transitions.

    The online network selects the next action and the frozen target network
    evaluates it:

    $$
    a^*=\arg\max_{a\in\mathcal{A}_{valid}}Q_{online}(s',a),\qquad
    y=r+\gamma b Q_{target}(s',a^*).
    $$

    Here $b$ is the bootstrap gate: it is one only for an admitted,
    non-terminal row with a materialized successor and at least one valid next
    action. Only rows admitted by
    :attr:`aria_nbv.lightning.qh_data.QhTransition.row_train_mask` contribute
    to the Huber objective. The summed local losses are normalized by the exact
    all-rank admitted-row count while preserving DistributedDataParallel's
    gradient averaging.

    This follows the action-selection/evaluation split from
    [Double DQN](https://arxiv.org/abs/1509.06461). Lifecycle hooks follow the
    official [LightningModule API](https://lightning.ai/docs/pytorch/stable/common/lightning_module.html).
    """

    def __init__(
        self,
        config: QhLightningModuleConfig,
        *,
        scorer: nn.Module | None = None,
    ) -> None:
        super().__init__()
        self.config = config
        self.online_scorer = scorer if scorer is not None else config.scorer.setup_target()
        self.target_scorer = deepcopy(self.online_scorer)
        self._freeze_target()
        self.register_buffer("optimizer_updates", torch.zeros((), dtype=torch.int64), persistent=True)
        self.register_buffer("validation_loss_sum", torch.zeros((), dtype=torch.float64), persistent=False)
        self.register_buffer("validation_row_count", torch.zeros((), dtype=torch.int64), persistent=False)
        self.save_hyperparameters({"config": config.model_dump_jsonable()})

    def forward(self, actor: Any) -> Float[Tensor, "B N"]:
        """Return online values ``Tensor["B N_q", float32]`` for one actor batch.

        Candidate-axis alignment and padding semantics are defined by
        :class:`aria_nbv.lightning.qh_data.QhActorInputs`.
        """

        return self.online_scorer(actor)

    def train(self, mode: bool = True) -> "QhLightningModule":
        """Propagate parent mode while keeping the target network in eval mode."""

        super().train(mode)
        self.target_scorer.eval()
        return self

    def transfer_batch_to_device(self, batch: QhBatch, device: torch.device, dataloader_idx: int) -> QhBatch:
        """Move tensor DTO fields while retaining CPU-only audit lineage.

        Delegates to :meth:`aria_nbv.lightning.qh_data.QhBatch.to`; rollout and
        source lineage remain ordinary immutable Python objects.
        """

        del dataloader_idx
        return batch.to(device)

    def training_step(self, batch: QhBatch, batch_idx: int) -> Tensor:
        """Compute and log globally count-normalized selected-action Huber loss."""

        del batch_idx
        loss, _targets, admitted = self.compute_fitted_q_loss(batch)
        batch_size = int(batch.transition.row_train_mask.shape[0])
        self.log(
            "train/loss",
            loss,
            on_step=True,
            on_epoch=True,
            prog_bar=True,
            sync_dist=True,
            batch_size=batch_size,
        )
        self.log(
            "train/admitted_rows",
            admitted.sum().float(),
            on_step=True,
            sync_dist=True,
            reduce_fx="sum",
            batch_size=batch_size,
        )
        return loss

    def validation_step(self, batch: QhBatch, batch_idx: int) -> Tensor:
        """Accumulate local exact-eval sums without per-batch collectives."""

        del batch_idx
        losses, _targets, admitted = self._fitted_q_components(batch)
        self.validation_loss_sum.add_(losses.detach().double().sum())
        self.validation_row_count.add_(admitted.sum())
        return losses.sum() / admitted.sum().clamp_min(1)

    def on_validation_epoch_start(self) -> None:
        """Reset rank-local exact-eval accumulators."""

        self.validation_loss_sum.zero_()
        self.validation_row_count.zero_()

    def on_validation_epoch_end(self) -> None:
        """Log the exact loss accumulated by the replicated evaluation loader."""

        if self.validation_row_count.item() > 0:
            self.log(
                "val/loss",
                (self.validation_loss_sum / self.validation_row_count).float(),
                sync_dist=False,
            )

    def compute_fitted_q_loss(
        self,
        batch: QhBatch,
    ) -> tuple[Tensor, Tensor, Tensor]:
        """Compute selected-transition Double-Q supervision.

        Args:
            batch: Padded :class:`QhBatch` with candidate values aligned on
                ``Tensor["B N_q", float32]`` and row admission on
                ``Tensor["B", bool]``.

        Returns:
            Tuple[Tensor, Tensor, Tensor]: Globally count-normalized scalar
            Huber loss ``Tensor["", float32]``, detached TD targets
            ``Tensor["B", float32]``, and admitted-row mask
            ``Tensor["B", bool]``.
        """

        losses, targets, admitted = self._fitted_q_components(batch)
        return self._global_count_mean(losses, admitted), targets, admitted

    def _fitted_q_components(self, batch: QhBatch) -> tuple[Tensor, Tensor, Tensor]:
        """Return unreduced selected losses, detached targets, and admission mask."""

        admitted = batch.transition.row_train_mask.bool()
        self._validate_selected_rows(batch, admitted)
        current_values = self.online_scorer(batch.current_actor)
        targets = batch.transition.reward.float().clone()

        bootstrap = admitted & ~batch.transition.terminal.bool() & batch.next_actor_present.bool()
        if bootstrap.any():
            if batch.next_actor is None:
                raise ValueError("Q_H bootstrap rows require next_actor inputs.")
            next_valid = batch.next_actor.actor_action_mask.bool()
            bootstrap &= next_valid.any(dim=1)
            if bootstrap.any():
                with torch.no_grad():
                    online_next = self.online_scorer(batch.next_actor)
                    selected_next = online_next[bootstrap].masked_fill(~next_valid[bootstrap], -torch.inf).argmax(dim=1)
                    self.target_scorer.eval()
                    target_next = self.target_scorer(batch.next_actor)[bootstrap]
                    bootstrap_values = target_next.gather(1, selected_next.unsqueeze(1)).squeeze(1)
                targets[bootstrap] = (
                    targets[bootstrap] + batch.transition.discount.float()[bootstrap] * bootstrap_values
                )

        selected = batch.transition.selected_candidate_index.long()[admitted]
        predictions = current_values[admitted].gather(1, selected.unsqueeze(1)).squeeze(1)
        losses = functional.huber_loss(
            predictions,
            targets[admitted].detach(),
            delta=self.config.huber_delta,
            reduction="none",
        )
        return losses, targets.detach(), admitted

    def configure_optimizers(self) -> Optimizer:
        """Construct AdamW over online-scorer parameters only."""

        params = [parameter for parameter in self.online_scorer.parameters() if parameter.requires_grad]
        return self.config.optimizer.setup_target(params)

    def optimizer_step(
        self,
        epoch: int,
        batch_idx: int,
        optimizer: Optimizer,
        optimizer_closure: Any | None = None,
    ) -> None:
        """Step the optimizer, then advance the hard-target synchronization clock."""

        del epoch, batch_idx
        optimizer.step(closure=optimizer_closure)
        self.record_optimizer_update()

    def record_optimizer_update(self) -> None:
        """Advance the checkpointed update counter and hard-sync on cadence.

        Called by :meth:`optimizer_step` after each completed optimizer update;
        a sync copies online parameters, freezes the target, and keeps it in
        evaluation mode.
        """

        self.optimizer_updates.add_(1)
        if int(self.optimizer_updates.item()) % self.config.target_sync_interval == 0:
            self.target_scorer.load_state_dict(self.online_scorer.state_dict())
            self._freeze_target()

    def _freeze_target(self) -> None:
        self.target_scorer.requires_grad_(False)
        self.target_scorer.eval()

    def _validate_selected_rows(self, batch: QhBatch, admitted: Tensor) -> None:
        if not admitted.any():
            return
        selected = batch.transition.selected_candidate_index.long()
        width = batch.current_actor.candidate_row_id.shape[1]
        valid_index = selected.ge(0) & selected.lt(width)
        if not valid_index[admitted].all():
            raise ValueError("Trainable selected Q_H row has an out-of-range candidate index.")
        safe = selected.clamp(0, max(width - 1, 0)).unsqueeze(1)
        row_ids = batch.current_actor.candidate_row_id.gather(1, safe).squeeze(1)
        actor_mask = batch.current_actor.actor_action_mask.gather(1, safe).squeeze(1)
        q_mask = batch.supervision.q_train_mask.gather(1, safe).squeeze(1)
        valid = (
            row_ids.eq(batch.transition.selected_candidate_row_id)
            & actor_mask.bool()
            & q_mask.bool()
            & torch.isfinite(batch.transition.reward)
            & torch.isfinite(batch.transition.discount)
        )
        if not valid[admitted].all():
            raise ValueError("Trainable selected Q_H row violates row-id, mask, reward, or discount admission.")

    @staticmethod
    def _global_count_mean(losses: Tensor, admitted: Tensor) -> Tensor:
        local_count = admitted.sum().to(dtype=losses.dtype, device=losses.device)
        global_count = local_count.detach().clone()
        world_size = 1
        if torch.distributed.is_available() and torch.distributed.is_initialized():
            torch.distributed.all_reduce(global_count, op=torch.distributed.ReduceOp.SUM)
            world_size = torch.distributed.get_world_size()
        return losses.sum() * world_size / global_count.clamp_min(1.0)


__all__ = ["QhLightningModule", "QhLightningModuleConfig"]
