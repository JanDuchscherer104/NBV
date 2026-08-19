---
name: aria-nbv-context
description: Use for Graphify-first ARIA-NBV owner-tree traversal, broad project relationships, or current Context7 evidence before handing work to an exact owner.
metadata:
  mode: router
  not_when:
    - "the exact local owner is already known and no external API/version uncertainty remains"
    - "a concrete failure command or traceback owns the task"
  handoff_to:
    - "graphify for a usable broad-context navigation graph"
    - "typst-authoring for thesis, glossary, shared-symbol, or shared-equation edits"
    - "nearest owning guide for concrete implementation or documentation work"
    - "nearest failure owner for a reproducer or traceback"
  evidence_required:
    - "selected branch in the compositional source-order tree"
    - "localized exact owner and nearest applicable AGENTS.md"
    - "Graphify provenance before Graphify-backed navigation"
    - "installed call site plus current external docs for Context7-backed claims"
    - "active shared scientific-language owner for durable terminology"
  applies_to:
    - "**"
  triggers:
    - "codebase architecture, ownership, relationships, or broad project context"
    - "locate an unknown ARIA-NBV owner or source family"
    - "thesis section, glossary, symbol, equation, or notation owner"
    - "current external API, SDK, or version behavior"
    - "semantic recall of prior decisions or failed approaches"
  must_read:
    - "AGENTS.md"
    - ".agents/references/source_order.md"
  canonical_sources:
    - "AGENTS.md"
    - ".agents/references/source_order.md#compositional-owner-tree"
    - ".agents/skills/aria-nbv-context/references/context_map.md"
    - ".agents/skills/aria-nbv-context/references/graphify-aria-boundary.md"
    - ".agents/skills/aria-nbv-context/references/context7_library_ids.md"
    - "docs/typst/thesis/main.typ"
    - "docs/typst/shared/glossary.typ"
    - "docs/typst/shared/symbols.typ"
    - "docs/typst/shared/equations.typ"
    - "docs/notation.yml"
    - ".graphifyignore"
    - "docs/literature/README.md#graphify-projection"
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
    - "make context when a required generated context view is stale or missing"
    - "python3 scripts/check_graphify_freshness.py --json before Graphify-backed claims"
    - "make graphify-state-check for strict scaffold validation"
---

# ARIA-NBV Context

Use this skill as the context-traversal interface. It chooses a branch, uses the
best navigation aid for that branch, opens the exact owner, then hands off.

## Owner-Tree Branch

Traverse `.agents/references/source_order.md` compositionally:

- durable terms, symbols, and equations start at the shared Typst glossary,
  symbols, equations, and notation registry;
- thesis claims start at the active thesis include graph;
- executable behavior starts at source, tests, active configuration, and the
  nearest package guide;
- agent workflow, accepted intent, and actionable work start at their guidance,
  accepted-spec, human-intent, or Agents-DB owner.

Generated context, retrieval, and historical evidence may locate an owner but
cannot replace it.

## Graphify Branch

For architecture, ownership, relationships, or broad project content, Graphify
is the primary navigation map. Initialize the worktree, run
`scripts/check_graphify_freshness.py --json`, then use upstream `graphify query`
for broad questions, `graphify path` for relationships, and `graphify explain`
for a focused concept before raw search.

Use a `fresh` or `usable-stale` graph; verify exact owners after navigation and
every consequential stale source in the latter case. Repair an `unusable`
bootstrap once before taking the reported direct-source fallback. The upstream
hook is the default local accelerator for post-commit/post-checkout code refresh,
but it neither proves semantic document freshness nor refreshes linked worktrees;
the state/repair detail remains in
[`references/graphify-aria-boundary.md`](references/graphify-aria-boundary.md).

## Context7 Branch

Use Context7 when a consequential decision depends on current external API,
SDK, package, or version behavior. Open the local owner and installed call site
first. Prefer the localized skill's `metadata.context7_refs`; otherwise use the
exact ID and focused seed query in
[`references/context7_library_ids.md`](references/context7_library_ids.md).

Use a supplied exact ID directly. Otherwise resolve the library ID, then issue
one narrow documentation query per concept. Verify the result against the
installed version, local source/tests, and exact ARIA owner.

## MemPalace Branch

Use semantic recall only for prior decisions, failed approaches, unknown
ownership, or cross-surface relationships that materially improve the task.
Choose one reviewed room, record source and authored date, then open the exact
current-worktree source. Code, tests, known symbols, and active configuration use
Graphify or direct owners rather than memory. Chronology never implies
supersession.

## Workflow

1. Select the smallest branch in the source-order tree.
2. For eligible broad project context, take the Graphify branch first.
3. For scientific language, open the active thesis include graph and the
   smallest shared glossary, symbol, or equation owner. Shared Typst facades own
   reusable body and metadata; `docs/notation.yml` is a generated consumer
   adapter.
4. For current external behavior, take the Context7 branch after the local call
   site is known.
5. Use MemPalace only for eligible semantic recall; use generated context only
   when source-family routing remains unclear.
6. Open the exact candidate source and nearest nested `AGENTS.md`; reject any
   navigation evidence that conflicts with them.
7. Hand off to the narrow implementation, docs, diagnostic, or review owner.
8. Stop retrieving when the owner and required verification are explicit.

## Zoom-Out Output

- selected source-order branch and exact owner
- domain term and shared-language anchor when one exists
- main callers, data contracts, and focused tests
- current external-doc evidence when it changes the decision
- stale, degraded, or missing context that still needs exact verification
