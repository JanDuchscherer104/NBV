#pagebreak()

= Appendix: Additional Diagnostics <sec:appendix-extra>
#import "../../shared/macros.typ": *
#import "../../shared/tables.typ": publication-table

#let breakable-key(key) = {
  key.replace("/", "/\u{200b}").replace("_", "_\u{200b}")
}

#let log-key(key) = code-inline(breakable-key(key))

This appendix collects additional diagnostics and logging definitions referenced
from the main text.


== Current Training Configuration (VIN v3 Ablation)

// <rm>
// Internal run identifier (date-stamped). Replace with a stable baseline spec reference
// (seed + config artifact) and remove run-name prose from the paper.
This table records the configuration used in the #code-inline[R2026-01-27_13-08-02]
VINv3 baseline training run.
// </rm>

// <rm>
// Run-name encoded in the artifact path; prefer a stable name (e.g., `vin_v3_baseline.toml`).
#let train_cfg_src = "/typst/seminar_paper/data/R2026-01-27_13-08-02_train_config.toml"
// </rm>
#let train_cfg = toml(train_cfg_src)
#let module_cfg = train_cfg.module_config
#let vin_cfg = module_cfg.vin
#let offline_cfg = train_cfg.datamodule_config.source.offline

#let bool_state(flag) = if flag { [enabled] } else { [off] }
#let aux_loss = module_cfg.aux_regression_loss
#let aux_loss_cell = if aux_loss == "none" {
  [none]
} else if aux_loss == "huber" {
  [Huber]
} else if aux_loss == "mse" {
  [MSE]
} else {
  [#aux_loss]
}

#let pool_grid = vin_cfg.global_pool_grid_size
#let pool_grid_cell = [#pool_grid#(sym.times)#pool_grid#(sym.times)#pool_grid]
#let sem_proj_enabled = vin_cfg.semidense_proj_grid_size > 0
#let cov_cell = [
  #module_cfg.coverage_weight_mode (
  anneal #module_cfg.coverage_weight_strength_start→#module_cfg.coverage_weight_strength_end
  over #module_cfg.coverage_weight_anneal_epochs epochs
  )
]

