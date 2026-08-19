---
name: aria-nbv-mermaid
description: Use for ARIA-NBV Mermaid source, local lint/render, and thesis-diagram style work.
metadata:
  mode: implementation
  not_when:
    - "the task is only Typst layout/prose without Mermaid sources"
    - "a concrete local lint or Mermaid CLI failure needs diagnosis"
    - "the requested visual is better as a raster image or non-Mermaid asset"
  handoff_to:
    - "typst-authoring for shared notation changes, Typst inclusion, captions, and final-page QA"
    - "nearest docs guide for Quarto pages containing Mermaid fences"
    - "nearest owning guide for reproduced local lint or Mermaid CLI failures"
  evidence_required:
    - "the source `.mmd` and its destination surface"
    - "the local style guide and symbol map before math-heavy or thesis-figure edits"
    - "local lint output; render output or an explicit `mmdc`-unavailable result"
  applies_to:
    - "**/*.mmd"
    - "tools/mermaid/**"
    - "docs/figures/**"
    - "docs/typst/**/figures/**"
  triggers:
    - "Mermaid"
    - ".mmd"
    - "thesis diagram"
    - "flowchart"
    - "sequence diagram"
  must_read:
    - "AGENTS.md"
    - "docs/AGENTS.md"
  canonical_sources:
    - "docs/AGENTS.md"
    - "tools/mermaid/references/aria_mermaid_style.md"
    - "tools/mermaid/references/aria_symbol_map.yaml"
    - "tools/mermaid/scripts/aria_mermaid_lint.py"
    - "tools/mermaid/scripts/render_mermaid.sh"
    - "docs/typst/shared"
  context7_refs:
    - "/mermaid-js/mermaid"
  tool_refs:
    - "mcp__codex_apps__context7_resolve_library_id"
    - "mcp__codex_apps__context7_query_docs"
  verification:
    - "python tools/mermaid/scripts/aria_mermaid_lint.py <file.mmd>"
    - "tools/mermaid/scripts/render_mermaid.sh <file.mmd> <out.svg> when `mmdc` is available"
---

# ARIA-NBV Mermaid Figure Skill

This skill owns the local Mermaid seam: versioned `.mmd` source through the
vendored `tools/mermaid` lint and render commands. It routes notation, final
document integration, and diagnosed tool failures to their existing owners.

## Use When

- Creating, editing, reviewing, linting, or rendering a repository `.mmd`.
- Updating `tools/mermaid` templates, examples, style guidance, the symbol map,
  or the local linter/render wrapper.
- Turning a local architecture, protocol, storage, or sequence into a Mermaid
  diagram.

## Read First

1. Read `AGENTS.md` and `docs/AGENTS.md`.
2. For a thesis figure or any math label, read the local style guide and symbol
   map; also inspect the relevant `docs/typst/shared` source.
3. For a rendering or linting failure, capture the exact local command and
   output before handing the evidence to the nearest owning guide.
4. Query `/mermaid-js/mermaid` only when current upstream grammar or renderer
   behavior is material; local source, lint, and render results remain decisive.

## Seam Rules

- Keep `.mmd` as the source of record. `tools/mermaid` owns local template,
  style, notation-projection, lint, and render behavior; do not add a second
  Mermaid CLI wrapper to another skill. Its wrapper resolves a repository-local
  CLI first, then an explicit `MERMAID_CLI` or `PATH` installation.
- Start from the matching local template or example. Flowcharts use the shared
  `input`, `compute`, `data`, and `output` classes; math-heavy flowcharts use
  the supplied frontmatter.
- Keep labels compact. Every new mathematical symbol must already be in shared
  Typst notation and its Mermaid projection; hand off to `typst-authoring`
  before changing either owner.
- Treat lint warnings as review evidence. Preserve existing visual intent and
  change it only for the requested diagram or a clear style mismatch.
- Render locally only. If `mmdc` is unavailable, report that condition rather
  than substituting an online renderer.

## Workflow

1. Identify the grammar and destination: source-only, Quarto fence, or a
   rendered Typst asset.
2. Copy the matching local template or adapt the closest local example.
3. For math labels, verify each symbol against the shared Typst owner and
   `aria_symbol_map.yaml`; stop and hand off if notation must change.
4. Edit the `.mmd`, then run:

   ```bash
   python tools/mermaid/scripts/aria_mermaid_lint.py <file.mmd>
   ```

   Resolve errors. Record warnings that remain intentional.
5. When the local renderer resolves a CLI, render a review artifact outside
   tracked figure paths unless an output asset is requested:

   ```bash
   tools/mermaid/scripts/render_mermaid.sh <file.mmd> /tmp/<name>.svg
   ```

6. Hand off Quarto inclusion to the nearest docs guide; hand off Typst asset inclusion,
   captioning, and page inspection to `typst-authoring`.

## Completion

Report the source path, exact lint result, render result or `mmdc` gap, and
the destination-owner handoff when one remains.
