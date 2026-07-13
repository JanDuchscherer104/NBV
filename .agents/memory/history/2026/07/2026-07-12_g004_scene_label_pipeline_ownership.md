---
id: 2026-07-12_g004_scene_label_pipeline_ownership
date: 2026-07-12
title: "G004 Scene Label Pipeline Ownership"
status: done
topics: [oracle, pipelines, scene-rri, app, ultragoal]
confidence: high
canonical_updates_needed: []
---

# G004 Scene Label Pipeline Ownership

## Scope

Moved the scene-level Oracle RRI label pipeline from the generic top-level
`pipelines` package to `oracle.pipelines` without changing label computation,
config fields, candidate generation, rendering, or RRI scoring.

## Changes

- Moved `oracle_rri_labeler.py` to `oracle/pipelines/scene_labels.py`.
- Migrated online/offline Oracle generators and Streamlit app state/config to
  the owning leaf path.
- Removed all exports from the old `aria_nbv.pipelines` package; its empty
  marker remains only for the later package-deletion gate.
- Added a contract test proving the new leaf and absence of the old module.
- Updated package ownership matrices and generated API navigation.
- Updated current context routing, backlog references, and the seminar-paper
  implementation anchor to the new owner.

Production Python LOC decreased from 67,976 to 67,966 (-10).

## Verification

- Ruff format/check, compileall, Quartodoc generation, Graphify refresh, stale
  import scans, and `git diff --check` passed.
- 69 app, Oracle, offline generation, rollout writer/CLI, and label integration
  tests passed; one real-data integration test skipped.
- `nbv-build-offline --help` passed after the move.
- Graphify proves direct `online_vin -> scene_labels` and
  `offline_vin -> scene_labels` edges.

## Canonical Updates Needed

- None. Package READMEs and API navigation now record the active owner.
