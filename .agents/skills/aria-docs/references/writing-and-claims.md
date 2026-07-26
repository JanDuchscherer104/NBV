# Writing And Claims

Use this branch for thesis or proposal prose, section structure, citations,
captions that make scientific claims, and advisor-facing revisions. The active
Typst thesis owns the narrative; direct code, evidence artifacts, and papers
own the facts it interprets.

## Drafting Modes

- **Fragment capture:** collect observations, candidate claims, objections,
  evidence gaps, and possible wording before structure exists.
- **Shape pass:** turn a fixed evidence set into scoped claims and paragraphs;
  mark missing support instead of fabricating it.
- **Beat pass:** improve the reader journey one move at a time: motivation,
  gap, method consequence, evidence, limitation, or transition.

Use the smallest mode that matches the draft state. Outline claims, scope,
evidence, limitations, and citations before polishing final paragraphs.

## Claim Discipline

Classify every substantive sentence as a definition, literature claim,
implementation fact, design decision, empirical result, limitation, or
hypothesis/future work. Unclassifiable prose is usually filler.

- Literature claims resolve to an exact primary source and locator; never
  invent a citation key.
- Implementation claims resolve to current code, tests, and active configs.
- Empirical claims resolve to immutable evidence and name the split, metric,
  aggregation, uncertainty, and limitation needed for interpretation.
- Report measured facts before causal interpretation.
- Use strong verbs only for direct evidence; calibrate limited evidence as a
  suggestion or hypothesis.
- Apply `.agents/references/direct_source_claim_checklist.md` to
  advisor-facing claims.

Use `#gh` only for final-worthy pinned code anchors. Use `#gh-wip` and
`#gh-symbol` as removable drafting links under
`.agents/references/thesis_code_links.md`.

## Paragraph Check

Each paragraph needs one job, a concrete claim, supporting evidence, explicit
scope, consistent terms or notation, and a transition when another paragraph
follows. Finish in connected prose unless the document structure genuinely
calls for a list. Review in this order: correctness, structure, evidence, then
style.
