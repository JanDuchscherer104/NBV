# Autoresearch Mission: Thesis Structure And Include Graph

## Mission

Find the best active structure for `docs/typst/thesis/main.typ` and the thesis
section source tree, using the current local ARIA-NBV thesis contract plus
external master's-thesis writing guidance from Hochschule München, TUM, and
general scientific-writing sources.

## Validation Mode

`prompt-architect-artifact`

## Success Criteria

- Verify the current `main.typ` include graph and identify whether existing
  section files are included directly, transitively, through the template
  appendix, or not at all.
- Propose a chapter and source-file structure that fits a computer-science
  master's thesis and ARIA-NBV's current RQ spine.
- Map each proposed chapter to content goals, research questions, current local
  source owners, and validation evidence.
- Identify what should move to appendix/provenance rather than remain in the
  numbered thesis body.
- Preserve source order: current roadmap/questions/memory and active thesis
  sections outrank historical seminar/proposal/advisor artifacts.
- Produce a concrete implementation handoff, but do not patch thesis files in
  this planning pass.
