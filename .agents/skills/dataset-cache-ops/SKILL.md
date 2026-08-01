---
name: dataset-cache-ops
description: Operate ARIA-NBV downloads, shards, meshes, immutable stores, manifests, storage estimates, or data smoke checks.
---

# Dataset Cache Ops

Use an owner-first operation loop. This skill coordinates an operation; the
owning package and command surface define the data contract.

1. Localize the active data surface through the data-handling
   [`AGENTS.md`](../../../aria_nbv/aria_nbv/data_handling/AGENTS.md), its module
   [`README.md`](../../../aria_nbv/aria_nbv/data_handling/README.md), and the exact
   CLI or source being exercised. Localization is complete when the input, store,
   and validation owner are named.
2. Inspect before mutation. Run the owner-provided listing, dry-run, status, or
   validation path and record the exact data root and failure or health evidence.
   Inspection is complete when rebuild, repair, download, or no-change is a
   falsifiable choice.
3. Choose the narrow branch:
   - downloads, shards, meshes, and source coverage stay with the data CLI;
   - immutable-store validation, manifests, splits, estimates, and rebuilds stay
     with `aria_nbv.data_handling`;
   - Zarr API, layout, codec, store, or concurrency changes hand off to
     `zarr-python`;
   - remote storage or batch execution hands off to `lrz-ai-systems`.
4. Execute the smallest owner-supported operation. A traceback or contradictory
   metric hands off to `diagnose-aria` with the command and captured evidence.
5. Verify through the same strict reader, smoke command, or focused package test
   that exposed the contract.

Completion requires the exact owner and command, the observed store disposition,
and fresh validation evidence or a precise blocker.
