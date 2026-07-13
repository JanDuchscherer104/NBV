# Pipelines

`aria_nbv.pipelines` is an empty package marker retained only until the
stale-path and packaging audit deletes it. Active label and generation
pipelines live under `aria_nbv.oracle.pipelines`.

## Layout

```text
pipelines/
  __init__.py
```

Baseline: `6b72b62639e24fc13bba845ec63bc8fc72c77aae`

Inventory generated: `2026-07-10T16:10:28.231382+00:00`

Graphify refresh: `2026-07-10T18:34:29+02:00`

## Symbol Ownership Matrix

### `__init__.py`

No top-level AST definitions; imported names and `__all__` are excluded.

### Moved symbols

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `OracleRriSample` | `DTO` | `public leaf` | `pipelines.oracle_rri_labeler` | `oracle.pipelines.scene_labels` | `oracle.pipelines.scene_labels` | `moved` |
| `_target_cls` | `function` | `private` | `pipelines.oracle_rri_labeler` | `oracle.pipelines.scene_labels` | `oracle.pipelines.scene_labels` | `moved` |
| `OracleRriLabelerConfig` | `config` | `public leaf` | `pipelines.oracle_rri_labeler` | `oracle.pipelines.scene_labels` | `oracle.pipelines.scene_labels` | `moved` |
| `OracleRriLabeler` | `class` | `public leaf` | `pipelines.oracle_rri_labeler` | `oracle.pipelines.scene_labels` | `oracle.pipelines.scene_labels` | `moved` |
