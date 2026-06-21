---
id: 2026-06-17_thesis_architecture_iteration28_directional_memory_ladder
date: 2026-06-17
title: "Thesis Architecture Iteration 28 Directional Memory Ladder"
status: done
topics: [thesis, architecture, directional-memory, s2, scone, fisherrf, hestia, e3nn]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/03-method.typ
  - docs/typst/thesis/sections/04-evaluation.typ
  - docs/contents/theory/candidate_view_dependence.qmd
  - docs/contents/literature/scone_fisherrf.qmd
  - docs/contents/literature/hestia.qmd
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Summary

Iteration 28 turned the directional-visibility idea into a ladder rather than a
default model choice. The recommended thesis path is to keep target-RRI as the
label and evaluation target, then add actor-visible support/novelty features:
current support diagnostics, second-moment `S^2` memory over selected views,
scalar directional novelty, Fisher-style branch-diversity diagnostics,
Hestia-style face/incidence bins, low-order SH/e3nn angular channels, and only
then learned SCONE/MACARONS-style visibility modules.

The key architecture boundary is that accumulated directional visibility is not
pose encoding. R6D/LFF and shell SH pose encoders describe candidate pose rows;
directional memory describes selected observation history around target/support
cells.

## Evidence

- SCONE predicts visibility gain from proxy points, occupancy/occlusion context,
  camera history projected onto a sphere, and spherical-harmonic visibility
  coefficients:
  `docs/literature/tex-src/arXiv-SCONE/camera_ready_2_approach.tex`.
- MACARONS modifies camera-history features so previous cameras count only when
  the point was plausibly visible, making direction history occlusion-aware:
  `docs/literature/tex-src/arXiv-MACARONS/7_appendix.tex`.
- Hestia tracks directional voxel-face visibility and uses coverage increments,
  but repo docs already scope it as a bridge/diagnostic rather than a target-RRI
  replacement:
  `docs/contents/literature/hestia.qmd`.
- FisherRF supports diminishing-return information channels and greedy batch
  selection, useful for branch diversity and target-local uncertainty features:
  `docs/literature/tex-src/arXiv-FisherRF/sec/method.tex`.
- Local theory already defines candidate token slots for `phi_dir`, second-moment
  `M_dir(v)`, and directional novelty `nu_i(v)`:
  `docs/contents/theory/candidate_view_dependence.qmd`.
- Implementation comments explicitly separate `S^2` candidate direction sampling
  and R6D/SH pose encodings from accumulated target visibility memory:
  `aria_nbv/aria_nbv/pose_generation/types.py`,
  `aria_nbv/aria_nbv/vin/model_v3.py`,
  `aria_nbv/aria_nbv/vin/experimental/spherical_encoding.py`, and
  `aria_nbv/aria_nbv/vin/experimental/pose_encoders.py`.

## Canonical Updates Needed

- Add thesis method text for a D0-D6 directional-memory ladder: current support
  diagnostics, second-moment `S^2` memory, scalar novelty, Fisher branch
  diversity, face/incidence bins, SH/e3nn channels, and learned visibility
  modules.
- Define the first artifact schema for actor-visible target/support cells,
  `M_dir`, `u_vis`, `u_info`, `u_dir`, candidate-family support bins,
  branch-overlap reports, selected-view provenance, and SH settings.
- Add evaluation tests for paired `S^2` rotation, source dropout, support-only
  versus support+direction ablations, branch-overlap reduction, and target-RRI
  correlation/top-k oracle hit.
- Keep SCONE, MACARONS, Hestia, and FisherRF as support/diagnostic inspirations
  until their auxiliary channels improve target-RRI ranking or finite-horizon
  endpoint target quality.
