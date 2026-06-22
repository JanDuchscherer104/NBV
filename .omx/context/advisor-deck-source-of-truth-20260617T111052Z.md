# Ralph Context Snapshot: Advisor Deck Source Of Truth Patch

## Task Statement

Patch `docs/typst/thesis/advisor_meeting_2026_05_22.typ` from `.omx/specs/autoresearch-advisor-deck-source-of-truth/` and iterate with the ARIA-NBV Typst authoring workflow until the deck compiles and the edited slides are visually checked.

## Desired Outcome

- The May 22 advisor deck incorporates the autoresearch report's highest-source-of-truth consolidation.
- The deck gains source-governance, state categories, implemented/WIP/open-decision structure, typed todo wrappers, citations/links, and shared-equation cleanup.
- Operational next edits are demoted from main-flow truth to WIP/open-decision evidence.
- The result is compiled and inspected, with KG claim checks for newly strengthened advisor-facing claims.

## Known Facts / Evidence

- `.omx/specs/autoresearch-advisor-deck-source-of-truth/report.md` identifies the May 22 deck as the strongest compact advisor-facing contract and lists exact additions, prune targets, shared equation replacements, todo wrappers, citations, and verification commands.
- `docs/AGENTS.md` requires source-order discipline, Typst rendering for non-trivial docs edits, and KG claim checks for advisor-facing thesis/literature claims.
- `.agents/references/source_order.md` currently says roadmap/questions/canonical memory own thesis direction until changed; the deck patch should make the deck internally explicit, but repo-wide owner promotion is a later mirror/update task unless this task expands scope.
- `docs/typst/thesis/advisor_meeting_2026_05_22.typ` already imports `../shared/macros.typ`, which exposes `eqs.*`, `symb.*`, and slide helpers.

## Constraints

- Preserve unrelated dirty worktree changes.
- Do not stage or revert other users' or previous agents' edits.
- Use shared Typst notation before local formulas.
- Use `#todo[...]` wrappers from `@preview/dashy-todo:0.1.3` for conflict/open/WIP markers.
- Keep main flow advisor-decision oriented; put implementation detail and historical material in compact backup slides.

## Unknowns / Open Questions

- Exact `dashy-todo` wrapper syntax may need compile-driven adjustment.
- Slide density may require visual iteration after compile.
- Source-order docs and public mirrors may need a later explicit promotion pass after the deck is accepted as highest truth.

## Likely Touchpoints

- `docs/typst/thesis/advisor_meeting_2026_05_22.typ`
- `.agents/memory/history/2026/06/` debrief for this non-trivial docs pass
- `.omx/state/.../ralph-state.json` via `omx state write/read`

