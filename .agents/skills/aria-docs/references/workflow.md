# ARIA Docs Workflow

1. Read `docs/AGENTS.md`, the target entrypoint or page, its imports, and the
   adjacent source. Use Graphify when fresh; otherwise use targeted `rg` within
   that owning subtree.
2. Author in the exact owner. Reuse `docs/typst/shared` for durable terms,
   symbols, equations, and shared style; do not restate those contracts here.
3. Preserve reproducible figure or table source beside, or traceably linked to,
   the document asset.
4. Run the narrowest owning check and render from the command contract in
   `docs/AGENTS.md`.
5. Inspect affected rendered pages, not only compiler output. Check legibility,
   clipping, math and reference attachment, captions, contrast, and layout.
6. Iterate until the source and rendered result agree, or report the exact
   environment blocker.

For Mermaid, follow `mermaid.md` in addition to this workflow.
