# Notation And Math

Use this branch for durable terms, symbols, equations, Glossarium references,
or Typst math syntax. Exact notation and scientific meaning remain owned by
`docs/typst/shared` and `docs/notation.yml`.

## Ownership

- Search the shared glossary, symbol facade, equation facade, and nearest
  domain module before adding notation.
- Put recurring prose terms and abbreviations in
  `docs/typst/shared/glossary.typ`; use Glossarium-native `@term` and
  `@term:short` references.
- Put reusable symbols and display equations under `docs/typst/shared`, expose
  them through the existing facade, and register stable mappings in
  `docs/notation.yml`.
- Ordinary local bound variables may stay local when `docs/AGENTS.md` permits
  them. Do not create a second alias for an existing shared concept.
- Run `make glossary` and the owning Typst compile after changing shared
  notation.

## Typst Math

Follow the established shared definitions rather than restating domain symbol
meanings here. The common construction vocabulary is:

- `cal(...)` for abstract sets or collections;
- `bold(...)` for vectors, matrices, tensors, images, and implementation
  arrays;
- `bb(...)` for number or probability spaces and expectations;
- `op("...")` for named operators.

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
