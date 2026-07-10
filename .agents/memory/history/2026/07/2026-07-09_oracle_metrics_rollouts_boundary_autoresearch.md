---
id: 2026-07-09_oracle_metrics_rollouts_boundary_autoresearch
date: 2026-07-09
title: "Oracle, Metrics, Rollouts Boundary Autoresearch"
status: done
topics: [aria-nbv, oracle, rri-metrics, rollouts, architecture]
confidence: high
canonical_updates_needed: []
artifacts:
  - .omx/specs/autoresearch-aria-nbv-oracle-boundaries-20260709/report.md
  - .omx/specs/autoresearch-aria-nbv-oracle-boundaries-20260709/completion.json
---

## Task

Produced a validator-gated architecture proposal for resolving responsibility conflicts between `oracle`, `rri_metrics`, `rollouts`, `data_handling`, and the legacy top-level `pipelines` package after PR15.

## Method

Used prior OMX planning artifacts, current source inspection, Graphify query evidence, and independent native `code-reviewer` plus `architect` review lanes. The first draft was tightened after both reviewers found that `oracle` risked becoming an umbrella package and that endpoint/root-gain ownership was still ambiguous.

## Output

The final report proposes:

- `rri_metrics` owns point-mesh primitives, RRI/gain formulas, endpoint returns, diagnostics, TorchMetric adapters, and objective helpers.
- `oracle.scoring` owns scene/target RRI label production, evidence/input preparation, target crop policy, and label-field semantics.
- `oracle.pipelines` replaces the legacy top-level `aria_nbv.pipelines` as a thin executable composition layer without root exports or formula/storage ownership.
- `rollouts` owns replay DTOs, finite-candidate transitions, Zarr storage, q_h replay projection, and read-side inspection.
- `data_handling.targets` owns target-source rows, target-task sampling, actor-visible target selection, and source geometry resolution.

## Verification

The architect validator re-reviewed the revised report and returned `APPROVED` with architectural status `CLEAR`. The code-review lane found no critical or high-severity blockers and its medium findings were integrated into the final artifact.

This was a planning-only pass. Future implementation should update package-level `AGENTS.md` files and public API contract tests when files actually move.
