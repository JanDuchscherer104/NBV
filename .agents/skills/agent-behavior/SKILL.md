---
name: agent-behavior
description: Use before non-trivial ARIA-NBV work to choose a lane, state assumptions, inspect owners, keep diffs traceable, and verify.
metadata:
  mode: router
  not_when:
    - "obvious one-line answer or command output with no durable edit"
  handoff_to:
    - "aria-nbv-context for unknown local ownership"
    - "aria-litkg-memory for KG-backed routing or claim checks"
    - "diagnose-aria for concrete failures"
    - "plan-grill for ambiguous high-impact decisions"
  evidence_required:
    - "root or nearest AGENTS.md for touched surface"
    - "request-traceable edit scope"
    - "surface-specific verification or explicit blocker"
  applies_to:
    - "**"
  triggers:
    - "non-trivial work"
    - "scaffold cleanup"
    - "memory or guidance edit"
  must_read:
    - "AGENTS.md"
  canonical_sources:
    - "AGENTS.md"
    - ".agents/references/source_order.md#capture-rule"
    - ".agents/skills/README.md#required-frontmatter"
  verification:
    - "surface-specific checks from .agents/references/verification_matrix.md"
    - "make check-agent-memory when agent guidance or memory changes"
---

# Agent Behavior

Apply this skill before non-trivial ARIA-NBV work. Keep it lightweight for
obvious one-line fixes.

## Principles

1. State assumptions and ambiguity before editing.
2. Inspect the nearest owner before changing a surface.
3. Prefer the simplest sufficient change.
4. Preserve unrelated user or agent work.
5. Verify the touched behavior before claiming completion.

## Lane Rule

- Do not guess silently. If ownership, evidence, or route is ambiguous, name
  the ambiguity before editing.
- Choose one lane from root `AGENTS.md` or the active skill metadata, state why
  it owns the work, and name the handoff if evidence disproves that choice.
- Keep diffs request-traceable: every changed file must map to the user
  request, the owning guidance surface, or required verification.
- Verify before done. If verification cannot run, report the exact blocker or
  missing evidence.

## Workflow

1. Localize the surface through root `AGENTS.md`, the nearest nested guide, or
   the relevant skill.
2. Name the intended behavior and success criteria.
3. Choose the narrowest edit set that satisfies the criteria.
4. Run the verification for the touched surface.
5. Capture durable deltas only in the smallest owning surface.

## Completion

- Every changed file maps to the user request or required verification.
- Any unverified item is called out explicitly.
- Any new durable rule, workflow, truth, preference, or action item is captured
  in the smallest correct surface named by root `AGENTS.md`.
