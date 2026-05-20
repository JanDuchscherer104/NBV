---
id: 2026-05-19_streamlit_rollout_inspection_regressions
date: 2026-05-19
title: "Streamlit Rollout Inspection Regressions"
status: done
topics: [streamlit, rollouts, target-selection, diagnostics]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/app/panels/counterfactual_rollouts.py
  - aria_nbv/aria_nbv/app/panels/stored_rollouts.py
  - aria_nbv/aria_nbv/app/panels/target_audit.py
  - aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py
---

Diagnosed and fixed three Streamlit inspection issues reported on 2026-05-19.

The actor-visible target table showed `projected_area_px=0` because the selected
OBB source did not carry valid EFM 2D boxes (`bb2_rgb`, `bb2_slaml`,
`bb2_slamr`) for those rows. The selector therefore used the configured
missing-projection visibility fallback (`0.35`) for otherwise supported
targets. The target audit panel now surfaces that explicitly.

The live rollout dashboard crashed because target-RRI scoring produced compact
valid metric vectors while the plotting helper assumed full-shell metric
vectors aligned with `mask_valid`. `_valid_step_metric_values` now accepts both
full-shell and compact-valid vectors and still rejects unrelated mismatches.

The stored rollout panel crashed on stale stores after validation failed
because it still read current-schema `q_h` arrays. The panel now stops after
displaying validation errors and tells the operator to regenerate incompatible
rollout shards.

Verification:

- `cd aria_nbv && uv run ruff check aria_nbv/app aria_nbv/rollouts aria_nbv/data_handling tests/app/panels/test_counterfactual_rollouts_panel.py tests/rollouts tests/data_handling/test_target_selection.py`
- `cd aria_nbv && uv run pytest tests/app/panels/test_counterfactual_rollouts_panel.py tests/app/panels/test_candidates_panel.py tests/rollouts/test_inspection.py tests/rerun_inspector/test_rollout_zarr_logger.py -q`
- `cd aria_nbv && uv run pytest tests/rollouts tests/app/panels/test_counterfactual_rollouts_panel.py tests/app/panels/test_candidates_panel.py tests/data_handling/test_target_selection.py tests/pose_generation/test_counterfactuals.py -q`

Canonical state impact: no thesis contract changed; these were UI/diagnostic
guard fixes and one explicit explanation for missing projected 2D OBB boxes.
