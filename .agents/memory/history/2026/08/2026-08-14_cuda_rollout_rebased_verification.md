---
id: 2026-08-14_cuda_rollout_rebased_verification
date: 2026-08-14
title: "CUDA rollout rebased verification"
status: in_progress
topics: [rollouts, cuda, campaign, rebase, verification]
confidence: high
canonical_updates_needed: []
files_touched:
  - .configs/build_rollouts_v1_cuda_campaign.toml
  - .configs/build_rollouts_v1_cuda_campaign_writer.toml
  - .configs/rollout_campaign100_source_manifest.json
  - aria_nbv/aria_nbv/oracle/pipelines/campaign.py
  - aria_nbv/aria_nbv/oracle/pipelines/cli.py
  - aria_nbv/aria_nbv/oracle/pipelines/shards.py
  - aria_nbv/aria_nbv/oracle/target_selection.py
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - aria_nbv/aria_nbv/rollouts/reporting.py
  - aria_nbv/aria_nbv/app/panels/campaign_generation.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py
  - aria_nbv/tests/oracle/test_campaign.py
  - aria_nbv/tests/oracle/test_target_selection.py
  - aria_nbv/tests/rollouts/test_cli_typer.py
  - aria_nbv/tests/rollouts/test_dataset_writer.py
  - aria_nbv/tests/rollouts/test_inspection.py
  - aria_nbv/tests/rollouts/test_reporting.py
  - aria_nbv/tests/app/panels/test_campaign_generation_panel.py
  - aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py
---

## Task

Advance the CUDA rollout campaign through the three implementation stories
before the replacement final-rebase story, without launching the broad
campaign. Keep the implementation and operational model simple for the local
RTX 3080 Ti host.

## Method

The implementation branch was rebased from pre-rebase commit
`463c9e7be8149cd32947c392e4546685edd445e6` onto exact `origin/main`
`4748c4dd01e77bae5bdb2ff6932e8980a9416b4c`; the rebased implementation head
is `229d175f3dc6aebab57cb437abe9d607b9bdb093`. Any evidence from before the
issue stories or before this rebase is stale for the replacement final gate.

Issue #58 now trusts only the canonical typed dictionary smoke-evidence
interface; the stringified `ast.literal_eval` compatibility path and synthetic
string-result test are gone. Issue #57 keeps one typed, ordered grouping
vocabulary in `rollouts.inspection` and materializes candidate audit rows once
per store for all reporting summaries. Issue #53 deepens the existing campaign
read model with truthful post-spawn PID/PGID state and validated promoted
artifact records, and keeps the CLI/Campaign Generation/read-only Rollout
Supervision handoff within the existing interfaces.

The missing canonical source prerequisite was closed without relaxing the
100-scene contract: a reviewed immutable V7 source store was completed with one
row per scene, the generated source manifest contains 100 rows across 100
scenes, and strict actor-visible admission produced 434 audit rows, 362
admitted targets, 72 explicitly rejected targets, and 870 deterministic
target/profile work units. Campaign admission audit reads were narrowed to the
persisted geometry/trajectory fields they consume, and CPU/CUDA OBB transform
alignment was repaired at the target-selection boundary.

The real smoke path then exposed and drove root-cause repairs for admission-row
hash normalization and the distinction between the reviewed campaign manifest
file digest and the VIN source-manifest identity. One-row shard lineage is now
bound before writer validation and uses the existing canonical split-hash
function. Failed pre-repair runtime artifacts were preserved under
`.campaign-quarantine-pre-source-lineage-fix-20260814/` rather than deleted.

## Findings

The earlier canonical one-target smoke established the simple local settings:
one serial worker, exactly 60 candidates, renderer
`max_views_per_batch = 2`, selected-depth `chunk_steps = 16`, branch factor 2,
and beam width 2. That diagnostic remains useful for tuning, but it cannot
satisfy the replacement final story after the issue changes.

The hardware evidence does not justify concurrent work units, a larger
candidate population, or another scheduling layer. Free VRAM is not treated as
evidence of idle compute; the GPU was already saturated.

## Verification

- The changed-files AI-slop pass made no changes; post-cleaner verification
  recorded 186 tests.
- Terminal CUDA smoke, final SHA/config-digest proof, independent reviews,
  architecture audit, and the mandatory final quality gate are ledger-owned
  evidence for the replacement final story and are not claimed here before
  that story runs.
- No push, pull request, issue, or other external GitHub write was performed.

## Canonical State Impact

None. The package code, tests, canonical TOML/source manifest, and durable
Ultragoal ledger own current behavior and terminal evidence. No
`.agents/memory/state/*.md` update is needed; this file is episodic debrief only.
