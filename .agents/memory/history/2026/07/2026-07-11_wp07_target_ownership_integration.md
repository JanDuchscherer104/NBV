---
id: 2026-07-11_wp07_target_ownership_integration
date: 2026-07-11
title: "WP07 Target Ownership Integration"
status: done
topics: [target-ownership, oracle, data-handling, rollouts]
confidence: high
canonical_updates_needed: []
---

## Outcome

- Joined the separately authored WP07a-WP07c commits after WP05-WP06.
- Fixed the retained rollout CLI to read the Oracle task-sampler cap.
- Removed privileged target identity from `TargetDescriptor`; its diagnostic id
  is derived only from sanitized descriptor fields.
- Composed `TargetDescriptor` inside `OracleTargetTaskRow`; privileged task
  fields no longer duplicate semantic and geometric descriptor state.
- Rejected non-finite descriptor geometry.
- Contracted `OracleTargetTaskSamplerConfig` to policy, seed, and maximum target
  count; removed VIN EVL/support/projection coupling and retained frozen zero
  sentinels for those persisted audit columns.
- Updated package matrices, guidance, public theory status, and Streamlit help
  text to distinguish current Oracle tasks from deferred actor selection.
- Regenerated the public rollout-generation SVG from its corrected Mermaid
  source.

## Verification

- Ruff passed for all integration-touched Python files.
- 158 target, Oracle, data API, pose-generation, rollout, app-panel, and config
  tests passed.
- The canonical smoke TOML completed `nbv-build-rollouts --dry-run` through the
  current `aria_nbv.oracle.pipelines.cli` entrypoint.
- Oracle/targets README symbol matrices reconcile with direct top-level AST
  definitions.

## Remaining Work

- WP08 extracts scene scoring and remaining evidence from metric/rollout owners.
- The deferred actor-visible selector remains design-only until implemented
  against observed evidence.
