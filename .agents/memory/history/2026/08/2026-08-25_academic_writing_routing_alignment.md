---
id: 2026-08-25_academic_writing_routing_alignment
date: 2026-08-25
title: "Academic writing routing alignment"
status: done
topics: [scaffold, academic-writing, literature, scientific-review]
confidence: high
canonical_updates_needed:
  - .agents/skills/academic-writing/SKILL.md
  - .agents/skills/literature-research/SKILL.md
  - .agents/skills/scientific-review/SKILL.md
  - .agents/skills/README.md
touched_owner_paths:
  - .agents/skills/academic-writing/SKILL.md
  - .agents/skills/literature-research/SKILL.md
  - .agents/skills/scientific-review/SKILL.md
  - scripts/scaffold/run_routing_trials.py
codex_thread: codex://threads/01a02ab6-c75e-7313-be12-e5f90ae0cde3
repo_object_format: sha1
repo_head: bea97c80bb667a9eea49920a661dc1f7a316b72e
repo_branch: "codex/upstream-academic-writing-alignment"
worktree_kind: linked
---

## Task
Add the smallest upstream-informed academic-writing scaffold improvement.

## Method
Retained ARIA's argument/review/Typst ownership split; selectively adapted
source-screening, material-change, computational-evidence, and display-provenance
mechanics from the pinned upstream WenyuChiou skill sources.

## Findings
Added an optional `literature-research` route, bounded material-change handling,
selective review profiles, and positive/near-miss routing coverage. The
upstream sources remain reference-only; active ARIA documentation,
bibliography, code, and Typst owners remain authoritative.

## Commits
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/fd647c8e1946eda517764a90045ad67c38863255
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/bea97c80bb667a9eea49920a661dc1f7a316b72e

## Verification
Passed `python -m pytest -q scripts/tests/test_ci_impact.py
scripts/tests/test_routing_trials.py` (95 tests, 62 subtests),
`python scripts/tests/test_agent_governance_g002.py`, `scaffold_audit.py`, and
`scaffold_audit.py --self-test`. The first local `python3 -m pytest` attempt
was unavailable because that interpreter lacks pytest; the repository venv ran
the same focused pytest suite successfully. The rebased hardening renamed the
discovery lane, preserved the HM/FK07 overlay, added material-change
invalidation, and covered source discovery plus its writing, review, Typst, and
current-API near-misses.

## Canonical Owner Impact
The four guidance owners listed in `canonical_updates_needed` now contain the
durable routing and review mechanics. No thesis, bibliography, code, or
experiment contract changed.
