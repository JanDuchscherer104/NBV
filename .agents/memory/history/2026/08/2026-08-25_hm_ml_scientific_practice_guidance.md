---
id: 2026-08-25_hm_ml_scientific_practice_guidance
date: 2026-08-25
title: "HM ML scientific practice guidance"
status: done
topics: [scaffold, academic-writing, hm, reproducibility]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - .agents/skills/academic-writing/SKILL.md
  - .agents/skills/academic-writing/references/empirical-reporting-and-reproducibility.md
  - .agents/skills/academic-writing/references/hm-scientific-practice.md
  - scripts/tests/test_agent_governance_g002.py
codex_thread: codex://threads/01a03839-e87c-7160-a79d-7cc1e8c6d588
repo_object_format: sha1
repo_head: a7c7b5da4cc8788fa0cef07d5900822662d4f36a
repo_branch: "codex/hm-ml-scientific-practice"
worktree_kind: linked
---

## Task
Add a dated HM scientific-practice branch and the missing ML venue-reporting precision to academic writing guidance.

## Method
Mapped HM ASPO and GWP §§7–8 and 11–12 into one disclosed institutional reference, then added only the uncertainty, aggregate-compute, and access/licensing gaps supported by current official ML venue guidance.

## Findings
The empirical guide now names uncertainty construction assumptions, material preliminary/failed compute, and artifact access/licensing. The new HM reference keeps documentation/retention distinct from public-access exceptions, preserves the statute's applicability caveat, and routes declaration realization back to the exact Typst owner.

The academic-writing entry point now routes HM/FK07 assessment work directly to that institutional overlay, including method, data/software documentation, access/licensing, AI-program, and declaration questions that do not pass through the empirical-results branch.

## Commits
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/a7c7b5da4cc8788fa0cef07d5900822662d4f36a
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/08cb63edf2aee197ce276c4aee2fb29a1444b777

## Verification
- `make scaffold-audit scaffold-audit-self-test check-agent-memory PYTHON_INTERPRETER=/home/jd/repos/ARIA-NBV/aria_nbv/.venv/bin/python` — passed before debrief generation.
- `python scripts/tests/test_agent_governance_g002.py` — passed, 25 checks.
- All eight official HM/ML links returned HTTP 200 on 2026-08-25.
- Independent review of revised staged diff `044bd41af4cfc9bdbcd022f7d8d1080ab697cd280848abebced6848507e541b4` — approved after separating retention from access restrictions and refreshing ICLR/ICML to 2026.
- Independent review of routing follow-up `66a148dd0779a25cd63e66fc04e5041c681980f4dc7142c3cd16a9f077c8ebd4` — approved with no findings; the focused governance suite passed 25 checks.
- `git diff --check` — passed.

## Canonical Owner Impact
Updated the generic empirical-writing contract and added one dated HM branch. Scientific evidence remains owned by exact code, data, configuration, artifact, and thesis sources.
