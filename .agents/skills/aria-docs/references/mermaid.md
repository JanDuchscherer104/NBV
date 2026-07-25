# ARIA-NBV Mermaid Contract

Read this file only for `.mmd` sources, Mermaid templates/tooling, or a Mermaid
asset entering Quarto or Typst.

## Read First

- `tools/mermaid/references/aria_mermaid_style.md`
- `tools/mermaid/references/aria_symbol_map.yaml`
- relevant notation under `docs/typst/shared`
- the nearest matching file under `tools/mermaid/templates/` or
  `tools/mermaid/examples/`

## Rules

1. Use the curated symbol map as the Mermaid/KaTeX projection of shared Typst
   notation. Do not invent notation in a diagram; update shared notation and
   then the symbol map.
2. Start from `flowchart_scientific.mmd` or `sequence_scientific.mmd` unless a
   different grammar is required.
3. Use the semantic flowchart classes `input`, `compute`, `data`, and `output`.
4. Math-heavy flowcharts use the established `htmlLabels`, ELK layout, and
   shared class palette.
5. Keep labels compact: a short bold title plus one to three math or code lines.
   Use a KaTeX array for multiline math where needed.
6. Keep `.mmd` as the source of truth. Render locally; never send unpublished
   thesis diagrams to an online renderer without explicit permission.
7. Preserve existing visual intent. Do not rewrite a diagram only because the
   linter reports a non-blocking warning.
8. Use Mermaid for architecture, process, topology, and state transitions, not
   quantitative geometry, directional fields, or real 3D evidence.

## Workflow

1. Choose the diagram role: data flow, model branch, rollout protocol, storage
   layout, sequence, or configuration graph.
2. Inspect shared notation, style, symbol map, and a matching template.
3. Edit the `.mmd`.
4. Run:

   ```bash
   python tools/mermaid/scripts/aria_mermaid_lint.py <file.mmd>
   ```

5. If global `mmdc` is available, render locally:

   ```bash
   tools/mermaid/scripts/render_mermaid.sh <file.mmd> /tmp/<name>.svg
   ```

6. Inspect the standalone asset. If included in Typst, also compile and inspect
   the final page; if included in Quarto, render the touched page.

Report the source path, lint result, render result or skipped-render reason, and
remaining warnings.
