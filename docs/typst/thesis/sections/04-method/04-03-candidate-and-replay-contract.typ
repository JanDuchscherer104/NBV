#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status

== Finite Candidate and Replay Contract

#thesis_status(
  implementation: "implemented",
  evidence: "pending",
  source: "aria_nbv/aria_nbv/rollouts/replay/types.py; aria_nbv/aria_nbv/rollouts/replay/engine.py; aria_nbv/aria_nbv/rollouts/zarr_store.py; aria_nbv/tests/rollouts/test_zarr_store.py",
  gate: [preserve deterministic shell identity and selected-transition validation],
)[Finite candidate tables, hard masks, lineage, selected transitions, and the derived `q_h/` view are implemented and schema-tested. Frozen scientific store evidence remains pending.]

At step $t$, candidate generation returns a finite full-shell table #symb.rl.candidate_table with a hard-valid mask $bold(m)_t$ and versioned invalid-reason bitsets. Scores are stored compactly only for hard-valid rows and are bound back to stable shell indices before selection. The admissible action set is

$
  #eqs.rl.finite_action_set
$

Invalid rows remain available for diagnostics and dense replay, but cannot be selected. A row enters the training mask only when it is actor-selectable and has a finite oracle target. Invalid rows have false masks and undefined labels; scene RRI is never substituted for a missing target-specific label.

=== Implemented replay transition

Rollout expansion records the full candidate table, selected valid and shell indices, policy scores and probabilities, selection policy, and random seed. The implemented transition is

$
  #eqs.rl.replay_transition
$

where $x_t$ is the current reference pose, $bold(H)_t$ the selected-pose history, $b_t$ the remaining budget, and $xi_t$ the deterministic generation context. The next candidate table is regenerated around the selected pose under the same target task, history constraints, and versioned generator configuration. This transition changes pose, history, budget, lineage, and action support. It does not imply that the actor has received a new RGB observation or recomputed EFM3D field.

The persisted factual tables retain source and target identity, lineage hashes, step order, selected rows, masks, reasons, sampler provenance, rewards, and support diagnostics. The derived `q_h/` view right-pads states, stores one-step and target-root-gain labels, and exposes only the factual selected transition needed for a temporal-difference backup. Readers can rebuild this view at a different discount without mutating factual replay.

=== Planned scene-state transition

#thesis_status(
  implementation: "planned",
  evidence: "pending",
  citation: [@GenNBV-chen2024 @Hestia-lu2026],
  source: "docs/contents/theory/efm3d_scene_embeddings.qmd; aria_nbv/aria_nbv/oracle/evidence.py",
  gate: [deterministic fusion, source masks, and no-future-observation tests],
)[A deployable successor-state encoder must update only evidence produced by the selected observation. Current GT-mesh selected depth is privileged counterfactual evidence.]

The existing geometry-level counterfactual uses a set union of retained points,

$
  #eqs.rl.counterfactual_transition
$

but a planning memory must additionally preserve whether space is observed occupied, observed free, or still unknown. The proposed sparse update is

$
  #eqs.scene.ray_memory_update
$

Here both evidence terms are indexed by the selected action $a_t$; no unselected candidate render enters the successor state. The source may be a deployable sensor observation or an explicitly privileged selected-depth counterfactual, and that role is stored. The update may add selected surface evidence, carve observed free space, update support and uncertainty, and refresh target-local directional memory. It must not attach RGB, DINO, detector, or EVL descriptors to counterfactual geometry unless a corresponding actor-visible observation exists. Counterfactual-only cells instead carry explicit source and missing-modality masks.

This split prevents two common errors: treating pose-only rollout as complete visual simulation, and treating privileged selected-depth geometry as a deployable sensor stream. The same replay schema supports both the current oracle experiment and later causal scene-memory ablations because source role is part of the state contract.
