# Source-grounded argument workflow

Read this branch for drafting or revising an academic section, paragraph, or
principal claim.

1. Define the question and intended reader-facing conclusion.
2. Inspect the smallest set of exact source owners that can support it. Record
   identities and locators, not copied excerpts or a second source inventory.
3. Classify each substantive sentence as definition, literature claim,
   implementation fact, design decision, empirical result, limitation, or
   hypothesis. Match verb strength to evidence.
4. Apply the section contract, scan downstream uses of the principal claim,
   and preserve incompatible scopes or contracts as separate claims.
5. Produce accepted prose plus locators, limitations, and a handoff note for
   Typst realization. If validity remains disputed, submit the unchanged
   candidate to `scientific-review`.

For claim-bearing Typst content, the canonical authoring form is an adjacent
non-rendered comment block:

```typst
// evidence:
// - @bib_key -> docs/literature/tex-src/paper/section.tex:82-92 (contribution)
```

The comment and its exact locator are the authoring owner. Graphify may parse
them as a derived projection, but it is not a second evidence store or source
of truth.

This proves traceability and bounded wording; it does not prove novelty,
entailment, causal validity, or statistical sufficiency.
