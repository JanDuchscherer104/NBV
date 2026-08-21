# Typst Package Reference Index

Use packages only when they reduce real document complexity and are already
available in the local Typst environment.

For current upstream behavior, select only the relevant ID from
`typst-authoring` metadata: Typst core, Glossarium, CeTZ, Fletcher, or Touying.
Do not retrieve all package docs by default; confirm the locked package version
and compile the local fixture after any API-sensitive change.

| Need | Prefer | Notes |
| --- | --- | --- |
| Prose glossary terms | `@preview/glossarium:0.5.10` | Owns thesis/proposal term entries and native `@term` / `@term:short` references. |
| Thesis architecture or process diagrams | Mermaid source rendered to PNG/SVG/PDF | Best for diffable pipeline figures and Quarto/Typst reuse. |
| Typst-native diagrams | Fletcher | Use when the diagram must inherit Typst styling or math layout. |
| Sparse typed 3D geometry | `@preview/scenery:0.1.0` | Pure-vector CeTZ output; fixture-gated and limited by painter ordering. |
| Local PLY/OBJ/STL bodies | `@preview/maquette:0.1.1` | SVG for moderate meshes; z-buffered PNG for dense meshes. |
| Result or comparison tables | Typst-native tables with `booktabs` rules | Use `@preview/booktabs:0.0.4` by default for thesis/proposal tables. |
| Typst slide decks | Local `definitely-not-isec-slides` template with Touying reveal helpers | Read `references/slides.md`; keep shared notation imports explicit. |
| Simple network schematics | `neural-netz` | Prefer Mermaid/Fletcher for ARIA-NBV pipelines. |
| Complex external figures | Versioned image/PDF assets | Keep source and render command next to the asset. |

Never introduce a new package into thesis/proposal sources without compiling a
minimal fixture and recording the package name, version/date checked, source
URL, and compile command in the relevant package reference.

Current package notes:

- `booktabs.md` and `booktabs-*.typ` - table rules and examples.
- `cetz.md` - native scientific geometry figures.
- `scenery.md` and `scenery-smoke.typ` - fixture-gated sparse 3D geometry.
- `maquette.md`, `maquette-smoke.typ`, and `maquette-octahedron.obj` -
  fixture-gated local mesh rendering.
- `fletcher.md` and `fletcher-*.typ` - diagram rules and examples.
- `fletcher-manual.md` - cleaned Fletcher manual for detailed package syntax.
- `neural-netz.md` and `neural-netz-example.typ` - simple network schematic
  fallback.
- `slides.md` - local slide template, Touying reveal controls, and slide QA
  expectations.
