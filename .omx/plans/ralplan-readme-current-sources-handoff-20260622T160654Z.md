# README Current Sources Handoff

## Task

Update the top-level `README.md` so it links to currently relevant ARIA-NBV
sources, especially:

- `docs/typst/thesis/main.typ`
- `docs/typst/thesis/advisor_meeting_2026_05_22.typ`
- important Quarto index/navigation files

Also prune stale README prose where it duplicates owned setup or docs pages.

## Grounding

- Root `AGENTS.md` routes public docs edits through `agent-behavior` and
  `docs-curator`.
- `docs/AGENTS.md` and `.agents/references/source_order.md` make
  `docs/contents/thesis/roadmap.qmd`, `docs/contents/thesis/questions.qmd`,
  and `.agents/memory/state/` the current thesis-direction owners.
- `docs/typst/thesis/main.typ` is the active thesis seed.
- `docs/typst/thesis/advisor_meeting_2026_05_22.typ` is useful provenance but
  must not override the current roadmap/questions contract.
- `docs/index.qmd`, `docs/_quarto.yml`,
  `docs/contents/literature/index.qmd`, and `docs/reference/index.qmd` are the
  relevant public Quarto entry/navigation/index surfaces.

## Execution Plan

1. Keep the README as a short gateway, not a duplicate roadmap.
2. Refresh the opening/current-focus bullets to match target-specific RRI,
   finite-candidate rollouts, and `Q_H`.
3. Replace the thin documentation map with links to Quarto, thesis, theory,
   Typst, API, and setup owners.
4. Prune the stray empty bullet and long duplicated downloader/offline prose in
   favor of a link to `SETUP.md`.
5. Verify Markdown/link syntax with `git diff --check` plus focused path checks
   for the linked files.

## Handoff

Approved for execution via `$ralph` as a narrow documentation edit to
`README.md`.
