---
id: 2026-06-17_thesis_architecture_iteration20_semantic_target_descriptors
date: 2026-06-17
title: "Thesis Architecture Iteration 20 Semantic Target Descriptors"
status: done
topics: [thesis, architecture, target-selection, semantics, q-h]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/03-method.typ
  - docs/typst/thesis/sections/04-evaluation.typ
  - docs/contents/theory/candidate_sampling_target_selection.qmd
  - docs/contents/thesis/roadmap.qmd
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Summary

Iteration 20 defines a semantic target-descriptor ladder for V1 target inputs.
The first path stays with actor-visible observed/predicted OBB geometry, class
probabilities, confidence, projected visibility, semidense support, EVL support,
and relative pose. Compact actor-visible crop descriptors are the first ablation.
Instance/object confidence is a diagnostic/support channel. SceneScript-style
structured semantics are future grounded memory, not current `Q_H` input.

## Evidence

- `.agents/memory/state/PROJECT_STATE.md` locks V0 GT OBB input as sanity or
  upper-bound only and V1 OBS-SEL / PRED-Q / GT-EVAL as the main result path.
- `.agents/memory/state/DECISIONS.md` says the first target input starts with
  observed/predicted OBB geometry plus class, confidence, projected area,
  semidense support, and EVL support.
- `docs/contents/theory/candidate_sampling_target_selection.qmd` separates
  actor-visible eligibility, target interest, and post-selection GT matching.
- `docs/contents/theory/efm3d_scene_embeddings.qmd` says EVL is local
  actor-visible target support and semidense/fused points are broader memory.
- Project Aria and EFM3D support Aria modality provenance, trajectories,
  calibration, semidense points, OBB predictions, and local EVL evidence as
  actor-visible inputs.
- Instance-NBV supports object confidence and target-focus diagnostics, while
  SceneScript supports future grounded entity/region token interfaces.

## Canonical Updates Needed

- Add the descriptor ladder to thesis method/evaluation prose.
- Audit rollout/model feature fields for target source mode, selector rank,
  actor-visible crop provenance, class/source stratification, GT-match status
  separation, and V0/V1 leakage guards.
- Keep target-invalid rows as invalid protocol cases, not low-RRI training
  samples.
