---
id: 2026-06-17_thesis_architecture_iteration2
date: 2026-06-17
title: "Thesis Architecture Iteration 2"
status: done
topics: [thesis, literature, architecture, q-h, geometry]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/03-method.typ
  - docs/typst/thesis/sections/02-background.typ
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Task

Continue the ongoing thesis architecture autoresearch by refining and critiquing
the planned finite-candidate `Q_H` architecture using local literature archive
evidence around QCNet, Set Transformer, Deep Sets, Deja View, and point-cloud
geometry backbones.

## Findings

The candidate value model should stay a row-equivariant set model over sampled
actions. QCNet/QCNeXt support typed query-relative pose and budget encodings,
but not motion-forecasting decoders or trajectory-distribution losses. Deep Sets
is the mandatory floor, while masked Set Transformer self-attention is the first
candidate-interaction default after calibration.

Deja View is useful only as a later tied-iteration ablation with strict trained
step-range monitoring. It should not become the default `Q_H` model and should
not be used to claim arbitrary extrapolation or fixed-point convergence.

Point Transformer, PTv3, and KPConv belong to semidense/point-attached support
feature extraction, not to the candidate table itself, unless simpler
target-local descriptors are shown to bottleneck.

## Canonical State Impact

The autoresearch artifact now contains a second architecture iteration with
design gates, an updated ablation ladder, failure monitors, and referenced-paper
follow-up leads. The active thesis can later consume this into a section on
geometric symmetries, candidate-set value modeling, and representation ablation
discipline.

## Verification

- `rg` scans over local TeX sources for QCNet/QCNeXt, Deep Sets, Set Transformer,
  Deja View, Point Transformer, PTv3, and KPConv grounded the update.
- Follow-up validation should rerun artifact grep, JSON parse, whitespace check,
  and `make check-agent-memory`.
