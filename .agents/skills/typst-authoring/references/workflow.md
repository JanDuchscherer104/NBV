# Typst Edit, Compile, Render, Inspect Loop

Use this loop for non-trivial edits: equations, figures, tables, layout,
captions, bibliography/cross-references, or multi-paragraph thesis prose.

## 1. Inspect Local Context

```bash
make context-typst-includes TYPST_INCLUDES_ARGS='--paper --mode includes'
make context-typst-outline TYPST_OUTLINE_ARGS='--paper --mode outline'
```

Then read the target file, adjacent sections, and relevant files under
`docs/typst/shared`.

## Thesis Mode Contract

- Unguarded thesis content is submission-facing by default.
- Wrap drafting diaries, alternative-design registries, diagnostic prose, and
  other development-only content lazily with `development_only(() => [...])`
  from `draft_markers.typ`; the thunk prevents nested includes from evaluating
  in submission mode.
- Use `submission_only(() => [...])` only for genuinely mode-specific final
  material.
- TODO markers and editorial `thesis_status` blocks must fail submission
  compilation. Rewrite their scientific substance as ordinary method,
  limitation, result, or future-work prose before submission.
- Mode applies to every rendered object: headings, prose, equations, figures,
  tables, captions, footnotes, and includes. A surrounding wrapper owns all
  nested content.
- Validate both modes. A submission failure caused by unresolved evidence or
  drafting markers is a successful gate, not a successful submission build.

## 2. Isolate Fragile Objects

For a complex equation, table, or figure, create or update a small fixture
first. This reduces noise and makes visual errors obvious.

## 3. Compile

Prefer repo Make targets for full document builds:

```bash
make thesis-pdf
```

`make thesis-pdf` and `make thesis-pdf-ci` run
`scripts/check_typst_pdf_column_bounds.py` after Typst compilation. The check
reads rendered Poppler bounding boxes, not source width guesses, and detects
each body-band line outside the template's declared 30 mm left/right column
(within a small point tolerance). Its `WARNING typst-column-overflow` records
the PDF page, actual horizontal bounds, violated side, and extracted text. Treat a
warning as a failure even when using `--warn-only` during detector adoption:
split the equation/table or use a deliberate readable layout; do not use
scaling, negative spacing, or clipping merely to silence it.

The current thesis invocation keeps `--warn-only` as an explicit transitional
baseline because it has pre-existing overflow warnings. It prints the warnings
in local builds and CI. Set `THESIS_COLUMN_CHECK_ARGS=` to make the identical
command non-zero on any finding once the baseline is clean.

Use the manual form when isolating an output path:

```bash
cd docs && typst compile typst/thesis/main.typ /tmp/thesis-main.pdf --root .
```

For files under `.agents/skills`, compile from the repo root with `--root .`.

## 4. Render Affected Pages

```bash
.agents/skills/typst-authoring/scripts/render_png.sh \
  -i docs/typst/thesis/main.typ \
  -o /tmp/thesis-pages \
  --root docs \
  --pages 1-4 \
  --ppi 300
```

Use `--ppi 600` for detailed equation/figure inspection.

## 5. Inspect Visually

Check attachment scope after `_` / `^`, bolding and symbol consistency, line
breaks and equation overflow, figure scale/cropping, caption clarity, table
alignment, cross-reference output, and awkward page breaks. The PDF
column-bound contract catches text/equation leakage mechanically, but visual
inspection remains necessary for clipped non-text graphics, readability, and
page-break quality.

For the thesis-wide authoring contract, also run:

```bash
make typst-authoring-contract
```

This static source check requires shared display-equation consumers, checks
recurring notation without globalising local binders, scopes structural labels
to the authored thesis inventory, and keeps raw implementation keys and
status vocabulary out of ordinary submission prose. Generated labels, metadata
query labels, fixtures, explicit code spans, and guarded development material
are deliberate exclusions.

## 6. Fix And Repeat

A clean compile alone is insufficient when the change affects rendering. Repeat
until the affected pages are visually clean.

## 7. Final Hygiene

```bash
.agents/skills/typst-authoring/scripts/hygiene_checks.sh --strict docs/typst/thesis/sections
.agents/skills/typst-authoring/scripts/hygiene_checks.sh --examples .agents/skills/typst-authoring
make check-agent-memory
git diff --check
```

Report exactly what was checked. If a command cannot run, say why.
