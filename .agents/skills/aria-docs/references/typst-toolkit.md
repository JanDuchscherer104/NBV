# Typst Toolkit

Use this branch when a document change depends on a Typst package, structured
data, scripting, layout, or slides. Prefer the target document's current
imports and local shared components; package manuals and versions remain
upstream-owned.

## Package Routing

| Need | Existing lane |
| --- | --- |
| Glossary terms | Glossarium through `docs/typst/shared/glossary.typ` |
| Process or architecture diagram | Mermaid or Fletcher |
| Exact vector geometry | CeTZ |
| Sparse typed 3D | Scenery, with painter-order limitations checked |
| Moderate local mesh | Maquette SVG; use a z-buffered raster for dense geometry |
| Publication table | Typst table with Booktabs rules |
| Slides | `docs/typst/shared/slide-template.typ` and the target deck |
| Complex external visual | Versioned asset with reproducible source and render command |

Introduce a package only when it removes real document complexity. Preserve an
existing pinned import when possible; otherwise compile a minimal fixture and
record the package, version, authoritative source, and compile command.

- CeTZ owns sparse exact geometry and should prefer orthographic projection
  when metric or angular interpretation matters.
- Fletcher diagrams use named nodes and explicit edges; they encode relations,
  not calibrated coordinate geometry.
- Scenery uses explicit imports because common names can shadow local Typst
  bindings. Its painter ordering, missing z-buffer, near-plane behavior, and
  version-specific opacity semantics require a fixture and final-size review.
- Maquette SVG is painter-sorted and suitable only for inspected low- or
  moderate-complexity meshes. Dense, concave, or intersecting geometry uses a
  z-buffered raster lane. Record units, up axis, projection, camera, shading,
  decimation, and input checksum.
- Neural-network packages are a fallback for simple layer schematics;
  Mermaid or Fletcher is clearer for system architecture and data flow.
- Booktabs tables use the target's pinned import and explicit rules rather than
  decorative cell borders.

## Data And Scripting

Typst may load small stable inputs with `csv()`, `json()`, or `toml()`.
Dictionary rows are usually clearest for CSV-backed tables. Keep parsing and
formatting declarative; perform heavy computation, statistical analysis, and
large-data transformation outside Typst, then retain the producing source and
input provenance.

Use small `let` functions, `map`, and `flatten` for document shaping. Reuse
shared helpers before adding a local macro. Use `import` for named module
members and `include` only when inserting document content is the intended
operation. Arrays preserve order; dictionaries provide named access and merge
with later keys winning. Treat loaded CSV values as strings until explicitly
converted, and do not use `repr` as a serialization format.

## Layout

Use `grid` for aligned panels, `stack` for one-dimensional composition,
`align`/`block`/`box`/`pad` for flow-aware placement, and `layout` with
`measure` only when sizing genuinely depends on the container. `move`,
`rotate`, `scale`, and `place` can alter appearance without reserving matching
flow space, so inspect overlap and pagination. Centralize document-wide style
with the existing `set` and `show` owners instead of accumulating local fixes.

## Slides

Read the target deck and shared slide template before changing theme or macros.
Each slide should make one primary reader move. Prefer a visual plus concise
evidence over manuscript paragraphs. Use progressive reveals only when order
carries meaning, and ensure the final revealed state fits without overflow or
tiny labels. Keep notation, terms, citations, and colors aligned with the
owning thesis sources. Reserve space deliberately when using reveal helpers,
keep caption and source labels readable at presentation distance, and move
secondary derivations or evidence to appendix slides.

Compile the target document or deck, render affected pages, and inspect package
behavior, layout stability, final-size legibility, and references.
