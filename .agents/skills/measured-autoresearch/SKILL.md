---
name: measured-autoresearch
description: Use inside an active OMX autoresearch mission when a frozen executable evaluator can decide one empirical ARIA-NBV hypothesis.
metadata:
  mode: implementation
  not_when:
    - "literature-only research has no executable evaluator"
    - "no active mission root and lifecycle owner are explicitly identified"
    - "the evaluator, budget, or mutable path set is still changing"
  handoff_to:
    - "aria-nbv-context for localizing candidate code or evidence"
    - "aria-nbv-context for source-backed inspiration after a measured plateau"
    - "owning OMX autoresearch workflow for continuation or completion"
  evidence_required:
    - "one explicit active mission root and lifecycle owner"
    - "frozen evaluator fingerprint, data identity, gates, metrics, budget, seed, and mutable paths"
    - "baseline plus candidate artifacts and helper-validated keep or discard record"
  applies_to:
    - ".omx/specs/autoresearch-*/measurements/**"
    - ".omx/goals/autoresearch/*/measurements/**"
    - ".agents/skills/measured-autoresearch/**"
  triggers:
    - "measured autoresearch experiment"
    - "frozen evaluator candidate"
    - "empirical keep or discard"
  must_read:
    - ".agents/skills/measured-autoresearch/references/measurement-contract.md"
  canonical_sources:
    - ".agents/skills/measured-autoresearch/references/measurement-contract.md"
    - ".agents/skills/measured-autoresearch/scripts/experiment.py"
    - ".agents/skills/measured-autoresearch/tests/test_experiment.py"
  literature_refs:
    - "docs/contents/literature/index.qmd"
  verification:
    - "python3 -m unittest .agents/skills/measured-autoresearch/tests/test_experiment.py"
    - "python3 <skill>/scripts/experiment.py validate --mission-root <mission>"
---

# Measured Autoresearch

The enclosing OMX workflow owns mission lifecycle, continuation, and terminal
validation. This sidecar owns only candidate measurement artifacts and the
helper-computed keep/discard evidence under the explicit active mission root.

## Loop

1. Resolve one mission from explicit handoff/goal evidence; never select by
   recency or glob historical missions.
2. Freeze the contract and ownership snapshot before candidate edits.
3. Measure a reproducible baseline, then one smallest falsifiable candidate.
4. Append results through `scripts/experiment.py`; never hand-author ledger
   rows or change the evaluator between candidates.
5. Keep only a helper-recorded `keep`. For discard, restore only declared
   mutable paths and record byte/status proof.
6. Validate and render the measurement report, then return control to the
   enclosing owner without declaring its workflow complete.

Read `references/measurement-contract.md` for exact artifact schema, command
shapes, ownership proof, plateau inspiration, and stop conditions.
