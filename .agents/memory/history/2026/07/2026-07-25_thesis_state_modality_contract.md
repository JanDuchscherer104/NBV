---
id: 2026-07-25_thesis_state_modality_contract
date: 2026-07-25
title: "Thesis State Modality Contract"
status: done
topics: [thesis, modalities, actor-state, oracle, visibility]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/typst/thesis/sections/03-oracle-and-data-generation/03-01-state-and-visibility.typ
---

## Task

Strengthen Chapter 3's state and visibility section so every logged,
counterfactual, and oracle modality has an explicit conceptual role and
information boundary.

## Outcome

The section now defines a modality by data, acquisition time, frame, support,
uncertainty, and provenance. It explains RGB, calibration and pose, semi-dense
geometry, frozen EVL evidence, target context, budget, candidates, masks,
reason codes, selected depth, visibility, backprojected points, normals,
free-space rays, GT meshes and crops, all-candidate renders, annotations, and
RRI labels. It also separates visibility, feasibility, utility, and V0/V1
source roles using the shared Typst state symbols and equations.

## Verification

`cd docs && typst compile typst/thesis/main.typ /tmp/aria-thesis-state-visibility.pdf --root .`
passed. The affected Chapter 3 pages were rendered to PNG and inspected without
overflow or broken equations.
KG claim checks found canonical support but returned `unverifiable` because the
literature graph lacks paper source paths; raw KG search located the Project
Aria and EFM3D evidence pages, and the prose carries those citations directly.

## Canonical State Impact

None. The edit clarifies the existing actor/oracle and V0/V1 contracts without
changing implementation status or thesis direction.
