---
id: 2026-07-25_thesis_ase_efm_modality_grounding
date: 2026-07-25
title: "Thesis ASE and EFM Modality Grounding"
status: done
topics: [thesis, ASE, EFM3D, EVL, modalities, citations]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/typst/thesis/sections/03-oracle-and-data-generation/03-01-state-and-visibility.typ
---

## Task

Replace generic modality prose in the Chapter 3 state boundary with claims
grounded in the EFM3D paper, the ASE and EFM3D literature reviews, and the
repository's typed raw-view contract.

## Outcome

The section now distinguishes calibrated RGB and greyscale snippets,
trajectory/calibration/gravity, semi-dense surface and observation-ray support,
derived EVL fields and task heads, ASE ground-truth channels, and geometry-only
counterfactual successors. It records the exact EFM3D lifting, local-grid,
surface/free-mask, occupancy-supervision, and OBB-head roles with
`@EFM3D-straub2024`, and grounds ASE depth, segmentation, point observations,
OBBs, and meshes with `@ProjectAria-ASE-2025`.

Implementation statements follow
`aria_nbv/aria_nbv/data_handling/raw/views.py`: `EfmCameraView` binds images to
calibration and timestamps, `EfmPointsView` preserves uncertainty and valid
support, and `EfmSnippetView` separates actor-visible fields from GT OBBs,
nested GT data, and attached meshes.

## Verification

The full thesis compiled in development and final-link modes. Thesis pages
37--41 were rendered to PNG and inspected without overflow or broken
references. `git diff --check` passed. KG claim checking supported the
semi-dense surface/free-space statement; the image-lifting and ASE-GT checks
returned `unverifiable` because paper nodes lack source paths, so those claims
were verified directly against
`docs/literature/tex-src/arXiv-EFM3D/method.tex`,
`docs/literature/tex-src/arXiv-EFM3D/dataset.tex`,
`docs/contents/literature/efm3d.qmd`, and
`docs/contents/ase_dataset.qmd`.

## Canonical State Impact

None. The change strengthens evidence and terminology without altering the
actor/oracle protocol or implementation status.
