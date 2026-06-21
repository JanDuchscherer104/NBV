---
id: 2026-06-18_code_review_skill_integration
date: 2026-06-18
title: "Code Review Skill Integration"
status: done
topics: [scaffold, skills, review]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/skills/code-review/SKILL.md
  - .agents/skills/code-review/agents/openai.yaml
---

## Task

Clarified how the ARIA-NBV code-review skill composes with the generic
oh-my-codex code-review harness and the GitHub review-comment handler.

## Output

The repo-local skill now states that `oh-my-codex:code-review` owns independent
review lanes and merge gating, `github:gh-address-comments` owns PR thread
state, and `code-review-aria-nbv` owns ARIA domain context, domain handoffs,
external-review triage, severity mapping, and focused verification choices.

The skill also points review-follow-up work to local sidecars such as
`simplification`, `python-docstrings`, `docs-curator`, `typst-authoring`,
`nbv-geometry-contracts`, `entity-aware-rri`,
`counterfactual-rollout-planner`, `dataset-cache-ops`,
`rerun-nbv-inspector`, `aria-litkg-memory`, and `agents-db`.

## Verification

Verification passed with:

- `python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" .agents/skills/code-review`
- `make check-agent-memory`
