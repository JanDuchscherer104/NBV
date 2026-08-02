# Architect Review: Thin Root/Nested AGENTS Rewrite

Date: 2026-08-01

Verdict: **APPROVE**

## Approved architecture

- Require an immutable integrated baseline for all overlapping root,
  source-order, MemPalace/context, routing-fixture, and G002 paths.
- Convert candidate-independent deterministic evaluator checks and prove them on
  the old integrated scaffold before editing guidance.
- Implement destination-first vertical claim slices: establish the owner,
  update consumers, prove behavior, then remove the source copy.
- Keep the claim ledger grouped, ephemeral migration evidence; expand every
  deleted, relocated, or replaced claim.
- Retain and thin all current nested `AGENTS.md` files; later file deletion is a
  separate evidence-backed decision.
- Keep permanent CI deterministic and native/model trials disposable.
- Run S1–S5 read-only. Run S6 in a controlled `workspace-write`, approval-never
  disposable worktree with an exact assigned guide, identical unrelated tracked
  and untracked sentinels, and external pre/post status/hash/content checks.
- Use an independent `test-engineer` to apply the frozen rubric and a verifier to
  audit retry decisions; the executor cannot self-grade or choose retries.
- Keep shared/overlapping paths under one serial integrator. Parallelize only
  disjoint leaf guides after baseline and evaluator gates.
- Expose only a complete coherent hierarchy at the merge boundary.

## Antithesis, tension, and synthesis

**Steelman antithesis:** an atomic file-batch rewrite offers the strongest
guarantee that consumers never encounter a partially migrated composed
instruction hierarchy.

**Tradeoff tension:** vertical slices improve attribution and rollback but allow
temporary internal duplication and create a serial integration bottleneck.

**Synthesis:** retain destination-first vertical internal slices while exposing
only the complete coherent hierarchy at merge. Combine deterministic permanent
checks, read-only discovery trials, and one tightly controlled writable S6.

## Evidence

- Vertical slice and immutable baseline:
  `.omx/plans/prd-thin-root-nested-agents-rewrite.md:20,207-312`
- S1–S5/S6 lifecycle and environment equality:
  `.omx/plans/test-spec-thin-root-nested-agents-rewrite.md:175-198`
- Independent grading and retry authority:
  `.omx/plans/test-spec-thin-root-nested-agents-rewrite.md:201-228`
- S6 assigned guide, sentinels, external oracle, and failure conditions:
  `.omx/plans/test-spec-thin-root-nested-agents-rewrite.md:293-363`
- Matching PRD acceptance/risk controls:
  `.omx/plans/prd-thin-root-nested-agents-rewrite.md:314-373`

## Incorporated closeout improvements

1. `$trial_root/evidence` is created before S6 output redirection, and external
   S6 `diff --check` output is captured.
2. Plan status and final Architect/Critic review links are current.
3. S1–S6 are the shared final corpus; destructive claim slices use only bounded
   workpackage-local comparisons where needed.

Architect gate is complete. The subsequent independent Critic review is also
approved at `.omx/plans/thin-root-nested-agents-rewrite-critic-review.md`.
