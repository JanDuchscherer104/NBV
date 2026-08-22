# Typst realization and release workflow

Read this branch for an accepted-content Typst edit, or when a release
candidate needs compile, render, or hygiene evidence.

1. Open the nearest docs guide, exact Typst owner, adjacent section, and
   relevant shared modules. Treat those sources as truth; this reference is
   only a procedure.
2. Compile the smallest fixture or document from the repository root. For a
   thesis-facing change, run the existing `make typst-authoring-contract`.
3. Render affected pages when layout, equations, figures, tables, captions,
   or cross-references changed; inspect the output and repeat if needed.
4. Run applicable hygiene checks and `git diff --check`. Report exact
   commands, outputs, and any unavailable visual check.

Use the Context7 plugin only when a current Typst API is uncertain after local
inspection, following the single [Context7 registry owner](../../aria-nbv-context/references/context7_library_ids.md).
Keep package and source ownership in exact repository owners; do not create a
parallel inventory.
