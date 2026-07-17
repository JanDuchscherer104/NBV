---
id: 2026-07-13_g009_rollout_read_model
date: 2026-07-13
title: "G009 Rollout Read Model And Root Contraction"
status: done
topics: [rollouts, read-model, streamlit, package-api, simplification]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/rollouts/read_model.py
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - aria_nbv/aria_nbv/rollouts/__init__.py
  - aria_nbv/aria_nbv/app/panels/stored_rollouts.py
artifacts:
  - .omx/plans/g008-bounded-rollout-read-model-contract-20260713.md
---

## Task

Implement the approved G008 read-model contract for Streamlit, delete duplicate
store joins and decoders, and contract `aria_nbv.rollouts` to its exact stable
eight-symbol root without changing persisted schemas or scientific formulas.

## Outcome

- Added four frozen, slotted, presentation-free persisted-store projections in
  `rollouts.read_model` and leaf-only lookup functions.
- Migrated rollout inspection and the Stored Rollouts panel to those records.
- Deleted duplicated dictionary, rollout-context, selected-candidate, entropy,
  selected-depth, and app adapter helpers.
- Reused `rollouts.audits.candidate_policy_entropy` as the sole entropy formula.
- Narrowed `rollouts.__all__` from 47 names to the approved eight names and
  migrated callers to owning leaf modules without compatibility exports.
- Preserved Zarr schema ids, arrays, dtypes, reason codes, CLI names, configs,
  checkpoint keys, and application output contracts.
- Production Python LOC changed from 67,829 at `5c4c450` to 67,729 (`-100`).

## Verification

- Ruff format/check and compileall passed for all touched Python surfaces.
- 182 rollout, Streamlit, Rerun, and configuration tests passed.
- 20 focused read-model/inspection tests passed after the final corrections;
  malformed and disabled selected-depth stores return bounded unavailable
  outcomes.
- Graphify refreshed to 5,512 nodes and 12,601 edges; G010 remains the owner of
  the independent Rerun adapter migration.
- Root-import and duplicate-helper scans passed; `git diff --check` passed.
- `make check-agent-memory` remains blocked only by `.omx` runtime files already
  tracked at the branch baseline; this work did not add or modify those files.

## Canonical State Impact

No canonical semantic state changes are required. This is a behavior-preserving
ownership and public-surface contraction; G010 should consume the same four
records while retaining Rerun-specific entities and presentation DTOs locally.
