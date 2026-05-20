---
id: 2026-05-20_target_first_rri_rollout_alignment
date: 2026-05-20
title: "Target-First RRI Rollout Alignment"
status: done
topics: [rri, rollouts, target-selection, candidate-generation, docs, agents-db]
confidence: high
canonical_updates_needed:
  - .agents/memory/state/DECISIONS.md
files_touched:
  - aria_nbv/aria_nbv/data_handling/_target_selection.py
  - aria_nbv/aria_nbv/pose_generation/candidate_mixture.py
  - aria_nbv/aria_nbv/rollouts/zarr_store.py
  - aria_nbv/aria_nbv/rollouts/dataset_writer.py
  - docs/contents/theory/rri_theory.qmd
  - docs/contents/theory/candidate_sampling_target_selection.qmd
  - docs/contents/theory/rl_planning.qmd
  - docs/typst/thesis/advisor_distillation.typ
  - .agents/issues.toml
  - .agents/todos.toml
---

## Task

Implement the 2026-05-20 target-first RRI and rollout alignment plan. The core thesis contract is now target-first, finite-candidate, H>1 canonical rollouts. Seminar scene-level RRI remains historical evidence and scene RRI is diagnostic, not the training reward.

## Method

Updated public theory and advisor-facing docs first, then aligned code around the locked contract. The target selector now uses clipped projected visible area and geometry/class-only GT match scoring after eligibility. The rollout store schema is now `1.0-target-rollout-core`, hot candidate and q_h tables carry `position_id`, target-eval crop point payloads are disabled by default and marked sampled/audit when enabled, selected depth is labeled as `selected_successor_state_history`, and seed-once lineage replaces the previous placeholder RNG hash. The default candidate mixture is now the three-family realistic profile; the previous richer five-family mix is a named ablation. The rollout writer also has a configurable low-valid-root skip gate.

## Outputs

Added `issue-032` plus `todo-080` through `todo-086` for target-first alignment, schema hardening, selector refactor, sampler simplification, scene splits, target sampling audit, and stale-doc cleanup. Existing rollout backlog text was updated so stale findings such as position_id-not-persisted, candidate-major q_h bootstrap arrays, and schema 0.7/0.9 are not treated as current truth.

## Verification

- `cd aria_nbv && uv run pytest tests/data_handling/test_target_selection.py tests/pose_generation/test_candidate_mixture.py tests/rollouts/test_zarr_store.py -q`
- `cd aria_nbv && uv run pytest tests/rollouts/test_dataset_writer.py tests/rollouts/test_inspection.py -q`
- `cd aria_nbv && uv run ruff check aria_nbv/data_handling/_target_selection.py aria_nbv/pose_generation/candidate_mixture.py aria_nbv/rollouts/dataset_writer.py aria_nbv/rollouts/zarr_store.py tests/data_handling/test_target_selection.py tests/pose_generation/test_candidate_mixture.py tests/rollouts/test_zarr_store.py`
- `make agents-db AGENTS_ARGS='validate' && make agents-db`
- `make qmd-frontmatter-check`
- `cd docs && quarto render contents/theory/rri_theory.qmd`
- `cd docs && quarto render contents/theory/candidate_sampling_target_selection.qmd`
- `cd docs && quarto render contents/theory/rl_planning.qmd`
- `typst compile --root docs docs/typst/thesis/advisor_distillation.typ docs/typst/thesis/advisor_distillation.pdf`

## State Impact

`.agents/memory/state/DECISIONS.md` now owns the durable 2026-05-20 decisions. No migration path was added for stale rollout stores; they should be regenerated under schema `1.0-target-rollout-core`.
