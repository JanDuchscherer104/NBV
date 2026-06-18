#import "../../shared/macros.typ": *
#import "../draft_markers.typ": *
#import "@preview/booktabs:0.0.4": *

= Evaluation

The thesis objective is a leakage-safe target-aware @next-best-view stack whose selected views reduce target point-mesh error under a fixed acquisition budget. The endpoint metric #symb.entity.endpoint_gain is primary, and the additive return #symb.entity.return_h is the training target for value learning.

== Objectives and Hypotheses

The first aim defines target-specific oracle @relative-reconstruction-improvement while keeping target selection and model input actor-visible. V1 uses observed or predicted target descriptors #symb.entity.target_desc. @ground-truth:short crops, boxes, meshes, and all-candidate renders are restricted to labels, upper bounds, and evaluation. The required evidence is target eligibility, match score, unmatched/ambiguous counts, endpoint #symb.entity.endpoint_gain, separate scene @relative-reconstruction-improvement:short, and acquisition cost.

The second aim trains a VIN-style myopic scorer over the same candidate table that later feeds #symb.rl.qh. The scorer predicts target @relative-reconstruction-improvement:short from actor-visible scene, target, and candidate features. It is the required learned one-step control, evaluated by rank correlation, top-$k$ oracle hit rate, calibration, selected-candidate oracle @relative-reconstruction-improvement:short, target visibility, invalid fraction, and grouped failures.

The third aim first estimates whether bounded oracle lookahead has headroom over one-step oracle greedy:

$
  #eqs.entity.lookahead_headroom
$

Only if this headroom is positive is #symb.rl.qh expected to recover part of it from offline rollout traces:

$
  #eqs.entity.q_recovery
$

Success is measured by oracle-rescored selected actions, not predicted values. If oracle lookahead itself has little headroom, the thesis reports that the current objective and candidate distribution are effectively myopic. If lookahead has headroom but #symb.rl.qh fails to recover it, the analysis reports whether the limiting factor is target observability, candidate support, rollout coverage, reward definition, or model capacity.

