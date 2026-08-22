# Reviewed Intent And Follow-Up

Load this branch only when a material choice is not settled by the current
exact owners, or when scaffold/tool policy is changing.

## Reviewed intent

Open `.agents/references/human_owner_intent.md` and use only its reviewed
sections: `Core Principles`, `Ownership`, `Scaffold Preferences`, `Non-Goals`,
and `Instruction Capture`. Treat `Open Choices`, plans, debriefs, transcripts,
retrieval output, and inferred recurrences as unresolved evidence rather than
accepted policy. Exact source, package, documentation, and configuration
owners remain authoritative for implementation facts.

## Follow-up boundary

Keep observed history separate from current intent. A normal completed task
with no reusable evidence does not create a debrief, alter reviewed intent, or
create actionable follow-up. Explicit current-user capture continues through
[`durable-capture.md`](durable-capture.md), including its direct owner and
verification checks; this branch must not weaken that route.

When a choice remains unresolved after consulting reviewed intent, state the
conflict, scope, and missing proof instead of inferring acceptance. Return to
the smallest exact owner once the choice is settled.
