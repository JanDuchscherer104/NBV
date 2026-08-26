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
  source: "aria_nbv/aria_nbv/vin/models/target_finite_horizon.py; aria_nbv/aria_nbv/lightning/qh_module.py; aria_nbv/aria_nbv/lightning/qh_q2_certification.py; aria_nbv/aria_nbv/oracle/pipelines/online_qh.py; aria_nbv/tests/lightning/test_qh_q2_certification.py",
  gate: [retain the one-step scorer as a matched control, populate a held-out exact-Q2 receipt, and require independent oracle-rescored policy evidence],
)[The modular A0/A1--S0-pose--root-moments finite-horizon scorer, H0/H1 pose-history seam, typed output, scalar horizon query, feasibility auxiliary, regression/CORAL value decoders, fitted-Q learner, bounded exact-Q2 certifier, hard-masked online adapter, and dense-valid data path are implemented. Both decoders complete a one-epoch GPU fit on a real bounded corpus. A1 remains the default interaction and H0 the default history control; H1 is exploratory. The learned exact-Q2 and scientific policy gates remain unmet.]

The actor DTO carries root semidense evidence, GT-derived target pose and extent, root-relative candidate geometry, selected-pose history, remaining budget, and candidate materialization support. It deliberately excludes supervision and audit lineage from scorer inputs. In `root_moments_v1`, semidense support is the number of finite persisted points divided by that chain's persisted point length; the collated batch width is padding only and cannot change the scene token or candidate scores. The current model makes this an executable `S0-pose` baseline, but neither a trained checkpoint nor task-sufficient reconstruction state follows from interface tests alone.

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

One candidate row is one geometric query. Candidate pose, candidate--target relation, and root-scene support are encoded once; remaining budget and requested horizon stay separate named state tokens. The implemented A0 and A1 controls receive identical query and state-token values and return the same-width context:

#eqs.model.qh_state_fusion_controls

followed by the same `[query, context, query times context]` decoder input and shared per-row value head. A0 flattens the five tokens in the fixed semantic order scene, target, causal history, budget, horizon and uses an independent-row MLP. A1 uses candidate-to-state cross-attention; candidates never become keys or values. The controls are feature-matched but not parameter-matched, so comparisons report trainable parameters and runtime rather than attributing a difference solely to attention. This conditioning follows the general principle of a shared value approximator queried by an explicit task variable @UVFA-schaul2015. Fixed-H models and separate $Q_1,dots,Q_H$ heads remain ablations rather than competing public interfaces.

The history token has its own versioned one-factor seam. H0 performs the original masked mean over selected poses expressed from the current camera. H1 keeps those geometric inputs fixed, adds normalized relative age $a_(t,j)=(t-1-j)/H_"max"$, and applies a causal Transformer with a learned empty-prefix token and last-valid readout. The immediate predecessor has age zero; no absolute step embedding is added. Materialized support must equal the complete prefix $j<t$, while padded states remain zero. H1 exposes causal pose order and prefix length, but it does not add selected observations or change the `S0-pose` state estimand. It remains unpromoted until a matched repeated-seed comparison and held-out endpoint evidence justify its capacity.

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

The stored evidence gives a particularly strong base case. The executable objective queries $h=1$ for every realized state and supervises every finite hard-valid candidate with continuous one-step root-normalized gain. Candidate losses are averaged within state before state means are averaged within horizon; non-empty horizons then receive equal weight. Selected-transition recursion is disjoint and begins at $h>1$. This prevents large candidate tables and abundant Q1 labels from silently dominating longer horizons. The bundle records the realized state/candidate support by horizon and online inference rejects a requested horizon absent from that support. If a selected first action has a successor table with dense one-step labels, then the exact finite-support H=2 target is

#eqs.rl.qh_exact_q2_target

The implemented certification surface distinguishes two claims. A unit-level
implementation control injects exact one-step values and proves that the
recursive tensor path reproduces this target. A frozen-bundle population run
instead measures the learned recursion error

#eqs.rl.qh_exact_q2_error

on held-out supported rows. That second quantity includes the learned $Q_1$
approximation and is therefore model evidence, not another implementation
parity test. The population is censused without actor-tensor materialization,
stratified by scene and target identity, configured horizon, candidate-width
bin, candidate generator, rollout recipe, and behavior policy, then selected
by a deterministic balanced hash under explicit global and per-stratum bounds.
The receipt reports chain coverage, exact-row support, per-stratum error,
numeric tolerances, and—when CORAL is used—outer-class occupancy and values
outside the fixed representative support. Longer-horizon interpretation remains
gated until this learned $Q_2$ error passes its frozen support and tolerance
contract and independent held-out endpoint evaluation establishes positive
oracle-lookahead headroom. The existing persisted terminal-step contrast is a
diagnostic proxy and cannot satisfy that endpoint gate.

The census denominator is the complete eligible held-out chain population,
not only chains that happen to contain an exact horizon-two row. A chain that
terminates or becomes unsupported before factual $h=2$ contributes zero exact
rows and therefore lowers support coverage. It must not disappear through
post-hoc filtering. Consequently, an executable one-epoch fit, a valid bundle,
or even low error on a few supported rows cannot promote $h>2$ when the frozen
minimum-row, coverage, or tolerance predicate fails.

Double Q is an optional estimator for the learned successor maximum. It uses the online scorer to select

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

Because dense one-step rows vastly outnumber selected transitions at longer horizons, training and evaluation report state-normalized loss and continuous-unit mean absolute calibration error separately by horizon. Dense $h=1$ additionally reports within-state pairwise ranking accuracy over unequal-target candidate pairs and greedy selected-action regret. The factual selected-transition labels at $h>1$ do not identify either counterfactual quantity, so their per-horizon ranking-pair and regret-state support remains explicitly zero instead of fabricating a metric. Exact or independently oracle-rescored longer-horizon candidate tables are required before those fields can become nonzero. If requested horizons share one learner, their sampling or weighting must be explicit; an aggregate loss must not allow $Q_1$ to hide longer-horizon failure.

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
