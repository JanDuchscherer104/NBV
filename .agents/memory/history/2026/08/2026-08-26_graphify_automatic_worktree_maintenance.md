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
repo_head: 3471828f262aae5998cf234891fee77ed3cdd27d
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

After rebasing, maintenance also treats a deleted projection owner as a rebuild
signal while strict admission still rejects the stale projection. This lets an
upstream owner removal repair itself without weakening query admission.
The strict checker materializes raw HEAD blobs beneath the authenticated Git
administrative directory instead of capacity-limited system tmpfs. The docs
pre-push hook also clears hook-scoped Git bindings before hermetic fixture repos
create commits.

## Commits
- [e03831ba10a64653d56ab7367b994f7e10307edd](https://github.com/JanDuchscherer104/ARIA-NBV/commit/e03831ba10a64653d56ab7367b994f7e10307edd)
- [5c54e23b5669a3efad2ef6049789409bc7fd7929](https://github.com/JanDuchscherer104/ARIA-NBV/commit/5c54e23b5669a3efad2ef6049789409bc7fd7929)
- [14cc4092440b8256e73e0109d86ed3cd7f63789b](https://github.com/JanDuchscherer104/ARIA-NBV/commit/14cc4092440b8256e73e0109d86ed3cd7f63789b)
- [5b6b7c498480a59b54f144be75774059e4e98d00](https://github.com/JanDuchscherer104/ARIA-NBV/commit/5b6b7c498480a59b54f144be75774059e4e98d00)
- [f7985d470815343fc8ab26217f699fe6cb5e6d54](https://github.com/JanDuchscherer104/ARIA-NBV/commit/f7985d470815343fc8ab26217f699fe6cb5e6d54)
- [1d151e90e59fbb8b38c61888314750def11d1579](https://github.com/JanDuchscherer104/ARIA-NBV/commit/1d151e90e59fbb8b38c61888314750def11d1579)
- [a448bc598a0e415ab7a7b3ba18af4d96ba8d09a6](https://github.com/JanDuchscherer104/ARIA-NBV/commit/a448bc598a0e415ab7a7b3ba18af4d96ba8d09a6)
- [3471828f262aae5998cf234891fee77ed3cdd27d](https://github.com/JanDuchscherer104/ARIA-NBV/commit/3471828f262aae5998cf234891fee77ed3cdd27d)

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

The removed-owner regression and the complete CI-equivalent scaffold, docs,
ownership, and focused lint suites passed again after the final rebase.

`make graphify-session-readiness-integration` completed both real explicit and
parentless disposable worktree paths in 304 seconds on the local host.

## Canonical Owner Impact
The setup scripts, seeder, reconciliation owner, freshness helper, maintenance
hook, and their focused tests are the canonical owners updated by this work.
