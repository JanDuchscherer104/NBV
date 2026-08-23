# Agents DB Workflow Modes

Use these names as workflow modes inside the `agents-db` skill. Do not create
separate trackers unless the user explicitly asks for GitHub publication.

## triage

Classify incoming work by updating existing `priority`, `status`, and `labels`.
Do not add new TOML schema fields for triage state.

For a residual, search all active and resolved records, open the candidates,
and prove each candidate against the exact current owner and its acceptance or
verification state. Select or amend the closest active record only when it is
independently actionable. Treat resolved records as precedent; do not recreate
completed work unless fresh exact-owner proof establishes a distinct
recurrence. Create a new record only after all-scope deduplication proves that
no active or resolved record can own the residual. In an abstract or read-only
residual simulation, instantiate the route on an existing active record whose
acceptance or proof remains incomplete, never on a completed historical
residual.

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

`.agents/proposals.toml` owns active typed lifecycle records;
`.agents/proposals_resolved.toml` retains closed receipts. Open a record with
`scripts/agents_db.py proposal-open`, including its source debrief, exact target
owner, statement, evidence, conflict, and scope. The debrief remains immutable
at `Disposition: proposed`.

Review with exactly one disposition through `proposal-review`. `accept` and
`narrow` require a commit that changes the exact target owner plus a proof
receipt; `reject` requires a reason and no owner-edit commit; `defer` keeps the
record active. After a non-defer review, `proposal-resolve` moves the typed
receipt to resolved history. The commands record lifecycle state but never edit
the target owner automatically.

A real disposition requires `--reviewer current-user` and a receipt naming the
exact current-task instruction selecting that branch. Existing policy or old
conversation evidence is insufficient; without current authority, leave the
proposal active and unresolved. Routing tests exercise fixed fixture records,
not simulated repository mutations.
