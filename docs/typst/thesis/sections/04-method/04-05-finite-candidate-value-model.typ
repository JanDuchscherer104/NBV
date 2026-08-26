#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status, research_todo, decision_todo, prune_todo

== Target-Conditioned Finite-Horizon Value Model

#prune_todo(
  [Retain scalar requested-horizon conditional Q with direct continuous Huber regression as the core. Keep exact horizon two, CORAL, residual, behavior-return, and alternative estimator variants explicitly labelled as diagnostics or ablations.],
  source: [this section; aria_nbv/aria_nbv/lightning/qh_module.py],
  gate: [a frozen scorer interface, training objective, checkpoint, and matched policy evaluation],
)

=== Implemented scorer and training interface

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@VIN-NBV-frahm2025 @CORAL-cao2019 @DoubleDQN-vanHasselt2015],
  source: "aria_nbv/aria_nbv/vin/models/target_finite_horizon.py; aria_nbv/aria_nbv/lightning/qh_module.py; aria_nbv/aria_nbv/oracle/pipelines/online_qh.py; aria_nbv/tests/vin/test_target_finite_horizon.py",
  gate: [retain the one-step scorer as a matched control, certify exact Q2, and require held-out oracle-rescored policy evidence],
)[The A1--S0-pose--root-moments finite-horizon scorer, typed output, scalar horizon query, feasibility auxiliary, modular regression/CORAL value decoders, fitted-Q learner, and hard-masked online adapter are implemented. The one-step VIN/CORAL scorer remains historical evidence and a myopic control; scientific policy evidence is pending.]

The actor DTO carries root semidense evidence, GT-derived target pose and extent, root-relative candidate geometry, selected-pose history, remaining budget, and candidate materialization support. It deliberately excludes supervision and audit lineage from scorer inputs. The current model makes this an executable `S0-pose` baseline, but neither a trained checkpoint nor task-sufficient reconstruction state follows from interface tests alone.

The scorer emits two policy-facing tensors before masking:

#eqs.rl.qh_scorer_interface

`conditional_q` is finite for every materialized row and is trained only where hard validity and Q-label support admit a target. `feasibility_logits` is produced by a target-, horizon-, and action-mask-independent physical trunk and may receive binary supervision on labelled materialized rows. A configured value decoder may attach training-only tensors, but neither policy masking nor feasibility reads them. Lightning owns hard-mask admission, decoder-specific value loss, optional feasibility BCE, exact $h arrow.l h-1$ recursion checks, Double-Q targets, and target synchronization. Online inference compacts conditional values only through the authoritative hard mask.

=== Scalar requested-horizon scorer

#thesis_status(
  implementation: "implemented",
  evidence: "pending",
  citation: [@FittedQIteration-ernst2005 @FixedHorizonTD-deAsis2020 @UVFA-schaul2015 @DeepSets-zaheer2017 @SetTransformer-lee2019 @zhou2023query],
  source: "docs/typst/thesis/sections/04-method/04-01-scene-representation-requirements.typ; docs/typst/thesis/sections/04-method/04-02-descriptor-and-encoding-plan.typ; aria_nbv/aria_nbv/lightning/qh_module.py",
  gate: [exact-Q2 certification, A0/A1 controls, per-horizon support tests, and held-out oracle policy comparison],
)[One scalar $h$ per state is implemented. Omitting the query uses factual remaining budget; public horizon vectorization remains evidence-gated.]

For target $e$, the return over exactly the requested residual horizon $h$ is

$
  #eqs.rl.finite_horizon_return
$

and the learned quantity is

$
  #eqs.rl.q_h
$

The notation $Q_H$ names a bounded finite-horizon family. One model query is

#eqs.model.qh_frozen_interface

rather than a value from a separately configured fixed-H model. The maximum $H_"max"$ is a dataset, model, and checkpoint contract. Requested residual horizon $h$ is a model input and remaining budget $b_t$ determines whether the query is admissible. The step index $t$ stays lineage unless a named non-stationarity ablation uses it.

One candidate row is one geometric query. Candidate pose, candidate--target relation, and root-scene support are encoded once, and a lightweight horizon embedding turns that candidate into a horizon--candidate query:

