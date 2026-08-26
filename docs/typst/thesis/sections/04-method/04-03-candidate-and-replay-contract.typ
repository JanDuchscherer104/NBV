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

=== Implemented replay transition

Rollout expansion records the full candidate table, selected valid and shell indices, policy scores and probabilities, selection policy, and random seed. The implemented transition is

$
  #eqs.rl.replay_transition
$

where $x_t$ is the current reference pose, $bold(H)_t$ the selected-pose history, $b_t$ the remaining budget, and $xi_t$ the deterministic generation context. The next candidate table is regenerated around the selected pose under the same target task, history constraints, and versioned generator configuration.

This transition is deliberately a replay-control transition, not yet a complete reconstruction-state update. It changes pose, selected-pose history, budget, lineage, and action support. It does not imply that the actor has received a new RGB observation, recomputed EFM3D field, or fused the selected depth into a spatial memory. Any implementation that consumes only these fields must be labelled `S0-pose`.

The persisted factual tables retain source and target identity, lineage hashes, step order, selected rows, masks, reasons, sampler provenance, rewards, selected-depth calibration, and support diagnostics. The derived `q_h/` view right-pads states, stores one-step and target-root-gain labels, and exposes only the factual selected transition needed for a temporal-difference backup. It does not create counterfactual labels for unselected actions or make privileged selected depth actor-visible.

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
