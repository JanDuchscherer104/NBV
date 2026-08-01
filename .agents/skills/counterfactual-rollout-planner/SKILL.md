---
name: counterfactual-rollout-planner
description: Plan ARIA-NBV counterfactual rollouts or compare finite-candidate Q_H evaluation.
---

# Plan Counterfactual Rollouts

1. **Locate the decision owner.** Read [rollout guidance](../../../aria_nbv/aria_nbv/rollouts/AGENTS.md)
   and the exact active method or experiment section. Completion: the code,
   claim, and evaluation owners are identified.
2. **Frame the comparison.** Obtain the owner-defined budget, validity, and
   evidence requirements before changing a rollout or reporting a result. Hand
   off target evidence to `entity-aware-rri`, spatial contracts to
   `nbv-geometry-contracts`, and concrete failures to `diagnose-aria`.
3. **Verify the selected branch.** Use the owner’s focused rollout test or
   document render. Completion: the comparison evidence and its verification
   are traceable to the owning source.
