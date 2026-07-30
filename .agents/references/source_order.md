# ARIA-NBV Source Order

Use this map when sources disagree. Prefer the narrowest owner that can prove
the claim.

## Authority

1. Source code, tests, and active configuration own implemented behavior.
2. `docs/typst/thesis/main.typ`, its included sections, and
   `docs/typst/shared/glossary.typ` own thesis claims, notation, and
   ubiquitous language. `docs/references.bib` and cited papers own scientific
   evidence.
3. Root or nearest `AGENTS.md` owns repository and package operating rules.
   Skills own routing and repeatable procedures only.
4. `.agents/issues.toml`, `.agents/todos.toml`, and `.agents/refactors.toml`
   own actionable work. Historical debriefs preserve evidence, not current
   truth.
5. `.agents/references/human_owner_intent.md` owns reviewed cross-task human
   preferences.

## Boundaries

- Generated documentation, indexes, graphs, and optional tools are discovery
  aids. Verify claims against their source owners.
- The seminar paper and archived material are historical evidence, not current
  thesis direction.
- `docs/typst/shared/style.typ` owns thesis-to-code link behavior. Links aid
  navigation but do not replace citations, equations, evidence, or tests.
- Optional tools produce evidence or proposals. Record durable outcomes only
  in the appropriate owner above.

## Capture

- Invariant: root or nearest `AGENTS.md`.
- Procedure: `.agents/skills/*/SKILL.md`.
- Work item: Agents DB through `agents-db`.
- Public narrative: Typst or Quarto source.
