#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status

== Finite Action and Causal Replay

#thesis_status(
  implementation: "implemented",
  evidence: "pending",
  source: "aria_nbv/aria_nbv/rollouts/replay/engine.py; aria_nbv/aria_nbv/rollouts/zarr_store.py; aria_nbv/aria_nbv/rollouts/qh_reader.py; aria_nbv/tests/rollouts/test_qh_reader.py",
  gate: [retain deterministic row identity, source roles, hard-mask isolation, and selected-transition validation],
)[Finite candidate tables, hard masks, factual selected transitions, and dense one-step label admission are implemented and tested. Population support and policy outcomes remain pending.]

At step $t$, the generator returns the full candidate table
#symb.rl.candidate_table, a hard-valid mask $bold(m)_t$, and versioned failure
reasons. The admissible action set is

$
  #eqs.rl.finite_action_set
$

Invalid rows remain auditable but cannot enter selection, Q supervision, or a
bootstrap maximum. A feasible row may have negative utility; infeasibility is
therefore never encoded as a small value. Padding, materialization,
`valid_action_mask`, `q_train_mask`, and any predicted feasibility remain
distinct. Under the dense-valid supervision profile, the writer proves and the
reader revalidates equality of Q-label support and hard action support on every
realized state. Unknown or legacy label-density profiles fail closed for this
claim.

Candidate orientations factor a component-specific base gaze from bounded
yaw--pitch perturbations. Paired proposal components may reuse a camera centre
across two base-gaze families, but both remain separate actions. This makes
translation and viewing direction distinguishable without collapsing their
values. Generator family, sampled support, hard rejection, and stable shell
identity remain attached to every row so proposal coverage can be audited
before policy quality is interpreted.

=== Factual transition

After selecting an admitted row, the replay engine applies

$
  #eqs.rl.replay_transition
$

where $x_t$ is the current reference pose, $bold(H)_t$ the selected-pose
prefix, $b_t$ the remaining budget, and $xi_t$ the deterministic generation
context. The next candidate table is regenerated around the selected pose under
the same target task and versioned generator. Proposal and action-selection
randomness use separate streams keyed by the factual selected-action history,
so reordering retained trajectories cannot change a previously defined state.

This is the complete transition of the selected `S0-pose` method. It changes
reference pose, selected-pose history, remaining budget, and finite action
support. It does not claim that the actor received RGB, fused depth, or updated
a spatial reconstruction. Selected mesh-rendered depth may be persisted as
privileged counterfactual evidence for a separate control, but unselected
candidate renders never enter a successor state.

The normalized replay view expands one retained chain into its realized
decision states. Each state sees only the prefix available before its action.
Several states from one chain may share a batch, but that tensor colocation
does not create temporal communication. The factual selected action supplies
the only successor link used by finite-horizon learning; no counterfactual
transition is fabricated for unselected rows.

Training, validation, and test populations must share reward, mask, target
protocol, actor-state protocol, horizon, and label-support semantics. They may
use different candidate generators or behavior policies because those fields
describe population shift rather than alter the value definition. Each split
therefore binds its own support provenance, and acquisition remains
scene-disjoint and independent of oracle outcomes or model error.
