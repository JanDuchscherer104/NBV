# Targets

`aria_nbv.targets` owns actor-safe semantic target instructions. It must not
contain GT row ids, matching scores, crop state, oracle validity, RRI labels,
or persisted-store details. Privileged target-task construction belongs to
`aria_nbv.oracle.target_selection`.

## Layout

```text
targets/
  __init__.py
  descriptor.py
```

Baseline: `4daf9d4`

## Symbol Ownership Matrix

### `__init__.py`

No top-level AST definitions; imported names and `__all__` are excluded.

### `descriptor.py`

| Symbol | Kind | Visibility | Before module | Current module | Final owner | Status |
|---|---|---|---|---|---|---|
| `TargetDescriptor` | DTO | public | none | `targets.descriptor` | `targets.descriptor` | moved |

## Target State

The package remains deliberately shallow. A future actor-visible selector may
live in `targets.selection` only when it consumes observed evidence and returns
`TargetDescriptor`; Oracle task sampling must not migrate here.