#eqs.model.qh_candidate_state_cross_attention

followed by one shared per-row value head. This conditioning follows the general principle of a shared value approximator queried by an explicit task variable @UVFA-schaul2015. Fixed-H models and separate $Q_1,dots,Q_H$ heads remain ablations rather than competing public interfaces.

The public interface scores one $h$ per state and returns $[B,S,N_q]$. Multiple horizons use separate calls; private batching may reuse encodings. A public $L$ axis is introduced only after two real atomic callers, measured inadequacy of private batching, and scalar/vector parity tests exist. Every query receives only the causal state available at step $t$; the learning target, not future scorer input, determines how many rewards the value represents.

The candidate materialization mask sanitizes padding. Changing only the valid-action mask cannot change raw conditional Q or feasibility logits:

#eqs.rl.qh_conditional_mask_independence

The valid-action mask instead gates the policy argmax, Q supervision, and every bootstrap maximum. Target-independent root encodings may be reused across targets, but target-dependent candidate generators require per-target tables or a union table with an explicit target--candidate availability mask.

The value family is defined relative to a frozen state and source protocol. An `S0-pose` value, a privileged `CF-GT` selected-depth value, and a deployable observed-state value are different functions even when their tensors have similar shapes. Likewise, “optimal” means optimal continuation only within the generated finite candidate support, hard-validity contract, represented state, and transition distribution. A pose-only state cannot be promoted to a task-sufficient reconstruction value merely by requesting a longer horizon.

=== Horizon-recursive offline learning

Batch fitted Q iteration learns a greedy action-value function from a fixed transition collection through successive supervised regression problems; it does not require online interaction @FittedQIteration-ernst2005. The frozen lower-horizon recursion is

#eqs.rl.target_root_gain_reward

and, for $h>1$,

#eqs.rl.qh_doubleq_target

where the lower-horizon prediction is detached, frozen, or supplied by a delayed target copy. The essential structural rule for this candidate is $Q_h arrow.l Q_(h-1)$: no horizon value bootstraps from itself. Fixed-horizon TD motivates this recursion and shows that horizon-indexed values can share parameters and be updated in parallel, although a staged $h=1$ to $H$ schedule remains the clearest initial control @FixedHorizonTD-deAsis2020.

The stored evidence gives a particularly strong base case. Every candidate admitted by `q_train_mask` can supervise continuous one-step root-normalized gain. If a selected first action has a successor table with dense one-step labels, then the exact finite-support H=2 target is

#eqs.rl.finite_horizon_return

This exact target is the required recursion check and H=2 control. Longer-horizon interpretation remains gated until fitted Q2 matches this factual target on held-out supported rows and oracle lookahead shows positive headroom.

Double Q is an optional estimator for the learned successor maximum. The
nonterminal bootstrap first intersects hard action support with factual support
at horizon $h-1$:

#eqs.rl.qh_supported_successor_set

The online scorer then selects

#eqs.rl.qh_doubleq_index

and a delayed scorer to evaluate that row. This may reduce overestimation from maximizing noisy learned values @DoubleDQN-vanHasselt2015. It is neither a requirement for offline learning nor the definition of the frozen scalar requested-horizon interface. It cannot repair unsupported long-horizon actions, an aliased actor state, or missing selected-observation evidence.

Complete stored chains also permit regression to truncated Monte-Carlo returns. Those targets estimate the continuation of the behavior policy that generated each chain, $Q^mu$, rather than the greedy finite-support value $Q^star$ unless that behavior policy is itself the specified target policy. They are therefore useful controls and diagnostics, but they must not be mixed with optimal Bellman targets without naming the estimand.

The objective-design comparison is therefore:

1. dense continuous $Q_1$ supervision on every candidate admitted by `q_train_mask`;
2. exact selected-action $Q_2$ supervision as a base-case certification;
3. direct continuous regression versus fixed-support CORAL decoding over the same fitted-Q targets;
4. the shared scalar-horizon model versus fixed-H or separate-head ablations for $h=1,dots,H_"max"$;
5. Double-Q selector/evaluator backups as a max-bias ablation;
6. behavior-policy Monte-Carlo return regression as a separate estimand;
7. an uncentred one-step-plus-residual decomposition.

