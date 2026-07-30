#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status, research_todo, decision_todo

== Target-Conditioned Finite-Horizon Value Model

=== Implemented training infrastructure and planned scorer

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@VIN-NBV-frahm2025 @CORAL-cao2019 @DoubleDQN-vanHasselt2015],
  source: "aria_nbv/aria_nbv/vin/models/target_myopic.py; aria_nbv/aria_nbv/lightning/qh_module.py; aria_nbv/aria_nbv/data_handling/qh_data/views.py",
  gate: [retain the one-step scorer as a matched control and implement the first finite-horizon scorer only after its interface decision],
)[The one-step VIN/CORAL scorer remains the historical myopic control. Replay-chain tensors and a selected-transition Double-Q trainer for an injected scorer are implemented. No deterministic H=2, candidate-to-state, or other production finite-horizon scorer is implemented.]

The implemented actor DTO can carry root semidense evidence, GT-derived target pose and extent, root-relative candidate geometry, selected-pose history, and remaining budget. It deliberately excludes supervision and audit lineage from scorer inputs. These tensors make an `S0-pose` baseline possible, but they do not establish an architecture, checkpoint, or task-sufficient reconstruction state.

Any injected scorer must emit one continuous value per candidate row, while the Lightning adapter owns hard-mask admission, Double-Q target construction, loss, and target synchronization. Candidate-to-state attention, candidate--candidate interaction, and the representation carrier remain production-scorer design choices.

=== Requested-horizon scorer design candidate

#thesis_status(
  implementation: "planned",
  evidence: "pending",
  citation: [@FittedQIteration-ernst2005 @FixedHorizonTD-deAsis2020 @UVFA-schaul2015 @DeepSets-zaheer2017 @SetTransformer-lee2019 @zhou2023query],
  source: "docs/typst/thesis/sections/04-method/04-01-scene-representation-requirements.typ; docs/typst/thesis/sections/04-method/04-02-descriptor-and-encoding-plan.typ; aria_nbv/aria_nbv/lightning/qh_module.py",
  gate: [fixed-H versus requested-horizon source-owner decision, dynamic-state reader, A0/A1 controls, horizon tests, and held-out oracle policy comparison],
)[An explicit requested-horizon query is one candidate design for sharing scene, target, and candidate encoders across horizons. The current canonical direction remains fixed-H with remaining budget in state until the source-owner gate selects and documents an interface.]

For target $e$, the return over exactly the requested residual horizon $h$ is

$
  #eqs.rl.finite_horizon_return
$

and the learned quantity is

$
  #eqs.rl.q_h
$

The notation $Q_H$ names a bounded finite-horizon family. If the explicit requested-horizon design is selected, one model query would be

$
  Q_theta(s_t, e, i, h) = Q_(h,e)^theta(s_t, i),
  quad 1 <= h <= b_t <= H
$

rather than a value from a separately configured fixed-H model. The maximum $H$ is a dataset contract and later a model/checkpoint contract. In this candidate design, requested residual horizon $h$ is a model input and remaining budget $b_t$ determines whether the query is admissible. In the fixed-H alternative, $h$ is implicit and $b_t$ remains state context. The step index $t$ stays lineage unless a named non-stationarity ablation uses it.

In the requested-horizon candidate design, one candidate row is one geometric query. Candidate pose, candidate--target relation, and candidate-local support are encoded once, and a lightweight horizon embedding turns that candidate into a horizon--candidate query:

$
  u_(t,e,h,i)
  =
  op("CrossAttn")_theta(
    x_(t,e,i) + op("Emb")_h(h),
    {h_e^"tgt", Phi_t^"scene", bold(H)_t, b_t}
  )
$

followed by one shared per-row value head. This conditioning follows the general principle of a shared value approximator queried by an explicit task variable @UVFA-schaul2015. Fixed-H models and separate $Q_1,dots,Q_H$ heads remain competing designs until the source-owner decision is complete.

This candidate could score one $h$ and return $[B,N_q]$, or vectorize admissible horizons and return $[B,L,N_q]$. Static encodings would be reused across the horizon axis. Such queries must receive only the causal state available at step $t$; the learning target, not future scorer input, determines how many rewards the value represents.

