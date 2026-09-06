# PR190 symbolic / computational diagram candidates

These four `.mmd` sources replace the diagram proposals in
[review 5100419765](https://github.com/JanDuchscherer104/ARIA-NBV/pull/190#pullrequestreview-5100419765).
They are **not thesis includes**. Their scientific/notation baseline is PR190
`b420d20cc01aa76451d002811f850bc87869b525`; hosted CI reads that complete generated
`docs/notation.yml` without executing code from the snapshot. Before inclusion,
revalidate against the destination branch. Main's notation is not silently
assumed identical to this unmerged Method revision.

## How to read computational labels

Mathematical data labels are exact projections from canonical Typst. A processing
box shows either a full canonical equation or source-bound computational notation.
`%% aria-compute` points to the governing equation; it does not assert that a
pseudocode string is a verbatim formula or executable implementation.

Names inside `<code>` denote input-port roles, not new thesis variables:
`query` is the candidate row, `state` is the shared token stack, and `context`
is A1's attended result; `physical` is the physical token. `scene`, `target`,
`history`, `budget` and `horizon` refer to their labelled mathematical inputs.
`root`/`current` inside `PoseEnc` are relative candidate transforms. A dot/arrow
in a layer pipeline means function composition; `*` in feature fusion is an
elementwise product. Layers act independently on each candidate row.

For replay, `gains` are current-state oracle labels, `action` indexes the selected
row, `next` is the factual successor, and `supported` is its hard-valid,
horizon-supported action set. The delayed target network evaluates the action
selected by the online network. Terminal continuation is zero **without** querying
a missing successor. Empty action support must terminate/abstain through the
owning protocol; an argmax over an empty set is not intended.

For the proposed memory, `compose` is a structural assembly, not a claimed learned
fusion layer. The ellipsis preserves the canonical optional point/appearance,
entity and directional context omitted from this compact view. `Pool(· | region)`
denotes a region-conditioned reduction, not conditioning on oracle returns.
`target_box` is actor-observed target geometry. Computational spellings must be
scientifically reviewed; the linter enforces form and source identity only.

## A — Candidate-wise scorer

Owners: `vin/models/target_finite_horizon.py`, `vin/modules/qh_state_fusion.py`,
`vin/modules/qh_value_decoders.py` under `aria_nbv/aria_nbv/`; shared
`equations/model.typ` and `equations/rl.typ` at the pinned revision.
Placement: Method overview / selected interaction.

**Caption:** Root/current-relative candidate poses and root evidence produce a
physical token through pose encoding, concatenation and a linear–GELU–LayerNorm
projection. Feasibility branches from that token before target conditioning.
The value query adds candidate-from-target geometry. A1 reads shared scene,
target, causal pose-history, budget and horizon tokens. Query, attended context
and their elementwise product feed direct regression. The hard action mask acts
only at selection. The selected experiment uses privileged target geometry and
oracle-derived action support; the figure does not assert deployability.

The context block abbreviates the individual token projection layers, which
remain in the implementation. History/budget/horizon symbols below its operation
identify conditioning inputs, not a claim that raw scalars are concatenated
without embedding. The descriptor label denotes target geometry available under
the selected protocol; appearance and association uncertainty are not implemented
inputs to this baseline. Dropout is training-only. Padding and losses are omitted.

## B — Ideal value and state construction

Owners: `04-method/04-05-finite-candidate-value-model.typ` and shared
`equations/rl.typ`: `q_h`, `qh_representation_map`, `qh_learned_predictor`,
`qh_sufficiency_factorization`. Placement: before carrier comparisons.

**Caption:** Optimal value is a supremum over admitted continuations, conditioned
on actor history and the first action. The model instead observes a compressed
representation, constructed by the displayed canonical map. Aliased histories
must have the same joint law of reward, successor representation, residual
budget, regenerated candidates, hard mask and termination for each physical
action, with target/protocol fixed, to justify the stated sufficient condition
for Bellman closure. A counterexample shows harmful aliasing. Finite predictive
tests challenge but do not prove universal sufficiency.

The full horizon, target and protocol conditioning of the optimal-value
computation remains in `q_h`. This is not behavior-return regression. A trained
Huber predictor is not automatically a conditional mean. Dashed status boxes
are logical outcomes, not data modalities or implemented testing algorithms.

## C — Oracle labels and a factual successor

Owners: `04-method/04-03-candidate-and-replay-contract.typ`,
`rollouts/replay/engine.py`, `lightning/qh_module.py`, and shared
`equations/rl.typ`: `target_root_gain_reward`, `replay_transition`,
`qh_doubleq_index`, `qh_doubleq_target`. Placement: causal replay / learning.

**Caption:** Oracle rendering/backprojection and target error measurement label
all evaluable hard-valid current candidates. Gathering the selected row gives
the reward. Current S0 replay changes pose, selected-pose prefix, budget and
candidate table, not actor RGB or EVL. Double-Q continuation uses the successor's
supported candidates and terminal convention; the resulting training target is
shown as a canonical equation. Selected-depth fusion is a separate privileged
S1 control. Unselected depth has no actor-state update path.

The policy block abbreviates state/candidate scoring and hard-mask selection,
which are expanded in A. The S1 point encoder, mean/max pooling, support features
and zero-initialized residual are owned by `model.qh_s1_selected_surface` and
`vin/modules/qh_scene_encoders.py`. Support features and initialization are not
pictured. Exact Q2 requires **successor** one-step gains, not the current labels.

## D — Shared memory, then symbolic readouts

Owners: `04-method/04-01-scene-representation-requirements.typ`, shared
`symbols/scene.typ` and `equations/scene.typ`: `qh_scene_memory`,
`candidate_query_pools`, `candidate_ray_query`.
Placement: actor-state requirements after local EVL's support limit.

**Caption:** In this proposed actor-visible state, local EVL and causal ray memory
contribute to shared evidence. Target-, frustum- and intersection-conditioned
pooling produces three distinct feature summaries; a ray query produces a
candidate-specific geometric descriptor. These are read-only operations, not
updates driven by hypothetical observations. Unknown and observed-free space
remain distinct. S0 and privileged S1 are independent controls, not additive
inputs to this proposed architecture.

The source-bound calls expose the computations without declaring the hybrid
carrier optimal or implemented. The dotted enclosing border and caption preserve
that scientific status independently of color.

## Verification and integration

The skill now requires a mathematical body for every data node and an equation
or source-bound computation for every processing node. The two terminal outcomes
in B are explicit `status` nodes. No ordinary architecture box is exempt.

Run exact-label and architecture-coverage checks with the proper projection, then
render and inspect color/grayscale at the declared physical width. Hosted CI
checks code text sizes as well as titles/math and exports QA JSON and previews.
A Mermaid Chart response is a preview widget, not a render-validation receipt.
Final captions/includes and PDF legibility still require destination-page QA.
Raw browser SVGs can require KaTeX CSS/fonts; PNG previews are self-contained.
