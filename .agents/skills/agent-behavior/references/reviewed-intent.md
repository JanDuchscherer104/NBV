# Reviewed Intent

Load this branch only after the current exact owner leaves a material policy
choice unsettled.

## Decision order

1. Open the exact code, test, configuration, documentation, or workflow owner
   for current facts.
2. For work inside an accepted scoped rework, open its accepted specification
   for requirements. The current scaffold rework is owned by
   `.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md`.
3. Open an accepted plan only for sequencing within those requirements. A plan
   does not override the exact owner or specification.
4. Open `.agents/references/human_owner_intent.md` only when the cross-task
   preference is still unsettled. Use only `Core Principles`, `Ownership`,
   `Scaffold Preferences`, `Non-Goals`, and `Instruction Capture`.

Treat `Open Choices`, debriefs, transcripts, retrieval output, inferred
recurrences, and unaccepted plans as unresolved evidence. If the accepted
specification already settles the choice, stop before loading general reviewed
intent. If reviewed intent still leaves the choice open, report the conflict,
scope, and missing decision instead of selecting a policy.

Explicit current-user capture continues through
[`durable-capture.md`](durable-capture.md). Return to the smallest exact owner
after the choice is settled.
