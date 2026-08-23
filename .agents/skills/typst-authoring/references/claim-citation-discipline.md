# Claim and citation handoff

## Principal-claim ledger

The principal ledger is a closed, machine-readable index of claim identities,
scope, maturity, review/release state, and structured evidence pointers. Its owner is
`docs/typst/thesis/data/principal-claims.toml`; validate it with
`scripts/check_thesis_claims.py`. Keep it grammar-only: no prose, metrics,
excerpts, conclusions, or copied source text. `repo:` locators must resolve to
safe existing files and line ranges; `bib:` locators must resolve to existing
keys; artifact locators must carry a matching SHA-256 digest. The only claim
enums are `rq`, `contribution`, and `result`; `core`, `conditional-bridge`, and
`future-work`; and `planned`, `implemented`, `pilot`, and `confirmatory`.
Limitations are nonempty repository locators. Evidence records contain only an
evidence class (`design`, `implementation`, `pilot`, or `confirmatory`), an
owner repo locator, and optional bibliography locator.

Surface receipts use one or more locator items, then a local `// evidence:`
record, then `// claims:`. Evidence may combine an exact same-surface repo
locator with an optional valid bibliography locator. The exact surface
membership and any exact occurrence count are owned by the top-level `surfaces`
contracts in the principal ledger; non-parity surfaces may partition their
registered membership across multiple markers. Each principal owner must also
reappear as adjacent same-claim surface evidence on its owner path.
Unknown IDs, duplicate markers, malformed/orphan evidence, wrong ranges, and
stale locators are fail-closed. Planned claims cannot have an artifact;
implemented, pilot, and confirmatory claims require immutable artifacts;
confirmatory maturity requires confirmatory evidence; admissibility additionally
requires current human review and release receipts. Automated receipts are
same-state advisory only, and pilot cannot be promoted to confirmatory.

Read this reference when accepted prose contains a literature, implementation,
empirical, limitation, or future-work claim. `academic-writing` constructs and
scopes the argument; this branch checks that realization preserves supplied
claim strength and citation identity.

- Never invent or silently strengthen a citation, result, causal statement, or
  novelty claim.
- Keep evidence locators beside claim-bearing content where local convention
  requires them. Bibliography and primary-source files remain exact owners; a
  pointer or ledger is not a second evidence store.
- If support is missing or wording exceeds the accepted contract, stop Typst
  realization and hand the candidate back to `academic-writing` or to the
  independent `scientific-review` route.

For a review-only question, load `scientific-review` instead of mutating prose.
