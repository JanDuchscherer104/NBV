---
id: 2026-08-30_align_recovery_estimand_with_oracle_baseline
date: 2026-08-30
title: "Align Recovery Estimand With Oracle Baseline"
status: done
topics: [thesis, q-h, endpoint-estimand, rollout-inspection, notation]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - aria_nbv/tests/rollouts/test_inspection.py
  - docs/typst/shared/equations/entity.typ
  - docs/typst/shared/equations.typ
  - docs/typst/shared/symbols.typ
  - docs/typst/shared/notation.generated.typ
  - docs/notation.yml
  - docs/_extensions/aria-glossary/notation.generated.lua
  - docs/typst/thesis/main.pdf
codex_thread: codex://threads/01a04fd9-0c7c-7813-a9c5-dc49f2f867a6
repo_object_format: sha1
repo_head: f067236497e534ecac9422b789d22755e7fc79fb
repo_branch: "codex/thesis-recovery-estimand-contract"
worktree_kind: linked
---

## Task
Repair the endpoint-recovery estimand mismatch exposed while reviewing the
Q-learning evidence figure, without conflating independent endpoint evaluation
with persisted rollout diagnostics.

## Method
Traced RQ2, the canonical Typst equation, generated notation projections, and
the rollout-inspection implementation. Kept the scientific estimand and its
diagnostic proxy distinct, added role-sensitive regression coverage, rebuilt
all generated notation surfaces, and independently reviewed the exact candidate.

## Findings
- The canonical recovery fraction now uses the oracle one-step policy in both
  numerator and denominator, matching RQ2's oracle-one-step endpoint-headroom
  baseline in `docs/typst/shared/equations/entity.typ`.
- `aria_nbv/aria_nbv/rollouts/inspection.py` now reports `eta_Q_proxy` over
  persisted `final_cumulative_target_root_gain` and explicitly reserves
  canonical `eta_Q` for independent matched endpoint evaluation.
- Learned one-step remains the comparison baseline for `delta_Q` only;
  changing it cannot alter `eta_Q_proxy`.
- Nonpositive or weak oracle headroom remains an explicit exclusion rather
  than a stabilized ratio or success claim.

## Commits
- [f067236497e534ecac9422b789d22755e7fc79fb](https://github.com/JanDuchscherer104/ARIA-NBV/commit/f067236497e534ecac9422b789d22755e7fc79fb) — align the canonical recovery estimand, diagnostic proxy, generated notation, tests, and rendered thesis.

## Verification
- Ruff format and lint passed for the modified Python files.
- `111` rollout-inspection and report-provenance tests passed.
- `make glossary`, `make thesis-pdf`, `make thesis-pdf-ci`,
  `make typst-authoring-contract`, `make thesis-marker-contract`, and
  `git diff --check` passed; the rendered thesis remains 123 A4 pages.
- Independent scientific review found zero valid P0--P2 findings.
- Targeted mypy could not start through the linked-worktree project because
  `external/efm3d` is uninitialized; direct shared-environment mypy reports a
  large pre-existing repository baseline. Coverage instrumentation also hits
  a pre-existing Torch import error, while ordinary pytest passes.

## Canonical Owner Impact
The nested entity equation owns the canonical scientific definition; the
shared equation/symbol facades and generated notation surfaces project it.
Rollout inspection owns the explicitly non-canonical proxy, and its test owner
locks role applicability, denominator exclusion, and proxy provenance.
