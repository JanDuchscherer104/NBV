---
name: plan-grill
description: Ground and grill high-impact ARIA-NBV plans.
metadata:
  mode: router
  not_when:
    - "a localized low-impact edit or concrete failure owns the task"
  handoff_to:
    - "aria-nbv-context when the source owner is unknown"
    - "aria-docs for the resulting public narrative"
  evidence_required:
    - "exact current owner, implementation evidence, and decision scope"
  applies_to:
    - "**"
  triggers:
    - "high-impact or cross-surface ARIA-NBV decision"
  must_read:
    - "AGENTS.md"
  canonical_sources:
    - "AGENTS.md#source-order"
    - ".agents/references/direct_source_claim_checklist.md"
    - "docs/typst/thesis/main.typ"
  verification:
    - "decision-ready handoff with owners, checks, risks, and deferred choices"
---

# Plan Grill

This is the ARIA evidence wrapper around the selected generic grilling or
planning capability. It does not own general interview, option-analysis, or
consensus behavior.

1. Localize the exact owner and current implementation evidence before
   grilling the plan.
2. Apply the generic capability selected by root guidance: use
   `deep-interview` for unresolved requirements and `ralplan` for reviewed
   implementation consensus.
3. For evidence-sensitive claims, follow the direct-source checklist. Keep current
   evidence, proposed changes, assumptions, and deferred work distinct.
4. Return a decision-ready handoff naming the goal, owner paths, boundaries,
   verification, risks, rollback point, and deferred choices.

Write durable outcomes only to the owner selected by root guidance.
