# ARIA-NBV Mermaid Workflow

Read the exact tooling owners:

- `tools/mermaid/references/aria_mermaid_style.md`
- `tools/mermaid/references/aria_symbol_map.yaml`
- the nearest template or example under `tools/mermaid/`
- relevant notation under `docs/typst/shared`

Keep `.mmd` as source, use the shared style and symbol map, and render locally.
Do not use an online renderer for unpublished material without explicit
permission.

```bash
python tools/mermaid/scripts/aria_mermaid_lint.py <file.mmd>
tools/mermaid/scripts/render_mermaid.sh <file.mmd> /tmp/<name>.svg
```

Run the renderer when `mmdc` is available, inspect the standalone asset, then
render and inspect the including Quarto or Typst page.
