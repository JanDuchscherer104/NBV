#pagebreak()

= Appendix: VIN v3 Streamlining Rationale


#import "../../shared/macros.typ": *

// TODO(paper-cleanup): This appendix contains many hard-coded numeric comparisons between runs
// (Spearman/top3/loss/LR/grad norms). Prefer importing these values from the same artifacts used
// by slides_4.typ (e.g., `/typst/shared/data/vin_v3_01_vs_t41_summary.json`,
// `/typst/shared/data/wandb_*_summary.json`, dynamics exports) to avoid drift.
// TODO(paper-cleanup): Keep notation consistent with macros (`#symb`/`#eqs`; bold(...) for vectors)
// and avoid mixing prose metrics with undefined symbols.

#block[
  #smallcaps[Scope] This appendix documents the streamlining decisions proposed
  for VIN v3 (our baseline candidate scorer) and ties them to the optuna sweep
  evidence. The goal is to justify which modules were removed and why, while
  identifying risks that must remain explicit in the baseline contract.
]

== Evidence from the vin-v2 optuna sweep

#let top_trials = csv("/typst/seminar_paper/data/optuna_v2_top_trials.csv", row-type: dictionary)
#let n_trials = top_trials.len()
#let n_corrected = top_trials.filter(r => r.regime == "corrected").len()
#let n_traj = top_trials.filter(r => r.traj == "T").len()
#let n_frustum = top_trials.filter(r => r.frustum == "T").len()
#let n_vfeat = top_trials.filter(r => r.vfeat == "T").len()
#let n_vgate_off = top_trials.filter(r => r.vgate == "F").len()

The optuna study is non-stationary because early trials required
configuration corrections (point encoder forced off). Still, the top trials
show consistent patterns: among the top #n_trials trials in the sweep
summary, #n_traj enable the trajectory encoder, #n_frustum enable semidense
frustum attention, #n_vfeat include voxel-validity features, and #n_vgate_off
disable the voxel gate. Only #n_corrected of the top #n_trials trials come
from the corrected regime, so point-encoder effects remain inconclusive.

== Deviations observed in the vin-v3-01 run

