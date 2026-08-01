---
name: entity-aware-rri
description: Validate ARIA-NBV target selection or target-specific RRI labels and diagnostics.
---

# Validate Target-Aware RRI

1. **Locate the evidence owner.** Read [RRI guidance](aria_nbv/aria_nbv/rri_metrics/AGENTS.md)
   and the exact active target-task or replay-contract section. Completion: the
   label, implementation, and claim owners are identified.
2. **Classify the evidence.** Use the owner to separate selection, label, and
   evaluation evidence before changing a target-related surface. Hand off
   multi-step evaluation to `counterfactual-rollout-planner`, spatial contracts
   to `nbv-geometry-contracts`, and concrete failures to `diagnose-aria`.
3. **Verify target support.** Run the owner’s focused RRI/data test or document
   render. Completion: target support and the result’s evidence are traceable
   to the owning source.
