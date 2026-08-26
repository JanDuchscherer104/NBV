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
repo_head: 6d0134ba9551e564d7a051e62721b75d408bb746
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

Raw HEAD snapshots now also initialize a private Git index for the exact commit.
That lets upstream Graphify distinguish tracked files from matching `.gitignore`
rules without consulting the mutable source index. The private commands clear
hook-scoped Git bindings, so a pre-commit check cannot reset the caller's index.

The parentless fallback now resolves equally near, query-admissible ancestors
with the existing stable path ordering instead of rejecting a valid worktree
set as ambiguous. A later main-branch tracked paper exposed the legacy PDF
directory link as unsafe; setup now preserves a local tracked PDF directory and
only uses the shared directory link when no PDF input is tracked.

## Commits
- [37b8a8848906c4652fc65d9dc62fc9999990bb2f](https://github.com/JanDuchscherer104/ARIA-NBV/commit/37b8a8848906c4652fc65d9dc62fc9999990bb2f)
- [b6de2ce1b57829de0a05ab7facf10a7cb3bbd0f8](https://github.com/JanDuchscherer104/ARIA-NBV/commit/b6de2ce1b57829de0a05ab7facf10a7cb3bbd0f8)
- [6cd9460698283a07a64b26077bfe0dd1e784ed8b](https://github.com/JanDuchscherer104/ARIA-NBV/commit/6cd9460698283a07a64b26077bfe0dd1e784ed8b)
- [395c8ccb9238ef8959274a902292db34e54be897](https://github.com/JanDuchscherer104/ARIA-NBV/commit/395c8ccb9238ef8959274a902292db34e54be897)
- [b9fe967a20dfcbed6d665344a8da14e68fc67402](https://github.com/JanDuchscherer104/ARIA-NBV/commit/b9fe967a20dfcbed6d665344a8da14e68fc67402)
- [bd8b9fadf573c7a6b829924bf2f2626d3fb8c98d](https://github.com/JanDuchscherer104/ARIA-NBV/commit/bd8b9fadf573c7a6b829924bf2f2626d3fb8c98d)
- [ab4854067a26345fd2f6a92ebccebc2928c10196](https://github.com/JanDuchscherer104/ARIA-NBV/commit/ab4854067a26345fd2f6a92ebccebc2928c10196)
- [153b09fc405d8bd7b6189987fa90e8c7d3a505b0](https://github.com/JanDuchscherer104/ARIA-NBV/commit/153b09fc405d8bd7b6189987fa90e8c7d3a505b0)
- [bc46bdc5ad14431c0d5cd7afa6463bb63380d438](https://github.com/JanDuchscherer104/ARIA-NBV/commit/bc46bdc5ad14431c0d5cd7afa6463bb63380d438)
- [1858f451d7e1ad7aebbf768181ffe757b3f0bbcb](https://github.com/JanDuchscherer104/ARIA-NBV/commit/1858f451d7e1ad7aebbf768181ffe757b3f0bbcb)
- [6d0134ba9551e564d7a051e62721b75d408bb746](https://github.com/JanDuchscherer104/ARIA-NBV/commit/6d0134ba9551e564d7a051e62721b75d408bb746)

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
The tracked-ignored snapshot and hook-bound index regressions passed with the
full freshness suite (29 tests and 20 subtests).

`make graphify-session-readiness-integration` completed both real explicit and
parentless disposable worktree paths in 304 seconds on the local host.

The post-main regression proof ran the exact final commit in two new detached
worktrees with `CODEX_SOURCE_WORKSPACE_PATH` absent and present. Both setups
were silent, retained the tracked `UVFA.pdf`, and resolved standard and deep
cache links under `/home/jd/repos/ARIA-NBV/.data/graphify-semantic-cache`.

## Canonical Owner Impact
The setup scripts, seeder, reconciliation owner, freshness helper, maintenance
hook, and their focused tests are the canonical owners updated by this work.
