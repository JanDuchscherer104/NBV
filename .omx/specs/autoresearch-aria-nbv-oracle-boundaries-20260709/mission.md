# Mission

Produce an artifact-gated architecture proposal for ARIA-NBV module boundaries across:

- `aria_nbv.oracle`
- `aria_nbv.rri_metrics`
- `aria_nbv.rollouts`
- `aria_nbv.data_handling`

The proposal must be grounded in current code and previous OMX artifacts. It must resolve the user's concern that earlier plans invite redundant definitions, especially around endpoint/root gains, Oracle-RRI scorers, rollout rewards, and target-selection DTOs.

## Validation Mode

`prompt-architect-artifact`

The completion artifact must record an architect approval verdict and point to the final report.

## Required Output

- A coherent module tree for each concerned package.
- Responsibilities for each module.
- Interaction rules between modules.
- Explicit single-owner decisions for:
  - point-mesh distance computation
  - RRI scalar formula
  - root-normalized target gain
  - endpoint gains
  - discounted rollout returns
  - target selection/task DTOs
  - rollout replay DTOs
  - oracle pipelines
- A code-review synthesis with remaining risks.

## Non-Goals

- Do not implement the refactor.
- Do not change source package code.
- Do not create new target descriptors, Q_H implementations, or VIN/Lightning changes.

