# RRI Metrics

`aria_nbv.rri_metrics` owns prepared Relative Reconstruction Improvement (RRI),
finite-horizon return kernels, ranking diagnostics, ordinal binning, and
stateful metric adapters. Oracle evidence preparation lives in
`aria_nbv.oracle`; operational rollout validity lives in
`aria_nbv.rollouts.audits`.

## Prepared RRI

```python
from aria_nbv.rri_metrics import RriConfig, compute_rri

result = compute_rri(before_distances, after_distances, config=RriConfig())
candidate_rri = result.rri
```

The differentiable formula is

```text
RRI(q) = (D(P_t, M) - D(P_t union P_q, M)) / max(D(P_t, M), epsilon)
```

RRI is dimensionless and may be negative for a valid candidate. Invalidity is
therefore never encoded as a low or zero RRI value; it remains a separate hard
mask and reason-code contract.

## Select the Right Module

| Module | Responsibility | Differentiable |
| --- | --- | ---: |
| `point_mesh` | Point-to-mesh and mesh-to-point distance primitives. | Where PyTorch3D permits |
| `rri` | Prepared candidate-aligned RRI formula and diagnostics. | Yes |
| `returns` | Step gains, endpoint gains, and finite-horizon return kernels. | Tensor kernels only |
| `ranking` | Top-k hits, selected-action comparison, regret, and rank. | No |
| `ordinal` | Empirical RRI binning for one-step CORAL supervision. | No |
| `torchmetrics_single` | Stateful one-step evaluation. | No |
| `torchmetrics_multi` | Stateful selected-rollout evaluation. | No |

The package root intentionally exports only `compute_rri`, `RriConfig`,
`RriResult`, and `RriOrdinalBinner`. Import specialized reducers from their leaf
modules.

## Finite-Horizon Semantics

`returns.py` owns reusable mathematical reducers; rollout stores own factual
transition rows; QH Lightning owns fitted targets and metric lifecycle. Direct
conditional-Q regression and CORAL decoding are scorer concerns and do not
change the RRI label definition.

The exact equations, shapes, and masking preconditions live in source
docstrings and the [generated API reference](../../../docs/reference/index.qmd).
Scientific interpretation belongs to the active
[method chapter](../../../docs/typst/thesis/sections/04-method/04-05-finite-candidate-value-model.typ).

## Verification

```sh
cd aria_nbv
uv run ruff check aria_nbv/rri_metrics
uv run pytest tests/vin/test_rri_binning.py tests/vin/test_coral.py
```

Run the focused return or ranking tests when changing those leaf modules.
