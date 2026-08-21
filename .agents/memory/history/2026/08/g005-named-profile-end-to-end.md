# G005 named-profile integration proof

## Task

Prove both named Q_H profiles preserve the actor allowlist through collation,
CPU transfer, DataModule admission, and module contract/hash admission; inspect
the changed seams for a behavior-preserving simplification.

## Method

Added a parametrized focused test for `qh_cf0_v1` and
`qh_cfplus_gt_depth_v1`. Each case constructs the typed actor contract, builds
the first collated batch, transfers it to CPU, checks that supervision-only RRI
fields are not actor attributes, and reconstructs module admission against the
DataModule contract/hash. Searched changed seams with `rg` for one-use aliases,
duplicate branches, and forwarding wrappers before deciding whether a cleanup
was safe.

## Findings

The named profile, actor contract hash, and optional CF+ geometry hash are
already canonical owners. No redundant production alias or branch could be
removed without widening compatibility or changing the public contract; the
simplification pass was therefore a deliberate no-op.

## Verification

- `tests/data_handling/test_qh.py -k named_profile_batch`: 2 passed.
- Existing G004 combined Q_H/reader/DataModule/module/rendering matrix: 141 passed.
- Ruff, compileall, and diff-check run on the final changed seams.
- Physical VIN-v9/rollout-Zarr fixture: 2 profile cases passed through final
  readers, dataset, DataModule, `pin_memory`, CPU batch transfer, and module
  admission; complete supervision/audit exclusion was checked on the actor.

## Canonical impact

Only the focused test seam and this debrief changed. Production ownership and
schema remain unchanged; RRI/audit data remains outside actor tensors.
A physical VIN-v9/rollout-Zarr fixture rewrites final actor source identity and
the production split-manifest hash before writing the rollout root. CF0 reads
the same rollout without selected depth while CF+ admits validated selected
depth.