Because dense one-step rows vastly outnumber selected transitions at longer horizons, training and evaluation must report support, loss, calibration, ranking, and selected-action regret separately by horizon under either interface. If requested horizons share one learner, their sampling or weighting must be explicit; an aggregate loss must not allow $Q_1$ to hide longer-horizon failure.

=== Modular continuous-value decoding

#thesis_status(
  implementation: "implemented",
  evidence: "pending",
  citation: [@CORAL-cao2019 @QRDQN-dabney2017],
  source: "aria_nbv/aria_nbv/vin/modules/qh_value_decoders.py; aria_nbv/aria_nbv/lightning/qh_module.py; aria_nbv/tests/vin/test_qh_value_decoders.py",
  gate: [fit-data-only support selection, held-out per-horizon ranking and calibration, support-saturation reports, and matched policy evaluation],
)[Direct regression and fixed-support CORAL are executable alternatives over the same candidate-state features and the same continuous fitted-Q targets. Regression remains canonical; CORAL is an ordinal ablation, not a new action-value estimand.]

The representation trunk produces one feature vector per materialized candidate row. A terminal decoder maps that vector to the scalar `conditional_q` consumed by the unchanged Double-Q backup and hard-masked selector. The regression decoder applies a per-row MLP and linear output, trained with Huber loss in continuous root-gain return units. The CORAL decoder applies a per-row MLP and $K-1$ cumulative thresholds. For fitted-Q target $y_n$, fixed edges #symb.rl.coral_q_edge create the ordinal class #symb.rl.coral_q_label; standard cumulative binary cross-entropy supervises the thresholds @CORAL-cao2019:

#eqs.rl.qh_coral_interface

CORAL provides order, not metric distance. The continuous interpretation used by backup and ranking is an additional experiment contract: repaired class mass is averaged through fixed, strictly increasing representatives #symb.rl.coral_q_value. Edges, representatives, threshold initialization, and decoder kind are therefore scorer configuration and inference-bundle identity. Changing them defines another model even if $K$ is unchanged. Invalid candidates are not mapped to the lowest class; hard-invalid and unsupported selected rows are excluded before either Huber or CORAL loss.

The outer CORAL classes are open-ended while decoded values saturate at the outer representatives. Every CORAL run consequently reports the fraction of fitted-Q targets below and above the representative support, the outer-class fraction, and pre-repair cumulative-probability order violations. Support edges and representatives must be selected using fit data only and then frozen before validation or test evaluation. A one-epoch GPU smoke proves the executable transaction and bundle reconstruction, not scientific superiority or comparability of Huber and cumulative-BCE loss magnitudes.

If a third decoder is promoted, quantile regression is the most coherent next study: it estimates a return distribution whose expectation can preserve the scalar ranking seam, whereas CORAL only discretizes one scalar target @QRDQN-dabney2017. Such a head is justified only after stochastic returns or actor-state aliasing are measured, and it requires a separately frozen distributional Bellman projection, quantile support, risk-neutral or risk-sensitive decoding rule, and calibration evaluation. It must not be introduced as a stylistic replacement for direct Q.

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

#eqs.rl.target_root_gain_reward

in the same additive units as the finite-horizon return. Historical state-relative RRI or an ordinal CORAL score may remain auxiliary ranking and calibration outputs, but they are not interchangeable with this additive base unless an explicit calibrated conversion is learned and validated. The residual captures candidate regeneration, selected-observation state changes, occlusion, support, and the requested residual horizon.

It is not exactly mean-centred within each candidate table because duplicate or unrelated rows would then change absolute value targets. Magnitude regularization may be tested without redefining the value field:

$
  #eqs.rl.qh_uncentered_residual
$

The historical one-step CORAL score remains a motivated myopic ranking and calibration interface, but it must not be confused with the implemented finite-horizon CORAL decoder above. The historical head discretizes one-step RRI; the new decoder discretizes the continuous fitted-Q target and decodes back to return units. Fixed-H and requested-horizon models, the exact H=2 control, Double-Q ablation, Monte-Carlo control, and residual learner form separate comparisons rather than one implicit architecture.

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
