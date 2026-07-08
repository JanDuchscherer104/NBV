# CeTZ

Use CeTZ for thesis-native scientific geometry figures where the figure should
inherit Typst math/text styling and remain editable as checked-in Typst source.

## Checked Version

- Package: `@preview/cetz:0.5.2`
- Checked: 2026-06-25
- Source: https://github.com/cetz-package/cetz
- Upstream docs: https://cetz-package.github.io/docs

## Import Pattern

```typ
#import "@preview/cetz:0.5.2"

#cetz.canvas({
  import cetz.draw: *
  // Drawing code.
})
```

## ARIA-NBV Usage

Prefer standalone figure sources under `docs/typst/thesis/figures/*.typ` that
compile to versioned PDF assets included by thesis sections. Use CeTZ for
coordinate frames, camera frusta, target boxes, ray bundles, finite candidate
families, point sets, and other geometric schematics. Keep thesis sections
responsible for the scientific caption and prose hook; keep drawing primitives
inside the figure source.

## Verification

Minimal fixture compiled successfully on 2026-06-25:

```bash
tmp=$(mktemp -d)
printf '#import "@preview/cetz:0.5.2": canvas, draw\n#canvas({ draw.line((0,0), (2,1)) })\n' > "$tmp/cetz.typ"
cd docs && typst compile "$tmp/cetz.typ" "$tmp/cetz.pdf" --root /
```

First thesis figure compiled successfully:

```bash
cd docs && typst compile typst/thesis/figures/candidate_generation_geometry.typ typst/thesis/figures/candidate_generation_geometry.pdf --root .
```
