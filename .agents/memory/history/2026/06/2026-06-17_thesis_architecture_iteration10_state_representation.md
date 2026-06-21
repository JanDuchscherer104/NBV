---
id: 2026-06-17_thesis_architecture_iteration10_state_representation
date: 2026-06-17
title: "Thesis Architecture Iteration 10 State Representation"
status: done
topics: [thesis, literature, q-h, representation, support-memory]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/03-method.typ
  - docs/typst/thesis/sections/04-evaluation.typ
  - docs/contents/theory/efm3d_scene_embeddings.qmd
  - docs/contents/theory/candidate_view_dependence.qmd
  - docs/contents/theory/rl_planning.qmd
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Task

Continue the architecture autoresearch by critiquing actor-visible state
representation, support memory, Deja View-style recurrence, and point/sparse
backbone adoption for the planned finite-candidate `Q_H`.

## Findings

The representation decision should start from the state contract. The first
thesis-core `Q_H` consumes `s_cf0`: frozen root EVL context, fused point proxy,
selected-view history, target descriptor, budget, candidate table, validity
masks, and current candidate-query features. `s_cf+` may add selected synthetic
observations after an action is chosen. `s_oracle` holds GT meshes, GT crops,
all-candidate renders, and RRI labels only for labels/evaluation.

The safest architecture path is compact actor-visible query pools before heavy
backbones: target pool, candidate-frustum pool, target-frustum intersection
pool, support novelty, and out-of-support flags. EFM3D/EVL justifies local
gravity-aligned voxel evidence and point/free-space support; Deja View justifies
bounded recurrent refinement; Point Transformer, KPConv, PTv3, and
MinkowskiEngine justify later support encoders only after compact features fail.

Directional support memory should start with low-order target-local summaries
and stratified diagnostics, not high-order spherical/tensor machinery.

## Canonical State Impact

The autoresearch report now adds a representation ladder from R0 compact state
through actor-visible support tokens, compressed DINO/EVL caches, EVL internals,
selected-view recurrence, and point/sparse/scene backbones.

Follow-up thesis edits should state the target/frustum/intersection query-pool
contract and the escalation rule for heavier support memories. Follow-up field
audits should check whether current rollout/model records already provide the
minimum R0/R1 fields before planning compressed DINO caches or recurrence.

## Verification

- Local scans covered `docs/contents/theory/efm3d_scene_embeddings.qmd`,
  `docs/contents/theory/candidate_view_dependence.qmd`,
  `docs/contents/theory/rl_planning.qmd`, architecture work notes, and local
  Deja View, EFM3D, Point Transformer, PTv3, KPConv, and MinkowskiEngine TeX
  sources.
- `make kg-route` returned open representation questions, roadmap/questions,
  thesis seed, active TODOs, and rollout/Zarr implementation surfaces as the
  owner stack for state representation and support memory.
- Follow-up validation should rerun artifact grep, JSON parse, whitespace check,
  and `make check-agent-memory`.
