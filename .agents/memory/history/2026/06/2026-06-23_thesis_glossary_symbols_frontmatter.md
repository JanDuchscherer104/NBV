---
id: 2026-06-23_thesis_glossary_symbols_frontmatter
date: 2026-06-23
title: "Thesis Glossary And Symbols Front Matter"
status: done
topics: [typst, thesis, glossary, notation, docs]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/notation.yml
  - docs/typst/shared/notation.typ
  - docs/typst/shared/notation.generated.typ
  - docs/typst/shared/glossary.typ
  - docs/typst/thesis/main.typ
  - docs/typst/thesis/template/layout/thesis_template.typ
  - scripts/glossary_build.py
artifacts:
  - docs/typst/thesis/main.pdf
---

## Task

Implement front-matter printing for the thesis Glossarium glossary and a
separate internal symbol list without forcing mathematical notation into
Glossarium term entries.

## Findings

Glossarium now owns prose terms and abbreviations in the thesis front matter.
The printed thesis glossary uses `show-all: true` and disabled back-references:
front-matter `show-all: false` introduced Typst layout convergence warnings
because the usage-filtered glossary was printed before later body references.

Symbols remain on the shared notation path. `docs/notation.yml` now marks the
explicit thesis symbol subset with `thesis_list: true`, descriptions, and stable
orders. `scripts/glossary_build.py` validates that listed symbols have
descriptions and emits renderable Typst notation data. `docs/typst/shared/notation.typ`
renders the thesis symbol table from that generated data, grouped by the key
namespace so the printed list separates oracle/reconstruction, RRI metrics, ASE
assets, VIN scorer, entity/target, planning/rollout, and shape/size notation.
Glossarium descriptions that mention thesis notation use Typst content rather
than quoted strings so inline expressions render as math in the printed
front-matter glossary.

## Verification

- `make glossary`
- `python3 scripts/glossary_build.py validate`
- `aria_nbv/.venv/bin/ruff check scripts/glossary_build.py`
- `cd docs && typst compile typst/thesis/main.typ --root .`
- `cd docs && typst query typst/thesis/main.typ heading --root .`
- `pdfinfo docs/typst/thesis/main.pdf`
- `pdftotext -f 1 -l 20 docs/typst/thesis/main.pdf -`
- Rendered and inspected PDF pages 1, 8, 18, and 19 under `.omx/tmp/thesis-glossary-pages/`.
- Rendered and inspected symbol-list pages 18 and 19 under `.omx/tmp/thesis-symbol-domains-*`.
- Rendered and inspected glossary math pages 11, 13, 14, and 15 under `.omx/tmp/thesis-glossary-math-page*`.

## Canonical State Impact

No source-order or thesis-direction update is needed. The implementation follows
the existing canonical split: Glossarium-native `@term` references for prose
terms, shared `symb`/`eqs` facades for math, and `docs/notation.yml` as the
generated bridge for lookup and rendered notation artifacts.
