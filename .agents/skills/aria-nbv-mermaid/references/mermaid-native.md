# Mermaid-Native Source And Rendering

Use this branch for an existing Mermaid-native asset or after conceptual review
selects Mermaid for a new or revised figure.

## Source Contract

- Keep `.mmd` as the source of record. `tools/mermaid` owns templates, style,
  notation projection, lint, and render behavior; do not add another wrapper.
- The wrapper resolves a repository-local CLI first, then an explicit
  `MERMAID_CLI` or `PATH` installation.
- Start from the matching local template or example. Flowcharts use the shared
  `input`, `compute`, `data`, and `output` classes; math-heavy flowcharts use the
  supplied frontmatter.
- Preserve contrast: every shared semantic `classDef` pins `color:#17202A` with
  its pale fill. The canonical definitions live in
  [`aria_mermaid_style.md`](../../../../tools/mermaid/references/aria_mermaid_style.md#3-node-classes).
- Keep labels compact. Every mathematical symbol must already exist in shared
  Typst notation and its Mermaid projection. Load `typst-authoring` before
  changing either owner.
- Treat lint warnings as review evidence. Preserve intentional visual semantics;
  do not normalize a diagram merely to silence a warning.

## Local Proof

Run the linter on every changed source:

```bash
python3 tools/mermaid/scripts/aria_mermaid_lint.py <file.mmd>
```

Resolve errors and record intentional warnings. Render review output outside
tracked figure paths unless the task intentionally changes the derived asset:

```bash
tools/mermaid/scripts/render_mermaid.sh <file.mmd> /tmp/<name>.svg
```

Inspect the standalone output, grayscale, and the final destination. If `mmdc`
is unavailable, report that condition instead of using an online renderer.
