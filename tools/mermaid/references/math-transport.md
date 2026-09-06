# Mathematical source, transport and visible glyphs

The authored Mermaid is an owner-reference language, not copied TeX. The
compiler emits ordinary Mermaid and an optional dependency/hash receipt.

The pinned Mermaid math-label path collapses pairs of backslashes before KaTeX;
the compiler doubles them for transport and the validator decodes that layer
before comparing canonical math. This preserves both commands and mathematical
row separators. Source equations never contain Mermaid transport escaping.

That is not sufficient to guarantee rendered meaning. The same host can turn
raw ampersand/greater-than characters into visible `amp;`/`gt;` during HTML
sanitization. The reviewed shared projections use multi-row `gathered`,
`\gt`/`\lt` where needed, and a one-column `cases` layout with each condition
under its expression. This changes layout, not branch conditions or mathematics.
A canonical equation requiring unsupported alignment must be reflowed at its
owner or rendered natively in Typst; do not strip mathematical tokens downstream.

The browser inspector rejects visible HTML-entity and unprocessed-TeX residues.
It also verifies math fonts, effective sizes and bounds. These regression checks
catch known host failures, not arbitrary mathematical inequivalence. Always
inspect the actual color/grayscale image. Shared source correctness, adapter
identity, render transport and final visual correctness are separate obligations.

Primary upstream paths inspected: Mermaid `rendering-util/createText.ts` and
`diagrams/common/common.ts`. Recheck transport when changing the pinned renderer.
