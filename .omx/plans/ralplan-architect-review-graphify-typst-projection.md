# RALPLAN Architect Review: Graphify Typst Projection

## Verdict

**ITERATE.** The per-entity projection is architecturally sound, but three
behavioral contracts remain ambiguous: eligible usage sources, glossary-use
syntax, and deterministic implementation-owner resolution.

## Strongest steelman antithesis

Grouped registry pages could give upstream semantic extraction better
cross-entity context while avoiding roughly 178 cache entries. The chosen
per-entity design improves identity and provenance but risks fragmented
extraction context and higher ingestion overhead.

## Meaningful tradeoff tension

Stable per-entity provenance and focused invalidation compete with extraction
cohesion and file-count cost. Separately, deterministic Markdown relations are
CI-owned, while Graphify's inferred graph remains advisory; the implementation
must not blur those proof levels.

## Synthesis

Retain per-entity pages because they fit the existing projection framework and
preserve exact provenance. Make the deterministic projection independently
complete, then use the bounded Graphify smoke only as ingestion evidence. Keep
equation-to-symbol dependency edges deferred as planned.

## Ownership and architecture check

Canonical ownership is correctly retained in Typst and `docs/notation.yml`;
generated Markdown and Graphify remain derived. The reuse seam should expose
one normalized validated read model, not an open-ended collection of promoted
parser helpers.

## Required improvements

1. Define usage-source eligibility and exclude non-section closure sources.
2. Specify glossary invocation grammar, aliases, delimiters, and failure rules.
3. Define deterministic, fail-closed implementation-owner resolution.
4. Isolate smoke output and cache state from pre-existing Graphify content.

## Optional improvements

- Add entity-removal coverage proving obsolete pages disappear.
- Record the exact staged path list before publication.
- Measure extraction quality before reconsidering grouped registries or
  equation-to-symbol edges.

## Proof adequacy

**Not yet adequate for implementation handoff.** After the four required
clarifications and matching tests, the proof strategy is sufficient.

## Iteration 2 verdict

**APPROVE.** The revised plan resolves all four required issues. Usage-source
eligibility, glossary invocation semantics, deterministic implementation-owner
resolution, and isolated smoke state are explicit. The proof plan is adequate
for implementation handoff, contingent on fresh execution against the final
implementation.
