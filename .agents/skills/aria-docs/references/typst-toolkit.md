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
Fletcher diagrams should use named nodes and explicit edges. Scenery needs
explicit imports and visual inspection of painter ordering. Maquette's vector
lane is appropriate only while mesh complexity and depth ordering remain
legible.

## Data And Scripting

Typst may load small stable inputs with `csv()`, `json()`, or `toml()`.
Dictionary rows are usually clearest for CSV-backed tables. Keep parsing and
formatting declarative; perform heavy computation, statistical analysis, and
large-data transformation outside Typst, then retain the producing source and
input provenance.

Use small `let` functions, `map`, and `flatten` for document shaping. Reuse
shared helpers before adding a local macro. Use `import` for named module
members and `include` only when inserting document content is the intended
operation.

## Slides

Read the target deck and shared slide template before changing theme or macros.
Each slide should make one primary reader move. Prefer a visual plus concise
evidence over manuscript paragraphs. Use progressive reveals only when order
carries meaning, and ensure the final revealed state fits without overflow or
tiny labels. Keep notation, terms, citations, and colors aligned with the
owning thesis sources.

Compile the target document or deck, render affected pages, and inspect package
behavior, layout stability, final-size legibility, and references.
