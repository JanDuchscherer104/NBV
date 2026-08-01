---
name: code-review-aria-nbv
description: Review an ARIA-NBV working-tree or pull-request diff, or validate review feedback against the current source.
---

# Review ARIA-NBV

1. **Establish the surface.** Read [root guidance](AGENTS.md), the exact diff
   or review artifact, and the nearest guide for every touched owner.
   Completion: every candidate finding has a current source and owner.
2. **Validate findings.** Check each reported or discovered issue against the
   owner and the smallest relevant test, command, or artifact. Hand off a
   symptom that needs reproduction to `diagnose-aria`; route an ownership
   question to the named nearest owner.
3. **Report the result.** Give line-referenced findings ordered by severity, or
   state that none were found with the unverified residual risk. Completion:
   every finding has evidence and a remedy or next diagnostic step.

## Verification

Run only the focused validation needed to confirm or refute likely findings.
