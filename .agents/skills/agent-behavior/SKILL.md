---
name: agent-behavior
description: Use before non-trivial ARIA-NBV work.
metadata:
  mode: router
  not_when:
    - "obvious one-line answer or read-only lookup"
  handoff_to:
    - "nearest skill named by root AGENTS.md"
  evidence_required:
    - "nearest owner and request-traceable verification"
  applies_to:
    - "**"
  triggers:
    - "non-trivial ARIA-NBV work"
  must_read:
    - "AGENTS.md"
  canonical_sources:
    - "AGENTS.md#routing"
    - ".agents/references/source_order.md#capture-rule"
  verification:
    - "surface-specific check from AGENTS.md"
---

# Agent Behavior

Use this workflow before non-trivial work.

1. State material assumptions and ambiguity.
2. Inspect the nearest owner before editing.
3. Choose the smallest request-traceable scope.
4. Preserve unrelated user and agent changes.
5. Verify the touched surface and report the evidence.

If verification cannot run, report the exact blocker. Capture durable changes
only in the actual owning surface named by root `AGENTS.md`.
