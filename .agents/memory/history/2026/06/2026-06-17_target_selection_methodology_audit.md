---
id: 2026-06-17_target_selection_methodology_audit
date: 2026-06-17
title: Target Selection Methodology Audit
owner: codex
status: done
scope: target selection methodology
topics:
  - target-selection
  - rri
  - rollouts
  - litkg
  - methodology
confidence: high
canonical_updates_needed:
  - docs/contents/thesis/questions.qmd
  - .configs/build_rollouts_v1_realistic.toml
  - docs/contents/theory/candidate_sampling_target_selection.qmd
---

# Target Selection Methodology Audit

## What Changed

- Created `.agents/work/target-selection-methodology/current-target-selection-audit-2026-06-17.md`.
- No package code, public docs, backlog, or canonical memory source files were changed.

## Evidence

- Used `agent-behavior`, `aria-litkg-memory`, and `entity-aware-rri` guidance.
- Created and handed off OMX autoresearch-goal slug
  `aria-nbv-current-target-selection-methodology-au`.
- Confirmed `make kg-status` returns `kg-status: ok`.
- Ran `kg-search`, `kg-route`, and `kg-claim-check`; claim-check returned a
  heuristic `contradicted` verdict while citing a span that actually states the
  same V0/V1 separation, so the audit relied on inspected docs/code.
- Inspected current thesis docs, target-selection theory, canonical project
  state/decisions, `_target_selection.py`, rollout writer/Zarr code, production
  rollout config, target-selection tests, and existing rollout probe stores.
- Ran targeted tests:
  `cd aria_nbv && uv run pytest tests/data_handling/test_target_selection.py tests/rollouts/test_zarr_store.py tests/rollouts/test_dataset_writer.py`
  -> `55 passed, 1 warning in 19.70s`.

## Findings

- V1 target selector/source boundary is implemented: detected OBBs first,
  EVL/backbone predicted OBBs next, GT refused except V0 sanity mode or
  post-selection GT label/eval matching.
- Rollout writer consumes `ActorVisibleTargetSelector`, skips no-target and
  label-invalid cases when configured, and persists target lineage and
  invalidity fields in standalone rollout Zarr.
- Existing rollout probe stores show selected, label-valid targets with
  `target_projected_area_pixels == 0.0` because production defaults allow
  missing projection when 3D support passes.
- Existing rollout probe stores also show selected targets with
  `target_selection_score == 0.0` when support saturation drives
  `deficit_score` to zero.
- Thesis prose and code are slightly misaligned on matching score semantics:
  docs describe a broader compact matching score, while code uses geometry-only
  3D IoU after eligibility.

## Verification Gaps

- Did not generate a fresh real-data rollout; inspected existing probe stores
  instead because they already expose the target-selection edge cases.
- Did not validate `.agents` backlog with `make agents-db`; KG route flagged
  dirty `.agents` backlog, so backlog entries were treated as context only.
