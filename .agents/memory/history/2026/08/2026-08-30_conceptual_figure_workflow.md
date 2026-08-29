---
id: 2026-08-30_conceptual_figure_workflow
date: 2026-08-30
title: "Conceptual Figure Workflow"
status: done
topics: [agents, diagrams, mermaid, typst, scientific-review, context7]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - AGENTS.md
  - docs/AGENTS.md
  - .agents/skills/aria-nbv-context/references/context7_library_ids.md
  - .agents/skills/aria-nbv-mermaid/SKILL.md
  - .agents/skills/aria-nbv-mermaid/references/conceptual-diagrams.md
  - .agents/skills/aria-nbv-mermaid/references/interactive-figure-research.md
  - .agents/skills/aria-nbv-mermaid/references/mermaid-native.md
  - .agents/skills/typst-authoring/references/figures-tables.md
  - .agents/skills/typst-authoring/references/scientific-visualizations.md
  - scripts/tests/test_agent_governance_g002.py
codex_thread: codex://threads/01a04f6f-b0ec-7073-9d78-9dd125d8436b
repo_object_format: sha1
repo_head: a7c2b699d402fdbf007cfa17f38f00dd9a7453a0
repo_branch: "codex/thesis-diagram-workflow"
worktree_kind: linked
---

## Task
Establish an explanation-first, cross-renderer thesis-figure workflow that
preserves the Mermaid implementation seam, delegates Typst/scientific rendering
to its existing owner, and supports artifact-gated iterative visual research.

## Method
Froze the source stack at `8d42381b08830265e68e152733cadf60e2626806`,
scientifically reviewed all eight tracked Mermaid/SVG pairs at the frozen
candidate, inspected their active consumers, and queried Context7 for Fletcher,
CeTZ, and Typst implementation guidance. Compared those results with the pinned
local package examples and primary Fletcher, CeTZ, and Janosh sources. Reworked
the guidance using progressive disclosure, then ran independent code-review and
architecture passes and patched every valid finding.

## Findings
- All eight tracked Mermaid/SVG figure families were orphaned from the current
  thesis include graph. Six materially contradicted current sampler, actor-state,
  horizon-support, or A1-H0-S0 architecture owners, so the new workflow rejects
  cosmetic reuse and requires consumer proof before retention.
- `.agents/skills/aria-nbv-mermaid/SKILL.md` now owns explanatory admissibility,
  review-versus-build authorization, relational Mermaid-vs-Typst routing, and
  Mermaid-native work without duplicating renderer implementations.
- `conceptual-diagrams.md` records professor/student lenses, retain/simplify/
  revise/replace/merge/remove decisions, design dos and don'ts, and the exact
  Context7 query effects and primary-source fallbacks.
- `interactive-figure-research.md` defines the figure candidate packet and hard
  gates while leaving validation mode, state, and result schemas with OMX
  autoresearch. Publication remains task-authorized and no-change figures do not
  create empty PRs.
- `mermaid-native.md` preserves the existing contrast, notation projection,
  lint, local render, and fail-closed `mmdc` contracts behind a conditional route.
- Typst guidance now uniquely owns exact scientific renderer selection,
  realization, captions, compilation, accessibility, and final-page QA.

## Commits
- [a7c2b699d402fdbf007cfa17f38f00dd9a7453a0](https://github.com/JanDuchscherer104/ARIA-NBV/commit/a7c2b699d402fdbf007cfa17f38f00dd9a7453a0) — cross-renderer figure workflow, conditional references, owner-boundary repair, and governance test update

## Verification
- Skill quick validation: passed.
- `make scaffold-audit`: passed with one unrelated pre-existing Mojo warning.
- `make scaffold-audit-self-test`: 34 negative probes and 25 governance tests passed.
- `make skill-source-self-test`: six sources and six tests passed.
- `make check-agent-memory` and `git diff --check`: passed.
- Independent code review: clean, zero findings after remediation.
- Independent architecture review: approved with no P0-P2 ownership findings.

## Canonical Owner Impact
The root/docs dispatchers, conceptual-diagram skill, Context7 registry, Typst
figure references, and governance test now encode the accepted workflow. The
full SVG review remains an ignored OMX review artifact; accepted durable
decisions are captured in these guidance owners and this debrief.
