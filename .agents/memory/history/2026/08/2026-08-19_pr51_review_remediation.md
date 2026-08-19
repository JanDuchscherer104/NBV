---
id: 2026-08-19_pr51_review_remediation
date: 2026-08-19
title: "PR 51 Review Remediation"
status: done
topics: [agent-scaffold, review, guidance, skills]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/skills/agent-behavior/SKILL.md
  - .agents/references/README.md
  - .agents/references/human_owner_intent.md
  - .codex/config.example.toml
  - scripts/scaffold/fixtures/routing.json
  - scripts/tests/test_agent_governance_g002.py
---

## Task

Verify and remediate the eight unresolved GPT-5.6 Pro review threads on PR #51.

## Findings

- The tracked Matt-skill inventory mixed a reviewed upstream snapshot, mutable
  install behavior, and ARIA activation posture. It was neither an immutable
  install contract nor an accepted `.agents/references` owner, so it was retired.
- `writing-for-agents` is optional authoring evidence; ARIA's skill style guide
  and validator own repository requirements.
- Change-locality and reversible-learning procedures remain in
  `agent-behavior`; they were removed from reviewed human-owner preferences.
- Workpackage completion now activates the Git/external-actions reference even
  when a prompt does not mention Git.
- The literature debrief now identifies the reviewed book by edition, publisher,
  date, ISBN, and P3.0 version while labelling the task PDF as local evidence.
- Governance coverage now checks retired-policy absence, live owner paths, and a
  no-Git workpackage-completion routing outcome instead of mirroring an upstream
  inventory.

## Verification

Run the focused governance test, scaffold audit, agent-memory check, and diff
hygiene checks before publication. Resolve review threads only after the pushed
head contains these repairs.

## Canonical-State Impact

The accepted source-order and reference-tree boundaries are restored. The
compact `agent-behavior` route remains the procedural owner; no external skill
inventory or unreviewed human preference becomes current policy.
