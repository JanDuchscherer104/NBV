# Notation And Math

Use this branch for durable terms, symbols, equations, Glossarium references,
or Typst math syntax. Exact notation and scientific meaning remain owned by
`docs/typst/shared` and `docs/notation.yml`.

## Ownership

- Search `glossary.typ`, the `symbols.typ` and `equations.typ` facades, their
  nearest domain modules, `math.typ`, and `docs/notation.yml` before adding
  notation.
- Put recurring prose terms and abbreviations in
  `docs/typst/shared/glossary.typ`; use Glossarium-native `@term` and
  `@term:short` references.
- Put reusable symbols and display equations under `docs/typst/shared`, expose
  them through the existing facade, and register stable mappings in
  `docs/notation.yml`.
- Connect glossary entries to mathematical owners through `symbol_refs` or
  `equation_refs` when the prose term owns that notation. Keep `terms.typ` as a
  generated compatibility facade, not a new prose API.
- Ordinary local bound variables may stay local when `docs/AGENTS.md` permits
  them. Do not create a second alias for an existing shared concept.
- Run `make glossary` and the owning Typst compile after changing shared
  notation.

When adding notation, update the nearest domain module, add a semantic comment,
export a new module through its facade, register the stable YAML mapping, and
use the facade from the document. If generated Typst, Quarto, Lua, or lookup
artifacts change, verify they were produced from these owners rather than
edited directly. Run `scripts/glossary_build.py validate` before the full
document compile.

## Typst Math

Follow the established shared definitions rather than restating domain symbol
meanings here. The common construction vocabulary is:

- `cal(...)` for abstract sets or collections;
- `bold(...)` for vectors, matrices, tensors, images, and implementation
  arrays;
- `bb(...)` for number or probability spaces and expectations;
- `op("...")` for named operators.

Abstract states, candidate rows, and sets do not become tensors merely because
an implementation batches them. Avoid nested `bold(cal(...))`, raw TeX
commands, spaced operator names, and Unicode lookalikes in mathematical source.

Attachment scope is a rendered contract. Leave a space between an attached
operator label and its arguments:

```typst
$ op("IoU")_"3D" (a, b) $
```

When a subscript selects an output component, group the complete call first:

```typst
$ (op("Model")_theta (bold(X)))_i $
```

Use quoted roman labels for semantic attachments and Typst math symbols rather
than Unicode lookalikes. Compile and inspect every changed display equation for
attachment scope, line overflow, font consistency, labels, and references.

Render thesis display equations with native `$ ... $` blocks. Do not wrap
shared equations in `block` or `align`; native display equations already center
their body and participate in the thesis equation-numbering counter.

Migrate stale notation when touching advisor-facing equations, but do not mix a
local edit with a broad compatibility cleanup. Compatibility keys may retain
old names while rendering current notation; infer semantics from the shared
definition, not the key spelling, and remove aliases only in a separate
verified cleanup.
