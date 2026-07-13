# Raw Data

`aria_nbv.data_handling.raw` owns live ASE/ATEK-to-EFM access. `dataset.py`
resolves shards and yields snippets, `loader.py` performs worker-local lookup,
and `views.py` owns typed zero-copy payload views. Shared string identifier
conversion lives one level up in `data_handling.identifiers`.

## Layout

```text
raw/
  __init__.py
  dataset.py
  loader.py
  views.py
```

Baseline: `14e1f5f`

Inventory refreshed: `2026-07-13`

Graphify refresh: `2026-07-13`

## Symbol Ownership Matrix

### `__init__.py`

No top-level AST definitions; imported names and `__all__` are excluded.

### `dataset.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `_infer_ids` | function | private | `data_handling.efm_dataset_utils` | `data_handling.raw.dataset` | `data_handling.raw.dataset` | moved |
| `_unique_preserve_order` | function | private | `data_handling.efm_dataset_utils` | `data_handling.raw.dataset` | `data_handling.raw.dataset` | moved |
| `_looks_like_shard_id` | function | private | `data_handling.efm_dataset_utils` | `data_handling.raw.dataset` | `data_handling.raw.dataset` | moved |
| `_normalize_shard_stem` | function | private | `data_handling.efm_dataset_utils` | `data_handling.raw.dataset` | `data_handling.raw.dataset` | moved |
| `_matches_snippet_token` | function | private | `data_handling.efm_dataset_utils` | `data_handling.raw.dataset` | `data_handling.raw.dataset` | moved |
| `_tar_contains_snippet` | function | private | `data_handling.efm_dataset_utils` | `data_handling.raw.dataset` | `data_handling.raw.dataset` | moved |
| `_resolve_tar_from_path` | function | private | `data_handling.efm_dataset_utils` | `data_handling.raw.dataset` | `data_handling.raw.dataset` | moved |
| `_resolve_tar_for_shard` | function | private | `data_handling.efm_dataset_utils` | `data_handling.raw.dataset` | `data_handling.raw.dataset` | moved |
| `_find_tar_for_sample` | function | private | `data_handling.efm_dataset_utils` | `data_handling.raw.dataset` | `data_handling.raw.dataset` | moved |
| `_split_snippet_ids` | function | private | `data_handling.efm_dataset_utils` | `data_handling.raw.dataset` | `data_handling.raw.dataset` | moved |
| `_tensor3` | function | private | `data_handling.efm_dataset_utils` | `data_handling.raw.dataset` | `data_handling.raw.dataset` | moved |
| `infer_semidense_bounds` | function | public | `data_handling.efm_dataset_utils` | `data_handling.raw.dataset` | `data_handling.raw.dataset` | moved |
| `AseEfmDatasetConfig` | config | public | `data_handling.efm_dataset` | `data_handling.raw.dataset` | `data_handling.raw.dataset` | already aligned |
| `AseEfmDataset` | class | public | `data_handling.efm_dataset` | `data_handling.raw.dataset` | `data_handling.raw.dataset` | already aligned |

### `loader.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `EfmSnippetLoader` | class | public | `data_handling.efm_snippet_loader` | `data_handling.raw.loader` | `data_handling.raw.loader` | already aligned |

### `views.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `_FIELD_DOC_CACHE` | constant | private | `data_handling.efm_views` | `data_handling.raw.views` | `data_handling.raw.views` | moved |
| `_extract_field_docs` | function | private | `data_handling.efm_views` | `data_handling.raw.views` | `data_handling.raw.views` | moved |
| `_get_field_doc` | function | private | `data_handling.efm_views` | `data_handling.raw.views` | `data_handling.raw.views` | moved |
| `_repr` | function | private | `data_handling.efm_views` | `data_handling.raw.views` | `data_handling.raw.views` | moved |
| `BaseView` | class | public | `data_handling.efm_views` | `data_handling.raw.views` | `data_handling.raw.views` | moved |
| `EfmGtCameraObbView` | DTO | public | `data_handling.efm_views` | `data_handling.raw.views` | `data_handling.raw.views` | moved |
| `CamerasDict` | alias | public | `data_handling.efm_views` | `data_handling.raw.views` | `data_handling.raw.views` | moved |
| `EfmGtTimestampView` | DTO | public | `data_handling.efm_views` | `data_handling.raw.views` | `data_handling.raw.views` | moved |
| `EfmGTView` | DTO | public | `data_handling.efm_views` | `data_handling.raw.views` | `data_handling.raw.views` | moved |
| `EfmCameraView` | DTO | public | `data_handling.efm_views` | `data_handling.raw.views` | `data_handling.raw.views` | moved |
| `EfmTrajectoryView` | DTO | public | `data_handling.efm_views` | `data_handling.raw.views` | `data_handling.raw.views` | moved |
| `EfmPointsView` | DTO | public | `data_handling.efm_views` | `data_handling.raw.views` | `data_handling.raw.views` | moved |
| `EfmObbView` | DTO | public | `data_handling.efm_views` | `data_handling.raw.views` | `data_handling.raw.views` | moved |
| `EfmSnippetView` | DTO | public | `data_handling.efm_views` | `data_handling.raw.views` | `data_handling.raw.views` | moved |
| `VinSnippetView` | DTO | public | `data_handling.efm_views` | `data_handling.raw.views` | `data_handling.raw.views` | moved |
| `is_efm_snippet_view_instance` | function | public | `data_handling.efm_views` | `data_handling.raw.views` | `data_handling.raw.views` | moved |
| `is_vin_snippet_view_instance` | function | public | `data_handling.efm_views` | `data_handling.raw.views` | `data_handling.raw.views` | moved |
