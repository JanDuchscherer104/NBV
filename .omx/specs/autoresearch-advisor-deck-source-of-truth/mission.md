# Autoresearch Mission: Advisor Deck As Source Of Truth

## Objective

Research what `docs/typst/thesis/advisor_meeting_2026_05_22.typ` should contain if it becomes the highest source of truth for ARIA-NBV thesis direction and advisor-facing state.

## Required Output

- A source-verified report at `.omx/specs/autoresearch-advisor-deck-source-of-truth/report.md`.
- A completion artifact at `.omx/specs/autoresearch-advisor-deck-source-of-truth/result.json`.

## Scope

- Verify current truth from thesis QMDs, canonical memory, current Typst proposal/distillation, historical seminar/outlook material, implementation references, and litkg retrieval.
- Identify deck content to add, update, prune, or mark with `#todo[...]`.
- Design Typst todo flavors derived from `@preview/dashy-todo:0.1.3` for conflicts, open decisions, necessary WIP, optional work, and prune candidates.
- Do not rewrite the deck in this research phase.

## Validator

Approve only if the report:

- verifies major source families against local repo state;
- lists add/update/prune recommendations for `advisor_meeting_2026_05_22.typ`;
- identifies ownership, conflicts, and open decisions;
- includes litkg evidence or fallback status;
- proposes a dashy-todo flavor design;
- avoids broad implementation edits.
