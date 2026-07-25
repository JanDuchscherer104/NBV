---
id: 2026-07-25_aria_docs_invariant_restoration
date: 2026-07-25
title: "ARIA Docs Invariant Restoration"
status: done
topics: [scaffold, docs, typst, mermaid]
confidence: high
canonical_updates_needed: []
---

# ARIA Docs Invariant Restoration

The compact `aria-docs` skill had dropped important Typst, thesis-writing,
scientific-visualization, slide, and Mermaid contracts when the former
specialist skills were merged.

The skill now uses progressive disclosure: its short entrypoint routes to
focused references for Typst/notation, thesis prose, visuals/slides, and
Mermaid. The restored contracts cover Glossarium and shared notation ownership,
thesis-specific outline/bootstrap commands, Booktabs, claim calibration,
scientific provenance and geometry safeguards, Rerun handoff, local Mermaid
validation, and rendered-page inspection. Generic Typst tutorials, archived
templates, vendored package manuals, stale fixtures, and duplicate render
wrappers remain removed.

Validation:

- skill `quick_validate.py`: passed
- `make scaffold-audit`: 9 skills, 0 errors, 0 warnings
- `make check-agent-memory`: passed
- thesis outline and include commands: passed against
  `docs/typst/thesis/main.typ`
- independent retention audit: PASS
