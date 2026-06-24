---
id: 2026-06-22_multistep_qh_architecture_thesis_refinement
date: 2026-06-22
title: "Multi-Step Q_H Architecture Thesis Refinement"
status: done
topics: [thesis, q_h, efm3d, rollouts, architecture]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/typst/thesis/sections/04-method/index.typ
  - docs/references.bib
artifacts:
  - .omx/goals/autoresearch/aria-nbv-geometrically-elegant-multi-step-q-h-ar/mission.json
  - .omx/goals/autoresearch/aria-nbv-geometrically-elegant-multi-step-q-h-ar/rubric.md
  - docs/typst/thesis/main.pdf
  - .omx/goals/autoresearch/aria-nbv-geometrically-elegant-multi-step-q-h-ar/artifacts/thesis-method-page-37.png
  - .omx/goals/autoresearch/aria-nbv-geometrically-elegant-multi-step-q-h-ar/artifacts/thesis-method-page-45.png
  - .omx/goals/autoresearch/aria-nbv-geometrically-elegant-multi-step-q-h-ar/artifacts/thesis-method-page-51.png
  - .omx/goals/autoresearch/aria-nbv-geometrically-elegant-multi-step-q-h-ar/artifacts/thesis-method-page-53.png
assumptions:
  - The method chapter is the thesis-facing owner for the architecture narrative; Quarto theory pages remain supporting background.
---

## Task

Refined the thesis method architecture for the multi-step finite-candidate
`Q_H` model using repo-local code, KG routing, existing thesis/Quarto theory,
and external primary literature.

## Method

Updated `docs/typst/thesis/sections/04-method/index.typ` in bounded iterations:
scene/support encoding, target descriptors, token ownership, and residual
finite-candidate value architecture. Added Typst comments with concrete
source-file/line pointers for the repo evidence behind the prose, and added
new bibliography entries to `docs/references.bib` for object-centric view
planning and geometric transformer context.

## Findings

The main architecture correction is that EVL should be described as local
actor-visible target/support evidence, not as complete long-horizon scene
memory. The broader scene state should come from semidense/fused point support,
selected successor geometry, directional memory, and later compressed
DINO-on-point features once cache/writer/reader support exists.

The value-model correction is to avoid a monolithic transformer as the first
thesis architecture. The thesis now frames the clean first model as a calibrated
one-step target utility field plus a masked zero-mean residual set correction.
This preserves the physical scale of immediate target gain while allowing
DeepSets, masked Set Transformer, and relative-geometry modules to explain
context-dependent advantage, redundancy, and finite-horizon effects.

The method chapter now flags an explicit inconsistency to resolve before the
first `Q_H` training run: outside-EVL extent is sometimes described as hard
invalidity, while current VIN evidence treats low EVL coverage as diagnostic
support. The intended rule is that infeasible poses, missing evaluation samples,
and empty target crops are hard invalid; low local EVL support alone is a model
feature unless it blocks evaluation.

## Verification

- `cd docs && typst compile typst/thesis/main.typ --root .`
- `git diff --check -- docs/typst/thesis/sections/04-method/index.typ docs/references.bib .agents/memory/history/2026/06/2026-06-22_multistep_qh_architecture_thesis_refinement.md`
- Rendered affected PDF pages 37, 45, 51, and 53 with `pdftoppm` and inspected
  the support equation, EVL ambiguity TODO, token-ownership table, and
  architecture critique table.

## Canonical State Impact

No state file update is required. The durable thesis-facing architecture
clarification lives in the method chapter; the unresolved EVL invalidity
ambiguity is intentionally left as a visible thesis validation TODO.
