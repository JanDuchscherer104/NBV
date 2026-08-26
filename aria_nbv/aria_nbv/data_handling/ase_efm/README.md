# ASE/ATEK-EFM Input

`aria_nbv.data_handling.ase_efm` streams tensorized ASE snippets from ATEK
WebDataset shards and presents them as typed EFM views. It is the live input
used by candidate generation, immutable VIN-store construction, and small
rollout-generation smoke tests.

ATEK shards carry calibrated observations, trajectory, and MPS semidense
points. Optional ASE meshes and GT annotations are attached as oracle/evaluation
assets and must not become ordinary actor inputs.

## Read Snippets

```python
from aria_nbv.data_handling.ase_efm import AseEfmDatasetConfig

dataset = AseEfmDatasetConfig(
    scene_ids=["81286"],
    load_meshes=True,
    require_mesh=True,
    device="cpu",
).setup_target()

snippet = next(iter(dataset))
print(snippet.scene_id, snippet.snippet_id)
```

`AseEfmDatasetConfig` resolves scene, shard, and sample filters; applies the
ATEK-to-EFM taxonomy; and optionally pairs ASE meshes. `EfmSnippetView` exposes
typed camera, trajectory, semidense-point, OBB, and GT surfaces without adding
a parallel field schema. `EfmSnippetLoader` is the worker-local adapter for
reattaching a known raw snippet to an immutable store row.

Use the downloader before constructing the dataset:

```sh
cd aria_nbv
uv run nbv-downloader -m list -c efm -n 10
uv run nbv-downloader -m download -c efm --ns 1 --max-shards 1
```

Detailed field, frame, and padding contracts live in the module docstrings and
[generated API reference](../../../../docs/reference/index.qmd).

## Verification

```sh
cd aria_nbv
uv run ruff check aria_nbv/data_handling/ase_efm
uv run pytest tests/data_handling/test_efm_dataset_snippet.py \
  tests/data_handling/test_efm_snippet_loader.py
```
