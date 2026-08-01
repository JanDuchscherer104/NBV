---
name: nbv-geometry-contracts
description: Verify ARIA-NBV pose, camera, coordinate-frame, projection, backprojection, frustum, shape, or unit changes.
---

# NBV Geometry Contracts

Use an evidence-tuple loop across the exact geometry boundary.

1. Read the package [`AGENTS.md`](../../../aria_nbv/AGENTS.md), then the nearest
   guide and typed source for the changed pose, rendering, data-view, target, or
   rollout surface. Localization is complete when both sides of the transform or
   projection are named.
2. Write down the evidence tuple required by that owner: frame convention,
   transform direction, tensor shape, and units. Source docstrings and tests
   settle executable behavior; the active thesis section settles scientific
   interpretation.
3. Follow the active branch:
   - semantic pose, frame, projection, or backprojection changes stay here;
   - target crop or target-label meaning hands off to `entity-aware-rri`;
   - Rerun entity or display output hands off to `rerun-nbv-inspector` after the
     semantic tuple is settled;
   - non-myopic candidate evaluation hands off to
     `counterfactual-rollout-planner`.
4. Run the narrowest pose-generation, rendering, or target test that proves the
   tuple. Use a visual artifact only when static evidence cannot settle the
   display branch.

Completion requires a resolved evidence tuple and focused passing proof, or the
exact unresolved owner boundary.
