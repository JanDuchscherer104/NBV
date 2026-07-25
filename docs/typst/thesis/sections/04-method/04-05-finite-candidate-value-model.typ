#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status, research_todo, decision_todo

== Target-Conditioned Finite-Horizon Value Model

=== Implemented controls and H=2 tracer

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@VIN-NBV-frahm2025 @CORAL-cao2019 @DoubleDQN-vanHasselt2015],
  source: "aria_nbv/aria_nbv/vin/models/target_myopic.py; aria_nbv/aria_nbv/vin/models/target_finite_horizon.py; aria_nbv/aria_nbv/lightning/qh_module.py; aria_nbv/aria_nbv/data_handling/qh.py",
  gate: [retain the one-step scorer as a matched control and label the H=2 implementation as an `S0-pose` tracer],
)[The one-step VIN/CORAL scorer remains the historical myopic control. A dedicated development path implements a deterministic V0, horizon-two, candidate-to-state scorer and selected-transition Double-Q trainer. Frozen matched-control and policy evidence remain pending.]

The implemented H=2 tracer receives root semidense geometry reduced to global moments, GT-derived target pose and extent, root-relative candidate geometry, candidate-local target relations, selected-pose history, and remaining budget. It does not consume root EVL voxel tokens, selected-depth geometry, or an occupied/free/unknown dynamic memory. It is therefore an `S0-pose` representation baseline and must not be described as the task-sufficient reconstruction-state model.

The target-conditioned tracer emits one continuous value per candidate row. Candidate rows are independent queries over shared scene-summary, target, budget, and history tokens; there is no candidate--candidate attention. The hard action mask remains external to the value head and gates selection and loss. This implementation establishes a runnable architecture and optimization seam, not evidence that non-myopic policy quality improves.

=== Canonical variable-horizon candidate scorer

#thesis_status(
  implementation: "planned",
  evidence: "pending",
  citation: [@FittedQIteration-ernst2005 @FixedHorizonTD-deAsis2020 @UVFA-schaul2015 @DeepSets-zaheer2017 @SetTransformer-lee2019 @zhou2023query],
  source: "docs/typst/thesis/sections/04-method/04-01-scene-representation-requirements.typ; docs/typst/thesis/sections/04-method/04-02-descriptor-and-encoding-plan.typ; aria_nbv/aria_nbv/vin/models/target_finite_horizon.py",
  gate: [explicit horizon-query DTO, dynamic-state reader, A0/A1 controls, horizon tests, and held-out oracle policy comparison],
)[The minimal thesis goal is one target-conditioned candidate scorer that evaluates any supported residual horizon with shared scene, target, and candidate encoders. Candidate--candidate interaction and exact equivariance remain later ablations.]

For target $e$, the return over exactly the requested residual horizon $h$ is

$
  #eqs.rl.finite_horizon_return
$

and the learned quantity is

$
  #eqs.rl.q_h
$

The notation $Q_H$ names the family supported up to a configured maximum $H$; one model query is

$
  Q_theta(s_t, e, i, h) = Q_(h,e)^theta(s_t, i),
  quad 1 <= h <= b_t <= H
$

rather than one value with an implicit fixed horizon. The maximum $H$ is a dataset, model, and checkpoint contract. The requested residual horizon $h$ is a mandatory model input. The remaining budget $b_t$ determines whether that query is admissible. The step index $t$ is retained as lineage and becomes a learned feature only in a named non-stationarity ablation; it is not required merely because $h$ and $b_t$ exist.

One candidate row is one geometric query. Candidate pose, candidate--target relation, and candidate-local support are encoded once. A lightweight horizon embedding then turns that candidate into a horizon--candidate query:

$
  u_(t,e,h,i)
  =
  op("CrossAttn")_theta(
    x_(t,e,i) + op("Emb")_h(h),
    {h_e^"tgt", Phi_t^"scene", bold(H)_t, b_t}
  )
$

followed by one shared per-row value head. This conditioning follows the general principle of a shared value approximator queried by an explicit task variable @UVFA-schaul2015. Separate $Q_1,dots,Q_H$ networks or heads remain a control for negative transfer between horizons, not the default architecture.

The same state may be scored for one $h$ and return $[B,N_q]$, or for a vector of admissible horizons and return $[B,L,N_q]$. Static scene, target, and candidate encodings are reused across the horizon axis. The horizon queries do not attend to future transitions and require no causal temporal mask: each query receives the same causal state available at step $t$, while the learning target determines how many future rewards it represents.

The valid-action mask sanitizes candidate rows, gates the masked policy argmax, and gates every supervised or bootstrap maximum. It becomes an attention key mask only in architectures where candidate rows themselves are keys. Target-independent root encodings may be reused across targets, but target-dependent candidate generators require per-target tables or a union table with an explicit target--candidate availability mask.

The value family is defined relative to a frozen state and source protocol. An `S0-pose` value, a privileged `CF-GT` selected-depth value, and a deployable observed-state value are different functions even when their tensors have similar shapes. Likewise, “optimal” means optimal continuation only within the generated finite candidate support, hard-validity contract, represented state, and transition distribution. A pose-only state cannot be promoted to a task-sufficient reconstruction value merely by requesting a longer horizon.

=== Horizon-recursive offline learning

Batch fitted Q iteration learns a greedy action-value function from a fixed transition collection through successive supervised regression problems; it does not require online interaction @FittedQIteration-ernst2005. For this bounded problem, the primary variable-horizon recursion is

$
  y_t^((1,e)) = r_t^e
$

and, for $h>1$,

