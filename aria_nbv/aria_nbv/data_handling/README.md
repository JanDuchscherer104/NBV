# Data Handling

`aria_nbv.data_handling` is the typed boundary between upstream ASE/ATEK-EFM
assets and ARIA-NBV training or evaluation objects. It owns raw snippet views,
immutable VIN stores, and the finite-horizon join between rollout chains and
their exact actor-visible source rows.

The central invariant is actor/oracle separation:

- Actor-visible state includes observed snippets, calibration and trajectory,
  semidense/EVL evidence, detected targets, finite candidate poses, causal
  history, budget, and masks.
- Privileged supervision includes GT scene/target geometry, oracle candidate
  renders, target-RRI labels, and evaluation crops.
- Invalid candidates are masks plus reason codes, never low-RRI examples.

## Public Entry Points

The package root exports the stable raw-view and immutable-store contracts:
`AseEfmDataset`, `AseEfmDatasetConfig`, `EfmSnippetView`, `VinSnippetView`,
`VinOracleBatch`, `VinOfflineDataset`, `VinOfflineDatasetConfig`, and
`VinOfflineStoreConfig`.

Specialized writer, reader, diagnostic, and QH contracts stay in their leaf
modules:

| Module | Responsibility |
| --- | --- |
| `ase_efm` | Stream typed EFM snippets from ATEK shards. |
| `vin_store` | Immutable indexed one-step evidence stores. |
| `qh_data.views` | Actor tensors, supervision tensors, chain and batch DTOs. |
| `qh_data.dataset` | Validate rollout-to-actor lineage and materialize chains. |
| `qh_data.batching` | Pad complete chains without conflating mask meanings. |

## Two-Store Architecture

![Data-store architecture](../../../docs/figures/diagrams/data_handling/mermaid/data_store_architecture.svg)

The physical stores remain separate:

- `vin_offline` stores expensive immutable one-step substrate such as actor
  blocks, candidate evidence, and optional oracle labels.
- `rollouts.zarr` stores factual multi-step replay, selected observations,
  derived QH rows, and stable references back to VIN source rows.

The current rollout compatibility identifier is
`2.0-target-rollout-provenance`; `ROLLOUT_ZARR_SCHEMA_VERSION` in
`aria_nbv.rollouts.zarr_store` remains the executable owner and the focused QH
test keeps this operator-facing value synchronized.

Raw streams and full meshes remain in their upstream-managed locations. Joined
readers avoid copying those assets or cached backbone blocks into every rollout
row.

## Build and Inspect Data

Run commands from `aria_nbv/`.

Download a bounded ASE/ATEK-EFM subset:

```sh
uv run nbv-downloader -m list -c efm -n 10
uv run nbv-downloader -m download -c efm --ns 1 --max-shards 1
```

Validate a VIN build before writing, then build and inspect it:

```sh
uv run nbv-build-offline \
  --config-path ../.configs/build_vin_offline_81286.toml \
  --dry-run
uv run nbv-build-offline \
  --config-path ../.configs/build_vin_offline_81286.toml
uv run nbv-offline-info summary --store vin_offline
uv run nbv-offline-info tree --store vin_offline
```

Generate and validate a local rollout smoke store:

```sh
uv run nbv-build-rollouts \
  --config-path ../.configs/build_rollouts_v1_smoke.toml \
  --dry-run
uv run nbv-build-rollouts \
  --config-path ../.configs/build_rollouts_v1_smoke.toml
uv run nbv-rollouts-info \
  --store ../.data/offline_cache/rollouts_v1_smoke.zarr \
  --validate
```

Completed stores are immutable inputs. Rebuild incompatible stores with the
current writer; never patch manifests, indices, split arrays, or Zarr payloads
to satisfy validation.

## Materialize a QH Dataset

`QhDatasetConfig` joins one or more ordered rollout stores to one immutable VIN
actor store and preflights every source reference before exposing a chain:

```python
from pathlib import Path

from aria_nbv.data_handling.qh_data import QhDatasetConfig
from aria_nbv.data_handling.vin_store.store import VinOfflineStoreConfig
from aria_nbv.utils import Stage

dataset = QhDatasetConfig(
    rollout_store_dirs=(Path("rollouts-train.zarr"),),
    actor=VinOfflineStoreConfig(store_dir=Path("vin_offline")),
    split=Stage.TRAIN,
    root_evl_profile="evl_v1",
    selected_observation_protocol="none",
    experiment_profile="qh_cf0_v1",
).setup_target()

chain = dataset[0]
actor = chain.actor
supervision = chain.supervision
```

`QhActorTensors` contains only scorer-legal evidence. `QhSupervision` contains
labels, selected-transition facts, and masks used by the objective. Audit
metadata remains CPU-only and outside device transfer.

## Inspection

Use the lightweight CLIs for manifest and table checks, Streamlit for
operational browsing, and Rerun for spatial evidence:

```sh
uv run nbv-st
uv run nbv-rerun-inspect \
  --config-path ../.configs/rerun_offline.toml \
  --rollout-store ../.data/offline_cache/rollouts_v1_smoke.zarr \
  --rollout-index 0 \
  --rollout-context required \
  --spawn
```

## Troubleshooting

- **Store version mismatch:** rebuild with the current writer; readers fail
  closed and intentionally provide no migration facade.
- **Missing manifest or lineage:** treat the artifact as partial or stale and
  regenerate it from the bound source store.
- **Existing destination:** choose a new immutable output path. Use overwrite
  only for a deliberately disposable smoke artifact.
- **QH source mismatch:** rebuild the actor and rollout corpus from the same
  source manifest and split identity.
- **Selected-depth mismatch:** use a compatible experiment profile; CF0 and the
  privileged CF+ selected-depth profile are separate contracts.

## Detailed Contracts and Verification

Field shapes, frames, masks, and lifecycle rules live in public docstrings and
the [generated API reference](../../../docs/reference/index.qmd). Rollout
persistence is documented by the [rollout guide](../rollouts/README.md).

```sh
cd aria_nbv
uv run ruff check aria_nbv/data_handling
uv run pytest tests/data_handling/test_vin_offline_store.py
uv run pytest tests/data_handling/test_public_api_contract.py
uv run pytest tests/data_handling/test_qh.py
```
