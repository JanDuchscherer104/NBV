---
id: 2026-06-24_thesis_rollout_store_data_generation_patch
date: 2026-06-24
title: "Thesis rollout store data generation patch"
status: done
topics: [thesis, typst, rollouts, q_h, data-generation]
confidence: high
canonical_updates_needed: []
---

## Task
Patched the thesis data-generation narrative so Chapter 03 explicitly owns the immutable VIN offline substrate, standalone target-conditioned rollout replay stores, diagnostic evidence slots, and the boundary between oracle labels and learned method inputs.

## Method
Used the OMX autoresearch-goal handoff/report for the current rollout-data objective, refreshed `make context`, inspected the current VIN offline and rollout store code paths, validated the live audit store with `nbv-rollouts-info`, checked `vin_offline` with `nbv-offline-info`, then patched the Typst thesis sections and shared data-layout-tree helpers.

## Findings
Added `docs/typst/thesis/sections/03-oracle-and-data-generation/03-03-replay-stores-and-diagnostics.typ` and included it from the Chapter 03 index. The new section explains why `vin_offline/` remains an immutable source substrate while `rollouts.zarr/` is a target-conditioned replay sidecar, reports audit-scale facts for `.data/offline_cache/rollouts_v1_realistic_35_train_20260621.zarr`, and lists result-chapter diagnostic plot slots already backed by Streamlit panels.

Updated `docs/typst/shared/data-layout-trees.typ` so the VIN and rollout schema trees match the current v7 VIN shard layout and schema `1.0-target-rollout-core`, while keeping figures compact enough for body text. Added short cross-references in `docs/typst/thesis/sections/04-method/04-03-candidate-and-replay-contract.typ` and `docs/typst/thesis/sections/05-experimental-design/05-02-learning-objective-and-replay-evidence.typ` so the method and experiment chapters depend on the Chapter 03 replay-store contract instead of duplicating storage details.

## Verification
Passed:

- `make context`
- `cd aria_nbv && uv run nbv-rollouts-info --store /home/jd/repos/ARIA-NBV/.data/offline_cache/rollouts_v1_realistic_35_train_20260621.zarr --validate --stats --json`
- `cd aria_nbv && uv run nbv-offline-info summary --store /home/jd/repos/ARIA-NBV/.data/offline_cache/vin_offline`
- `cd aria_nbv && uv run nbv-offline-info tree --store /home/jd/repos/ARIA-NBV/.data/offline_cache/vin_offline`
- `cd docs && typst compile typst/thesis/main.typ /tmp/aria-thesis-rollout-data.pdf --root . --input aria-wip-links=false`
- `git diff --check`
- `pdftotext -layout /tmp/aria-thesis-rollout-data.pdf - | rg ...` for new headings, figures, tables, and unresolved-reference markers
- visual QA of `/tmp/aria-thesis-pages/replay5-053.png`
- `make kg-claim-check KG_CLAIM="ARIA-NBV keeps immutable VIN offline rows as the one-step logged-source substrate and uses standalone target-conditioned rollout Zarr stores for finite-candidate selected-transition Q_H replay."`

OMX autoresearch-goal verdict was recorded as `pass` for `aria-nbv-counterfactual-rollout-generation-thesi`. The follow-up `omx autoresearch-goal complete --slug ... --codex-goal-json '{"goal":null,...}'` refused reconciliation because `get_goal` returned no active goal after the Codex goal had already been marked complete; the mission therefore remains professor-critic `passed` rather than CLI `complete`.

## Canonical State Impact
None. The patch updates thesis/public documentation surfaces only; no `.agents/memory/state/*.md` canonical-state update is needed.
