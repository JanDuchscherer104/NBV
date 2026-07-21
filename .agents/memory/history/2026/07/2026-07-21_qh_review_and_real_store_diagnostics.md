---
id: 2026-07-21_qh_review_and_real_store_diagnostics
date: 2026-07-21
title: "Q_H Review and Real-Store Diagnostics"
status: done
topics: [qh, code-review, architecture, docstrings, real-data]
confidence: high
canonical_updates_needed: []
artifacts:
  - /tmp/architecture-review-20260721T104825Z.html
---

## Task

Review and harden the isolated Q_H data/training seam, audit its public Python
docstrings and architecture, and exercise its reader and training contracts
against the requested realistic rollout store without claiming a scientific
training result.

## Result

Independent review blockers were resolved with bounded reader preflight,
correct mixed-horizon maximum semantics, canonical ASE and ATEK identifiers,
removal of the optional availability feature, a minimal training DTO field set,
and contract-focused docstrings with relevant Python-domain cross-references.
The review found no reason to widen the existing one-step Lightning module or
introduce additional DTO layers. The architecture report at
`/tmp/architecture-review-20260721T104825Z.html` is an ephemeral review aid,
not a canonical repository artifact.

The requested store reports `v1_observed` while its target provenance is
`gt_obbs_oracle`, a fail-closed contradiction under the current reader
contract. Its inspected structure contains 160 states, 96 rollouts, and 9,600
candidates, and its VIN manifest matches the expected source. These diagnostics
do not establish real-data trainability: the code intentionally continues to
reject the contradictory store before training.

The worktree now shares the root repository's large data subtrees through
symlinks for `.data/ase_efm`, `.data/ase_meshes`,
`.data/ase_meshes_processed`, and `.data/offline_cache`.

## Verification

- 232 Q_H and adjacent tests passed. One initial config-test collection failed
  because an external submodule path was absent from this worktree environment;
  after using the shared external path, all 28 config tests passed.
- Ruff and the docstring audit passed across the 36 reviewed Python files.
- `make check-agent-memory` passed after this debrief was added.

## Canonical state impact

No canonical update is needed. `PROJECT_STATE.md` already records the runnable
Q_H tracer bullet and keeps the scaled scientific result open; the contradictory
real store adds diagnostic evidence only and does not change that status.
