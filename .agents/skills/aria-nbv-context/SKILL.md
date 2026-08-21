---
name: aria-nbv-context
description: Use to locate the smallest authoritative ARIA-NBV owner for broad project context, scientific-source routing, reviewed recall, or current external API and version questions.
---

# ARIA-NBV Context

Select the smallest hierarchy leaf, open the exact owner, then hand off.
Derived, retrieved, generated, and historical material may locate truth but
cannot replace its owner.

## Owner Hierarchy

- **Scientific language**: `docs/typst/shared/symbols.typ`,
  `docs/typst/shared/equations.typ`, and `docs/typst/shared/glossary.typ` own
  reusable notation and terms; `docs/typst/glossary/` is the rendered/modular
  glossary output surface, not a term owner. `docs/notation.yml` is a generated
  cross-format adapter; the shared Typst facades own reusable bodies and
  metadata.
- **Thesis direction:** `docs/typst/thesis/main.typ` and active includes own
  narrative and claims; question and development-gate files own narrower
  contracts; `docs/typst/thesis/sections/` owns active claim placement.
- **Literature:** `docs/literature/sources.jsonl` owns source
  acquisition/relevance metadata; `docs/references.bib` and
  `docs/references-qh.bib` own citation identities; `docs/contents/literature/`
  owns review synthesis.
- **Executable system:** the nearest package `AGENTS.md`, source, tests, and
  active configuration own behavior and proof.
- **Project intent and work:** accepted spec supersessions and reviewed human
  intent own decisions; Agents-DB TOMLs own actionable work.
- **Agent execution:** root or nested `AGENTS.md` files own invariants; skills
  own activation, procedure, handoff, and verification.

## Conflict Rule

Prefer the narrowest active owner: active thesis over seminar or archive
history; source, tests, and configuration over documentation or retrieval; and
explicit accepted supersessions over plans or chronology. Planned work is not
an implemented result.

## Capture Rule

- Repo invariant: root or nearest nested `AGENTS.md`.
- Repeatable workflow: the owning skill's `SKILL.md`.
- Actionable work: Agents-DB issues, todos, or refactors.
- Public narrative or scientific language: the smallest active Quarto/Typst,
  glossary, symbol, equation, notation, bibliography, or source owner.
- Reviewed preference: `.agents/references/human_owner_intent.md`.
- Accepted scoped target: the relevant explicit `.omx/specs/` supersession.
- Debriefs and optional tools capture evidence or proposals, not current truth.

Use the owner hierarchy to select one leaf before opening optional references.

## Branch Index

Use this index only for branches with many subtopics. A linked branch reference
may route one additional hop to a leaf; do not chain through another index.

## Graphify Branch

- **Broad architecture, relationship, or project-content question:** Read
  [`references/graphify-aria-boundary.md`](references/graphify-aria-boundary.md),
  classify the navigation state, use the upstream Graphify route when eligible,
  and verify every consequential exact owner.
## Context7 Plugin Branch

- **External API or version uncertainty:** Read
  [`references/context7_library_ids.md`](references/context7_library_ids.md),
  the Context7 library reference. Use a supplied exact ID directly; otherwise call
  the resolver documented there, select one library, issue one focused
  query per concept, and verify the answer against the installed owner and
  tests. Do not use Docker MCP Context7.
- **Prior decision or failed-approach recall:** Read
  [`references/semantic-memory-boundary.md`](references/semantic-memory-boundary.md)
  and use only its reviewed, read-only, fail-closed route before opening the
  current owner.
- **Non-obvious cross-surface or literature owner:** Read
  [`references/context_map.md`](references/context_map.md) to reveal the exact
  owner, then open that owner and its nearest guide.
- **Unknown local implementation or symbol owner:** After selecting the source
  family, use `mcp__code_index.search_code_advanced` for a narrow lookup, open
  the exact source and tests, then hand off. Treat index output as navigation
  evidence rather than the behavior owner.
- **Already-known exact owner:** Open it and its nearest `AGENTS.md`, hand off
  immediately, and leave optional branch references unopened.
- **Concrete failure or traceback:** Hand the reproducer to the nearest failure
  owner; use context routing only when ownership remains unknown.

## Completion

Report the selected branch, exact owner, nearest applicable guide, evidence
used, references opened, handoff, and any freshness or verification gap. Stop
retrieving once the owner and proof are explicit.
