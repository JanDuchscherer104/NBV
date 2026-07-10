# Mission: ARIA-NBV Module-Pruning Plan Revision

Date: 2026-07-10

## Objective

Re-audit the 2026-07-09 module-pruning research and the latest draft execution
plan against the current ARIA-NBV code. Identify contradictions, redundant
ownership, shallow modules, and unresolved design decisions before producing a
new consensus RALPLAN.

## Inputs

- `.omx/state/autoresearch-aria-nbv-module-pruning-20260709/autoresearch-state.json`
- `.omx/specs/autoresearch-aria-nbv-module-pruning-20260709/report.md`
- `.omx/plans/autopilot-aria-nbv-oracle-metrics-refactor-20260709T165010Z.md`
- Current `aria_nbv.rri_metrics`, `aria_nbv.rollouts`,
  `aria_nbv.pipelines`, and `aria_nbv.data_handling` source and tests
- Current package guidance and glossary terms
- Graphify relationship evidence

## Required Output

A review artifact that:

1. separates observed code facts from recommendations;
2. applies module, interface, depth, seam, adapter, leverage, locality, and the
   deletion test consistently;
3. identifies where the latest draft plan is not execution-ready;
4. resolves fixed ownership invariants without prematurely prescribing final
   interfaces;
5. lists explicit decisions that must be closed by the next RALPLAN;
6. defines hard reduced-LOC and end-to-end validation requirements.

## Validator

Use prompt-and-architect validation. Approval requires a current-code-grounded,
non-contradictory pre-RALPLAN handoff with no silent compatibility, formula,
DTO, or data-generation ownership assumptions.
