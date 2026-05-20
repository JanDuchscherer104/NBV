# Review Questions For Next Plan-Grill

Use this checklist after external review of the plan pack.

## Invalidity

1. Do we accept the all-reasons bitset plus primary-reason contract?
2. What priority order should choose the primary invalid reason?
3. Which diagnostic masks are hard invalidity masks and which are audit-only?

## Sampler

1. What production minimum valid-action count is defensible?
2. Should each state require at least one valid target-aware non-forward action?
3. Do we skip low-valid roots, relax realism, or run upper-bound/free-shell
   diagnostics first when target-aware families collapse?
4. What reward-signal threshold turns a flat target-root-gain probe into a hard
   blocker?

## Preflight

1. Is preflight an extension of `nbv-rollouts-info` or a new dedicated command?
2. Which checks fail production profiles versus only warn for smoke/audit runs?
3. What minimal JSON report schema should downstream LRZ campaign tooling rely
   on?

## Storage

1. Do factual row-table chunks target a byte budget, row count, or both?
2. Which manifest fields must be repeated in every shard, and which belong only
   in a campaign manifest?
3. Can disabled optional audit groups be omitted entirely, or should they remain
   as tiny marker groups for reader simplicity?

## Rollout Generation Gate

1. What is the smallest multi-scene audit subset that can justify broad
   generation?
2. Should stale local stores be deleted, renamed, or left as failed preflight
   fixtures?
3. Which results are required before LRZ generation: validation pass, sampler
   diversity pass, storage-footprint pass, reward-signal pass, scene-split
   manifest, and seed lineage?

