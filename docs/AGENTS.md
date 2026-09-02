# Docs Guidance

Apply this file under `docs/`; use the
[owner hierarchy](../.agents/skills/aria-nbv-context/SKILL.md#owner-hierarchy)
when owners conflict.

## Owners And Hazards

- Current thesis direction, research questions, and development gate views are
  owned by `typst/thesis/main.typ` and its includes, especially
  `typst/thesis/sections/01-research-questions.typ` and
  `typst/thesis/development/roadmap.typ`. The adjacent `roadmap.toml` owns the
  rendered strategic snapshot, milestone dates, states, blockers, evidence
  pointers, and review cadence.
  Seminar and archived proposal material is historical evidence, not priority.
- The chapter-level learning journey is owned by
  `typst/thesis/development/reader-state.toml`; `reader-state.typ` is its
  development-only projection and validator. The ledger records editorial
  prerequisites, teaching goals, takeaways, and outgoing dependencies. It is
  authored rather than inferred and never replaces active chapter prose as the
  owner of scientific claims.
- `typst/shared/glossary.typ` owns durable terms; `typst/shared/symbols.typ` and
  `equations.typ` own reusable Typst bodies and their cross-format registry;
  `notation.yml` is generated from those facades. `references.bib` owns citation
  identities; exact primary sources support advisor-facing scientific
  claims. `typst/shared/style.typ` owns thesis-to-code link behavior.
- Keep public docs aligned with these owners. Do not expose agent guidance,
  generated context, OMX state, or rendered artifacts as public source content.
- Public Python docstrings own symbol-level implementation contracts and feed
  the generated API reference. Package READMEs are user-facing workflow and
  navigation guides; keep detailed shapes, field catalogs, and private symbol
  inventories in source rather than duplicating them there.
- The privileged V0/GT target path is only a sanity or upper-bound route; use
  `docs/typst/thesis/sections/01-research-questions.typ#ssec:rq3`. The
  conditional online bridge is RQ5 at
  `docs/typst/thesis/sections/01-research-questions.typ#ssec:rq5`. Its
  development gate remains deferred pending the offline P1-P3 evidence chain at
  `docs/typst/thesis/development/roadmap.typ#ssec:promotion-queue`.

## Procedure And Proof

- Use the outline helpers or direct source search to locate one relevant page or
  Typst include. `academic-writing` owns source-grounded argument construction;
  `scientific-review` owns independent non-mutating validity review; and
  `typst-authoring` realizes accepted content, notation, citations, and rendered
  pages. `aria-nbv-mermaid` owns Mermaid procedure and local rendering.
- Before changing a chapter's conceptual order or prose flow, read its
  `reader-state.toml` record. Update that record in the same change only when
  the chapter's central reader question, prerequisites, durable takeaways,
  teaching device, or outgoing dependency changes. Copy editing, citation
  repair, and layout-only work leave the ledger unchanged unless they alter the
  learning journey.
- Role-disjoint setup and documentation verification commands route through
  [`docs/README.md`](README.md); executable behavior remains owned by the
  Makefile, CI workflow, and exact source/test owners.
- Roadmap status changes update `typst/thesis/development/roadmap.toml` and run
  `make thesis-roadmap-contract`; do not copy internal tracker state into the
  public thesis projection.
- For thesis claims, inspect the cited primary source and the local evidence.
  Compile the touched Typst surface; development compilation validates and
  renders the reader-state ledger, while submission mode omits it. For
  final-link review use the documented `aria-wip-links=false` and pinned
  `aria-code-ref` inputs in `style.typ`.
- For broader Quarto changes, run the relevant frontmatter/render/check command;
  do not generate API, agent, or site artifacts unless that is the task.
- For README changes, verify every command and relative link against the exact
  source owner. For public-docstring changes, generate the affected API pages
  rather than hand-editing Quartodoc output.
