# Docs Guidance

Apply this file under `docs/`; use `.agents/references/source_order.md` when
owners conflict.

## Owners And Hazards

- Current thesis direction, research questions, and development gate views are
  owned by `typst/thesis/main.typ` and its includes, especially
  `typst/thesis/sections/01-research-questions.typ` and
  `typst/thesis/development/{roadmap,m1-contract-report}.typ`.
  Seminar and archived proposal material is historical evidence, not priority.
- `typst/shared/glossary.typ` owns durable terms; `typst/shared/symbols.typ` and
  `equations.typ` own reusable Typst bodies and their cross-format registry;
  `notation.yml` is generated from those facades. `references.bib` and `references-qh.bib` own
  citation identities; exact primary sources support advisor-facing scientific
  claims. `typst/shared/style.typ` owns thesis-to-code link behavior.
- Keep public docs aligned with these owners. Do not expose agent guidance,
  generated context, OMX state, or rendered artifacts as public source content.
- Do not present V0 GT actor-visible-target runs as main V1 performance. The
  advisor-facing RQ5 bridge is online discrete `Q_H` over the existing
  finite-candidate ASE mesh/oracle loop, only after offline `Q_H` evidence is
  stable.

## Procedure And Proof

- Use the outline helpers or direct source search to locate one relevant page or
  Typst include. `typst-authoring` owns full authoring and citation procedure;
  `aria-nbv-mermaid` owns Mermaid procedure and local rendering.
- Role-disjoint setup and documentation verification commands route through
  [`docs/README.md`](README.md); executable behavior remains owned by the
  Makefile, CI workflow, and exact source/test owners.
- For thesis claims, inspect the cited primary source and the local evidence.
  Compile the touched Typst surface; for final-link review use the documented
  `aria-wip-links=false` and pinned `aria-code-ref` inputs in `style.typ`.
- For broader Quarto changes, run the relevant frontmatter/render/check command;
  do not generate API, agent, or site artifacts unless that is the task.
