# Claim Ledger Template

This scratch template is for claim-level planning only. The released principal
claims contract is the machine-readable
`docs/typst/thesis/data/principal-claims.toml` ledger, validated by
`scripts/check_thesis_claims.py`.

Use this as scratch scaffolding for non-trivial thesis/proposal sections.
Do not paste the ledger into final advisor-facing prose unless explicitly
requested.

| Paragraph | Claim type | Claim | Evidence owner | Citation/result | Status |
| --- | --- | --- | --- | --- | --- |
| P1 | Literature claim | Prior work uses ... | `docs/references.bib:@key` | `@key` | unchecked |
| P2 | Design decision | ARIA-NBV separates actor-visible state from oracle labels. | roadmap/questions/shared notation | internal docs | checked |
| P3 | Implementation fact | The current repository stores ... | code path or generated context | path/result | unchecked |
| P4 | Limitation | This does not establish continuous-control deployment. | thesis boundary | none needed | checked |

Use only the approved enums (`rq`, `contribution`, `result`; `core`,
`conditional-bridge`, `future-work`; `planned`, `implemented`, `pilot`,
`confirmatory`) and grammar-constrained repository/bibliography locators in
the machine-readable ledger. Limitations are nonempty `repo:path:start-end`
locators. Evidence is a table with `class` (`design`, `implementation`,
`pilot`, or `confirmatory`) and an `owner` repo locator, plus optional
`bibliography`; it has no semantic identity field. Do not copy prose, metrics,
excerpts, conclusions, or source text into that ledger.

Active-surface markers have one or more locator items first, then `// evidence:`,
then `// claims: <id>[, <id>...]`. Locator items may include same-surface repo
evidence and optional valid bibliography evidence; a repo item must end before
its marker and be within the documented four-line adjacency gap. Empty receipts
are valid for the planned/unreviewed/withheld ledger; automated receipts are
same-state advisory only. Human maturity transitions are closed and
dimension-aware, while review and release receipts update their own states.
Planned claims have no artifact; all later maturity states require an immutable
SHA-256 artifact, and confirmatory maturity requires confirmatory evidence.
The ledger's top-level `surfaces` contracts own registered membership and any
exact occurrence count; non-parity surfaces may partition that membership across
markers. Every principal owner must be represented by adjacent same-claim repo
evidence on its owner path.
