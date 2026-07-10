#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": *
#import "@preview/booktabs:0.0.4": *

== Learning Objective and Replay Evidence

The learned value model is interpreted only after the myopic scorer passes ranking, calibration, and oracle-selected rollout checks, and after the replay store passes support, mask, seed, and successor-table checks. These gates make the evaluation contract a scientific guardrail rather than a post-hoc reporting checklist. Seminar-paper diagnostics such as scene-level RRI ranking, CORAL bin behavior, and offline-cache storage are reported as historical substrate evidence unless they are regenerated under the target-task sampler and rollout-store protocol.

The replay evidence gate starts from the Chapter 03 store contract: immutable VIN offline rows supply the one-step source substrate, while standalone rollout rows supply selected-transition evidence, successor history, masks, and derived #symb.rl.qh arrays. The current audit table in @tab:current-rollout-store-audit is therefore a precondition for interpreting learning curves, not a result metric by itself.

The replay pipeline in @fig:qh-rollout-replay-doubleq is the operational boundary for this interpretation: all-candidate labels can train and calibrate the one-step scorer, while #symb.rl.qh evidence comes only from selected-transition rows whose successor state and successor candidate mask are reproducible.

#figure(
  table(
    columns: (0.72fr, 1.02fr, 1.06fr),
    toprule(),
    table.header([*Data product*], [*Purpose*], [*Minimum evidence*]),
    midrule(), [one-step all-candidate labels], [train and calibrate $hat(r)_psi^e$],
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
    midrule(), [Oracle RRI labeler], [Implemented scene-level depth-render, fusion, and point-mesh scoring substrate.],
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

    [A0-A5 ablation ladder is compared by paired oracle-rescored endpoint gain.], bottomrule(),
  ),
  caption: [Substrate-to-thesis evidence matrix used to avoid treating historical seminar results as final target-Q_H claims.],
) <tab:seminar-to-thesis-evidence>

#prune_todo(
  [This seminar-to-thesis evidence matrix is an internal migration checklist. Final Experimental Design should specify the actual evidence and controls directly; historical substrate routing belongs in the development appendix.],
  source: [thesis peer review],
  gate: [final experiment-design pass],
)

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

#figure(
  image(
    "../../figures/qh_learning_evidence_loop.pdf",
    width: 100%,
  ),
  caption: [Selected-transition replay contract for #symb.rl.qh. All valid candidates can receive one-step oracle target labels, but bootstrapped finite-horizon targets require materialized selected actions, successor counterfactual state, regenerated successor candidate tables, masks, terminal flags, and masked Double-Q targets.],
) <fig:qh-rollout-replay-doubleq>
