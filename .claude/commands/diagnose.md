---
description: Run a feedback-loop-first ARIA-NBV bug investigation.
argument-hint: "<symptom or failing command>"
---

Before patching:

1. Search `.agents/resolved.toml` for similar prior work — do not redo settled
   diagnoses.
2. Build the smallest reproducible loop for "$ARGUMENTS" (focused pytest, CLI
   smoke, Graphify query, exact-source inspection, render). Do not guess at
   fixes until the loop fails the same way the user reported, or state
   explicitly why no loop is possible.
3. Write 3–5 ranked falsifiable hypotheses; probe one variable at a time.
4. Turn the minimized repro into a regression test when a real seam exists.
5. Remove every `[DEBUG-...]` probe before reporting.

Verify with the narrowest check from
`.agents/references/verification_matrix.md` for the failing surface.
