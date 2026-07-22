"""Selected-transition fitted Double-Q training for finite-candidate rollouts.

:class:`QhLightningModule` owns Bellman target construction, distributed loss
normalization, optimization, and hard target-network synchronization. It
consumes the canonical data-owned admission from
:attr:`aria_nbv.data_handling.qh.QhTransition.row_train_mask` and delegates
selected-row consistency to :meth:`aria_nbv.data_handling.qh.QhBatch.assert_selected_rows_consistent`;
it does not recreate the data admission predicate. Actor-only feature construction belongs to
:mod:`aria_nbv.vin.models.target_finite_horizon`; transition loading and padding
belong to :mod:`aria_nbv.data_handling.qh`.
"""

from __future__ import annotations

import math
import warnings
from copy import deepcopy

import pytorch_lightning as pl
import torch
from jaxtyping import Float
from pydantic import Field, FiniteFloat
from torch import Tensor, nn
from torch.nn import functional
from torch.optim import Optimizer

from ..data_handling.qh import QhActorInputs, QhBatch
from ..utils import TargetConfig
from ..vin.models.target_finite_horizon import MultiStepCandidateScorerConfig
from .optimizers import AdamWConfig


class QhLightningModuleConfig(TargetConfig["QhLightningModule"]):
    """Configure the finite-horizon scorer, loss, optimizer, and target sync."""

    scorer: MultiStepCandidateScorerConfig = Field(default_factory=MultiStepCandidateScorerConfig)
    """Actor-only finite-candidate value scorer."""

    optimizer: AdamWConfig = Field(default_factory=AdamWConfig)
    """AdamW settings applied only to online-scorer parameters."""

    huber_delta: FiniteFloat = Field(default=1.0, gt=0.0)
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
    :attr:`aria_nbv.data_handling.qh.QhTransition.row_train_mask` contribute
    to the Huber objective. The summed local losses are normalized by the exact
    all-rank admitted-row count while preserving DistributedDataParallel's
    gradient averaging.

    Stage-qualified diagnostics expose absolute TD error, selected prediction
    and target summaries, terminal/bootstrap coverage, invalid-successor
    coverage, actor support, finite-value failures, and target-network age.
    These are optimization diagnostics rather than policy-quality evidence;
    endpoint policy evaluation remains outside this module. Hard-sync age is
    measured in completed optimizer updates and resets to zero after every
    :meth:`record_optimizer_update` that reaches ``target_sync_interval``.

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
        self.automatic_optimization = False
        self.online_scorer = scorer if scorer is not None else config.scorer.setup_target()
        self.target_scorer = deepcopy(self.online_scorer)
        self._freeze_target()
        self.register_buffer("optimizer_updates", torch.zeros((), dtype=torch.int64), persistent=True)
        self.register_buffer("target_syncs", torch.zeros((), dtype=torch.int64), persistent=True)
        self.register_buffer("training_loss_sum", torch.zeros((), dtype=torch.float64), persistent=False)
        self.register_buffer("training_row_count", torch.zeros((), dtype=torch.int64), persistent=False)
        self.register_buffer("validation_loss_sum", torch.zeros((), dtype=torch.float64), persistent=False)
        self.register_buffer("validation_row_count", torch.zeros((), dtype=torch.int64), persistent=False)
        self.register_buffer("test_loss_sum", torch.zeros((), dtype=torch.float64), persistent=False)
        self.register_buffer("test_row_count", torch.zeros((), dtype=torch.int64), persistent=False)
        self.save_hyperparameters({"config": config.model_dump_jsonable()})

    def forward(self, actor: QhActorInputs) -> Float[Tensor, "B N"]:
        """Return online values ``Tensor["B N_q", float32]`` for one actor batch.

        Candidate-axis alignment and padding semantics are defined by
        :class:`aria_nbv.data_handling.qh.QhActorInputs`.
        """

        return self.online_scorer(actor)

    def train(self, mode: bool = True) -> "QhLightningModule":
        """Propagate parent mode while keeping the target network in eval mode."""

        super().train(mode)
        self.target_scorer.eval()
        return self

    def on_fit_start(self) -> None:
        """Validate manual-step policies and warn about unreachable target sync.

        The reachability check treats Lightning's public
        ``trainer.estimated_stepping_batches`` as total configured capacity and
        subtracts the public restored ``trainer.global_step``. A warning is
        emitted only when that finite remaining capacity cannot complete the
        next hard target copy from the checkpointed optimizer-update counter.
        Equality is reachable because synchronization occurs after the update.
        """

        for scheduler in self.trainer.lr_scheduler_configs:
            if scheduler.interval != "step" or scheduler.reduce_on_plateau:
                raise ValueError("Q_H supports only non-plateau per-step learning-rate schedulers.")
        estimated_steps = self.trainer.estimated_stepping_batches
        updates_until_sync = self.config.target_sync_interval - (
            int(self.optimizer_updates.item()) % self.config.target_sync_interval
        )
        if math.isfinite(float(estimated_steps)):
            restored_global_step = max(int(self.trainer.global_step), 0)
            remaining_capacity = max(float(estimated_steps) - restored_global_step, 0.0)
            if updates_until_sync > remaining_capacity:
                warnings.warn(
                    "Q_H "
                    f"target sync requires {updates_until_sync} remaining optimizer updates but Trainer has "
                    f"{remaining_capacity:g} estimated updates remaining "
                    f"(estimated_stepping_batches={estimated_steps}, global_step={restored_global_step}); "
                    "lower the interval or extend training.",
                    UserWarning,
                    stacklevel=2,
                )

    def training_step(self, batch: QhBatch, batch_idx: int) -> Tensor | None:
        """Execute one exact globally normalized manual optimizer transaction.

        Every rank first contributes its canonical
        :attr:`~aria_nbv.data_handling.qh.QhTransition.row_train_mask` count.
        A globally empty batch returns before model execution or any training
        clock advances. Otherwise every rank backpropagates; a locally empty
        rank contributes a graph-connected zero so DDP gradient hooks match.
        """

        del batch_idx
        admitted = batch.transition.row_train_mask.bool()
        global_count = self._global_admitted_count(admitted)
        if int(global_count.item()) == 0:
            return None

        losses, targets, admitted, predictions, bootstrap, no_valid_next = self._fitted_q_components(batch)
        local_loss_sum = losses.sum()
        world_size = torch.distributed.get_world_size() if self._distributed() else 1
        loss = local_loss_sum * world_size / global_count.to(dtype=local_loss_sum.dtype)

        optimizer = self.optimizers()
        optimizer.zero_grad()
        self.manual_backward(loss)
        optimizer.step()
        self._step_learning_rate_schedulers()
        self.record_optimizer_update()

        self.training_loss_sum.add_(local_loss_sum.detach().double())
        self.training_row_count.add_(admitted.sum())
        self.log(
            "train/loss",
            loss.detach(),
            on_step=True,
            on_epoch=False,
            prog_bar=True,
            sync_dist=True,
        )
        self.log(
            "train/admitted_rows",
            global_count.float(),
            on_step=True,
            sync_dist=False,
        )
        self.log("train/optimizer_updates", self.optimizer_updates.float(), on_step=True, sync_dist=False)
        self._log_step_diagnostics(
            "train",
            batch=batch,
            losses=losses,
            predictions=predictions,
            targets=targets[admitted],
            admitted=admitted,
            bootstrap=bootstrap,
            no_valid_next=no_valid_next,
        )
        return loss.detach()

    def on_train_epoch_start(self) -> None:
        """Reset exact training loss and admitted-row accumulators."""

        self.training_loss_sum.zero_()
        self.training_row_count.zero_()

    def on_train_epoch_end(self) -> None:
        """Log exact all-rank training sums over emitted sampler rows."""

        self._log_aggregate("train", self.training_loss_sum, self.training_row_count, distributed=True)

    def validation_step(self, batch: QhBatch, batch_idx: int) -> Tensor:
        """Accumulate local exact-eval sums without per-batch collectives."""

        del batch_idx
        return self._evaluation_step(batch, "validation")

    def test_step(self, batch: QhBatch, batch_idx: int) -> Tensor:
        """Accumulate held-out loss with the validation lifecycle contract."""

        del batch_idx
        return self._evaluation_step(batch, "test")

    def on_validation_epoch_start(self) -> None:
        """Reset rank-local exact-eval accumulators."""

        self.validation_loss_sum.zero_()
        self.validation_row_count.zero_()

    def on_validation_epoch_end(self) -> None:
        """Log the exact loss accumulated by the replicated evaluation loader."""

        self._log_aggregate("val", self.validation_loss_sum, self.validation_row_count, distributed=False)

    def on_test_epoch_start(self) -> None:
        """Reset rank-local exact held-out accumulators."""

        self.test_loss_sum.zero_()
        self.test_row_count.zero_()

    def on_test_epoch_end(self) -> None:
        """Log exact held-out metrics from the replicated evaluation loader."""

        self._log_aggregate("test", self.test_loss_sum, self.test_row_count, distributed=False)

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

        losses, targets, admitted, _predictions, _bootstrap, _no_valid_next = self._fitted_q_components(batch)
        return self._global_count_mean(losses, admitted), targets, admitted

    def _fitted_q_components(
        self,
        batch: QhBatch,
    ) -> tuple[Tensor, Tensor, Tensor, Tensor, Tensor, Tensor]:
        """Return loss inputs and branch masks without duplicating admission."""

        batch.assert_selected_rows_consistent()
        admitted = batch.transition.row_train_mask.bool()
        current_values = self.online_scorer(batch.current_actor)
        targets = batch.transition.reward.float().clone()

        terminal = batch.transition.terminal.bool()
        successor_present = batch.next_actor_present.bool()
        has_valid_next = torch.zeros_like(admitted)
        if batch.next_actor is not None:
            has_valid_next = batch.next_actor.actor_action_mask.bool().any(dim=1)
        bootstrap = admitted & ~terminal & successor_present & has_valid_next
        no_valid_next = admitted & ~terminal & successor_present & ~has_valid_next
        if bootstrap.any():
            if batch.next_actor is None:
                raise ValueError("Q_H bootstrap rows require next_actor inputs.")
            next_valid = batch.next_actor.actor_action_mask.bool()
            with torch.no_grad():
                online_next = self.online_scorer(batch.next_actor)
                selected_next = online_next[bootstrap].masked_fill(~next_valid[bootstrap], -torch.inf).argmax(dim=1)
                self.target_scorer.eval()
                target_next = self.target_scorer(batch.next_actor)[bootstrap]
                bootstrap_values = target_next.gather(1, selected_next.unsqueeze(1)).squeeze(1)
            targets[bootstrap] = targets[bootstrap] + batch.transition.discount.float()[bootstrap] * bootstrap_values

        selected = batch.transition.selected_candidate_index.long()[admitted]
        predictions = current_values[admitted].gather(1, selected.unsqueeze(1)).squeeze(1)
        losses = functional.huber_loss(
            predictions,
            targets[admitted].detach(),
            delta=self.config.huber_delta,
            reduction="none",
        )
        return losses, targets.detach(), admitted, predictions.detach(), bootstrap, no_valid_next

    def configure_optimizers(self) -> Optimizer:
        """Construct AdamW over online-scorer parameters only."""

        params = [parameter for parameter in self.online_scorer.parameters() if parameter.requires_grad]
        return self.config.optimizer.setup_target(params)

    def record_optimizer_update(self) -> None:
        """Advance the checkpointed update counter and hard-sync on cadence.

        Called by :meth:`training_step` after each completed manual optimizer update;
        a sync copies online parameters, freezes the target, and keeps it in
        evaluation mode.
        """

        self.optimizer_updates.add_(1)
        if int(self.optimizer_updates.item()) % self.config.target_sync_interval == 0:
            self.target_scorer.load_state_dict(self.online_scorer.state_dict())
            self._freeze_target()
            self.target_syncs.add_(1)

    def _evaluation_step(self, batch: QhBatch, stage: str) -> Tensor:
        losses, targets, admitted, predictions, bootstrap, no_valid_next = self._fitted_q_components(batch)
        loss_sum = losses.detach().double().sum()
        row_count = admitted.sum()
        if stage == "validation":
            self.validation_loss_sum.add_(loss_sum)
            self.validation_row_count.add_(row_count)
        elif stage == "test":
            self.test_loss_sum.add_(loss_sum)
            self.test_row_count.add_(row_count)
        else:
            raise ValueError(f"Unknown Q_H evaluation stage {stage!r}.")
        self._log_step_diagnostics(
            "val" if stage == "validation" else stage,
            batch=batch,
            losses=losses,
            predictions=predictions,
            targets=targets[admitted],
            admitted=admitted,
            bootstrap=bootstrap,
            no_valid_next=no_valid_next,
        )
        return losses.sum() / row_count.clamp_min(1)

    def _log_step_diagnostics(
        self,
        stage: str,
        *,
        batch: QhBatch,
        losses: Tensor,
        predictions: Tensor,
        targets: Tensor,
        admitted: Tensor,
        bootstrap: Tensor,
        no_valid_next: Tensor,
    ) -> None:
        """Log interpretable selected-transition diagnostics from fitted-Q tensors."""

        count = admitted.sum()
        denominator = count.clamp_min(1).to(dtype=torch.float32)
        terminal = batch.transition.terminal.bool() & admitted
        support_actions = batch.current_actor.actor_action_mask.bool()[admitted].sum()
        zero = losses.new_zeros(())

        def _mean(values: Tensor) -> Tensor:
            return values.mean() if values.numel() else zero

        def _std(values: Tensor) -> Tensor:
            return values.std(unbiased=False) if values.numel() else zero

        def _min(values: Tensor) -> Tensor:
            return values.min() if values.numel() else zero

        def _max(values: Tensor) -> Tensor:
            return values.max() if values.numel() else zero

        metrics = {
            "td_abs_mean": _mean((predictions - targets).abs()),
            "q_prediction_mean": _mean(predictions),
            "q_prediction_std": _std(predictions),
            "q_prediction_min": _min(predictions),
            "q_prediction_max": _max(predictions),
            "q_target_mean": _mean(targets),
            "q_target_std": _std(targets),
            "q_target_min": _min(targets),
            "q_target_max": _max(targets),
            "terminal_fraction": terminal.sum().float() / denominator,
            "bootstrap_fraction": bootstrap.sum().float() / denominator,
            "no_valid_next_fraction": no_valid_next.sum().float() / denominator,
            "support_actions": support_actions.float(),
            "nonfinite_count": ((~torch.isfinite(predictions)).sum() + (~torch.isfinite(targets)).sum()).float(),
            "target_age": (self.optimizer_updates % self.config.target_sync_interval).float(),
            "target_syncs": self.target_syncs.float(),
        }
        is_training = stage == "train"
        for name, value in metrics.items():
            reduce_fx = "sum" if name in {"support_actions", "nonfinite_count"} else "mean"
            self.log(
                f"{stage}/{name}",
                value,
                on_step=is_training,
                on_epoch=not is_training,
                sync_dist=False,
                batch_size=max(int(count.item()), 1),
                reduce_fx=reduce_fx,
            )

    def _log_aggregate(self, stage: str, loss_sum: Tensor, row_count: Tensor, *, distributed: bool) -> None:
        total_loss = loss_sum.detach().clone()
        total_count = row_count.detach().clone()
        if distributed and self._distributed():
            torch.distributed.all_reduce(total_loss, op=torch.distributed.ReduceOp.SUM)
            torch.distributed.all_reduce(total_count, op=torch.distributed.ReduceOp.SUM)
        if int(total_count.item()) == 0:
            return
        self.log(f"{stage}/loss", (total_loss / total_count).float(), sync_dist=False)
        self.log(f"{stage}/admitted_rows", total_count.float(), sync_dist=False)

    def _step_learning_rate_schedulers(self) -> None:
        if not self.trainer.lr_scheduler_configs:
            return
        schedulers = self.lr_schedulers()
        if not isinstance(schedulers, list):
            schedulers = [schedulers]
        for scheduler in schedulers:
            scheduler.step()

    def _freeze_target(self) -> None:
        self.target_scorer.requires_grad_(False)
        self.target_scorer.eval()

    @staticmethod
    def _global_count_mean(losses: Tensor, admitted: Tensor) -> Tensor:
        global_count = QhLightningModule._global_admitted_count(admitted)
        world_size = torch.distributed.get_world_size() if QhLightningModule._distributed() else 1
        return losses.sum() * world_size / global_count.to(dtype=losses.dtype).clamp_min(1)

    @staticmethod
    def _global_admitted_count(admitted: Tensor) -> Tensor:
        global_count = admitted.sum().to(dtype=torch.int64, device=admitted.device)
        if QhLightningModule._distributed():
            torch.distributed.all_reduce(global_count, op=torch.distributed.ReduceOp.SUM)
        return global_count

    @staticmethod
    def _distributed() -> bool:
        return torch.distributed.is_available() and torch.distributed.is_initialized()


__all__ = ["QhLightningModule", "QhLightningModuleConfig"]
