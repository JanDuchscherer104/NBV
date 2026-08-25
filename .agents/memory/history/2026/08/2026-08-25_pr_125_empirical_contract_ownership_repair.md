---
id: 2026-08-25_pr_125_empirical_contract_ownership_repair
date: 2026-08-25
title: "PR 125 empirical contract ownership repair"
status: done
topics: [scaffold, academic-writing, scientific-review, verification]
confidence: high
canonical_updates_needed:
  - .agents/skills/academic-writing/SKILL.md
  - .agents/skills/academic-writing/references/empirical-reporting-and-reproducibility.md
  - .agents/skills/scientific-review/SKILL.md
  - .agents/skills/typst-authoring/SKILL.md
  - scripts/scaffold/fixtures/routing.json
  - scripts/tests/test_agent_governance_g002.py
touched_owner_paths:
  - .agents/skills/academic-writing/SKILL.md
  - .agents/skills/academic-writing/references/empirical-reporting-and-reproducibility.md
  - .agents/skills/scientific-review/SKILL.md
  - .agents/skills/typst-authoring/SKILL.md
  - scripts/scaffold/fixtures/routing.json
  - scripts/tests/test_agent_governance_g002.py
codex_thread: codex://threads/01a02ab6-c75e-7313-be12-e5f90ae0cde3
repo_object_format: sha1
repo_head: dfcf9f85c3fa5e5fa09f72f3ba0875983afc2093
repo_branch: "codex/pr109-academic-scaffold-salvage"
worktree_kind: linked
---

## Task

Resolve the final independent-architecture blocker on PR #125: the empirical
reporting contract was stored under the non-mutating scientific-review skill
while authoring, review, and Typst realization all needed it.

## Method

Mapped every pointer to the contract, retained its single canonical content,
and moved it to the argument-construction owner. Updated review and realization
as consumers, then strengthened the governance test. Corrected the claim-ledger
template so generated context can no longer be presented as implementation
evidence.

## Findings

Empirical guidance now has one authoring owner at
`.agents/skills/academic-writing/references/empirical-reporting-and-reproducibility.md`.
Scientific review consumes the authoring contract independently; Typst consumes
it only for realization. The move removes the cross-role private-reference
cycle without duplicating the experimental requirements. The routing fixture
and governance test name the new owner.

## Commits

- [dfcf9f85c3fa5e5fa09f72f3ba0875983afc2093](https://github.com/JanDuchscherer104/ARIA-NBV/commit/dfcf9f85c3fa5e5fa09f72f3ba0875983afc2093) — implementation: give empirical guidance one authoring owner

## Verification

- `python3 scripts/tests/test_agent_governance_g002.py` — 25 governance tests passed.
- `uv run --no-project --with pytest --with ruff pytest -q scripts/tests/test_routing_trials.py scripts/tests/test_scientific_review_trials.py` — 91 tests passed.
- `make scaffold-audit scaffold-audit-self-test debrief-index check-agent-memory PYTHON_INTERPRETER=python3` — passed.
- `git diff --check` — passed.

## Canonical Owner Impact

Academic-writing owns the reusable empirical argument contract. Scientific
review retains the independent review procedure; Typst authoring retains only
realization procedure. Active thesis, code, tests, configuration, and evidence
artifacts remain their exact source owners.
