# Scenery 0.1.0

Use Scenery for sparse, typed 3D geometry that should remain pure vector:
calibrated frusta, rays, axes, boxes, triangulated patches, and orientation
spheres. Import names explicitly because the package exports names such as
`label`, `scale`, and `group` that can shadow Typst or local bindings.

Project fixture:
`../../assets/fixtures/scenery-smoke.typ`. Compile from the repository root:

```sh
typst compile \
  .agents/skills/typst-authoring/assets/fixtures/scenery-smoke.typ \
  /tmp/scenery-smoke.pdf --root .
```

The fixture passed with Typst 0.14.2 on 2026-07-19. Keep the camera and all
world coordinates explicit. The default renderer uses a painter's algorithm;
there is no z-buffer or perspective near-plane clipping, and complex or cyclic
intersections can still order incorrectly. Use the WASM engine only after a
fixture and final-size render check. Route dense scene meshes to a hybrid
z-buffered raster base instead.

Scenery 0.1.0's `fill-opacity` style is a *transparentize amount*, despite the
name: `0%` is opaque and `100%` removes the fill. Use `100%` for a wire-only
orientation sphere or frustum, and keep a fixture for this version-sensitive
semantic. Do not assume CSS/SVG opacity behavior.

Primary sources: [Typst Universe](https://typst.app/universe/package/scenery/)
and [upstream repository](https://github.com/GiggleLiu/scenery).
