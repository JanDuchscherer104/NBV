#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": development_only

== Finite Candidate and Replay Contract

=== Implemented finite action and replay substrate

// evidence:
// - aria_nbv/aria_nbv/rollouts/zarr_store.py:545-546,970-985,1450-1504 -> hard action/q-training validation and cross-table mask invariants.
// - aria_nbv/aria_nbv/rollouts/qh_reader.py:932-935 -> aligned padded read-model masks and labels.
// - aria_nbv/tests/rollouts/test_zarr_store.py:182-206 and aria_nbv/tests/rollouts/test_qh_reader.py:548-558 -> stored return semantics, padding identity, and q_train subset checks.

At step $t$, candidate generation returns a finite table #symb.rl.candidate_table with stable row identity, hard validity, and versioned invalid reasons:

$
  #eqs.rl.finite_action_set
$

Three masks remain separate: the valid-action mask selects physically admitted rows; `q_train_mask` is stricter and additionally requires finite oracle labels; padding marks absent rows in the materialized rectangular view. Invalid rows cannot enter selection, loss, or bootstrap. They remain available for diagnostics. An all-invalid successor has no utility value: it sets no-bootstrap support explicitly rather than becoming a zero or an imputed target.

The implemented replay transition is:

$
  #eqs.rl.replay_transition
$

It updates pose, factual selected-pose history, remaining budget, lineage, and regenerated candidate support. It does not imply a new RGB observation, a recomputed EVL field, or a fused selected-depth scene state. A pose/history chain is therefore an `S0-pose` replay state, not a task-sufficient visual successor.

=== Selected observations and oracle roles

// evidence:
// - aria_nbv/aria_nbv/data_handling/qh_data/views.py:229-257 -> supervision labels, selected transition, discount, and terminal fields are outside actor tensors.
// - aria_nbv/aria_nbv/data_handling/qh_data/batching.py:84-136 -> successor support and explicit bootstrap mask; no-label successors are not silently bootstrapped.
// - aria_nbv/tests/data_handling/test_qh.py:583-622 -> root-only and privileged selected-observation profile admission.

Selected depth is a typed observation with calibration, validity, pose, and source role. The `CF-GT` source is privileged and belongs only to `qh_cfplus_gt_depth_v1`. It is not an ordinary actor input and cannot be silently mixed with `qh_cf0_v1`. Unselected candidate renders never enter the actor state.

The current replay carrier does not update a visual successor state. Missing source or modality evidence is therefore not replaced with a fabricated descriptor; selected depth remains typed metadata and is admitted to actor tensors only under the explicit privileged CF+ protocol.

#development_only(() => [
  === Development and future evidence

  The planned causal update is expressed by the shared equation:

  $
    #eqs.scene.ray_memory_update
  $

  Only selected evidence may update a future successor state. Missing source or modality evidence is represented by masks, not fabricated descriptors.

  Exact $H=2$ targets, recursive targets beyond the supported chain, requested-horizon queries, and Monte Carlo behavior returns are separate development controls. They require their own admitted transition/support evidence and cannot turn sparse replay into dense long-horizon support.
])
