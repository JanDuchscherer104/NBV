---
id: 2026-08-26_graphify_automatic_worktree_maintenance
date: 2026-08-26
title: "Graphify automatic worktree maintenance"
status: done
topics: [graphify, worktrees, codex, setup]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - scripts/setup_codex_worktree_env.sh
  - scripts/setup_worktree_env.sh
  - scripts/graphify_worktree_seed.py
  - scripts/reconcile_graphify_worktree.py
  - scripts/check_graphify_freshness.py
codex_thread: codex://threads/01a03a4a-114d-7f71-b9ec-140f32b8b20b
repo_object_format: sha1
repo_head: 470cdf5152bd614b6d087bbbd37afb6aa46a48cd
repo_branch: "codex/fix-parentless-graphify-setup"
worktree_kind: linked
---

## Task
Make every Codex worktree inherit only a query-admissible graph while keeping
Graphify 0.9.48's semantic lifecycle and cache namespaces authoritative.

## Method
Validated explicit and parentless source selection before parent runtime use;
anchored semantic caches at the registered primary checkout; delegated
incremental extraction to upstream `graphify extract`; and routed automatic
maintenance through the existing setup boundary and pre-commit hook.

## Findings
`scripts/setup_codex_worktree_env.sh` now rejects malformed modes and unsafe
canonical cache topology before parent admission, handles hook-provided Git
bindings, and normalizes successful setup to silence. `scripts/setup_worktree_env.sh`
uses independently authenticated primary cache targets, while
`scripts/graphify_worktree_seed.py` records them without trusting a selected
parent's cache links. Reconciliation rebuilds the projection only for changed
projection owners and invokes the upstream incremental extractor for the
declared standard/deep consumers.

The follow-up keeps that extractor active even for an equal Git tree, so dirty
inputs and cold deep mode remain upstream-detector decisions. Linked maintenance
validates its current owned seed and canonical cache links before reconciliation;
the mutating seed path safely migrates older owned cache links to the primary.

The final topology boundary uses explicit Git directory and work-tree arguments
with command-scoped `core.worktree` for every cross-worktree operation. The
pinned upstream command-path proof asserts Graphify 0.9.48, rejects a legacy
flat standard-cache entry for deep mode, and records deep-only lookup/save
namespaces. Guidance now reserves strict state diagnostics for CI and pre-push
owners rather than ordinary model actions.

The final proof adds an opt-in disposable-worktree integration target. It runs
the generated Codex TOML bridge with both present and empty source values,
requires silent setup, performs a real query through the pinned runtime, and
checks both child cache links resolve beneath the canonical primary `.data`
root. Standard and deep command-path cache assertions now prove their actual
mode-specific namespace containment.

## Commits
- [cc1a76f301d37aeb7fcb0d4283f66cd86e69b1b8](https://github.com/JanDuchscherer104/ARIA-NBV/commit/cc1a76f301d37aeb7fcb0d4283f66cd86e69b1b8)
- [ec52c743cebcb8be0151797e151109987b381f25](https://github.com/JanDuchscherer104/ARIA-NBV/commit/ec52c743cebcb8be0151797e151109987b381f25)
- [805b4149d6145a5b335b82d5cd65a1848910183f](https://github.com/JanDuchscherer104/ARIA-NBV/commit/805b4149d6145a5b335b82d5cd65a1848910183f)
- [470cdf5152bd614b6d087bbbd37afb6aa46a48cd](https://github.com/JanDuchscherer104/ARIA-NBV/commit/470cdf5152bd614b6d087bbbd37afb6aa46a48cd)

## Verification
Focused seed, reconciliation, freshness, session, setup, guidance, governance,
and CI-impact suites passed; Ruff, shell syntax, diff checks, automatic
maintenance, and strict Graphify state checks passed. Fresh disposable explicit
and empty-source setup both emitted no output, produced query-admissible graphs,
answered a real Graphify query, and linked both semantic caches under the
canonical primary checkout.

The pinned Graphify 0.9.48 command-path test also verified warm-standard zero
dispatch, one-file semantic refresh, deep namespace isolation, cold-deep
warmup, legacy-flat-cache rejection, and matching lookup/save prompt
fingerprints.

`make graphify-session-readiness-integration` completed both real explicit and
parentless disposable worktree paths in 304 seconds on the local host.

## Canonical Owner Impact
The setup scripts, seeder, reconciliation owner, freshness helper, maintenance
hook, and their focused tests are the canonical owners updated by this work.
