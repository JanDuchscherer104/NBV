---
id: 2026-08-23_g003_owner_specific_preferences
date: 2026-08-23
title: "G003 Owner-Specific Preferences"
status: done
topics: [scaffold, guidance, ownership, memory]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - .agents/skills/README.md
  - .agents/skills/python-standards/references/general_conventions.md
  - aria_nbv/aria_nbv/app/AGENTS.md
  - scripts/tests/test_agent_governance_g003.py
codex_thread: codex://threads/019fff4c-cc77-7351-bb81-9759852617c6
repo_object_format: sha1
repo_head: f4ff24c9901d16250ef11f423e8b8c4e3e44ac86
repo_branch: "codex/scaffold-intent-pr3"
worktree_kind: linked
---

## Task

Record the completed G003 owner-specific guidance workpackage at its exact
clean implementation head, with its scoped owners, verification evidence, and
known Graphify limitation.

## Method

- Used the exact owner files and the focused G003 governance test; no Graphify
  query or generated bundle was used.
- Recorded the stacked base as
  `61a93f19792433f6d94f265e5e43d5f08d80fccc`.
- Excluded the root `AGENTS.md`, `.agents/references/human_owner_intent.md`, the Graphify
  bundle/generated graph, and package code from this owner-specific work.

## Findings

G003 restored scoped contracts and focused proof across the four listed owner
paths. Graphify after commit was `state=unusable` at
`graph_revision=a121cd821f7748f979c2cddf0f7c3af0e0b6a5a7` and
`head=f4ff24c9901d16250ef11f423e8b8c4e3e44ac86`, because “Graphify detector
reported an unbounded stale-source set”; `stale_sources=[]` and
  `next_action=bash scripts/setup_worktree_env.sh`. Rerunning setup completed, but Graphify
remained unusable and `graphify-usable-check` failed. No Graphify bundle or
generated artifact changed. G005 owns setup reproducibility as a later accepted
story, not a canonical update here.

## Verification

- G003 direct: 4 passed; G002: 27 passed.
- Scaffold audit: `skills=12 errors=0 warnings=0`.
- Scaffold self-test: `passed=33 failures=0`; upstream self-test: 4 OK.
- Ruff format/check, `compileall`, and `git diff --check`: passed.
- Independent review: APPROVE/CLEAR after frontmatter, body, all-byte, and
  collapsed/subordinate preservation checks.

## Canonical-State Impact

`canonical_updates_needed` is empty. The workpackage's canonical owner paths
are recorded for provenance; this debrief and the regenerated index are
episodic/derived navigation surfaces. No Graphify query or generated artifact
was added, and setup reproducibility remains assigned to G005.

## Commits
- [f4ff24c9901d16250ef11f423e8b8c4e3e44ac86](https://github.com/JanDuchscherer104/ARIA-NBV/commit/f4ff24c9901d16250ef11f423e8b8c4e3e44ac86) — G003 owner-specific guidance workpackage: restored scoped contracts and focused proof
