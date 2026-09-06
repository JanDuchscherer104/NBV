---
name: aria-nbv-mermaid
description: Author mathematical ARIA-NBV diagrams with direct Typst symbol/equation references, generate Mermaid from the canonical projection, and validate scientific meaning and final-size readability.
---

# Mathematical Mermaid Figures

**Symbols carry data; equations carry transformations; edges carry dependencies;
captions carry qualifications.** A heading, English function call or protocol
name is not a substitute for the mathematical mechanism.

## Owner-first route

Read root/nearest `AGENTS.md`, the exact passage and implementation. Use
`docs/typst/shared/symbols.typ`, `equations.typ` and their domain modules for
meaning. `docs/notation.yml` is only the generated TeX projection; its `typst`
fields identify the exact owners. Do not create another symbol dictionary.

Load only the relevant reference:

- [Direct-reference syntax, mathematical grammar and sizing](../../../tools/mermaid/references/symbolic-style.md).
- [Scientific and cold-reader review](references/figure-review.md).
- [Bounded iteration and Mermaid Chart](references/iteration.md).
- New notation, dense mathematics, spatial geometry and final PDF: `typst-authoring`.

The seminar diagrams are composition baselines, not current model evidence.
Keep selected implementations, privileged controls and proposed architectures
visibly distinct. Do not change scientific dependencies to improve layout.

## Authoring contract

Start from `tools/mermaid/templates/flowchart_symbolic.mmd`. New architecture
sources require `%% aria-notation: typst` and
`%% aria-architecture: symbolic-computational`.

```mermaid
State["<b>Memory</b>$$#symb.scene.scene_memory_t$$"]:::data
Pools["<b>Pooling</b>$$#eqs.scene.candidate_query_pools$$"]:::compute
```

Every math block is **one complete exported Typst name**. Data uses `#symb`;
processes use `#eqs`. No copied TeX, local alias, suffix manipulation, expression
slicing or `<code>` escape hatch. Split reusable equation rows at their shared
Typst owner, then regenerate its adapters. Whole-equation references can contain
sets, intersections, expectations, cases, sums, products and update rules; these
are mathematical operations, not decoration.

Keep one- or two-word bold CMU Serif headings outside math. Use the full
mathematical expression beneath them; explain prerequisites in the section and
limitations in the caption. Retain sets and case conditions that give the
expression its meaning. Abbreviated projections must be repaired at the owner,
not silently trusted because a spelling check passes.

## Compile and verify

```sh
python3 tools/mermaid/scripts/aria_mermaid_owners.py path/to/figure.mmd \
  --output /tmp/figure.mmd --receipt /tmp/figure.refs.json
python3 tools/mermaid/scripts/aria_mermaid_lint.py /tmp/figure.mmd
python3 -W error -m unittest discover -s scripts/tests -p 'test_aria_mermaid_*.py'
tools/mermaid/scripts/render_mermaid.sh path/to/figure.mmd /tmp/figure.svg
node tools/mermaid/scripts/inspect_mermaid.mjs /tmp/figure.svg 160 /tmp/figure
```

The existing render wrapper resolves owner references automatically. The authored
`.mmd` is canonical; generated plain Mermaid and hash receipts are build evidence.
Send **generated** Mermaid to the official Mermaid Chart `display_mermaid` tool
or GitHub fences. Neither host understands project Typst identifiers itself.
A successful tool response is not a rendering or font-validation certificate.

Use the professor/student loop on actual artifacts. Inspect mathematical fonts,
indices, set membership, case branches and domains as well as physical sizes,
clipping and grayscale. A self-review is not independent approval. Reflow or
split a formula-heavy view before shrinking the type; one shared equation can
teach more than ten labelled boxes.

## Completion

Report exact owners, notation-regeneration evidence, direct-reference tests,
rendered math/font/size checks and inspected images. Final thesis inclusion still
requires destination-source consistency, caption/include/cross-reference and
PDF-page QA. Do not claim arbitrary Typst syntax runs inside Mermaid: only
registered `#symb`/`#eqs` projections are supported. Use native Typst for math that
its KaTeX projection cannot faithfully express.
