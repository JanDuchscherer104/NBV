# PRD: Minimal shared-Typst projection for Graphify

## Requirements summary

Extend ARIA-NBV's existing deterministic Markdown projection so upstream
Graphify can ingest glossary terms, shared symbols, shared equations, and their
uses in the active thesis Typst closure. Keep canonical content in Typst and
`docs/notation.yml`; keep the projection and graph derived-only; do not modify
the byte-identical upstream Graphify bundle or add a repository-owned graph,
cache, schema, or provider backend.

The implementation targets a new PR from `codex/graphify-typst-projection` to
`main`. It does not commit `graphify-input/`, `graphify-out/`, caches, or optional
exports.

## RALPLAN-DR summary

### Principles

1. Canonical owners remain canonical; generated Markdown only exposes stable
   identities, provenance, and relations.
2. Deterministic projection contracts are CI invariants; LLM-produced graph
   details are bounded local evidence, not CI truth.
3. Reuse existing glossary/notation validation instead of introducing a second
   parser or ontology.
4. Preserve upstream Graphify byte identity and native ingestion behavior.
5. Prefer the smallest reviewable extension to the existing projection builder.

### Decision drivers

1. Stable queryable identities and explicit source-linked usage edges.
2. Drift prevention across `glossary.typ`, shared Typst facades, and
   `docs/notation.yml`.
3. Low maintenance cost and no expansion of ARIA-owned Graphify machinery.

### Viable options

#### Option A — one generated Markdown page per term/symbol/equation (chosen)

Pros:

- stable identity and `source_file` provenance for every concept;
- ordinary relative Markdown links express deterministic relations;
- uses the existing `_Page`/slug/link/install framework;
- focused cache invalidation when one entity changes.

Cons:

- roughly 178 additional small Markdown files on the current corpus;
- semantic ingestion has more file-level cache entries.

#### Option B — three registry pages with one heading per entity

Pros:

- fewer generated files and fewer semantic cache entries;
- related entities share extraction context.

Cons:

- Graphify provenance collapses many concepts onto three files;
- heading-anchor identity and link validation require new projection machinery;
- small edits invalidate large registry pages.

#### Option C — ingest raw Typst/YAML directly

Pros:

- no generated entity pages.

Cons:

- upstream Graphify does not own ARIA-specific Typst/Glossarium semantics;
- raw files are intentionally excluded by `.graphifyignore`;
- it would weaken source-role clarity and make extraction nondeterministic.

Option C is invalidated by the accepted source-order and corpus-boundary
contracts. Option B remains viable but loses the stable per-entity provenance
that motivates this change.

## Target contract

### Canonical inputs

- `docs/typst/shared/glossary.typ`: term IDs, labels, definitions, aliases,
  parent taxonomy labels, related term IDs, citations, internal links, `symbol_refs`, and
  `equation_refs`.
- `docs/notation.yml`: stable symbol/equation keys, TeX, Typst expressions,
  descriptions, and list metadata.
- `docs/typst/shared/symbols/*.typ` and `equations/*.typ`: executable Typst
  implementation owners, reached through the shared facades.
- the active closure rooted at `docs/typst/thesis/main.typ`: source discovery;
- files in that closure below `docs/typst/thesis/sections/`: usage sources.

### Generated identities

- `glossary-term:<term-id>` under `graphify-input/glossary/`;
- `symbol:<notation-key>` under `graphify-input/symbols/`;
- `equation:<notation-key>` under `graphify-input/equations/`;
- existing `thesis-source:<path>`, citation, literature, code, and asset
  identities remain unchanged.

Each entity page contains only normalized canonical metadata, relative links to
other generated identities, and human-provenance links to exact owners. Generated
files never claim ownership.

### Deterministic edges

- thesis source `uses_term` glossary term, with lexical multiplicity;
- thesis source `uses_symbol` symbol, with lexical multiplicity;
- thesis source `uses_equation` equation, with lexical multiplicity;
- glossary term `parent_label` taxonomy metadata and strict `related` glossary-term edges;
- glossary term `symbol_ref` and `equation_ref` notation entities;
- glossary term `citation` existing citation identities;
- symbol/equation `implementation_owner` exact shared Typst module plus
  `metadata_owner` `docs/notation.yml`.

Usage scanning applies `_strip_typst_noncode` and emits usage edges only for
active-closure files below `docs/typst/thesis/sections/`. The root file, shared
facades, registries, and implementation modules may establish closure or
ownership but never emit section-usage edges.

