---
name: measured-autoresearch
description: Alternate research and measured iterations.
metadata:
  mode: implementation
  not_when:
    - "literature-only research has no executable evaluator"
    - "no active mission root and lifecycle owner are explicitly identified"
    - "the evaluator, budget, or mutable path set is still changing"
  handoff_to:
    - "aria-nbv-context for localizing candidate code or inspiration evidence"
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
  must_read:
    - ".agents/skills/measured-autoresearch/references/measurement-contract.md"
  canonical_sources:
    - ".agents/skills/measured-autoresearch/references/measurement-contract.md"
    - ".agents/skills/measured-autoresearch/scripts/experiment.py"
    - ".agents/skills/measured-autoresearch/tests/test_experiment.py"
  literature_refs:
    - "docs/contents/literature/index.qmd"
  verification:
    - "make measured-autoresearch-self-test"
    - "python3 <skill>/scripts/experiment.py validate --mission-root <mission>"
---

# Measured Autoresearch

The enclosing OMX workflow owns lifecycle and terminal validation. This sidecar
owns only inspiration and helper-computed measurement evidence.

## Mixed iteration loop

1. Resolve one mission from explicit handoff/goal evidence; never select by
   recency or glob history. Freeze its contract/ownership, then measure baseline.
2. **Research/inspiration:** inspect local, then useful external evidence;
   append source provenance, mechanism, and a falsifiable hypothesis to
   `inspiration.jsonl`. Mutate no source, evaluator, contract, or budget, and
   create no experiment row.
3. **Implementation/measurement:** make one smallest causal change; run the
   unchanged gates/evaluator and let the helper record `keep` or `discard`.
   Restore discards only within declared mutable paths with byte/status proof.
4. Deliberately alternate iteration types, especially at plateau or after
   contradictory evidence. Research proposes the next measured candidate.
5. Validate and render after measurement, then return control without claiming
   lifecycle completion.

Read `references/measurement-contract.md` for schemas, commands, and safeguards.
