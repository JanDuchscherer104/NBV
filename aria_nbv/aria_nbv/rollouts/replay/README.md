# Finite-Candidate Replay

`aria_nbv.rollouts.replay` owns the in-memory transition protocol used during
rollout generation. It combines a finite candidate table, a score source, a
policy specification, and a state transition while retaining masks and
provenance.

## Main Contracts

| Contract | Purpose |
| --- | --- |
| `CandidateScores` | Compact values aligned to the hard-valid candidate rows. |
| `RolloutPolicySpec` | Selection family and its deterministic/stochastic parameters. |
| `CounterfactualPoseGeneratorConfig` | Bounded rollout and candidate-generation composition. |
| `CounterfactualTrajectory` | Ordered selected poses and transition facts. |
| `CounterfactualRolloutResult` | Complete generated chain plus diagnostics. |

Import the stable surface from `aria_nbv.rollouts`:

```python
from aria_nbv.rollouts import (
    CandidateScores,
    CounterfactualPoseGeneratorConfig,
    RolloutPolicySpec,
)
```

Policies select only from hard-valid rows. Invalid rows never receive sentinel
scores, and negative valid scores remain selectable because masking—not
zero-filling—defines the support.

Replay is storage-independent. `trace.py` and `zarr_store.py` own conversion to
persisted factual tables; Oracle pipeline composition supplies targets,
candidate generation, scoring, and environment transitions.

Detailed state, policy, and callback protocols live in public docstrings and
the [generated API reference](../../../../docs/reference/index.qmd).

## Verification

```sh
cd aria_nbv
uv run ruff check aria_nbv/rollouts/replay
uv run pytest tests/rollouts/test_counterfactuals.py \
  tests/rollouts/test_replay_oracle_golden_parity.py
```
