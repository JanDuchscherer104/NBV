---
id: 2026-08-24_candidate_owner_intent_capture
date: 2026-08-24
title: "Candidate owner intent capture"
status: done
topics: [scaffold, agent-behavior, memory]
confidence: high
canonical_updates_needed:
  - .agents/skills/agent-behavior/references/reviewed-intent.md
  - .agents/memory/README.md
touched_owner_paths:
  - .agents/skills/agent-behavior/references/reviewed-intent.md
  - .agents/memory/README.md
  - scripts/new_debrief.py
  - scripts/tests/test_agent_governance_g002.py
  - scripts/tests/test_debrief_index.py
codex_thread: codex://threads/019fff4c-cc77-7351-bb81-9759852617c6
repo_object_format: sha1
repo_head: a03a3660d9597958653d139a3071dccccf45b4e9
repo_branch: "codex/intent-candidate-capture"
worktree_kind: linked
---

## Task
Add a compact, current-user-gated route for reusable human-preference candidates.

## Method
Placed candidate eligibility and promotion authority in the existing
`agent-behavior` reviewed-intent branch, then exposed the optional evidence
shape in the native debrief owner and generator.

## Findings
Candidates require a direct instruction or bounded recurring evidence, a precise
cross-task statement, and an exact target owner. They remain debrief evidence
until the current user accepts that specific statement; no proposal registry or
automatic `human_owner_intent.md` update was added.

## Commits
- [773a7117c05d67f987a39b610962d391418bc1e5](https://github.com/JanDuchscherer104/ARIA-NBV/commit/773a7117c05d67f987a39b610962d391418bc1e5) — candidate route: documented eligibility, evidence, scope, and current-user acceptance.
- [a03a3660d9597958653d139a3071dccccf45b4e9](https://github.com/JanDuchscherer104/ARIA-NBV/commit/a03a3660d9597958653d139a3071dccccf45b4e9) — native debrief integration: documented and generated the optional evidence shape.

## Verification
`pytest -q scripts/tests/test_agent_governance_g002.py scripts/tests/test_debrief_index.py` passed (61 tests); `quick_validate.py .agents/skills/agent-behavior` passed.

## Canonical Owner Impact
The reviewed-intent reference now owns candidate routing; the memory README and
generator own the optional native-debrief representation.
