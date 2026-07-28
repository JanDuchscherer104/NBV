# Matt Pocock Skills Contract

This contract adapts `mattpocock/skills` to ARIA-NBV without making Matt's
repo layout a second source of project truth.

## Boundary

- Install/update Matt skills outside this repo with
  `npx skills@latest add mattpocock/skills`.
- Keep ARIA-owned skills under `.agents/skills/*`.
- Keep the tracked ARIA activation policy in
  `.agents/references/mattpocock_skills_manifest.toml`.
- Treat `.codex/config.toml` as untracked operator-local runtime state. It may
  mirror the manifest when a runtime supports project-specific skill enablement,
  but it is not the canonical policy.

## Source Mapping

| Matt assumption | ARIA-NBV owner |
|---|---|
| `CONTEXT.md` domain language | `docs/typst/shared/glossary.typ`, generated `docs/contents/glossary.qmd`, and `.agents/references/source_order.md` |
| `docs/adr/` decisions | The smallest owner selected through `.agents/references/source_order.md`; no generic ADR or legacy-journal destination |
| Issue tracker setup | `.agents/issues.toml`, `.agents/todos.toml`, `.agents/refactors.toml`, and `.agents/resolved.toml` through `agents-db` |
| Code standards | root or nearest `AGENTS.md`, `.agents/references/python_conventions.md`, `.agents/references/verification_matrix.md`, and package tests |
| Research notes | `aria-litkg-memory`, `semantic-scholar-litkg`, `docs-curator`, Quarto literature pages, and `docs/references.bib` |

Do not create Matt-native truth surfaces for ARIA-NBV unless a future explicit
decision demotes the current ARIA owner. In particular, do not let raw
`setup-matt-pocock-skills` create first-class `CONTEXT.md`, `docs/adr/`, or
`docs/agents/` surfaces for this repo.

## Activation Rules

- Model-invoked defaults: `codebase-design`, `tdd`.
- Explicit-only defaults: `improve-codebase-architecture`,
  `writing-great-skills`, `handoff`, `teach`.
- Keep `prototype` reference-only unless the local runtime can force
  explicit-only use.
- Keep overlapping generic skills reference-only: `code-review`,
  `diagnosing-bugs`, `research`, `domain-modeling`, `grill-me`,
  `grill-with-docs`, `grilling`, `to-prd`, `to-issues`, `triage`,
  `implement`, and `setup-matt-pocock-skills`.
- Skip deprecated, in-progress, personal, and misc Matt skills unless a future
  task names one explicitly.

## Integration Rules

- Matt skills provide generic engineering discipline; ARIA local skills provide
  source-order, domain semantics, evidence, and verification.
- Do not add Matt skill names or paths to ARIA skill
  `metadata.canonical_sources`.
- Do not add Matt skill names to machine-facing `metadata.handoff_to`.
- Use short repo-local reference files under individual ARIA skills only where
  an upstream Matt skill reduces duplicated generic prose.
- If a Matt skill proposes an output path, translate it through the source
  mapping above before writing anything.
- If routing is ambiguous, ARIA source order wins and the local ARIA skill
  remains authoritative.