Glossary usage recognizes `@<term-id>` and `@<term-id>:short`, where `<term-id>`
is an exact canonical glossary ID. Aliases are metadata, not invocation IDs.
Matches use the same punctuation-safe token boundary as bibliography citations;
`:short` is presentation metadata and maps to the base term identity. A
glossary ID colliding with a bibliography key fails as ambiguous. An unknown
`@...:short` fails with source and line; other unknown `@...` tokens retain the
existing compiled bibliography validation path rather than being guessed as
terms.

Symbol and equation usage matches known keys with delimiter-safe patterns,
counts repeated uses, and rejects unresolved `#symb.*` or `#eqs.*` references
with source and line. Sentence punctuation must not become part of a key.

Implementation ownership is derived only from a notation entry whose `typst`
field exactly matches `#symb.<namespace>.<member>` or
`#eqs.<namespace>.<member>`. It resolves to the corresponding
`docs/typst/shared/symbols/<namespace>.typ` or
`docs/typst/shared/equations/<namespace>.typ`, and the module must declare the
member in its exported dictionary. A malformed expression, missing module,
missing member, or multiple candidate declaration fails closed with the
notation key and candidate paths. Shared equation-to-symbol dependencies are
deferred: they are useful, but not required by the user's section-usage scope
and would expand the parser beyond the minimal seam.

### Reuse boundary

Promote the smallest glossary-building helpers needed to load/normalize/validate
queried terms and notation metadata from `scripts/glossary_build.py`, or expose
one narrow public model-loading surface there. `build_graphify_projection.py`
continues to own projection identity/rendering/install behavior and routes Typst
queries through its injected runner so hermetic tests remain hermetic.

## Acceptance criteria

1. A fixture with two terms, two symbols, and two equations produces stable
   per-entity pages and unchanged bytes across two builds.
2. Active thesis section pages link to every used term/symbol/equation with exact
   lexical multiplicity; the thesis root, shared owners, inactive files,
   comments, raw blocks, and import statements do not create usage edges.
3. `#symb.rl.qh.` resolves to `symbol:rl.qh`, never `symbol:rl.qh.`.
4. Unknown `#symb.*`, `#eqs.*`, or `@...:short` usage in an eligible section
   fails closed with source path and line; ambiguous glossary/bibliography IDs
   and unknown glossary metadata refs also fail closed.
5. Entity pages link to exact canonical metadata and Typst implementation owners;
   all generated relative Markdown links validate.
6. `graphify-input/index.md` records glossary/notation owners and family counts,
   so their mutation invalidates freshness.
7. Existing citation, literature, code-link, output-swap, symlink-safety, and
   deterministic-render tests remain green.
8. `scripts/glossary_build.py validate` still reports the live canonical counts
   and generated glossary behavior remains byte-compatible unless an intentional
   helper-only refactor requires no output changes.
9. A bounded local upstream Graphify smoke ingests representative generated term,
   symbol, equation, and thesis pages, accounts for every dispatched file, and
   yields at least the representative usage/reference path. This evidence is
   recorded in the debrief, not asserted in CI.
10. `.agents/skills/graphify/**` is byte-identical to `origin/main`; no Claude,
    Gemini, or provider API backend is used.
11. Focused tests, `make check-agent-memory`, `git diff --check`, and the final
    independent review gates pass before publication.

## Implementation steps

1. In `scripts/glossary_build.py:48-275`, expose the smallest reusable
   normalization/validation surface without changing generated outputs.
2. In `scripts/build_graphify_projection.py:31-140`, add canonical glossary and
   notation inputs plus typed render data/page families.
3. Near `scripts/build_graphify_projection.py:190-310`, add delimiter-safe active
   closure usage extraction beside existing comment/raw stripping and lexical
   citation extraction.
4. Near `scripts/build_graphify_projection.py:817-1125`, render per-entity pages,
   explicit links/multiplicities, owner provenance, and index family counts.
5. In `scripts/tests/test_build_graphify_projection.py`, extend the hermetic
   fixture and add contract tests for identities, relations, multiplicity,
   punctuation, exclusions, unknown keys, owner digests, and unchanged legacy
   behavior.
6. Run the deterministic verification and bounded native-Codex upstream ingestion
   smoke; do not generate optional exports or commit generated graph artifacts.
