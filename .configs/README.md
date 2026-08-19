# Rollout campaign configuration inventory

These are the reviewed operator entry points. Paths are repository-relative and
are resolved from the current checkout; generated manifests and stores are not
committed here. The V8 source-store identity is immutable and intentionally
fresh: `vin_offline_rollout_campaign100_v8_rebuilt`.

| Config | Role | Depends on |
| --- | --- | --- |
| `build_rollouts_v1_cuda_campaign.toml` | Broad 100-scene CUDA campaign | `build_rollouts_v1_cuda_campaign_writer.toml` |
| `build_rollouts_v1_cuda_campaign_pilot_corrected_v10.toml` | Corrected paired pilot | `build_rollouts_v1_cuda_campaign_writer.toml` |
| `build_rollouts_v1_cuda_campaign_writer.toml` | Local 100-row generation writer | `rollout_campaign100_source_manifest.json` and local VIN source store |
| `build_vin_offline_rollout_campaign100_v8.toml` | Local 100-row V8 source-store build | VIN source shards listed in the file |
| `build_rollouts_v1_lrz.template.toml` | LRZ generation template | Replace `/ABS/PATH/TO/...` placeholders |

## Exact operator commands

Prepare the checkout, then build the reviewed V8 source store and bootstrap the
portable source manifest directly from the writer TOML:

```bash
scripts/setup_worktree_env.sh --check
source .env
cd aria_nbv
uv run nbv-build-offline --config-path ../.configs/build_vin_offline_rollout_campaign100_v8.toml
uv run nbv-plan-rollout-source \
  --config-path ../.configs/build_rollouts_v1_cuda_campaign_writer.toml \
  --output-manifest ../.configs/rollout_campaign100_source_manifest.json
```

The source-manifest command is a required post-build reconciliation step: it
refreshes the source cache version, source-store basename, row hash, and split
hash from the newly promoted immutable store. Do not launch a campaign using a
pre-build copy of the tracked manifest. The committed manifest is the reviewed
baseline; after regeneration, update the writer's `source_offline_store_version`
and `split_manifest_hash` fields before planning:

```bash
uv run python - <<'PY'
import json
from pathlib import Path
m = json.loads(Path('../.configs/rollout_campaign100_source_manifest.json').read_text())
print('source_offline_store_version =', repr(m['source_cache_version']))
print('split_manifest_hash =', repr(m['split_manifest_hash']))
PY
```

Plan the corrected paired pilot, run its smoke, launch at most ten new units,
and inspect status:

```bash
uv run nbv-rollout-campaign plan \
  --config-path ../.configs/build_rollouts_v1_cuda_campaign_pilot_corrected_v10.toml \
  --source-manifest ../.configs/rollout_campaign100_source_manifest.json
uv run nbv-rollout-campaign smoke \
  --config-path ../.configs/build_rollouts_v1_cuda_campaign_pilot_corrected_v10.toml
uv run nbv-rollout-campaign run \
  --config-path ../.configs/build_rollouts_v1_cuda_campaign_pilot_corrected_v10.toml \
  --plan-path .campaign/cuda-rollouts-v1-pilot-corrected-v10/plan.json \
  --max-new-units 10
uv run nbv-rollout-campaign status \
  --config-path ../.configs/build_rollouts_v1_cuda_campaign_pilot_corrected_v10.toml
```
