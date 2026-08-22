---
id: 2026-08-22_target_population_inspection
date: 2026-08-22
title: "Target Population And Admission Inspection"
status: done
topics: [streamlit, targets, admission, iou, dataset-inspection]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/data_handling/vin_store/target_inventory.py
  - aria_nbv/aria_nbv/dataset_bundle.py
  - aria_nbv/aria_nbv/oracle/pipelines/admission_evidence.py
  - aria_nbv/aria_nbv/app/panels/training_dataset.py
  - aria_nbv/aria_nbv/app/panels/campaign_generation.py
codex_thread: codex://threads/01a023ce-d7cb-7552-9936-6255e3485e9f
repo_object_format: sha1
repo_head: 0e20bc8f11e76743f0d835d548ecc973d41dc77d
repo_branch: codex/streamlit-session-cache-plan
worktree_kind: linked
---

## Task

Add statistically useful, read-only inspection of complete detected and GT
target populations and of the exact campaign admission audit without changing
generation, persistence, schemas, or training behavior.

## Method And Findings

The VIN root store now has one presentation-free target inventory that retains
zero-target samples and excludes padded, non-finite, or invalid geometry with
explicit counts. Training Dataset renders availability, class support, OBB
volume and aspect ratio, and detected confidence from that inventory.

Campaign admission evidence is independently validated against campaign,
source-manifest, and audit identities. Campaign Generation renders exact
admission reasons, finite same-class oriented-IoU evidence, ambiguity,
duplicate GT use, and scene-macro admission rates. The reader enforces the
canonical strict oriented-IoU threshold greater than 0.20 for admitted rows.
Inventory class counts are explicitly not presented as detector accuracy.

## Verification

- 98 focused target, admission, matching, bundle, and Streamlit tests passed.
- Ruff format and lint passed on all changed Python paths.
- Targeted mypy passed on both new presentation-free readers.
- Compileall and git diff checks passed.

## Canonical-State Impact

Current truth is owned by the new read-only domain projections, the existing
Training Dataset and Campaign Generation panels, and their focused tests. No
schema, artifact, campaign-generation, training, service, or dependency
contract changed.
