# Conceptual Diagram Review And Design

## Start With The Explanatory Job

Before drawing, record:

- the exact thesis concept and canonical source passages;
- the one insight the reader should gain;
- the misconception or hidden distinction the figure should expose;
- the visual operation that prose cannot provide: topology, comparison,
  coordinate relation, causal boundary, or quantitative pattern.

If none exists, remove the figure. A polished inventory of boxes is not an
argument.

## Classify Before Editing

Classify the complete source/render family as `active`, `superseded`,
`orphaned`, or `development-only`, then choose one action:

- `retain`: already correct, necessary, and legible;
- `simplify`: correct but visually redundant or cognitively overloaded;
- `revise`: the concept is necessary but its encoding is weak or ambiguous;
- `replace`: the current visual grammar cannot express the concept faithfully;
- `merge`: two figures divide one comparison or mechanism without benefit;
- `remove`: no active consumer, no unique insight, or unsafe competing truth.

Never improve an obsolete asset merely because it looks unfinished. Prove its
consumer and claim owner first.

## Renderer Handoff

| Explanatory need | Handoff | Required discipline |
| --- | --- | --- |
| Mermaid-native Quarto/docs topology or intentional `.mmd` asset | This skill plus `tools/mermaid` | Versioned `.mmd`, local lint/render, compact labels, canonical class contrast |
| Typst-native relational or mathematical figure | `typst-authoring` | Named relations, editable notation, final-page compilation and inspection |
| Scientific geometry, spatial/3D scene, or quantitative evidence | `typst-authoring` scientific-visualization route plus the data/code owner | Declared provenance, frames/units/scales, deterministic regeneration |
| No unique visual operation | Prose/table/remove | Do not create a decorative diagram |

The exact Fletcher, CeTZ, Scenery, Maquette, Matplotlib, Plotly, or Rerun choice
belongs only to
[`scientific-visualizations.md`](../../typst-authoring/references/scientific-visualizations.md#renderer-routing).
One figure still needs one coherent coordinate and typography system.

## Two Review Lenses

### Professor

- Are geometry, frames, transforms, branch predicates, and information
  boundaries correct?
- Does the visual add conceptual or argumentative value?
- Does it distinguish implemented facts, measured evidence, assumptions, and
  prospective hypotheses?
- Do figure and caption jointly entail the adjacent claim without overstating
  causality or empirical support?

### Student

- Is the reading order obvious without first reading the caption?
- Which label, edge, or group will be misunderstood on first encounter?
- Is the cognitive load spent on the thesis distinction or on decoding layout?
- Can shape, stroke, position, and wording preserve meaning without color?

## Mechanism-Rich Patterns

- Give every edge a real meaning: transform, data dependency, branch predicate,
  supervision path, or causal/information boundary.
- Use named anchors and semantic constructors so layout follows relations rather
  than arbitrary screen coordinates.
- Use an enclosure only when membership itself matters. Label the enclosure's
  role, not merely its implementation name.
- Show the comparison or counterfactual that produces insight: legal versus
  privileged input, greedy versus lookahead return, primitive distance versus
  reductions, retained versus pruned branch.
- Pair an occluded context view with a complete-domain or orthographic view when
  spatial support would otherwise be hidden.
- Use a shared visual vocabulary so repeated colors, shapes, and strokes keep
  the same meaning. Reinforce color with at least one non-color channel.
- Keep labels direct and compact; move interpretation to the caption and
  adjacent prose instead of shrinking paragraphs into nodes.

## Do Not

- reproduce paragraph order as a generic left-to-right box chain;
- use decorative pseudo-3D or perspective without a declared camera/projection;
- imply an unimplemented module, richer actor state, measured effect, or causal
  result;
- encode semantics by color alone or use unlabeled ambiguous arrows;
- preserve generated SVG/PDF as a parallel source of truth;
- copy upstream artwork or coordinates. Adapt reusable visual grammar only;
- accept a standalone render without inspecting the final page and grayscale.

## Guidance Record (2026-08-30)

The Context7 app was queried first with the user-specified library targets and
scoped questions. Exact IDs remain centralized in the
[Context7 registry](../../aria-nbv-context/references/context7_library_ids.md).
The following guidance affected this workflow:

- Fletcher query: "Scientific architecture diagrams using reusable node styles,
  anchors, semantic grouping, orthogonal edge routing, edge labels, branches,
  skip connections, and final-size legibility." Retrieved named nodes, relative
  anchors, enclosures,
  reusable defaults, labelled multi-segment edges, and explicit layers support
  semantic topology and skip/branch paths.
- CeTZ 0.4.2 query: "Geometrically correct scientific diagrams using coordinate
  transformations, camera frames, frustums, rays, planes, projections, clipping,
  layers, intersections, annotations, and reusable styles." Retrieved coordinate
  transforms, anchors, intersections,
  clipping, and layers support derived geometry rather than decorative placement.
- Typst documentation query: "Reusable vector figure functions, captions,
  labels, references, layout measurement, scaling, consistent typography,
  accessibility, and reliable PDF output." Retrieved reusable functions,
  measurement/alignment, explicit sizing, labels/references, figure alternative
  text, and deterministic PDF output support final-page and accessibility QA.
- Typst community extra-docs query: "Advanced relative positioning,
  measurement, alignment, reusable layout patterns, and debugging complex
  scientific figures." The result contained little relevant figure guidance and
  did not affect a design decision beyond confirming local pinned examples must
  remain decisive.

Context7 did not expose the repository-pinned Fletcher `0.5.8` or CeTZ `0.5.2`
IDs. Therefore exact local imports and these primary sources determine API
compatibility:

- Fletcher 0.5.8 package and gallery:
  <https://github.com/typst/packages/tree/main/packages/preview/fletcher/0.5.8>
  and
  <https://raw.githubusercontent.com/typst/packages/main/packages/preview/fletcher/0.5.8/docs/gallery/03-ml-architecture.typ>
- Fletcher upstream: <https://github.com/Jollywatt/typst-fletcher>
- CeTZ upstream and repository-pinned `0.5.2` local examples:
  <https://github.com/cetz-package/cetz>
- Open-source comparison corpus: <https://github.com/janosh/diagrams>

The Fletcher ML example influenced reusable semantic node constructors and
explicit skip paths. CeTZ examples influenced coordinate-derived construction,
named anchors, intersections, and direct annotations. Janosh's diagrams
influenced shared visual vocabularies and mechanism-first layouts. The SLAM
Handbook, PLOS Ten Simple Rules, Claus Wilke, and Distill are exposition
guidance only; cite domain sources, not these guides, for thesis claims.
