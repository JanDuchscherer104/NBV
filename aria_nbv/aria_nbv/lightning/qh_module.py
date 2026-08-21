"""Scorer-independent fitted-Q optimization for finite-candidate chains.

The injected scorer maps :class:`~aria_nbv.data_handling.qh_data.QhActorTensors`
directly to candidate values. This module owns Double-Q targets, exact
distributed admission, one optimizer transaction, metrics, and target sync.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytorch_lightning as pl
import torch
from pydantic import Field, FiniteFloat
from torch import Tensor, nn
from torch.nn import functional
from torch.optim import Optimizer

from ..data_handling.qh_data import QhActorTensors, QhBatch
from ..data_handling.qh_data.views import (
    QhExperimentProfile,
    QhRootEvlProfile,
    QhSelectedObservationProtocol,
    validate_experiment_profile,
)
from ..utils import Stage, TargetConfig
from .optimizers import AdamWConfig, OneCycleSchedulerConfig


class QhLightningModuleConfig(TargetConfig["QhLightningModule"]):
    """Configure fitted-Q optimization without constructing a scorer."""

    optimizer: AdamWConfig = Field(default_factory=AdamWConfig)
    """AdamW settings applied only to the online scorer."""

    lr_scheduler: OneCycleSchedulerConfig | None = Field(default_factory=OneCycleSchedulerConfig)
    """Optional stateful schedule stepped once after each real optimizer update."""

    huber_delta: FiniteFloat = Field(default=1.0, gt=0.0)
    """Positive transition point for selected-action Huber loss."""

    target_sync_interval: int = Field(default=100, ge=1)
    """Hard target-copy cadence measured in completed optimizer updates."""

    root_evl_profile: QhRootEvlProfile = "none"
    """Exact root-EVL carrier the injected scorer accepts."""

    selected_observation_protocol: QhSelectedObservationProtocol = "none"
    """Exact selected-observation source the injected scorer accepts; privileged CF-GT is opt-in."""

    experiment_profile: QhExperimentProfile | None = None
    """Closed named role; ``None`` retains legacy diagnostic-only construction."""

    privileged: bool = False
    """Allow the CF+ upper-bound role; deployable modules must leave this false."""

    actor_state_contract_hash: str | None = None
    """Expected stable hash of the admitted DataModule actor-state contract."""

    geometry_contract_hash: str | None = None
    """Expected selected-depth geometry hash; required only for CF+ admission."""

    @property
    def target_type(self) -> type["QhLightningModule"]:
        """Return the runtime module type used by config-as-factory setup."""

        return QhLightningModule


class QhLightningModule(pl.LightningModule):
    r"""Optimize selected finite-horizon transitions with Double-Q targets.

    The online scorer selects the supported successor action and the frozen target scorer evaluates it:

    $$
    a^*=\arg\max_{a\in\mathcal{A}_{action}\cap\mathcal{A}_{label}}
    Q_{online}(s',a),\qquad
    y=r+\gamma Q_{target}(s',a^*).
    $$

    Manual optimization is restricted to the admitted-row transaction. All
    ranks first all-reduce the selected-row count. A globally empty batch is an
    exact no-op; otherwise every rank scores and steps once, with locally empty
    ranks contributing a zero connected to the online scorer graph.

    Args:
        config: Optimizer, scheduler, Huber, and target-sync policy.
        scorer: Required actor-only module returning
            ``Tensor["B S N", float]`` for the input actor tensors.
    """

    optimizer_updates: Tensor
    """``Tensor["", int64]`` checkpointed count of real optimizer updates."""

    training_loss_sum: Tensor
    """``Tensor["", float64]`` local admitted-loss sum for the current epoch."""

    training_row_count: Tensor
    """``Tensor["", int64]`` local admitted-row count for the current epoch."""

    validation_loss_sum: Tensor
    """``Tensor["", float64]`` single-device validation loss sum."""

    validation_row_count: Tensor
    """``Tensor["", int64]`` single-device validation admitted-row count."""

    test_loss_sum: Tensor
    """``Tensor["", float64]`` single-device test loss sum."""

    test_row_count: Tensor
    """``Tensor["", int64]`` single-device test admitted-row count."""

    def __init__(self, config: QhLightningModuleConfig, *, scorer: nn.Module) -> None:
        super().__init__()
        if config.selected_observation_protocol == "cf_gt" and config.experiment_profile is None:
            raise ValueError("Q_H selected_observation_protocol='cf_gt' requires qh_cfplus_gt_depth_v1.")
        if config.experiment_profile is not None:
            validate_experiment_profile(
                config.experiment_profile,
                root_evl_profile=config.root_evl_profile,
                selected_observation_protocol=config.selected_observation_protocol,
                privileged=config.privileged,
            )
            if config.actor_state_contract_hash is None:
                raise ValueError("Named Q_H modules require an exact actor_state_contract_hash.")
            if config.experiment_profile == "qh_cfplus_gt_depth_v1" and config.geometry_contract_hash is None:
                raise ValueError("CF+ Q_H modules require an exact geometry_contract_hash.")
        self.config = config
        self.automatic_optimization = False
        self.online_scorer = scorer
        self.target_scorer = deepcopy(scorer)
        self._freeze_target()
        self.register_buffer("optimizer_updates", torch.zeros((), dtype=torch.int64), persistent=True)
        self.register_buffer("training_loss_sum", torch.zeros((), dtype=torch.float64), persistent=False)
        self.register_buffer("training_row_count", torch.zeros((), dtype=torch.int64), persistent=False)
        self.register_buffer("validation_loss_sum", torch.zeros((), dtype=torch.float64), persistent=False)
        self.register_buffer("validation_row_count", torch.zeros((), dtype=torch.int64), persistent=False)
        self.register_buffer("test_loss_sum", torch.zeros((), dtype=torch.float64), persistent=False)
        self.register_buffer("test_row_count", torch.zeros((), dtype=torch.int64), persistent=False)
        self.save_hyperparameters({"config": config.model_dump_jsonable()})

    def forward(self, actor: QhActorTensors) -> Tensor:
        """Return online candidate values with the actor's exact batch shape.

        Args:
            actor: Actor-visible chain tensors whose `action_mask` defines the
                required ``Tensor["B S N", bool]`` output shape.

        Returns:
            ``Tensor["B S N", float]`` candidate values.
        """

        self._validate_actor_profile(actor)
        return self._score(self.online_scorer, actor)

    def _validate_actor_profile(self, actor: QhActorTensors) -> None:
        """Fail closed when scorer configuration and materialized actor carriers differ."""

        has_evl = actor.static_context is not None
        expects_evl = self.config.root_evl_profile == "evl_v1"
        if has_evl != expects_evl:
            raise ValueError(
                f"Q_H scorer root_evl_profile={self.config.root_evl_profile!r} does not match actor EVL presence."
            )
        has_selected_observation = actor.selected_observation_prefix is not None
        expects_selected_observation = self.config.selected_observation_protocol == "cf_gt"
        if has_selected_observation != expects_selected_observation:
            raise ValueError(
                "Q_H scorer selected_observation_protocol="
                f"{self.config.selected_observation_protocol!r} does not match actor selected-observation presence."
            )

        if self.config.experiment_profile is not None:
            if actor.static_context is None:
                raise ValueError("Named Q_H experiment profiles require compact root EVL actor context.")
            expected_selected = self.config.experiment_profile == "qh_cfplus_gt_depth_v1"
            if (actor.selected_observation_prefix is not None) != expected_selected:
                raise ValueError(f"Q_H actor does not match experiment profile {self.config.experiment_profile!r}.")

    def train(self, mode: bool = True) -> "QhLightningModule":
        """Propagate mode to the online scorer while keeping the target in eval."""

        super().train(mode)
        self.target_scorer.eval()
        return self

    def on_fit_start(self) -> None:
        """Reject lifecycle settings incompatible with the exact transaction."""

        if self.trainer.accumulate_grad_batches != 1:
            raise ValueError("Q_H manual optimization requires accumulate_grad_batches=1.")
        for scheduler in self.trainer.lr_scheduler_configs:
            if scheduler.interval != "step" or scheduler.reduce_on_plateau:
                raise ValueError("Q_H supports only non-plateau per-step learning-rate schedulers.")
        self._validate_datamodule_contract(self.trainer.datamodule)

    def _validate_datamodule_contract(self, data_module: object) -> None:
        """Reject DataModule profile/hash drift before the first training batch."""

        if self.config.experiment_profile is not None and getattr(data_module, "experiment_profile", None) != (
            self.config.experiment_profile
        ):
            raise ValueError("Q_H module and DataModule experiment profiles must match exactly.")
        if (
            self.config.actor_state_contract_hash is not None
            and getattr(data_module, "actor_state_contract_hash", None) != self.config.actor_state_contract_hash
        ):
            raise ValueError("Q_H module and DataModule actor-state contract hashes must match exactly.")
        if self.config.experiment_profile == "qh_cfplus_gt_depth_v1":
            expected = self.config.geometry_contract_hash
            actual = getattr(data_module, "geometry_contract_hash", None)
            if expected is None or actual != expected:
                raise ValueError("Q_H module and DataModule selected-depth geometry hashes must match exactly.")

    def training_step(self, batch: QhBatch, batch_idx: int) -> Tensor | None:
        """Execute one globally admitted optimizer transaction or an exact no-op."""

        del batch_idx
        admitted = self._fitted_q_admission_mask(batch)
        global_count = self._global_admitted_count(admitted)
        if int(global_count.item()) == 0:
            selected_global_count = self._global_admitted_count(batch.selected_train_mask)
            if int(selected_global_count.item()) > 0:
                self._log_unsupported_backup_metrics(Stage.TRAIN, batch=batch)
            return None

        losses, targets, admitted, online_values, target_values = self._fitted_q_components(batch)
        local_loss_sum = losses.sum() if bool(admitted.any()) else self._parameter_connected_zero()
        world_size = torch.distributed.get_world_size() if self._distributed() else 1
        loss = local_loss_sum * world_size / global_count.to(dtype=local_loss_sum.dtype)

        optimizer = self.optimizers()
        if isinstance(optimizer, list):
            raise RuntimeError("Q_H requires exactly one optimizer.")
        optimizer.zero_grad()
        self.manual_backward(loss)
        optimizer.step()
        self._step_learning_rate_schedulers()
        self._record_optimizer_update()

        self.training_loss_sum.add_(local_loss_sum.detach().double())
        self.training_row_count.add_(admitted.sum())
        self.log("train/loss", loss.detach(), on_step=True, prog_bar=True, sync_dist=True)
        self.log("train/admitted_rows", global_count.float(), on_step=True, sync_dist=False)
        self._log_infrastructure_metrics(
            Stage.TRAIN,
            batch=batch,
            admitted=admitted,
            online_values=online_values,
            target_values=target_values,
        )
        return loss.detach()

    def on_train_epoch_start(self) -> None:
        """Reset local training aggregates."""

        self.training_loss_sum.zero_()
        self.training_row_count.zero_()

    def validation_step(self, batch: QhBatch, batch_idx: int) -> Tensor:
        """Accumulate exact single-device validation loss."""

        del batch_idx
        return self._evaluation_step(batch, Stage.VAL)

    def test_step(self, batch: QhBatch, batch_idx: int) -> Tensor:
        """Accumulate exact single-device held-out loss."""

        del batch_idx
        return self._evaluation_step(batch, Stage.TEST)

    def on_validation_epoch_start(self) -> None:
        """Reset validation aggregates."""

        self.validation_loss_sum.zero_()
        self.validation_row_count.zero_()

    def on_validation_epoch_end(self) -> None:
        """Log admitted-row-weighted validation loss."""

        self._log_aggregate(Stage.VAL, self.validation_loss_sum, self.validation_row_count)

    def on_test_epoch_start(self) -> None:
        """Reset held-out aggregates."""

        self.test_loss_sum.zero_()
        self.test_row_count.zero_()

    def on_test_epoch_end(self) -> None:
        """Log admitted-row-weighted held-out loss."""

        self._log_aggregate(Stage.TEST, self.test_loss_sum, self.test_row_count)

    def compute_fitted_q_loss(self, batch: QhBatch) -> tuple[Tensor, Tensor, Tensor]:
        """Return local selected-action Huber loss, targets, and admission mask."""

        losses, targets, admitted, _online, _target = self._fitted_q_components(batch)
        return losses.sum() / admitted.sum().clamp_min(1), targets, admitted

    def configure_optimizers(self) -> Optimizer | dict[str, Any]:
        """Construct AdamW over the online scorer and its optional scheduler."""

        params = [parameter for parameter in self.online_scorer.parameters() if parameter.requires_grad]
        optimizer = self.config.optimizer.setup_target(params)
        if self.config.lr_scheduler is None:
            return optimizer
        return {
            "optimizer": optimizer,
            "lr_scheduler": self.config.lr_scheduler.setup_lightning(
                optimizer,
                trainer=getattr(self, "_trainer", None),
            ),
        }

    def _fitted_q_components(self, batch: QhBatch) -> tuple[Tensor, Tensor, Tensor, Tensor, Tensor]:
        admitted = self._fitted_q_admission_mask(batch)
        online_values = self(batch.actor)
        with torch.no_grad():
            target_values = self._score(self.target_scorer, batch.actor)

        selected = batch.supervision.selected_index.long()
        safe_selected = selected.clamp(0, max(online_values.shape[-1] - 1, 0))
        selected_reward = batch.supervision.candidate_reward.gather(-1, safe_selected.unsqueeze(-1)).squeeze(-1)
        targets = selected_reward.float().clone()
        bootstrap = admitted & ~batch.supervision.terminal & batch.successor_present
        if bool(bootstrap.any()):
            successor_support = batch.successor_backup_mask
            online_next = torch.zeros_like(online_values)
            target_next = torch.zeros_like(target_values)
            online_next[:, :-1] = online_values[:, 1:]
            target_next[:, :-1] = target_values[:, 1:]
            self._require_finite(
                online_next[bootstrap][successor_support[bootstrap]],
                "online successor predictions used for backup selection",
            )
            next_index = online_next[bootstrap].masked_fill(~successor_support[bootstrap], -torch.inf).argmax(dim=-1)
            next_value = target_next[bootstrap].gather(-1, next_index.unsqueeze(-1)).squeeze(-1)
            self._require_finite(next_value, "target successor predictions used for backup evaluation")
            targets[bootstrap] += batch.supervision.discount.float()[bootstrap] * next_value

        predictions = online_values[admitted].gather(-1, safe_selected[admitted].unsqueeze(-1)).squeeze(-1)
        self._require_finite(predictions, "selected online predictions used for fitted-Q loss")
        losses = functional.huber_loss(
            predictions,
            targets[admitted].detach(),
            delta=self.config.huber_delta,
            reduction="none",
        )
        return losses, targets.detach(), admitted, online_values, target_values

    def _evaluation_step(self, batch: QhBatch, stage: Stage) -> Tensor:
        if self._effective_world_size() != 1:
            raise ValueError("Q_H validation and test require single-device execution.")
        losses, _targets, admitted, online_values, target_values = self._fitted_q_components(batch)
        loss_sum = losses.detach().double().sum()
        row_count = admitted.sum()
        if stage is Stage.VAL:
            self.validation_loss_sum.add_(loss_sum)
            self.validation_row_count.add_(row_count)
        else:
            self.test_loss_sum.add_(loss_sum)
            self.test_row_count.add_(row_count)
        if int(row_count.item()) > 0:
            self._log_infrastructure_metrics(
                stage,
                batch=batch,
                admitted=admitted,
                online_values=online_values,
                target_values=target_values,
            )
        elif bool(batch.selected_train_mask.any()):
            self._log_unsupported_backup_metrics(stage, batch=batch)
        return losses.sum() / row_count.clamp_min(1)

    def _log_infrastructure_metrics(
        self,
        stage: Stage,
        *,
        batch: QhBatch,
        admitted: Tensor,
        online_values: Tensor,
        target_values: Tensor,
    ) -> None:
        count = admitted.sum()
        denominator = count.clamp_min(1).float()
        nonterminal_no_successor = admitted & ~batch.supervision.terminal & ~batch.actor_successor_present
        valid = batch.actor.candidate_mask & batch.actor.step_mask.unsqueeze(-1)
        metrics = {
            "bootstrap_fraction": batch.bootstrap_mask.sum().float() / denominator,
            "terminal_fraction": (admitted & batch.supervision.terminal).sum().float() / denominator,
            "no_successor_fraction": nonterminal_no_successor.sum().float() / denominator,
            "nonfinite_valid_values": (
                ((~torch.isfinite(online_values)) & valid).sum() + ((~torch.isfinite(target_values)) & valid).sum()
            ).float(),
        }
        training = stage is Stage.TRAIN
        for name, value in metrics.items():
            self.log(
                f"{stage.value}/{name}",
                value,
                on_step=training,
                on_epoch=not training,
                sync_dist=False,
                batch_size=max(int(count.item()), 1),
                reduce_fx="sum" if name == "nonfinite_valid_values" else "mean",
            )
        self._log_unsupported_backup_metrics(stage, batch=batch)

    def _log_unsupported_backup_metrics(self, stage: Stage, *, batch: QhBatch) -> None:
        selected = batch.selected_train_mask
        unsupported = self._unsupported_backup_mask(batch)
        training = stage is Stage.TRAIN
        counts = torch.stack((unsupported.sum(), selected.sum())).to(dtype=torch.float32)
        if training and self._distributed():
            torch.distributed.all_reduce(counts, op=torch.distributed.ReduceOp.SUM)
        unsupported_count, selected_count = counts.unbind()
        denominator = selected_count.clamp_min(1)
        for name, value, reduce_fx in (
            ("unsupported_backup_rows", unsupported_count, "sum"),
            ("unsupported_backup_fraction", unsupported_count / denominator, "mean"),
        ):
            self.log(
                f"{stage.value}/{name}",
                value,
                on_step=training,
                on_epoch=not training,
                sync_dist=False,
                batch_size=max(int(selected_count.item()), 1),
                reduce_fx=reduce_fx,
            )

    def _log_aggregate(self, stage: Stage, loss_sum: Tensor, row_count: Tensor) -> None:
        if int(row_count.item()) == 0:
            return
        self.log(f"{stage.value}/loss", (loss_sum / row_count).float(), sync_dist=False)
        self.log(f"{stage.value}/admitted_rows", row_count.float(), sync_dist=False)

    def _step_learning_rate_schedulers(self) -> None:
        if not self.trainer.lr_scheduler_configs:
            return
        scheduler = self.lr_schedulers()
        if isinstance(scheduler, list):
            if len(scheduler) != 1:
                raise RuntimeError("Q_H requires at most one learning-rate scheduler.")
            scheduler = scheduler[0]
        scheduler.step()

    def _record_optimizer_update(self) -> None:
        self.optimizer_updates.add_(1)
        if int(self.optimizer_updates.item()) % self.config.target_sync_interval == 0:
            self.target_scorer.load_state_dict(self.online_scorer.state_dict())
            self._freeze_target()

    def _freeze_target(self) -> None:
        self.target_scorer.requires_grad_(False)
        self.target_scorer.eval()

    def _parameter_connected_zero(self) -> Tensor:
        terms = [
            torch.nan_to_num(parameter).sum() * 0
            for parameter in self.online_scorer.parameters()
            if parameter.requires_grad
        ]
        if not terms:
            raise RuntimeError("Q_H scorer must expose at least one trainable parameter.")
        return torch.stack(terms).sum()

    @staticmethod
    def _unsupported_backup_mask(batch: QhBatch) -> Tensor:
        return (
            batch.selected_train_mask
            & ~batch.supervision.terminal
            & batch.actor_successor_present
            & ~batch.successor_present
        )

    @classmethod
    def _fitted_q_admission_mask(cls, batch: QhBatch) -> Tensor:
        return batch.selected_train_mask & ~cls._unsupported_backup_mask(batch)

    @staticmethod
    def _require_finite(values: Tensor, description: str) -> None:
        if not bool(torch.isfinite(values).all()):
            count = int((~torch.isfinite(values)).sum().item())
            raise ValueError(f"Q_H scorer produced {count} non-finite {description}.")

    @staticmethod
    def _score(scorer: nn.Module, actor: QhActorTensors) -> Tensor:
        values = scorer(actor)
        expected = actor.action_mask.shape
        if not isinstance(values, Tensor) or values.shape != expected:
            actual = getattr(values, "shape", type(values).__name__)
            raise ValueError(f"Q_H scorer must return shape {tuple(expected)}, got {actual}.")
        return values

    @staticmethod
    def _global_admitted_count(admitted: Tensor) -> Tensor:
        global_count = admitted.sum().to(dtype=torch.int64, device=admitted.device)
        if QhLightningModule._distributed():
            torch.distributed.all_reduce(global_count, op=torch.distributed.ReduceOp.SUM)
        return global_count

    def _effective_world_size(self) -> int:
        if self._distributed():
            return torch.distributed.get_world_size()
        return int(getattr(getattr(self, "_trainer", None), "world_size", 1))

    @staticmethod
    def _distributed() -> bool:
        return torch.distributed.is_available() and torch.distributed.is_initialized()


__all__ = ["QhLightningModule", "QhLightningModuleConfig"]
