---
id: 2026-09-01_candidate_persistence_codecs_pr5
date: 2026-09-01
title: "Candidate persistence codecs PR5"
status: done
topics: [candidate-generation, persistence, zarr, vin, rollout-inspection]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/rollouts/trace.py
  - aria_nbv/aria_nbv/rollouts/zarr_store.py
  - aria_nbv/aria_nbv/rollouts/read_model.py
  - aria_nbv/aria_nbv/data_handling/vin_store/candidate_codec.py
codex_thread: codex://threads/01a05903-535c-7c21-8ae7-e7c17079427c
repo_object_format: sha1
repo_head: 8590b7e2ea544f88cdbce39b6228b70cafe5ca16
repo_branch: "codex/candidate-persistence-codecs-pr5"
worktree_kind: linked
---

## Task
Persist the frozen candidate-generation facts through additive rollout-Zarr and VIN codecs without changing legacy arrays or actor/training inputs.

## Method
Added versioned immutable trace and VIN DTOs, additive Zarr tables and dictionary bindings, lazy read-model projections, current-store semantic consumers, and fail-closed old/current codec validation. Characterized byte-level legacy preservation and adversarial mixed-version, alignment, sentinel, provenance, and admission failures.

## Findings
- `aria_nbv/aria_nbv/rollouts/trace.py` owns the canonical `CandidateSet` to immutable CPU persistence projection with explicit N/V/A, semantic lineage, admission, program/request, proposal, and legacy-config identities.
- `aria_nbv/aria_nbv/rollouts/zarr_store.py` dual-writes five additive candidate tables plus a codec-local dictionary while preserving every legacy array path, dtype, shape, chunks, values, and encoded chunk bytes.
- `aria_nbv/aria_nbv/rollouts/read_model.py`, inspection, candidate evidence, and Rerun consume persisted semantic facts directly for current stores and retain explicit legacy fallbacks for old stores.
- `aria_nbv/aria_nbv/data_handling/vin_store/candidate_codec.py` owns an independently versioned audit payload; `VinOracleBatch`, Q_H inputs, and legacy `oracle.candidates` bytes remain unchanged.
- Production replay still supplies legacy `CandidateSamplingResult`; PR6 remains the truthful composition owner that will attach the schema-ready `CandidateTraceFacts` to production steps.

## Commits
- [8590b7e2ea544f88cdbce39b6228b70cafe5ca16](https://github.com/JanDuchscherer104/ARIA-NBV/commit/8590b7e2ea544f88cdbce39b6228b70cafe5ca16) — additive candidate persistence codecs and consumer migration.
- [4e0960ee4a3cd6cb716299914e4556b0431b554b](https://github.com/JanDuchscherer104/ARIA-NBV/commit/4e0960ee4a3cd6cb716299914e4556b0431b554b) — replay golden source receipt and Quartodoc discovery registration.

## Verification
- Focused persistence/inspection matrix: 231 passed, 16 warnings.
- Python-contract remediation matrix: 40 passed, 15 warnings.
- Ruff format/check on all changed Python files: passed.
- Data-handling and rollout public API mypy contracts: passed.
- Focused owned-module mypy retains one pre-existing `no-any-return` diagnostic in the unchanged legacy `_candidate_invalid_reasons` body.
- Architecture and Python-contract exact-diff review: clear, no P0-P2 findings.

## Canonical Owner Impact
The Python codecs, schema contract, typed readers, and tests listed above are the updated current-truth owners. No further canonical update is required in PR5; production replay composition is explicitly staged to PR6.
