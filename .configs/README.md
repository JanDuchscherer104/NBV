# Rollout campaign configuration inventory

These are the reviewed operator entry points. Paths are repository-relative and
are resolved from the current checkout; generated stores are not committed
here. The current strict source-store identity is
`vin_offline_rollout_campaign100_v10_rebuilt`. Existing corrected-V10 rollout
shards remain immutable historical artifacts because they were generated from
the V8 source manifest; the corrected-V11 campaign is a historical V10-bound
rollout destination. The writer and LRZ template are the canonical production
profiles and use seminar view jitter (60° azimuth, 30° elevation, 0° roll).
The corrected-V11 plan preserves the V10 source-manifest identity and the
selected five-snippet/two-profile/four-temperature workload shape only. It
delegates to the canonical writer, so rerunning it now uses seminar 60°/30°/0°
and does not reproduce historical plan/work-unit IDs or the historical
zero-jitter candidate contract. Historical plan/work-unit/generation hashes are
revision-bound evidence, not current rerun identities.
That historical zero-jitter fact/config is revision-bound to PR116 commit
`52e9d262577260074bae25134fbd61c2bfda0533`.

| Config | Role | Depends on |
| --- | --- | --- |
| `build_rollouts_v1_cuda_campaign.toml` | Broad 100-scene CUDA campaign | `build_rollouts_v1_cuda_campaign_writer.toml` |
| `build_rollouts_v1_cuda_campaign_pilot_corrected_v11.toml` | Current V10-bound corrected paired pilot | `build_rollouts_v1_cuda_campaign_writer.toml` |
| `build_rollouts_v1_cuda_campaign_writer.toml` | Local 100-row generation writer | `rollout_campaign100_source_manifest.json` and local VIN source store |
| `build_vin_offline_rollout_campaign100_v10.toml` | Current strict-V10 source-store build | VIN source shards listed in the file |
| `build_vin_offline_rollout_campaign100_v8.toml` | Historical immutable reviewed V8 source-store build (non-current) | VIN source shards listed in the file |
| `build_rollouts_v1_lrz.template.toml` | LRZ generation template | Replace `/ABS/PATH/TO/...` placeholders |

## Exact operator commands

Prepare the checkout, then build the reviewed V10 source store and bootstrap the
portable source manifest directly from the writer TOML:

```bash
scripts/setup_worktree_env.sh --check
source .env
cd aria_nbv
uv run nbv-build-offline --config-path ../.configs/build_vin_offline_rollout_campaign100_v10.toml
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
  --config-path ../.configs/build_rollouts_v1_cuda_campaign_pilot_corrected_v11.toml \
  --source-manifest ../.configs/rollout_campaign100_source_manifest.json
uv run nbv-rollout-campaign smoke \
  --config-path ../.configs/build_rollouts_v1_cuda_campaign_pilot_corrected_v11.toml
uv run nbv-rollout-campaign run \
  --config-path ../.configs/build_rollouts_v1_cuda_campaign_pilot_corrected_v11.toml \
  --plan-path .campaign/cuda-rollouts-v1-pilot-corrected-v11/plan.json \
  --max-new-units 10
uv run nbv-rollout-campaign status \
  --config-path ../.configs/build_rollouts_v1_cuda_campaign_pilot_corrected_v11.toml
```