#figure(
  table(
    columns: (0.86fr, 1.32fr, 1.48fr),
    toprule(),
    table.header([*Claim*], [*Primary evidence*], [*Decision rule*]),
    midrule(),
    [Target utility],
    [#symb.entity.endpoint_gain, #symb.entity.return_h, scene @relative-reconstruction-improvement:short, cost],
    [#symb.entity.endpoint_gain decides endpoint quality; #symb.entity.return_h trains and ranks rollouts.],
    [Input safety],
    [actor-visible #symb.entity.target_desc, match score, support, leakage checks],
    [@ground-truth:short is label/evaluation only for the V1 result.],
    [Myopic control],
    [target-rank metrics, selected-candidate oracle @relative-reconstruction-improvement:short, calibration],
    [One-step target scoring is the comparator for #symb.rl.qh, not the final policy claim.],
    [Planning headroom],
    [#symb.entity.lookahead_headroom and recovered fraction #symb.entity.q_recovery],
    [#symb.rl.qh is meaningful only relative to measured oracle-lookahead headroom.],
    bottomrule(),
  ),
  caption: [Objective-to-evidence matrix.],
) <tab:thesis-objective-evidence>

== Learning Objective and Replay Evidence

The learned value model is interpreted only after the myopic scorer passes ranking, calibration, and oracle-selected rollout checks, and after the replay store passes support, mask, seed, and successor-table checks. These gates make the evaluation contract a scientific guardrail rather than a post-hoc reporting checklist. Seminar-paper diagnostics such as scene-level RRI ranking, CORAL bin behavior, and offline-cache storage are reported as historical substrate evidence unless they are regenerated under the target-task sampler and rollout-store protocol.

#figure(
  table(
    columns: (0.72fr, 1.02fr, 1.06fr),
    toprule(),
    table.header([*Data product*], [*Purpose*], [*Minimum evidence*]),
    midrule(),
    [one-step all-candidate labels],
    [train and calibrate $hat(r)_psi^e$],
    [rank correlation, top-$k$ oracle hit, calibration],
    [paired greedy/lookahead roots],
    [measure #symb.entity.lookahead_headroom],
    [same root, target, seed, $N_q$, horizon, and validity masks],
    [stochastic support traces],
    [avoid fitting #symb.rl.qh only on greedy states],
    [policy entropy, unique selected chains, target visibility],
    [invalid near-misses],
    [stress hard masks and failure modes],
    [invalid-reason distribution and with/without-mask diagnostics],
    [target and candidate strata],
    [test support across target difficulty and candidate families],
    [class/support/area/occlusion bins, per-strategy @relative-reconstruction-improvement:short histograms, successor-table availability],
    bottomrule(),
  ),
  caption: [Rollout-support coverage. Target, candidate, validity, and successor-table gaps are reported before interpreting value-model differences.],
) <tab:thesis-support-coverage>

The one-step scorer is trained on all valid candidate rows with oracle immediate target-specific @relative-reconstruction-improvement:short labels. The bootstrapped #symb.rl.qh backup is trained only on expanded transition rows for which the selected action, successor counterfactual state, successor candidate table, successor mask, and terminal flag are materialized. If all-candidate successor expansion is unavailable, non-expanded candidates contribute myopic supervision but not bootstrapped finite-horizon targets.

#figure(
  table(
    columns: (0.72fr, 1.03fr, 1.25fr),
    toprule(),
    table.header([*Evidence surface*], [*Seminar evidence role*], [*Current thesis gate*]),
    midrule(),
    [Oracle RRI labeler],
    [Implemented scene-level depth-render, fusion, and point-mesh scoring substrate.],
    [Target-cropped labels, empty-crop invalidity, and identity-match audit pass on current manifests.],
    [Candidate sampling],
    [Legacy free-shell candidate generator and pruning diagnostics.],
    [Target-conditioned mixture reports strategy counts, invalid reasons, headroom strata, and hard-turn diagnostics.],
    [CORAL scorer],
    [One-step ordinal RRI calibration and expected-RRI interface.],
    [Target scorer passes ranking/calibration before residual #symb.rl.qh is interpreted.],
    [Offline stores],
    [Immutable one-step VIN payload proves feasibility of materialized labels.],
    [Selected-transition rollout store reports successor tables, masks, seeds, storage, and replay integrity.],
    [Architecture],
    [VINv3/EVL myopic scorer is the implemented control.],
    [A0-A5 ablation ladder is compared by paired oracle-rescored endpoint gain.],
    bottomrule(),
  ),
  caption: [Substrate-to-thesis evidence matrix used to avoid treating historical seminar results as final target-Q_H claims.],
) <tab:seminar-to-thesis-evidence>

The finite-candidate value model decodes actions only over valid candidate tokens:

$
  #eqs.rl.qh_candidate_token
$

$
  #eqs.rl.qh_masked_argmax
$

The initial backup is fitted masked Double-Q @DoubleDQN-vanHasselt2015. Here $d_t=1$ at horizon termination, budget termination, or when no valid successor action exists:

$
  #eqs.rl.qh_doubleq_index
$

$
  #eqs.rl.qh_doubleq_target
$

The replay dataset $cal(D)$ contains selected-action transition rows with state, action, immediate target reward, successor state, validity masks, and terminal flags:

$
  #eqs.rl.qh_loss
$

== Policy Comparison

All selected actions are oracle-evaluated under the same acquisition and candidate budgets. Equal budget means equal selected-view horizon $H$, candidate count $N_q$, candidate-generation distribution, and validity constraints; path length, runtime, and oracle evaluation count are reported separately. Coverage is reported against the planned full scale bar of 100 @ground-truth:short mesh @aria-synthetic-environments:short scenes and 4,608 snippet windows from the current thesis contract, or against an explicit scene-level held-out subset if scale is blocked @ProjectAria-ASE-2025. Final splits are scene-level; sample-level splitting across snippets from the same scene is not valid for final claims.

#validation_todo(
  [Replace planned scale bars with generated manifest statistics for the current one-step store and rollout store; historical seminar subset counts are not current thesis evidence unless regenerated.],
  source: [docs/typst/seminar_paper/sections/04-dataset.typ; docs/typst/seminar_paper/sections/09a-evaluation.typ; current dataset manifests],
  gate: [final experiment tables],
)

#figure(
  table(
    columns: (0.72fr, 0.58fr, 0.58fr, 0.52fr, 1.3fr),
    toprule(),
    table.header([*Policy*], [*Actor input*], [*@ground-truth:short decision*], [*H*], [*Role*]),
    midrule(),
    [$pi_"rand"$], [yes], [no], [1], [lower reference over valid candidates],
    [$pi_"learned-1"$], [yes], [no], [1], [myopic learned target scorer],
    [$pi_"oracle-1"$], [no], [yes], [1], [one-step oracle upper bound],
    [$pi_"oracle-look"$], [no], [yes], [$H$], [cumulative-@relative-reconstruction-improvement:short headroom estimate],
    [$pi_Q$], [yes], [no], [$H$], [learned recovery over myopic scoring when headroom is positive],
    bottomrule(),
  ),
  caption: [Leakage-aware policy comparison. Report #symb.entity.endpoint_gain, #symb.entity.return_h, scene @relative-reconstruction-improvement:short, cost, invalidity, runtime, and coverage for each row.],
) <tab:thesis-policy-comparison>

Policy comparisons are paired by root snippet, target, candidate seed, candidate budget, and horizon. Report mean, median, bootstrap confidence intervals, and per-scene win rates for #symb.entity.endpoint_gain, #symb.entity.return_h, and invalidity; scene-level failures are reported separately from global averages.

== Failure Interpretation

The failure interpretation is part of the research contract. If geometry or oracle labels fail, the contribution becomes a validation and one-step-scoring study. If target matching is sparse or ambiguous, target-specific @relative-reconstruction-improvement:short is reported only on validated subsets with unmatched counts and acceptance filters. If #symb.entity.lookahead_headroom is near zero, the thesis reports no measurable non-myopic headroom for the evaluated split, target set, horizon, branch factor, and candidate distribution. The next diagnosis is target matching, candidate support, and supervision scale; added model complexity is justified only after those evidence gaps are ruled out. Scaling and online-discrete tests remain interpretable only if they preserve target-specific @relative-reconstruction-improvement:short supervision.

#validation_todo(
  [Replace planned evidence gates with actual result tables, figures, and failure cases after M1-M5 runs are complete.],
  source: [proposal objectives/evaluation; advisor handout],
  gate: [final experiments],
)
