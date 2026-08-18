# Claim And Citation Discipline

## Claim Taxonomy

Every sentence that does scientific work should be classifiable as one of:

1. Definition: introduces a term, symbol, metric, or scope.
2. Literature claim: summarizes prior work and requires citation.
3. Implementation fact: describes code, data flow, or repository behavior.
4. Design decision: explains an architecture, representation, metric, or
   workflow choice.
5. Empirical result: reports measured performance, runtime, ablation outcome,
   or qualitative finding.
6. Limitation: bounds what can be claimed.
7. Hypothesis / future work: explicitly marked as not yet established.

If a claim cannot be classified, it is probably filler.

## Citation Rules

- Never invent citations or bibliography keys.
- Prefer primary sources for methods, datasets, and benchmarks.
- Use review papers only for broad context.
- Avoid citation clusters that do not say what each source contributes.
- Use `[CITATION NEEDED: expected source type]` only as a temporary marker.
- Do not use a citation as a substitute for explaining the connection to
  ARIA-NBV.

## Claim-Level Source Locators

For claim-bearing thesis paragraphs, keep a non-rendered evidence block beside
the paragraph. Use one block per paragraph, figure, table, or equation whose
support differs; do not maintain one distant file-wide list.

```typst
// evidence:
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:82-92 (RRI definition)
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:122-129 (oracle labels)
```

The bibliography key remains the citation identity. The locator records which
local primary-source passage was actually checked for this claim. Prefer exact
line ranges in `docs/literature/tex-src/`; otherwise record a PDF page, section,
figure, or table. A missing local source is an explicit provenance gap, not a
reason to invent a locator.

Use comments as the canonical authoring form because they cannot leak into the
submission render and are easy to audit with repository tools. A development
macro may display parsed provenance, but it must remain a derived view rather
than a second source of truth. Projection tooling may parse these blocks into
derived Graphify edges after resolving the bibliography key through
`docs/references.bib`, `docs/references-qh.bib`, and
`docs/literature/sources.jsonl`.

## Evidence Gate

For each non-obvious claim, verify at least one evidence path:

- `@bib_key` in `docs/references.bib`;
- code path or generated context artifact;
- table/figure/result in `docs/typst/shared/data`;
- explicit limitation or hypothesis wording.

For advisor-facing scientific claims, complete this direct-source check:

1. Classify the claim using the taxonomy above.
2. Resolve every literature citation in `docs/references.bib` and inspect the
   cited paper, authoritative TeX source, or PDF at the exact relevant locator.
3. For implementation facts, inspect the defining code, its tests, and active
   configuration. For results, inspect the immutable measurement manifest,
   table, or figure source.
4. Downgrade unsupported wording, add the missing evidence, or mark the claim
   as a hypothesis or limitation before treating it as supported.

This check is unnecessary for skill-only edits or purely mechanical Typst fixes.

For non-trivial sections, build a scratch claim ledger before final prose. Use
`assets/templates/claim-ledger.md` to track paragraph, claim type, evidence
path, citation/result, and status. The ledger is an authoring artifact, not a
required final thesis table.

For empirical claims, also apply
`empirical-reporting-and-reproducibility.md`; a citation does not substitute for
run-level result provenance.

## Hedging

Use strong verbs only when the evidence is strong:

- demonstrates / shows: direct empirical evidence;
- suggests / indicates: indirect evidence or limited samples;
- may / could: hypotheses and future work.

Do not stack hedges.

## Results Prose Pattern

Use claim-first paragraphs:

```text
The VIN proxy ranks oracle-preferred candidates more reliably after adding semi-dense projection features. In the offline validation split, ... . This improvement is consistent with the feature design, because ... .
```

Avoid procedure-first prose:

```text
We trained the model and then evaluated the predictions. Figure X shows the results.
```

## Related-Work Paragraph Protocol

For each related-work paragraph:

1. name the subfield;
2. identify what prior work contributes;
3. state the unresolved limitation relative to ARIA-NBV;
4. cite specific sources;
5. avoid generic openings such as "many works have explored".

Useful local searches:

```bash
make context-literature-index
make context-literature-search LITERATURE_SEARCH_QUERY='next best view learned reconstruction'
rg -n 'GenNBV|VIN-NBV|NBV' docs/references.bib docs/literature docs/_generated/context
```
