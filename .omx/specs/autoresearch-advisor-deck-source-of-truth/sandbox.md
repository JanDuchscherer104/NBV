# Sandbox Notes

## Local Guidance Read

- `AGENTS.md` from prompt.
- `.agents/skills/agent-behavior/SKILL.md`
- `.agents/skills/docs-curator/SKILL.md`
- `.agents/skills/typst-authoring/SKILL.md`
- `.agents/skills/aria-litkg-memory/SKILL.md`
- `docs/AGENTS.md`
- `.agents/references/source_order.md`
- `.agents/references/verification_matrix.md`
- `.agents/references/litkg_quick_reference.md`
- `.agents/skills/typst-authoring/references/slides.md`
- `.agents/skills/typst-authoring/references/aria-nbv-notation.md`
- `.agents/skills/typst-authoring/references/claim-citation-discipline.md`

## Current Autoresearch Mode

Validation mode: `prompt-architect-artifact`

Output artifact: `.omx/specs/autoresearch-advisor-deck-source-of-truth/report.md`

Completion artifact: `.omx/specs/autoresearch-advisor-deck-source-of-truth/result.json`

## Notes

- The report should be source-order aware. Current thesis QMDs and canonical memory outrank historical seminar and outlook decks unless the task intentionally promotes the May 22 deck as a new consolidated owner.
- `litkg` is healthy at mission start (`make kg-status` returned `ok`).
- Root guidance mentions `scripts/nbv_typst_includes.py`, but that path was not present from repo root during this run; use direct `rg`/file reads for Typst localization.