The valid-action mask sanitizes candidate rows, gates the masked policy argmax, and gates every supervised or bootstrap maximum. It becomes an attention key mask only in architectures where candidate rows themselves are keys. Target-independent root encodings may be reused across targets, but target-dependent candidate generators require per-target tables or a union table with an explicit target--candidate availability mask.

The value family is defined relative to a frozen state and source protocol. An `S0-pose` value, a privileged `CF-GT` selected-depth value, and a deployable observed-state value are different functions even when their tensors have similar shapes. Likewise, “optimal” means optimal continuation only within the generated finite candidate support, hard-validity contract, represented state, and transition distribution. A pose-only state cannot be promoted to a task-sufficient reconstruction value merely by requesting a longer horizon.

=== Horizon-recursive offline learning

Batch fitted Q iteration learns a greedy action-value function from a fixed transition collection through successive supervised regression problems; it does not require online interaction @FittedQIteration-ernst2005. If the requested-horizon design is selected, one candidate lower-horizon recursion is

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

where the lower-horizon prediction is detached, frozen, or supplied by a delayed target copy. The essential structural rule for this candidate is $Q_h arrow.l Q_(h-1)$: no horizon value bootstraps from itself. Fixed-horizon TD motivates this recursion and shows that horizon-indexed values can share parameters and be updated in parallel, although a staged $h=1$ to $H$ schedule remains the clearest initial control @FixedHorizonTD-deAsis2020.

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

This exact target is a useful recursion check and H=2 control. Whether the production learner is one requested-horizon scorer or a fixed-H family remains open at the source-owner gate.

Double Q is an optional estimator for the learned successor maximum. It uses the online scorer to select

$
  j^star
  =
  op("argmax", limits: #true)_(j : m_(t+1,j)=1)
  Q_theta(s_(t+1),e,j,h-1)
$

and a delayed scorer to evaluate that row. This may reduce overestimation from maximizing noisy learned values @DoubleDQN-vanHasselt2015. It is neither a requirement for offline learning nor the definition of the requested-horizon design candidate. It cannot repair unsupported long-horizon actions, an aliased actor state, or missing selected-observation evidence.

Complete stored chains also permit regression to truncated Monte-Carlo returns. Those targets estimate the continuation of the behavior policy that generated each chain, $Q^mu$, rather than the greedy finite-support value $Q^star$ unless that behavior policy is itself the specified target policy. They are therefore useful controls and diagnostics, but they must not be mixed with optimal Bellman targets without naming the estimand.

The objective-design comparison is therefore:

1. dense continuous $Q_1$ supervision on every candidate admitted by `q_train_mask`;
2. exact selected-action $Q_2$ supervision as a base-case certification;
3. fixed-H fitted models versus one explicitly horizon-conditioned model for $h=1,dots,H$;
4. Double-Q selector/evaluator backups as a max-bias ablation;
5. behavior-policy Monte-Carlo return regression as a separate estimand;
6. an uncentred one-step-plus-residual decomposition.

Because dense one-step rows vastly outnumber selected transitions at longer horizons, training and evaluation must report support, loss, calibration, ranking, and selected-action regret separately by horizon under either interface. If requested horizons share one learner, their sampling or weighting must be explicit; an aggregate loss must not allow $Q_1$ to hide longer-horizon failure.

=== One-step base and finite-horizon residual

#thesis_status(
  implementation: "exploratory",
  evidence: "pending",
  citation: [@CORAL-cao2019 @FixedHorizonTD-deAsis2020],
  source: "docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex, ordinal RRI paragraph, line 125; docs/contents/theory/candidate_view_dependence.qmd",
  gate: [target-specific root-gain calibration and direct-versus-residual ablation across horizons],
)[The residual decomposition is a testable hypothesis. Direct continuous finite-horizon value prediction remains the required control under whichever time-query interface is selected.]

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

but additive finite-horizon returns are learned in continuous root-gain units. Fixed-H and requested-horizon models, the exact H=2 control, Double-Q ablation, Monte-Carlo control, and residual learner form separate comparisons rather than one implicit architecture.

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

The scientific endpoint is not training loss. For every claimed horizon, selected trajectories are regenerated under the documented candidate and state protocol and re-scored by the same target-specific oracle used for the baselines. The model succeeds only if it recovers a prespecified fraction of positive oracle-lookahead headroom on held-out scenes without violating horizon, mask, provenance, source, or support constraints.