7. Record the non-trivial work under `.agents/memory/history/2026/08/`, execute
   final cleanup/review gates, then commit, push, and open a draft PR to `main`.

## Risks and mitigations

- **Parser duplication:** share glossary validation helpers; do not reimplement
  the Glossarium model in the projection.
- **False lexical matches:** match only known stable keys, apply source cleaning,
  and test punctuation/comments/raw/import boundaries.
- **Projection explosion:** keep pages small, deterministic, ignored, and limited
  to the active canonical registries.
- **LLM ingestion variance:** keep CI on projection contracts and treat one
  bounded upstream smoke as advisory evidence.
- **Owner ambiguity:** encode both metadata owner and executable Typst owner;
  generated pages explicitly say they are derived.
- **Concurrent repository work:** remain in the dedicated clean worktree and
  rebase/fast-forward only through non-destructive Git operations.

## ADR

### Decision

Generate one small deterministic Markdown page per glossary term, symbol, and
equation, and link active thesis source pages to the notation they use.

### Drivers

Stable provenance, exact-source ownership, deterministic testing, and upstream
Graphify compatibility.

### Alternatives considered

Grouped registry pages and direct raw Typst/YAML ingestion.

### Why chosen

Per-entity pages fit the existing projection primitives and provide the clearest
stable Graphify ingestion unit without custom graph construction.

### Consequences

The ignored projection gains about 178 small files and corresponding semantic
cache entries. Changes to canonical registry entries now invalidate only their
content-addressed projections. Graphify remains optional and derived.

### Follow-ups

Measure whether equation-to-symbol dependency edges materially improve real
queries before expanding the lexical model. Keep optional HTML/tree/call-flow
exports on demand and continue skipping SVG/GraphML/wiki/Obsidian by default.

## Available agent types and follow-up staffing

Available relevant roles: `planner`, `architect`, `critic`, `executor`,
`test-engineer`, `verifier`, `code-reviewer`, and `code-simplifier`.

- Ultragoal leader: current root agent, high reasoning; owns goals, integration,
  checkpoints, and Git publication.
- Implementation lane: one `executor`, medium reasoning, may own the two scripts
  and projection tests if delegation materially helps.
- Verification lane: one `test-engineer` or `verifier`, high reasoning, owns
  focused regression evidence and ingestion-smoke audit.
- Final gate: distinct `code-reviewer` high and `architect` xhigh, sequentially
  independent of the implementation lane.

The work is compact and overlapping, so default execution is sequential
Ultragoal rather than Team. If implementation and ingestion proof become
independent, a Team launch may use:

```text
$team 2:executor "Implement .omx/plans/prd-graphify-typst-projection.md; lane 1 owns projection/helpers/tests, lane 2 owns bounded ingestion verification only."
```

Team must return changed-path ownership, focused test output, ingestion coverage,
and blockers before shutdown; the Ultragoal leader independently integrates and
checkpoints that evidence. `$ralph` is only a fallback if a persistent
single-owner fix/verify loop is explicitly selected after failed verification.

## Review-blocker clarification (2026-08-02)

Canonical glossary evidence distinguishes `parent` taxonomy slugs from entity
references: `parent` is validated as a lowercase hyphenated taxonomy label and
rendered only as `parent_label`; every `related` value is a canonical glossary
ID and fails validation when missing. The previous `vin-nbv` dangling related
value is corrected to `view-introspection-network`. Projection output safety
resolves all notation implementation owners before validating the output path,
so an output cannot overlap a shared symbol or equation module.

## Goal-mode follow-up suggestions

- `$ultragoal` is the selected durable implementation and verification path.
- `$team` is optional only if the work separates cleanly into implementation and
  ingestion-evidence lanes.
- `$autoresearch-goal` is not appropriate: this is implementation, not a research
  deliverable.
- `$performance-goal` is not appropriate unless later work measures projection or
  extraction performance.

## Consensus improvement changelog

- Architect iteration 1: limited usage edges to active files below the thesis
  sections root; specified exact glossary grammar, alias and ambiguity rules;
  made notation implementation-owner resolution exact and fail-closed; required
  an isolated temporary smoke corpus, output, and cache.
- Architect iteration 2: APPROVE with no remaining required issues; proof plan
  is adequate contingent on fresh implementation evidence.
- Critic: APPROVE with no required issues; added an optional final-diff audit for
  provider/backend imports or configuration.
