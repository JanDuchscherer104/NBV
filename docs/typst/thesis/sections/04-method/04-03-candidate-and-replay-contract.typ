#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status

== Finite Candidate and Replay Contract

#thesis_status(
  implementation: "implemented",
  evidence: "pending",
  source: "aria_nbv/aria_nbv/rollouts/replay/types.py; aria_nbv/aria_nbv/rollouts/replay/engine.py; aria_nbv/aria_nbv/rollouts/zarr_store.py; aria_nbv/aria_nbv/rollouts/qh_reader.py; aria_nbv/tests/rollouts/test_qh_reader.py",
  gate: [preserve deterministic shell identity, source roles, and selected-transition validation],
)[Finite candidate tables, hard masks, lineage, selected transitions, selected-depth persistence, the derived `q_h/` view, and a fail-closed dense-valid supervision profile are implemented and schema-tested. Frozen scientific policy evidence remains pending.]

At step $t$, candidate generation returns a finite full-shell table #symb.rl.candidate_table with a hard-valid mask $bold(m)_t$ and versioned invalid-reason bitsets. Scores are stored compactly only for hard-valid rows and are bound back to stable shell indices before selection. The admissible action set is

$
  #eqs.rl.finite_action_set
$

Candidate orientations factor a component-specific base gaze from a local
yaw--pitch perturbation. Production rollout mixtures resolve every component
to the final seminar support: symmetric yaw and pitch caps of $60 degree$ and
$30 degree$, respectively, with zero roll jitter. A zero resolved yaw or pitch
cap is rejected as a configuration error. The sampled residuals and their
resolved bounds and a per-row bounded-support flag remain attached to the full
shell for visual and statistical audit. Legacy zero-cap spherical samplers are
explicitly unbounded rather than being misrepresented by a zero-area box; view
jitter changes proposal support but does not bypass hard validity rules.

A paired proposal component may reuse one sampled world-space camera center for
two distinct base-gaze families before applying their independent view jitter.
Both rows remain first-class actions and retain a shared `position_pair_id`
plus a `gaze_variant_id`; they are not averaged or collapsed before scoring.
This controlled intervention separates the value of camera translation from
the value of viewing direction at identical acquisition positions.

Invalid rows remain available for diagnostics and dense replay, but cannot be selected. A row enters the training mask only when it is actor-selectable and has a finite oracle target. Invalid rows have false masks and undefined labels; scene RRI is never substituted for a missing target-specific label. `valid_action_mask`, `q_train_mask`, padding, and any deployable feasibility estimate are distinct fields with distinct owners.

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
denominator. A candidate-only Phase-A audit has no such labels, so
`flat_gain` is unavailable rather than inferred from geometric dispersion. A
passing Phase-A family gate is necessary but not sufficient for broad rollout
generation; the final hash-bound pre-scale decision remains a later issue-120
gate.

The frozen 100-scene Phase-A control attempted $6,000$ candidates and admitted
$3,146$ into the compact valid shells. It nevertheless failed the support gate:
$44$ applicable state/family cells had no selected row, $24$ states missed the
aggregate non-forward target-aware-family floor, and $8$ states missed the
root-support threshold. All $100$ reviewed source rows, scenes, and target
states were represented without exclusions. Since this phase deliberately
contains no oracle labels, the flat-gain outcome is unavailable with
denominator zero. This is proposal-support evidence, not evidence about RRI or
candidate quality, and it does not admit broad rollout generation.

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
    artifact is bound to implementation revision
    `31888f86fc6348ef223e5c606f7ad41fda7e3082` and artifact SHA-256
    `78632654ffb1bdf8cc085874483547f090bb6013eab5264efe35a5628c39d356`.
  ],
) <fig:candidate-family-phase-a-support>

=== Implemented replay transition

Rollout expansion records the full candidate table, selected valid and shell indices, policy scores and probabilities, selection policy, and random seed. The implemented transition is

$
  #eqs.rl.replay_transition
$

