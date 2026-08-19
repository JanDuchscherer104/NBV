# Rollout campaign configuration inventory

These are the reviewed operator entry points. Paths are repository-relative and
are resolved from the current checkout; generated manifests and stores are not
committed here.

| Config | Role | Depends on |
| --- | --- | --- |
| `build_rollouts_v1_cuda_campaign.toml` | Broad 100-scene CUDA campaign | `build_rollouts_v1_cuda_campaign_writer.toml` |
| `build_rollouts_v1_cuda_campaign_pilot_corrected_v2.toml` | Corrected paired pilot | `build_rollouts_v1_cuda_campaign_writer.toml` |
| `build_rollouts_v1_cuda_campaign_writer.toml` | Local 100-row generation writer | `rollout_campaign100_source_manifest.json` and local VIN source store |
| `build_vin_offline_rollout_campaign100_v8.toml` | Local 100-row V8 source-store build | VIN source shards listed in the file |
| `build_rollouts_v1_lrz.template.toml` | LRZ generation template | Replace `/ABS/PATH/TO/...` placeholders |

## Exact operator commands

From the repository root, review the source rows directly from the writer TOML:

```bash
uv run nbv-plan-rollout-shards source-manifest \
  --config-path .configs/build_rollouts_v1_cuda_campaign_writer.toml \
  --output-manifest .configs/rollout_campaign100_source_manifest.json
```

Plan profile-specific shards without building stores:

```bash
uv run nbv-plan-rollout-shards \
  --config-path .configs/build_rollouts_v1_cuda_campaign_writer.toml \
  --output-manifest .campaign/cuda-rollouts-v1/shards.jsonl \
  --rows-per-shard 1
```

Run campaign gates and the bounded smoke before launch:

```bash
uv run nbv-rollout-campaign preflight --config-path .configs/build_rollouts_v1_cuda_campaign.toml
uv run nbv-rollout-campaign plan --config-path .configs/build_rollouts_v1_cuda_campaign.toml \
  --source-manifest .configs/rollout_campaign100_source_manifest.json
uv run nbv-rollout-campaign smoke --config-path .configs/build_rollouts_v1_cuda_campaign.toml \
  --plan-path .campaign/cuda-rollouts-v1/plan.json
```
