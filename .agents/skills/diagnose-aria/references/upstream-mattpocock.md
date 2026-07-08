# Upstream Matt Pocock Guidance For Diagnose ARIA

Use this as reference-only inspiration from Matt `diagnosing-bugs`.

Borrow:

- build a tight red-capable feedback loop before hypothesizing;
- reproduce and minimize the exact user-visible symptom;
- generate several ranked falsifiable hypotheses;
- instrument one variable at a time;
- convert the minimized repro into a regression test when the seam is real;
- remove temporary debug probes before completion.

ARIA differences:

- `diagnose-aria` owns ARIA command selection and symptom surfaces.
- Geometry, RRI, VIN, rollout, Rerun, Streamlit, docs, KG, and cache failures
  use their local owners and verification commands.
- If no reproducible loop exists, report the missing artifact or access rather
  than guessing a patch.
