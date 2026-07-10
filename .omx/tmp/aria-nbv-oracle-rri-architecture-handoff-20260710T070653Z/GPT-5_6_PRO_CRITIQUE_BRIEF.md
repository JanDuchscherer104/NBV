# GPT-5.6 Pro: Critique And Correct The Oracle/RRI Refactor Plan

## Assignment

Review the supplied prior-pass artifacts against the current, post-PR15
ARIA-NBV source. Produce a critical, evidence-backed architecture assessment
and a revised implementation plan that makes the Oracle-RRI/offline-rollout
data flow materially simpler. Your deliverable is a planning PR, not an
implementation PR.

The current drafts are not authoritative. Treat them as hypotheses. In
particular, test the proposed `aria_nbv.oracle` package and the proposal to
move general generation orchestration from `aria_nbv.pipelines` into
`aria_nbv.oracle.pipelines` against current callers, the actual data flow, and
the deletion test.

## Non-Negotiable Design Invariants

1. A scientific gain or return formula has one implementation owner in
   `rri_metrics`; scalar/tensor, scene/target, table/store, and objective
   callers are adapters to that owner, not independent definitions.
2. `oracle` owns privileged scene/target supervision semantics and the input
   evidence needed to score them. It may choose a reward mode or label field;
   it may not own or duplicate metric mathematics.
3. `rollouts` owns generic finite-candidate replay, traces, persistence, and
   inspection. It must not understand a wide, oracle-specific score/evidence
   DTO merely because it persists values.
4. `data_handling` owns raw/offline data access and persisted-format adapters.
   Actor-visible target selection and privileged GT target-task/crop policy
   must be separated deliberately; do not mechanically split the current
   target-selection file before proving its seams.
5. A data-generation composition root has one owner. Determine whether that
   is `oracle.pipelines` or another existing module from evidence, and delete
   the competing ownership. No top-level `pipelines` shell or compatibility
   facade without a real external downstream contract and removal condition.
6. `rri_metrics` contains only RRI/return mathematics and real metric
   adapters. Training logging policies belong with Lightning; visualization
   belongs with diagnostics/rendering; unused stateful TorchMetrics default to
   deletion after current-import evidence.
7. New DTOs are producer-owned by default. A package `types.py` is reserved
   for a genuine cross-module contract within that package. Persisted row/store
   schemas live beside their persistence owner. Do not create a package-wide
   DTO dumping ground.
8. The resulting eventual refactor must reduce scoped active Python LOC. A
   move alone is not simplification.

## Required Critique Questions

Answer each with exact current file/symbol references and classify it as a
blocker, a required decision, a follow-up, or rejected scope.

1. What is the one canonical owner and interface for normalized error gain,
   log-error gain, endpoint target/log gains, and discounted selected return?
   Demonstrate all duplicate definitions/adapters and require value plus
   gradient parity where an operation is presented as differentiable.
2. Does the proposed top-level `oracle` actually become a deep module, or does
   it merely aggregate shallow files? Identify its smallest external interface
   and the hidden implementation it should own.
3. Which exact symbols from `rollouts/counterfactuals.py`,
   `rollouts/target_counterfactuals.py`, `rollouts/dataset_writer.py`,
   `rollouts/shards.py`, `rollouts/shard_manifest.py`, and `rollouts/cli.py`
   are replay/persistence mechanics versus oracle semantics versus pipeline
   composition? Map each before proposing a move.
4. Separate three currently conflated result shapes: minimum replay selection
   result, scientific oracle labels, and optional evidence retained for a
   store. Give each a proposed producer and persistence adapter. Do not retain
   the current wide DTO by another name.
5. Which `rri_metrics` code is core differentiable return math, ordinary
   evaluation, training-only policy, UI/plotting, or unused test-only
   machinery? Prove production imports before retaining stateful
   `torchmetrics_multi` classes. The named candidate/provenance/path sanity
   helpers are not automatically core metrics.
6. For target selection, distinguish actor-visible model-input identity from
   privileged oracle GT matching/task sampling/crop resolution. State the
   minimum ownership correction necessary for this PR and what must wait.
