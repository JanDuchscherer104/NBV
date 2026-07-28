---
id: 2026-07-28_config_driven_data_generation
date: 2026-07-28
title: "Config-Driven Local Data Generation"
status: done
topics: [streamlit, generation, vin, rollouts, configs]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/app/panels/data_generation.py
  - aria_nbv/aria_nbv/oracle/pipelines/generation.py
  - aria_nbv/aria_nbv/oracle/pipelines/progress.py
  - aria_nbv/aria_nbv/oracle/pipelines/offline_vin.py
  - aria_nbv/aria_nbv/oracle/pipelines/rollout_dataset.py
  - aria_nbv/aria_nbv/configs/path_config.py
  - aria_nbv/aria_nbv/utils/config_paths.py
  - .configs/README.md
  - .configs/generation/
  - .configs/training/
  - .configs/inspection/
  - .configs/infrastructure/
  - .configs/models/
  - .configs/evidence/
---

## Task

Add a simple Streamlit surface for config-driven VIN offline and rollout
generation, preserve typed-config ownership and defaults, expose progress, and
replace the flat `.configs` directory with a navigable hierarchy.

## Outcome

- Added a thin `Data Generation` page that selects nested TOMLs, renders the
  resolved typed config read-only, performs local safety preflight, and starts
  generation only after an explicit action.
- Added an app-free synchronous generation runner under the existing oracle
  pipeline owner. Streamlit does not parse TOML or reconstruct config fields.
- Added immutable progress events to both writers without changing their
  default CLI behavior.
- Local runs fail closed for missing rollout sources, existing rollout stores,
  unconfirmed VIN replacement, configs without a finite `max_samples`, and
  rollout campaign/template profiles that remain CLI/Slurm-owned.
- Streamlit-triggered rollout stores retain the selected TOML path, source
  text, and SHA-256 in their programmatic invocation provenance.
- Reorganized configs by generation, training, inspection, infrastructure,
  model, and evidence ownership. Unique TOML basenames remain compatible via
  recursive resolution, while selectors display relative nested paths.
- Removed three proven stale, unreferenced files: the obsolete generated run
  dump, the superseded rollout microset, and the historical sweep snapshot.
  The remaining 21 TOMLs are nested; no TOML remains at `.configs` root.
- Corrected the multihorizon Oracle campaign protocol to `v0_gt_input`, which
  matches its GT target source and the current writer contract.

## Verification

- All 21 TOMLs parse; all three VIN and six rollout generation TOMLs pass the
  production CLI dry-run path.
- Ruff passed over every existing modified or new Python file.
- Strict mypy passed for the new generation runner, progress contract, page,
  and shared config-path helper. Two legacy writer/path typing findings remain
  outside this change.
- The affected application/config/generation suite passed with `211 passed`;
  the separately collected VIN diagnostics suite passed with `4 passed`.
- The headless Streamlit server started successfully.
- `git diff --check` and `make check-agent-memory` passed.
- Graphify structural refresh completed. Freshness remains nonzero while the
  dirty corpus has uncommitted changes and semantic extraction is pending.
- The QH instrumentation suite passed 9 of 10 tests; its unrelated exact LOC
  assertion expects 1834 while the current QH-owned files measure 1838.
- Independent scoped code review returned `APPROVE`; architecture review
  returned `CLEAR` after campaign-scope and config-provenance repairs.

## Canonical state impact

None. Writer semantics and persisted schemas are unchanged. `.configs/README.md`
owns the new repository-local configuration layout.
