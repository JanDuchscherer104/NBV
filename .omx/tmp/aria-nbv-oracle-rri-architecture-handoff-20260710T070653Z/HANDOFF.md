# ARIA-NBV Oracle/RRI Architecture Critique Handoff

Created: 2026-07-10T07:06:53Z  
Source checkout: `/home/jd/repos/ARIA-NBV` at `f6d108d5d494f7cb49d877d2a381fd0f3a1b0b90`  
Source branch: `codex/full-rri-rollout-worktree`  
Status: planning evidence only; no runtime implementation is authorized by this handoff.

## Purpose

This package gives a fresh reviewer the complete recent evidence trail for an
ARIA-NBV architecture cleanup around Oracle-RRI supervision, `rri_metrics`,
counterfactual rollouts, data handling, and offline rollout generation. The
reviewer's job is to expose unresolved design errors and return one smaller,
coherent, implementation-ready plan. It must not simply reconcile filenames.

The main target is a deep module structure: a small interface at each seam,
with scientific semantics, orchestration, persistence, and UI adapters owned
once. The desired outcome is increased leverage and locality, fewer public
surfaces, and a demonstrated reduction in scoped active Python LOC.

## Read First

1. `GPT-5_6_PRO_CRITIQUE_BRIEF.md` defines the requested review, constraints,
   required evidence, and PR deliverable.
2. `artifacts/.omx/specs/autoresearch-aria-nbv-module-pruning-revision-20260710/`
   is included in full (`mission.md`, `sandbox.md`, `report.md`, and
   `completion.json`). Its report is the newest critique of the prior plan and
   its completion artifact records the approved validator result; together they
   are the immediate challenge set.
3. `artifacts/.omx/specs/autoresearch-aria-nbv-module-pruning-20260709/report.md`
   is the main evidence report. Its HTML map is adjacent.
4. `artifacts/.omx/specs/autoresearch-aria-nbv-oracle-boundaries-20260709/report.md`
   contains the cross-package ownership review.
5. `artifacts/.omx/plans/autopilot-aria-nbv-oracle-metrics-refactor-20260709T165010Z.md`
   is the latest concise implementation draft, but it remains draft-pending
   review and is not an approved design.

## Important Conflict To Resolve

Earlier work proposed that top-level `aria_nbv.pipelines` owns Oracle-RRI
generation. Later work proposed `aria_nbv.oracle.pipelines` and deleting the
top-level package. Both arrangements are present here because they represent
the reasoning trail, not settled truth. The reviewer must decide the actual
composition owner from the current source/import graph and explain why the
chosen module passes the deletion test. Do not preserve either arrangement only
because an older artifact names it.

The same caution applies to proposed `oracle/rewards.py`: the corrected
artifacts reject it as a formula owner. Canonical gain and return mathematics
must have one metrics-owned implementation; oracle code may select a label
field or reward mode but must not redefine the mathematics.

## Package Contents

- `artifacts/`: byte-preserving copies of previous-pass plans, handoffs,
  reports, visual maps, debriefs, and the two validator-state snapshots.
  This explicitly includes the complete
  `.omx/specs/autoresearch-aria-nbv-module-pruning-revision-20260710/` package.
- `guidance/`: the root/package guidance and source-order snapshot needed to
  understand the prior routing rules. Re-read the live repository versions
  before committing because these copies can become stale.
- `input/previous-pass-artifact-list.png`: the user-provided artifact list that
  anchored this collection.
- `ARTIFACT_CATALOG.md`: reading order, provenance, and supersession status.
- `MANIFEST.sha256`: checksums for integrity verification.

## Current-Checkout Warning

The source checkout was dirty at packaging time, including `rri_metrics`,
`rollouts`, `pipelines`, Streamlit panels, Lightning, tests, and documentation.
Do not use it as the base for a critique PR or infer that its uncommitted code
is a decided architecture. The review brief requires a fresh worktree from the
post-PR15 remote base.

## Suggested Skills

- `mempalace-aria-nbv:agent-behavior`: choose the planning/review lane and
  preserve traceability.
- `mempalace-aria-nbv:graphify`: rebuild the current dependency evidence before
  accepting any architectural claim from this package.
- `mempalace-aria-nbv:code-review-aria-nbv` and `oh-my-codex:code-review`:
  perform a blocker-first, read-only review of the live source and draft plan.
- `improve-codebase-architecture` plus `codebase-design`: apply depth, seam,
  deletion-test, leverage, and locality reasoning to the final recommendation.
- `mempalace-aria-nbv:counterfactual-rollout-planner` and
  `mempalace-aria-nbv:entity-aware-rri`: validate replay and target-oracle
  contract claims.
- `mempalace-aria-nbv:zarr-python`: use only if reviewing rollout-store schema
  ownership or persistence semantics.

## Stop Condition

The next agent is done only after it has committed a critique-and-revised-plan
PR from a clean worktree. The PR must identify every unresolved decision,
reject unsupported interfaces/adapters, provide a data-flow map for generating
new limited offline rollout samples, and set executable gates for LOC
reduction, CI, and Streamlit verification. It must not claim that the refactor
or its end-to-end validation has already happened.
