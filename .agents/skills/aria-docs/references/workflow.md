# ARIA Docs Workflow

1. Choose one branch from `SKILL.md`. Read only that reference plus
   `docs/AGENTS.md`, the target entrypoint or page, its imports, and adjacent
   source. Use Graphify when fresh; otherwise use targeted `rg` in the owning
   subtree.
2. Establish the artifact contract before writing: claim and evidence for
   prose; notation owner for math; construction provenance and evidential role
   for visuals; reader move for slides.
3. Author in the exact owner. Reuse `docs/typst/shared` and existing local
   components before introducing document-local helpers or dependencies.
4. Isolate a fragile equation, table, diagram, or layout component when a
   focused fixture or page makes failures easier to observe.
5. Run the narrowest owning check and compile command from `docs/AGENTS.md`.
   Render affected Typst pages directly when possible, for example:

   ```bash
   cd docs
   typst compile typst/thesis/main.typ \
     '/tmp/aria-thesis-page-{0p}.png' --root . --pages <pages> --ppi 220
   ```

6. Inspect rendered pages, not only compiler output. Check legibility,
   clipping, math attachment, references, captions, contrast, page breaks, and
   final-size layout.
7. Iterate until source, evidence, and render agree. Report exact commands,
   inspected pages, warnings, skipped checks, or the environment blocker.

For Mermaid, follow `mermaid.md` in addition to this workflow.
