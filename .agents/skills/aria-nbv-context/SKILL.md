---
name: aria-nbv-context
description: Use to localize unknown ARIA-NBV files, symbols, docs, or source families through deterministic local discovery or eligible Graphify navigation before handoff.
metadata:
  mode: router
  not_when:
    - "exact file and owner are already known"
    - "a concrete failure command or traceback owns the task"
  handoff_to:
    - "graphify for an existing usable graph"
    - "nearest owning guide for concrete failures"
    - "nearest AGENTS.md or narrow skill after localization"
  evidence_required:
    - "localized owning files or source family"
    - "nearest applicable AGENTS.md"
    - "targeted rg or generated context evidence"
    - "freshness evidence before any Graphify-backed claim"
  applies_to:
    - "**"
  triggers:
    - "locate files"
    - "cross-surface context"
    - "where is this implemented"
    - "source family"
    - "codebase architecture, file relationships, or project-content questions"
  must_read:
    - "AGENTS.md"
    - ".agents/references/source_order.md"
  canonical_sources:
    - "AGENTS.md"
    - ".agents/references/source_order.md#role-split"
    - ".agents/skills/aria-nbv-context/references/context_map.md"
    - ".graphifyignore"
    - "docs/literature/README.md#optional-graphify-projection"
  literature_refs:
    - "docs/contents/literature/index.qmd"
    - "docs/literature/sources.jsonl"
    - "quality-driven-rri"
    - "finite-candidate-rl"
  tool_refs:
    - "mcp__code_index.search_code_advanced"
    - "mcp__code_index.get_symbol_body"
  verification:
    - "make context when generated context is stale or missing"
    - "python3 scripts/check_graphify_freshness.py --json before Graphify-backed claims"
    - "make graphify-state-check for strict scaffold validation"
---

# Aria NBV Context

Use this skill as the local discovery layer. It should identify the smallest
relevant set of files, then hand off to a narrower implementation, docs, or
diagnostic workflow.

## Graphify branch

For architecture, relationship, or broad project-content discovery, treat an
existing `graphify-out/graph.json` as the default trusted retrieval index. Run
`python3 scripts/check_graphify_freshness.py --json`, then hand off to the
byte-identical upstream skill at `.agents/skills/graphify/SKILL.md` whenever the
result says `usable: true`, including `structural-stale` or `semantic-stale`.
Query Graphify first; its provenance and `source_location` route the exact-source
check. For paths listed in `stale_sources`, verify consequential claims directly
before acting. Only `missing` or `invalid` states bypass Graphify entirely.

Before a build, refresh, or semantic reconciliation, read
[`references/graphify-aria-boundary.md`](references/graphify-aria-boundary.md).
It owns the conditional lifecycle and acceptance mechanics.

## Workflow

1. Read `AGENTS.md` and `.agents/references/source_order.md`.
2. Apply the Graphify branch above for broad project discovery.
3. Use `docs/_generated/context/source_index.md` only when it already exists or
   source-family routing is unclear; refresh with `make context` only when
   needed.
4. Use source-specific outline tools before broad raw reads:
   - Quarto: `scripts/nbv_qmd_outline.sh --compact`
   - Typst: `scripts/nbv_typst_includes.py --paper --mode outline`
   - Literature: `scripts/nbv_literature_index.sh`
   - Code/contracts: `scripts/nbv_get_context.sh modules|contracts|match <term>`
5. Open the nearest nested `AGENTS.md` once the surface is known.
6. Use targeted `rg` inside the narrowed file set.

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
