---
id: 2026-07-26_aria_docs_typst_workflow_restoration
date: 2026-07-26
title: "ARIA Docs Typst Workflow Restoration"
status: done
topics: [scaffold, docs, typst]
confidence: high
canonical_updates_needed: []
---

# ARIA Docs Typst Workflow Restoration

Commit `40a36caa` over-compacted `aria-docs`: it removed the disclosed Typst,
writing, and visual branches restored earlier, leaving only generic ownership
and render instructions. The historical debrief still described those branches,
which made the regression harder to notice.

`aria-docs` now routes progressively to four compact references:

- notation, Glossarium, math attachment, and shared-owner workflow;
- thesis drafting modes, claim classification, evidence, and paragraph checks;
- scientific figure/table provenance, renderer choice, accessibility, and QA;
- Typst packages, structured data, scripting, layout, and slides.

The restoration deliberately excludes old package manuals, fixtures, duplicate
ARIA scientific definitions, Context7 query registries, LitKG claim commands,
generated-context helpers, and retired render wrappers. Exact thesis, shared
Typst, bibliography, code, evidence, and upstream package sources remain the
owners of content; the skill owns authoring workflow only.

A follow-up retention audit against the full former skill closure restored
missing behavioral contracts without changing the branch structure: notation
facade synchronization and migration-on-touch, scoped claims and falsifiers,
section checks, typed draft/submission markers, label/reference conventions,
spherical-domain safeguards, hybrid-render provenance, package failure modes,
Typst data/layout semantics, and slide reveal constraints.
The model-visible description now names these authoring branches explicitly;
the updated integrated description budget remains below its frozen ceiling.
An independent retention audit added the remaining opt-in rule for generated
bitmap imagery and otherwise returned no authoring-contract gaps.

Validation:

- skill `quick_validate.py`: passed;
- `make scaffold-audit`: 10 skills, 0 errors, 0 warnings;
- `make check-agent-memory`: passed;
- `git diff --check`: passed.
