---
id: 2026-06-18_glossarium_authoring_cleanup
date: 2026-06-18
title: "Glossarium Authoring Cleanup"
status: done
topics: [docs, typst, glossary, thesis]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/typst/shared/glossary.typ
  - docs/typst/thesis/main.typ
  - docs/typst/thesis/sections/01-introduction.typ
  - docs/typst/thesis/sections/02-foundations/index.typ
  - docs/typst/thesis/sections/04-method/index.typ
  - docs/typst/thesis/sections/05-experimental-design/index.typ
  - docs/typst/thesis/sections/08-conclusion.typ
  - docs/typst/thesis/sections/06-draft-open-work.typ
---

## Task

Implemented the thesis Glossarium authoring cleanup: active thesis prose now
uses Glossarium `@term` references instead of the local `#gls(...)` wrapper or
generated acronym constants.

## Method

Removed local `gls` and `glspl` wrapper exports from the canonical glossary
facade. Added `load-aria-glossary-references()` so thesis builds can materialize
Glossarium reference labels without printing the glossary inline. Converted
active thesis text from `#gls(...)`, `#NBV`, `#RRI`, `#ASE`, and `#EVL` style
references to `@term` / `@term:short` references. A follow-up pass also
converted plain prose/table short forms such as `GT`, `EFM3D`, `EVL`,
`OBS-SEL`, `PRED-Q`, and `GT-EVAL` across existing thesis sections, while
leaving project names, citation keys, and dense math string constants intact.

## Verification

- `typst query docs/typst/shared/glossary.typ '<aria-glossary-term>' --field value`
- `cd docs && typst compile typst/thesis/main.typ --root .`
- `cd docs && typst compile typst/glossary/main.typ --root .`
- `rg -n "#gls\\(|#glspl\\(|#NBV\\b|#RRI\\b|#ASE\\b|#EVL\\b|#GT\\b|#ADT\\b|#AEO\\b|#EFM3D\\b|#SLAM\\b" docs/typst/thesis/main.typ docs/typst/thesis/sections -S`

## Canonical State Impact

No canonical state update is needed. `docs/typst/shared/glossary.typ` remains
the terminology source of truth; the change narrows the Typst authoring API to
Glossarium references for thesis prose.
