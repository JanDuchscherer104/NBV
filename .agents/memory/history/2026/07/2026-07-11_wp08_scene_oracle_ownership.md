---
id: 2026-07-11_wp08_scene_oracle_ownership
date: 2026-07-11
title: "WP08 Scene Oracle Ownership"
status: done
topics: [oracle, rri-metrics, rollouts, scene-rri]
confidence: high
canonical_updates_needed: []
---

## Outcome

- Moved privileged root evaluation point-cloud preparation from `rri_metrics`
  to `oracle.evidence` and colocated target OBB evidence resolution there.
- Moved prepared point-mesh RRI orchestration to private `oracle._scoring`,
  delegating point-mesh primitives and the RRI formula to `rri_metrics`.
- Extracted `SceneRriScorer` and `SceneRriScorerConfig` from rollout replay.
- Added rollout-neutral `SceneRriState` and `SceneRriEvaluation` contracts;
  rollout replay adapts the Oracle result into its persisted evaluation DTO.
- Removed scene scorer exports from `aria_nbv.rollouts` and kept the serialized
  nested config field name `oracle` unchanged.
- Updated package ownership matrices, API navigation, glossary links, and
  architecture diagrams without compatibility modules.
- Reduced production Python by one line relative to the WP08 starting commit;
  the larger duplicate-scorer reduction remains WP09.

## Verification

- Ruff passed on all touched Python files.
- 272 Oracle, RRI, rollout, Streamlit-panel, integration, and data-contract
  tests passed; one optional integration test was skipped.
- The canonical rollout smoke TOML completed the retained CLI dry-run.
- Graphify shows `rollouts.counterfactuals -> oracle.scene_rri ->
  rri_metrics.returns`; scorer modules under `oracle` do not import rollout
  replay or persistence contracts.
- Mermaid sources rendered successfully and the updated Oracle-RRI figure was
  visually inspected.

## Remaining Work

- WP09 extracts target scoring from `rollouts.target_counterfactuals` and
  reuses the prepared scorer/evidence boundary established here.
- WP10-WP12 still own replay contraction, split label/evidence aggregation,
  and final pipeline relocation.
