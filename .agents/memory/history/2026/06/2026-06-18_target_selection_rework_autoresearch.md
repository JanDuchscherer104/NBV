---
id: 2026-06-18_target_selection_rework_autoresearch
date: 2026-06-18
title: "Target Selection Rework Autoresearch"
status: done
topics: [target-selection, rri, rollouts, thesis, autoresearch]
confidence: high
canonical_updates_needed:
  - aria_nbv/aria_nbv/data_handling/_target_selection.py
  - aria_nbv/tests/data_handling/test_target_selection.py
  - aria_nbv/aria_nbv/rollouts/dataset_writer.py
  - aria_nbv/aria_nbv/rollouts/zarr_store.py
  - docs/typst/thesis/sections/04-method/index.typ
  - docs/contents/theory/candidate_sampling_target_selection.qmd
  - docs/contents/thesis/questions.qmd
  - .agents/memory/state/DECISIONS.md
  - .agents/memory/state/OPEN_QUESTIONS.md
  - .configs/build_rollouts_v1_realistic.toml
artifacts:
  - .omx/specs/autoresearch-target-selection-rework/mission.md
  - .omx/specs/autoresearch-target-selection-rework/sandbox.md
  - .omx/specs/autoresearch-target-selection-rework/report.md
  - .omx/specs/autoresearch-target-selection-rework/result.json
---

## Task

Aggregated the target-selection evidence requested on 2026-06-18 before
reworking the implementation. The research covered transcript
`019ed4da-5d8f-7740-a68e-e2ee800d7bee`, its persisted `.omx` goal artifacts,
distilled memory entries, `.agents/work/target-selection-sampling`, the current
Typst method section, implementation code, tests, rollout persistence, docs,
backlog, and KG route evidence.

## Findings

The current V1 selector mostly preserves the source-boundary contract: observed
or predicted actor-visible targets are selected before GT labels/evaluation, and
GT OBBs are refused as normal V1 target input. The remaining design problem is
that the default selector is still score/TopK oriented, while the current thesis
requirement is a simple actor-visible labelable target pool with relatively
uniform or stratified sampling.

Recommended next step: add a `stratified_uniform` target selection policy with
coarse bins for support, projected area, distance, class, and target-bearing or
hard-turn angle; persist stratum metadata; enable multiple target-conditioned
samples per source snippet; and keep GT matching as deterministic
class-compatible 3D IoU after actor-visible eligibility.

## Verification

Created the autoresearch artifact set under
`.omx/specs/autoresearch-target-selection-rework/`. The artifact records the
validation prompt and an approved prompt-architect result. No production code or
active thesis files were changed in this iteration.
