---
id: 2026-08-24_pr125_academic_authoring_review_resolution
date: 2026-08-24
title: "PR 125 academic authoring review resolution"
status: done
topics: [scaffold, academic-writing, scientific-review, typst, routing]
confidence: high
canonical_updates_needed:
  - .agents/skills/README.md
  - .agents/skills/academic-writing/SKILL.md
  - .agents/skills/scientific-review/SKILL.md
  - .agents/skills/typst-authoring/SKILL.md
  - scripts/scaffold/fixtures/routing.json
  - scripts/ci_impact.py
  - scripts/scaffold_audit.py
  - .agents/skills/scientific-review/references/review-protocol.md
touched_owner_paths:
  - .agents/skills/README.md
  - .agents/skills/academic-writing/SKILL.md
  - .agents/skills/academic-writing/references/source-grounded-workflow.md
  - .agents/skills/scientific-review/SKILL.md
  - .agents/skills/scientific-review/references/review-protocol.md
  - .agents/skills/typst-authoring/SKILL.md
  - scripts/scaffold/fixtures/routing.json
  - scripts/scaffold/fixtures/routing_prompts.jsonl
  - scripts/scaffold/run_routing_trials.py
  - scripts/scaffold_audit.py
  - scripts/ci_impact.py
  - scripts/tests/test_agent_governance_g002.py
  - scripts/tests/test_ci_impact.py
  - scripts/tests/test_routing_trials.py
repo_object_format: sha1
repo_head: 6393da2cae8f4e911f8f86bf5a2d851b67d0bf25
repo_branch: "codex/pr109-academic-scaffold-salvage"
worktree_kind: linked
codex_thread: codex://threads/01a02ab6-c75e-7313-be12-e5f90ae0cde3
---

## Task

Resolve the remaining valid review findings for the academic-authoring skill
split while retaining separate authoring, review, and Typst realization owners.

## Decision

Keep `scientific-review` as a broad advisory review skill, but route each
review kind to existing claim, section, notation, empirical, and active-thesis
owners. Keep the shared phase transition in the skills style guide rather than
duplicating it in all three skills.

## Findings

- Independent review requires a fresh candidate-bound context; otherwise its
  result is advisory.
- A repository-edit request can compose authoring, optional review, and Typst
  realization, but scientific release remains a separate human/evidence gate.
- The focused routing suite now uses natural synthesis, mechanical-repair,
  frozen-review, claim-revision, empirical-revision, and non-writing cases.
- Workspace-write routing cases must produce the required active-Thesis diff
  and compile/render receipt; their disposable subject checkout excludes both
  evaluator fixtures and the candidate repository history.
- Empirical-result candidates need a candidate-bound review without a blocking
  finding before they are ready for Typst realization.
- Authoring-owner changes trigger both documentation and scaffold CI gates.
- Routing subjects exclude evaluator fixtures, tests, debriefs, and OMX state;
  their fresh Git baseline detects untracked and committed writes, and
  workspace-write trials accept only the required Typst roots plus a full-page
  render receipt.
- Empirical readiness requires an independent review receipt separately from
  its blocking, advisory, or clear finding gate.
- Subject cleanup removes only the exact linked-worktree registry entry; a
  sibling-worktree regression proves unrelated registrations survive.
- Baseline evidence includes ignored files, and proof compares every rendered
  PNG page identity with Poppler's bounded PDF page count.
- Bubblewrap mounts only the sanitized subject, a separate receipt directory,
  system runtime files, and the Codex auth file; its regression proves the
  evaluator's absolute fixture path cannot be read.
- The sandbox builder accepts an injected test auth file, keeping its
  production auth requirement while allowing credential-free CI validation.
- PR #104 had no unresolved review threads at its exact live head, so it needed
  no retrospective patch.

## Commits

- [6c1669ac1d4c7367148a481fcbf88b625135d903](https://github.com/JanDuchscherer104/ARIA-NBV/commit/6c1669ac1d4c7367148a481fcbf88b625135d903) — implementation: compose academic authoring phases
- [6f7d170b9b88607a333a4de00bccb58c3abb06d1](https://github.com/JanDuchscherer104/ARIA-NBV/commit/6f7d170b9b88607a333a4de00bccb58c3abb06d1) — implementation: enforce authoring routing evidence
- [a76cef4590579f46dff29e59c398529ab9443765](https://github.com/JanDuchscherer104/ARIA-NBV/commit/a76cef4590579f46dff29e59c398529ab9443765) — implementation: close routing review gaps
- [8f74f1183dbb09b00900cf66bd6225dba6039959](https://github.com/JanDuchscherer104/ARIA-NBV/commit/8f74f1183dbb09b00900cf66bd6225dba6039959) — implementation: preserve sibling worktree registrations
- [3e61fb34c2c17083a58c3c44d68d2d53ab0fd790](https://github.com/JanDuchscherer104/ARIA-NBV/commit/3e61fb34c2c17083a58c3c44d68d2d53ab0fd790) — implementation: close routing evidence escapes
- [e2348b3091932c882e7d8c55b447e86c5db78388](https://github.com/JanDuchscherer104/ARIA-NBV/commit/e2348b3091932c882e7d8c55b447e86c5db78388) — implementation: isolate routing trial subjects
- [6393da2cae8f4e911f8f86bf5a2d851b67d0bf25](https://github.com/JanDuchscherer104/ARIA-NBV/commit/6393da2cae8f4e911f8f86bf5a2d851b67d0bf25) — test: make routing isolation portable

## Verification

- `uv run --no-project --with pytest --with pyyaml pytest -q scripts/tests/test_agent_governance_g002.py scripts/tests/test_routing_trials.py scripts/tests/test_scientific_review_trials.py` — 68 passed.
- `uv run --no-project --with pytest --with pyyaml pytest -q scripts/tests/test_routing_trials.py scripts/tests/test_ci_impact.py scripts/tests/test_agent_governance_g002.py scripts/tests/test_scientific_review_trials.py scripts/tests/test_debrief_index.py` — 124 passed, 50 subtests passed.
- `make scaffold-audit scaffold-audit-self-test ci-impact-self-test check-agent-memory PYTHON_INTERPRETER=python3` — passed.
- `uv run --no-project --with pytest --with pyyaml pytest -q scripts/tests/test_routing_trials.py scripts/tests/test_ci_impact.py scripts/tests/test_agent_governance_g002.py scripts/tests/test_scientific_review_trials.py` — 90 passed, 51 subtests passed.
- The three modified skills passed the skill validator.
- `git diff --check` and routing fixture JSON/JSONL parsing passed.

## Canonical Owner Impact

The skills style guide owns cross-skill phase states. Individual skills retain
only their own workflow branches, and routing fixtures remain the tested
navigation contract rather than a source of scientific truth.
