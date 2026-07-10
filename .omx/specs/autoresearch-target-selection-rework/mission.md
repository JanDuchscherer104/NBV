# Autoresearch Mission: Target Selection Rework

## Request

Aggregate the existing ARIA-NBV target-selection research and repo evidence before
changing the implementation.

Required inputs:

- Transcript `019ed4da-5d8f-7740-a68e-e2ee800d7bee` and its persisted research
  artifacts.
- Distilled transcript entries under
  `.agents/memory/transcripts/distilled/2026-06-18` that mention target selection.
- `.agents/work/target-selection-sampling`.
- Current target-selection thesis method section, especially
  `docs/typst/thesis/sections/03-method.typ` section
  `Target-Specific RRI Labels`.
- Current repo code, docs, tests, backlog, and KG route evidence needed to
  understand requirements, attempted designs, implementation issues, and
  rework ideas.

## Validation Mode

`prompt-architect-artifact`

The report is acceptable iff it:

- Separates verified current implementation facts from stale or superseded prior
  review notes.
- Covers the requested transcript, artifacts, distilled memory, work notes,
  method section, code, tests, docs, backlog, and KG route evidence.
- Identifies target-selection requirements, attempted approaches, current
  implementation issues, and concrete rework recommendations.
- Preserves the owner split: actor-visible target selection is not GT-evaluation,
  and GT matching remains deterministic label/evaluation logic unless future
  evidence justifies changing it.
