---
id: 2026-08-24_pr105_slim_reviewed_intent_revision
date: 2026-08-24
title: "PR105 Slim Reviewed Intent Revision"
status: done
topics: [scaffold, intent, routing, governance]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - .agents/skills/agent-behavior/SKILL.md
  - .agents/skills/agent-behavior/agents/openai.yaml
  - .agents/skills/agent-behavior/references/reviewed-intent.md
  - scripts/tests/test_agent_governance_g002.py
codex_thread: codex://threads/019fff4c-cc77-7351-bb81-9759852617c6
repo_object_format: sha1
repo_head: 87047e8b0ec0db5e2fc6b2c5aac8c65a349e8941
repo_branch: "codex/pr105-slim-rewrite"
worktree_kind: linked
---

## Task

Reconstruct PR #105 from current `origin/main` as a compact owner-routing
contract without tracked model-run output or PR-specific evaluator machinery.

## Method

- Added the lowest-shared-owner invariant to the `agent-behavior` entrypoint.
- Disclosed accepted-specification, exact-owner, accepted-plan, and reviewed-
  intent precedence through one conditional reference.
- Kept routing execution output under the existing ignored `.agents/work/`
  boundary and replaced behavioral measurement with deterministic governance
  assertions.

## Findings

- General human intent is consulted only after scoped requirements, exact
  owners, and accepted sequencing leave a material choice unsettled.
- `.agents/skills/agent-behavior/references/reviewed-intent.md` is the single
  detailed owner for that decision order; the 88-line entrypoint retains only
  the trigger and core invariant.
- Raw events, responses, reports, local paths, and runtime identifiers are not
  source owners or test fixtures and remain untracked.

## Verification

- `python -m pytest -q scripts/tests/test_agent_governance_g002.py`: 24 passed.
- `python -m ruff check scripts/tests/test_agent_governance_g002.py`: passed.
- `python -m ruff format --check scripts/tests/test_agent_governance_g002.py`:
  passed.
- `quick_validate.py .agents/skills/agent-behavior`: passed.
- `make scaffold-audit`: 12 skills, 0 errors, 0 warnings.
- `make scaffold-audit-self-test`: 33 self-tests and 24 governance checks
  passed.
- `git ls-files '.agents/work/routing-trials/**'`: no tracked paths.
- `git check-ignore .agents/work/routing-trials/probe/events.jsonl`: matched
  `.gitignore`'s `.agents/work/` rule.

## Canonical Owner Impact

The production skill and its one-hop reference own the active guidance; the
governance test owns its deterministic regression contract. This debrief is an
episodic verification receipt and introduces no competing policy surface.

## Commits

- [87047e8b0ec0db5e2fc6b2c5aac8c65a349e8941](https://github.com/JanDuchscherer104/ARIA-NBV/commit/87047e8b0ec0db5e2fc6b2c5aac8c65a349e8941)
  — add the slim reviewed-intent route and deterministic contract tests.
