# Critic Review: Local Scientific Agent Skill Adapters

Verdict: APPROVE

## Quality Gate

The revised plan is actionable, principle-consistent, and verifiable. It keeps K-Dense as a pinned external evidence source, exposes only compact ARIA-owned adapters, preserves source-order ownership, and includes concrete static checks, external-source checks, routing fixtures, and adapter dry exercises.

## Architect Improvements Verified

- Phase 1 names a pinned git submodule as the concrete storage mechanism.
- Phase 4 merges into adjacent owners only after fixture or dry-exercise evidence.
- The test spec includes nearest-neighbor collision fixtures for `scientific-writing` versus `typst-authoring` and `scientific-visualization` versus `aria-nbv-mermaid`.

## Final Improvements Applied

- Added a mocked/dry-run update smoke requirement for `scripts/external_skills.py update`.
- Added a Phase 0 requirement to record existing dirty `.agents/external/litkg-rs` state before K-Dense work.
- Added stable fixture IDs to the planned routing fixtures.

## Stop Condition

Consensus gate is approved. No implementation was performed in ralplan.
