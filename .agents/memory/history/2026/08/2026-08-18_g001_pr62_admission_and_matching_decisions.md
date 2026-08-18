---
id: 2026-08-18_g001_pr62_admission_and_matching_decisions
date: 2026-08-18
title: "G001 PR62 admission and matching decisions"
status: done
topics: [cuda, rollout-campaign, target-matching, memory]
confidence: high
canonical_updates_needed:
  - .agents/memory/state/DECISIONS.md
  - .agents/memory/state/OPEN_QUESTIONS.md
files_touched:
  - .agents/memory/state/DECISIONS.md
  - .agents/memory/state/OPEN_QUESTIONS.md
  - .agents/memory/history/2026/08/2026-08-18_g001_pr62_admission_and_matching_decisions.md
---

## Task
Persist the G001 D2 admission contract and retain D1 as an explicitly
unresolved target-matching decision for PR62 repair.

## Method
Inspected the target worktree's canonical memory owners and repository memory
contract, then captured the requested decisions without changing implementation
or configuration files.

## Findings
D2 is adopted: with `N_q = 60`, minimum valid root support is
`max(12, ceil(0.25 * N_q)) = 15`; 14 valid candidates are rejected and 15 are
admitted. The current PR62 code/config value `10` is stale and must be repaired
before generation.

D1 remains unresolved. Current implementation evidence supports same-class
oriented IoU strictly greater than `0.20` plus exact uniqueness. Current
artifacts do not include the runner-up score or score gap, so choosing a thesis
composite `mu + gap` requires defining the score, `tau_mu`, `tau_gap`, and the
no-runner-up convention, followed by a new exact-transform audit.

## Verification
`make check-agent-memory` and `git diff --check` passed after the edits. The
focused local commit contains only the two canonical memory files and this
debrief; no implementation, configuration, GitHub, or OMX state was changed.

## Canonical State Impact
D2 is now current truth in `DECISIONS.md`. D1 is retained as an open question
in `OPEN_QUESTIONS.md` and is deliberately not selected.
