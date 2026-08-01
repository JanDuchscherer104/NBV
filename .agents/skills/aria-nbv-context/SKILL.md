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
    - "nearest owning guide for concrete failures"
    - "nearest AGENTS.md or narrow skill after localization"
  evidence_required:
    - "localized owning files or source family"
    - "nearest applicable AGENTS.md"
    - "targeted rg or generated context evidence"
    - "freshness evidence before any Graphify-backed claim"
    - "exact-source verification after any MemPalace result"
  applies_to:
    - "**"
  triggers:
    - "locate files"
    - "cross-surface context"
    - "where is this implemented"
    - "source family"
    - "codebase architecture, file relationships, or project-content questions"
    - "semantic recall of prior decisions, related work, or failed approaches"
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

ARIA-NBV owns only this preflight, `.graphifyignore`, the ignored Markdown
projection, and the read-side freshness gate. Do not patch, overlay, append to,
or add helper scripts beneath the upstream Graphify skill bundle. Build the
projection with `python3 scripts/build_graphify_projection.py --output
graphify-input --aria-code-ref "$(git rev-parse HEAD)"`, then use the repository
root as Graphify's corpus root.

Use upstream Graphify lifecycle and semantic reconciliation instead of a
repository-owned dispatch, cache, merge, or manifest implementation. Prefer an
upstream-supported CLI backend for semantic refreshes. If an explicitly chosen
Codex host-agent flow selects an agent role, use a self-contained prompt with
`fork_turns="none"`; inherited full history and explicit role selection are not
callable together. Do not accept a semantic refresh unless upstream Graphify
accounts for every dispatched file and excludes existing-file nodes outside the
dispatched set. If the current client cannot satisfy that contract, leave the
graph stale and continue from exact sources.

Graphify 0.9.31 writes the semantic-refresh marker at
`graphify-out/needs_update`, while its host-agent runbook clears the historical
`.needs_update` spelling. Until upstream aligns those names, remove
`graphify-out/needs_update` only after the upstream refresh has completed and
the coverage and reconciliation checks above have passed. Leave the marker in
place after any partial, failed, or unverified refresh so the read-side gate
continues to fail closed.

Every linked worktree must run `scripts/setup_worktree_env.sh`; its standard
contract creates and links the shared `semantic` and `semantic-deep`
content-addressed cache namespaces. Only those caches are shared. Projections,
graphs, manifests, AST state, and semantic run state remain worktree-local, and
cache presence never establishes graph freshness.

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
3. When semantic recall is eligible, choose one reviewed wing and normally one
   room through the MemPalace branch above. Search `aria-codex-history` only for
   an explicit raw-history request.
4. Take the Graphify branch above only when its eligibility gate succeeds;
   otherwise continue with exact-source discovery.
5. Use `docs/_generated/context/source_index.md` only when it already exists or
   source-family routing is unclear; refresh with `make context` only when
   needed.
6. Use source-specific outline tools before broad raw reads:
   - Quarto: `scripts/nbv_qmd_outline.sh --compact`
   - Typst: `scripts/nbv_typst_includes.py --paper --mode outline`
   - Literature: `scripts/nbv_literature_index.sh`
   - Code/contracts: `scripts/nbv_get_context.sh modules|contracts|match <term>`
7. Open the exact candidate source and nearest nested `AGENTS.md` once the
   surface is known; reject optional retrieval that conflicts with its owner.
8. Use targeted `rg` inside the narrowed file set.

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
