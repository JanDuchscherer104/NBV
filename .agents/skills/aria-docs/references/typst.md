# Typst, Notation, And Render Contract

Read this file for Typst syntax, equations, shared notation, Glossarium, or
compile/render work. Read `thesis-writing.md` or `visuals.md` only when the task
also changes prose or visual argumentation.

## Bootstrap

1. Read `docs/AGENTS.md`, the target entrypoint, its imports, and adjacent
   sections.
2. Localize large documents with native Graphify traversal when fresh, or with
   `rg -n '^\s*(=+ |#include\s+")' docs/typst -g '*.typ'` as the exact-source
   fallback.

3. Inspect the relevant files under `docs/typst/shared/`.
4. Compile from `docs/` with `--root .`; do not guess import roots from the
   current shell directory.

Reuse `docs/typst/shared/style.typ`, `macros.typ`, `math.typ`,
`slide-template.typ`, and existing nearby figure sources before adding another
helper. Preserve package versions and import patterns from the owning document;
do not recover vendored package manuals or archived templates as active policy.

## Source-Of-Truth Split

- `docs/typst/shared/glossary.typ` owns durable prose terms and abbreviations.
  Use Glossarium-native `@term` and `@term:short` references in prose.
- `docs/typst/shared/symbols.typ` and its domain modules own reusable
  mathematical symbols through the `#symb...` facade.
- `docs/typst/shared/equations.typ` and its domain modules own reusable
  equations through the `#eqs...` facade.
- `docs/typst/shared/math.typ` owns shared math helpers.
- `docs/notation.yml` maps stable notation keys across Typst and generated
  documentation.

Do not add a local acronym wrapper, one-off recurring symbol alias, or duplicate
equation in a thesis section. If notation is missing, update the nearest shared
domain module, its facade, and `docs/notation.yml`; update the glossary only
when a prose term is also needed. Run `make glossary` after source changes.

## Mathematical Conventions

- Use `cal(...)` for abstract sets, spaces, point sets, candidate sets, meshes,
  and geometric collections.
- Use `bold(...)` for vectors, matrices, tensors, fields, embeddings, images,
  depth, voxels, and implementation arrays.
- Use `bb(...)` for number/probability spaces and expectations.
- Use `op("...")` for named operators and manifolds.
- Use quoted superscripts for semantic tags.
- Candidate rows, abstract states, and sets are not tensors merely because a
  later implementation batches them.
- New thesis reconstruction math uses the shared point-mesh error notation,
  not an uncontrolled generic Chamfer-distance alias.
- Use Typst math symbols rather than Unicode lookalikes. Parenthesize a full
  base before attaching nested subscripts or superscripts when attachment scope
  is not visually obvious.

Inspect existing shared definitions before relying on these conventions; the
files, not this summary, own exact rendered symbols.

## Compile And Inspect

Full thesis:

```bash
make thesis-pdf
```

Focused PDF:

```bash
cd docs
typst compile typst/thesis/main.typ /tmp/aria-thesis.pdf --root .
```

Affected pages as PNG:

```bash
cd docs
typst compile typst/thesis/main.typ \
  '/tmp/aria-thesis-page-{0p}.png' --root . --pages 1-4 --ppi 220
```

Use 300-600 PPI for equation or fine-detail inspection. Check attachment scope,
line and equation overflow, font consistency, cross-references, figure
placement, caption wrapping, clipping, and awkward page breaks. Repeat until
the affected pages are visually clean; compilation alone is insufficient.

For final thesis-link review, follow
`.agents/references/thesis_code_links.md` and compile with draft links disabled
and a pinned `aria-code-ref`.
