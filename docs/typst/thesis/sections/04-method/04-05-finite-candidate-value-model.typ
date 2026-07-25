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
)[The one-step VIN/CORAL scorer remains the historical myopic control. A dedicated development path now implements a deterministic V0, horizon-two, candidate-to-state scorer and selected-transition Double-Q trainer. Frozen matched-control and policy evidence remain pending.]

The implemented H=2 tracer receives root semidense geometry reduced to global moments, GT-derived target pose and extent, root-relative candidate geometry, candidate-local target relations, selected-pose history, and remaining budget. It does not consume root EVL voxel tokens, selected-depth geometry, or an occupied/free/unknown dynamic memory. It is therefore an `S0-pose` representation baseline and must not be described as the task-sufficient reconstruction-state model.

The target-conditioned tracer emits one continuous value per candidate row. Candidate rows are independent queries over shared scene-summary, target, budget, and history tokens; there is no candidate--candidate attention. The hard action mask remains external to the value head and gates selection and loss. This implementation establishes a runnable architecture and optimization seam, not evidence that non-myopic policy quality improves.

=== Canonical candidate-to-state model

#thesis_status(
  implementation: "planned",
  evidence: "pending",
  citation: [@DeepSets-zaheer2017 @SetTransformer-lee2019 @zhou2023query @DoubleDQN-vanHasselt2015],
  source: "docs/typst/thesis/sections/04-method/04-01-scene-representation-requirements.typ; aria_nbv/aria_nbv/vin/models/target_finite_horizon.py; docs/contents/theory/candidate_view_dependence.qmd",
  gate: [dynamic-state reader, A0/A1 controls, invariant tests, and held-out oracle policy comparison],
)[The canonical method is a target-conditioned candidate-to-state model over a typed static/dynamic scene state. Candidate--candidate interaction and exact equivariance remain later ablations.]

For target $e$, the return over at most $h$ future selections is

$
  #eqs.rl.finite_horizon_return
$

and the learned quantity is

$
  #eqs.rl.q_h
$

Here $H$ denotes the experiment's maximum planning horizon, $h$ the requested residual horizon for one value query, $b_t$ the remaining acquisition budget, and $t$ the current step. The implemented fixed-H=2 tracer sets $h=b_t$ by construction. A general model must either receive $h$ explicitly or expose separate $Q_1, dots, Q_H$ heads; encoding only $H$ and $b_t$ is not sufficient to define arbitrary residual-horizon queries.

One candidate row is one query. The query contains candidate-local pose, target relation, and candidate-specific support reads. Target state, static scene context, dynamic selected-observation memory, ordered history, remaining budget, current step, and requested horizon form shared state tokens. The canonical interaction is

$
  #eqs.model.qh_candidate_state_cross_attention
$

followed by a shared per-row value head. The valid-action mask gates candidate query sanitization, policy selection, and every supervised or bootstrap maximum. It is applied as an attention key mask only in architectures where candidate rows themselves become keys. No candidate-index embedding is permitted.

Target-independent root encodings may be reused across targets. Target-dependent candidate generators do not generally produce the same table for every target; multi-target evaluation therefore uses per-target candidate tables or a union table with an explicit target--candidate availability mask.

=== Learning-target ladder

All eligible candidate rows can supervise one-step root-normalized gain. For a successor state with dense one-step labels, a fixed H=2 target is available without a learned bootstrap:

$
  y_t^((2,e))
  =
  r_t^e
  +
  gamma
  max_(i : m_(t+1,i)^"train" = 1)
  r_(t+1,i)^e
$

This exact finite-support target is the primary H=2 control because it removes target-network drift and uses the oracle labels already stored for successor candidates. Selected-transition Double Q remains a valid generalized fitted-value method and an ablation, but it becomes methodologically necessary only when the required future-horizon value is not directly available from dense labels, as for H>2 or sparse successor supervision.

The controlled objective sequence is therefore:

1. dense continuous $Q_1$ supervision on every candidate admitted by `q_train_mask`;
2. exact selected-action $Q_2$ supervision from dense successor one-step labels;
3. fitted masked Double Q for longer horizons or incomplete future labels;
4. an uncentred one-step-plus-residual decomposition.

=== One-step base and finite-horizon residual

#thesis_status(
  implementation: "exploratory",
  evidence: "pending",
  citation: [@CORAL-cao2019 @DoubleDQN-vanHasselt2015],
  source: "docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex, ordinal RRI paragraph, line 125; docs/contents/theory/candidate_view_dependence.qmd",
  gate: [target-specific root-gain calibration and direct-versus-residual ablation],
)[The residual decomposition is a testable hypothesis. Direct continuous $Q_h$ and exact H=2 supervision remain required controls.]

The hypothesis separates calibrated immediate utility from downstream effects:

$
  #eqs.rl.qh_residual_decomposition
$

The base $b_(psi,i)$ must predict continuous one-step target root gain

$
  (Delta_t^e - Delta_(t+1)^e) / (Delta_0^e + epsilon)
$

in the same additive units as the finite-horizon return. Historical state-relative RRI or an ordinal CORAL score may remain auxiliary ranking and calibration outputs, but they are not interchangeable with this additive base unless an explicit calibrated conversion is learned and validated. The residual captures candidate regeneration, selected-observation state changes, occlusion, support, and remaining horizon.

It is not exactly mean-centred within each candidate table because duplicate or unrelated rows would then change absolute value targets. Magnitude regularization may be tested without redefining the value field:

$
  #eqs.rl.qh_uncentered_residual
$

CORAL remains a motivated one-step ranking and calibration interface,

$
  #eqs.rl.qh_coral_interface
$

but additive finite-horizon returns are learned in continuous root-gain units. The direct continuous model, exact H=2 learner, Double-Q learner, and residual learner form separate controlled comparisons rather than one implicit architecture.

#research_todo(
  [Compare dense Q1, exact supervised Q2, selected-transition Double Q, and the uncentred residual only after the target-specific label distribution and positive oracle-lookahead headroom are established.],
  source: [finite-horizon learning-target contract],
  gate: [A0/A1 learning and headroom report],
)

#decision_todo(
  [For the residual ablation, freeze, slow-fine-tune, and joint-training variants remain admissible until validation evidence selects one; record the chosen base update rule and checkpoint provenance.],
  source: [residual training hypothesis],
  gate: [model-selection protocol freeze],
)

The scientific endpoint is not training loss. For every trained policy, selected trajectories are regenerated under the documented candidate and state protocol and re-scored by the same target-specific oracle used for the baselines. The model succeeds only if it recovers a prespecified fraction of positive oracle-lookahead headroom on held-out scenes without violating mask, provenance, source, or support constraints.