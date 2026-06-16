# ARIA-NBV Source Order

Use this reference when a task needs current project truth or sources disagree.

## Role Split

- Current thesis direction: `docs/contents/thesis/roadmap.qmd`,
  `docs/contents/thesis/questions.qmd`, and `.agents/memory/state/` describe
  the active thesis plan, locked decisions, open questions, gotchas, and current
  state.
- Current terminology: `docs/typst/shared/glossary.typ` owns terms and symbols;
  `docs/contents/glossary.qmd` is generated public output.
- Idea archive: `docs/contents/ideas.qmd` is read-only scratch/history, not
  current direction.
- Advisor proposal narrative: `docs/typst/thesis/proposal.typ` and its included
  sections own proposal-facing wording once proposal work is in scope.
- Seminar evidence: `docs/typst/seminar_paper/main.typ` and included sections
  describe the older implemented substrate and past seminar writeup. Use them
  for historical evidence, not for current thesis priority.
- Active maintenance work: `.agents/issues.toml`, `.agents/todos.toml`,
  `.agents/refactors.toml`, and `.agents/resolved.toml` via `make agents-db`.
- Generated routing artifacts: `docs/_generated/context/source_index.md`,
  `literature_index.md`, and `data_contracts.md`; refresh with `make context`
  when stale.
- Operator aids and long conventions: `.agents/references/`.
- Optional tool and adapter boundaries:
  `.agents/references/alignment_tools_contract.md`. KG/backend operational
  details remain with `.agents/external/litkg-rs/docs/` and `.configs/litkg.toml`.

## Conflict Rule

When current thesis docs or canonical memory conflict with the seminar paper,
prefer the current source for direction and keep the seminar paper as historical
implemented evidence. Do not promote planned work to implemented results.

## Capture Rule

- Repo invariant: root or nearest nested `AGENTS.md`.
- Repeatable workflow: `.agents/skills/*/SKILL.md`.
- Current truth: `.agents/memory/state/`.
- Actionable work: `.agents/issues.toml`, `.agents/todos.toml`, or
  `.agents/refactors.toml` through `agents-db`.
- Public narrative: Quarto or Typst docs.
- Human-owner preference: `.agents/references/human_owner_intent.md`.
- Optional tool boundary: `.agents/references/alignment_tools_contract.md`.
