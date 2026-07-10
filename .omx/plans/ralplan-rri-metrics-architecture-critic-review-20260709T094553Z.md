# Critic Review: `aria_nbv.rri_metrics` Architecture Plan

Verdict: APPROVE_WITH_CHANGES

## Blocking Objections

No architecture-level blocker. The target direction is sound, but the plan
needs edits before execution so implementers do not guess.

## Required Plan Edits

- Move `selected_path_length_tensor` out of `rollout/returns.py` or explicitly
  justify it there. The plan calls `returns.py` the core objective-like tensor
  module but labels path length as a diagnostic. Put it in
  `rollout/diagnostics.py` unless a separate cost module is explicitly chosen.
- Make TorchMetric state enforcement a real test/check, not just an AST/static
  check or review pass. Current `torchmetrics_multi.py` has 50 `add_state(...)`
  calls with no class-level state docs, while `torchmetrics_single.py` shows
  the enforceable pattern.
- Resolve DTO inconsistency: the plan keeps `DistanceBreakdown` in `types.py`
  for the first pass, while the visual report says it should move to
  `distance.py` unless cycles force otherwise. Pick one.
- Add private-helper placement guidance for the `multi_step.py` split. Tiny
  helpers should stay private in the leaf that uses them, with minimal
  duplication if needed; do not invent a generic `rollout/utils.py` bucket
  without a real cycle.
- Narrow cross-surface touchpoints to import-only updates. Broad app,
  Lightning, tests, generated API refs, and docs changes are acceptable only as
  mechanical import retargeting, not behavior changes.

## Non-Blocking Implementation Cautions

- Keep `rollout/__init__.py`, `oracle/__init__.py`, and
  `objectives/__init__.py` empty or narrow; do not recreate `metrics.__all__`.
- Keep `_histogram_overlay` and `_plot_hist_counts_mpl` imports pointed at
  `utils.plotting`, not re-exported from `rri_metrics.plotting`.
- Do not touch VIN behavior, Lightning logging semantics, Q_H implementation,
  target descriptors, data stores, or app panels beyond import fixes.

## Final Recommendation

Go after the required edits above. Do not proceed to implementation from the
current plan verbatim, but this is not a revise-from-scratch case.