where $x_t$ is the current reference pose, $bold(H)_t$ the selected-pose history, $b_t$ the remaining budget, and $xi_t$ the deterministic generation context. The next candidate table is regenerated around the selected pose under the same target task, history constraints, and versioned generator configuration.

Proposal and action-selection randomness use separate deterministic streams.
The proposal stream is keyed by the campaign proposal root, the ordered
full-shell indices of previously selected actions, and an explicit proposal
replica. It excludes transient frontier and beam indices. Consequently,
reordering retained trajectories does not change the candidate table for the
same replay state, while changing the replica yields an independent shell
without perturbing action-selection randomness. Selection uses a distinct
recipe seed keyed by the same selected-action history.

This transition is deliberately a replay-control transition, not yet a complete reconstruction-state update. It changes pose, selected-pose history, budget, lineage, and action support. It does not imply that the actor has received a new RGB observation, recomputed EFM3D field, or fused the selected depth into a spatial memory. Any implementation that consumes only these fields must be labelled `S0-pose`.

The persisted factual tables retain source and target identity, lineage hashes, step order, selected rows, masks, reasons, sampler provenance, rewards, selected-depth calibration, and support diagnostics. The derived `q_h/` view right-pads states, stores one-step and target-root-gain labels, and exposes only the factual selected transition needed for the temporal-difference backup defined in @ssec:thesis-horizon-recursive-offline-learning. It does not create counterfactual labels for unselected actions or make privileged selected depth actor-visible.

Training, validation, and test stores must share the same learning semantics:
reward definition, mask meanings, target and actor-state protocols, horizon
support, and label-support profile. They need not share a candidate-generator
hash, rollout-recipe hash, or behavior-policy label. Those fields identify the
sampled population rather than the value function, so each stage binds its own
population provenance into the experiment bundle while the training contract
remains the model identity. This permits a genuinely held-out distribution
without weakening semantic checks. Stage acquisition is deterministic and
scene-disjoint: complete eligible units are hash-ranked within each requested
split, input-feasibility rejections are recorded, and no unit is replaced or
selected using its oracle labels or model error.

=== Selected observation and planned scene-state transition

#thesis_status(
  implementation: "planned",
  evidence: "pending",
  citation: [@GenNBV-chen2024 @Hestia-lu2026],
  source: "docs/contents/theory/efm3d_scene_embeddings.qmd; aria_nbv/aria_nbv/oracle/evidence.py; aria_nbv/aria_nbv/rollouts/zarr_store.py",
  gate: [typed selected-observation reader, deterministic fusion, source masks, and no-future-observation tests],
)[A task-sufficient successor state must update only evidence produced by the selected observation. Current GT-mesh selected depth is privileged counterfactual evidence and requires an explicit `CF-GT` state protocol.]

A selected observation is a typed tuple containing depth, validity mask,
calibration, root-relative camera pose, and an explicit source role. The
geometry successor state consumes this selected evidence:

#eqs.rl.s_cf_geom

The source role distinguishes privileged mesh depth, declared sensor-like
simulation, and an actor-visible sensor observation. Unselected candidate
renders at step $t$ are never elements of the student state.

The existing geometry-level counterfactual uses a set union of retained points,

$
  #eqs.rl.counterfactual_transition
$

but a planning memory must additionally preserve whether space is observed occupied, observed free, or still unknown. The proposed sparse update is

$
  #eqs.scene.ray_memory_update
$

Here both evidence terms are indexed by the selected action $a_t$; no unselected candidate render enters the successor state. The update may add selected surface evidence, carve observed free space, update support and uncertainty, and refresh target-local directional memory. It must not attach RGB, DINO, detector, or EVL descriptors to counterfactual geometry unless a corresponding actor-visible observation exists. Counterfactual-only cells instead carry explicit source and missing-modality masks.

Raw selected depth is an input to the state builder, not necessarily a permanent model token. The reader may emit either the typed selected-observation prefix or a deterministically derived `DynamicSceneState`, but those two representations must not be mixed silently. This split prevents two common errors: treating pose-only replay as complete visual simulation, and treating privileged selected-depth geometry as a deployable sensor stream.
