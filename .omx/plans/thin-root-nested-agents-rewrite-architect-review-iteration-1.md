# Architect Review: Thin Root/Nested AGENTS Rewrite — Iteration 1

Date: 2026-08-01

Verdict: **REVISE BEFORE CRITIC**

## Blocking findings

1. The proposed root-then-nested sequence is still file-led. For every claim
   family, establish and verify the destination owner, update its consumers,
   prove the replacement, and only then remove the source copy.
2. The smoke set lacks an explicit lifecycle. Default to no new checked-in
   model-evaluation runner: freeze prompts and a rubric, run baseline/candidate
   trials in disposable worktrees or sessions, record exact client/model/config,
   and keep permanent CI deterministic.
3. An explicitly bounded dirty diff is insufficient for destructive edits to
   the overlapping MemPalace/root/test paths. Require an immutable integrated
   commit for those paths before deletion, relocation, or semantic replacement.

## High findings

- Convert G002 and routing evidence to candidate-independent owner/outcome
  assertions while the old scaffold still passes. Only then edit guidance.
- Do not parallelize root, shared fixtures/G002, source order, or overlapping
  MemPalace paths. One serial integrator owns them. Parallelism is limited to
  disjoint leaf guides after owner and evaluator contracts are frozen.
- Keep unrelated skill line-budget and semantic-drift cleanup outside this
  rewrite unless it directly blocks the candidate.

## Medium findings

- Keep the claim ledger ephemeral and grouped by claim family. Expand to
  claim-level rows only when owner, consumer, disposition, or proof differs;
  detailed rows remain mandatory for deleted, relocated, or replaced claims.
- Add `make graphify-skill-upstream-self-test` to baseline and final gates.
- `make scaffold-audit-self-test` already runs G002; avoid an immediately
  duplicate direct G002 run except as a focused diagnostic.
- Remove the nonexistent `scripts/tests/test_scaffold_audit.py` touchpoint;
  scaffold-audit self-tests are inline in `scripts/scaffold_audit.py`.
- Refresh concurrency evidence at execution time; the worktree acquired another
  untracked debrief after the context snapshot.
- Interpret “root plus nearest guide is sufficient” as sufficient to identify
  the exact owner, local hazard, local validation, and relevant procedural route,
  not as containing the full procedure.
- Preserve stable identifiers when an accepted owner and live consumer prove a
  compatibility contract. The rollout eight-symbol API and `python-standards`
  name are current examples.
- Retain all current nested `AGENTS.md` files in this rewrite and thin them.
  Any later file deletion needs its own consumer and repeated-ambiguity evidence.

## Antithesis and synthesis

Steelman for an atomic rewrite: Codex consumes root and nested files as one
composed interface, so a single coherent change avoids temporary contradiction
and the risk that later packages never land.

Tradeoff: small rollback boundaries conflict with atomic coherence; exhaustive
tracking conflicts with keeping migration machinery smaller than the guidance.

Synthesis: retain the gated series as internal commits on one integration
branch, but make each commit a vertical claim slice and expose only a complete,
coherent hierarchy as the merge boundary. Keep the grouped ledger ephemeral and
permanent validation deterministic.

## Required revision

- Reorder workpackages around immutable integration baseline, candidate-
  independent evaluator conversion, then vertical destination/proof/source cuts.
- Decide the temporary smoke evidence lifecycle and minimal retry rule.
- Narrow parallel staffing and permanent validator scope.
- Correct command/touchpoint gaps and trim duplicated plan prose.
