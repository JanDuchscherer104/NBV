# Architect Review: Thin Root/Nested AGENTS Rewrite — Iteration 2

Date: 2026-08-01

Verdict: **REVISE**

All iteration-1 structural findings are resolved. One executable lifecycle gap
remains: native scenario S6 tests dirty-tree mutation/preservation, but the
documented harness is read-only and defines no dirty sentinels or external
preservation oracle.

## Required correction

- Run S1–S5 in read-only disposable worktrees.
- Give S6 identical baseline/candidate disposable fixtures with one exact
  assigned guide, unrelated tracked and untracked sentinels, `workspace-write`,
  approval `never`, and recorded pre/post `git status`, file hashes, and content.
- Reject any mutation outside the assigned guide/evidence output boundary or any
  sentinel change/removal.
- State that environment equality applies within each baseline/candidate
  scenario pair; S6 intentionally differs from S1–S5 only in sandbox/fixture.
- Name the rubric grader. Retries occur on disagreement between the executing
  record and the independent grader/verifier, never at the executor's sole
  discretion.

Antithesis and synthesis remain unchanged: atomic file-batch rewriting offers
the strongest externally coherent instruction chain, while vertical internal
slices provide attribution and rollback. Keep vertical slices, an atomic merge
boundary, read-only discovery trials, and one tightly controlled writable S6.
