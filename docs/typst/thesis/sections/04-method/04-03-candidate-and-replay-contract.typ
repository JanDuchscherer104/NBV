#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": *
#import "@preview/booktabs:0.0.4": *

== Candidate and Replay Contract

// source: aria_nbv/aria_nbv/pose_generation/candidate_mixture.py:16-24 and aria_nbv/aria_nbv/pose_generation/candidate_mixture.py:150-177 define the three-family default and per-row provenance.
// source: aria_nbv/aria_nbv/rollouts/zarr_store.py:224-263 persists candidate masks, sampler provenance, rewards, and support metrics.
Each decision state carries a finite candidate table #symb.rl.candidate_table, hard mask $bold(m)_t$, invalid-reason vector $bold(rho)_t$, and the target descriptor #symb.entity.target_desc. It also stores selected-view history and remaining budget. The admissible action is a valid candidate row index:

$
  #eqs.rl.finite_action_set
$

Selecting a candidate means choosing a valid index $a_t=i in cal(A)_t$ for the transition. Oracle rendering follows the calibrated depth-rendering contract, so camera-frame and rasterizer conventions are part of the label contract rather than model input @PyTorch3D-Cameras-2025. All valid candidates may be rendered at the oracle layer to score one-step labels, while the rollout writer separately persists selected/parent depth at a canonical configured resolution as actor-history state for successor #symb.rl.qh encoders.

After selection, acquired geometry is added to the current geometry:

$
  #eqs.rl.counterfactual_transition
$

The representation-level transition also updates the sparse ray-aware memory:

$
  #eqs.scene.ray_memory_update
$

This update can add selected surface evidence, ray-carve selected free space, convert unknown cells into observed-free or observed-surface cells, update support counts and uncertainty, and refresh target-local directional memory. It cannot attach a visual descriptor to newly selected counterfactual geometry unless a corresponding actor-visible RGB observation exists; those cells instead carry a selected-depth geometry source and a missing-visual-descriptor mask.

The next candidate table $cal(Q)_(t+1)$ is regenerated from updated geometry, selected-view history, and remaining horizon metadata with the same logged mixture families, while root local @egocentric-voxel-lifting:short evidence remains fixed unless a later ablation explicitly recomputes it. The current target-conditioned mixture vocabulary contains forward/local candidates, target-bearing candidates, lateral target-bypass candidates, bounded orientation jitter, and per-row strategy provenance. The older radial free-shell sampler from the seminar paper is retained as a historical upper-bound or stress ablation, not as the default target-conditioned candidate distribution.

Candidate provenance is a model input only through typed scalar or embedding channels. The row stores `strategy_id`, `position_id`, `mixture_id`, `sampler_probability`, target-distance/bearing diagnostics, motion-realism diagnostics, and invalid-reason bits. The training reader may embed these as candidate-family tokens, but the model must still pass row-shuffle and duplicate-row tests: the family label explains how the row was sampled, not an ordering prior.

Candidate order has no semantics, so shuffled-candidate evaluation is required. The descriptor section defines the candidate self token, query-local relation encodings, and target-local directional memory used by the model. The replay contract stores the canonical facts those descriptors are derived from: poses in documented frames, selected-view lineage, candidate-family provenance, target/support counters, masks, and reason codes. This keeps row descriptors reproducible without making their current tensor encoding the immutable data format.

The minimum replay row contains scene/snippet/target/step identifiers, counterfactual state, target descriptor, candidate table, masks, invalid reasons, selected action, target reward, successor state, successor candidates, successor masks, and policy/seed/sampler metadata. This row reproduces the mask, selected transition, value target, and oracle re-evaluation.
