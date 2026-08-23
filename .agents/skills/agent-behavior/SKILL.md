---
name: agent-behavior
description: Use before non-trivial ARIA-NBV work to locate the authoritative owner, consult reviewed intent when a material choice is unsettled, scope one traceable lane, preserve concurrent work, and verify the result.
---

# Agent Behavior

Use the owner-first loop before a non-trivial edit, review, diagnosis, or
handoff. Obvious one-line answers and read-only command output do not need the
full preflight. The loop ends when the exact owner, scoped result, and proof are
explicit.

## Invariant

- **Thesis-code synchronization.** Keep the active thesis sources and executable
   implementation in sync. When a change affects an implemented scientific or
   behavioral claim, update and verify both owning surfaces together; do not let
   thesis prose describe behavior unsupported by current code and tests.

- **Lowest shared owner.** Place behavior used by demonstrated consumers at
  their lowest shared domain owner. Use Graphify for non-obvious consumer
  discovery and exact sources for proof; do not create a generic utility owner
  without demonstrated variation.

## Owner-first loop

1. **Locate the owner.** Read the root `AGENTS.md`, then the nearest guide or
   active skill for the touched surface. Stop when the exact owner is named or
   the ambiguity is explicit.
2. **Define the result.** Surface conflicting interpretations, terminology, and
   tradeoffs before editing. State the intended behavior, success evidence,
   material assumptions, exclusions, and earliest failed contract that would
   redirect the lane. Another agent must be able to distinguish done, deferred,
   and out of scope.
3. **Choose the simplest lane.** Prefer existing or native behavior over a local
   abstraction, adapter, option, or feature the request does not require. Keep
   likely change local behind the current owner's smallest interface and verify
   through that interface; add a seam, adapter, or abstraction only for
   demonstrated variation. Use one purpose, one owner, and one proof; hand off
   when evidence disproves the lane.
4. **Make a surgical change.** Inspect the live worktree, touch only what the
   request requires, and remove only debris created by this change. Adapt around
   unrelated user or agent work and report pre-existing cleanup separately.
5. **Verify literally.** Run the smallest owner-defined proof. Distinguish
   configured, initialized, healthy, fresh, successful, blocked, and stale
   states in the report. Every completion claim needs fresh evidence or an
   explicit gap.
6. **Persist once.** Route each durable delta to its smallest authoritative
   owner and use stable owner-defined pointers elsewhere. Do not introduce a
   second source of truth.

For scaffold or tool policy, read
[`references/reviewed-intent.md`](references/reviewed-intent.md) before opening
any general intent source. Also load it when the current exact owner leaves a
material policy choice unsettled or the question asks for policy inside an
accepted scoped rework. Follow its scoped-specification precedence and stop
before general reviewed intent when that specification settles the choice. Do
not load reviewed intent for a settled exact-owner task outside such a scoped
policy decision.

## Conditional branches

- **Durable capture:** When the user directly requests persistence in deliberate
  angle-bracket prose, read
 [`references/durable-capture.md`](references/durable-capture.md) and apply
  its exclusions for quoted material, markup tags, code, and tool output, plus
  its owner checks.
- **Workpackage completion, Git, or external action:** After completing a durable
  workpackage, or before staging, committing, pushing, changing a pull request,
  publishing review comments, retargeting, or releasing, read
  [`references/external-actions.md`](references/external-actions.md).
- **Failure-first diagnosis:** For a bug, regression, suspicious metric, or
  failing check, read the failure-first section of
  [`references/execution-branches.md`](references/execution-branches.md).
- **Reversible learning:** When uncertainty blocks the lane, read the
  reversible-learning section of
  [`references/execution-branches.md`](references/execution-branches.md).
- **Cleanup or replacement:** When deleting, merging, or replacing a
  capability, use the `simplification` workflow and preserve the outcome until
  comparative evidence supports its retained, replaced, removed, deferred, or
  open status.
- **Unknown local owner:** Route to `aria-nbv-context` for hierarchical owner
  localization before editing.
- **Ambiguous high-impact decision:** Route to `aria-grill` before choosing a
  durable interface, architecture, or research-facing direction.
- **Concrete failure owner:** Hand the reproducer and exact evidence to the
  nearest package, docs, or specialist owner.

## Completion

- Every changed path is request-owned or required verification.
- Every claim has fresh evidence or names its exact gap.
- Every durable delta has one authoritative owner.
- Every activated branch meets its referenced completion criteria.
