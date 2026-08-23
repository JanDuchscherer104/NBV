# Proposal Routing Fixtures

These fixed read-only records exercise lifecycle routing without creating
policy or TOML mutations during evaluation.

## Eligible proposal

- ID: `proposal-fixture-config-factory`
- Source debrief: `.agents/memory/history/2026/08/2026-08-23_g002_pr2_proposal_review_lifecycle.md`
- Proposed statement: Prefer the existing custom configuration factory when
  multiple construction sites need the same validated configuration contract.
- Evidence: repeated current-user preference for the custom config-as-factory
  pattern across project interactions.
- Current conflict: no accepted scoped requirement selects a construction
  pattern for the general configuration surface.
- Target owner: `.agents/references/human_owner_intent.md`
- Expected state: eligible proposal evidence; no disposition.

## Already-owned near miss

- Candidate: keep thesis and executable code synchronized.
- Exact owner: `.agents/skills/agent-behavior/SKILL.md`.
- Accepted scoped requirement:
  `.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md`.
- Expected state: no proposal; the accepted requirement and exact owner settle
  the decision before general reviewed intent.

## Verified residual

- Record: `todo-044` in `.agents/todos.toml`.
- Current state: active until the typed lifecycle and reviewable matched routing
  evidence are complete.
- Expected state: amend the existing record after exact-owner proof; do not
  create a duplicate.

## Review commands

- `defer proposal-fixture-config-factory`: current-user authority records one
  typed defer receipt and retains the active record.
- `accept proposal-fixture-config-factory` without an exact current-task user
  instruction, target-owner commit, and proof: invalid; leave it proposed.
