---
id: 2026-08-20_rollout_plot_axis_context
date: 2026-08-20
title: "Rollout Plot Axis Controls And Interpretation Context"
status: done
topics: [streamlit, rollout-inspection, reconstruction, visualization]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/app/panels/common.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py
  - aria_nbv/aria_nbv/app/panels/counterfactual_rollouts.py
---

## Task

Give reconstruction-quality-over-time figures independent logarithmic y-axis
controls and require sufficient interpretation context beside each plot.

## Result

The stored population trajectory, stored raw-rollout trajectory, live selected
return, live valid-candidate band, and live top-k headroom plots each have an
independently keyed linear/log control. Linear remains the default. The shared
axis helper copies figures before changing layout and discloses that logarithmic
axes hide zero and negative values.

Every Rollout Supervision Plotly chart now crosses the single scientific plot
renderer and therefore carries question, population, metric, denominator,
comparison, expected-pattern, failure-mode, evidence-role, and source context.
The affected live plots similarly cross one wrapper that always renders their
existing info popover plus axis-scale semantics.

## Verification

Focused Streamlit and stored-rollout laziness suites passed. Ruff format/check,
module compilation, and `git diff --check` passed in the shared ARIA environment.
Graphify remained unusable because its projection revision was not an ancestor
of the branch, so exact source and tests remained authoritative.