We compare the first VIN v3 training run (#code-inline[vin-v3-01], W&B id
#code-inline[jzddfu6u]) against the best optuna run (#code-inline[T41],
#code-inline[wsfpssd8]). The comparison highlights a loss of candidate-specific
signal and reduced candidate validity rather than issues in the voxel backbone.
// TODO(paper-cleanup): Pull all compared metrics from a single export/JSON and cite the exact
// run IDs + timestamped exports; avoid “about …” approximations when numbers are shown elsewhere.

- *Ranking signal collapses.* #code-inline[train-aux/spearman] drops from 0.328
  to 0.025 and #code-inline[train-aux/top3_accuracy] drops from 0.285 to 0.201.
  Validation shows the same pattern (0.312 to 0.186 spearman).
- *Candidate validity and semidense visibility fall.* #code-inline[candidate_valid_frac]
  is about 0.78 in v3 vs 1.0 in T41, while #code-inline[semidense_candidate_vis_frac_mean]
  drops from about 0.082 to 0.062 (train) and 0.087 to 0.065 (val). In contrast,
  #code-inline[voxel_valid_frac_mean] remains about 0.70 in both runs.
- *Loss gap widens early.* #code-inline[train/loss] increases from 7.24 to 7.66,
  and #code-inline[val/loss] increases from 7.21 to 7.60.
- *Optimization weights diverge.* v3 uses a stronger coverage weighting
  (#code-inline[coverage_weight_strength]=0.6 vs 0.2) and a larger auxiliary
  regression weight (10 vs 8.1), which can amplify weak candidate signals.

== Architecture deltas tied to the deviations

The following deltas are the most plausible architectural causes for the
observed metric gaps. Each item maps directly to the v3 changes and the metric
drift above.

- *Semidense frustum MHCA is removed.* T41 used candidate-conditioned frustum
  attention plus visibility embeddings. Removing it eliminates view-dependent
  cues that help rank candidates.
- *Trajectory context is disabled by default in v3.* T41 encoded trajectory
  poses and attended them with candidate pose queries. Keeping this path off
  removes temporal context that correlated with higher ranking accuracy.
- *Voxel validity features are not appended in v3.* v3 keeps the voxel gate off
  and uses validity only for diagnostics and candidate masking, whereas T41
  appends voxel-validity features, which can stabilize early learning.
- *Projection-weighting and grid-size differences across runs.* v3 uses a
  configurable projection grid (often #code-inline[12x12] in current configs)
  and reliability weights derived from #code-inline[n_obs] and
  #code-inline[inv_dist_std]. Earlier runs (e.g., T41) used different grid sizes
  and weighting/normalization settings, which can shift visibility fractions
  and candidate validity.

== Learning-rate and grad-norm diagnostics

We compared the logged #code-inline[lr-AdamW] schedule and
#code-inline[train-gradnorms/...] metrics between #code-inline[vin-v3-01] and the
best optuna run (#code-inline[T41]). The results highlight that v3 receives
weaker gradient signals early, which aligns with the flat loss curve and
mode-collapse.
// TODO(paper-cleanup): Ensure LR-schedule statements match the actual scheduler used in each
// run (one-cycle vs ReduceLROnPlateau etc). If different schedulers were used, clarify.

- *One-cycle schedule differs in peak timing and amplitude.*
  T41 peaks at #code-inline[1.83e-4] by step 32 and decays to
  #code-inline[1.3e-8] by step 266, while v3 ramps to only
  #code-inline[6.61e-5] by step 353 and does not decay within the logged
  window. The lower and later peak reduces early learning pressure when the
  model still needs to escape the collapsed solution.
- *Gradient norms are an order of magnitude smaller in v3.*
  Early-epoch means show head and context modules much quieter:
  #code-inline[grad_norm_head_mlp] is about 0.63 in v3 vs 6.86 in T41,
  #code-inline[grad_norm_head_coral] 0.83 vs 5.64,
  #code-inline[grad_norm_global_pooler] 0.06 vs 0.68, and
  #code-inline[grad_norm_field_proj] 0.01 vs 0.22. The pose encoder is also
  smaller (0.02 vs 0.09). This indicates the objective is not driving strong
  updates in the core scorer in v3.
- *Candidate-specific modules carry large gradients in T41.*
  T41 shows additional gradient energy in the trajectory, frustum, and point
  encoder paths (e.g., #code-inline[grad_norm_traj_attn] around 3.08 early and
  #code-inline[grad_norm_point_encoder] around 8.09). These paths are absent in
  v3, leaving fewer routes for candidate-specific signals to influence the
  objective.

Taken together, the slower one-cycle LR and markedly smaller grad norms in v3
imply that the objective landscape is explored more conservatively, while the
model lacks the candidate-specific modules that produced large early gradients
in T41. This combination is consistent with the observed loss plateau and
mode-collapse.

=== Latest run dynamics (v03-best, W&B id #code-inline[rtjvfyyp])

The most recent v3 run (#code-inline[v03-best]) shows a shallow but consistent
loss reduction that plateaus by epoch 25, without evidence for early stopping
being the cause of the stop.

- *Training length.* The run terminates at #code-inline[epoch=25] with no
  early-stopping keys recorded in the W&B config or summary, indicating a
  #code-inline[max_epochs=25] stop rather than an early-stop trigger.
- *Loss trend (epoch).* #code-inline[train/coral_loss_rel_random] decreases from
  a mean 0.742 (early) to 0.673 (mid) and 0.636 (late), while
  #code-inline[val/coral_loss_rel_random] moves from 0.725 to 0.676 and 0.665.
  Late-epoch slopes are very small (train: $-3.5 * 10^-5$ per step, val:
  $-6.1 * 10^-6$), indicating a plateau.
- *One-cycle schedule behavior.* #code-inline[lr-AdamW] decays monotonically
  from $8.0 * 10^-4$ to $4.34 * 10^-4$ without a warmup peak, and the
  step-level loss correlates positively with LR ($rho approx 0.43$).
- *Noise and batch-size signal.* Step-level loss variability in the late
  segment has a coefficient of variation of about 0.11 (min 0.45, max 0.91),
  suggesting moderate stochasticity. This level of noise is consistent with
  a potential gain from a larger batch size or gradient accumulation if the
  objective remains noisy at the current batch.

Overall, the dynamics suggest that the run is not under-optimized (loss moves
downward early), but it does not continue improving meaningfully past about
epoch 20 without a schedule change or higher signal-to-noise in the gradients.

== Scheduled coverage reweighting (curriculum)

We apply a scheduled coverage reweighting only during training to stabilize
optimization when candidate evidence is sparse or noisy. Each candidate $i$
provides a coverage fraction $c_i$ in $[0, 1]$ (e.g., voxel-valid fraction or
semidense visibility), which we map to a base weight

$w_i^("base") = f + (1 - f) c_i^p$

with floor $f$ and exponent $p$ to avoid zeroing low-coverage samples while
preserving stronger gradients for high-evidence candidates. The final weight
blends uniform and coverage weighting,

$w_i(t) = (1 - lambda_t) + lambda_t w_i^("base")$

where $lambda_t$ anneals from $lambda_0$ to $lambda_T$ over a fixed number
of epochs (or steps), using linear or cosine schedules. The weighted loss is

$cal(L) = frac(sum_i w_i(t) ell_i, sum_i w_i(t))$.

*Motivation.* Early in training, low-coverage candidates often have ambiguous
geometry and noisy RRI labels, increasing gradient variance and encouraging
collapse toward dominant ordinal bins. The annealed weighting acts as a
curriculum: it prioritizes high-evidence candidates to establish a stable
ranking signal, then decays toward uniform weighting so the model still learns
from difficult, low-coverage cases. The floor $f$ ensures every candidate keeps
a nonzero gradient contribution. @CurriculumLearning-bengio2009

== VIN-NBV (Frahm 2025) feature set vs VIN v3

The original VIN-NBV design explicitly constructs per-candidate view features
from projected reconstruction evidence, while VIN v3 relies on compact
semidense statistics plus EVL voxel context. The following summary is based on
the VIN-NBV paper design description. [@VIN-NBV-frahm2025]

*VIN-NBV features (paper design).*
- Reconstruct $cal(R)_"base"$ and enrich points with surface normals, visibility
  count, and depth.
- Project the enriched cloud into each candidate view, forming a
  #code-inline[512x512x5] feature grid (normals + visibility + depth), then
  downsample to #code-inline[256x256] and compute per-pixel variance
  $F_v$ alongside the pooled grid $F_p$.
- Compute an emptiness feature $F_"empty"$ by counting empty pixels inside and
  outside the hull of non-empty projections.
- Provide the number of base views $F_"base"$ as a stage cue.
- Encode $F_v \oplus F_p$ with a CNN to a global view feature $V_"view"$, then
  score with an MLP using $V_"view" \oplus F_"empty" \oplus F_"base"$.

*VIN v3 features (current).*
- EVL voxel field channels + pose encoding, pooled by pose-conditioned global
  attention to obtain $bold(g)$.
- Semidense projection statistics per candidate:
  coverage, empty fraction, visibility fraction, depth mean, depth std, plus a
  tiny CNN over the projection grid (occupancy + depth mean/std).
- Candidate validity from voxel coverage + semidense visibility.
- FiLM modulation of $bold(g)$ using projection stats, then an MLP + CORAL head.

*Key differences.*
- VIN-NBV uses a dense 2D projection grid + CNN encoder; v3 uses compact
  per-candidate statistics plus a tiny CNN over a coarse projection grid.
- VIN-NBV explicitly encodes surface normals and per-pixel variance; v3 does
  not model local geometric variance (only global depth mean/std).
- VIN-NBV includes explicit emptiness inside/outside a hull and a stage cue
  $F_"base"$; v3 does not include either signal by default.
- v3 adds EVL voxel context and pose-conditioned pooling, which VIN-NBV does
  not leverage.

*Actionable suggestions for `vin/model_v3.py`.*
- #textbf[Add a stage cue.] Introduce an optional scalar feature
  $F_"base"$ (number of base views or acquisition step) in
  `VinOracleBatch`, thread it through `_forward_impl`, and append it to the
  head input in the same way as semidense stats.
- #textbf[Add an emptiness proxy closer to $F_"empty"$.] Extend
  `_encode_semidense_projection_features` to compute empty-bin counts inside
  and outside a hull (or a convex/filled mask) in the projection grid. Append
  the two scalars to the projection feature vector.
- #textbf[Add a lightweight variance cue.] Compute a per-bin depth variance grid
  during projection, then summarize it (mean/max or a small histogram) and
  append to the projection feature vector. This approximates VIN-NBV's $F_v$
  without a full CNN.
- #textbf[Optional: tiny 2D encoder toggle.] A tiny CNN over the projection grid
  is already implemented in v3; keep it behind a config flag and report when it
  is enabled/disabled in ablations.

== Streamlining adjustments that preserve signal (no PointNeXt)

These are minimal changes that keep v3 streamlined and avoid the PointNeXt path
while restoring candidate-specific cues.

- *Keep semidense projection stats in the head.* v3 already concatenates the
  5-dim projection features; avoid ablations that remove this signal.
- *Prefer validity features over gating.* Disable the voxel gate and append
  $(v, 1 - v)$ where $v$ is voxel-valid fraction to the head input.
- *Match the sweep grid size.* Use #code-inline[semidense_proj_grid_size=12] to
  match the stronger sweep regime, and always report grid size when comparing
  runs.
- *Provide a no-weighting mode for projection weights.* Allow the
  $n_"obs"$ and $sigma_(rho)$ weights to default to 1.0 to match T41 behavior
  and avoid down-weighting sparse candidates.

== Streamlining candidates for VIN v3

The following changes reduce architectural complexity while keeping the
highest-signal cues supported by sweep evidence. Each change is accompanied by
arguments and risks.

- *Remove PointNeXt point encoder (already done in v3).*
  - *For:* reduces external dependencies and training variance; sweep evidence
    is inconclusive because point encoder was off in the corrected regime.
  - *Against:* best W&B run used point encoder, so v3 will underperform that
    configuration by design.

- *Remove semidense frustum MHCA (already done in v3).*
  - *For:* simplifies per-candidate computation and removes an attention block
    that was only weakly supported by sweep evidence.
  - *Against:* frustum attention is enabled in most top trials; removing it
    reduces view-dependent signal strength and may lower ranking quality.

- *Remove trajectory encoder (already done in v3).*
  - *For:* reduces memory and runtime while focusing on immediate view context.
  - *Against:* trajectory features are enabled in most top trials; this removal
    should be treated as a baseline trade-off rather than a proven improvement.

- *Remove voxel-projection FiLM (suggested).*
  - *For:* avoids a second projection path that duplicates semidense cues and
    adds failure modes when camera metadata is inconsistent.
  - *Against:* might carry complementary global context when semidense points
    are sparse; would need a targeted ablation to confirm.

- *Fix or remove the voxel-valid gate (suggested).*
  - *For:* best trials keep the gate off and use the validity feature instead;
    a hard gate can suppress learning when candidates are out of bounds.
  - *Against:* gate helps enforce spatial trust; removing it requires relying
    on coverage-weighted loss or explicit validity features.

== Baseline contract (fail-fast requirements)

To avoid silent degradation, VIN v3 should enforce the following:

- Semidense inputs must exist and include 5-channel points
  $(x, y, z, sigma_(rho), n_"obs")$, where $sigma_(rho)$ is `inv_dist_std`.
- Camera intrinsics/extrinsics must be complete and batched consistently with
  the candidate poses.
- If `apply_cw90_correction` is enabled, the caller must pass pre-corrected
  cameras and tag them accordingly.

These constraints keep the streamlined baseline honest: if a dependency is
missing, the model should fail loudly rather than degrade into a constant
predictor.

In the current VIN offline-store configuration (`.configs/training/vin/offline_only.toml`),
`VinOfflineDataset` returns collapsed semidense points with both `inv_dist_std`
and `n_obs` (5-channel points). The fail-fast contract above matches the active
training configuration.
