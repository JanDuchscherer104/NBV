---
id: 2026-08-02_graphify_shared_typst_projection
date: 2026-08-02
title: "Shared Typst Graphify projection smoke"
status: done
topics: [graphify, typst, glossary, projection, verification]
confidence: high
canonical_updates_needed: []
---

## Task

Prepare and execute the bounded local upstream Graphify smoke for the shared
Typst glossary, symbol, and equation projection. The task required an isolated
four-page corpus, an isolated cache/output tree, native-Codex semantic evidence,
and queryable graph proof without a provider backend or optional exports.

## Method

Built the live ignored projection with
`python3 scripts/build_graphify_projection.py --output graphify-input
--aria-code-ref "$(git rev-parse HEAD)"`; it produced 500 Markdown pages.
Copied a closed temporary subset to
`/tmp/aria-nbv-graphify-typst-smoke.Azneea/corpus`:

- `glossary-term:finite-horizon-q-function`;
- `symbol:rl.qh`;
- `equation:rl.q_h`;
- `thesis-source:docs/typst/thesis/sections/05-experimental-design/05-01-objectives-and-hypotheses.typ`.

The temporary copies deleted only links and owner lines whose targets lay outside
the four-page corpus. The thesis page retained its real generated
`uses_symbol: symbol:rl.qh` relation; no link or relation was added. The native
Codex chunk wrote four nodes and three `EXTRACTED` edges to
`/tmp/aria-nbv-graphify-typst-smoke.Azneea/graphify-out/.graphify_chunk_01.json`.
The remaining upstream cache, semantic merge, extraction merge, graph build,
community analysis, JSON export, and report generation used the isolated
`graphify-cache` and `graphify-out` directories.

## Findings

The fresh graph has four nodes, three extracted edges, and two communities. Its
source coverage contains exactly the four dispatched temporary Markdown paths;
no source path lies outside the subset. The public upstream command
`graphify path 'Objectives and Hypotheses' 'Q_H' --graph <fresh graph.json>`
returned the requested traversal:

`Objectives and Hypotheses --references--> Q_H <--references-- Finite-Horizon Q Function --references--> Q_H`.

The two `Q_H` labels are distinct graph nodes: the shared-symbol page and the
shared-equation page. This is expected from their distinct generated identities.

Relevant implementation paths already modified in the worktree, not edited by
this smoke lane, were:

- `scripts/build_graphify_projection.py`;
- `scripts/glossary_build.py`;
- `scripts/tests/test_build_graphify_projection.py`;
- `docs/notation.yml` and generated notation outputs.

## Verification

- Projection build succeeded with 500 ignored Markdown pages.
- The temporary corpus contained exactly four files, three relative Markdown
  links, zero unresolved links, and no symlinks.
- Upstream detection found four documents; cache preparation found zero hits and
  four uncached files. Cache save persisted four semantic entries in the isolated
  cache.
- Graph JSON contains four nodes and three links, all `EXTRACTED`; native chunk
  source coverage is four allowed paths with zero outside paths.
- No Claude, Gemini, or provider API backend was invoked. The semantic chunk was
  supplied by a native Codex host agent; Graphify's remaining local operations
  used the installed upstream `graphifyy` package.

## Canonical-State Impact

No canonical source changed in this verification lane. The graph is advisory
local ingestion evidence only: its LLM-derived relations do not weaken or extend
the deterministic projection contract. No optional SVG, GraphML, wiki, Obsidian,
tree, or call-flow artifact was generated, and no commit or push occurred.

## Review-blocker repair addendum

The canonical glossary contract was clarified after review: `parent` values are
taxonomy slugs rather than glossary identities, while `related` values are
canonical glossary identities. The canonical dangling `vin-nbv` related value
was corrected to `view-introspection-network`; validation now rejects any future
missing related ID. Output validation now includes resolved shared notation
implementation modules before install, and lexical scanners consume complete
dotted notation tokens and permit only the exact `:short` glossary suffix.
