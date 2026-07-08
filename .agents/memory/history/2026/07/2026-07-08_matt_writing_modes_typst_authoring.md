---
id: 2026-07-08_matt_writing_modes_typst_authoring
date: 2026-07-08
title: "Matt Writing Modes For Typst Authoring"
status: done
topics: [skills, typst, thesis, mattpocock, scientific-writing]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/skills/typst-authoring/SKILL.md
  - .agents/skills/typst-authoring/references/thesis-writing.md
  - .agents/skills/typst-authoring/references/upstream-matt-writing.md
  - .agents/references/mattpocock_skills_manifest.toml
  - .agents/references/scaffold_routing_fixtures.json
---

# Matt Writing Modes For Typst Authoring

## Task

Adapted Matt `writing-fragments`, `writing-shape`, and `writing-beats` as
reference-only writing mechanics behind ARIA-NBV `typst-authoring`.

## Method

Kept `prose-draft` and `prose-polish` as the visible task modes. Added nested
`fragment-capture`, `shape-pass`, and `beat-pass` guidance under the existing
thesis-writing reference so the `SKILL.md` hot path stays compact.

## Outputs

Added `upstream-matt-writing.md` with pinned upstream links and ARIA adaptation
rules. Updated the Matt manifest to mark the three writing skills as
reference-only with `typst-authoring` ownership. Added a scaffold routing
fixture so thesis prose mentioning Matt writing modes still routes to local
ARIA authoring.

## Verification

- `make scaffold-audit` passed with 0 errors and existing warnings.
- `make scaffold-audit-self-test` passed with 13 fixtures and 0 failures.
- `make check-agent-memory` passed.
- `git diff --check` passed for the touched guidance, manifest, fixture, and
  debrief files.

## Canonical State Impact

No thesis, glossary, package, or current-project-state update is required. This
is scaffold guidance for how `typst-authoring` uses external writing mechanics.
