---
name: rerun-nbv-inspector
description: Inspect ARIA-NBV offline samples or rollout stores through Rerun, including entities, layers, validity, sinks, and display frames.
---

# Rerun NBV Inspector

Use an observer-artifact loop. Rerun presents package-owned data and never
settles data, geometry, or scientific meaning.

1. Read the inspector
   [`README.md`](../../../aria_nbv/aria_nbv/rerun_inspector/README.md), then the
   exact logger, session, offline-sample, or rollout adapter and its focused
   tests. When the input store is involved, also read its owning data-handling or
   rollout guide. Localization is complete when the input adapter, entity/layer
   owner, and sink are named.
2. Choose the inspection branch:
   - offline samples use the offline inventory and sample adapter;
   - rollout stores use `aria_nbv.rollouts.read_model` for shared typed
     interpretation and the Rerun rollout adapter for presentation;
   - candidates, validity, RGB/depth/cameras, OBBs, meshes, and trajectories use
     their existing logger paths;
   - frame or projection meaning hands off to `nbv-geometry-contracts` before a
     display fix is accepted.
3. For a nontrivial SDK change, consult current official Rerun documentation.
   Continue with local evidence when it suffices; otherwise state the precise
   upstream-evidence blocker.
4. Produce the smallest useful proof: a focused fake-Rerun test or a one-sample
   saved `.rrd` artifact using the module README's current invocation. An invalid
   input store hands off to `dataset-cache-ops`; a traceback hands off to
   `diagnose-aria`.
5. Confirm the inspector did not mutate its input and that the requested branch,
   empty/all-invalid case, and sink behavior are covered.

Completion requires the opened owner paths, the inspection branch and sink, and
fresh focused test or artifact evidence, or an exact blocker.
