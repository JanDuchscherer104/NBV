---
name: aria-nbv-context
description: Use for hierarchical ARIA-NBV owner localization, Graphify-first project relationships, scientific-source initialization, or current Context7 App evidence before handing work to an exact owner.
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
    - "selected branch and leaf in the owner hierarchy"
    - "localized exact owner and nearest applicable AGENTS.md"
    - "Graphify provenance before Graphify-backed navigation"
    - "installed call site plus current external docs for Context7-backed claims"
  applies_to:
    - "**"
  triggers:
    - "codebase architecture, ownership, relationships, or broad project context"
    - "locate an unknown ARIA-NBV owner or source family"
    - "thesis section, glossary, symbol, equation, notation, or literature owner"
    - "current external API, SDK, or version behavior"
    - "semantic recall of prior decisions or failed approaches"
  must_read:
    - "AGENTS.md"
  canonical_sources:
    - "AGENTS.md"
    - ".agents/skills/aria-nbv-context/references/graphify-aria-boundary.md"
    - ".agents/skills/aria-nbv-context/references/context7_library_ids.md"
    - "docs/typst/thesis/main.typ"
    - "docs/typst/thesis/sections/01-research-questions.typ"
    - "docs/typst/thesis/development/roadmap.typ"
    - "docs/typst/shared/glossary.typ"
    - "docs/typst/shared/symbols.typ"
    - "docs/typst/shared/equations.typ"
    - "docs/typst/glossary/main.typ"
    - "docs/notation.yml"
    - "docs/literature/sources.jsonl"
    - "docs/references.bib"
    - "docs/contents/literature/index.qmd"
    - "docs/typst/thesis/sections/02-foundations/02-01-related-work.typ"
  literature_refs:
    - "docs/contents/literature/index.qmd"
    - "docs/literature/sources.jsonl"
    - "quality-driven-rri"
    - "finite-candidate-rl"
  context7_refs: ["/graphify-labs/graphify", "/websites/typst_app", "/facebookresearch/atek", "/websites/facebookresearch_github_io_projectaria_tools", "/facebookresearch/efm3d", "/facebookresearch/pytorch3d", "/websites/zarr_readthedocs_io_en_stable", "/rerun-io/rerun"]
  tool_refs:
    - "mcp__codex_apps__context7_resolve_library_id"
    - "mcp__codex_apps__context7_query_docs"
    - "mcp__code_index.search_code_advanced"
    - "mcp__code_index.get_symbol_body"
  verification:
    - "make context when a required generated context view is stale or missing"
    - "python3 scripts/check_graphify_freshness.py --json before Graphify-backed claims"
    - "make graphify-state-check for strict scaffold validation"
---

# ARIA-NBV Context

Select the smallest hierarchy leaf, use navigation only when it helps, open the
exact owner, then hand off. Derived, retrieved, generated, and historical
material may locate truth but cannot replace its owner.

## Owner Hierarchy

- **Scientific language**
  - `docs/typst/shared/symbols.typ`: composed `symb` facade; domain symbol
    modules beneath it own reusable notation bodies.
  - `docs/typst/shared/equations.typ`: composed `eqs` facade; domain equation
    modules beneath it own reusable mathematical bodies.
  - `docs/typst/shared/glossary.typ`: editable term registry linking prose,
    symbols, equations, and sources. `docs/typst/glossary/` renders and checks
    that registry; it is not another glossary owner.
  - `docs/notation.yml`: generated cross-format lookup adapter; shared Typst
    facades own reusable bodies and metadata.
- **Thesis direction**: `docs/typst/thesis/main.typ` and its active includes own
  narrative and claims; question and development-gate files own their narrower
  contracts. Seminar, archived proposal, and dated history are evidence only.
- **Literature to thesis**
  - `docs/literature/sources.jsonl`: checked-in paper manifest for acquisition,
    relevance, and adoptable-idea metadata.
  - `docs/references.bib` and `docs/references-qh.bib`: citation identities and
    bibliographic metadata; exact primary sources support external claims.
  - `docs/contents/literature/`: paper-by-paper review and ARIA-NBV synthesis.
  - `docs/typst/thesis/sections/`: current claim placement and narrative;
    foundations/related work starts at `02-foundations/02-01-related-work.typ`.
- **Executable system**: nearest package `AGENTS.md`, source, tests, and active
  configuration own behavior and proof.
- **Project intent and work**: accepted spec supersessions and reviewed human
  intent own decisions; Agents-DB TOMLs own actionable work.
- **Agent execution**: root/nested `AGENTS.md` own invariants; skills own
  activation, procedure, handoff, and verification.

## Conflict Rule

Prefer the narrowest active owner: active thesis over seminar/archive history;
source, tests, and configuration over documentation or retrieval; explicit
accepted supersessions over plans or chronology. Planned work is not an
implemented result.

## Capture Rule

- Repo invariant: root or nearest nested `AGENTS.md`.
- Repeatable workflow: `.agents/skills/*/SKILL.md`.
- Actionable work: Agents-DB issues, todos, or refactors.
- Public narrative or scientific language: the smallest active Quarto/Typst
  section, glossary, symbol, equation, notation, bibliography, or source owner.
- Reviewed preference: `.agents/references/human_owner_intent.md`.
- Accepted scoped target: the relevant explicit `.omx/specs/` supersession.
- Debriefs and optional tools capture evidence or proposals, not current truth.

## Graphify Branch

For architecture, ownership, relationships, or broad project content, initialize
the worktree and run `scripts/check_graphify_freshness.py --json`. For `fresh`
or `usable-stale`, use upstream `graphify query` for context, `graphify path`
for relationships, and `graphify explain` for a concept before raw search.
Verify exact owners and every consequential stale source. Repair `unusable`
once, then report it and use direct sources if repair fails. Read
[`references/graphify-aria-boundary.md`](references/graphify-aria-boundary.md)
for freshness, repair, lifecycle, and fallback rules.

## Context7 App Branch

Use the Context7 App only after locating the local owner and installed call
site. Use a supplied exact ID directly; otherwise call
`mcp__codex_apps__context7_resolve_library_id`, then issue one concept per
`mcp__codex_apps__context7_query_docs` call. Verify against the installed
version and local source/tests. The IDs above are initialization seeds; read
[`references/context7_library_ids.md`](references/context7_library_ids.md) for
their concise scopes, the full registry, and focused query menus. Do not use the
deprecated MCP-Docker Context7 tools.

## Workflow

1. Select one hierarchy leaf and its nearest `AGENTS.md`.
2. For scientific language, open the active thesis include graph and the
   smallest shared glossary, symbol, or equation owner; treat `docs/notation.yml`
   as a generated consumer.
3. Use Graphify first for eligible broad context, subject to its state contract.
4. Use the Context7 App only for consequential current external behavior.
5. Use reviewed semantic memory only when prior decisions or failed approaches
   materially help; chronology never implies supersession.
6. Open the exact owner, reject conflicting navigation evidence, hand off, and
   stop retrieving when the owner and proof are explicit.
