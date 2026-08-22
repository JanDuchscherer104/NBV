# Stored-rollout session/cache seam context

## Task statement

Run a focused Ralplan for the stored-rollout Streamlit session/cache seam, then
publish exactly two evidence-backed GitHub issues:

1. Deepen stored-rollout session, identity, caching, and invalidation.
2. Reuse typed inspection results across Streamlit, CLI, and exports; depend on
   the first issue.

Implementation and pull requests are explicitly deferred.

## Desired outcome

- One consensus-reviewed plan limited to the session/cache seam and its later
  typed-result consumer.
- Behavior-locking tests precede refactoring.
- Measurable completion criteria cover cache identity, invalidation, lazy reads,
  atomic same-path store replacement, and cross-page ownership.
- Two GitHub issues, with the typed-result issue depending on the cache issue.

## Exact baseline

- Repository: `JanDuchscherer104/ARIA-NBV`
- Worktree: `/home/jd/.codex/worktrees/aria-streamlit-session-cache-plan`
- Branch: `codex/streamlit-session-cache-plan`
- Base: `origin/main`
- SHA: `a3be5a625a40597f3050c34fc5d89ba26b093be4`
- Explicit git-dir/work-tree status is clean. Ordinary `git status` is unsafe in
  this repository because shared `core.worktree` points at another worktree.

## Known facts and evidence

- `aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:177-198` owns the
  replacement-sensitive cached reader/validation/manifest bundle.
- `aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:221-325` owns one wide,
  string-selected Streamlit projection dispatcher. Domain functions remain in
  `aria_nbv.rollouts`.
- `aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:328-354` computes a
  replacement-sensitive identity from relative file paths, stat metadata, and
  the promoted content seal without reading payload bytes solely for identity.
- `aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:377-480` owns topology,
  failure, report, reader, projection, inventory, and explicit invalidation.
- `aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py:22-366`
  already proves bounded candidate materialization, lazy lightweight reads,
  same-path replacement, mutation detection, promotion validation, and cache
  recomputation.
- `aria_nbv/aria_nbv/rollouts/read_model.py`, `inspection.py`, and
  `reporting.py` are presentation-free owners for persisted meaning,
  projections, and deterministic export frames.
- `aria_nbv/aria_nbv/rollouts/info_cli.py:52-169` already consumes the same
  inspection/reporting owners for validation, compact statistics, preflight,
  and report-bundle export.
- `aria_nbv/aria_nbv/utils/rich_summary.py:21-276` owns generic structured tensor
  diagnostics and optional Rich/plain-text rendering. It must remain a
  rendering adapter rather than acquire rollout-domain semantics.

## Locked constraints

- No scientific or persistence behavior changes.
- Domain projections remain in `aria_nbv.rollouts`.
- No generic projection framework and no compatibility aliases.
- Preserve lazy reads and atomic same-path store-replacement detection.
- Add behavior-locking tests before refactoring.
- Issue A is one focused PR with no visual redesign.
- Issue B is a separate PR and depends on Issue A.
- Reassess scientific-figure grammar, shared page framing, and typed per-workflow
  state only after both deeper seams exist.

## Unknowns and planning questions

- How small can the extracted/deepened session owner remain while removing the
  wide dispatcher and manual cache-clear coupling?
- Which cache dependencies need explicit invalidation tests beyond current
  same-path replacement coverage?
- What is the smallest shared typed-result slice that gives genuine
  Streamlit/CLI/export parity without adding speculative CLI surfaces?

## Likely touchpoints

- `aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py`
- a focused stored-rollout session/cache module under the same panel package
- `aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py`
- `aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py`
- later only: `aria_nbv/aria_nbv/rollouts/{read_model,inspection,reporting,info_cli}.py`
- later only: `aria_nbv/aria_nbv/utils/{rich_summary,cli_format}.py`

## Retrieval status

Graphify bootstrap was reinitialized from a compatible sibling worktree, but
the resulting graph is still `unusable`: its source revision is not an ancestor
of this HEAD and projection-owner digests differ. No graph claims are used.
Planning evidence falls back to exact current sources and focused tests.
