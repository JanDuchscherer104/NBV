#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status, research_todo, decision_todo

== Target-Conditioned Finite-Horizon Value Model

=== Implemented control and explicit scaffold

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@VIN-NBV-frahm2025 @CORAL-cao2019],
  source: "aria_nbv/aria_nbv/vin/models/target_myopic.py; aria_nbv/aria_nbv/vin/models/target_finite_horizon.py; aria_nbv/aria_nbv/lightning/_candidate_scorer_contract.py",
  gate: [retain the current one-step scorer as the matched myopic control],
)[The one-step VIN/CORAL scorer and finite-horizon configuration scaffold exist. Frozen matched-control evidence is pending. Positive-width target conditioning and the finite-horizon network are not implemented.]

The current VINv3 scorer predicts per-candidate ordinal one-step RRI evidence from scene and candidate geometry without a learned target token. Its target-conditioned configuration accepts only target-descriptor width zero. The finite-horizon configuration records horizon, discount, and candidate-token width, but model construction raises `NotImplementedError`, and the current Lightning contract rejects the configuration because its CORAL objective does not consume rollout returns, hard action masks, or selected-transition links.

This boundary makes the implemented VIN path a necessary control rather than evidence for the proposed planner. Learned-policy claims require a dedicated `q_h/` reader, finite-horizon checkpoint, frozen split and configuration, and oracle re-evaluation of selected trajectories.

=== Canonical planned transformer

#thesis_status(
  implementation: "planned",
  evidence: "pending",
  citation: [@DeepSets-zaheer2017 @SetTransformer-lee2019 @zhou2023query @DoubleDQN-vanHasselt2015],
  source: "docs/literature/tex-src/arXiv-Set-Transformer/03_main.tex, Sec. Set Transformer, lines 2--51; docs/literature/tex-src/arXiv-QCNet/main.tex, Sec. Query-Centric Scene Encoder, lines 159--161; aria_nbv/aria_nbv/vin/models/target_finite_horizon.py; docs/contents/theory/candidate_view_dependence.qmd",
  gate: [A0 reader/MLP control, A1 implementation, invariant tests, and held-out oracle policy comparison],
)[The canonical model is a minimal target-conditioned candidate-to-state Transformer. Candidate-candidate interaction, exact equivariance, and richer scene encoders are ordered ablations rather than prerequisites.]

For target $e$, the return over at most $H$ selections is

$
  #eqs.rl.finite_horizon_return
$

and the learned quantity is

$
  #eqs.rl.q_h
$

One candidate row is one query. Target, scene, selected history, remaining budget, current step, and requested horizon form shared state tokens. The canonical interaction is

$
  #eqs.model.qh_candidate_state_cross_attention
$

followed by a shared per-row value head. The valid-action mask is applied to attention where rows are keys, to selection, and to every bootstrap maximum. The training mask gates supervised losses. No candidate-index embedding is permitted. Multiple target tokens may share scene and candidate encodings and be evaluated in parallel under a target--candidate mask, which preserves the same network for single-target and multi-target inference.

Time and horizon conditioning prevent an otherwise identical candidate from receiving the same value at different remaining budgets. They do not reveal future observations: a state at step $t$ contains only logged or selected evidence available through $t$. A requested horizon longer than the remaining rollout support is masked or terminated rather than padded with invented transitions.

The first implementation sequence is A0 followed by A1 from @tab:geometric-learning-ladder. A0 establishes whether the replay target is learnable without attention. A1 then tests whether reusable target and scene tokens explain additional value. Candidate-candidate attention is introduced only if fixed-state candidate queries leave a measurable error correlated with valid-set context.

=== One-step base and finite-horizon residual

#thesis_status(
  implementation: "exploratory",
  evidence: "pending",
  citation: [@CORAL-cao2019 @DoubleDQN-vanHasselt2015],
  source: "docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex, ordinal RRI paragraph, line 125; docs/contents/theory/candidate_view_dependence.qmd",
  gate: [target-specific label audit and direct-versus-residual ablation],
)[The residual decomposition is a testable hypothesis, not a consequence of object-centric NBV literature. Direct continuous $Q_H$ remains the required control.]

The hypothesis separates calibrated immediate utility from downstream effects:

$
  #eqs.rl.qh_residual_decomposition
$

The base $b_(psi,i)$ represents one-step target gain. The residual captures candidate regeneration, selected-history geometry, occlusion, support, and remaining horizon. It is not exactly mean-centred within each candidate table because duplicate or unrelated rows would then change absolute temporal-difference targets. Magnitude regularization may be tested without redefining the value field:

$
  #eqs.rl.qh_uncentered_residual
$

CORAL remains a motivated one-step ranking and calibration interface,

$
  #eqs.rl.qh_coral_interface
$

but additive finite-horizon returns are learned in continuous units. The direct continuous $Q_H$ head, the residual head with a frozen base, and the residual head with slow or joint fine-tuning form the controlled comparison.

#research_todo(
  [Compare direct continuous value prediction against the uncentred residual only after the target-specific label distribution, one-step calibration, and positive oracle-lookahead headroom are established.],
  source: [finite-horizon model contract],
  gate: [A0/A1 learning and headroom report],
)

#decision_todo(
  [Freeze, slow-fine-tune, and joint-training variants are all admissible until validation evidence selects one; the final thesis must record the chosen base-network update rule and checkpoint provenance.],
  source: [residual training hypothesis],
  gate: [model-selection protocol freeze],
)

The scientific endpoint is not training loss. For every trained policy, selected trajectories are regenerated under the documented candidate contract and re-scored by the same target-specific oracle used for the baselines. The model succeeds only if it recovers a prespecified fraction of positive oracle-lookahead headroom on held-out scenes without violating mask, provenance, or support constraints.
