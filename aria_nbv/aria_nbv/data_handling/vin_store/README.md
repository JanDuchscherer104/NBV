# Immutable VIN Store

`aria_nbv.data_handling.vin_store` persists expensive one-step evidence as an
indexed, manifest-bound, immutable dataset. It is the source substrate for
one-step VIN training, rollout generation, QH actor joins, and inspection.

## Store Layout

```text
vin_offline/
  manifest.json
  sample_index.jsonl
  splits/
    all.npy
    train.npy
    val.npy
  shards/
    shard-000000/
      numeric_blocks.zarr/
      records.msgpack
      records_offsets.npy
```

The manifest binds format version, source configuration, materialized blocks,
feature provenance, and shard identities. `sample_index.jsonl` maps stable
global rows to scene, snippet, split, shard, and shard-local row. Readers reject
unsupported versions and never migrate or repair a store in place.

## Build and Inspect

```sh
cd aria_nbv
uv run nbv-build-offline \
  --config-path ../.configs/build_vin_offline_81286.toml \
  --dry-run
uv run nbv-build-offline \
  --config-path ../.configs/build_vin_offline_81286.toml

uv run nbv-offline-info summary --store vin_offline
uv run nbv-offline-info tree --store vin_offline
uv run nbv-offline-info samples --store vin_offline --split train --limit 5
```

The writer owns manifests, indices, split arrays, shards, and optional records.
If the destination already exists, choose a new output path unless deliberately
replacing a disposable smoke store.

## Read Samples

```python
from pathlib import Path

from aria_nbv.data_handling import VinOfflineDatasetConfig
from aria_nbv.data_handling.vin_store.store import VinOfflineStoreConfig
from aria_nbv.utils import Stage

dataset = VinOfflineDatasetConfig(
    store=VinOfflineStoreConfig(store_dir=Path("vin_offline")),
    split=Stage.TRAIN,
    return_format="sample",
    load_backbone=True,
    load_candidates=True,
).setup_target()

sample = dataset[0]
```

Use `return_format="vin_batch"` for the one-step training DTO. QH joins use
`VinOfflineStoreReader.read_actor_snippet()` internally and deliberately decode
only actor-visible blocks needed by `QhActorTensors`.

## Ownership

| Module | Responsibility |
| --- | --- |
| `format` | Manifest, index, shard, and materialized-block schema. |
| `writer` | Atomic construction of new immutable stores. |
| `store` | Strict read-only manifest, split, and shard access. |
| `dataset` | User-facing indexed dataset and return-format selection. |
| `batch` | One-step VIN training DTOs. |
| `views` | Actor-visible typed snippet projection. |
| `diagnostics` / `inventory` | Read-only summaries and coverage. |
| `info_cli` | Human- and JSON-readable store inspection. |

Detailed tensor fields and lifecycle failures live in public docstrings and the
[generated API reference](../../../../docs/reference/index.qmd).

## Verification

```sh
cd aria_nbv
uv run ruff check aria_nbv/data_handling/vin_store
uv run pytest tests/data_handling/test_vin_offline_store.py
uv run pytest tests/data_handling/test_public_api_contract.py
```
