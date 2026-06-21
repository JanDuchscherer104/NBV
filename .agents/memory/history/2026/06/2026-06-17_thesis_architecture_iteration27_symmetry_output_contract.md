---
id: 2026-06-17_thesis_architecture_iteration27_symmetry_output_contract
date: 2026-06-17
title: "Thesis Architecture Iteration 27 Symmetry Output Contract"
status: done
topics: [thesis, architecture, symmetry, equivariance, gauge, q-h, directional-memory]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/03-method.typ
  - docs/typst/thesis/sections/04-evaluation.typ
  - docs/contents/theory/candidate_view_dependence.qmd
  - docs/contents/theory/rl_planning.qmd
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Summary

Iteration 27 refined the planned geometric-learning architecture from a broad
"make it invariant/equivariant" slogan into an output-type-specific symmetry
contract. Scalar one-step and finite-horizon values should be stable to
arbitrary global frame choices for the same physical state/action, candidate row
scores should permute with candidate rows, pooled state summaries should be
candidate-order invariant, support/point pools should be point-order invariant
unless emitting point-wise outputs, and directional memory should be tested under
paired rotations on the target/support sphere.

The iteration also separates true symmetries from information-boundary rules:
selected history is temporal rather than row-exchangeable, and the actor/oracle
split is a causal evidence boundary rather than an invariance property.

## Evidence

- Geometric Deep Learning notes distinguish invariant and equivariant maps and
  describe equivariant layers followed by invariant pooling:
  `docs/literature/tex-src/arXiv-Geometric-Deep-Learning/geometricpriors.tex`.
- Deep Sets provides the set-function contract and permutation-equivariant layer
  form used to ground candidate-row and pooled-summary behavior:
  `docs/literature/tex-src/arXiv-Deep-Sets/nips_2017.tex`.
- EGNN and SE(3)-Transformer sources support treating exact E(n)/SE(3)
  equivariance as a controlled ablation with transform tests rather than a
  default scalar-value requirement:
  `docs/literature/tex-src/arXiv-EGNN/` and
  `docs/literature/tex-src/arXiv-SE3-Transformer/`.
- GDL gauge-domain notes show why mesh/tangent gauge models require local
  support and connection/parallel-transport contracts before they can be
  thesis-core architecture:
  `docs/literature/tex-src/arXiv-Geometric-Deep-Learning/geometricdomains.tex`.
- MACARONS and local S2/e3nn metadata support a directional-memory ladder that
  starts with simple selected-view sphere statistics before spherical harmonic
  feature channels:
  `docs/literature/tex-src/arXiv-MACARONS/3_method.tex` and
  `docs/literature/sources.jsonl`.
- Current ARIA VIN code already uses local relative-pose/R6D pose controls in
  the candidate-query path, so the thesis should test that frame contract before
  escalating to exact equivariant backbones:
  `aria_nbv/aria_nbv/vin/pose_encoders.py` and
  `aria_nbv/aria_nbv/vin/model_v3.py`.

## Canonical Updates Needed

- Add a thesis method subsection that maps output objects to symmetry contracts:
  scalar values, candidate-row scores, pooled state values, support/point banks,
  directional memory, selected history, and optional pose/vector outputs.
- Add evaluation tests for candidate row permutation, invalid-row firewall,
  global translation and yaw gauge changes, paired S2 directional rotations,
  selected-history ordering, exact-equivariance ablation error, and CW90 display
  isolation.
- Keep exact EGNN, SE(3)-Transformer, e3nn/spherical-harmonic, and
  gauge-equivariant variants as ablations until the output type, transform
  group, provenance, storage, and runtime contracts are explicit.
