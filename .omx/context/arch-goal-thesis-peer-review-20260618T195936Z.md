# Ralph Context Snapshot: Arch-Goal Thesis Peer Review

Created: 2026-06-18T19:59:36Z

## Task Statement

Complete the active Codex goal: run an OMX autoresearch-goal arch-goal with at
least ten useful iterations, peer-review every active thesis section and total
coherence, compare against seminar paper, litkg, theory docs, and local/external
literature, rank inclusion candidates from
`.omx/specs/autoresearch-thesis-lit-review`, produce conflict/citation/inclusion
matrices, identify exact thesis patches and dashy TODO markers, then implement
the approved patch set in `docs/typst/thesis` through a Ralph-style verified
completion path.

## Desired Outcome

The current thesis seed compiles and reflects the research audit: seminar
implementation details are adapted without overclaiming, geometric-learning
theory has a dedicated section, related-work citations are close to claims,
candidate/replay and target-selection ownership are clear, and unresolved
conflicts are visible through dashy TODO helpers.

## Known Evidence

- `.omx/specs/autoresearch-thesis-lit-review/report.md` contains Iterations
  2-33, covering candidate-query architecture, offline value learning,
  objective boundaries, symmetry contracts, rollout readiness, target matching,
  frame invariance, feature banks, recurrence, and sequence-model boundaries.
- `.omx/specs/autoresearch-thesis-lit-review/result.json` records architect
  approval through Iteration 33.
- `.omx/goals/autoresearch/peer-review-and-patch-aria-nbv-thesis-sections-a/peer_review_matrix.md`
  records the initial conflict/citation/inclusion matrix and patch evidence.
- `.omx/goals/autoresearch/arch-goal-thesis-peer-review-with-at-least-ten-a/arch_goal_completion_audit.md`
  maps at least ten iterations to exact thesis patches.
- The current patch set is under `docs/typst/thesis`.

## Constraints

- Preserve unrelated dirty worktree changes.
- Do not treat historical seminar evidence as current thesis direction.
- Do not promote planned `Q_H` behavior as implemented evidence.
- Use dashy TODO helpers for unresolved conflicts, validation needs, and open
  decisions.
- Keep tables in booktabs style.

## Unknowns / Open Questions

- Final experiment scale, manifest-backed counts, target thresholds, gamma, and
  final appendix detail remain intentional thesis TODOs.
- `docs/AGENTS.md` names `scripts/nbv_typst_includes.py`, but that helper is not
  present in this worktree; include graph was inspected directly instead.

## Likely Touchpoints

- `docs/typst/thesis/main.typ`
- `docs/typst/thesis/appendix/index.typ`
- `docs/typst/thesis/sections/*.typ`
- `.omx/goals/autoresearch/arch-goal-thesis-peer-review-with-at-least-ten-a/`
- `.agents/memory/history/2026/06/2026-06-18_thesis_peer_review_patch.md`
