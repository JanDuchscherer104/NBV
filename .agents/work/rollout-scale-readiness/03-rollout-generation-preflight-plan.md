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
- per-position valid and selected counts,
- invalid-reason histograms,
- selected and all-candidate target-root-gain distributions,
- selected-depth and target-eval-crop retention status,
- file/chunk counts and group sizes,
- seed/split/lineage metadata,
- explicit production go/no-go reasons.

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
5. Fail on validation errors, missing required hot fields, unexpected required
   audit payloads, low valid-action counts, target-aware family collapse, and
   excessive file/chunk counts.
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
2. What is the first production reward-signal threshold? Recommended: require a
   nonzero robust spread and report absolute values, then refine from multi-scene
   audit evidence.
3. Should stale local defaults fail every run or only production-profile runs?
   Recommended: fail production profiles, warn for explicit smoke/audit paths.
4. Should file/chunk count thresholds be absolute or scale-normalized?
   Recommended: normalize per candidate/step plus an absolute cap for tiny
   probes.

