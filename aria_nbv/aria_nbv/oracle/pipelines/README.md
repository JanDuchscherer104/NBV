# Oracle Pipelines

`aria_nbv.oracle.pipelines` composes data access, candidate generation,
privileged scoring, replay, and immutable persistence. It does not redefine the
lower-level storage, target, RRI, or scorer contracts.

## Command-Line Workflows

Run from `aria_nbv/`:

| Command | Purpose |
| --- | --- |
| `nbv-build-offline` | Build an immutable one-step VIN store. |
| `nbv-build-rollouts` | Generate one rollout store or one planned shard. |
| `nbv-plan-rollout-shards` | Bind ordered source rows into a shard manifest. |
| `nbv-plan-rollout-source` | Build a source-population manifest. |
| `nbv-status-rollout-shards` | Validate and summarize shard completion. |
| `nbv-rollout-campaign` | Run a bounded resumable rollout campaign. |

Always validate configuration before generation:

```sh
uv run nbv-build-offline \
  --config-path ../.configs/build_vin_offline_81286.toml \
  --dry-run
uv run nbv-build-rollouts \
  --config-path ../.configs/build_rollouts_v1_smoke.toml \
  --dry-run
```

## Composition Boundaries

| Module | Responsibility |
| --- | --- |
| `offline_vin` | Stream raw snippets, prepare expensive evidence, and write VIN rows. |
| `rollout_dataset` | Compose target tasks, candidates, oracle scoring, replay, and store writes. |
| `scene_labels` | Generate scene-level labels over finite candidate tables. |
| `evaluated_rollout` | Bind replay transitions to retained oracle evaluation. |
| `shards` | Plan and atomically promote independent generation shards. |
| `campaign` | Resume bounded local/CUDA campaign work with explicit receipts. |
| `online_vin` | Live one-step oracle dataset for the historical control. |
| `online_qh` | Verify an immutable QH bundle and adapt hard-valid values to replay `CandidateScores`. |

`online_qh` fails closed on actor, learning, target, candidate-generator,
action-mask, representation, geometry, or trained-horizon mismatches. It does
not rank by `P(valid) * Q`; the authoritative hard mask defines deployable
support.

## Verification

```sh
cd aria_nbv
uv run ruff check aria_nbv/oracle/pipelines
uv run pytest tests/rollouts/test_cli_typer.py
uv run pytest tests/oracle/test_online_qh.py
uv run nbv-build-rollouts \
  --config-path ../.configs/build_rollouts_v1_smoke.toml \
  --dry-run
```

Use the [data-handling guide](../../data_handling/README.md) for source/store
preparation and the [rollout guide](../../rollouts/README.md) for persisted
validation and inspection.
