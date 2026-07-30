---
description: Apply the diagnose-aria skill — feedback-loop-first bug investigation.
argument-hint: "<symptom or failing command>"
---

Apply `.agents/skills/diagnose-aria/SKILL.md`. Before patching:

1. Search `.agents/resolved.toml` for similar prior work — do not redo settled
   diagnoses.
2. Build the smallest reproducible loop for "$ARGUMENTS" (focused pytest, CLI
   smoke, KG command, render). Do not guess at fixes until the loop fails the
   same way the user reported, or state explicitly why no loop is possible.
3. Write 3–5 ranked falsifiable hypotheses; probe one variable at a time.
4. Turn the minimized repro into a regression test when a real seam exists.
5. Remove every `[DEBUG-...]` probe before reporting.

Verify with the narrowest check named by the failing surface's package guide or
diagnostic skill.
