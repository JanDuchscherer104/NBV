---
name: aria-nbv-context
description: Use to localize unknown ARIA-NBV owners through deterministic discovery or optional semantic recall of prior decisions, related work, and failed approaches before handoff.
metadata:
  mode: router
  not_when:
    - "exact file and owner are already known"
    - "a concrete failure command or traceback owns the task"
  handoff_to:
    - "graphify for an existing usable graph"
    - "typst-authoring for thesis, glossary, shared-symbol, or shared-equation edits"
    - "nearest owning guide for concrete failures"
    - "nearest AGENTS.md or narrow skill after localization"
  evidence_required:
    - "localized owning files or source family"
    - "nearest applicable AGENTS.md"
    - "targeted rg or generated context evidence"
    - "freshness evidence before any Graphify-backed claim"
    - "exact-source verification after any MemPalace result"
    - "active thesis or shared scientific-language owner for thesis-facing terms"
  applies_to:
    - "**"
  triggers:
    - "locate files"
    - "cross-surface context"
    - "where is this implemented"
    - "source family"
    - "thesis section, glossary, symbol, equation, or notation owner"
    - "codebase architecture, file relationships, or project-content questions"
    - "semantic recall of prior decisions, related work, or failed approaches"
  must_read:
    - "AGENTS.md"
    - ".agents/references/source_order.md"
  canonical_sources:
    - "AGENTS.md"
    - ".agents/references/source_order.md#role-split"
    - ".agents/skills/aria-nbv-context/references/context_map.md"
    - ".agents/skills/aria-nbv-context/references/graphify-aria-boundary.md"
    - ".agents/skills/aria-nbv-context/references/context7_library_ids.md"
    - "docs/typst/thesis/main.typ"
    - "docs/typst/shared/glossary.typ"
    - "docs/typst/shared/symbols.typ"
    - "docs/typst/shared/equations.typ"
    - "docs/notation.yml"
    - ".graphifyignore"
    - "docs/literature/README.md#optional-graphify-projection"
  literature_refs:
    - "docs/contents/literature/index.qmd"
    - "docs/literature/sources.jsonl"
    - "quality-driven-rri"
    - "finite-candidate-rl"
  tool_refs:
    - "mcp__MCP_DOCKER.resolve_library_id"
    - "mcp__MCP_DOCKER.get_library_docs"
    - "mcp__code_index.search_code_advanced"
    - "mcp__code_index.get_symbol_body"
  verification:
    - "make context when generated context is stale or missing"
    - "python3 scripts/check_graphify_freshness.py --json before Graphify-backed claims"
    - "make graphify-state-check for strict scaffold validation"
---

# Aria NBV Context

## Graphify branch

For architecture, relationship, or broad project-content discovery, treat an
existing `graphify-out/graph.json` as the default trusted retrieval index. Run
`python3 scripts/check_graphify_freshness.py --json`; whenever the result says
`usable: true`, including `structural-stale` or `semantic-stale`, hand off to the
byte-identical upstream skill at `.agents/skills/graphify/SKILL.md`. Query
Graphify first; its provenance and `source_location` route the exact-source
check. Verify consequential `stale_sources` claims directly; only `missing` or
`invalid` states bypass Graphify entirely.

Freshness validates rather than globally gates reads. `make graphify-state-check`
remains strict for scaffold and pre-push validation; `make graphify-usable-check`
proves ordinary query safety. A Git HEAD mismatch alone is not staleness when the
recorded graph and projection revisions are ancestors and indexed bytes still
match. Refreshes first regenerate the deterministic projection with
`scripts/build_graphify_projection.py`. Native semantic refreshes use
`fork_turns="none"` and require every dispatched file to be accounted for.

Before any build or semantic refresh, read
[`references/graphify-aria-boundary.md`](references/graphify-aria-boundary.md),
which owns ARIA's projection, upstream-only, coverage, marker, and linked-worktree
rules. Leave incomplete or unreconciled graphs strict-gate stale, keep the last
valid snapshot queryable, and verify affected sources directly.

## MemPalace semantic-recall branch

Use semantic recall only when prior decisions, failed approaches, unknown
ownership, or cross-surface relationships materially improve the task. Known
files and symbols, implementation, tests, and active configuration use direct
`rg`, code-index, and exact-source reads; code is outside the reviewed corpus.
Use only a prompt-visible MCP search surface verified by upstream `--read-only`
plus Codex's explicit fail-closed `enabled_tools` allowlist; otherwise report it
unavailable or unverified and continue deterministically.
Read-only hides/refuses mutating tools; backend bookkeeping may still occur.

Choose the smallest wing: `aria-thesis`; `aria-literature-reviews` then the
matching `aria-papers` room for primary evidence; `aria-project-docs`;
`aria-debriefs`; or `aria-codex-history` only for explicit raw-history requests.
Treat results as candidate evidence: record source and authored date, open the
exact current-worktree source, and apply source order. Chronology alone never
implies supersession; ingestion-only dates stay unknown.

## Workflow

1. Read `AGENTS.md` and `.agents/references/source_order.md`.
2. Route implementation, test, configuration, or known-symbol questions
   directly to `rg`, code-index, and the defining source; do not query
   MemPalace for them.
3. For thesis-facing sections, terms, symbols, or equations, use the active thesis
   lane in `references/context_map.md`, its include graph, and the smallest shared
   owner among `glossary.typ`, `symbols.typ`, `equations.typ`, and `docs/notation.yml`;
   generated projections are not owners.
4. When semantic recall is eligible, choose one reviewed wing and normally one
   room through the MemPalace branch above. Search `aria-codex-history` only for
   an explicit raw-history request.
5. Take the Graphify branch above whenever the artifact is usable; use its
   `stale_sources` list to scope exact-source verification. Continue without
   Graphify only when the artifact is missing or invalid.
6. Use `docs/_generated/context/source_index.md` only when it already exists or
   source-family routing is unclear; refresh with `make context` only as needed.
7. Use source-specific outline tools before broad raw reads:
   - Quarto: `scripts/nbv_qmd_outline.sh --compact`
   - Active thesis: `scripts/nbv_typst_includes.py --thesis --mode outline`
   - Historical seminar: `scripts/nbv_typst_includes.py --seminar --mode outline`
   - Literature: `scripts/nbv_literature_index.sh`
   - Code/contracts: `scripts/nbv_get_context.sh modules|contracts|match <term>`
8. Open the exact candidate source and nearest nested `AGENTS.md` once the
   surface is known; reject optional retrieval that conflicts with its owner.
9. For external API behavior, use the localized skill's `metadata.context7_refs`;
   otherwise consult `references/context7_library_ids.md`, re-resolve consequential
   IDs at use time, and verify against local source/tests.
10. Use targeted `rg` inside the narrowed file set.

## Zoom-Out Output

- domain term and glossary anchor when one exists
- owning package/module and nearest `AGENTS.md`
- main callers and data contracts
- relevant tests or render checks
- docs/memory surfaces likely to need updates
- open risks or missing context

## References

- `references/context_map.md` for non-obvious concept-to-source routing.
