---
id: 2026-06-17_thesis_architecture_iteration13_frame_invariance
date: 2026-06-17
title: "Thesis Architecture Iteration 13 Frame Invariance"
status: done
topics: [thesis, architecture, geometry, invariance, q-h]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/03-method.typ
  - docs/typst/thesis/sections/04-evaluation.typ
  - docs/contents/theory/candidate_view_dependence.qmd
  - docs/contents/theory/candidate_sampling_target_selection.qmd
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Task

Continue architecture autoresearch by refining geometric invariance,
coordinate-frame, and relative-encoding requirements for candidate-query `Q_H`.

## Findings

ARIA-NBV should not use full SE(3) equivariance as a blanket design goal. The
architecture has three regimes: candidate rows require permutation equivariance;
candidate, target, and history geometry should be expressed in local/root/target
frames; gravity, egocentric heading, observed support, and target bearing remain
semantic and should not be erased by full rotation invariance.

QCNet/QCNeXt transfers as query-centric relative encoding: each candidate token
can serve as a query whose relationships to other candidates, selected history,
and target support are encoded in local coordinates. Geometric Deep Learning,
SE(3)-Transformer, and EGNN motivate symmetry tests and possible ablations, but
Point Transformer, KPConv, PTv3, MinkowskiEngine, and exact equivariant
backbones should follow compact descriptor failures rather than precede them.

## Canonical State Impact

The autoresearch report now defines a frame-aware invariance contract:
permutation symmetry is exact for candidate rows, global pose is canonicalized
through relative descriptors, gravity and egocentric target semantics are
preserved, and heavier point/sparse/equivariant backbones are ablations gated by
measured failures.

Follow-up implementation/tests should cover row-shuffle equivariance, duplicate
stability, mask isolation, global translation consistency, yaw-frame
consistency, CW90/display isolation, depth-convention provenance, target-frame
ablation, and sampler-provenance ablation.

## Verification

- Local scans covered `docs/contents/theory/candidate_view_dependence.qmd`,
  `docs/contents/theory/candidate_sampling_target_selection.qmd`,
  `.agents/references/external_stack_contracts.md`, QCNet/QCNeXt TeX,
  Geometric Deep Learning TeX, SE(3)-Transformer TeX, EGNN TeX, Point
  Transformer/PTv3, KPConv, and MinkowskiEngine TeX.
- `make kg-route` returned canonical decisions, questions/roadmap, thesis seed,
  rollout/Zarr implementation surfaces, and active geometry/rollout backlog
  items as the owner stack.
- Follow-up validation should rerun artifact grep, JSON parse, whitespace check,
  and `make check-agent-memory`.
