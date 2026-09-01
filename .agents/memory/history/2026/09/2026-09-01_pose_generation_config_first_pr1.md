---
id: 2026-09-01_pose_generation_config_first_pr1
date: 2026-09-01
title: "Pose Generation Config First PR1"
status: done
topics: [pose-generation, configuration, candidate-mixture, compatibility]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/pose_generation/config.py
  - aria_nbv/aria_nbv/pose_generation/candidate_mixture.py
  - .configs
codex_thread: codex://threads/01a04842-7454-7353-9a6b-f59cc99302b5
repo_object_format: sha1
repo_head: 93344281bf732e644aab23372bef41a75b9754e9
repo_branch: "codex/pose-generation-config-pr1"
worktree_kind: linked
---

## Task
Implement PR1 of the approved config-first pose-generation deep-module plan without changing candidate behavior or historical evidence identities.

## Method
Characterized origin/main candidate outputs, introduced nested config-as-factory values, migrated active profiles, and independently reviewed the diff twice against the plan.

## Findings
`pose_generation/config.py` now owns typed center, gaze, jitter, and mixture-component authoring. `candidate_mixture.py` retains the established generator/result seam through one private transitional resolver. Active nested profiles use versioned v2 stores and campaign identity; the v1 realistic, writer, and campaign configs remain byte-identical historical evidence.

## Commits
- [93344281bf732e644aab23372bef41a75b9754e9](https://github.com/JanDuchscherer104/ARIA-NBV/commit/93344281bf732e644aab23372bef41a75b9754e9)

## Verification
Focused pose-generation, config, rollout, campaign, CLI, and app tests passed: 141 passed, 1 skipped. Exact full-rule fingerprints, including every named admission mask, match origin/main for all eight active profiles. Ruff format/check, mypy on the new config and benchmark readers, and `git diff --check` passed. Independent review approved with no findings. PR1 remains intentionally non-mergeable alone until stacked PR2 deletes `_legacy_leaf_config`.

## Canonical Owner Impact
Current authoring truth moved to nested component configuration in `pose_generation/config.py`; active rollout and campaign profiles now use that schema. Historical persisted flat metadata remains readable only through bounded dual-format projections.
