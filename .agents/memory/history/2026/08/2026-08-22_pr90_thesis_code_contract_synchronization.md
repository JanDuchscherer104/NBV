---
id: 2026-08-22_pr90_thesis_code_contract_synchronization
date: 2026-08-22
title: "PR90 thesis code contract synchronization"
status: done
topics: [qh, learning-contract, thesis, rri, state]
confidence: high
canonical_updates_needed: []
codex_thread: codex://threads/01a02a39-bcfd-76f0-bd84-6da1d9d0abb2
---

## Task
Resolve PR 90 review blockers by making checkpoint admission, actor-state vocabulary, and reward/RRI thesis claims match the implementation.

## Method
Reviewed exact PR head `17a19e6bcd`, traced persisted replay lineage into `QhDataContract`, separated the complete learning identity from the actor-state identity, updated canonical Typst sources, regenerated derived glossary/notation artifacts, and ran focused Python and Typst verification.

## Findings
- `aria_nbv/aria_nbv/rollouts/qh_reader.py` now retains the exact candidate-configuration, rollout-configuration, and behavior-policy mixture admitted by a corpus.
- `aria_nbv/aria_nbv/lightning/qh_datamodule.py` rejects unequal configured stage horizons and hashes the data contract, maximum horizon, and versioned selected-row Huber aggregation together.
- `docs/typst/shared/equations/rl.typ` distinguishes marginal and cumulative target RRI diagnostics from the root-normalized training reward and cumulative root gain.
- The thesis maps `qh_cf0_v1` to `S0-pose` and `qh_cfplus_gt_depth_v1` to the implemented privileged selected-depth carrier; geometry fusion remains explicitly planned.
- `.agents/skills/agent-behavior/SKILL.md` now requires thesis and executable scientific/behavioral claims to remain synchronized.

## Verification
- `python3 scripts/glossary_build.py all`: passed, 56 glossary terms, 82 symbols, and 92 equations validated.
- `make thesis-pdf-ci typst-authoring-contract`: passed.
- Focused Ruff format/check over touched Python and tests: passed.
- Focused pytest matrix over Q_H DataModule, module, and reader: 109 passed.
- Targeted mypy remains blocked by the repository baseline: 741 errors across 80 imported files when checking three touched source files.

## Canonical Owner Impact
- Python owners: `qh_reader.py`, `qh_datamodule.py`, and their focused tests.
- Scientific owners: shared Typst symbols, equations, glossary, active thesis sections, and regenerated notation/glossary projections.
- Guidance owner: `agent-behavior/SKILL.md` thesis-code synchronization invariant.
