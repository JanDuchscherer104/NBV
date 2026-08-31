# Recent Human-Intent Mining Mission

## Objective

Mine ARIA-NBV Codex sessions from 2026-08-17 through 2026-08-31 for
human-authored, cross-task preferences that are not meaningfully represented in
`.agents/references/human_owner_intent.md`.

## Deliverables

- A public-safe report that accounts for the mined corpus, candidate filtering,
  accepted additions, already-captured preferences, and rejected task-local or
  stale instructions.
- A minimal update to the canonical human-intent owner containing only
  well-supported, reusable preferences.
- A completion artifact with an independent architect approval verdict.

## Acceptance criteria

- The session window and ARIA-NBV project filter are explicit and reproducible.
- Human prompts and plan-mode answers are considered; system, developer,
  assistant, tool, and injected bootstrap text cannot establish intent.
- Every proposed addition has evidence from the window and is compared against
  the live owner, including owner changes made during the same window.
- Task-local requests, status commands, corrections of one implementation,
  secrets, private paths, and raw transcript prose are excluded from the PR.
- The canonical edit is concise, preference-only, and does not duplicate a
  workflow, implementation contract, scientific claim, or backlog item.

## Validation mode

`prompt-architect-artifact`: approve only if the report is corpus-accountable,
conservative about promotion, traceable without publishing raw transcripts,
and the owner edit contains every and only justified reusable preferences.
