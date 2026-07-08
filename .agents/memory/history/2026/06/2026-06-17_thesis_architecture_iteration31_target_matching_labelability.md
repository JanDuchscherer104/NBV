---
id: 2026-06-17_thesis_architecture_iteration31_target_matching_labelability
date: 2026-06-17
title: "Thesis Architecture Iteration 31 Target Matching And Labelability"
status: done
topics: [thesis, architecture, target-selection, target-rri, labelability, obb]
confidence: high
canonical_updates_needed:
  - docs/contents/thesis/questions.qmd
  - docs/typst/thesis/sections/04-method/index.typ
  - docs/typst/thesis/sections/05-experimental-design/index.typ
  - docs/contents/theory/candidate_sampling_target_selection.qmd
  - aria_nbv/tests/data_handling/test_target_selection.py
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Summary

Iteration 31 refined the target protocol around OBS-SEL / PRED-Q / GT-EVAL. The
live selector and rollout store already enforce most of the boundary, but the
architecture should name five separate stages: actor-visible source selection,
actor-visible eligibility, actor-visible target ranking, GT-evaluation matching,
and GT-crop labeling. Support and projection belong to eligibility/ranking and
reports, not to the default GT association score.

## Evidence

- `docs/contents/thesis/questions.qmd` currently blends support/projection with
  the GT matching rule, while `docs/contents/theory/candidate_sampling_target_selection.qmd`
  separates eligibility, interest, and post-selection GT match audit.
- `aria_nbv/aria_nbv/data_handling/_target_selection.py` resolves V1 detected or
  predicted OBB sources, refuses GT-only V1 sources, computes score factors from
  confidence, projection, support, and deficit, then performs semantic-compatible
  IoU matching with ambiguity checks only after target selection.
- `aria_nbv/tests/data_handling/test_target_selection.py` covers V1 refusal of
  GT-only sources, missing projection fallback, projected visibility hard mode,
  geometry-only GT match score, duplicate predicted-to-GT ambiguity, unmatched
  GT invalidity, and V0 GT sanity mode.
- `aria_nbv/aria_nbv/pose_generation/target_counterfactuals.py` refuses
  GT-invalid rows and raises target-RRI invalidity for empty mesh crops and
  sparse current target support.
- `aria_nbv/aria_nbv/rollouts/zarr_store.py` persists target validity, invalid
  reasons, matched GT ids, match status, and GT-label-valid masks, and blocks
  `q_train` when target label validity is false.
- EFM3D and SceneScript provide matching/evaluation precedents using class,
  geometric costs, IoU, thresholds, and Hungarian-style assignment, but those are
  audit ideas rather than actor-visible target-selection inputs.

## Canonical Updates Needed

- Update thesis method wording so OBS-SOURCE, OBS-ELIG, OBS-RANK,
  GT-EVAL-MATCH, and GT-CROP-LABEL are distinct stages.
- Update `questions.qmd` to stop implying that support/projection are default
  GT association score terms; they should remain eligibility/ranking/reporting
  fields unless a concrete M3 failure motivates an extra match criterion.
- Add evaluation reports for target counts, invalid reasons, score factors,
  IoU/gap ambiguity, crop validity, paired V0/V1 audits, and visual
  actor-visible-versus-GT overlays.
- Consider adding stable target-label invalidity codes for empty mesh crops and
  sparse current target support before large-scale rollout generation.
