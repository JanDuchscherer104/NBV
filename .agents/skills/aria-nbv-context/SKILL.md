---
name: aria-nbv-context
description: Use to localize unknown ARIA-NBV owners through deterministic discovery or optional semantic recall of prior decisions, related work, and failed approaches before handoff.
metadata:
  mode: router
  not_when:
    - "exact file and owner are already known"
    - "a concrete failure command or traceback owns the task"
  handoff_to:
    - "graphify for an eligible fresh graph"
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
    - "python3 scripts/check_graphify_freshness.py --quiet before Graphify-backed claims"
---

# Aria NBV Context

Use this skill as the local discovery layer. It should identify the smallest
relevant set of files, then hand off to a narrower implementation, docs, or
diagnostic workflow.

## Graphify branch

For architecture, relationship, or broad project-content discovery, check
`graphify-out/graph.json` and run
`python3 scripts/check_graphify_freshness.py --quiet` first. A zero exit permits
handoff to the byte-identical upstream skill at
`.agents/skills/graphify/SKILL.md`; verify every consequential graph result in
its exact owner. Any other exit stays in the deterministic workflow below.

Before any build or semantic refresh, read
[`references/graphify-aria-boundary.md`](references/graphify-aria-boundary.md).
It owns ARIA's projection, upstream-only, coverage, marker, and linked-worktree
rules. Leave an incomplete or unreconciled graph stale and continue from exact
sources.

## MemPalace semantic-recall branch

Use semantic recall only when prior decisions, failed approaches, unknown
ownership, or cross-surface relationships materially improve the task. Known
files and symbols, implementation, tests, and active configuration use direct
`rg`, code-index, and exact-source reads; code is outside the reviewed corpus.
Use only a prompt-visible MCP search surface verified by upstream `--read-only`
plus Codex's explicit fail-closed `enabled_tools` allowlist. Otherwise report it
unavailable or unverified and continue deterministically.
Read-only means mutating MCP tools are hidden and refused, although Chroma may
still update internal bookkeeping while serving a search.

Choose the smallest wing: `aria-thesis`; `aria-literature-reviews` then the
matching `aria-papers` room for primary evidence; `aria-project-docs`;
`aria-debriefs`; or, only for explicit raw-history requests,
`aria-codex-history`. Treat results as candidate evidence: record source and
authored date, open the exact current-worktree source, and apply source order.
Chronology alone never implies supersession; ingestion-only dates stay unknown.

## Workflow

1. Read `AGENTS.md` and `.agents/references/source_order.md`.
2. Route implementation, test, configuration, or known-symbol questions
   directly to `rg`, code-index, and the defining source; do not query
   MemPalace for them.
3. For thesis-facing sections, terms, symbols, or equations, use the active
   thesis lane in `references/context_map.md`. Open the thesis include graph and
   the smallest shared owner among `glossary.typ`, `symbols.typ`,
   `equations.typ`, and `docs/notation.yml`; generated projections are not owners.
4. When semantic recall is eligible, choose one reviewed wing and normally one
   room through the MemPalace branch above. Search `aria-codex-history` only for
   an explicit raw-history request.
5. Take the Graphify branch above only when its eligibility gate succeeds;
   otherwise continue with exact-source discovery.
6. Use `docs/_generated/context/source_index.md` only when it already exists or
   source-family routing is unclear; refresh with `make context` only when
   needed.
7. Use source-specific outline tools before broad raw reads:
   - Quarto: `scripts/nbv_qmd_outline.sh --compact`
   - Active thesis: `scripts/nbv_typst_includes.py --thesis --mode outline`
   - Historical seminar: `scripts/nbv_typst_includes.py --seminar --mode outline`
   - Literature: `scripts/nbv_literature_index.sh`
   - Code/contracts: `scripts/nbv_get_context.sh modules|contracts|match <term>`
8. Open the exact candidate source and nearest nested `AGENTS.md` once the
   surface is known; reject optional retrieval that conflicts with its owner.
9. For external API behavior, use the localized skill's `metadata.context7_refs`.
   If no narrow skill owns the question, consult `references/context7_library_ids.md`;
   re-resolve consequential IDs at use time and verify against local source/tests.
10. Use targeted `rg` inside the narrowed file set.

## Zoom-Out Output

When asked to map a surface, return:

- domain term and glossary anchor when one exists
- owning package/module and nearest `AGENTS.md`
- main callers and data contracts
- relevant tests or render checks
- docs/memory surfaces likely to need updates
- open risks or missing context

## References

- `references/context_map.md` for non-obvious concept-to-source routing.
