# PR190 diagram replacements — review candidates

These four `.mmd` sources supersede the diagram proposals in review
[5100419765](https://github.com/JanDuchscherer104/ARIA-NBV/pull/190#pullrequestreview-5100419765).
They are deliberately **not included in the thesis**. Their scientific and
notation baseline is PR190 commit `b420d20cc01aa76451d002811f850bc87869b525`,
not an assertion that those changes have merged to main. The workflow reads that
immutable `docs/notation.yml` without executing any code from the snapshot.
Before inclusion, revalidate against the destination branch and remove the
historical pin if that branch has become the canonical owner.

## A — Candidate-wise scorer

Owner: `aria_nbv/aria_nbv/vin/models/target_finite_horizon.py`,
`vin/modules/qh_state_fusion.py`, and shared `equations/model.typ` at the above
revision. Intended placement: Method overview / selected interaction.

**Caption:** Each candidate is projected from root/current-relative geometry
and root scene evidence. The physical token branches to the auxiliary feasibility
head **before** target-relative conditioning. A1 reads five shared tokens: scene,
target, causal H0 pose history, normalized remaining budget and requested horizon.
The decoder receives query, attended context and their elementwise product.
The hard action mask is applied after raw value prediction. Target geometry and
action support in the selected experiment are privileged; this figure does not
claim a deployable actor. Padding and auxiliary training losses are omitted.

Repairs: no target-conditioned row feeds feasibility; A1 is not falsely equated
to its downstream concatenated token; no candidate-to-candidate interaction is
implied; symbols name data and operations remain short text where no registered
operator exists. Shared context is not a claim of observation-updated memory.

## B — Ideal value and compression

Owner: `04-method/04-05-finite-candidate-value-model.typ`, shared
`equations/rl.typ` (`q_h`, `qh_representation_map`,
`qh_sufficiency_factorization`). Intended placement: before carrier comparisons.

**Caption:** The ideal object is the optimal history-conditioned value over
admitted continuations under a frozen decision protocol. The learned function
receives a compressed representation of that history. Decision-context sufficiency
requires that aliased histories induce the same joint law of reward, successor
representation, residual budget, regenerated candidates, hard support and
termination, for each physical action (with target and protocol fixed).
That condition is sufficient for Bellman closure; a counterexample demonstrates
harmful aliasing. Finite empirical tests can challenge but do not prove universal
sufficiency. Huber-fitted predictions are not automatically conditional means.

Repairs: preserves optimal rather than behavior-policy value; avoids an
unconditional abbreviated Bellman identity; different histories alone are not
mislabelled as harmful aliasing. The full law stays in the canonical equation
and caption instead of a diagram-wide formula.

## C — Dense labels, one successor

Owner: `04-method/04-03-candidate-and-replay-contract.typ`,
`rollouts/replay/engine.py`, `lightning/qh_module.py` and shared
`equations/rl.typ` (`replay_transition`, `qh_doubleq_target`).
Intended placement: causal replay / finite-horizon supervision.

**Caption:** Oracle evaluation may label all evaluable hard-valid candidates
at the current state. One selected row provides the reward and factual successor
link for learning. The current S0 transition updates pose, pose prefix, budget
and candidate table; it does not acquire actor RGB or refresh EVL. Only selected
depth can enter a separate privileged surface control; actor-visible observation
fusion is a target requirement. Unselected renders have no update path. Double-Q
backup uses the successor's support, continuation values and terminal convention.
Exact Q2 uses dense **successor** one-step gains, not the current dense labels.

Repairs: no fabricated S0 sensor transition; selected-depth gating is explicit;
no false current-label-to-exact-Q2 edge; no shortened single-network maximum
standing in for the selected Double-Q estimator.

## D — Shared memory before candidate reads

Owner: `04-method/04-01-scene-representation-requirements.typ`, shared
`symbols/scene.typ` and `equations/scene.typ`. Intended placement: actor-state
requirements, after explaining finite-support local EVL.

**Caption:** This is a proposed actor-visible representation, not an implemented
model. Local EVL and causal ray memory contribute to shared spatial evidence.
An observed target and candidate pose query that evidence to obtain target,
frustum, target–frustum and ray descriptors. Candidate-conditioned readouts do
not feed back into the shared state. S0 and privileged S1 remain separate
executable controls; they are not extra additive inputs to the proposed model.
Unknown and observed-free space must remain distinct in the memory.

Repairs: fixes the direction of shared-memory/readout dependence; distinguishes
controls from compositional components; labels the proposed architecture
explicitly in words and dashed borders, independently of color.

## Verification and integration

Use the exact-label checker with the pinned projection and the repository
renderer. `Symbolic Mermaid figures` CI exports color/grayscale PNGs, browser
SVGs and physical-size/font/bounds reports. A Mermaid Chart tool response is a
preview widget, not server-side render validation. Actual artifact inspection
is recorded in the PR, not fabricated here. Final thesis integration needs a
caption, figure call site and PDF check. Browser SVG foreignObjects are not
assumed portable to Typst; use a verified PDF/PNG export or native realization.
