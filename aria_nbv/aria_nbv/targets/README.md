# Targets

`aria_nbv.targets` owns actor-safe target instructions. It converts observed
detector OBBs into stable descriptors without carrying ground-truth rows,
matching diagnostics, labels, gains, or rollout storage details.

## Public API

```python
from aria_nbv.targets import observed_target_descriptors

observed = observed_target_descriptors(vin_offline_sample)
valid = tuple(item.descriptor for item in observed if item.descriptor is not None)
```

`TargetDescriptor` contains semantic identity, object pose, full metric
extents, and the object pose relative to the snippet reference rig.
`ObservedTargetDescriptor` additionally retains actor-visible source identity,
confidence, and a provenance hash.

## Ownership Boundary

- `targets.selection` reads detected OBBs only and preserves their source-row
  ordering.
- `targets.protocol` defines the target-input protocol and label-evidence
  admission vocabulary used by stores and QH readers.
- `oracle.target_selection` performs privileged GT matching and task sampling.
- Oracle labels, crop geometry, invalidity, and rollout persistence never enter
  `TargetDescriptor`.

The detailed field and frame contracts live in the public docstrings and
[generated API reference](../../../docs/reference/index.qmd).

## Verification

```sh
cd aria_nbv
uv run ruff check aria_nbv/targets
uv run pytest tests/targets tests/oracle/test_target_selection.py
```
