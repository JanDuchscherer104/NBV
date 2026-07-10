# Raw Data

`aria_nbv.data_handling.raw` owns ASE/EFM dataset access and on-demand snippet loading. Shared view DTOs and dataset identifier helpers remain at the parent until their future symbol-level split.

## Layout

```text
data_handling/raw/
  __init__.py   # stable raw-access facade
  dataset.py
  loader.py
```

Baseline: `6b72b62639e24fc13bba845ec63bc8fc72c77aae`

Inventory generated: `2026-07-10T16:27:20.693866+00:00`

Graphify refresh: `2026-07-10T18:34:29+02:00`

## Symbol Ownership Matrix

### `__init__.py`

No top-level AST definitions; imported names and `__all__` are excluded.

### `dataset.py`

| Symbol                | Kind     | Visibility | Before module               | Mechanical module           | Final owner                 | Status  |
| --------------------- | -------- | ---------- | --------------------------- | --------------------------- | --------------------------- | ------- |
| `AseEfmDatasetConfig` | `config` | `public`   | `data_handling.efm_dataset` | `data_handling.raw.dataset` | `data_handling.raw.dataset` | `moved` |
| `AseEfmDataset`       | `class`  | `public`   | `data_handling.efm_dataset` | `data_handling.raw.dataset` | `data_handling.raw.dataset` | `moved` |

### `loader.py`

| Symbol             | Kind    | Visibility | Before module                      | Mechanical module          | Final owner                | Status  |
| ------------------ | ------- | ---------- | ---------------------------------- | -------------------------- | -------------------------- | ------- |
| `EfmSnippetLoader` | `class` | `public`   | `data_handling.efm_snippet_loader` | `data_handling.raw.loader` | `data_handling.raw.loader` | `moved` |

<!-- Start READ-ONLY: Code Owner Notes -->
# Code Owner Notes
- any handling of the initial ASE / EFM / ATEK datasets should be handeled in a submodule of data_handling. today raw only contains datasets.py and loader.py but not efm_views, efm_dataset_utils, ... also dataset.py is too broad. should be one file per specific dataset - i.e. atek_efm_dataset.py

<!-- End READ-ONLY -->
