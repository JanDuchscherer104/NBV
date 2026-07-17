# CeTZ

Use CeTZ for thesis-native scientific geometry figures where the figure should
inherit Typst math/text styling and remain editable as checked-in Typst source.

## Checked Version

- Package: `@preview/cetz:0.5.2`
- Checked: 2026-07-17
- Source: https://github.com/cetz-package/cetz
- Upstream docs: https://cetz-package.github.io/docs
- Orthographic projection: https://cetz-package.github.io/docs/api/draw-functions/projections/ortho/
- 3D coordinates: https://cetz-package.github.io/docs/basics/coordinate-systems/

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
compile to versioned PDF assets included by thesis sections. CeTZ owns sparse,
exact geometry such as coordinate frames, camera frusta, target boxes, ray
bundles, finite candidate families, great circles, point sets, visible/hidden
arcs, and Typst-native annotations. Prefer orthographic projection when metric
or angular interpretation matters, and make foreground/background treatment
explicit. Use a data or scene renderer for dense fields, meshes, or point
clouds, with Typst/CeTZ as the annotation layer. Keep thesis sections
responsible for the scientific caption and prose hook; keep drawing primitives
inside the figure source. Read `../scientific-visualizations.md` for renderer
selection and the geometry/provenance contract.

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