$
  y_t^((h,e))
  =
  r_t^e
  +
  gamma (1-d_t)
  op("max", limits: #true)_(j : m_(t+1,j)=1)
  Q_(bar(theta))(s_(t+1), e, j, h-1)
$

where the lower-horizon prediction is detached, frozen, or supplied by a delayed target copy. The essential structural rule is $Q_h arrow.l Q_(h-1)$: no horizon value bootstraps from itself. Fixed-horizon TD motivates this recursion and shows that horizon-indexed values can share parameters and be updated in parallel, although a staged $h=1$ to $H$ schedule remains the clearest initial control @FixedHorizonTD-deAsis2020.

The stored evidence gives a particularly strong base case. Every candidate admitted by `q_train_mask` can supervise continuous one-step root-normalized gain. If a selected first action has a successor table with dense one-step labels, then the exact finite-support H=2 target is

$
  y_t^((2,e), "exact")
  =
  r_t^e
  +
  gamma
  op("max", limits: #true)_(j : m_(t+1,j)^"train"=1)
  r_(t+1,j)^e
$

This exact target is a mandatory recursion check and H=2 control, not the final thesis objective. The main learner remains the single horizon-conditioned scorer over all supported $h$.

Double Q is an optional estimator for the learned successor maximum. It uses the online scorer to select

$
  j^star
  =
  op("argmax", limits: #true)_(j : m_(t+1,j)=1)
  Q_theta(s_(t+1),e,j,h-1)
$

and a delayed scorer to evaluate that row. This may reduce overestimation from maximizing noisy learned values @DoubleDQN-vanHasselt2015. It is neither a requirement for offline learning nor the definition of the variable-horizon architecture. It cannot repair unsupported long-horizon actions, an aliased actor state, or missing selected-observation evidence.

Complete stored chains also permit regression to truncated Monte-Carlo returns. Those targets estimate the continuation of the behavior policy that generated each chain, $Q^mu$, rather than the greedy finite-support value $Q^star$ unless that behavior policy is itself the specified target policy. They are therefore useful controls and diagnostics, but they must not be mixed with optimal Bellman targets without naming the estimand.

The controlled objective sequence is therefore:

1. dense continuous $Q_1$ supervision on every candidate admitted by `q_train_mask`;
2. exact selected-action $Q_2$ supervision as a base-case certification;
3. one shared, explicitly horizon-conditioned fitted value model for $h=1,dots,H$;
4. Double-Q selector/evaluator backups as a max-bias ablation;
5. behavior-policy Monte-Carlo return regression as a separate estimand;
6. an uncentred one-step-plus-residual decomposition.

Because dense one-step rows vastly outnumber selected transitions at longer horizons, training must balance or sample requested horizons explicitly. Support, loss, calibration, ranking, and selected-action regret are reported separately for every $h$; an aggregate loss must not allow $Q_1$ to hide failure at longer horizons.

=== One-step base and finite-horizon residual

#thesis_status(
  implementation: "exploratory",
  evidence: "pending",
  citation: [@CORAL-cao2019 @FixedHorizonTD-deAsis2020],
  source: "docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex, ordinal RRI paragraph, line 125; docs/contents/theory/candidate_view_dependence.qmd",
  gate: [target-specific root-gain calibration and direct-versus-residual ablation across horizons],
)[The residual decomposition is a testable hypothesis. Direct continuous horizon-conditioned value prediction remains the required control.]

The hypothesis separates calibrated immediate utility from downstream effects:

$
  #eqs.rl.qh_residual_decomposition
$

The base $b_(psi,i)$ must predict continuous one-step target root gain

$
  (Delta_t^e - Delta_(t+1)^e) / (Delta_0^e + epsilon)
$

in the same additive units as the finite-horizon return. Historical state-relative RRI or an ordinal CORAL score may remain auxiliary ranking and calibration outputs, but they are not interchangeable with this additive base unless an explicit calibrated conversion is learned and validated. The residual captures candidate regeneration, selected-observation state changes, occlusion, support, and the requested residual horizon.

It is not exactly mean-centred within each candidate table because duplicate or unrelated rows would then change absolute value targets. Magnitude regularization may be tested without redefining the value field:

$
  #eqs.rl.qh_uncentered_residual
$

CORAL remains a motivated one-step ranking and calibration interface,

$
  #eqs.rl.qh_coral_interface
$

but additive finite-horizon returns are learned in continuous root-gain units. The direct variable-horizon model, exact H=2 control, Double-Q ablation, Monte-Carlo control, and residual learner form separate comparisons rather than one implicit architecture.

#research_todo(
  [Compare staged and joint shared-parameter variable-horizon fitted Q against separate per-horizon heads; include dense Q1, exact Q2, Double Q, behavior-return regression, and the uncentred residual after positive oracle-lookahead headroom is established.],
  source: [variable-horizon learning-target contract],
  gate: [A0/A1 learning, per-horizon support report, and headroom report],
)

#decision_todo(
  [Freeze the maximum horizon, horizon-sampling or loss-weighting rule, lower-horizon target-update schedule, and target-network rule in the resolved training manifest. For the residual ablation, also record whether the one-step base is frozen, slow-fine-tuned, or jointly trained.],
  source: [variable-horizon fitted-value hypothesis],
  gate: [model-selection protocol freeze],
)

The scientific endpoint is not training loss. For every requested-horizon policy, selected trajectories are regenerated under the documented candidate and state protocol and re-scored by the same target-specific oracle used for the baselines. The model succeeds only if it recovers a prespecified fraction of positive oracle-lookahead headroom on held-out scenes without violating horizon, mask, provenance, source, or support constraints.
