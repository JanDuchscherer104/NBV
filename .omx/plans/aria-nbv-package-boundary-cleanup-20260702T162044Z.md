# Ralplan: ARIA-NBV Package Boundary Cleanup

Status: draft pending architect and critic review.

## Outcome

Produce an implementation-ready, narrowly scoped cleanup plan for PR #15 that
improves package ownership without adding new thesis functionality.

## Principles

1. Candidate-table generation and selected-transition replay are separate
   modules. Keep `pose_generation` about finite candidate rows, masks, and
   pose geometry.
2. A package interface should say the scientific contract it actually
   implements. Names such as `target_finite_horizon` are acceptable as scaffold
   names only when they do not imply a working Q_H implementation.
3. Optional online RL adapters must not look like current thesis core.
4. App panels should be UI glue. Pure reducers can move only when already
   tested or directly adjacent to a required cleanup.
5. No compatibility facade should be added unless an existing public test or
   documented import path requires it.

## Decision drivers

1. Reduce PR #15 merge risk.
2. Align package seams with the current thesis architecture.
3. Avoid scope expansion into target-conditioned model implementation.

## Viable options

### Option A: Counterfactuals-first cleanup

Move `pose_generation.counterfactuals` and
`pose_generation.target_counterfactuals` to `aria_nbv.rollouts`. Update direct
imports, package exports, tests, docs references, and the nested
`rollouts/AGENTS.md` wording if it still assigns rollout transition ownership
to `pose_generation`.

Known live migration surfaces:

- `aria_nbv/aria_nbv/rollouts/trace.py`
- `aria_nbv/aria_nbv/rollouts/zarr_store.py`
- `aria_nbv/aria_nbv/rl/counterfactual_env.py`
- `aria_nbv/aria_nbv/app/panels/counterfactual_rollouts.py`
- `aria_nbv/tests/rollout_fixtures.py`
- `aria_nbv/tests/rollouts/test_zarr_store.py`
- `aria_nbv/tests/pose_generation/test_counterfactuals.py`
- `aria_nbv/tests/rl/test_counterfactual_env.py`
- `aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py`
- `aria_nbv/tests/data_handling/test_public_api_contract.py`
- `docs/_quarto.yml`
- `docs/reference/_sidebar.yml`
- `docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ`

Pros:

- Highest leverage package-edge cleanup.
- Aligns code with candidate-table versus replay evidence ownership.
- Keeps the implementation slice small and testable.

Cons:

- Requires careful import updates across rollouts, tests, docs, and app helpers.
- May expose old public imports. Add no compatibility shim unless tests prove
  it is currently part of the public contract.

Recommended: yes. This is the default execution slice.

### Option B: VIN naming alignment

Adopt the PR #15 model-family names as branch merge policy:
`scene_myopic`, `target_myopic`, and `target_finite_horizon`. Replace vague
names such as `multi_step` only where the files and tests already exist in the
branch being merged.

Pros:

- Reduces branch drift between PR #15 and rollout-diverse work.
- Makes the model interface describe the scientific family.

Cons:

- Easy to turn into architecture implementation by accident.
- Naming alone does not improve runtime behavior.

Recommended: secondary. Do this only if it is directly involved in PR #15 merge
conflicts or import cleanup.

### Option C: Quarantine optional RL adapter

Remove, archive, or explicitly rename `aria_nbv.rl` as experimental.

Pros:

- Prevents online Gymnasium/SB3 control from looking like thesis core.
- Matches roadmap positioning of online RL as later bridge/future work.

Cons:

- Not currently unused. Public package imports, app wiring, and tests exist.
- Deleting it safely requires a broader app/config/test cleanup.

Recommended: follow-up, not part of the first implementation slice.

### Option D: App pure-helper extraction

Move pure reducers and plotting helpers out of Streamlit panels into
`rollouts/inspection.py`, `vin/diagnostics`, or `rri_metrics` leaves.

Pros:

- Better locality and easier unit testing.

Cons:

- High risk of broad UI churn.
- Not needed for the highest-value package move unless duplicate helpers block
  imports.

Recommended: defer unless directly adjacent to Option A.

### Option E: Broad package reshaping

Create new target, scene-memory, Q_H, or data_handling package splits.

Pros:

- Could eventually match the full thesis architecture.

Cons:

- Violates the user's current refactor budget.
- Adds implementation expectations that PR #15 should not carry.

Recommended: no. Treat as explicitly out of scope.

## Architecture Decision Record

Decision: choose Option A as the only default implementation slice. Keep
Options B and D as conditional cleanups. Defer Option C. Reject Option E.

Rationale: Option A repairs the highest-leverage package seam with the smallest
reviewable diff. It also helps the next target-conditioned PR by making
rollouts the owner of transition replay and target-RRI evidence without
pretending that target-conditioned scoring or Q_H is implemented.

Consequences:

- `pose_generation` becomes closer to a candidate-table module.
- `rollouts` becomes the home for selected-transition replay contracts.
- Tests must prove that import updates preserve current behavior.
- Documentation and nested guidance may need a small wording update.

## Execution handoff

Preferred lane after consensus: a single-owner execution lane, because the
first slice is mostly import ownership plus tests. Use team execution only if
VIN naming and RL quarantine are intentionally split into independent follow-up
work.

Suggested task order:

1. Inspect all imports of `pose_generation.counterfactuals` and
   `pose_generation.target_counterfactuals` in the target worktree.
2. Move the two modules into `aria_nbv/aria_nbv/rollouts/`.
3. Remove those exports from `pose_generation.__init__` and add appropriate
   rollouts exports only if local package style expects them. Treat root
   `pose_generation.__init__` exports as intentionally moved to direct
   `aria_nbv.rollouts` imports, not preserved by a facade, unless an existing
   public test proves the old root import is a public contract.
4. Update tests and docs references with direct imports from `aria_nbv.rollouts`.
5. Update `aria_nbv/aria_nbv/rollouts/AGENTS.md` if its ownership wording is
   now stale.
6. Run targeted validation, then stop.

Validation:

- `cd aria_nbv && uv run ruff format --check <touched-python-files>`
- `cd aria_nbv && uv run ruff check <touched-python-files>`
- `cd aria_nbv && uv run pytest tests/pose_generation/test_counterfactuals.py`
- `cd aria_nbv && uv run pytest tests/rollouts`
- `cd aria_nbv && uv run pytest tests/rri_metrics`
- `cd aria_nbv && uv run pytest tests/lightning`
- `cd aria_nbv && uv run pytest tests/rl/test_counterfactual_env.py`
- `cd aria_nbv && uv run pytest tests/app/panels/test_counterfactual_rollouts_panel.py`
- `cd aria_nbv && uv run pytest tests/data_handling/test_public_api_contract.py`
- `rg -n "pose_generation\\.(counterfactuals|target_counterfactuals)" aria_nbv/aria_nbv aria_nbv/tests docs/_quarto.yml docs/reference docs/typst/thesis/sections`
- If a broader docs/history scan is run, classify historical or archived hits
  separately instead of treating `.agents/archive`, transcript/history dumps,
  generated docs output, or old meeting notes as active stale imports.

Exit criteria:

- No package code claims target-conditioned scoring or Q_H is implemented.
- No new target descriptor, scene-memory, online RL core, or broad
  data_handling/app restructuring appears in the diff.
- The diff is smaller or strictly better scoped than before.
- Targeted tests pass, or any skipped dependency-gated tests are reported with
  exact skip reason.
