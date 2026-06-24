---
id: 2026-06-23_thesis_code_link_macros
date: 2026-06-23
title: "Thesis Code Link Macros"
status: done
topics: [typst, thesis, code-links, litkg, scaffold]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/typst/shared/style.typ
  - .agents/references/thesis_code_links.md
  - docs/AGENTS.md
  - .agents/skills/typst-authoring/SKILL.md
  - .agents/references/source_order.md
  - .agents/references/litkg_quick_reference.md
---

Task: added a two-tier Typst convention for links from thesis prose to source
code, with final-visible pinned anchors and removable WIP/agent navigation
links.

Method: extended the shared Typst style macros with `#gh`, `#gh-wip`, and
`#gh-symbol`; documented the convention in `.agents/references`; and pointed
docs, Typst-authoring, source-order, and litkg guidance at the convention.

Verification: compile and guidance checks were run as part of the implementation
turn and reported in the final response.

Follow-up: active `#gh`, `#gh-wip`, and `#gh-symbol` labels now render blue and
underlined so custom bodies still advertise that they are hyperlinks. The
temporary demo under `.tmp/thesis-code-links-demo/` uses examples that exist on
`origin/main` and renders final mode with `aria-code-ref=main` rather than a
placeholder release tag.

Canonical state impact: no `.agents/memory/state` updates are needed. The
durable convention is captured in `.agents/references/thesis_code_links.md` and
referenced from the owning guidance surfaces.
