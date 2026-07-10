---
id: 2026-07-10_rri_metrics_ownership_refactor
date: 2026-07-10
title: "RRI Metrics Ownership Refactor"
status: done
topics: [rri-metrics, rollouts, architecture, torchmetrics]
confidence: high
canonical_updates_needed: []
---

WP05 replaced the mixed rollout-metric files with explicit owners for prepared
RRI, differentiable returns, non-differentiable ranking, one-step TorchMetrics,
multi-step TorchMetrics, and rollout operational audits. The package root was
narrowed to four stable symbols. The scene scorer and privileged evidence stay
temporarily under `rri_metrics` for the later WP08 extraction.

The tensor kernels in `returns.py` now own root-normalized gain, log gain,
endpoint gains, and discounted return. Scalar/table adapters delegate to those
kernels. Scene/candidate 3D plotting moved to `rendering.plotting`; lightweight
`RriResult` plots remain in `rri_metrics.plotting`.

Verification covered Ruff, stale-path and import-boundary scans, prepared-RRI
and return-kernel autograd tests, the complete `tests/rri_metrics` and
`tests/rollouts` suites, and affected Lightning, data-handling, plotting, and
public-API tests. Production Python LOC decreased from 68,659 to 68,614.
`make check-agent-memory` was also attempted; it is blocked by the base branch's
pre-existing tracked `.omx` runtime artifacts, not by this debrief.
