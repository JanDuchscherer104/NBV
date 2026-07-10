# Autoresearch Mission: Source-Of-Truth Conflict Verification

## Mission

Verify every item in `.agents/work/source-of-truth-conflicts.md` against the
current local repository state, identify the exact conflicting sources, and
recommend the owning surface for each item.

## Validation Mode

`mission-validator-script`

## Success Criteria

- Every C1-C16 and R1-R4 item from the source ledger is covered.
- Each covered item cites current local source paths with line numbers.
- Stale or partially changed ledger claims are corrected instead of repeated.
- Ownership recommendations follow `.agents/references/source_order.md` and
  `.agents/references/alignment_tools_contract.md`.
- No tracked repo source is modified by this research pass.
