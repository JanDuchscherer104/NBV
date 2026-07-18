---
id: 2026-07-18_science_first_stored_dataset_inspector
date: 2026-07-18
title: "Science-First Stored Dataset Inspector"
status: done
topics: [streamlit, rollouts, zarr, rerun, topology, diagnostics]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/app/panels/stored_rollouts.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py
  - aria_nbv/aria_nbv/app/panels/offline_dataset.py
  - aria_nbv/aria_nbv/dataset_topology.py
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - aria_nbv/aria_nbv/app/rerun_launch.py
  - aria_nbv/aria_nbv/rerun_inspector/_config.py
  - aria_nbv/aria_nbv/rerun_inspector/_layers.py
  - aria_nbv/aria_nbv/rerun_inspector/_blueprint.py
  - aria_nbv/aria_nbv/rerun_inspector/_rollout_zarr.py
  - docs/contents/setup.qmd
artifacts:
  - /tmp/aria-nbv-rerun-smoke/stored-rollout-0.rrd
  - /tmp/aria-nbv-rerun-smoke/stored-rollout-web.rrd
---

## Task

Replace the eager ten-tab stored-rollout diagnostic dump with a science-first,
progressively disclosed inspector while preserving the immutable rollout/VIN
schema and existing deterministic reporting owner.

## Implementation

- Kept `render_stored_rollouts_panel()` as the stable public entry point and
  moved presentation into a private five-workspace page module.
- Added presentation-neutral invariant, mask-combination, matched-cohort,
  paired-bootstrap, selected-rank/regret, failure, and root-relative Z-up
  geometry projections.
- Added a shared read-only topology model that resolves rollout lineage, VIN
  manifests, source indexes, ATEK roots, meshes, derived caches, reports, and
  Rerun recordings with explicit resolution and modality roles.
- Added complete scientific explanation contracts and deterministic filtered
  CSV/JSON/evidence-bundle downloads.
- Added Rerun layer presets with separate inclusion and initial visibility,
  deterministic resolved TOML artifacts, four launch modes, captured logs,
  artifact/URL health, and stop/restart lifecycle controls.

## Verification

- Ruff format/check passed for all touched app, rollout, topology, reporting,
  Rerun, and focused test files.
- Focused inspection/reporting/topology/Rerun/AppTest suites passed; AppTests
  cover current, stale, single-policy, missing-depth, and larger-store paths.
- Headless Streamlit started successfully on `2026-07-18`.
- A compatible current rollout store produced a saved `.rrd`; loopback
  `--serve-web` became reachable and was then stopped cleanly.
- `docs/contents/setup.qmd` rendered successfully.

## Canonical State Impact

No rollout/VIN persisted schema, model input, oracle label, or training
contract changed. Public operator documentation now describes the inspector;
no additional canonical memory update is required.
