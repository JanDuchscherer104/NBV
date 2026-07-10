# Oracle

`aria_nbv.oracle` is the ownership root for privileged scoring inputs and generation pipelines. This move-only pass creates the package boundary without moving scorer implementations.

## Layout

```text
oracle/
  pipelines/
  # scorer/evidence modules remain future semantic WPs
```

Baseline: `6b72b62639e24fc13bba845ec63bc8fc72c77aae`

Inventory generated: `2026-07-10T16:10:28.231382+00:00`

Graphify refresh: `2026-07-10T18:34:29+02:00`

## Symbol Ownership Matrix

### `__init__.py`

No top-level AST definitions; imported names and `__all__` are excluded.
