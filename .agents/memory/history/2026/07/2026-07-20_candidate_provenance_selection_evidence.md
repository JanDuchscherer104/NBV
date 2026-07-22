---
id: 2026-07-20_candidate_provenance_selection_evidence
date: 2026-07-20
title: "Candidate Provenance and Selection Evidence Redesign"
status: done
topics: [rollouts, inspection, streamlit, candidate-selection, rri]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py
  - aria_nbv/tests/rollouts/test_inspection.py
  - aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py
---

## Task

Redesign the stored-rollout candidate provenance view so its root contains all
scoped persisted candidates, remove redundant generation stages, and add
selection-policy and target-RRI-rank evidence without migrating rollout stores.

## Method and outputs

- Replaced the mixture, position, and orientation columns with one persisted
  proposal signature that retains mixture, center, and view semantics.
- Routed actor-invalid candidates to their primary invalid reason, while
  preserving selected-invalid rows as `selection_contract_violation`.
- Extended the selected-candidate rank projection with persisted policy
  temperature, probability, entropy, score source, selection-score rank,
  target-RRI competition rank, and finite actor-valid denominator.
- Added a second selected-step Sankey plus downloadable aggregate-flow and exact
  per-step evidence tables. Target-RRI rank remains explicitly diagnostic and
  distinct from the score that governed behavior-policy sampling.

## Verification

- `uv run ruff format aria_nbv/rollouts/inspection.py aria_nbv/app/panels/_stored_rollouts_page.py tests/rollouts/test_inspection.py tests/app/panels/test_counterfactual_rollouts_panel.py`
- `uv run ruff check aria_nbv/rollouts/inspection.py aria_nbv/app/panels/_stored_rollouts_page.py tests/rollouts/test_inspection.py tests/app/panels/test_counterfactual_rollouts_panel.py`
- `uv run pytest tests/rollouts/test_inspection.py tests/app/panels/test_counterfactual_rollouts_panel.py -q` (`72 passed`)

## Canonical state impact

No rollout-store schema, generation recipe, or canonical research-direction
change was made. The change is a read-only inspection and visualization
contract over already persisted evidence.
