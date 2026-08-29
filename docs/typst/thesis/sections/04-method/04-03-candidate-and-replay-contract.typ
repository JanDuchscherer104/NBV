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

The persisted supervision profile makes label density an auditable contract
rather than an inference from array shape. Historical stores declare
`legacy_unspecified` together with `subset_of_action_v1`: their Q-label support
may be any subset of hard-valid materialized rows and cannot establish dense
one-step supervision. A fitted-Q store may instead declare `dense_valid`
together with `equals_action_on_realized_steps_v1`. The writer then proves,
and the reader revalidates, exact equality between `q_train_mask` and
`valid_action_mask` on every realized state. Padding is excluded from both
masks. Hard-invalid materialized rows remain useful binary examples for the
physical feasibility head, but receive neither a fabricated Q target nor
bootstrap support. Unknown or crossed profile pairs fail closed.

For benchmark reporting, *proposal support* is the persisted set of candidate
rows that a declared generator attempted, with applicability and validity
masks retained per family. *Proposal regret* is a descriptive comparison
between the selected row and the best admissible row under the same persisted
oracle contract; it is unavailable when no compatible oracle labels exist.
Scene-paired aggregation first computes state-level quantities and then gives
each scene equal weight, preventing scenes with more states from dominating a
macro estimate. An immutable evidence bundle is the hash-bound JSON manifest
and Parquet projection of these facts. Readers reject incomplete, stale,
schema-mismatched, fixture, or hash-mismatched bundles; presentation layers
consume the reader and do not recompute scientific quantities.

The candidate-family preflight separates two estimands. Per factual state, the
root-support floor is $max(12, ceil(0.25 N_q))$; thus $14$ hard-valid rows fail
and $15$ pass for $N_q=60$. Independently, the versioned diagnostic family
floor requires at least one final-shell row from every applicable family in
each audited state and at least three final-shell rows in total from
applicable non-forward target-aware families. Forward-local selections cannot
satisfy the second requirement. Inapplicable family/state cells remain
explicit and do not fail the gate, whereas missing legacy applicability is an
unknown provenance state and fails closed for deployment. These rules diagnose
proposal support; they do not assign low utility to invalid or absent
candidates. Here selection means admission into the compact valid action shell,
not the single action later chosen by the rollout policy.

Reward variation is label-conditional. When finite target-root-gain labels
exist under one manifest-bound oracle contract, the preflight compares their
observed range with a versioned tolerance and reports the exact label-support
denominator. A Phase-A audit has no such reward labels, so `flat_gain` is
unavailable with both its label and eligible-state denominators reported as
zero rather than being inferred from geometric dispersion. It is specifically
a no-render, no-reward-label proposal-support audit with privileged
ground-truth target instruction and mesh validity, not an oracle-free audit. A
passing Phase-A family gate is necessary but not sufficient for broad rollout
generation; the final hash-bound pre-scale decision remains a later issue-120
gate.

All persisted Phase-A geometry uses the proposal-support normalization
$ #eqs.spatial.candidate_proposal_support_normalization $. The columns of
$bold(B)_(r,t)^"Z-up"$ are the horizontal expansion-to-target direction, its
world-Z-up left direction, and world up. Candidate centres and target-relative
vectors are divided by the current three-dimensional target distance, while
camera-forward directions are rotated by the same basis but remain unit
vectors. Hence target-forward and target-lateral plots are invariant to factual
rig yaw; rig-frame components cannot carry those axis labels directly.

The frozen 100-scene Phase-A control attempted $6,000$ candidates and admitted
$3,146$ into the compact valid shells. It nevertheless failed the support gate:
$44$ applicable state/family cells had no selected row, $24$ states missed the
aggregate non-forward target-aware-family floor, and $8$ states missed the
root-support threshold. All $100$ reviewed source rows, scenes, and target
states were represented without exclusions. Since this phase deliberately
contains no reward labels, the flat-gain outcome is unavailable with label and
eligible-state denominators both zero. This is proposal-support evidence, not
evidence about RRI or candidate quality, and it does not admit broad rollout
generation.

#figure(
  image(
    "../../../../contents/evidence/candidate_family_phase_a_wp02_audit_heatmap.svg",
    width: 100%,
  ),
  caption: [
    Candidate-family survival for one deterministic scene from each of the ten
    persisted Phase-A audit strata. Each cell reports compact-valid-shell
    membership divided by attempted rows for one factual state and proposal
    family. The complete 100-state matrix remains in the evidence bundle. The
    artifact is bound to clean execution revision
    `2baf7cf6b276b81c50d01d45b152016d7cf68033`, generation revision
    `a2ae86b7463930c9`, and artifact SHA-256
    `6d33e9e3d68737c8a6a5589ae5117c1e4d7fcaa89056fcfcaec1d315e4509c83`.
    The stored shells, support counts, verdict, and execution identity are
    unchanged. Geometry correction revision
    `phase-a-target-aligned-z-up-v1` rotates the authenticated candidate
    centres, target-relative vectors, and view directions into the canonical
    target-aligned world-Z-up basis without rerunning candidate generation. Its
    predecessor artifact is
    `60b271db515a5e665fcb7bbeeecb87e6acb4bac2ff8e28b26b7308911328759c`.
  ],
) <fig:candidate-family-phase-a-support>

=== Implemented replay transition

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
