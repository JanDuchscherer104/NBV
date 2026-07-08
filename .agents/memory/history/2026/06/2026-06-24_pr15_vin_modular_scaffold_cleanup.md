---
id: 2026-06-24_pr15_vin_modular_scaffold_cleanup
date: 2026-06-24
title: "PR15 VIN Modular Scaffold Cleanup"
status: done
topics: [vin, rri, lightning, scaffold, pr15]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/vin/models/scene_myopic.py
  - aria_nbv/aria_nbv/vin/models/target_myopic.py
  - aria_nbv/aria_nbv/vin/models/target_finite_horizon.py
  - aria_nbv/aria_nbv/lightning/lit_module.py
  - aria_nbv/aria_nbv/rri_metrics/__init__.py
  - aria_nbv/tests/vin/test_models_namespace.py
  - aria_nbv/tests/rri_metrics/test_public_api.py
---

## Task

Integrated the VIN modular scaffold cleanup directly on the PR15 head branch
after confirming the earlier local cleanup branch was not a descendant of
`codex/rollout-diverse-metrics-models`.

## Outputs

Renamed the current VIN scorer modules to purpose-specific names:
`scene_myopic.py`, `target_myopic.py`, and `target_finite_horizon.py`. Removed
legacy active imports of the old module paths, tightened the RRI and VIN type
root APIs, and kept legacy diagnostics available from their leaf modules.

Moved inference checkpoint loading and CORAL bin-value preparation into
`VinLightningModule.load_for_inference()` and
`VinLightningModule.prepare_for_inference()`, so app panels no longer own a
private permissive checkpoint loader or private binner setup flow.

## Verification

- `uvx ruff check ...` on the touched Python files
- `/home/jd/repos/ARIA-NBV/aria_nbv/.venv/bin/python -m py_compile ...` on the touched Python files
- `PYTHONPATH=/home/jd/repos/ARIA-NBV-packages/vin-modular-scaffold/aria_nbv /home/jd/repos/ARIA-NBV/aria_nbv/.venv/bin/python -m pytest tests/vin/test_models_namespace.py tests/vin/test_types.py tests/vin/test_coral.py tests/lightning/test_resume_checkpoint.py tests/lightning/test_vin_batch_collate.py tests/rri_metrics/test_public_api.py tests/rri_metrics/test_rollout_metrics.py tests/rri_metrics/test_torch_rollout_metrics.py tests/rri_metrics/test_eval_pointclouds.py tests/pose_generation/test_counterfactuals.py tests/app/panels/test_counterfactual_rollouts_panel.py -q`

The focused pytest set passed with 190 tests and warnings only.
