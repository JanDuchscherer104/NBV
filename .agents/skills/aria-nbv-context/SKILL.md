---
name: aria-nbv-context
description: Locate ARIA-NBV files, symbols, docs, and owners.
metadata:
  mode: router
  not_when:
    - "exact file and owner are already known"
    - "authority-sensitive claim review is required"
    - "a concrete failure command or traceback owns the task"
  handoff_to:
    - "aria-docs for direct-source claim review"
    - "specialized diagnostic capability for concrete failures"
    - "nearest AGENTS.md or narrow skill after localization"
  evidence_required:
    - "localized owning files or source family"
    - "nearest applicable AGENTS.md"
    - "targeted rg, outline, contract, or directory-tree evidence"
  applies_to:
    - "**"
  triggers:
    - "locate files"
    - "cross-surface context"
    - "where is this implemented"
    - "source family"
  must_read:
    - "AGENTS.md"
    - ".agents/references/source_order.md"
  canonical_sources:
    - "AGENTS.md"
    - ".agents/references/source_order.md#role-split"
    - ".agents/references/graphify_contract.md"
  literature_refs:
    - "docs/contents/literature/index.qmd"
    - "docs/literature/sources.jsonl"
    - "VIN-NBV-frahm2025"
    - "docs/contents/literature/rl_planning.qmd"
  tool_refs:
    - "mcp__code_index.search_code_advanced"
    - "mcp__code_index.get_symbol_body"
  verification:
    - "targeted exact-source command from this skill"
---

# Aria NBV Context

Use this skill as the local discovery layer. It should identify the smallest
relevant set of files, then hand off to a narrower implementation, docs,
exact-source, or diagnostic workflow.

## Workflow

1. Read `AGENTS.md` and `.agents/references/source_order.md`.
2. Use fresh Graphify navigation when available; otherwise continue directly
   with exact source owners and targeted `rg`.
3. Use source-specific inspection before broad raw reads:
   - Quarto: `scripts/nbv_qmd_outline.sh --compact`
   - Typst: `scripts/nbv_typst_includes.py --paper --mode outline|includes`
   - Literature: direct `rg -n <term> docs/literature/tex-src docs/references.bib`
   - Code/contracts: `make context-contracts`
   - Trees: `make context-dir-tree` or `make context-qmd-tree`
4. Open the nearest nested `AGENTS.md` once the surface is known.
5. Use targeted `rg` inside the narrowed file set.

## Zoom-Out Output

When asked to map a surface, return:

- domain term and glossary anchor when one exists
- owning package/module and nearest `AGENTS.md`
- main callers and data contracts
- relevant tests or render checks
- docs/memory surfaces likely to need updates
- open risks or missing context
