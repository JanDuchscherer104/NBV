---
name: aria-nbv-mermaid
description: "Use for ARIA-NBV conceptual diagrams and SVGs: explanatory-depth review, Mermaid/Typst routing, Mermaid source and rendering, and interactive thesis-figure research packets."
---

# ARIA-NBV Conceptual Diagrams

Own the cross-renderer conceptual-diagram contract: decide what a figure must
explain, whether it deserves to exist, and which renderer fits the mechanism.
Retain the repository's canonical Mermaid seam; route accepted Typst-native
realization and document integration to `typst-authoring`.

## Use When

- Reviewing, retaining, simplifying, revising, replacing, merging, or removing
  an ARIA-NBV conceptual figure or SVG.
- Routing a concept to Mermaid-native, Typst-native, scientific/data, or no
  figure.
- Creating, editing, linting, or rendering repository `.mmd` source.
- Preparing an iterative thesis-figure research packet.

## Read First

1. Read `AGENTS.md`, `docs/AGENTS.md`, and the exact thesis passage or software
   contract the figure explains.
2. For conceptual review or Mermaid-vs-Typst selection, read
   [conceptual-diagrams.md](references/conceptual-diagrams.md).
3. For iterative visual research, also read
   [interactive-figure-research.md](references/interactive-figure-research.md).
4. For Mermaid-native source or rendering, read
   [mermaid-native.md](references/mermaid-native.md).
5. For mathematical notation, inspect `docs/typst/shared`; for a Typst-native
   candidate, load `typst-authoring` and its scientific-visualization guidance.
6. For current upstream API details, use `aria-nbv-context`'s Context7 route
   after local owner inspection. The local pinned package and exact render remain
   decisive.

## Ownership Boundary

- This skill owns the figure question, explanatory standard, handoff into the
  owning renderer policy, cross-renderer review packet, and Mermaid-native work.
- `tools/mermaid` is the sole Mermaid lint/render implementation. Keep `.mmd` as
  the source of record; do not add another CLI wrapper.
- `typst-authoring` owns the exact Typst/scientific renderer decision, accepted
  source realization, captions, labels, inclusion, compilation, rendered-page
  inspection, and PDF handoff.
- `scientific-review` independently tests claims, geometry, notation, and
  caption--figure entailment. It advises; the implementation lane patches valid
  findings.
- Data/code owners determine quantitative values and geometry. A diagram never
  promotes a hypothesis, implementation, or result beyond those owners.

## Workflow

1. Write the concept brief: exact source/passages, one reader takeaway, likely
   misconception, and what the visual can show that prose cannot.
2. Freeze a baseline at actual thesis page size. Search all consumers and
   classify the source/render family as active, superseded, orphaned, or
   development-only.
3. Judge the figure using both professor and student lenses from the reference.
   Choose `retain`, `simplify`, `revise`, `replace`, `merge`, or `remove`.
4. Route relational figures to Mermaid-native or Typst-native work. Route
   scientific, geometric, spatial, 3D, and quantitative figures to
   `typst-authoring`, whose scientific-visualization table selects the renderer.
5. For a review/report request, return the classification, severity-ranked
   findings, and recommendations without mutation or external publication.
6. For an authorized change/build request, implement one bounded accepted
   action through the owning skill. A retained/no-change figure only receives a
   recorded disposition. Remove a superseded family only after proving its
   consumers and complete source/render boundary.
7. For retained or changed candidates, inspect the standalone asset and final
   pages for reading order, notation, clipping, final-size text, grayscale,
   caption complementarity, and unsupported implications.
8. Run an independent scientific review on the exact candidate. Patch valid
   P0--P2 findings only in an authorized implementation lane.

## Completion

Report the concept and decision, canonical source, guidance that affected the
design, exact lint/compile/render checks, inspected thesis pages, scientific
review disposition, and any remaining owner handoff.
