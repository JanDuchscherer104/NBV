---
name: zarr-python
description: Change ARIA-NBV Zarr API, layout, chunking, codecs, stores, sharding, concurrency, or migration behavior.
---

# Zarr Python

Use a round-trip change loop. Existing-store operation without a storage-
implementation change belongs to `dataset-cache-ops`.

1. Localize the writer, reader, and test through the nearest data-handling or
   rollout [`AGENTS.md`](../../../aria_nbv/aria_nbv/rollouts/AGENTS.md) and
   [`README.md`](../../../aria_nbv/aria_nbv/rollouts/README.md). Localization is
   complete when one code owner and one round-trip proof are named.
2. Read the installed dependency constraint in
   [`aria_nbv/pyproject.toml`](../../../aria_nbv/pyproject.toml). For a
   nontrivial upstream API or migration decision, consult current official
   Zarr-Python documentation and record when that evidence is unavailable.
3. Change the smallest owning writer/reader surface. Keep dataset operations in
   `dataset-cache-ops`, rollout meaning in `counterfactual-rollout-planner`, and
   concrete failures in `diagnose-aria`.
4. Run the focused owner test that writes and reads the affected arrays or store;
   add the relevant CLI validation only when the CLI path changed.

Completion requires a local owner, current upstream evidence when needed, and a
fresh round trip or an exact evidence blocker.
