---
name: diagnose-aria
description: Diagnose a concrete ARIA-NBV command, metric, UI, document-build, or data-result failure.
---

# Diagnose ARIA

1. **Localize the symptom.** Read [root guidance](AGENTS.md), the exact failing
   output, and the nearest guide for its owner. Completion: the symptom and its
   owner are concrete, or the missing artifact is named.
2. **Build a red loop.** Reproduce and minimize the symptom, then rank
   falsifiable hypotheses and vary one factor at a time. Hand off a concrete
   diff review to `code-review-aria-nbv` and a specialized contract question to
   the owner named by the nearest guide.
3. **Close the loop.** Fix only a confirmed cause, rerun the minimized and
   original loops, and remove temporary probes. Completion: a passing loop and
   focused regression proof exist, or the exact missing seam is reported.

## Verification

Use the smallest reproducer and its focused regression test.
