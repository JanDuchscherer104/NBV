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

## 2. Isolate Fragile Objects

For a complex equation, table, or figure, create or update a small fixture
first. This reduces noise and makes visual errors obvious.

## 3. Compile

Prefer repo Make targets for full document builds:

```bash
make thesis-pdf
```

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
alignment, cross-reference output, and awkward page breaks.

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
