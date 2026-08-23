# Agents DB Workflow Modes

Use these names as workflow modes inside the `agents-db` skill. Do not create
separate trackers unless the user explicitly asks for GitHub publication.

## triage

Classify incoming work by updating existing `priority`, `status`, and `labels`.
Do not add new TOML schema fields for triage state.

## to-issues

Split a plan into independently grabbable vertical slices in
`.agents/todos.toml` or `.agents/refactors.toml`.

Each slice should deliver one narrow behavior or decision path end to end.
Acceptance criteria should be verifiable from commands, docs renders, tests, or
reviewable artifacts.

## to-prd

Synthesize the current conversation into a problem statement, solution, affected
modules, implementation decisions, testing decisions, out-of-scope list, and
follow-up TOML slices.

For non-trivial work, preserve narrative in `.agents/memory/history/` rather
than public docs.

## proposal-review

Review an evidence-backed Human Intent Proposal with exactly one disposition:
`accept`, `reject`, `narrow`, or `defer`. Accept or narrow only through an
ordinary reviewed edit to the smallest policy owner. Reject or defer leave the
reviewed policy bytes unchanged and record the reason in the existing review
surface. After the installed change and its proof, resolve the Agents-DB
record; never delete it, and keep deferred records active.
