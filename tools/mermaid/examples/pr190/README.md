# Mathematical replacements for the PR190 review diagrams

These are source-only review candidates, not active thesis includes. Every
formula in `.mmd` is a direct `#symb` or `#eqs` reference, resolved from this
branch's generated notation. The historical PR190 pin is no longer the runtime
notation source. Its accepted history/representation distinction is registered
additively in the shared RL owner; main's existing state-conditioned `q_h` is
not overwritten. No model behavior or thesis chapter is changed.

Generate plain Mermaid before sending it to a widget or a GitHub fence:

```sh
python3 tools/mermaid/scripts/aria_mermaid_owners.py \
  tools/mermaid/examples/pr190/scene_state_architecture.mmd \
  --output /tmp/scene.mmd --receipt /tmp/scene.refs.json
```

## A: candidate_value_scorer.mmd — selected interaction

The view is deliberately narrower than the former full-module inventory.
`x` is the supplied candidate-relative value query. The shared five-token state,
A1 cross-attention, query/context/elementwise-product fusion and masked selection
are shown as equations. Set Ak=A1 here; the aggregate owner also retains A0 as a
matched control. The output symbol is the scorer's conditional value. The generic
value notation in the selection equation denotes that same return-valued score.

**Caption:** A1 reads a shared scene/target/history/budget/horizon context for
each candidate independently. The attended context is combined with the query
and their elementwise product before value decoding. The authoritative mask acts
only at selection. Upstream geometric encoding, the physical-only feasibility
head and auxiliary losses are outside this focused interaction view; no target
information is sent to feasibility and no candidate self-attention is implied.

Owners: shared `equations/model.typ` reusable fusion rows and
`equations/rl.typ::qh_masked_argmax`; executable context is
`aria_nbv/aria_nbv/vin/modules/qh_state_fusion.py`. Do not infer upstream feature
contents from this diagram or from unrelated historical descriptor equations.

## B: value_state_sufficiency.mmd — what compression must preserve

**Caption:** The ideal optimum conditions on the full causal history and the
physical first action. The learned predictor uses a representation of that
history. At fixed target and decision protocol, sufficiency requires equality of
the conditional laws of the displayed joint decision outcome, for every admitted
history/action. The outcome includes reward, successor representation, residual
budget, regenerated candidates, hard support and termination. This equality is
a sufficient condition, not an empirical result or a guarantee that a Huber-fitted
predictor equals an expectation. Different histories alone do not demonstrate
harmful aliasing. Dashed edges denote the requirement, not runtime computation.

Owners: shared RL `qh_history_optimum`, `qh_representation_map`,
`qh_decision_outcome`, `qh_decision_sufficiency`, and corresponding symbols.
The history optimum is separate from main's existing state-conditioned `q_h`.

## C: factual_counterfactual_replay.mmd — the actual recursive target

**Caption:** A selected pose-only transition updates pose, prefix, remaining
budget and candidate set. It does not acquire actor RGB or refresh EVL. The
selected reward is measured by the privileged oracle. Successor support
intersects physical admissibility with horizon-specific value-label support.
Double-Q selects with the online network and evaluates with the delayed network;
its bootstrap is zero at horizon one, termination or empty support. The target
adds this continuation to the immediate root-normalized gain. Dense labels at
the current state are not successor values; exact Q2 requires successor Q1 gains.
Only selected depth may enter a separately labelled privileged surface control.

Owners: shared RL transition, reward, supported-successor, Double-Q and target
equations; `rollouts/replay/engine.py` and `lightning/qh_module.py` for execution.
The restored piecewise projection retains all conditions of the Typst body.

## D: scene_state_architecture.mmd — sets and rays, not an inventory

**Caption:** Proposed actor-visible memory, not an implemented carrier. The
state tuple makes its modalities explicit. The three spatial pools read target
support, candidate-frustum support and their intersection. The ray query returns
near depth, observed-free and unknown intervals, hits, target weights, support,
geometric uncertainty and directional information. All reads are conditioned on
target/candidate geometry and leave shared memory unchanged. S0 and privileged
S1 are independent controls, not additive inputs to this proposed architecture.

Owners: shared `equations/scene.typ`. The canonical projection now preserves all
three pooling domains and the full ray-readout tuple, instead of abbreviated
English or a misleading single pooling equation.

## Publication boundary

The compiler emits ordinary Mermaid plus optional source/notation/output hashes.
The render workflow uploads those receipts and generated sources alongside
color/grayscale images and physical-size/font reports. Only generated Mermaid
belongs in preview tools and GitHub fences. Actual visual evidence is recorded
in the PR, not presumed from a successful tool response. Final thesis inclusion
requires source consistency, a caption/call site and PDF-page QA; browser SVGs
with HTML/KaTeX are not assumed portable vectors. No font files are distributed.
