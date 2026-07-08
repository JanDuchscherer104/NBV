---
id: 2026-06-17_thesis_architecture_iteration14_temporal_memory
date: 2026-06-17
title: "Thesis Architecture Iteration 14 Temporal Memory"
status: done
topics: [thesis, architecture, recurrence, q-h, rollouts]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/04-method/index.typ
  - docs/typst/thesis/sections/05-experimental-design/index.typ
  - docs/contents/theory/rl_planning.qmd
  - .agents/references/rollout_zarr_q_invalidity_contract.md
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Summary

Iteration 14 adds a selected-view memory and recurrence critique to the thesis
autoresearch report. The recommended architecture keeps temporal memory in the
core plan but gates Deja View / RAFT-style recurrence behind selected-history
provenance, leakage tests, and explicit finite-horizon evaluation.

## Evidence

- `aria_nbv/aria_nbv/rl/counterfactual_env.py` currently exposes pose history,
  history masks, candidate positions, valid masks, current position, and step
  fraction in the RL observation.
- `.agents/references/rollout_zarr_q_invalidity_contract.md` defines
  `selected_depth/` as durable selected-view observation history for the first
  `Q_H` / history-encoder path, separate from all-candidate oracle scoring.
- `docs/contents/literature/scone_fisherrf.qmd` motivates directional view
  history around target/support-local points.
- Local Deja View sources motivate bounded shared-weight iterative refinement
  but also show beyond-trained-range degradation, so recurrence should remain
  an ablation until finite-horizon history contracts are proven.

## Canonical Updates Needed

- Add the memory ladder to the thesis method and evaluation chapters.
- Align rollout/Zarr metadata around the role name
  `selected_successor_state_history`.
- Add leakage tests proving `Q_H` cannot consume unselected candidate renderings
  before any recurrent history encoder is trained.