7. Draw the actual end-to-end data flow for generating a new limited rollout
   dataset: source row -> candidate table -> replay -> scene/target evidence ->
   canonical metric math -> label/persistence -> Zarr reader -> Streamlit page.
   Mark every composition root, DTO crossing, and current duplicate.
8. Identify deletions that reduce LOC rather than rehoming it: stale public
   exports, compatibility wrappers, duplicated helpers, unused TorchMetrics,
   duplicate rollout readers, experimental/legacy code, and the inactive `rl`
   surface. Do not broaden into VIN, Lightning behavior, or a Zarr schema
   rewrite unless a current import cycle/semantic bug proves it necessary.

## Required Method

1. Read the supplied `HANDOFF.md`, guidance snapshot, and artifact catalog.
2. Create a clean worktree, never from the dirty source checkout:

   ```bash
   git -C /home/jd/repos/ARIA-NBV fetch origin --prune
   git -C /home/jd/repos/ARIA-NBV symbolic-ref --short refs/remotes/origin/HEAD
   mkdir -p /home/jd/.agents/work
   git -C /home/jd/repos/ARIA-NBV worktree add -b codex/gpt56-oracle-rri-plan-critique \
     /home/jd/.agents/work/aria-nbv-oracle-rri-plan-critique <resolved-origin-default-branch>
   ```

   If the branch name or worktree exists, choose a timestamped replacement and
   record it. Confirm that the selected base contains the merged PR15 commit.
3. Invoke the skills listed in `HANDOFF.md`; use Graphify first when
   `graphify-out/graph.json` is present. Re-query the live source rather than
   trusting copied line numbers or old dependency claims.
4. Run a blocker-first code review of the plans and the current source. Keep
   evidence separate from inference. Search production imports separately from
   test imports.
5. Record a starting-commit, path-scoped active-Python LOC baseline for
   `rri_metrics`, `oracle` if present, `rollouts`, `pipelines`, and the exact
   `data_handling` files proposed for modification. Do not count tests,
   generated references, or copied handoff files.
6. Build a new visual architecture/data-flow artifact. It must show before and
   after ownership, formula flow, the three DTO classes, and the limited-dataset
   execution path. It should make the composition root testable as an
   interface, not expose every helper.
7. Produce a revised plan with ordered workpackages. Each package needs an
   explicit owner, source moves/deletions, stable interface, regression tests,
   migration/deletion condition, LOC hypothesis, and stop condition.

## Scope And Safety

- Do not implement the refactor in this PR.
- Do not alter VIN scoring, Lightning behavior, RRI semantics, target
  descriptors, Q_H, online RL, or Zarr schema semantics.
- Do not carry old public paths by default. A compatibility adapter requires a
  named released consumer, a bounded interface, and a removal condition.
- Preserve stable console command names only if the actual command contract
  requires it; internal module paths can move.
- Do not rely on the dirty `/home/jd/repos/ARIA-NBV` worktree as evidence of a
  merged or supported public contract.

## Commit And PR Deliverable

Commit the findings on the new worktree branch and open a draft PR. The commit
should contain only review/planning artifacts in their correct repo-owned
locations, normally:

- `.omx/plans/gpt56-oracle-rri-architecture-critique-<timestamp>.md`
- `.omx/specs/gpt56-oracle-rri-architecture-critique-<timestamp>.html`
- `.agents/memory/history/YYYY/MM/<date>_oracle_rri_architecture_critique.md`

Use `.agents/refactors.toml` only for genuinely actionable follow-up items and
validate it through `make agents-db`. Do not commit this temporary handoff
directory or a copy of its evidence into the repository.

The PR description must lead with unresolved blockers, followed by the chosen
module tree and data-flow diagram, then the workpackage sequence. It must
include the baseline LOC command/result, exact source/test evidence, and an
implementation validation matrix that requires all of the following before the
future refactor PR is merged:

- targeted and root CI passing;
- a newly generated limited rollout dataset from the new composition root;
- the associated Streamlit rollout/oracle pages smoke-tested against that
  dataset;
- stale-import scans clean;
- final scoped active-Python LOC strictly below the recorded baseline.

Do not claim these gates have passed in this planning PR. State the exact
future commands/configs required after discovering them from the current tree.
