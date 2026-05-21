# Plan: Rollout Generation Preflight Gate

Backlog: `todo-089`, linked to `issue-032`, `issue-018`, `issue-022`, and
`issue-028`.

## Problem

Broad offline generation is risky while the local default stores are stale,
fresh collision-aware probes fail validation, the validating structural probe
has degenerate sampler contribution, and selected target gains can be near
numerical noise.

The project needs one current-schema go/no-go report before LRZ or broader
local generation.

## Desired Contract

Preflight is a production gate, not a dashboard-only convenience. It should
exit nonzero for production profiles when a store is stale, invalid, degenerate,
or unexpectedly heavy.

The report should cover:

- schema and validator status,
- source rows/scenes/snippets/targets/rollouts/steps/candidates,
- stale store detection against current expected schema,
- scene-level split override status and shard split purity,
- per-position valid and selected counts,
- invalid-reason histograms,
- selected and all-candidate target-root-gain distributions,
- selected-depth and target-eval-crop retention status,
- file/chunk counts and group sizes,
- seed/split/lineage metadata, including stochastic replay provenance,
- explicit production go/no-go reasons.

Recommended CLI shape:

```bash
uv run nbv-rollouts-info path/to/store.zarr \
  --preflight \
  --profile production \
  --json
```

Stable JSON sections:

- `schema`: version, expected version, compatibility status.
- `validation`: validator errors and warnings.
- `lineage`: source store ids, scene split manifest hash, stochastic seed
  provenance, writer/config hashes.
- `coverage`: source rows, scenes, snippets, targets, rollouts, steps,
  candidates, q_h rows.
- `validity`: actor/q/train masks, invalid-reason counts, per-position and
  per-strategy valid counts.
- `rewards`: target-root-gain quantiles, selected-gain quantiles,
  target-vs-scene diagnostic comparison, flat-signal status.
- `retention`: selected-depth status, target-eval-crop payload status, audit
  group presence.
- `storage`: bytes, chunk policy, file counts, group sizes.
- `go_no_go`: `pass|warn|fail`, failures, warnings, and profile-specific
  threshold values.

Recommended first production failures:

- unsupported/stale schema or validation errors,
- missing scene-level split override for thesis profiles,
- missing replay-grade stochastic provenance for stochastic training traces,
- `num_valid_candidates < max(12, ceil(0.25 * N_q))`,
- fewer than three valid non-forward target-aware actions per state,
- median absolute valid `target_root_gain < 1e-4` and p90
  `target_root_gain < 1e-3`, unless explicitly running smoke/audit,
- unexpected audit-heavy payload retention in a training-core profile,
- excessive file/chunk count relative to candidate/step count.

## Implementation Plan

1. Extend `nbv-rollouts-info` or add a narrow companion command that reuses the
   same reader/inspection code.
2. Define a JSON output schema with stable top-level sections:
   `schema`, `validation`, `coverage`, `validity`, `rewards`, `retention`,
   `storage`, `lineage`, and `go_no_go`.
3. Add production-profile thresholds as config/CLI options rather than hardcode
   all numbers in the reader.
4. Fail on unsupported or stale schema for production profiles; do not add
   migration readers.
5. Fail on validation errors, missing required hot fields, missing scene split
   lineage, missing stochastic replay provenance for stochastic training traces,
   unexpected required audit payloads, low valid-action counts, target-aware
   family collapse, flat reward signal, and excessive file/chunk counts.
6. Keep smoke/audit modes able to report failures without blocking, so
   investigation remains easy.
7. Document the command in the operator runbook or rollout README once the
   behavior is reviewed.

## Tests And Verification

- `cd aria_nbv && uv run pytest tests/rollouts/test_inspection.py tests/rollouts/test_zarr_store.py -q`
- `cd aria_nbv && uv run nbv-rollouts-info --store <fresh_schema_1_store> --validate --stats --json`
- Add fixtures for stale schema, invalid store, degenerate sampler, and a small
  passing schema-1.0 store.

## Open Decisions For Review

1. Should preflight be a new command or an extension of `nbv-rollouts-info`?
   Recommended: extend `nbv-rollouts-info` if the interface stays readable;
   add a new command only if go/no-go options become too dense.
2. What is the first production reward-signal threshold? Recommended: fail
   production if median absolute valid `target_root_gain < 1e-4` and p90
   `target_root_gain < 1e-3`, while smoke only warns.
3. Should stale local defaults fail every run or only production-profile runs?
   Recommended: fail production profiles, warn for explicit smoke/audit paths.
4. Should file/chunk count thresholds be absolute or scale-normalized?
   Recommended: normalize per candidate/step plus an absolute cap for tiny
   probes.
