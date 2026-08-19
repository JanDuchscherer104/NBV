---
id: 2026-08-14_cuda_campaign_contract_hardening
date: 2026-08-14
title: "CUDA Campaign Contract Hardening"
status: done
topics: [rollouts, cuda, campaign, verification]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/oracle/pipelines/campaign.py
  - aria_nbv/aria_nbv/oracle/pipelines/cli.py
  - aria_nbv/aria_nbv/oracle/pipelines/rollout_dataset.py
  - aria_nbv/aria_nbv/oracle/pipelines/shards.py
  - aria_nbv/tests/oracle/test_campaign.py
  - aria_nbv/tests/rollouts/test_cli_typer.py
  - aria_nbv/tests/rollouts/test_dataset_writer.py
---

## Task

Close and prove the CUDA rollout campaign contracts after the G002 campaign
core, while keeping the broad rollout, Streamlit page, rich inspection, and
external GitHub writes out of this story.

## Method And Findings

Hardened the campaign and writer owners around a mandatory CUDA/PyTorch3D
preflight before source or rollout writes, including nested device fields and
the source renderer backend. The campaign remains one serial local worker;
process-group watchdogs now terminate, quarantine, and record timed-out
attempts before continuing.

The implementation now enforces strict actor-visible target admission,
including an explicit exact-one GT-match count, and explicit reasons for
non-admitted targets. Profile and resume identity checks fail closed on
mismatched payloads or configuration evidence. It also provides deterministic
one-target/profile work units and identity hashes; writer-owned root-support
preflight with the 9-versus-10 candidate boundary; exact six-profile recipes
and intermediate trajectory prefixes; staged validation, atomic promotion,
completion evidence, and flushed JSONL events; and resume only for fully
matching validated evidence. Typed status and the presentation-free CLI expose
progress, terminal outcomes, and failure reasons without adding Rerun
monitoring or a collection abstraction.

The architecture audit's duplicate-quarantine finding was repaired by using a
single shard-owned quarantine owner for both worker and parent timeout paths.
The duplicate campaign helper was removed, and root-support policy remains
writer-owned. Legacy V0 target/shard behavior and the existing TargetLineage,
target-array, and Zarr schema were preserved.

## Verification

- Focused campaign, rollout-writer, CLI, and app-router verification passed:
  116 tests passed.
- Format, lint, and path-scoped diff checks passed after the contract repairs.
- The full rollout suite retains one known pre-existing failure,
  `test_multihorizon_highgain_profile_selects_exact_ordered_cross_scene_roots`.
  Its unchanged `v1_observed` configuration selects the Oracle GT target
  source; G004 does not alter that configuration or behavior, so the failure
  is outside this story.
- No broad campaign was launched, and no push, pull request, issue, or other
  external GitHub write was performed.

## Canonical-State Impact

The seven package and test paths above remain the canonical implementation and
verification owners. No separate agent-memory or state update is required.
This debrief owns only the history record; the parent workflow owns the
focused local commit for the implementation paths.