#let train_rows = (
  ([Number of classes], [#module_cfg.num_classes]),
  ([Head hidden dim], [#vin_cfg.head_hidden_dim]),
  ([Head layers], [#vin_cfg.head_num_layers]),
  ([Head dropout], [#vin_cfg.head_dropout]),
  ([Field dim], [#vin_cfg.field_dim]),
  ([Global pool grid], pool_grid_cell),
  ([Semidense proj CNN], bool_state(sem_proj_enabled)),
  ([Semidense obs. count], bool_state(offline_cfg.at("semidense_include_obs_count", default: false))),
  ([Trajectory encoder], [off]),
  ([Point encoder (PointNeXt)], [off]),
  ([Voxel valid-frac gate], bool_state(vin_cfg.use_voxel_valid_frac_gate)),
  ([Optimizer], [AdamW]),
  ([Learning rate], [#module_cfg.optimizer.learning_rate]),
  ([Weight decay], [#module_cfg.optimizer.weight_decay]),
  ([Scheduler], [ReduceLROnPlateau]),
  ([LR factor / patience], [#module_cfg.lr_scheduler.factor / #module_cfg.lr_scheduler.patience]),
  ([Gradient clip], [#train_cfg.trainer_config.gradient_clip_val]),
  ([Coverage weighting], cov_cell),
  ([Aux loss], aux_loss_cell),
  ([Aux weight gamma], [#module_cfg.aux_regression_weight_gamma]),
  ([CORAL bias init], [#module_cfg.coral_bias_init.replace("_", " ")]),
)
#let train_cells = train_rows.flatten()

#figure(
  kind: "table",
  supplement: [Table],
  // <rm>
  // Date-stamped run wording; keep the table but remove the run/date reference.
  caption: [Training configuration for the VIN v3 baseline (Jan 2026 run).],
  // </rm>
  publication-table(
    columns: (18em, auto),
    header: ([Parameter], [Value]),
    align: (left, left),
    rows: train_cells,
  ),
) <tab:train-config>

// <rm>
// References run-specific W&B figures (see `09c-wandb.typ`); remove if those figures are
// moved out of the main paper.
Note: auxiliary regression can be disabled; the curves in
@fig:wandb-aux correspond to a run where it was enabled.
// </rm>

== Logged training metrics (VIN Lightning)

We log scalars and diagnostic figures in a few namespaces:

- #code-inline("stage/...") for main loss scalars, where #code-inline("stage") is one of
  #code-inline("train"), #code-inline("val"), or #code-inline("test").
- #code-inline("stage-aux/...") for auxiliary/diagnostic scalars (ranking, validity, and loss variants).
- #code-inline("stage-figures/...") for confusion matrices and label histograms (logged as images).
- #code-inline("train-gradnorms/grad_norm_*") for per-module gradient norms (training only).

When the same scalar is logged both per-step and per-epoch, Lightning emits two
keys with suffixes #code-inline("_step") and #code-inline("_epoch"). Some
diagnostics are explicitly step-only (e.g. #code-inline("train-aux/spearman_step")).

#text(size: 8.5pt)[
  *Logged loss scalars.*

  - Main losses (#code-inline("stage/...")):
    - #log-key("stage/loss"): Combined objective (Eq. @eq:vin-loss-total).
    - #log-key("stage/coral_loss"): Mean ordinal loss (CORAL thresholds; Eq. @eq:coral-loss).
    - #log-key("stage/coral_loss_rel_random"): Relative-to-random baseline (diagnostic; Eq. @eq:coral-rel-random).
  - Auxiliary / diagnostic losses (#code-inline("stage-aux/...")):
    - #log-key("stage-aux/aux_regression_loss"): Optional regression on expected RRI $#symb.vin.rri_hat$
      (Huber: Eq. @eq:vin-aux-huber; MSE: Eq. @eq:vin-aux-mse).
    - #log-key("stage-aux/coral_loss_balanced_bce"): Balanced-BCE threshold loss (diagnostic;
      Eq. @eq:coral-balanced-bce, weights Eq. @eq:coral-balanced-weight).
    - #log-key("stage-aux/coral_loss_focal"): Focal threshold loss (diagnostic; Eq. @eq:coral-focal, defs Eq. @eq:coral-focal-defs).

  *Logged diagnostic scalars + figures.*

  - Ranking + calibration (#code-inline("stage-aux/...")):
    - #log-key("stage-aux/rri_mean"): Mean oracle $#symb.vin.rri$ (Eq. @eq:metric-rri-mean).
    - #log-key("stage-aux/pred_rri_mean"): Mean predicted $#symb.vin.rri_hat$ (Eq. @eq:metric-pred-rri-mean).
    - #log-key("stage-aux/spearman"): Spearman correlation (Eq. @eq:metric-spearman).
    - #log-key("train-aux/spearman_step"): Step-interval Spearman (every #code-inline("log_interval_steps")).
    - #log-key("stage-aux/top3_accuracy"): Top-3 bin accuracy (k=3; Eq. @eq:metric-topk-acc).
    - #log-key("val-aux/pred_rri_bias2"): Validation $"bias"^2$ (diagnostic).
    - #log-key("val-aux/pred_rri_variance"): Validation variance (diagnostic).
  - Validity + coverage (#code-inline("stage-aux/...")):
    - #log-key("stage-aux/candidate_valid_frac"): Candidate validity fraction (Eq. @eq:metric-candidate-valid-frac).
    - #log-key("stage-aux/voxel_valid_frac_mean") / #log-key("stage-aux/voxel_valid_frac_std"): Voxel proxy mean/std
      (mean/std over candidates).
    - #log-key("stage-aux/semidense_candidate_vis_frac_mean") / #log-key("stage-aux/semidense_candidate_vis_frac_std"):
      Semidense visibility mean/std (over candidates).
    - #log-key("train-aux/coverage_weight_strength"): Coverage-weight strength $#symb.vin.cov_strength$ (train only;
      Eq. @eq:coverage-strength-linear / @eq:coverage-strength-cosine).
    - #log-key("train-aux/coverage_weight_mean"): Mean weight $#symb.vin.cov_weight$ (train only; Eq. @eq:metric-cov-weight-mean).
    - #log-key("stage-aux/aux_regression_weight"): Aux-loss weight schedule $#symb.vin.aux_weight$ (Eq. @eq:vin-aux-weight-schedule).
  - CORAL sanity (#code-inline("stage-aux/...")):
    - #log-key("stage-aux/coral_monotonicity_violation_rate"): Monotonicity violation rate (Eq. @eq:coral-violation).
  - Robustness flags (#code-inline("stage/...")):
    - #log-key("stage/drop_nonfinite_logits_frac"): Non-finite logits among finite RRIs (Eq. @eq:metric-drop-nonfinite).
    - #log-key("stage/skip_nonfinite_logits"): Skip indicator when logits are non-finite (Eq. @eq:metric-skip-nonfinite).
    - #log-key("stage/skip_no_valid"): Skip indicator when no finite RRIs exist (Eq. @eq:metric-skip-no-valid).
  - Figures (#code-inline("stage-figures/...")):
    - #log-key("stage-figures/confusion_matrix"): Confusion matrix image (Eq. @eq:metric-confusion).
    - #log-key("stage-figures/label_histogram"): Label histogram image (Eq. @eq:metric-label-hist).
    - #log-key("train-figures/confusion_matrix_step") / #log-key("train-figures/label_histogram_step"): Step-interval variants (train only).
  - Optimization diagnostics:
    - #log-key("train-gradnorms/grad_norm_*"): Gradient norms over selected `vin` submodules (train only; Eq. @eq:metric-grad-norm).
]

=== Definitions (selected)

Losses:

#block[#align(center)[#eqs.vin.loss_total <eq:vin-loss-total>]]
#block[#align(center)[#eqs.coral.loss <eq:coral-loss>]]
#block[#align(center)[#eqs.coral.rel_random <eq:coral-rel-random>]]
#block[#align(center)[#eqs.vin.aux_reg_huber <eq:vin-aux-huber>]]
#block[#align(center)[#eqs.vin.aux_reg_mse <eq:vin-aux-mse>]]
#block[#align(center)[#eqs.coral.balanced_bce <eq:coral-balanced-bce>]]
#block[#align(center)[#eqs.coral.balanced_bce_weight <eq:coral-balanced-weight>]]
#block[#align(center)[#eqs.coral.focal <eq:coral-focal>]]
#block[#align(center)[#eqs.coral.focal_defs <eq:coral-focal-defs>]]

Metrics and schedules:

#block[#align(center)[#eqs.metrics.rri_mean <eq:metric-rri-mean>]]
#block[#align(center)[#eqs.metrics.pred_rri_mean <eq:metric-pred-rri-mean>]]
#block[#align(center)[#eqs.metrics.spearman <eq:metric-spearman>]]
#block[#align(center)[#eqs.metrics.topk_acc <eq:metric-topk-acc>]]
#block[#align(center)[#eqs.metrics.confusion <eq:metric-confusion>]]
#block[#align(center)[#eqs.metrics.label_hist <eq:metric-label-hist>]]
#block[#align(center)[#eqs.metrics.candidate_validity <eq:metric-candidate-validity>]]
#block[#align(center)[#eqs.metrics.candidate_valid_frac <eq:metric-candidate-valid-frac>]]
#block[#align(center)[#eqs.metrics.cov_weight_mean <eq:metric-cov-weight-mean>]]
#block[#align(center)[#eqs.vin.aux_weight <eq:vin-aux-weight-schedule>]]
#block[#align(center)[#eqs.coverage.strength_linear <eq:coverage-strength-linear>]]
#block[#align(center)[#eqs.coverage.strength_cosine <eq:coverage-strength-cosine>]]
#block[#align(center)[#eqs.coral.violation <eq:coral-violation>]]
#block[#align(center)[#eqs.metrics.drop_nonfinite_logits_frac <eq:metric-drop-nonfinite>]]
#block[#align(center)[#eqs.metrics.skip_nonfinite_logits <eq:metric-skip-nonfinite>]]
#block[#align(center)[#eqs.metrics.skip_no_valid <eq:metric-skip-no-valid>]]
#block[#align(center)[#eqs.metrics.grad_norm <eq:metric-grad-norm>]]

Gradient norms (#code-inline("train-gradnorms/grad_norm_*")) are logged in
#code-inline("VinLightningModule.on_after_backward") and computed over
config-selected `vin` submodules. Targets are collected by walking
`vin.named_modules()` and selecting either modules at a fixed
#code-inline("group_depth") or explicit #code-inline("include") glob patterns
(with optional #code-inline("exclude")), capped by #code-inline("max_items");
#code-inline("norm_type") selects #code-inline("L1")/#code-inline("L2")/#code-inline("Linf").


== Training dynamics

We summarize the most salient training-dynamics signals from the logged
#code-inline(raw("train-aux/*")) metrics (see @fig:wandb-coral and
@fig:wandb-aux):

- *Coverage weighting anneals as intended:* the coverage-weight strength decays
  to zero, and the mean per-sample weight rises toward one, indicating the
  curriculum transitions to uniform weighting.
- *Coverage/validity distributions are stable:* voxel-valid and semidense
  visibility means/standard deviations remain roughly constant over training,
  suggesting the schedule, not data drift, drives weight changes.
- *Aux-loss behaves as a stabilizer:* the auxiliary regression loss drops
  smoothly while its weight decays; predicted RRI mean converges near the oracle
  mean, indicating the aux task is quickly satisfied and then faded out.
- *Ranking improves after aux decay:* Spearman correlation and top-3 accuracy
  increase steadily even after coverage weighting diminishes, supporting the
  idea that the curriculum reduces early noise without preventing later ordinal
  learning.

== EVL output summary

#figure(
  placement: none,
  image("/figures/external/arXiv-EFM3D/evl_output_summary.png", width: 60%),
  caption: [EVL output summary used to construct the VIN scene field.],
) <fig:evl-summary>
