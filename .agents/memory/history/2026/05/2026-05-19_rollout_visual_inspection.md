---
id: 2026-05-19_rollout_visual_inspection
date: 2026-05-19
title: "Rollout Visual Inspection"
status: done
topics: [rollouts, streamlit, rerun, target-selection, qa]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - aria_nbv/aria_nbv/app/panels/stored_rollouts.py
  - aria_nbv/aria_nbv/app/panels/candidates.py
  - aria_nbv/aria_nbv/app/panels/counterfactual_rollouts.py
  - aria_nbv/aria_nbv/app/panels/target_audit.py
  - aria_nbv/aria_nbv/rerun_inspector/_rollout_zarr.py
---

Implemented the hybrid rollout/candidate inspection workflow requested on 2026-05-19.

The rollout side now has read-only inspection helpers that join `candidates/`,
`candidate_diagnostics/`, target rows, and rollout/source dictionaries into
Streamlit-ready rows. The stored rollout panel exposes validity waterfalls,
target audit tables, candidate grouping summaries, geometry/label histograms,
and suspicious-row queries with direct Rerun commands.

The live candidate and rollout panels gained target-selection score audit
tables, current candidate-family vocabulary, target-root-gain coloring, fanout
diagnostics by position family and invalid reason, and target/context overlays
for actor-visible target points. Rerun rollout replay logs candidate metadata,
family/reason grouped center layers, and scalar tracks for valid count,
invalid fraction, selected position id, selected target RRI, and selected
target root gain.

Verification:

- `cd aria_nbv && uv run ruff check aria_nbv/app aria_nbv/rollouts aria_nbv/rerun_inspector aria_nbv/pose_generation tests/rollouts/test_inspection.py tests/rollouts/test_zarr_store.py tests/rerun_inspector/test_rollout_zarr_logger.py tests/app/panels/test_counterfactual_rollouts_panel.py tests/app/panels/test_candidates_panel.py`
- `cd aria_nbv && uv run pytest tests/rollouts tests/rerun_inspector/test_rollout_zarr_logger.py tests/app/panels/test_counterfactual_rollouts_panel.py tests/app/panels/test_candidates_panel.py tests/data_handling/test_target_selection.py tests/pose_generation/test_counterfactuals.py -q`

Canonical state impact: no durable thesis direction changed; this is an
inspection/debugging implementation layer over existing rollout and target
contracts.
