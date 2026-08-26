# Oracle Evidence and Labels

`aria_nbv.oracle` owns privileged evidence preparation, scene- and target-level
RRI scoring, GT target-task selection, label payloads, and generation pipeline
composition. Its outputs supervise and evaluate actor-side models; privileged
geometry is not an ordinary VIN or QH input.

## Public Scorers

```python
from aria_nbv.oracle import (
    SceneRriScorerConfig,
    TargetRriScorerConfig,
)

scene_scorer = SceneRriScorerConfig().setup_target(sample=snippet)
target_scorer = TargetRriScorerConfig().setup_target(sample=snippet)
```

Both scorers evaluate finite candidate tables against prepared point-mesh
evidence. `SceneRriScorer` evaluates the scene crop; `TargetRriScorer` evaluates
a selected target crop and may retain diagnostic scene RRI from the same
candidate renders.

Expected target-evidence failures return stable invalidity reasons suitable for
hard masks and diagnostics. They do not become numeric RRI targets.

## Ownership Map

| Module | Responsibility |
| --- | --- |
| `evidence` | Privileged root/current point clouds, target crops, and evaluation provenance. |
| `labels` | Candidate-aligned labels separated from optional retained evidence. |
| `scene_rri` | Scene-level oracle scorer facade. |
| `target_rri` | Target-cropped oracle scorer facade and invalidity. |
| `target_selection` | GT matching and privileged target-task sampling. |
| `environment` | Decision context and actor-visible state transition boundary. |
| `pipelines` | Offline VIN, rollout, shard, campaign, and online-QH composition. |

The private `_scoring.py` engine shares rendering and point-mesh mechanics
between the public scorers; consumers should use the scorer facades.

## Actor/Oracle Boundary

Actor-visible target instructions are defined in `aria_nbv.targets` and may be
stored in `QhActorTensors`. GT meshes, GT OBB matching, dense counterfactual
renders, target crops, oracle labels, and headroom diagnostics remain
supervision/evaluation assets. The distinction is preserved through stores,
QH datasets, bundles, and online inference.

Operational generation commands are documented in the
[pipeline guide](pipelines/README.md). Detailed fields and failure contracts
live in public docstrings and the
[generated API reference](../../../docs/reference/index.qmd).

## Verification

```sh
cd aria_nbv
uv run ruff check aria_nbv/oracle
uv run pytest tests/oracle
```
