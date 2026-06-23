---
id: 2026-06-23_thesis_glossary_stub_blank_pages
date: 2026-06-23
title: "Thesis Glossary Stub Blank Pages"
status: done
topics: [typst, thesis, glossary, docs]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/typst/shared/glossary.typ
  - docs/typst/thesis/main.pdf
artifacts:
  - docs/typst/thesis/main.pdf
---

## Task

Diagnose and fix why `docs/typst/thesis/main.typ` compiled to a PDF with six blank pages before the title page.

## Finding

The thesis entry point called `load-aria-glossary-references()` before the `thesis` template body. That helper used `hide(print-aria-glossary(show-all: true, disable-back-references: true))`. Typst `hide` makes content invisible while still laying it out, so the full glossary consumed six invisible pages before the title page.

Removing the helper broke Glossarium `@term` labels, so the fix keeps the helper but changes it to emit only empty `glossarium_entry` label stubs for the base and shorthand labels. This preserves `@term`, `@term:short`, and related references without printing or laying out the full glossary.

## Verification

- `cd docs && typst compile typst/thesis/main.typ --root .`
- `pdfinfo docs/typst/thesis/main.pdf` reported 77 pages after the fix, down from 83 before the fix.
- `pdftotext -f 1 -l 1 docs/typst/thesis/main.pdf -` now starts with the title page text instead of blank output or hidden glossary text.
- `cd docs && typst query typst/thesis/main.typ heading --root .` no longer reports hidden glossary group headings before `Contents`.

## Canonical State Impact

No canonical thesis direction, source-order rule, or public narrative changed.
