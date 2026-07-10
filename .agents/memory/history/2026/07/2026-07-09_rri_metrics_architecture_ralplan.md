---
id: 2026-07-09_rri_metrics_architecture_ralplan
date: 2026-07-09
title: "RRI Metrics Architecture RALPLAN"
status: done
topics: [aria-nbv, rri-metrics, architecture, ralplan]
confidence: high
canonical_updates_needed: []
artifacts:
  - .omx/plans/ralplan-rri-metrics-architecture-handoff-20260709T094553Z.json
  - .omx/plans/ralplan-rri-metrics-architecture-20260709T094553Z.md
  - .omx/specs/rri-metrics-architecture-review-20260709T094553Z.html
---

## Task

Planned a better `aria_nbv.rri_metrics` module hierarchy after the first
post-PR15 hierarchy refactor still felt over-nested and too public.

## Method

Used repo guidance, `make context-heavy` artifacts, Graphify query evidence,
and RALPLAN-style architect/critic review. The work was planning-only; no
package implementation files were changed.

## Output

The consensus plan recommends one justified nested family,
`rri_metrics.rollout`, while collapsing shallow one-file folders back to
`rri_metrics.logging` and `rri_metrics.plotting`. It keeps cross-seam DTOs in
`types.py`, colocates rollout DTOs with producer modules, separates core return
tensors from diagnostics, and requires a TorchMetric state-contract test.

The critic initially required five clarifications: move
`selected_path_length_tensor` to diagnostics, make TorchMetric state enforcement
testable, keep `DistanceBreakdown` in `types.py` for the first pass, avoid a
generic `rollout/utils.py`, and restrict cross-surface changes to mechanical
import retargeting. Those changes were integrated and the final critic verdict
was APPROVE.

## Verification

- `aria_nbv/.venv/bin/python -m json.tool
  .omx/plans/ralplan-rri-metrics-architecture-handoff-20260709T094553Z.json`
  validated the handoff JSON.
- The `.omx` artifacts are ignored by `.git/info/exclude`; the visible dirty
  code/docs worktree state was pre-existing and unrelated to this planning
  handoff.

## Canonical State Impact

No canonical state update is needed. This is an implementation handoff for a
future package refactor, not a thesis semantics or project-decision change.
