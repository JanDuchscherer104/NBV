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
    QhActionMaskSemantics,
    QhExperimentProfile,
    QhRootEvlProfile,
    QhSelectedObservationProtocol,
    validate_experiment_profile,
)
from ..utils import Stage, TargetConfig
from ..vin.models.target_finite_horizon import QhScoreOutput
from ..vin.ordinal import coral_loss
from .optimizers import AdamWConfig, OneCycleSchedulerConfig


class QhLightningModuleConfig(TargetConfig["QhLightningModule"]):
    """Configure fitted-Q optimization without constructing a scorer."""

    optimizer: AdamWConfig = Field(default_factory=AdamWConfig)
    """AdamW settings applied only to the online scorer."""

    lr_scheduler: OneCycleSchedulerConfig | None = Field(default_factory=OneCycleSchedulerConfig)
    """Optional stateful schedule stepped once after each real optimizer update."""

    huber_delta: FiniteFloat = Field(default=1.0, gt=0.0)
    """Positive transition point for the direct-regression decoder's Huber loss."""

    feasibility_loss_weight: FiniteFloat = Field(default=0.0, ge=0.0)
    """Auxiliary binary-feasibility loss weight; zero preserves the A1 control."""

    action_mask_semantics: QhActionMaskSemantics = "oracle_action_mask_v1"
    """Named hard-validity teacher used by the auxiliary feasibility loss."""

    target_sync_interval: int = Field(default=100, ge=1)
    """Hard target-copy cadence measured in completed optimizer updates."""

    root_evl_profile: QhRootEvlProfile = "evl_v1"
    """Exact root-EVL carrier the injected scorer accepts."""

    selected_observation_protocol: QhSelectedObservationProtocol = "none"
    """Exact selected-observation source the injected scorer accepts; privileged CF-GT is opt-in."""

    experiment_profile: QhExperimentProfile = "qh_cf0_v1"
    """Closed deployable role; CF+ is explicit and privileged."""

    privileged: bool = False
    """Allow the CF+ upper-bound role; deployable modules must leave this false."""

    actor_state_contract_hash: str = Field(min_length=1)
    """Required stable hash of the admitted DataModule actor-state contract."""

    learning_contract_hash: str = Field(min_length=1)
    """Required stable hash of the complete effective rollout learning contract."""

    geometry_contract_hash: str | None = Field(default=None, min_length=1)
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
        config: Optimizer, scheduler, regression-Huber, feasibility, and
            target-sync policy. A CORAL scorer supplies its ordinal loss
            metadata through :class:`QhScoreOutput`.
        scorer: Required actor-only module returning :class:`QhScoreOutput`.
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
        validate_experiment_profile(
            config.experiment_profile,
            root_evl_profile=config.root_evl_profile,
            selected_observation_protocol=config.selected_observation_protocol,
            privileged=config.privileged,
        )
        if config.experiment_profile == "qh_cfplus_gt_depth_v1" and config.geometry_contract_hash is None:
            raise ValueError("CF+ Q_H modules require an exact geometry_contract_hash.")
        if config.action_mask_semantics == "learned_feasibility_v1":
            raise ValueError(
                "The deployable Q_H core rejects learned_feasibility_v1; "
                "learned-only selection requires a separately versioned calibrated profile."
            )
        self.config = config
        self.automatic_optimization = False
        self.online_scorer = scorer
        self.target_scorer = deepcopy(scorer)
        self._freeze_target()
        self.register_buffer("optimizer_updates", torch.zeros((), dtype=torch.int64), persistent=True)
        self.register_buffer("training_loss_sum", torch.zeros((), dtype=torch.float64), persistent=False)
        self.register_buffer("training_row_count", torch.zeros((), dtype=torch.int64), persistent=False)
        # Persist exact validation aggregates so experiment-level checkpoint
        # selection can implement the closed loss/update tie-break itself.
        self.register_buffer("validation_loss_sum", torch.zeros((), dtype=torch.float64), persistent=True)
        self.register_buffer("validation_row_count", torch.zeros((), dtype=torch.int64), persistent=True)
        self.register_buffer("test_loss_sum", torch.zeros((), dtype=torch.float64), persistent=False)
        self.register_buffer("test_row_count", torch.zeros((), dtype=torch.int64), persistent=False)
        self.save_hyperparameters({"config": config.model_dump_jsonable()})

    def forward(self, actor: QhActorTensors) -> QhScoreOutput:
        """Return raw online predictions with the actor's exact batch shape.

        Args:
            actor: Actor-visible chain tensors whose `action_mask` defines the
                required ``Tensor["B S N", bool]`` output shape.

        Returns:
            Candidate-aligned conditional Q and feasibility logits. Policy
            masks are intentionally not applied to this raw result.
        """

        self._validate_actor_profile(actor)
        return self._score(
            self.online_scorer,
            actor,
            requested_horizon=actor.horizon_remaining,
        )

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

    def on_validation_start(self) -> None:
        """Reject validation when the attached DataModule contract has drifted."""

        self._validate_datamodule_contract(self.trainer.datamodule)

    def on_test_start(self) -> None:
        """Reject testing when the attached DataModule contract has drifted."""

        self._validate_datamodule_contract(self.trainer.datamodule)

    def on_predict_start(self) -> None:
        """Reject any supported prediction lifecycle after DataModule drift."""

        self._validate_datamodule_contract(self.trainer.datamodule)

    def _validate_datamodule_contract(self, data_module: object) -> None:
        """Reject DataModule profile/hash drift before any lifecycle batch."""

        if getattr(data_module, "experiment_profile", None) != self.config.experiment_profile:
            raise ValueError("Q_H module and DataModule experiment profiles must match exactly.")
        if getattr(data_module, "actor_state_contract_hash", None) != self.config.actor_state_contract_hash:
            raise ValueError("Q_H module and DataModule actor-state contract hashes must match exactly.")
        if getattr(data_module, "learning_contract_hash", None) != self.config.learning_contract_hash:
            raise ValueError("Q_H module and DataModule learning contract hashes must match exactly.")
        learning_contract = getattr(data_module, "learning_contract", None)
        data_contract = getattr(learning_contract, "data_contract", None)
        if getattr(data_contract, "action_mask_semantics", None) != self.config.action_mask_semantics:
            raise ValueError("Q_H module and DataModule action-mask semantics must match exactly.")
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
        feasibility_support = self._feasibility_label_mask(batch)
        global_feasibility_count = self._global_admitted_count(feasibility_support)
        if int(global_count.item()) == 0 and int(global_feasibility_count.item()) == 0:
            selected_global_count = self._global_admitted_count(batch.selected_train_mask)
            if int(selected_global_count.item()) > 0:
                self._log_unsupported_backup_metrics(Stage.TRAIN, batch=batch)
            return None

        losses, targets, admitted, online_output, target_output = self._fitted_q_components(batch)
        local_loss_sum = losses.sum() if bool(admitted.any()) else self._parameter_connected_zero()
        world_size = torch.distributed.get_world_size() if self._distributed() else 1
        loss = self._parameter_connected_zero()
        if int(global_count.item()) > 0:
            loss = loss + local_loss_sum * world_size / global_count.to(dtype=local_loss_sum.dtype)
        feasibility_loss_sum = self._feasibility_losses(batch, online_output).sum()
        if int(global_feasibility_count.item()) > 0:
            loss = loss + float(self.config.feasibility_loss_weight) * (
                feasibility_loss_sum * world_size / global_feasibility_count.to(dtype=feasibility_loss_sum.dtype)
            )

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
        if int(global_feasibility_count.item()) > 0:
            self.log(
                "train/feasibility_loss",
                (
                    feasibility_loss_sum * world_size / global_feasibility_count.to(dtype=feasibility_loss_sum.dtype)
                ).detach(),
                on_step=True,
                sync_dist=True,
            )
        self.log("train/admitted_rows", global_count.float(), on_step=True, sync_dist=False)
        self._log_infrastructure_metrics(
            Stage.TRAIN,
            batch=batch,
            admitted=admitted,
            online_values=online_output.conditional_q,
            target_values=target_output.conditional_q,
        )
        self._log_coral_metrics(
            Stage.TRAIN,
            batch=batch,
            output=online_output,
            targets=targets,
            admitted=admitted,
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
        """Return selected-action decoder loss, fitted-Q targets, and support."""

        losses, targets, admitted, _online, _target = self._fitted_q_components(batch)
        return losses.sum() / admitted.sum().clamp_min(1), targets, admitted

    def compute_feasibility_loss(self, batch: QhBatch) -> tuple[Tensor, Tensor]:
        """Return auxiliary BCE over materialized valid and invalid rows."""

        output = self(batch.actor)
        support = self._feasibility_label_mask(batch, enabled_only=False)
        losses = self._feasibility_losses(batch, output, enabled_only=False)
        return losses.sum() / support.sum().clamp_min(1), support

    def compute_exact_q2_targets(self, batch: QhBatch) -> tuple[Tensor, Tensor]:
        """Return dense-successor exact-Q2 targets and their factual support.

        This diagnostic contains no learned successor value: the second-step
        maximum comes directly from persisted one-step candidate rewards.  A
        row is exact only when every hard-valid successor action has a label;
        partial successor support cannot certify the maximum over the factual
        action set.
        """

        selected = batch.supervision.selected_index.long()
        width = batch.actor.candidate_mask.shape[-1]
        safe_selected = selected.clamp(0, max(width - 1, 0))
        selected_reward = batch.supervision.candidate_reward.gather(
            -1,
            safe_selected.unsqueeze(-1),
        ).squeeze(-1)
        successor_action_mask = batch.successor_action_mask
        successor_backup_mask = batch.successor_backup_mask
        complete_successor_support = successor_action_mask.any(dim=-1) & torch.eq(
            successor_backup_mask,
            successor_action_mask,
        ).all(dim=-1)
        support = (
            batch.selected_train_mask
            & batch.actor.horizon_remaining.eq(2)
            & ~batch.supervision.terminal
            & complete_successor_support
        )
        if bool(support.any()):
            self._validate_horizon_recursion(batch, support)
        successor_reward = torch.zeros_like(batch.supervision.candidate_reward)
        successor_reward[:, :-1] = batch.supervision.candidate_reward[:, 1:]
        supported_successor = successor_reward[support][successor_backup_mask[support]]
        self._require_finite(supported_successor, "one-step successor rewards used for exact Q2")
        targets = selected_reward.float().clone()
        if bool(support.any()):
            next_reward = (
                successor_reward[support]
                .masked_fill(
                    ~successor_backup_mask[support],
                    -torch.inf,
                )
                .amax(dim=-1)
            )
            targets[support] += batch.supervision.discount.float()[support] * next_reward
        return targets.detach(), support

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

    def _fitted_q_components(
        self,
        batch: QhBatch,
    ) -> tuple[Tensor, Tensor, Tensor, QhScoreOutput, QhScoreOutput]:
        admitted = self._fitted_q_admission_mask(batch)
        online_output = self(batch.actor)
        with torch.no_grad():
            target_output = self._score(
                self.target_scorer,
                batch.actor,
                requested_horizon=batch.actor.horizon_remaining,
            )
        online_values = online_output.conditional_q
        target_values = target_output.conditional_q

        selected = batch.supervision.selected_index.long()
        safe_selected = selected.clamp(0, max(online_values.shape[-1] - 1, 0))
        selected_reward = batch.supervision.candidate_reward.gather(-1, safe_selected.unsqueeze(-1)).squeeze(-1)
        targets = selected_reward.float().clone()
        bootstrap = (
            admitted & batch.actor.horizon_remaining.gt(1) & ~batch.supervision.terminal & batch.successor_present
        )
        if bool(bootstrap.any()):
            self._validate_horizon_recursion(batch, bootstrap)
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
        losses = self._value_losses(
            online_output,
            predictions=predictions,
            targets=targets[admitted].detach(),
            admitted=admitted,
            selected=safe_selected,
        )
        return losses, targets.detach(), admitted, online_output, target_output

    def _value_losses(
        self,
        output: QhScoreOutput,
        *,
        predictions: Tensor,
        targets: Tensor,
        admitted: Tensor,
        selected: Tensor,
    ) -> Tensor:
        r"""Return per-row loss for the scorer's configured value decoder.

        Regression applies Huber loss directly in fitted-Q units. CORAL maps
        the same continuous targets to fixed ordinal classes using the bin
        edges attached by the decoder, then applies cumulative-threshold BCE.
        Bellman recursion is unchanged: it always bootstraps from decoded
        ``conditional_q`` in continuous Q units. Hard-invalid, unsupported,
        and padded rows are removed by ``admitted`` before either objective.
        """

        auxiliary = output.value_auxiliary
        if auxiliary is None:
            return functional.huber_loss(
                predictions,
                targets,
                delta=self.config.huber_delta,
                reduction="none",
            )

        logits_by_row = auxiliary.logits[admitted]
        num_thresholds = logits_by_row.shape[-1]
        gather_index = selected[admitted].reshape(-1, 1, 1).expand(-1, 1, num_thresholds)
        selected_logits = logits_by_row.gather(1, gather_index).squeeze(1)
        self._require_finite(selected_logits, "selected CORAL logits used for fitted-Q loss")
        labels = torch.bucketize(targets, auxiliary.bin_edges).to(dtype=torch.int64)
        return coral_loss(
            selected_logits,
            labels,
            num_classes=num_thresholds + 1,
            reduction="none",
        )

    def _evaluation_step(self, batch: QhBatch, stage: Stage) -> Tensor:
        if self._effective_world_size() != 1:
            raise ValueError("Q_H validation and test require single-device execution.")
        losses, _targets, admitted, online_output, target_output = self._fitted_q_components(batch)
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
                online_values=online_output.conditional_q,
                target_values=target_output.conditional_q,
            )
            self._log_coral_metrics(
                stage,
                batch=batch,
                output=online_output,
                targets=_targets,
                admitted=admitted,
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

    def _log_coral_metrics(
        self,
        stage: Stage,
        *,
        batch: QhBatch,
        output: QhScoreOutput,
        targets: Tensor,
        admitted: Tensor,
    ) -> None:
        r"""Report CORAL support saturation and threshold-order diagnostics.

        CORAL supplies ordinal order but not continuous metric distance. The
        configured representatives create that extra interpretation and bound
        the decoded scalar. This diagnostic therefore counts fitted-Q targets
        below or above the outer representatives, as well as targets assigned
        to either open-ended outer class. It also reports adjacent cumulative
        probabilities that violate :math:`P(y>k+1)\leq P(y>k)` before the
        inference decoder repairs class marginals.

        Training counts are explicitly all-reduced before fractions are
        formed, avoiding rank-mean bias when admitted-row counts differ.
        Validation and test are already restricted to one device.
        """

        auxiliary = output.value_auxiliary
        if auxiliary is None:
            return
        if stage is not Stage.TRAIN and not bool(admitted.any()):
            return
        fitted_targets = targets[admitted]
        labels = torch.bucketize(fitted_targets, auxiliary.bin_edges)
        logits_by_row = auxiliary.logits[admitted]
        num_thresholds = logits_by_row.shape[-1]
        selected = batch.supervision.selected_index.long().clamp(0, output.conditional_q.shape[-1] - 1)
        gather_index = selected[admitted].reshape(-1, 1, 1).expand(-1, 1, num_thresholds)
        selected_logits = logits_by_row.gather(1, gather_index).squeeze(1)
        probabilities_gt = torch.sigmoid(selected_logits)
        violation_count = (
            (probabilities_gt[..., 1:] > probabilities_gt[..., :-1]).sum()
            if num_thresholds > 1
            else fitted_targets.new_zeros((), dtype=torch.int64)
        )
        pair_count = fitted_targets.numel() * max(num_thresholds - 1, 0)
        counts = torch.stack(
            (
                fitted_targets.lt(auxiliary.bin_values[0]).sum(),
                fitted_targets.gt(auxiliary.bin_values[-1]).sum(),
                (labels.eq(0) | labels.eq(num_thresholds)).sum(),
                violation_count,
                fitted_targets.new_tensor(fitted_targets.numel(), dtype=torch.int64),
                fitted_targets.new_tensor(pair_count, dtype=torch.int64),
            )
        ).to(dtype=torch.float64)
        if stage is Stage.TRAIN and self._distributed():
            torch.distributed.all_reduce(counts, op=torch.distributed.ReduceOp.SUM)
        below, above, outer, violations, row_count, ordered_pair_count = counts.unbind()
        if int(row_count.item()) == 0:
            return
        metrics = {
            "coral_target_below_support_fraction": below / row_count.clamp_min(1),
            "coral_target_above_support_fraction": above / row_count.clamp_min(1),
            "coral_outer_class_fraction": outer / row_count.clamp_min(1),
            "coral_monotonicity_violation_rate": violations / ordered_pair_count.clamp_min(1),
        }
        training = stage is Stage.TRAIN
        for name, value in metrics.items():
            self.log(
                f"{stage.value}/{name}",
                value.float(),
                on_step=training,
                on_epoch=not training,
                sync_dist=False,
                batch_size=max(int(row_count.item()), 1),
            )

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

    def _feasibility_label_mask(self, batch: QhBatch, *, enabled_only: bool = True) -> Tensor:
        """Return hard-validity supervision support without treating padding as invalid."""

        if enabled_only and float(self.config.feasibility_loss_weight) == 0.0:
            return torch.zeros_like(batch.actor.candidate_mask)
        if self.config.action_mask_semantics == "learned_feasibility_v1":  # guarded at construction
            raise ValueError("learned_feasibility_v1 cannot supervise the feasibility head.")
        return batch.actor.candidate_mask & batch.actor.step_mask.unsqueeze(-1)

    def _feasibility_losses(
        self,
        batch: QhBatch,
        output: QhScoreOutput,
        *,
        enabled_only: bool = True,
    ) -> Tensor:
        """Return per-row BCE for the named hard-validity teacher."""

        support = self._feasibility_label_mask(batch, enabled_only=enabled_only)
        logits = output.feasibility_logits[support]
        self._require_finite(logits, "feasibility logits used for binary supervision")
        targets = batch.actor.action_mask[support].to(dtype=logits.dtype)
        return functional.binary_cross_entropy_with_logits(logits, targets, reduction="none")

    @staticmethod
    def _validate_horizon_recursion(batch: QhBatch, bootstrap: Tensor) -> None:
        """Require every admitted backup to query the factual successor at ``h-1``."""

        horizon = batch.actor.horizon_remaining
        successor_horizon = torch.zeros_like(horizon)
        successor_horizon[:, :-1] = horizon[:, 1:]
        if bool((bootstrap & successor_horizon.ne(horizon - 1)).any()):
            raise ValueError("Q_H recursive backup requires the successor requested horizon to equal h-1 exactly.")

    @staticmethod
    def _require_finite(values: Tensor, description: str) -> None:
        if not bool(torch.isfinite(values).all()):
            count = int((~torch.isfinite(values)).sum().item())
            raise ValueError(f"Q_H scorer produced {count} non-finite {description}.")

    @staticmethod
    def _score(
        scorer: nn.Module,
        actor: QhActorTensors,
        *,
        requested_horizon: Tensor,
    ) -> QhScoreOutput:
        output = scorer(actor, requested_horizon=requested_horizon)
        expected = actor.action_mask.shape
        if not isinstance(output, QhScoreOutput):
            raise ValueError(f"Q_H scorer must return QhScoreOutput, got {type(output).__name__}.")
        for name, values in (
            ("conditional_q", output.conditional_q),
            ("feasibility_logits", output.feasibility_logits),
        ):
            if not isinstance(values, Tensor) or values.shape != expected:
                actual = getattr(values, "shape", type(values).__name__)
                raise ValueError(f"Q_H scorer {name} must have shape {tuple(expected)}, got {actual}.")
            if values.dtype is not torch.float32:
                raise ValueError(f"Q_H scorer {name} must use float32 dtype, got {values.dtype}.")
            if values.device != actor.action_mask.device:
                raise ValueError(f"Q_H scorer {name} must remain on the actor device.")
        auxiliary = output.value_auxiliary
        if auxiliary is not None:
            logits = auxiliary.logits
            if not isinstance(logits, Tensor) or logits.shape[:3] != expected or logits.ndim != 4:
                actual = getattr(logits, "shape", type(logits).__name__)
                raise ValueError(f"Q_H scorer CORAL logits must have shape (B,S,N,K-1), got {actual}.")
            if logits.shape[-1] < 1 or logits.dtype is not torch.float32 or logits.device != actor.action_mask.device:
                raise ValueError("Q_H scorer CORAL logits require K-1 >= 1, float32 dtype, and the actor device.")
            edges = auxiliary.bin_edges
            if (
                not isinstance(edges, Tensor)
                or edges.shape != (logits.shape[-1],)
                or edges.dtype is not torch.float32
                or edges.device != actor.action_mask.device
                or not bool(torch.isfinite(edges).all())
                or not bool((edges[1:] > edges[:-1]).all())
            ):
                raise ValueError("Q_H scorer CORAL bin edges must be finite, strictly increasing float32[K-1].")
            values = auxiliary.bin_values
            if (
                not isinstance(values, Tensor)
                or values.shape != (logits.shape[-1] + 1,)
                or values.dtype is not torch.float32
                or values.device != actor.action_mask.device
                or not bool(torch.isfinite(values).all())
                or not bool((values[1:] > values[:-1]).all())
                or not bool(((values[:-1] <= edges) & (edges <= values[1:])).all())
            ):
                raise ValueError(
                    "Q_H scorer CORAL representatives must be finite, strictly increasing float32[K] "
                    "with each edge between adjacent values."
                )
        return output

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
