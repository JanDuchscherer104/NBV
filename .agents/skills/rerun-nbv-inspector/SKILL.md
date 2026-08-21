---
name: rerun-nbv-inspector
description: Use for ARIA-NBV Rerun SDK integration, offline-sample or rollout-Zarr visual inspection, saved .rrd evidence, entity and sink review, camera/depth logging, blueprints, or display-frame diagnostics.
---

# Rerun NBV Inspector

Use this skill as the Rerun-specific observer and artifact-production procedure.
Package code, tests, configuration, and the module README own behavior; this
skill owns only activation, evidence routing, review order, and preferences.

## Procedure

1. Read the module README, then open the data-handling or rollout guide only for
   the selected input branch. Treat Rerun as a consumer, never the store or
   scientific-semantics owner.
2. Establish the exact command, sink, entity path, or `rr.*` call chain. Inspect
   every touched logging call from selection and preflight through session setup
   and entity emission.
3. Verify the owner-defined invariants in source and tests: non-mutation,
   candidate prefix and hard validity, frame and transform direction, camera
   parameter ordering, metric-depth interpretation, and display-only transforms.
   Do not restate or revise those meanings here.
4. For uncertain or changed Rerun APIs, hand off through
   [`aria-nbv-context`](../aria-nbv-context/SKILL.md), read its
   [Context7 registry](../aria-nbv-context/references/context7_library_ids.md),
   then read [`references/context7-queries.md`](references/context7-queries.md)
   and request the smallest current official-doc slice. Use
   [`references/official-examples-map.md`](references/official-examples-map.md)
   only to choose a current upstream example; verify installed signatures and
   local call sites before changing code.
5. Prefer a saved one-sample `.rrd` for reproducible review evidence. If the
   real store is missing, partial, or version-blocked, record the exact failure
   and use fake-Rerun or fixture tests instead of weakening store validation.
6. Run the narrowest logger, CLI, frustum, lifecycle, or rollout-consumption
   tests. Report the command or artifact path, inspected entity/sink boundary,
   owner evidence, and any unresolved data or geometry handoff.

## Preferences

- Prefer stable, low-cardinality entity paths and batched repeated geometry;
  isolate a selected candidate only when inspection benefits from it.
- Prefer native Rerun camera and transform archetypes when current SDK evidence
  and focused tests cover their relation and ordering.
- Prefer `save` for review and regression artifacts, `spawn` for interactive
  diagnosis, and `connect` only when a viewer or server is already intentional.
- Keep blueprints, colours, labels, downsampling, and rotations presentation-only.
- Keep `.rrd` output outside VIN and rollout training stores.
