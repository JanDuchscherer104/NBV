---
id: 2026-08-21_stored_rollout_geometry_diagnostic_cleanup
date: 2026-08-21
title: "Stored rollout geometry diagnostic cleanup"
status: done
topics: [rollout-inspection, streamlit, geometry]
confidence: high
canonical_updates_needed: []
codex_thread: codex://threads/019fffa4-b85c-7db1-8404-d69c73e6485e
---

## Task
Make normalized proposal geometry easier to interpret without displaying a forest of pose frames.

## Method
Kept the presentation-free geometry projection as the scientific owner, added bounded presentation controls, and rendered compact distribution diagnostics from typed projected fields.

## Findings
`aria_nbv/aria_nbv/rollouts/inspection.py` now projects normalized proposal radius and explicit frame/camera orientation diagnostics. `aria_nbv/aria_nbv/app/panels/_stored_rollouts/candidate_generation.py` hides pose triads by default, permits one-frame or bounded all-frame overlays, and adds plot-first radius and orientation summaries with collapsed raw rows.

## Verification
Focused inspection tests passed 52/52. Focused Streamlit geometry, cache, and panel tests passed 109/109. Ruff format/check and `git diff --check` passed; changed modules compiled successfully.

## Canonical Owner Impact
The inspection projection and stored-rollout panel are the updated canonical Python owners. No schema, campaign-generation, dependency, or training contract changed.
