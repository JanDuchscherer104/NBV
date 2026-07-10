# Pipelines

`aria_nbv.pipelines` is a temporary package containing the scene-label pipeline that still depends on flat oracle/RRI surfaces. It is intentionally not moved in this mechanical pass.

## Layout

```text
pipelines/
  oracle_rri_labeler.py  # future oracle.pipelines.scene_labels
```

Baseline: `6b72b62639e24fc13bba845ec63bc8fc72c77aae`

Inventory generated: `2026-07-10T16:10:28.231382+00:00`

Graphify refresh: `2026-07-10T18:34:29+02:00`

## Symbol Ownership Matrix

### `__init__.py`

No top-level AST definitions; imported names and `__all__` are excluded.

### `oracle_rri_labeler.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `OracleRriSample` | `DTO` | `public` | `pipelines.oracle_rri_labeler` | `pipelines.oracle_rri_labeler` | `oracle.pipelines.scene_labels` | `deferred: semantic WP` |
| `_target_cls` | `function` | `private` | `pipelines.oracle_rri_labeler` | `pipelines.oracle_rri_labeler` | `oracle.pipelines.scene_labels` | `deferred: semantic WP` |
| `OracleRriLabelerConfig` | `config` | `public` | `pipelines.oracle_rri_labeler` | `pipelines.oracle_rri_labeler` | `oracle.pipelines.scene_labels` | `deferred: semantic WP` |
| `OracleRriLabeler` | `class` | `public` | `pipelines.oracle_rri_labeler` | `pipelines.oracle_rri_labeler` | `oracle.pipelines.scene_labels` | `deferred: semantic WP` |
