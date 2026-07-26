---
id: 2026-07-26_native_thesis_equations
date: 2026-07-26
title: "Native Thesis Equations"
status: done
topics: [thesis, typst, equations, notation]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/typst/thesis/template/layout/thesis_template.typ
  - docs/typst/thesis/sections
  - .agents/skills/aria-docs/references/notation-and-math.md
artifacts:
  - /tmp/aria-thesis-equations.pdf
  - /tmp/aria-thesis-equations-page35.png
---

# Native Thesis Equations

## Outcome

The active thesis now enables native equation numbering and renders shared
display equations through plain `$ ... $` blocks. Section-level
`block(align(...))` wrappers were removed because they produced generic layout
content instead of numbered `math.equation` elements.

## Verification

- The complete thesis compiled to a 122-page PDF.
- The active thesis sections contain no shared-equation `block(align(...))`
  wrappers or bare block-level `#eqs` insertions.
- Rendered page 35 shows centered equations numbered `(3)` and `(4)` after the
  two equations in the preceding section.
- The notation validator accepts native displays containing one shared
  `#eqs.*` reference and still rejects locally owned raw display math; both
  focused regression tests pass.
- Shared equation definitions were not modified by this change.

## Canonical State Impact

The thesis template owns equation numbering. Active thesis sections own the
display call sites. The existing notation workflow now records the native
display-math rule; this debrief is supporting evidence only.

## TODO Disposition

The inline TODO requesting removal of `block(align(...))` was resolved. No new
agents-DB item is required.
