# Upstream Scientific Practice Sources

This file records external provenance for practices adapted into `aria-docs`.
It does not own executable guidance. The local owners are
`writing-and-claims.md`, `figures-and-tables.md`, and `workflow.md`.

When adapting another external source, add its immutable revision or access
date, exact source path or URL, local destination, adopted idea, and rejected
scope. Link instead of copying the upstream body.

## K-Dense Scientific Agent Skills

Snapshot: `K-Dense-AI/scientific-agent-skills` commit
`a1b84fb2235e3b24d4af08b0b118414ff3d95d41`, reviewed 2026-07-26. License:
MIT as declared by the referenced skills.

| Source | Adopted into | Adapted practice | Deliberately not adopted |
| --- | --- | --- | --- |
| [`scientific-writing/SKILL.md`](https://github.com/K-Dense-AI/scientific-agent-skills/blob/a1b84fb2235e3b24d4af08b0b118414ff3d95d41/skills/scientific-writing/SKILL.md) | `writing-and-claims.md` | Separate discovery, drafting, verification, and approval; fail closed on missing evidence; preserve uncertainty and negative outcomes; reconcile methods and results. | Manuscript scaffolds, authorship/declaration workflows, generic journal submission machinery, and biomedical reporting-guideline routing. |
| [`scientific-writing/references/evidence_workflow.md`](https://github.com/K-Dense-AI/scientific-agent-skills/blob/a1b84fb2235e3b24d4af08b0b118414ff3d95d41/skills/scientific-writing/references/evidence_workflow.md) | `writing-and-claims.md` | Exact-source verification and locator discipline; discovery artifacts are not verified evidence. | Parallel claim, source, consistency, authorship, and reporting registries; inline evidence-ID syntax. ARIA already has direct-source checks, draft markers, immutable evidence, code, and bibliography owners. |
| [`scientific-writing/references/figures_tables.md`](https://github.com/K-Dense-AI/scientific-agent-skills/blob/a1b84fb2235e3b24d4af08b0b118414ff3d95d41/skills/scientific-writing/references/figures_tables.md) | `figures-and-tables.md` | Figures are optional and provenance-bound; reconcile them with prose and evidence; inspect accessibility and scientific meaning manually. | Fixed figure quotas, generic display templates, and any image-generation mandate. |
| [`scientific-visualization/SKILL.md`](https://github.com/K-Dense-AI/scientific-agent-skills/blob/a1b84fb2235e3b24d4af08b0b118414ff3d95d41/skills/scientific-visualization/SKILL.md) | `figures-and-tables.md` | Honest encodings, explicit missing data and uncertainty, redundant color encoding, static/interactive separation, hybrid raster/vector disclosure, and final-size inspection. | Bundled exporters, style presets, package snapshots, publisher profiles, generic Seaborn patterns, and a parallel visualization skill. |
| [`scientific-visualization/references/color_palettes.md`](https://github.com/K-Dense-AI/scientific-agent-skills/blob/a1b84fb2235e3b24d4af08b0b118414ff3d95d41/skills/scientific-visualization/references/color_palettes.md) | `figures-and-tables.md` | Match qualitative, sequential, diverging, or cyclic color to data semantics; use non-color cues; do not treat named palettes or grayscale review as certification. | Vendored palettes and a new palette-audit utility without a measured local need. |

The older user-local `scientific-writing` comparison supplied on 2026-07-26
mandated AI-generated schematics, fixed figure quotas, universal IMRAD, and
paragraph-only output. No practice was adopted from those rules; the current
K-Dense revision above explicitly makes figures optional and structure
venue-dependent.

## Matt Writing Mechanics

The fragment, shape, and beat modes in `writing-and-claims.md` were adapted
from `mattpocock/skills` commit
`896f14d9c25659f03b24e08e4efc3ee69bbade08`, reviewed before the repository's
current Matt allowlist pin. They are reference mechanics, not active ARIA
skills:

- [`writing-fragments`](https://github.com/mattpocock/skills/blob/896f14d9c25659f03b24e08e4efc3ee69bbade08/skills/in-progress/writing-fragments/SKILL.md)
- [`writing-shape`](https://github.com/mattpocock/skills/blob/896f14d9c25659f03b24e08e4efc3ee69bbade08/skills/in-progress/writing-shape/SKILL.md)
- [`writing-beats`](https://github.com/mattpocock/skills/blob/896f14d9c25659f03b24e08e4efc3ee69bbade08/skills/in-progress/writing-beats/SKILL.md)

Only the progression from scratch fragments to evidence-shaped paragraphs and
reader-facing beats was adopted. Upstream scratch-file ownership, activation,
and generic content authority were rejected. The active Matt installation and
allowlist remain governed separately by
`.agents/references/mattpocock_skills_manifest.toml`.

## Typst Package Sources

Package versions are owned by imports in the active Typst sources. These links
only ground the package roles summarized in `typst-toolkit.md` and
`figures-and-tables.md`.

| Source | Adapted local role |
| --- | --- |
| [Glossarium](https://typst.app/universe/package/glossarium/) | Glossary registration and term references through `docs/typst/shared/glossary.typ`. |
| [Booktabs](https://typst.app/universe/package/booktabs/) | Restrained publication-table rules using the version imported by the target document. |
| [Fletcher](https://typst.app/universe/package/fletcher/) | Named-node process, architecture, and relation diagrams; not calibrated coordinate geometry. |
| [CeTZ](https://typst.app/universe/package/cetz/) | Sparse exact vector geometry and Typst-native annotation. |
| [Scenery](https://typst.app/universe/package/scenery/) | Sparse typed 3D vector scenes with explicit painter-order and maturity limitations. |
| [Maquette](https://typst.app/universe/package/maquette/) | Inspected low- or moderate-complexity local mesh rendering; dense geometry remains in a z-buffered raster lane. |

## Official Tool And Accessibility Sources

| Source | Local use |
| --- | --- |
| [Plotly static image export](https://plotly.com/python/static-image-export/) | Static export formats, Kaleido/Chrome dependency, pixel scaling, and rasterized WebGL layers inside vector containers. ARIA's lockfile remains the version owner. |
| [Matplotlib `Figure.savefig`](https://matplotlib.org/stable/api/_as_gen/matplotlib.figure.Figure.savefig.html) | Explicit output format, dimensions, DPI for raster content, background, and metadata. ARIA plot builders remain the implementation owners. |
| [WCAG 2.2](https://www.w3.org/TR/WCAG22/) | Web-oriented text alternatives, use-of-color, and contrast guidance. It is not treated as journal-artwork certification. |
| [Typst image reference](https://typst.app/docs/reference/visualize/image/) | Supported image formats, sizing, and alternative text for included assets. |
| [Rerun blueprints](https://rerun.io/docs/concepts/visualization/blueprints) | Separation of recorded evidence from a reproducible view specification; Rerun implementation remains owned by `rerun-nbv-inspector`. |

## Local Adoption Rule

External sources may inform a workflow, but they do not become ARIA truth
owners. Scientific meaning remains in thesis sources, code, immutable evidence,
and exact papers. Package versions remain in the project lockfile. Local skill
references contain only the smallest adapted rule that changes agent behavior.
