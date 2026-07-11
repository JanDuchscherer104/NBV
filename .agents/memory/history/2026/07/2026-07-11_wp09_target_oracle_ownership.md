---
id: 2026-07-11_wp09_target_oracle_ownership
date: 2026-07-11
title: "WP09 Target Oracle Ownership"
status: done
topics: [oracle, rollouts, target-rri, invalidity]
confidence: high
canonical_updates_needed: []
---

## Outcome

- Moved target-specific RRI scoring from `rollouts.target_counterfactuals` to
  `oracle.target_rri` without a compatibility module.
- Added a shared private Oracle engine for candidate depth rendering,
  backprojection, root-evidence caching, history fusion, and prepared RRI
  scoring; scene and target facades both use it.
- Moved target OBB crop preparation into `oracle.evidence` and represented
  expected evidence failures with stable semantic reason values.
- Added rollout-neutral target evaluation and invalidity results. Existing
  replay adapts evaluations to its current DTO and temporarily converts typed
  invalidity to replay control flow until WP10 introduces the minimal replay
  contract.
- Removed target scorer exports from `aria_nbv.rollouts`; the `aria_nbv.oracle`
  root exports only scene/target scorer classes and configs.
- Preserved canonical TOML field names, CLI command names, rollout Zarr arrays,
  and persisted numeric reason codecs.

## Verification

- Ruff and Python compilation passed on every touched Python file.
- 300 Oracle, RRI, rollout, Streamlit-panel, integration, data-contract, and
  configuration tests passed; one optional real-data test was skipped.
- Independent review identified and the follow-up fixed four expected ASE
  root-evidence failures that still used plain exceptions. Missing depth,
  malformed depth shape, empty observed prefixes, and empty reconstructed root
  points now carry stable typed reasons through scorer and writer skip paths.
- The canonical smoke TOML completed the rollout CLI dry-run.
- Quartodoc generated `oracle.target_rri` and removed the obsolete
  `rollouts.target_counterfactuals` navigation entry.
- Graphify shows replay importing the Oracle facade and the facade importing
  the shared scoring engine; Oracle scorer/evidence modules do not import
  rollout contracts.
- The complete ownership branch is 541 production Python lines below its
  baseline. WP09 itself adds 136 production lines for the explicit neutral
  result and invalidity boundaries.

## Remaining Work

- WP10 replaces the transitional replay invalidity exception and broad
  counterfactual DTOs with the minimal replay contract and one policy spec.
- WP11 splits candidate labels from retained heavy evidence.
- WP12 completes generation-pipeline ownership and removes the old top-level
  pipeline package.
