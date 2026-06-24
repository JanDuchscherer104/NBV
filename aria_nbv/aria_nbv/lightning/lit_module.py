"""LightningModule for training VIN (View Introspection Network).

This module implements the same core logic as `aria_nbv/scripts/train_vin.py`,
but with PyTorch Lightning training loops and optional W&B logging via the
trainer factory.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Literal, Self, cast

import matplotlib
import pytorch_lightning as pl
import torch
from matplotlib import pyplot as plt
from pydantic import Field, field_validator, model_validator
from pytorch_lightning.loggers import WandbLogger
from torch import Tensor, nn
from torch.nn import functional as functional

from ..configs import PathConfig
from ..data_handling import (
    VinOracleBatch,
    is_efm_snippet_view_instance,
    is_vin_snippet_view_instance,
)
from ..rri_metrics import (
    Loss,
    Metric,
    RriErrorStats,
    RriOrdinalBinner,
    VinMetricsConfig,
    coral_loss,
    coral_random_loss,
    loss_key,
    metric_key,
    topk_accuracy_from_probs,
)
from ..rri_metrics.coral import coral_logits_to_label, coral_monotonicity_violation_rate
from ..utils import Console, Stage, TargetConfig
from ..utils.grad_norms import (
    GradNormLoggingConfig,
    _collect_grad_norm_targets,
    _grad_norm_from_params,
)
from ..vin.candidate_scorer import CandidateScorer, CandidateScorerConfig
from ..vin.diagnostics import plot_vin_encodings_from_debug
from ..vin.model_v3 import VinModelV3Config
from ..vin.vin_utils import largest_divisor_leq
from .optimizers import AdamWConfig, OneCycleSchedulerConfig, ReduceLrOnPlateauConfig


class VinLightningModuleConfig(TargetConfig["VinLightningModule"]):
    """Configuration for `VinLightningModule`."""

    @property
    def target_type(self) -> type["VinLightningModule"]:
        return VinLightningModule

    vin: CandidateScorerConfig = Field(default_factory=VinModelV3Config)
    """Candidate scorer configuration.

    The field name remains ``vin`` to preserve existing TOML, checkpoint, and
    experiment-config compatibility. New scorer architectures should enter via
    `aria_nbv.vin.candidate_scorer.CandidateScorerConfig` instead of adding
    Lightning-specific branches.
    """

    optimizer: AdamWConfig = Field(default_factory=AdamWConfig)
    """Optimizer configuration."""

    lr_scheduler: OneCycleSchedulerConfig | ReduceLrOnPlateauConfig | None = Field(
        default_factory=ReduceLrOnPlateauConfig,
    )
    """Learning-rate scheduler configuration (set to ``None`` to disable)."""

    num_classes: int = 8
    """Number of ordinal classes (must match `vin.head.num_classes`)."""

    coral_bias_init: Literal["default", "prior_logits"] = "default"
    """Bias initialization strategy for CORAL thresholds."""

    coral_loss_variant: Literal["coral", "balanced_bce", "focal"] = "coral"
    """Loss variant for CORAL thresholds."""

    coral_balance_source: Literal["binner", "batch"] = "binner"
    """Source for threshold priors when balancing CORAL loss."""

    coral_balance_eps: float = Field(default=1e-6, gt=0.0)
    """Epsilon for clamping threshold priors away from 0/1."""

    coral_focal_gamma: float = Field(default=2.0, ge=0.0)
    """Focal gamma for CORAL focal loss."""

    coral_focal_alpha: float | None = Field(default=None, ge=0.0, le=1.0)
    """Optional focal alpha for CORAL focal loss (None → inferred from priors)."""

    binner_fit_snippets: int | None = None
    """Number of oracle-labelled snippets used to fit the ordinal binner. If `` None`` uses all available (offline) or fit until interrupted (online)."""

    binner_max_attempts: int = 64
    """Maximum number of skipped oracle batches while fitting the binner (guards against bad oracle settings)."""

    save_binner: bool = True
    """Persist `rri_binner.json` into the run directory on fit start."""

    binner_path: Path | None = None
    """Optional explicit path to save `rri_binner.json` (defaults to trainer root dir)."""

    aux_regression_loss: Literal["mse", "huber"] | None = "huber"
    """Auxiliary regression loss on expected RRI (set to ``None`` to disable)."""

    aux_regression_weight: float = 10.0
    """Initial weight for the auxiliary regression loss."""

    aux_regression_weight_gamma: float = Field(default=0.99, gt=0.0, le=1.0)
    """Exponential decay factor for the auxiliary regression weight."""

    aux_regression_weight_min: float = Field(default=0.1, ge=0.0)
    """Minimum auxiliary regression weight after decay."""

    aux_regression_weight_interval: Literal["epoch", "step"] = "epoch"
    """Whether to apply aux loss decay per epoch or per global step."""

    log_interval_steps: int | None = Field(default=None)
    """Step interval for logging rank/confusion/histogram metrics (train stage only). If ``None`` only log per-epoch metrics."""

    grad_norms: GradNormLoggingConfig = Field(default_factory=GradNormLoggingConfig)
    """Configuration for gradient-norm logging."""

    coverage_weight_mode: Literal["none", "voxel", "semidense", "min", "mean", "product"] = "none"
    """How to compute coverage-based loss weights from VIN predictions."""

    coverage_weight_floor: float = Field(default=0.2, ge=0.0, le=1.0)
    """Minimum loss weight for low-coverage candidates."""

    coverage_weight_power: float = Field(default=1.0, ge=0.0)
    """Exponent applied to coverage fractions before weighting."""

    coverage_weight_strength_start: float = Field(default=0.5, ge=0.0, le=1.0)
    """Initial blend strength for coverage weighting (0 = uniform, 1 = full weighting)."""

    coverage_weight_strength_end: float = Field(default=0.0, ge=0.0, le=1.0)
    """Final blend strength after annealing."""

    coverage_weight_schedule: Literal["linear", "cosine"] = "linear"
    """Schedule used to anneal coverage weighting strength."""

    coverage_weight_interval: Literal["epoch", "step"] = "epoch"
    """Whether to anneal coverage weighting per epoch or per step."""

    coverage_weight_anneal_epochs: int | None = Field(default=None, ge=1)
    """Epochs over which to anneal coverage weighting (None keeps constant)."""

    coverage_weight_anneal_steps: int | None = Field(default=None, ge=1)
    """Steps over which to anneal coverage weighting (None keeps constant)."""

    coverage_weight_apply_aux: bool = True
    """Whether to apply coverage weights to the auxiliary regression loss."""

    @field_validator("aux_regression_loss", mode="before")
    @classmethod
    def _validate_aux_regression_loss(cls, value: Any) -> Any:
        return None if value is None or value in ("", "none", "None") else value

    @field_validator("log_interval_steps")
    @classmethod
    def _validate_log_interval_steps(cls, value: int | None) -> int | None:
        if value is None or not value:
            return None
        value = int(value)
        if value < 1:
            raise ValueError("log_interval_steps must be >= 1 or None.")
        return value

    @model_validator(mode="after")
    def _validate_num_classes(self) -> Self:
        if self.num_classes != (vin_num_cls := getattr(self.vin, "num_classes", self.num_classes)):
            raise ValueError(
                f"num_classes={self.num_classes} must match vin.num_classes={vin_num_cls}.",
            )
        if self.aux_regression_weight_min > self.aux_regression_weight:
            raise ValueError(
                "aux_regression_weight_min must be <= aux_regression_weight.",
            )

        return self


class VinLightningModule(pl.LightningModule):
    """PyTorch Lightning module for VIN training with CORAL ordinal regression."""

    def __init__(self, config: VinLightningModuleConfig) -> None:
        super().__init__()
        self.config = config
        self.save_hyperparameters(config.model_dump_jsonable())

        self.console = Console.with_prefix(self.__class__.__name__)

        self.vin = config.vin.setup_target()
        self._binner: RriOrdinalBinner | None = None
        metrics_cfg = VinMetricsConfig(num_classes=self.config.num_classes)

        self._metrics = nn.ModuleDict(
            {
                f"{Stage.TRAIN.value}_stage": metrics_cfg.setup_target(),
                f"{Stage.VAL.value}_stage": metrics_cfg.setup_target(),
                f"{Stage.TEST.value}_stage": metrics_cfg.setup_target(),
            },
        )
        self._interval_metrics = metrics_cfg.setup_target()
        self._rri_error_stats = nn.ModuleDict({f"{Stage.VAL.value}_stage": RriErrorStats()})
        self._logged_effective_config = False

    @property
    def candidate_scorer(self) -> CandidateScorer:
        """Return the registered scorer through the structural VIN protocol.

        `self.vin` intentionally remains the owning `torch.nn.Module` attribute
        so historical checkpoints keep their ``vin.*`` state-dict prefix. This
        property is a typed view only; it must not register a duplicate module.
        """

        return cast(CandidateScorer, self.vin)

    # --------------------------------------------------------------------- lifecycle
    def setup(self, stage: str) -> None:
        super().setup(stage)
        self._integrate_console()
        if self._binner is None:
            self._binner = self._load_binner_from_config()
        self._maybe_init_bin_values()
        self._maybe_init_coral_bias()
        self._log_vin_effective_config()

    def _log_vin_effective_config(self) -> None:
        """Log the effective VIN config (post-sanitization) and persist it as JSON."""
        if self._logged_effective_config:
            return

        vin_cfg = self.config.vin
        effective = vin_cfg.model_dump_jsonable()

        field_dim = getattr(vin_cfg, "field_dim", None)
        field_gn_groups = getattr(vin_cfg, "field_gn_groups", None)
        applied: list[str] = []
        if field_dim is not None and field_gn_groups is not None:
            eff_groups = largest_divisor_leq(int(field_dim), int(field_gn_groups))
            effective["field_gn_groups_effective"] = eff_groups
            if int(field_gn_groups) != eff_groups:
                applied.append("field_gn_groups")

        if field_dim is not None:
            effective["global_pool_num_heads_effective"] = largest_divisor_leq(int(field_dim), 4)

        effective["vin_config_class"] = vin_cfg.__class__.__name__
        if applied:
            effective["applied_corrections"] = applied

        run_dir: Path | None = None
        config_path: Path | None = None
        wandb_run = None

        logger = getattr(self, "logger", None)
        if isinstance(logger, WandbLogger):
            try:
                wandb_run = logger.experiment
            except Exception:  # pragma: no cover - optional dep guard
                wandb_run = None
            if wandb_run is not None:
                run_dir = Path(str(getattr(wandb_run, "dir", ""))).expanduser()

        if run_dir is None:
            log_dir = getattr(self.trainer, "log_dir", None)
            if log_dir is not None:
                run_dir = Path(str(log_dir)).expanduser()

        if run_dir is not None:
            run_dir.mkdir(parents=True, exist_ok=True)
            config_path = run_dir / "vin_effective.json"
            config_path.write_text(json.dumps(effective, indent=2, sort_keys=True))

        if wandb_run is not None:
            try:
                wandb_run.config.update({"vin_effective": effective}, allow_val_change=True)
                if config_path is not None and config_path.exists():
                    import wandb  # type: ignore[import-not-found]

                    artifact = wandb.Artifact("vin_effective_config", type="config")
                    artifact.add_file(str(config_path))
                    wandb_run.log_artifact(artifact)
            except Exception:  # pragma: no cover - wandb optional
                pass

        self._logged_effective_config = True

    def on_save_checkpoint(self, checkpoint: dict[str, Any]) -> None:
        if self._binner is not None:
            checkpoint["rri_binner"] = self._binner.to_dict()

    def on_load_checkpoint(self, checkpoint: dict[str, Any]) -> None:
        data = checkpoint.get("rri_binner")
        if data is not None:
            self._binner = RriOrdinalBinner.from_dict(data)

    # ------------------------------------------------------------------ training/val/test
    def training_step(self, batch: VinOracleBatch, batch_idx: int) -> Tensor | None:
        return self._step(batch, batch_idx, stage=Stage.TRAIN)

    def validation_step(self, batch: VinOracleBatch, batch_idx: int) -> Tensor | None:
        return self._step(batch, batch_idx, stage=Stage.VAL)

    def test_step(self, batch: VinOracleBatch, batch_idx: int) -> Tensor | None:
        return self._step(batch, batch_idx, stage=Stage.TEST)

    # ------------------------------------------------------------------ epoch-end metrics
    def on_train_epoch_end(self) -> None:
        self._log_epoch_metrics(Stage.TRAIN)
        self._interval_metrics.reset()

    def on_validation_epoch_end(self) -> None:
        self._log_epoch_metrics(Stage.VAL)
        self._log_rri_error_stats()

    def on_test_epoch_end(self) -> None:
        self._log_epoch_metrics(Stage.TEST)

    def on_after_backward(self) -> None:
        grad_cfg = self.config.grad_norms
        if not grad_cfg.enabled:
            return
        if getattr(self.trainer, "sanity_checking", False):
            return
        if not self.training:
            return

        targets = _collect_grad_norm_targets(self.vin, grad_cfg)
        for name, params in targets:
            value = _grad_norm_from_params(params, grad_cfg.norm_type)
            self.log(
                f"train-gradnorms/grad_norm_{name}",
                value,
                on_step=True,
                on_epoch=False,
                prog_bar=False,
            )

    # ------------------------------------------------------------------ optim
    def configure_optimizers(self) -> dict[str, Any]:
        params = [p for p in self.vin.parameters() if p.requires_grad]
        if not params:
            raise RuntimeError(
                "No trainable parameters found (did you freeze everything?).",
            )
        optimizer = self.config.optimizer.setup_target(params=params)
        scheduler_cfg = self.config.lr_scheduler
        if scheduler_cfg is None:
            return {"optimizer": optimizer}

        lr_scheduler = scheduler_cfg.setup_lightning(
            optimizer,
            trainer=getattr(self, "trainer", None),
        )
        return {
            "optimizer": optimizer,
            "lr_scheduler": lr_scheduler,
        }

    # ------------------------------------------------------------------ internals
    def _step(
        self,
        batch: VinOracleBatch,
        batch_idx: int,
        *,
        stage: Stage,
    ) -> Tensor | None:
        if self._binner is None:
            raise RuntimeError(
                "RRI binner not initialized. Provide `VinLightningModuleConfig.binner_path` (a fitted .json), "
                "or resume from a checkpoint that contains `rri_binner`.",
            )

        efm_snippet_view = batch.efm_snippet_view
        if is_efm_snippet_view_instance(efm_snippet_view) or is_vin_snippet_view_instance(efm_snippet_view):
            efm = efm_snippet_view
        else:
            raise RuntimeError(
                "VIN batch missing semidense snippet view; VinModelV3 requires VinSnippetView or EfmSnippetView.",
            )
        backbone_out = batch.backbone_out
        if backbone_out is None and not is_efm_snippet_view_instance(efm_snippet_view):
            raise RuntimeError(
                "VIN batch missing both efm snippet view and cached backbone outputs.",
            )

        if backbone_out is not None:
            backbone_out = backbone_out.to(self.device)

        p3d_cameras = batch.p3d_cameras.to(self.device)
        if p3d_cameras.device != self.device:
            p3d_cameras = p3d_cameras.to(self.device)

        candidate_poses_world_cam = batch.candidate_poses_world_cam.to(device=self.device)
        reference_pose_world_rig = batch.reference_pose_world_rig.to(device=self.device)

        candidate_scorer = self.candidate_scorer
        pred = candidate_scorer.forward(
            efm,
            candidate_poses_world_cam=candidate_poses_world_cam,
            reference_pose_world_rig=reference_pose_world_rig,
            p3d_cameras=p3d_cameras,
            backbone_out=backbone_out,
        )
        log_enabled = not getattr(self.trainer, "sanity_checking", False)
        candidate_mask = batch.candidate_valid_mask(device=self.device).reshape(-1)
        log_batch_size = max(int(candidate_mask.sum().item()), 1)
        logits = pred.logits
        if logits.ndim == 2:
            logits = logits.unsqueeze(0)
        logits_flat = logits.reshape(-1, logits.shape[-1])
        logits_finite = torch.isfinite(logits_flat).all(dim=-1)

        rri = batch.rri.to(device=logits.device)
        rri_flat = rri.reshape(-1)
        candidate_mask = candidate_mask.to(device=logits.device)
        mask_rri = torch.isfinite(rri_flat)
        valid_targets = candidate_mask & mask_rri
        mask = valid_targets & logits_finite
        if log_enabled and (~logits_finite & valid_targets).any():
            denom = valid_targets.to(dtype=torch.float32).sum().clamp_min(1.0)
            frac = (~logits_finite & valid_targets).to(dtype=torch.float32).sum() / denom
            self.log(
                f"{stage.value}/drop_nonfinite_logits_frac",
                frac,
                on_step=True,
                prog_bar=False,
                batch_size=log_batch_size,
            )

        if not mask.any():
            if log_enabled:
                if valid_targets.any():
                    self.log(
                        f"{stage.value}/skip_nonfinite_logits",
                        1.0,
                        on_step=True,
                        prog_bar=False,
                        batch_size=log_batch_size,
                    )
                else:
                    self.log(
                        f"{stage.value}/skip_no_valid",
                        1.0,
                        on_step=True,
                        prog_bar=False,
                        batch_size=log_batch_size,
                    )
            return None

        valid_count = int(mask.sum().item())
        log_batch_size = max(valid_count, 1)
        rri_valid = rri_flat[mask]

        # Avoid NaNs propagating through label conversion; masked values are ignored downstream.
        rri_for_labels = torch.nan_to_num(
            torch.where(candidate_mask, rri_flat, torch.zeros_like(rri_flat)),
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )
        labels = self._binner.transform(rri_for_labels)
        labels_valid = labels[mask]
        logits_valid = logits_flat[mask]

        loss_per = self._coral_loss_variant(
            logits_valid,
            labels_valid,
            num_classes=int(self._binner.num_classes),
        )
        coverage_weights, _, coverage_strength = self._coverage_weights(pred, mask, stage=stage)
        if coverage_strength is None and self.config.coverage_weight_mode != "none":
            coverage_strength = self._coverage_weight_strength()
        if coverage_weights is not None:
            coral_loss_value = (loss_per * coverage_weights).sum() / coverage_weights.sum().clamp_min(1e-6)
        else:
            coral_loss_value = loss_per.mean()

        probs = pred.prob
        if probs.ndim == 2:
            probs = probs.unsqueeze(0)
        probs = probs.reshape(-1, probs.shape[-1])
        probs_valid = probs[mask]
        pred_rri_proxy = None
        pred_rri_proxy_valid = None
        aux_loss = None
        if self.config.aux_regression_loss is not None or log_enabled:
            pred_rri_proxy = candidate_scorer.head_coral.expected_from_probs(probs)
            pred_rri_proxy_valid = pred_rri_proxy.reshape(-1)[mask]

        combined_loss = coral_loss_value
        aux_weight = None
        if self.config.aux_regression_loss is not None:
            if pred_rri_proxy is None:
                raise RuntimeError("Expected pred_rri_proxy to be computed.")
            if self.config.aux_regression_loss == "mse":
                diff = pred_rri_proxy_valid - rri_valid.to(dtype=pred_rri_proxy.dtype)
                aux_loss_per = diff * diff
            elif self.config.aux_regression_loss == "huber":
                aux_loss_per = functional.smooth_l1_loss(
                    pred_rri_proxy_valid,
                    rri_valid.to(dtype=pred_rri_proxy.dtype),
                    reduction="none",
                )
            else:
                raise ValueError(
                    f"Unknown aux_regression_loss='{self.config.aux_regression_loss}'.",
                )
            if coverage_weights is not None and self.config.coverage_weight_apply_aux:
                aux_loss = (aux_loss_per * coverage_weights).sum() / coverage_weights.sum().clamp_min(1e-6)
            else:
                aux_loss = aux_loss_per.mean()
            aux_weight = self._aux_regression_weight()
            combined_loss = coral_loss_value + aux_weight * aux_loss

        if not log_enabled:
            return combined_loss

        random_coral_loss = coral_random_loss(int(self._binner.num_classes))
        loss_metrics: dict[Loss, Tensor | float] = {
            Loss.LOSS: combined_loss,
            Loss.CORAL: coral_loss_value,
            Loss.CORAL_REL_RANDOM: coral_loss_value / random_coral_loss,
        }
        aux_loss_metrics: dict[Loss, Tensor | float] = {}
        with torch.no_grad():
            aux_loss_metrics[Loss.ORD_BALANCED_BCE] = self._coral_loss_variant(
                logits_valid,
                labels_valid,
                num_classes=int(self._binner.num_classes),
                variant="balanced_bce",
            ).mean()
            aux_loss_metrics[Loss.ORD_FOCAL] = self._coral_loss_variant(
                logits_valid,
                labels_valid,
                num_classes=int(self._binner.num_classes),
                variant="focal",
            ).mean()
        if aux_loss is not None:
            aux_loss_metrics[Loss.AUX_REGRESSION] = aux_loss
        self._log_loss_scalars(
            loss_metrics,
            stage=stage,
            batch_size=log_batch_size,
        )
        if aux_loss_metrics:
            self._log_aux_scalars(
                aux_loss_metrics,
                stage=stage,
                batch_size=log_batch_size,
            )

        nan_tensor = torch.tensor(float("nan"), device=combined_loss.device)
        voxel_valid = self._flatten_and_mask(getattr(pred, "voxel_valid_frac", None), mask)
        semidense_valid_raw = getattr(
            pred,
            "semidense_candidate_vis_frac",
            getattr(pred, "semidense_valid_frac", None),
        )
        semidense_valid = self._flatten_and_mask(semidense_valid_raw, mask)
        candidate_valid = self._flatten_and_mask(getattr(pred, "candidate_valid", None), mask)
        coverage_payload: dict[Metric, Tensor | float] = {
            Metric.VOXEL_VALID_FRAC_MEAN: voxel_valid.mean()
            if voxel_valid is not None and voxel_valid.numel() > 0
            else nan_tensor,
            Metric.VOXEL_VALID_FRAC_STD: voxel_valid.std(unbiased=False)
            if voxel_valid is not None and voxel_valid.numel() > 1
            else nan_tensor,
            Metric.SEMIDENSE_CANDIDATE_VIS_FRAC_MEAN: semidense_valid.mean()
            if semidense_valid is not None and semidense_valid.numel() > 0
            else nan_tensor,
            Metric.SEMIDENSE_CANDIDATE_VIS_FRAC_STD: semidense_valid.std(unbiased=False)
            if semidense_valid is not None and semidense_valid.numel() > 1
            else nan_tensor,
            Metric.SEMIDENSE_VALID_FRAC_MEAN: semidense_valid.mean()
            if semidense_valid is not None and semidense_valid.numel() > 0
            else nan_tensor,
            Metric.SEMIDENSE_VALID_FRAC_STD: semidense_valid.std(unbiased=False)
            if semidense_valid is not None and semidense_valid.numel() > 1
            else nan_tensor,
            Metric.CANDIDATE_VALID_FRAC: candidate_valid.to(dtype=torch.float32).mean()
            if candidate_valid is not None and candidate_valid.numel() > 0
            else nan_tensor,
            Metric.COVERAGE_WEIGHT_MEAN: coverage_weights.mean()
            if coverage_weights is not None and coverage_weights.numel() > 0
            else nan_tensor,
            Metric.COVERAGE_WEIGHT_STRENGTH: float(coverage_strength) if coverage_strength is not None else nan_tensor,
        }
        self._log_aux_scalars(
            {
                Metric.RRI_MEAN: rri_valid.mean(),
                Metric.PRED_RRI_MEAN: pred_rri_proxy_valid.mean()
                if pred_rri_proxy_valid is not None
                else torch.tensor(float("nan"), device=combined_loss.device),
                Metric.TOP3_ACCURACY: topk_accuracy_from_probs(
                    probs_valid,
                    labels_valid,
                    top_k=3,
                ),
                Metric.AUX_REGRESSION_WEIGHT: float(aux_weight)
                if aux_weight is not None
                else torch.tensor(float("nan"), device=combined_loss.device),
                **coverage_payload,
            },
            stage=stage,
            batch_size=log_batch_size,
        )

        pred_class = coral_logits_to_label(logits_valid)
        monotonicity_rate = coral_monotonicity_violation_rate(logits_valid).mean()
        self._log_aux_scalars(
            {Metric.CORAL_MONOTONICITY_VIOLATION_RATE: monotonicity_rate},
            stage=stage,
            batch_size=log_batch_size,
        )
        stage_key = f"{stage.value}_stage"
        self._metrics[stage_key].update(
            pred_scores=pred.expected_normalized.reshape(-1)[mask].to(
                dtype=torch.float32,
            ),
            rri=rri_valid.to(dtype=torch.float32),
            pred_class=pred_class,
            labels=labels_valid,
        )
        if stage is Stage.TRAIN:
            self._interval_metrics.update(
                pred_scores=pred.expected_normalized.reshape(-1)[mask].to(
                    dtype=torch.float32,
                ),
                rri=rri_valid.to(dtype=torch.float32),
                pred_class=pred_class,
                labels=labels_valid,
            )
        if stage is Stage.VAL and pred_rri_proxy_valid is not None:
            self._rri_error_stats[f"{Stage.VAL.value}_stage"].update(
                pred_rri_proxy_valid,
                rri_valid.to(dtype=pred_rri_proxy_valid.dtype),
            )
        self._log_interval_metrics(
            stage,
            batch_idx=batch_idx,
            batch_size=log_batch_size,
        )

        return combined_loss

    def _aux_regression_weight(self) -> float:
        """Compute the decayed auxiliary regression weight."""
        weight = float(self.config.aux_regression_weight)
        gamma = float(self.config.aux_regression_weight_gamma)
        if gamma < 1.0:
            if self.config.aux_regression_weight_interval == "step":
                decay_steps = int(self.global_step)
            else:
                decay_steps = int(self.current_epoch)
            weight *= gamma**decay_steps
        return max(weight, float(self.config.aux_regression_weight_min))

    def _coverage_weight_strength(self) -> float:
        """Compute the current blend strength for coverage weighting."""
        start = float(self.config.coverage_weight_strength_start)
        end = float(self.config.coverage_weight_strength_end)
        if self.config.coverage_weight_interval == "step":
            total = self.config.coverage_weight_anneal_steps
            step = int(self.global_step)
        else:
            total = self.config.coverage_weight_anneal_epochs
            step = int(self.current_epoch)
        if total is None or total <= 0:
            return start
        progress = min(max(step / float(total), 0.0), 1.0)
        if self.config.coverage_weight_schedule == "cosine":
            return float(end + (start - end) * 0.5 * (1.0 + math.cos(math.pi * progress)))
        return float(start + (end - start) * progress)

    def _flatten_and_mask(self, values: Tensor | None, mask: Tensor) -> Tensor | None:
        if values is None:
            return None
        flat = values.reshape(-1)
        if flat.shape[0] != mask.shape[0]:
            raise ValueError(
                f"Expected coverage tensor of length {mask.shape[0]}, got {flat.shape[0]}.",
            )
        masked = flat[mask]
        if masked.numel() == 0:
            return masked
        if not masked.is_floating_point():
            return masked
        return torch.nan_to_num(masked, nan=0.0, posinf=0.0, neginf=0.0)

    def _select_coverage_fraction(self, pred: Any) -> Tensor | None:
        voxel_frac = getattr(pred, "voxel_valid_frac", None)
        sem_frac = getattr(pred, "semidense_candidate_vis_frac", None)
        if sem_frac is None:
            sem_frac = getattr(pred, "semidense_valid_frac", None)
        match self.config.coverage_weight_mode:
            case "none":
                return None
            case "voxel":
                return voxel_frac
            case "semidense":
                return sem_frac
            case "min":
                if voxel_frac is not None and sem_frac is not None:
                    return torch.minimum(voxel_frac, sem_frac)
                return voxel_frac if voxel_frac is not None else sem_frac
            case "mean":
                if voxel_frac is not None and sem_frac is not None:
                    return 0.5 * (voxel_frac + sem_frac)
                return voxel_frac if voxel_frac is not None else sem_frac
            case "product":
                if voxel_frac is not None and sem_frac is not None:
                    return voxel_frac * sem_frac
                return voxel_frac if voxel_frac is not None else sem_frac
        return None

    def _coverage_weights(
        self,
        pred: Any,
        mask: Tensor,
        *,
        stage: Stage,
    ) -> tuple[Tensor | None, Tensor | None, float | None]:
        if stage is not Stage.TRAIN:
            return None, None, None
        if self.config.coverage_weight_mode == "none":
            return None, None, None
        coverage = self._select_coverage_fraction(pred)
        coverage_masked = self._flatten_and_mask(coverage, mask)
        if coverage_masked is None or coverage_masked.numel() == 0:
            return None, coverage_masked, None
        coverage_masked = coverage_masked.clamp(0.0, 1.0)
        floor = float(self.config.coverage_weight_floor)
        power = float(self.config.coverage_weight_power)
        base_weight = floor + (1.0 - floor) * coverage_masked.pow(power)
        strength = self._coverage_weight_strength()
        weights = torch.lerp(torch.ones_like(base_weight), base_weight, strength)
        return weights, coverage_masked, strength

    def _log_epoch_metrics(self, stage: Stage) -> None:
        if getattr(self.trainer, "sanity_checking", False):
            stage_key = f"{stage.value}_stage"
            self._metrics[stage_key].reset()
            return

        stage_key = f"{stage.value}_stage"
        metrics = self._metrics[stage_key].compute()
        if not metrics:
            self._metrics[stage_key].reset()
            return

        spearman = metrics["spearman"]
        if torch.isfinite(spearman):
            self._log_aux_scalars(
                {Metric.SPEARMAN: spearman},
                stage=stage,
                batch_size=1,
            )

        self._log_confusion_matrix(
            metrics["confusion"],
            stage=stage,
            tag=Metric.CONFUSION_MATRIX.value,
        )
        self._log_label_histogram(
            metrics["label_hist"],
            stage=stage,
            tag=Metric.LABEL_HISTOGRAM.value,
        )
        self._metrics[stage_key].reset()

    def _log_interval_metrics(
        self,
        stage: Stage,
        *,
        batch_idx: int,
        batch_size: int,
    ) -> None:
        if stage is not Stage.TRAIN:
            return
        interval = self.config.log_interval_steps
        if interval is None:
            return
        interval = int(interval)
        if interval <= 0 or (batch_idx + 1) % interval != 0:
            return

        if getattr(self.trainer, "sanity_checking", False):
            self._interval_metrics.reset()
            return

        metrics = self._interval_metrics.compute()
        if not metrics:
            self._interval_metrics.reset()
            return

        spearman = metrics["spearman"]
        if torch.isfinite(spearman):
            self._log_aux_scalars(
                {Metric.SPEARMAN_STEP: spearman},
                stage=stage,
                batch_size=batch_size,
            )

        self._log_confusion_matrix(
            metrics["confusion"],
            stage=stage,
            tag=Metric.CONFUSION_MATRIX_STEP.value,
        )
        self._log_label_histogram(
            metrics["label_hist"],
            stage=stage,
            tag=Metric.LABEL_HISTOGRAM_STEP.value,
        )
        self._interval_metrics.reset()

    def _log_rri_error_stats(self) -> None:
        if getattr(self.trainer, "sanity_checking", False):
            self._rri_error_stats[f"{Stage.VAL.value}_stage"].reset()
            return
        stats = self._rri_error_stats[f"{Stage.VAL.value}_stage"].compute()
        if not stats:
            self._rri_error_stats[f"{Stage.VAL.value}_stage"].reset()
            return
        self._log_aux_scalars(
            {
                Metric.PRED_RRI_BIAS2: stats["bias2"],
                Metric.PRED_RRI_VARIANCE: stats["variance"],
            },
            stage=Stage.VAL,
            batch_size=1,
        )
        self._rri_error_stats[f"{Stage.VAL.value}_stage"].reset()

    def _log_confusion_matrix(
        self,
        confusion: Tensor,
        *,
        stage: Stage,
        tag: str,
    ) -> None:
        if matplotlib.get_backend().lower() != "agg":
            matplotlib.use("Agg", force=True)
        confusion_np = confusion.detach().cpu().numpy()
        fig, ax = plt.subplots(figsize=(5.2, 4.6))
        ax.imshow(confusion_np, cmap="magma")
        ax.set_title(f"{stage.value} confusion matrix")
        ax.set_xlabel("Predicted")
        ax.set_ylabel("True")
        fig.colorbar(ax.images[0], ax=ax, fraction=0.046, pad=0.04)
        self._log_figure(f"{stage.value}-figures/{tag}", fig)

    def _log_label_histogram(self, counts: Tensor, *, stage: Stage, tag: str) -> None:
        if matplotlib.get_backend().lower() != "agg":
            matplotlib.use("Agg", force=True)
        fig, ax = plt.subplots(figsize=(5.2, 3.2))
        xs = torch.arange(int(counts.shape[0])).cpu()
        counts_cpu = counts.detach().cpu()
        ax.bar(xs.numpy(), counts_cpu.numpy())
        ax.set_title(f"{stage.value} label histogram")
        ax.set_xlabel("Class")
        ax.set_ylabel("Count")
        self._log_figure(f"{stage.value}-figures/{tag}", fig)

    def _log_figure(self, tag: str, fig: plt.Figure) -> None:
        logger = getattr(self, "logger", None)
        if logger is None:
            plt.close(fig)
            return
        experiment = getattr(logger, "experiment", None)
        if experiment is None:
            plt.close(fig)
            return
        try:
            if isinstance(logger, WandbLogger):
                import wandb

                experiment.log(
                    {
                        tag: wandb.Image(fig),
                        "epoch": int(self.current_epoch),
                    },
                )
                plt.close(fig)
                return
        except Exception:  # pragma: no cover - logger/optional deps guard
            pass
        if hasattr(experiment, "add_figure"):
            experiment.add_figure(tag, fig, global_step=int(self.global_step))
        plt.close(fig)

    def _log_loss_scalars(
        self,
        values: dict[Loss, Tensor | float],
        *,
        stage: Stage,
        batch_size: int,
    ) -> None:
        payloads: dict[tuple[bool, bool, bool], dict[str, Tensor | float]] = {}
        for key, val in values.items():
            spec = key.log_spec(stage)
            if not spec.enabled:
                continue
            payloads.setdefault((spec.on_step, spec.on_epoch, spec.prog_bar), {})[loss_key(stage, key)] = val
        for (on_step, on_epoch, prog_bar), payload in payloads.items():
            self.log_dict(
                payload,
                on_step=on_step,
                on_epoch=on_epoch,
                prog_bar=prog_bar,
                batch_size=batch_size,
            )

    def _log_aux_scalars(
        self,
        values: dict[Metric | Loss, Tensor | float],
        *,
        stage: Stage,
        batch_size: int,
    ) -> None:
        payloads: dict[tuple[bool, bool, bool], dict[str, Tensor | float]] = {}
        for key, val in values.items():
            if isinstance(key, Metric):
                spec = key.log_spec(stage)
                if not spec.enabled:
                    continue
                payloads.setdefault((spec.on_step, spec.on_epoch, spec.prog_bar), {})[
                    metric_key(stage, key, namespace="aux")
                ] = val
                continue
            if isinstance(key, Loss):
                spec = key.log_spec(stage)
                if not spec.enabled:
                    continue
                payloads.setdefault((spec.on_step, spec.on_epoch, spec.prog_bar), {})[
                    loss_key(stage, key, namespace="aux")
                ] = val
                continue
            payloads.setdefault((False, True, False), {})[f"{stage.value}-aux/{str(key)}"] = val
        for (on_step, on_epoch, prog_bar), payload in payloads.items():
            self.log_dict(
                payload,
                on_step=on_step,
                on_epoch=on_epoch,
                prog_bar=prog_bar,
                batch_size=batch_size,
            )

    def _maybe_init_bin_values(self) -> None:
        """Initialize learnable CORAL bin values from the fitted binner."""
        if self._binner is None:
            return
        head_coral = getattr(self.vin, "head_coral", None)
        if head_coral is None or not hasattr(self.vin, "init_bin_values"):
            return

        if self._binner.bin_means is not None:
            target = self._binner.bin_means
        else:
            target = self._binner.class_midpoints()

        device = next(self.vin.parameters()).device
        target = target.to(device=device, dtype=torch.float32)
        self.vin.init_bin_values(target, overwrite=False)

    def _maybe_init_coral_bias(self) -> None:
        """Initialize CORAL biases from fitted class priors (if configured)."""
        if self._binner is None:
            return
        if self.config.coral_bias_init != "prior_logits":
            return
        head_coral = getattr(self.vin, "head_coral", None)
        if head_coral is None or not hasattr(head_coral, "init_bias_from_priors"):
            return

        priors = self._binner.class_priors()
        try:
            head_coral.init_bias_from_priors(priors, overwrite=True)
        except Exception as exc:  # pragma: no cover - init guard
            self.console.warn(f"Failed to init CORAL bias from priors: {exc}")

    def _coral_loss_variant(
        self,
        logits: Tensor,
        labels: Tensor,
        *,
        num_classes: int,
        variant: Literal["coral", "balanced_bce", "focal"] | None = None,
    ) -> Tensor:
        """Compute the configured CORAL loss variant (per-sample)."""
        variant = self.config.coral_loss_variant if variant is None else variant
        if variant == "coral":
            return coral_loss(
                logits,
                labels,
                num_classes=num_classes,
                reduction="none",
            )

        if self._binner is None:
            raise RuntimeError("Binner not initialized; cannot compute CORAL loss.")

        levels = self._binner.labels_to_levels(labels)
        eps = float(self.config.coral_balance_eps)

        if self.config.coral_balance_source == "binner":
            priors = self._binner.threshold_priors().to(
                device=logits.device,
                dtype=logits.dtype,
            )
        else:
            priors = levels.to(dtype=logits.dtype).mean(dim=0)
        priors = priors.clamp(min=eps, max=1.0 - eps)

        if variant == "balanced_bce":
            pos_weight = (1.0 - priors) / priors
            loss = functional.binary_cross_entropy_with_logits(
                logits,
                levels.to(dtype=logits.dtype),
                pos_weight=pos_weight,
                reduction="none",
            )
            return loss.mean(dim=-1)

        if variant == "focal":
            prob = torch.sigmoid(logits)
            levels_f = levels.to(dtype=logits.dtype)
            p_t = prob * levels_f + (1.0 - prob) * (1.0 - levels_f)
            if self.config.coral_focal_alpha is None:
                alpha = (1.0 - priors).clamp(min=eps, max=1.0 - eps)
            else:
                alpha = torch.full_like(priors, float(self.config.coral_focal_alpha))
            alpha_t = alpha * levels_f + (1.0 - alpha) * (1.0 - levels_f)
            loss = (
                -alpha_t
                * (1.0 - p_t).pow(float(self.config.coral_focal_gamma))
                * torch.log(
                    p_t.clamp_min(eps),
                )
            )
            return loss.mean(dim=-1)

        raise ValueError(f"Unknown coral_loss_variant='{variant}'.")

    def _load_binner_from_config(self) -> RriOrdinalBinner:
        if self.config.binner_path is None:
            raise RuntimeError(
                "Missing `VinLightningModuleConfig.binner_path`. Fit a binner first (e.g. via `nbv-fit-binner`) "
                "and point this config field to the resulting `rri_binner.json`, or resume from a checkpoint.",
            )

        resolved = PathConfig().resolve_artifact_path(
            self.config.binner_path,
            expected_suffix=".json",
            create_parent=False,
        )
        if not resolved.exists():
            raise FileNotFoundError(
                f"RRI binner not found at {resolved}. Run `nbv-fit-binner --out-dir <run_dir>` to create it "
                "or set `VinLightningModuleConfig.binner_path` to an existing fitted binner JSON.",
            )
        return RriOrdinalBinner.load(resolved)

    def _integrate_console(self) -> None:
        logger = getattr(self, "logger", None)
        if logger is not None:
            Console.integrate_with_logger(logger, global_step=int(self.global_step))

    def summarize_vin(
        self,
        batch: VinOracleBatch,
        *,
        include_torchsummary: bool = True,
        torchsummary_depth: int = 3,
    ) -> str:
        """Summarize VIN inputs/outputs for a single oracle-labeled batch.

        Args:
            batch: Oracle-labeled VIN batch from `VinDataModule`.
            include_torchsummary: Whether to append torchsummary module summaries.
            torchsummary_depth: Max depth for torchsummary module traversal.

        Returns:
            Multiline string with VIN summary information.
        """
        return self.vin.summarize_vin(
            batch,
            include_torchsummary=include_torchsummary,
            torchsummary_depth=torchsummary_depth,
        )

    def plot_vin_encodings_batch(
        self,
        batch: VinOracleBatch,
        *,
        out_dir: Path,
        lmax: int,
        sh_normalization: str,
        radius_freqs: list[float],
        file_stem_prefix: str,
    ) -> dict[str, Path]:
        """Generate VIN encoding plots for a single oracle-labeled batch.

        Args:
            batch: Oracle-labeled VIN batch from `VinDataModule`.
            out_dir: Output directory for plots.
            lmax: Max SH degree for visualization.
            sh_normalization: Spherical harmonics normalization mode.
            radius_freqs: Fourier frequencies for radius plot.
            file_stem_prefix: Filename prefix for the plots.

        Returns:
            Mapping of plot names to saved paths.
        """
        if isinstance(self.config.vin, VinModelV3Config):
            self.console.warn(
                "VIN v3 does not support SH/legacy encoding plots; returning empty plot set.",
            )
            return {}

        if batch.efm_snippet_view is None:
            raise RuntimeError(
                "VIN encoding plots require efm inputs; cached batches omit raw EFM data.",
            )

        was_training = self.vin.training
        self.vin.eval()
        with torch.no_grad():
            _, debug = self.vin.forward_with_debug(
                batch.efm_snippet_view.efm,
                candidate_poses_world_cam=batch.candidate_poses_world_cam,
                reference_pose_world_rig=batch.reference_pose_world_rig,
                p3d_cameras=batch.p3d_cameras,
                backbone_out=batch.backbone_out,
            )
        if was_training:
            self.vin.train()

        return plot_vin_encodings_from_debug(
            debug,
            out_dir=out_dir,
            lmax=int(lmax),
            sh_normalization=str(sh_normalization),
            radius_freqs=radius_freqs,
            file_stem_prefix=file_stem_prefix,
            pose_encoder_lff=self.vin.pose_encoder_lff,
        )


__all__ = [
    "AdamWConfig",
    "OneCycleSchedulerConfig",
    "ReduceLrOnPlateauConfig",
    "VinLightningModule",
    "VinLightningModuleConfig",
]
