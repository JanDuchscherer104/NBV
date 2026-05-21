# Plan: Hard-Diagnostic Invalidity Consistency

Backlog: `todo-087`, linked to `issue-032`, `issue-021`, and `issue-018`.

## Problem

Collision-aware rollout probes can write candidate diagnostics where
`path_collision_mask=true`, while the corresponding candidate
`invalid_reason_bitset` does not include the `PATH_SEGMENT_COLLISION` bit. The
validator rejects this because invalidity is supposed to be a hard mask/reason
contract, not an optional diagnostic side channel.

The likely implementation cause is a first-failing-rule contract: one surface
records the first cumulative invalidity reason, while rule masks record every
rule that fired. A candidate can fail clearance first and still collide along
its path.

The same consistency rule must cover every diagnostic mask or scalar that means
hard infeasibility, not just path collision. Candidate diagnostics such as
motion-realism rejection, invalid free-space margin, mesh-clearance violation,
depth/render no-hit, target-support failure, and target/source invalidity should
either imply matching invalidity bits or be explicitly documented as soft
audit-only diagnostics.

## Desired Contract

Use a two-level invalidity model:

- `invalid_reason_bitset`: all hard invalidity reasons known for the candidate.
- `primary_invalid_reason`: one deterministic human-facing reason, chosen from
  the bitset by a fixed priority table.

This keeps Q/action masks conservative and preserves compact diagnostics for
human inspection.

Recommended primary-reason priority:

1. target/source invalid,
2. pose nonfinite or frame invalid,
3. out of extent or free-space invalid,
4. path collision,
5. mesh clearance,
6. motion realism,
7. depth/render no-hit,
8. target crop or target support invalid,
9. oracle scoring failed.

## Implementation Plan

1. Trace candidate-rule outputs from `candidate_generation_rules.py` through
   `rollouts/trace.py` and `rollouts/zarr_store.py`.
2. Classify every candidate diagnostic as `hard_invalidity` or `audit_only`.
3. Make `_candidate_invalid_reasons` or its caller accumulate all failed rule
   bits when rule masks are available.
4. Add or preserve a primary-reason field/derivation for compact reporting.
5. Tighten validation so every hard diagnostic rule mask or infeasible scalar has
   the matching bit in `invalid_reason_bitset`.
6. Add synthetic regression candidates that fail multiple hard diagnostics,
   including clearance plus path collision and motion realism plus free-space.
   Assert all bits are present and the primary reason is stable.
7. Regenerate a small collision-aware schema-1.0 probe and require store
   validation to pass without disabling path collision.

## Tests And Verification

- `cd aria_nbv && uv run pytest tests/rollouts/test_zarr_store.py tests/rollouts/test_dataset_writer.py tests/pose_generation/test_pose_generation.py -q`
- Generate a small collision-aware rollout probe and run
  `nbv-rollouts-info --validate --stats`.
- Inspect one multi-reason invalid row to confirm bitset and primary reason
  agree with the contract.

## Open Decisions For Review

1. Should the primary reason be first-failing order, severity order, or
   deterministic rule-priority order? Recommended: deterministic fixed priority,
   because it is stable across implementation refactors.
2. Should independent diagnostic masks ever be allowed without invalidity bits?
   Recommended: only for non-hard diagnostics; all hard feasibility masks must
   map to bits.
3. Do we need a named `primary_invalid_reason` hot field, or is it acceptable to
   derive it from the bitset when displaying? Recommended: persist a compact
   primary field if existing consumers already assume one reason per row.
