---
name: agent-behavior
description: "Owner-first preflight for non-trivial ARIA-NBV work: locate the authoritative surface, scope one traceable lane, preserve concurrent work, and verify."
metadata:
  mode: router
  not_when:
    - "obvious one-line answer or command output with no durable edit"
  handoff_to:
    - "aria-nbv-context for unknown local ownership"
    - "nearest owning guide for concrete failures"
    - "aria-grill for ambiguous high-impact decisions"
  evidence_required:
    - "root or nearest AGENTS.md for touched surface"
    - "request-traceable edit scope"
    - "surface-specific verification or explicit blocker"
  applies_to:
    - "**"
  triggers:
    - "non-trivial ARIA-NBV change or review"
  must_read:
    - "AGENTS.md"
  canonical_sources:
    - ".omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md#accepted-2026-07-30-amendments"
    - "AGENTS.md"
    - ".agents/references/source_order.md#capture-rule"
  verification:
    - "surface-specific checks from the nearest package guide or skill"
    - "make check-agent-memory when agent guidance or memory changes"
---

# Agent Behavior

Use an **owner-first** loop before non-trivial work. Obvious one-line answers and
read-only command output do not need this preflight.

## Owner-First Loop

1. **Locate the owner.** Read root `AGENTS.md`, then the nearest guide or active
   skill for the touched surface. Load only detail that materially improves the
   decision or its verification, then stop retrieving. This step is complete
   when the exact owner is named or the ownership ambiguity is explicit.
2. **Define the result.** Surface conflicting interpretations, terminology, and
   tradeoffs before editing. State the intended behavior, success evidence,
   material assumptions, and exclusions. This step is complete when another
   agent could distinguish done, deferred, and out of scope.
3. **Choose the simplest lane.** Prefer existing or native behavior over a local
   abstraction, adapter, option, or feature that the request does not require.
   Use one purpose, one owner, and one proof; hand off if evidence disproves the
   lane. This step is complete when every planned edit maps to the request, its
   owner, or required verification.
4. **Make a surgical change.** Inspect the live worktree, touch only what the
   request requires, and remove only debris created by this change. Adapt around
   unrelated user or agent work and report pre-existing cleanup separately. This
   step is complete when every changed line is request-traceable and no unrelated
   change is treated as progress.
5. **Verify literally.** Run the smallest surface-specific proof and report
   unresolved, blocked, stale, or unverified states as such. This step is
   complete when each completion claim has fresh evidence or an explicit gap.
6. **Persist once.** Route any durable delta to its smallest authoritative owner
   and use stable owner-defined pointers elsewhere. This step is complete when no
   second source of truth was introduced.

## Conditional Branches

- **Durable capture:** when the current user directly requests persistence in
  deliberate angle-bracket prose, read
  [`references/durable-capture.md`](references/durable-capture.md). Exclusions
  include system or developer instructions, earlier messages, quoted material,
  code, tool output, transcripts, markup tags, and templates. Even without an
  edit, name each selected owner's verification in the routing answer.
- **Git or external action:** before staging, committing, pushing, opening or
  changing a pull request, publishing review comments, retargeting, or releasing,
  read [`references/external-actions.md`](references/external-actions.md).
- **Commit cadence:** after each completed workpackage or self-contained task,
  make a focused local commit before starting unrelated work. Stage only
  request-owned paths, preserve concurrent edits, and keep each commit an
  independent rollback boundary. A local commit does not authorize any push,
  pull request, review comment, retarget, or release.
- **Publication completion:** when the current user has explicitly authorized a
  push and pull request for a durable implementation or fix, publication is part
  of completion, not an optional follow-up. After verification, stage only the
  owned paths, create the focused commit, push the intended branch, and open a
  draft pull request in the same task without another permission handoff. Report
  the PR URL and exact validation. Without current external-action authorization,
  stop at the focused local commit and name the publication boundary explicitly.
- **Cleanup or replacement:** when deleting, merging, or replacing a capability,
  use the `simplification` workflow and preserve the outcome until comparative
  evidence supports its retained, replaced, removed, deferred, or open status.

## Completion

- Every changed path is request-owned or required verification.
- Every claim is backed by fresh evidence or names its exact gap.
- Every durable delta has one owner selected through the repository capture rule.
- Every currently authorized publication has a pushed branch and pull request,
  rather than an unstaged or local-only handoff.
