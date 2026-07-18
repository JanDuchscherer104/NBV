#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs

== Finite Candidate and Replay Contract

// implementation: rollouts/replay/types.py; rollouts/replay/engine.py; rollouts/zarr_store.py
At step $t$, candidate generation returns a finite full-shell table #symb.rl.candidate_table with a hard-valid mask $bold(m)_t$ and versioned invalid-reason bitsets. Scores are stored compactly only for hard-valid rows and are bound back to their stable shell indices before selection. The admissible action set is therefore

$
  #eqs.rl.finite_action_set
$

and a selected action is one valid shell row, never an arbitrary continuous pose. The score contract verifies both equality with the table's hard mask and one-to-one alignment between score values and valid shell indices. Invalid rows remain present for diagnostics and dense replay, but they cannot be selected.

Rollout expansion records one transition for every retained branch. A transition contains the full candidate table, selected valid and shell indices, policy scores and probabilities, the selection policy, and the random seed. The trajectory appends the selected pose to the root pose chain. At the next depth, the generator uses the previous selected pose as its reference and regenerates a new finite table while applying the configured history and sibling-diversity constraints. Thus the implemented state transition changes pose, history, budget, and candidate table; it does not claim to synthesize a new actor-visible image or update a learned scene field.

The persisted factual tables preserve source and target identity, lineage hashes, step order, selected candidate row, candidate masks, reason codes, sampler provenance, rewards, and support diagnostics. Target root gain is the finite-horizon reward field. A candidate enters the training mask only when it is actor-selectable, the target and GT label are valid, and the target-root-gain reward is finite. Invalid rows have false masks and `NaN` labels; scene RRI is never substituted for a missing target label.

The derived `q_h/` view right-pads each state to the maximum candidate count in the store. It exposes state, source, target, candidate, and position identifiers; valid-action and training masks; selected candidate indices; one-step target RRI and target root gain; invalid-reason bitsets; and selected-transition temporal-difference fields. The latter contain the selected candidate row, selected reward, next step row, terminal flag, and discount. The store validates this cache against the canonical step and candidate tables, so readers can rebuild it at a different discount without changing factual replay.

Selected-depth rasters and optional target-evaluation crops are separate oracle artifacts. They are aligned to selected steps or candidate rows and carry camera, shape, mask, crop-policy, and source-role metadata. They support successor-state experiments and audits, but their GT-mesh origin prevents them from being silently treated as sensor observations at deployment time.
