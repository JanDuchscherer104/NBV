---
kind: spec
status: accepted
---

# Regression test specification: ownership and branch consolidation

The completed migration is checked directly against canonical Typst, Python,
configuration, tests, public documentation, and agent-routing sources. Generated
OMX inventories and receipts remain ignored orchestration evidence and are not
committed as substitute owners.

## Gates

- All seven retired QMD/state paths remain absent.
- `.agents/references/source_order.md` links the research-question, roadmap,
  and M1 Typst owners.
- Every theory QMD remains deprecated archive/navigation material with
  `owner: docs` and no canonical-owner claim.
- Active tracked sources contain no reference to a retired owner. Dated history,
  transcripts, archives, and the accepted migration plan remain provenance.
- Generated OMX inventories, HTML reports, and JSON runtime output are not
  tracked.
- Typst marker checks run through `make thesis-marker-contract`: development and
  submission fixtures must compile, while invalid promotion fixtures and the
  submission-mode TODO fixture must fail.
- Root `ci` depends on `ownership-consolidation-contract`; hosted CI invokes
  the same target and runs the direct-source migration tests.

The contract test deliberately reads the current source owners instead of a
generated migration ledger. Git history retains the one-time execution receipt;
the live gate protects only the enduring ownership boundary.
